"""Pure preference replay and schema-8/9 transport upgrade; no Flask imports."""
from bisect import bisect_right, insort
from copy import deepcopy
import json
import math
import hashlib

LEGACY_COLUMNS = ('id', 'winner_id', 'loser_id', 'mode', 'created_at',
                  'winner_before', 'winner_after', 'loser_before', 'loser_after')
EVENT_COLUMNS = LEGACY_COLUMNS + ('offer_token', 'origin', 'rules_version',
                                  'winner_snapshot', 'loser_snapshot')


def calculate_new_elo(winner, loser, k_factor=32):
    expected_winner = 1 / (1 + 10 ** ((loser - winner) / 400))
    expected_loser = 1 / (1 + 10 ** ((winner - loser) / 400))
    return winner + k_factor * (1 - expected_winner), loser - k_factor * expected_loser


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def records(state, name):
    table = state['tables'].get(name, {'columns': [], 'rows': []})
    return [dict(zip(table['columns'], row)) for row in table['rows']]


def table(columns, rows, key=None):
    rows = sorted(rows, key=lambda row: compact(row).encode('utf-8'))
    result = {'columns': list(columns), 'rows': rows}
    if key is not None:
        result.update(rowids=[row[key] for row in rows], rowid_alias='rowid')
    return result


def catalogue_snapshots(state):
    songs = {row['id']: row for row in records(state, 'songs')}
    albums = {row['id']: row for row in records(state, 'albums')}
    artists = {row['id']: row for row in records(state, 'artists')}
    links = {}
    for row in records(state, 'song_artists'):
        links.setdefault(row['song_id'], []).append(row['artist_id'])
    result = {}
    for song_id, song in songs.items():
        artist_ids = sorted(links.get(song_id, []))
        album = albums.get(song.get('album_id'), {})
        result[song_id] = compact({'id': song_id, 'title': song['title'], 'album_id': song.get('album_id'),
            'album': album.get('title', ''), 'cover_url': album.get('cover_url'),
            'audio_url': song.get('audio_url'), 'artist_ids': artist_ids,
            'artist': ', '.join(artists[a]['name'] for a in artist_ids if a in artists),
            'artist_links': [{'id': a, 'name': artists[a]['name']} for a in artist_ids if a in artists]})
    return result


def verified_legacy(songs, events):
    ratings = {s['id']: 1200.0 for s in songs}
    counts = {s['id']: 0 for s in songs}
    for event in sorted(events, key=lambda row: row['id']):
        w, l = event['winner_id'], event['loser_id']
        if w not in ratings or l not in ratings or w == l or event['mode'] not in ('standard', 'blind'):
            return False
        a, b = ratings[w], ratings[l]
        na, nb = calculate_new_elo(a, b)
        expected = (a, na, b, nb)
        if any(event.get(key) is None or not math.isclose(event[key], value, rel_tol=0, abs_tol=1e-8)
               for key, value in zip(LEGACY_COLUMNS[5:], expected)):
            return False
        ratings[w], ratings[l] = na, nb
        counts[w] += 1; counts[l] += 1
    return all(s.get('elo_score') is not None and s.get('matches_played') == counts[s['id']]
               and math.isclose(s['elo_score'], ratings[s['id']], rel_tol=0, abs_tol=1e-8)
               for s in songs)


def _upgrade_history(original):
    """Map the old physical history to immutable events; preserve all original cells."""
    if 'history' not in original['tables']:
        return original
    if original['user_version'] > 10:
        raise ValueError('Database needs a newer app.')
    if 'preference_events' in original['tables']:
        raise ValueError('Both old history and preference events exist; a dedicated migration is required.')
    old = original['tables']['history']
    if set(old['columns']) != set(LEGACY_COLUMNS):
        raise ValueError('Unsupported legacy history columns; no data was discarded.')
    if 'rowids' in old and old['rowids'] != [row[old['columns'].index('id')] for row in old['rows']]:
        raise ValueError('Unsupported legacy history ID layout; no data was discarded.')
    state = deepcopy(original)
    events = records(state, 'history')
    songs = records(state, 'songs')
    verified = verified_legacy(songs, events)
    boundary = max((event['id'] for event in events), default=0)
    snapshots = catalogue_snapshots(state)
    rows = []
    for event in events:
        rows.append([event[name] for name in LEGACY_COLUMNS] + [None, 'legacy', 0,
            snapshots.get(event['winner_id'], compact({'id': event['winner_id'], 'title': 'Deleted song'})),
            snapshots.get(event['loser_id'], compact({'id': event['loser_id'], 'title': 'Deleted song'}))])
    state['tables']['preference_events'] = table(EVENT_COLUMNS, rows, key=0)
    del state['tables']['history']
    state['tables']['preference_rating_projection'] = table(
        ('event_id', 'winner_before', 'winner_after', 'loser_before', 'loser_after'),
        [[event['id'], *[event[key] for key in LEGACY_COLUMNS[5:]]] for event in events], key=0)
    state['tables']['preference_rating_seeds'] = table(
        ('song_id', 'elo', 'matches', 'highest_elo', 'highest_rank'),
        [[song['id'], 1200.0 if verified else song['elo_score'], 0 if verified else song['matches_played'],
          song.get('highest_elo') or song['elo_score'], song.get('highest_rank') or 9999] for song in songs], key=0)
    state['tables']['preference_replay_state'] = table(
        ('id', 'cutoff_event_id', 'legacy_boundary', 'baseline_kind', 'rules_version'),
        [[1, 0 if verified else boundary, boundary, 'verified_replay' if verified else 'legacy_anchor', 1]], key=0)
    if 'history' in state['sequences']:
        state['sequences']['preference_events'] = state['sequences'].pop('history')
    # Older extension views may read history; its compatible view retains all nine fields.
    state['user_version'] = 10
    return state


