"""Transactional offers and idempotent subjective decisions for V5.1.

Only completed answers enter projections. Pending offers are resumed, not appended
on refresh. Unanswered/skipped receipts expire after seven days; answered facts
remain compact and losslessly exportable. This module has no Flask dependency.
"""
import hashlib
import json
import random
import secrets
import time

from songranker.modes import shared_spotlight, vibe_map
from songranker.modes.preferences import transaction, owner_hash
from songranker.modes.judgement_selection import draw

MODES = {m.KEY: m for m in (shared_spotlight, vibe_map)}
SLUGS = {'shared-spotlight': 'spotlight', 'vibe-map': 'vibe'}
RETENTION_SECONDS = 7 * 86400


class JudgementError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message); self.status = status


def mode_key(value):
    key = SLUGS.get(value, value) if isinstance(value, str) else None
    if key not in MODES:
        raise JudgementError('Unknown V5.1 mode.', 404)
    return key


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def available(conn):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name='judgement_rounds' AND type='table'").fetchone())


def identity(conn, sid):
    row = conn.execute('SELECT title FROM songs WHERE id=?', (sid,)).fetchone()
    artists = ', '.join(r[0] for r in conn.execute('''SELECT a.name FROM artists a
        JOIN song_artists s ON s.artist_id=a.id WHERE s.song_id=? ORDER BY a.id''', (sid,)))
    result = dict(title=row[0][:160], artist=artists[:160])
    while len(compact(result)) > 512:
        result = {k: v[:max(1,len(v)//2)] for k, v in result.items()}
    return compact(result)


def songs_for(conn, round_id):
    items = conn.execute('SELECT * FROM judgement_items WHERE round_id=? ORDER BY slot', (round_id,)).fetchall()
    result = []
    for item in items:
        saved = json.loads(item['identity'])
        live = conn.execute('''SELECT s.id,s.title,s.audio_url,a.id album_id,a.title album,a.cover_url
            FROM songs s LEFT JOIN albums a ON a.id=s.album_id WHERE s.id=?''', (item['song_id'],)).fetchone()
        song = dict(live) if live else dict(id=None, title=saved['title'], audio_url=None, album=None, album_id=None, cover_url=None)
        song.update(slot=item['slot'], song_key=item['song_key'], saved_title=saved['title'], saved_artist=saved['artist'])
        song['artists'] = [dict(r) for r in conn.execute('''SELECT a.id,a.name FROM artists a
            JOIN song_artists s ON s.artist_id=a.id WHERE s.song_id=? ORDER BY a.id''', (item['song_id'],))] if live else []
        result.append(song)
    return result


def result(conn, row):
    answer = dict(id=row['id'], token=row['token'], mode=row['mode'], rules_version=row['rules_version'],
                  status=row['status'], created_at=row['created_at'], closed_at=row['closed_at'])
    if row['status'] == 'answered':
        if row['mode'] == 'spotlight':
            values = [r[0] for r in conn.execute('SELECT points FROM spotlight_allocations WHERE round_id=? ORDER BY slot', (row['id'],))]
            answer.update(allocations=values, support=[shared_spotlight.support(p) for p in values])
        elif row['mode'] == 'vibe':
            answer['maps'] = [dict(map=r['map_key'],x=r['x'],y=r['y']) for r in conn.execute('SELECT * FROM vibe_placements WHERE round_id=? ORDER BY map_key', (row['id'],))]
            if row['themes_reviewed']:
                answer['themes'] = [dict(id=r['tag_id'],tag_key=r['tag_key'],label=r['label']) for r in conn.execute('SELECT * FROM vibe_themes WHERE round_id=? ORDER BY tag_key', (row['id'],))]
    return answer


def get_offer(conn, owner, mode, rng=random, *, now=None):
    mode = mode_key(mode); spec = MODES[mode]; now = time.time() if now is None else now
    if not isinstance(owner, str) or not owner:
        raise JudgementError('A browser owner is required.')
    hashed = owner_hash(owner)
    with transaction(conn):
        # Bounded abandoned/skipped storage; successful receipts are never pruned.
        conn.execute("DELETE FROM judgement_rounds WHERE status!='answered' AND created_at<?", (now-RETENTION_SECONDS,))
        row = conn.execute("SELECT * FROM judgement_rounds WHERE owner_hash=? AND mode=? AND status='open'", (hashed, mode)).fetchone()
        if row:
            valid = conn.execute("""SELECT COUNT(*) FROM judgement_items i JOIN songs s ON s.id=i.song_id
                WHERE i.round_id=? AND TRIM(COALESCE(s.audio_url,''))!=''""", (row['id'],)).fetchone()[0]
            if valid != spec.SONGS:
                conn.execute('DELETE FROM judgement_rounds WHERE id=?', (row['id'],)); row = None
        if row is None:
            try: ids = draw(conn, mode, hashed, spec.SONGS, rng)
            except ValueError as error: raise JudgementError(str(error), 409) from error
            token = secrets.token_urlsafe(32)
            cursor = conn.execute('INSERT INTO judgement_rounds(token,owner_hash,mode,created_at) VALUES(?,?,?,?)', (token,hashed,mode,now))
            rid = cursor.lastrowid
            conn.executemany('INSERT INTO judgement_items VALUES(?,?,?,?,?)',
                [(rid,slot,sid,sid,identity(conn,sid)) for slot,sid in enumerate(ids)])
            row = conn.execute('SELECT * FROM judgement_rounds WHERE id=?', (rid,)).fetchone()
        answer = result(conn, row); answer['songs'] = songs_for(conn, row['id'])
        if mode == 'spotlight': answer['points'] = shared_spotlight.POINTS
        if mode == 'vibe':
            sid = answer['songs'][0]['id']
            seen = dict(conn.execute("""SELECT v.map_key,COUNT(*) FROM vibe_placements v
                JOIN judgement_items i ON i.round_id=v.round_id AND i.slot=0
                JOIN judgement_rounds r ON r.id=v.round_id WHERE i.song_id=?
                AND r.status='answered' GROUP BY v.map_key""", (sid,)))
            answer['suggested_maps'] = [m['key'] for m in sorted(vibe_map.MAPS,key=lambda m:seen.get(m['key'],0))]
        return answer


def normalized(mode, payload):
    if not isinstance(payload, dict): raise JudgementError('Send a JSON object.')
    common = {'token','rules_version','skip','listening'}
    fields = {'spotlight': {'allocations'}, 'vibe': {'maps','themes'}}[mode]
    if set(payload)-common-fields: raise JudgementError('Unsupported fields for this mode.')
    version = payload.get('rules_version', 1)
    if type(version) is not int or version != 1: raise JudgementError('Unsupported rules version; reload the round.', 409)
    skip = payload.get('skip', False)
    if type(skip) is not bool: raise JudgementError('Skip must be true or false.')
    if skip:
        if fields & set(payload): raise JudgementError('A skipped round cannot also have an answer.')
        return dict(skip=True)
    try:return dict(skip=False, **MODES[mode].validate(payload))
    except ValueError as error:raise JudgementError(str(error)) from error


def save_answer(conn, owner, mode, payload, *, now=None):
    mode = mode_key(mode); answer = normalized(mode, payload)
    token = payload.get('token')
    if not isinstance(token, str) or not 32 <= len(token) <= 64: raise JudgementError('Use the offered round token.')
    if not isinstance(owner, str) or not owner: raise JudgementError('Open this round in the current browser.',403)
    fingerprint = hashlib.sha256(compact(answer).encode()).hexdigest()
    with transaction(conn):
        row = conn.execute('SELECT * FROM judgement_rounds WHERE token=? AND owner_hash=? AND mode=?', (token,owner_hash(owner),mode)).fetchone()
        if row is None: raise JudgementError('This round is not available in the current browser.',404)
        if row['status'] != 'open':
            if row['answer_hash'] != fingerprint: raise JudgementError('This round already has a different saved answer.',409)
            return dict(result(conn,row), replayed=True)
        items = conn.execute('SELECT song_key,song_id FROM judgement_items WHERE round_id=? ORDER BY slot', (row['id'],)).fetchall()
        if len(items) != MODES[mode].SONGS or any(i['song_id'] is None for i in items):
            raise JudgementError('The catalogue changed. Request a new round before answering.',409)
        rid = row['id']
        if not answer['skip']:
            if mode == 'spotlight':
                conn.executemany('INSERT INTO spotlight_allocations VALUES(?,?,?)', [(rid,i,p) for i,p in enumerate(answer['allocations'])])
            elif mode == 'vibe':
                conn.executemany('INSERT INTO vibe_placements VALUES(?,?,?,?)', [(rid,m['map'],m['x'],m['y']) for m in answer['maps']])
                for tid in answer.get('themes', []):
                    tag = conn.execute('SELECT name FROM genres WHERE id=?', (tid,)).fetchone()
                    if tag is None: raise JudgementError('A chosen tag was removed. Review the tags again.',409)
                    conn.execute('INSERT INTO vibe_themes VALUES(?,?,?,?)', (rid,tid,tid,tag[0][:160]))
        closed = max(row['created_at'], time.time() if now is None else now)
        conn.execute('UPDATE judgement_rounds SET status=?,closed_at=?,answer_hash=?,themes_reviewed=? WHERE id=?',
            ('skipped' if answer['skip'] else 'answered',closed,fingerprint,int('themes' in answer),rid))
        if not answer['skip']:
            from songranker.listening import record
            record(conn,mode,rid,[i['song_key'] for i in items],None,payload.get('listening'))
        return dict(result(conn,conn.execute('SELECT * FROM judgement_rounds WHERE id=?',(rid,)).fetchone()), replayed=False)
