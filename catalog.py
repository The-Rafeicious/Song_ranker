"""Shared library projections and aggregation. Each song contributes once."""
from collections import defaultdict
from services import app, get_db_connection


def proper_album(album):
    title = str(album.get('title') or '').strip().casefold()
    return bool(title) and title != 'unknown album' and not title.endswith(' - single')


TOURNAMENT_TOTALS = ('tournament_wins', 'tournament_losses', 'tournament_points',
                     'championships', 'runner_ups', 'semifinals',
                     'top_four_finishes', 'tournament_appearances', 'third_places', 'fourth_places', 'podiums')


def song_performance(data):
    """Derive achievements from saved matches; final placements require completion."""
    result = {s['id']: {key: 0 for key in TOURNAMENT_TOTALS} for s in data['songs']}
    brackets = {t['id']: t for t in data.get('tournaments', [])}
    appearances = defaultdict(set)
    placements = {key: set() for key in ('championships', 'runner_ups', 'semifinals', 'third_places', 'fourth_places')}
    for entry in data.get('tournament_entries', []):
        if entry['song_id'] in result and entry['tournament_id'] in brackets:
            appearances[entry['song_id']].add(entry['tournament_id'])
    for t in brackets.values():
        champion = t.get('champion_id')
        if t.get('status') == 'completed' and champion in result:
            placements['championships'].add((t['id'], champion))
            appearances[champion].add(t['id'])
        if t.get('status') == 'completed':
            for key,column in [('runner_ups','runner_up_id'),('third_places','third_place_id'),('fourth_places','fourth_place_id')]:
                if t.get(column) in result: placements[key].add((t['id'],t[column]))
    for match in data.get('tournament_matches', []):
        t = brackets.get(match['tournament_id'])
        if not t:
            continue
        for song_id in (match.get('song1_id'), match.get('song2_id')):
            if song_id in result:
                appearances[song_id].add(t['id'])
        winner, loser = match.get('winner_id'), match.get('loser_id')
        if match.get('status') != 'completed' or winner not in result or loser not in result or winner == loser:
            continue
        result[winner]['tournament_wins'] += 1
        result[loser]['tournament_losses'] += 1
        result[winner]['tournament_points'] += float(match.get('points_awarded') or 0)
        if t.get('status') == 'completed':
            size = int(t.get('size') or 0)
            if size >= 2 and size & (size - 1) == 0:
                final_round = size.bit_length() - 1
                if match.get('match_type','bracket') != 'bracket':
                    continue
                if match.get('round_number') == final_round:
                    placements['runner_ups'].add((t['id'], loser))
                elif size >= 4 and match.get('round_number') == final_round - 1:
                    placements['semifinals'].add((t['id'], loser))
    for key, finishes in placements.items():
        for _, song_id in finishes:
            result[song_id][key] += 1
    for _, song_id in set().union(*placements.values()):
        result[song_id]['top_four_finishes'] += 1
    for _,song_id in placements['championships'] | placements['runner_ups'] | placements['third_places']:
        result[song_id]['podiums'] += 1
    for song_id, stats in result.items():
        stats['tournament_appearances'] = len(appearances[song_id])
    return result


def aggregate_performance(songs):
    """Pool recognition attempts and total distinct linked songs' achievements."""
    songs = list({s['id']: s for s in songs}.values())
    attempts = sum(int(s.get('attempts') or 0) for s in songs)
    correct = sum(int(s.get('correct') or 0) for s in songs)
    available = sum(int(s.get('available_points',2*int(s.get('attempts') or 0)) or 0) for s in songs)
    return {
        **{key: sum(s.get(key) or 0 for s in songs) for key in TOURNAMENT_TOTALS},
        'recognition_attempts': attempts,
        'recognition_correct': correct,
        'tested_tracks': sum(int(s.get('attempts') or 0) > 0 for s in songs),
        'recognition_score': 100 * correct / available if available else None,
    }


def collection():
    conn = get_db_connection()
    try:
        data = {'songs':[dict(r) for r in conn.execute('SELECT s.*,COALESCE(ts.attempts,0) AS attempts,COALESCE(ts.correct,0) AS correct,COALESCE(ts.available_points,0) AS available_points,COALESCE(ts.legacy_attempts,0) AS legacy_attempts,COALESCE(ts.legacy_correct,0) AS legacy_correct,COALESCE(ts.new_attempts,0) AS new_attempts,COALESCE(ts.title_correct,0) AS title_correct,COALESCE(ts.artist_correct,0) AS artist_correct,COALESCE(ts.album_attempts,0) AS album_attempts,COALESCE(ts.album_correct,0) AS album_correct FROM songs s LEFT JOIN trivia_stats ts ON ts.song_id=s.id')]}
        for key, table in [('artists','artists'),('albums','albums'),('tags','genres'),('history','history'),('tournaments','tournaments'),('tournament_entries','tournament_entries'),('tournament_matches','tournament_matches')]:
            data[key]=[dict(r) for r in conn.execute(f'SELECT * FROM {table}')]
        data['trivia_rounds']=[dict(r) for r in conn.execute('SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 100')]
        data['global_stats']=dict(conn.execute('SELECT key,value FROM global_stats'))
        artist_links, tag_links = defaultdict(list), defaultdict(list)
        for row in conn.execute('SELECT * FROM song_artists'):artist_links[row['song_id']].append(row['artist_id'])
        for row in conn.execute('SELECT * FROM song_genres'):tag_links[row['song_id']].append(row['genre_id'])
        for song in data['songs']:
            song.update(artist_ids=artist_links[song['id']],tag_ids=tag_links[song['id']])
        data['history'].sort(key=lambda r:r['id'],reverse=True)
        data['tournaments'].sort(key=lambda r:r['id'],reverse=True)
        performance = song_performance(data)
        for song in data['songs']:
            song.update(performance[song['id']])
        return data
    finally: conn.close()


def ranked(data, kind):
    artists={r['id']:r for r in data['artists']};albums={r['id']:r for r in data['albums']};tags={r['id']:r for r in data['tags']}
    songs=[]
    for row in data['songs']:
        album=albums.get(row['album_id'],{})
        songs.append({**row,'name':row['title'],'artist':', '.join(artists[a]['name'] for a in row['artist_ids'] if a in artists),
                      'album':album.get('title',''),'cover_url':album.get('cover_url',''),'album_is_single':str(album.get('title','')).casefold().endswith(' - single'),
                      'genres':', '.join(tags[t]['name'] for t in row['tag_ids'] if t in tags),'impact_score':row['elo_score']})
    if kind=='songs':return sorted(songs,key=lambda r:(-r['elo_score'],r['title'].casefold()))
    result=[]
    for row in data[kind]:
        related=[s for s in songs if row['id'] in s['artist_ids']] if kind=='artists' else ([s for s in songs if s['album_id']==row['id']] if kind=='albums' else [s for s in songs if row['id'] in s['tag_ids']])
        result.append({**row,**aggregate_performance(related),'name':row.get('name',row.get('title')),'title':row.get('title',row.get('name')),
            'song_count':len(related),'avg_elo':sum(s['elo_score'] for s in related)/len(related) if related else 0,
            'impact_score':1200+sum(s['elo_score']-1200 for s in related),
            'artist':', '.join(dict.fromkeys(s['artist'] for s in related if s['artist']))})
    return sorted(result,key=lambda r:(-r['impact_score'],r['name'].casefold()))