def effective_events(state):
    latest = {}
    for row in sorted(records(state, 'preference_corrections'), key=lambda r: r['id']):
        latest[row['event_id']] = row
    result = []
    for row in records(state, 'preference_events'):
        row.update(active=1, revision=0)
        if row['id'] in latest:
            correction = latest[row['id']]
            row.update({key: correction[key] for key in ('winner_id','loser_id','mode','active')})
            row['revision'] = correction['id']
        result.append(row)
    return result


def mode_replay(songs, events):
    """Independent K32 streams. Public overrides/anchors never leak into them."""
    result = {(s['id'], mode): dict(elo=1200.0, matches=0, tournament_matches=0)
              for s in songs for mode in ('standard', 'blind')}
    for event in sorted(events, key=lambda row: row['id']):
        w, l, mode = event['winner_id'], event['loser_id'], event['mode']
        if not event.get('active', 1) or w == l or (w, mode) not in result or (l, mode) not in result:
            continue
        first, second = result[w, mode], result[l, mode]
        first['elo'], second['elo'] = calculate_new_elo(first['elo'], second['elo'], 32 * event.get('rating_weight', 1))
        for row in (first, second):
            row['matches'] += 1
            row['tournament_matches'] += int(event['origin'] == 'tournament')
    return result


def _upgrade_to_11(original):
    """Normalize 8/9/10 transports to 11 without rewriting existing stored facts."""
    state = _upgrade_history(original)
    if state['user_version'] >= 11:
        return state
    state = deepcopy(state)
    if 'preference_mode_ratings' in state['tables']:
        raise ValueError('A pre-11 extension uses preference_mode_ratings; a dedicated migration is required. No data was discarded.')
    for name, additions in (
        ('preference_events', (('rating_weight', 1.0), ('tournament_id', None), ('tournament_match_id', None))),
        ('tournaments', (('elo_policy_version', 0), ('elo_weight', 0.0))),
    ):
        target = state['tables'].get(name)
        if target:
            for column, default in additions:
                if column in target['columns']:
                    raise ValueError(f'A pre-11 extension uses {name}.{column}; a dedicated migration is required.')
                target['columns'].append(column)
                for row in target['rows']:
                    row.append(default)
    modes = mode_replay(records(state, 'songs'), effective_events(state))
    state['tables']['preference_mode_ratings'] = table(
        ('song_id','mode','elo','matches','tournament_matches'),
        [[sid, mode, row['elo'], row['matches'], row['tournament_matches']]
         for (sid, mode), row in modes.items()])
    # A composite-key SQLite table still has a hidden rowid. Persist deterministic IDs.
    target = state['tables']['preference_mode_ratings']
    target.update(rowids=list(range(1, len(target['rows']) + 1)), rowid_alias='rowid')
    # Verify the old view contract before accounting for its three new columns.
    if 'preference_effective' in state['view_hashes']:
        keys = ('id','offer_token','origin','rules_version','created_at',
                'winner_id','loser_id','mode','active','revision')
        rows = [[row[key] for key in keys] for row in effective_events(state)]
        def view_hash(values):
            return hashlib.sha256(compact(sorted(values, key=lambda row: compact(row).encode('utf-8'))).encode('utf-8')).hexdigest()
        if view_hash(rows) != state['view_hashes']['preference_effective']:
            raise ValueError('Unsupported preference_effective view; no stored data was changed.')
        rows = [row[:5] + [1.0, None, None] + row[5:] for row in rows]
        state['view_hashes']['preference_effective'] = view_hash(rows)
    state['user_version'] = 11
    return state


