"""Read-only Trivia dashboard. Field totals and saved-round records stay distinct."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import isfinite

from catalog import proper_album
from trivia import FIELDS, round_points


def percentage(correct, attempts):
    return round(100 * correct / attempts, 1) if attempts else None


def nonnegative(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def finite(value):
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_recognition_stats(conn, now=None):
    """Use one caller-owned read snapshot, with no history LIMIT on aggregates."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    artists = {r['id']: dict(r) for r in conn.execute('SELECT * FROM artists')}
    albums = {r['id']: dict(r) for r in conn.execute('SELECT * FROM albums')}
    tags = {r['id']: dict(r) for r in conn.execute('SELECT * FROM genres')}
    artist_links, tag_links = defaultdict(set), defaultdict(set)
    for row in conn.execute('SELECT song_id,artist_id FROM song_artists'):
        if row['artist_id'] in artists:
            artist_links[row['song_id']].add(row['artist_id'])
    for row in conn.execute('SELECT song_id,genre_id FROM song_genres'):
        if row['genre_id'] in tags:
            tag_links[row['song_id']].add(row['genre_id'])
    songs = {}
    for row in conn.execute('SELECT * FROM songs'):
        song = dict(row)
        album = albums.get(song['album_id'], {})
        song.update(cover_url=album.get('cover_url') or '',
                    artist_links=sorted((artists[a] for a in artist_links[song['id']]),
                                        key=lambda a: (a['name'].casefold(), a['id'])),
                    album_link=album if proper_album(album) else None)
        songs[song['id']] = song

    fields = [dict(key=key, name=label, kind=kind, attempts=0, correct=0)
              for key, label, kind in [('title', 'Song', 'song'),
                                       ('artist', 'Artist', 'artist'),
                                       ('album', 'Album', 'album')]]
    by_artist, by_album, by_tag = {}, {}, {}
    tested = []

    def add_group(target, identity, attempts, correct, sid):
        if not attempts:
            return
        group = target.setdefault(identity, dict(attempts=0, correct=0, songs=set()))
        group['attempts'] += attempts
        group['correct'] += correct
        group['songs'].add(sid)

    for row in conn.execute('SELECT * FROM trivia_stats'):
        song = songs.get(row['song_id'])
        if not song:
            continue
        attempts = nonnegative(row['new_attempts'])
        if not attempts:
            continue
        opportunities = dict(title=attempts, artist=attempts,
                             album=min(attempts, nonnegative(row['album_attempts'])))
        correct = {key: min(opportunities[key], nonnegative(row[key + '_correct'])) for key in FIELDS}
        available, earned = sum(opportunities.values()), sum(correct.values())
        song.update(attempts=attempts, correct=earned, available=available,
                    accuracy=percentage(earned, available),
                    title_missed=attempts - correct['title'])
        tested.append(song)
        for field in fields:
            key = field['key']
            field['attempts'] += opportunities[key]
            field['correct'] += correct[key]
        for aid in artist_links[song['id']]:
            add_group(by_artist, aid, opportunities['artist'], correct['artist'], song['id'])
        if song['album_link']:
            add_group(by_album, song['album_id'], opportunities['album'], correct['album'], song['id'])
        for tid in tag_links[song['id']]:
            add_group(by_tag, tid, available, earned, song['id'])

    timing = {key: dict(seconds=0.0, count=0) for key in FIELDS}
    outcomes = Counter()
    recent = []
    rounds = week = month = scored_rounds = 0
    total_points = 0.0
    # Stream the entire saved history; only the display list is capped at twenty.
    query = 'SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC'
    for raw in conn.execute(query):
        row = dict(raw)
        rounds += 1
        completed = finite(row['completed_at'])
        if completed is not None:
            week += now - 7 * 86400 <= completed <= now
            month += now - 30 * 86400 <= completed <= now
        eligible = [key for key in FIELDS if key != 'album' or row['album_available']]
        complete = all(row[key + '_correct'] in (0, 1) for key in eligible)
        correct_count = sum(row[key + '_correct'] == 1 for key in eligible)
        seconds = {key: finite(row[key + '_seconds']) for key in eligible}
        timed = all(seconds[key] is not None and 0 <= seconds[key] <= 30
                    for key in eligible if row[key + '_correct'] == 1)
        if complete:
            outcome = 'perfect' if correct_count == len(eligible) else 'partial' if correct_count else 'missed'
        else:
            outcome = 'unknown'
        points = None
        if complete and timed:
            # Historical eligibility wins over today's album link or stray data.
            scored = dict(row, album_correct=row['album_correct'] if row['album_available'] else None)
            scored.update({key + '_seconds': seconds[key] for key in eligible})
            points = round_points(scored)
            total_points += points
            scored_rounds += 1
        outcomes[outcome] += 1
        for key in eligible:
            elapsed = seconds[key]
            if row[key + '_correct'] == 1 and elapsed is not None and 0 <= elapsed <= 30:
                timing[key]['seconds'] += elapsed
                timing[key]['count'] += 1
        if len(recent) < 20:
            date = None
            if completed is not None:
                try:
                    date = datetime.fromtimestamp(completed, timezone.utc).isoformat()
                except (OverflowError, OSError, ValueError):
                    pass
            recent.append(dict(row, song=songs.get(row['song_id']), points=points,
                               outcome=outcome, date=date))

    for field in fields:
        samples = timing[field['key']]
        field.update(missed=field['attempts'] - field['correct'],
                     accuracy=percentage(field['correct'], field['attempts']),
                     seconds=round(samples['seconds'] / samples['count'], 1) if samples['count'] else None,
                     timed_answers=samples['count'])

    def category(kind, title, note, source, identities):
        rows = []
        for identity, totals in source.items():
            row = identities[identity]
            rows.append(dict(row, name=row.get('name', row.get('title', '')),
                             attempts=totals['attempts'], correct=totals['correct'],
                             missed=totals['attempts'] - totals['correct'],
                             tested=len(totals['songs']),
                             accuracy=percentage(totals['correct'], totals['attempts'])))
        return dict(kind=kind, title=title, note=note,
                    best=sorted(rows, key=lambda r: (-r['correct'] / r['attempts'], -r['attempts'], r['name'].casefold(), r['id']))[:5],
                    missed=sorted((r for r in rows if r['missed']),
                                  key=lambda r: (-r['missed'], -r['attempts'], r['name'].casefold(), r['id']))[:5])

    playable = [s for s in songs.values() if str(s.get('audio_url') or '').strip()]
    tested_ids = {s['id'] for s in tested}
    tested_playable = sum(s['id'] in tested_ids for s in playable)
    correct, available = sum(f['correct'] for f in fields), sum(f['attempts'] for f in fields)
    records = dict(conn.execute("SELECT key,value FROM global_stats WHERE key IN ('trivia_high_score','trivia_high_streak')"))
    outcomes_list = [dict(key=key, label=label, count=outcomes[key], share=percentage(outcomes[key], rounds))
                     for key, label in [('perfect', 'All fields correct'), ('partial', 'Some fields correct'),
                                        ('missed', 'No fields correct'), ('unknown', 'Result unavailable')]
                     if key != 'unknown' or outcomes[key]]
    return dict(
        summary=dict(rounds=rounds, tested=len(tested), correct=correct, available=available,
                     accuracy=percentage(correct, available), best_score=round(finite(records.get('trivia_high_score')) or 0, 2),
                     best_streak=nonnegative(records.get('trivia_high_streak')), week=week, month=month,
                     points=round(total_points, 2) if scored_rounds else None, scored_rounds=scored_rounds,
                     average_points=round(total_points / scored_rounds, 3) if scored_rounds else None),
        fields=fields, outcomes=outcomes_list, recent=recent,
        coverage=dict(playable=len(playable), tested=tested_playable, untested=len(playable) - tested_playable,
                      accuracy=percentage(tested_playable, len(playable)),
                      without_preview=len(tested) - tested_playable),
        top_stats=sorted(tested, key=lambda s: (-s['correct'] / s['available'], -s['attempts'], s['title'].casefold(), s['id']))[:10],
        bottom_stats=sorted(tested, key=lambda s: (s['correct'] / s['available'], -s['attempts'], s['title'].casefold(), s['id']))[:10],
        categories=[category('artist', 'Artist answers', 'Artist-field accuracy', by_artist, artists),
                    category('album', 'Album answers', 'Eligible album-field accuracy', by_album, albums),
                    category('tag', 'Recognition by tag', 'All eligible fields', by_tag, tags)])
