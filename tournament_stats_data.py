"""Read-only tournament dashboard, derived from saved brackets, entries and matches."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import ceil, isfinite

from catalog import proper_album, song_performance
from global_stats_data import percent, timestamp

ARCHIVE_SIZE = 10


def number(value):
    try:
        value = float(value)
        return value if isfinite(value) and value >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def saved_time(value):
    if value is None or str(value).strip() == '':
        return None
    stamp = timestamp(value)
    if stamp == 0:
        # The shared parser uses zero for invalid dates; preserve a real epoch.
        numeric = number(value)
        if numeric is not None:
            stamp = numeric
        else:
            try:
                datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            except (TypeError, ValueError, OverflowError):
                return None
    if not isfinite(stamp):
        return None
    try:
        return dict(seconds=stamp, iso=datetime.fromtimestamp(stamp, timezone.utc).isoformat())
    except (ValueError, OverflowError, OSError):
        return None


def stage_name(size, round_number, match_type='bracket'):
    if match_type == 'third_place':
        return 'Third-place playoff'
    if match_type != 'bracket':
        return 'Other saved matches'
    if not isinstance(size, int) or size < 2 or size & (size - 1) or not isinstance(round_number, int) or round_number < 1:
        return 'Round ' + str(round_number or '?')
    remaining = size // 2 ** (round_number - 1)
    return {2: 'Final', 4: 'Semi-finals', 8: 'Quarter-finals'}.get(remaining,
            'Round of ' + str(remaining) if remaining >= 2 else 'Round ' + str(round_number))


def recorded_result(match):
    winner, loser = match.get('winner_id'), match.get('loser_id')
    if match['status'] != 'completed' or winner is None or loser is None or winner == loser:
        return False
    pair = (match.get('song1_id'), match.get('song2_id'))
    return None in pair or {winner, loser} == set(pair)


def podium_points(sid, matches):
    played = [m for m in matches if m['status'] == 'completed'
              and sid is not None and sid in (m.get('song1_id'), m.get('song2_id'), m.get('winner_id'), m.get('loser_id'))]
    if not played:
        return None
    won = [number(m.get('points_awarded')) for m in played if m.get('winner_id') == sid]
    return round(sum(won), 2) if all(p is not None for p in won) else None


def build_tournament_stats(conn, now=None, selected=None, archive_page=1):
    """A caller-owned snapshot; no writes, API calls, history cap or Elo inference."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    artists = {r['id']: dict(r) for r in conn.execute('SELECT * FROM artists')}
    albums = {r['id']: dict(r) for r in conn.execute('SELECT * FROM albums')}
    tags = {r['id']: dict(r) for r in conn.execute('SELECT * FROM genres')}
    artist_links, tag_links = defaultdict(set), defaultdict(set)
    for r in conn.execute('SELECT song_id,artist_id FROM song_artists'):
        if r['artist_id'] in artists:
            artist_links[r['song_id']].add(r['artist_id'])
    for r in conn.execute('SELECT song_id,genre_id FROM song_genres'):
        if r['genre_id'] in tags:
            tag_links[r['song_id']].add(r['genre_id'])
    songs = {}
    for raw in conn.execute('SELECT * FROM songs'):
        song = dict(raw)
        album = albums.get(song.get('album_id'), {})
        song.update(cover_url=album.get('cover_url') or '',
                    artist_links=sorted((artists[a] for a in artist_links[song['id']]), key=lambda a: (a['name'].casefold(), a['id'])),
                    album_link=album if proper_album(album) else None)
        songs[song['id']] = song
    brackets = {r['id']: dict(r) for r in conn.execute('SELECT * FROM tournaments')}
    entries = [dict(r) for r in conn.execute('SELECT * FROM tournament_entries') if r['tournament_id'] in brackets]
    matches = [dict(r) for r in conn.execute('SELECT * FROM tournament_matches') if r['tournament_id'] in brackets]
    entries_by, matches_by, appearances = defaultdict(list), defaultdict(list), defaultdict(set)
    seed = {}
    for entry in entries:
        entries_by[entry['tournament_id']].append(entry)
        seed[entry['tournament_id'], entry['song_id']] = entry['seed']
        if entry['song_id'] in songs:
            appearances[entry['song_id']].add(entry['tournament_id'])
    for match in matches:
        matches_by[match['tournament_id']].append(match)
        for key in ('song1_id', 'song2_id', 'winner_id', 'loser_id'):
            if match.get(key) in songs:
                appearances[match[key]].add(match['tournament_id'])
    for t in brackets.values():
        if t['status'] == 'completed':
            size = t.get('size')
            final = size.bit_length() - 1 if isinstance(size, int) and size >= 2 and not size & (size - 1) else None
            for m in matches_by[t['id']]:
                if not recorded_result(m):
                    continue
                if (m.get('match_type', 'bracket') == 'bracket' and final
                        and m['round_number'] == final and m['match_number'] == 1
                        and (t.get('champion_id') is None or t['champion_id'] == m['winner_id'])):
                    if t.get('champion_id') is None:
                        t['champion_id'] = m['winner_id']
                    if t.get('runner_up_id') is None:
                        t['runner_up_id'] = m['loser_id']
                if m.get('match_type') == 'third_place':
                    if t.get('third_place_id') is None:
                        t['third_place_id'] = m['winner_id']
                    if t.get('fourth_place_id') is None:
                        t['fourth_place_id'] = m['loser_id']
            for key in ('champion_id', 'runner_up_id', 'third_place_id', 'fourth_place_id'):
                if t.get(key) in songs:
                    appearances[t[key]].add(t['id'])

    # Reuse the existing achievement owner, with invalid point values excluded.
    performance = song_performance(dict(songs=list(songs.values()), tournaments=list(brackets.values()),
                                       tournament_entries=entries,
                                       tournament_matches=[dict(m, points_awarded=number(m.get('points_awarded')) or 0) for m in matches]))
    for sid, song in songs.items():
        song.update(performance[sid], entries=len(appearances[sid]))
        song['played'] = song['tournament_wins'] + song['tournament_losses']
        song['win_rate'] = percent(song['tournament_wins'], song['played'])

    def identity(sid, absent='Not recorded'):
        return songs.get(sid) or dict(id=None, title='Track unavailable' if sid is not None else absent,
                                      cover_url='', artist_links=[], album_link=None)

    def scope(t):
        kind = t.get('scope_type')
        row = {'artist': artists, 'album': albums, 'tag': tags}.get(kind, {}).get(t.get('scope_id'))
        if kind == 'global':
            return dict(kind='tournament', name='Whole collection', row=None)
        if row and (kind != 'album' or proper_album(row)):
            return dict(kind=kind, name=row.get('name', row.get('title')), row=row)
        return dict(kind='tournament', name={'artist': 'Artist scope', 'album': 'Album scope', 'tag': 'Tag scope'}.get(kind, 'Scope unavailable'), row=None)

    finished, sizes, scopes, visibility = [], Counter(), Counter(), Counter()
    entry_total = missing_entries = week = month = top_half = seeded_champions = first_seed = 0
    champion_seeds = []
    for t in brackets.values():
        t['finished'] = t['status'] == 'completed'
        t['scope'] = scope(t)
        t['visibility'] = 'Blind' if t.get('is_blind') == 1 else 'Non-blind' if t.get('is_blind') == 0 else 'Not recorded'
        t['date'] = saved_time(t.get('completed_at')) if t['finished'] else saved_time(t.get('updated_at'))
        t['date'] = t['date'] or saved_time(t.get('created_at')) or saved_time(t.get('timestamp'))
        t['completion_date'] = saved_time(t.get('completed_at'))
        declared = t.get('size')
        t['entry_count'] = declared if isinstance(declared, int) and declared > 0 else len(entries_by[t['id']]) or None
        if t['entry_count'] is None:
            missing_entries += 1
        else:
            entry_total += t['entry_count']
        sizes[declared if declared in (32, 16, 8) else 'other'] += 1
        scopes[t['scope_type'] if t['scope_type'] in ('global', 'artist', 'album', 'tag') else 'other'] += 1
        visibility[t['visibility']] += 1
        saved = matches_by[t['id']]
        t['decided'] = sum(m['status'] == 'completed' for m in saved)
        t['created_matches'] = len(saved)
        expected = (declared - 1 + int(bool(t.get('playoff_enabled')))
                    if isinstance(declared, int) and declared >= 2 and not declared & (declared - 1) else None)
        t['expected_matches'] = expected
        t['progress'] = percent(min(t['decided'], expected), expected) if expected else None
        t['points'] = round(sum(number(m.get('points_awarded')) or 0 for m in saved if m['status'] == 'completed'), 2)
        placements = {key: t.get(key) for key in ('champion_id', 'runner_up_id', 'third_place_id')}
        if t['finished']:
            finished.append(t)
            completed = t['completion_date']
            if completed:
                week += now - 7*86400 <= completed['seconds'] <= now
                month += now - 30*86400 <= completed['seconds'] <= now
            position = seed.get((t['id'], t.get('champion_id')))
            if isinstance(position, int) and isinstance(declared, int) and 1 <= position <= declared:
                seeded_champions += 1
                first_seed += position == 1
                top_half += position <= declared / 2
                champion_seeds.append(dict(song=identity(t['champion_id']), seed=position, bracket=t))
        t['podium'] = [dict(place=i, song=identity(placements[key]),
                            points=podium_points(placements[key], saved))
                       for i, key in enumerate(('champion_id', 'runner_up_id', 'third_place_id'), 1)]
        t['champion'] = identity(t.get('champion_id'), 'Champion not recorded' if t['finished'] else 'In progress')

    finished.sort(key=lambda t: ((t['date'] or {}).get('seconds', float('-inf')), t['id']), reverse=True)
    decided = [m for m in matches if m['status'] == 'completed']
    known_points = [number(m.get('points_awarded')) for m in decided]
    stages = Counter()
    higher_seed_wins = seeded_matches = match_week = 0
    for m in decided:
        t = brackets[m['tournament_id']]
        stages[stage_name(t.get('size'), m['round_number'], m.get('match_type', 'bracket'))] += 1
        a, b = seed.get((t['id'], m.get('winner_id'))), seed.get((t['id'], m.get('loser_id')))
        size = t.get('size')
        if (recorded_result(m) and isinstance(a, int) and isinstance(b, int) and isinstance(size, int)
                and 1 <= a <= size and 1 <= b <= size and a != b and m.get('winner_id') != m.get('loser_id')):
            seeded_matches += 1
            higher_seed_wins += a > b
        date = saved_time(m.get('played_at'))
        if date:
            match_week += now - 7*86400 <= date['seconds'] <= now

    def breakdown(counter, keys):
        return [dict(key=k, label=label, count=counter[k], share=percent(counter[k], len(brackets))) for k, label in keys]
    size_rows = breakdown(sizes, [(32, '32 tracks'), (16, '16 tracks'), (8, '8 tracks')])
    if sizes['other']:
        size_rows += breakdown(sizes, [('other', 'Other / unknown')])
    scope_rows = breakdown(scopes, [('global', 'Whole collection'), ('artist', 'Artist'), ('album', 'Album'), ('tag', 'Tag')])
    if scopes['other']:
        scope_rows += breakdown(scopes, [('other', 'Not recorded')])
    visibility_rows = breakdown(visibility, [('Blind', 'Blind'), ('Non-blind', 'Non-blind')])
    if visibility['Not recorded']:
        visibility_rows += breakdown(visibility, [('Not recorded', 'Not recorded')])
    entered_songs = [s for s in songs.values() if s['entries']]
    records = []
    for label, key, unit, pool in [
            ('Most titles', 'championships', 'titles', entered_songs),
            ('Most podiums', 'podiums', 'podiums', entered_songs),
            ('Most tournament points', 'tournament_points', 'points', entered_songs),
            ('Most entries', 'entries', 'brackets', entered_songs),
            ('Most match wins', 'tournament_wins', 'wins', entered_songs),
            ('Best win rate · 3+ matches', 'win_rate', '%', [s for s in entered_songs if s['played'] >= 3])]:
        candidates = [s for s in pool if s[key] is not None and s[key] > 0]
        best = min(candidates, key=lambda s: (-(s['tournament_wins'] / s['played'] if key == 'win_rate' else s[key]), -s['played'], s['title'].casefold(), s['id']), default=None)
        records.append(dict(label=label, song=best,
                            value=round(best[key], 2) if best and key == 'tournament_points' else best[key] if best else None, unit=unit))

    def category(kind, identities, links):
        grouped = defaultdict(list)
        for song in entered_songs:
            for key in links(song):
                if key in identities:
                    grouped[key].append(song)
        rows = []
        for key, related in grouped.items():
            row = identities[key]
            rows.append(dict(row, name=row.get('name', row.get('title', '')),
                             titles=sum(s['championships'] for s in related),
                             podiums=sum(s['podiums'] for s in related),
                             points=round(sum(s['tournament_points'] for s in related), 2),
                             tracks=len(related), brackets=len(set().union(*(appearances[s['id']] for s in related)))))
        rows.sort(key=lambda r: (-r['titles'], -r['podiums'], -r['points'], -r['brackets'], r['name'].casefold(), r['id']))
        return dict(kind=kind, rows=rows[:5])

    archive = sorted(brackets.values(), key=lambda t: (t['status'] == 'in_progress',
                     (t['date'] or {}).get('seconds', float('-inf')), t['id']), reverse=True)
    pages = max(1, ceil(len(archive) / ARCHIVE_SIZE))
    archive_page = max(1, min(archive_page or 1, pages))
    if selected in brackets:
        archive_page = next(i for i, t in enumerate(archive) if t['id'] == selected) // ARCHIVE_SIZE + 1
    shown = archive[(archive_page-1)*ARCHIVE_SIZE:archive_page*ARCHIVE_SIZE]
    for t in shown:
        groups = defaultdict(list)
        for m in sorted(matches_by[t['id']], key=lambda m: (m['round_number'], m.get('match_type') == 'third_place', m['match_number'], m['id'])):
            label = stage_name(t.get('size'), m['round_number'], m.get('match_type', 'bracket'))
            groups[label].append(dict(m, left=identity(m.get('song1_id'), 'Track unavailable' if m['status'] == 'completed' else 'Awaiting qualifier'),
                                      right=identity(m.get('song2_id'), 'Track unavailable' if m['status'] == 'completed' else 'Awaiting qualifier'),
                                      points=number(m.get('points_awarded')),
                                      date=saved_time(m.get('played_at'))))
        t['rounds'] = [dict(label=k, matches=v) for k, v in groups.items()]
        t['selected'] = t['id'] == selected
    return dict(
        summary=dict(brackets=len(brackets), unfinished=len(brackets)-len(finished), finished=len(finished),
                     completion=percent(len(finished), len(brackets)), matches=len(decided),
                     entries=entry_total, missing_entries=missing_entries, week=week, month=month,
                     match_week=match_week, main_matches=sum(m.get('match_type', 'bracket') == 'bracket' for m in decided),
                     bronze_matches=sum(m.get('match_type') == 'third_place' for m in decided),
                     other_matches=sum(m.get('match_type', 'bracket') not in ('bracket', 'third_place') for m in decided),
                     points=round(sum(p for p in known_points if p is not None), 2) if any(p is not None for p in known_points) else None,
                     missing_points=sum(p is None for p in known_points)),
        latest=finished[0] if finished else None, recent_champions=finished[1:6],
        sizes=size_rows, scopes=scope_rows, visibility=visibility_rows,
        coverage=dict(entered=len(entered_songs), unentered=len(songs)-len(entered_songs), total=len(songs),
                      champions=sum(s['championships'] > 0 for s in songs.values()),
                      share=percent(len(entered_songs), len(songs))),
        stages=[dict(label=k, count=v, share=percent(v, len(decided))) for k, v in sorted(stages.items(),
                key=lambda item: ({'Round of 32': 0, 'Round of 16': 1, 'Quarter-finals': 2, 'Semi-finals': 3, 'Final': 4, 'Third-place playoff': 5}.get(item[0], 6), item[0]))],
        records=records,
        categories=[category('artist', artists, lambda s: artist_links[s['id']]),
                    category('album', {i: a for i, a in albums.items() if proper_album(a)}, lambda s: {s.get('album_id')}),
                    category('tag', tags, lambda s: tag_links[s['id']])],
        seeds=dict(known=seeded_champions, first=first_seed, top_half=top_half, bottom_half=seeded_champions-top_half,
                   top_share=percent(top_half, seeded_champions), matches=seeded_matches, upsets=higher_seed_wins,
                   upset_share=percent(higher_seed_wins, seeded_matches),
                   largest=min(champion_seeds, key=lambda r: (-r['seed'], -r['bracket']['id']), default=None)),
        archive=shown, archive_page=archive_page, archive_pages=pages, archive_total=len(archive),
        selected_missing=selected is not None and selected not in brackets)