def upgrade_state(original):
    """Apply lossless upgrades; recognize complete known SQL-dump layouts."""
    if original['user_version']==0:
        from songranker.storage.database_schema import table_columns
        from songranker.storage.challenge_state import ADDITIONS as quiz_additions
        from songranker.storage.catalog_source_state import ADDITIONS as song_additions
        current={name:set(columns) for name,columns in table_columns().items()}
        from songranker.storage.vibe_state import TABLES as vibe_tables
        layouts=[(17,current)]
        sixteen={name:columns for name,columns in current.items() if name not in vibe_tables}
        # Pre-17 SQL dumps share the older 14-16 column layout; retain its
        # established transport adapters when the version pragma was omitted.
        layouts.append((14,sixteen))
        thirteen={name:set(columns) for name,columns in sixteen.items() if name not in ('song_details','competition_state','listening_observations')}
        layouts.append((13,thirteen))
        twelve={name:set(columns) for name,columns in thirteen.items() if name!='song_sources'}
        twelve['songs']-={name for name,_ in song_additions}
        layouts.append((12,twelve))
        eleven={name:set(columns) for name,columns in twelve.items() if name!='challenge_runs'}
        for name,additions in quiz_additions.items():eleven[name]-={column for column,_ in additions}
        layouts.append((11,eleven))
        ten={name:set(columns) for name,columns in eleven.items() if name!='preference_mode_ratings'}
        ten['preference_events']-={'rating_weight','tournament_id','tournament_match_id'}
        ten['tournaments']-={'elo_policy_version','elo_weight'}
        layouts.append((10,ten))
        for version,layout in layouts:
            if (set(original['tables'])&set(current)==set(layout) and
                all(set(original['tables'][name]['columns'])==columns for name,columns in layout.items())):
                original=deepcopy(original);original['user_version']=version;break
    from songranker.storage.challenge_state import upgrade_state as upgrade_challenges
    from songranker.storage.catalog_source_state import upgrade_state as upgrade_sources
    from songranker.storage.source_storage import upgrade_state as upgrade_storage
    from songranker.storage.tag_limits import upgrade_state as upgrade_tags
    from songranker.storage.vibe_state import upgrade_state as upgrade_vibes
    return upgrade_vibes(upgrade_tags(upgrade_storage(upgrade_sources(upgrade_challenges(_upgrade_to_11(original))))))


def replay(songs, seeds, events, overrides, cutoff, boundary):
    """Return current ratings/counts and effective snapshots from immutable inputs."""
    result = {s['id']: dict(seeds[s['id']]) for s in songs}
    ordered = sorted((row['elo'], sid) for sid, row in result.items())
    projected = {}
    adjustments = sorted(overrides, key=lambda row: (row['after_event_id'], row['id']))
    index = 0
    def set_rating(sid, value):
        if sid not in result:
            return
        old = (result[sid]['elo'], sid)
        pos = bisect_right(ordered, old) - 1
        if pos < 0 or ordered[pos] != old:
            raise ValueError('Rating projection is inconsistent.')
        ordered.pop(pos); insort(ordered, (value, sid)); result[sid]['elo'] = value
    def apply_before(event_id):
        nonlocal index
        while index < len(adjustments) and adjustments[index]['after_event_id'] < event_id:
            row = adjustments[index]; set_rating(row['song_id'], row['new_elo']); index += 1
    for event in sorted(events, key=lambda row: row['id']):
        if event['id'] <= cutoff:
            continue
        apply_before(event['id'])
        w, l = event['winner_id'], event['loser_id']
        if not event['active'] or w not in result or l not in result or w == l:
            continue
        a, b = result[w]['elo'], result[l]['elo']
        na, nb = calculate_new_elo(a, b, 32 * event.get('rating_weight', 1))
        set_rating(w, na); set_rating(l, nb)
        if event['origin'] in ('legacy', 'ordinary'):
            result[w]['matches'] += 1; result[l]['matches'] += 1
        projected[event['id']] = (a, na, b, nb)
        if event['id'] > boundary:
            for sid in (w, l):
                value = result[sid]['elo']
                result[sid]['highest_elo'] = max(result[sid]['highest_elo'], value)
                rank = len(ordered) - bisect_right(ordered, (value, float('inf'))) + 1
                result[sid]['highest_rank'] = min(result[sid]['highest_rank'], rank)
    apply_before(float('inf'))
    return result, projected

