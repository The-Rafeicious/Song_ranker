"""Shared library projections and aggregation. Each song contributes once."""
from collections import defaultdict
from songranker.services import (app, get_db_connection)


def proper_album(album):
    title = str(album.get('title') or '').strip().casefold()
    return bool(title) and title != 'unknown album' and not title.endswith(' - single')


def versus_metadata(album, linked_artists):
    """Shared display links for paired song rows; preserve whole artist names."""
    album = album or {}
    return dict(
        cover_url=album.get('cover_url') or '',
        artist_links=[dict(id=a['id'], name=a['name'])
                      for a in sorted(linked_artists, key=lambda a: (a['name'], a['id']))],
        album_link=dict(id=album['id'], title=album['title']) if proper_album(album) else None)


TOURNAMENT_TOTALS = ('tournament_wins', 'tournament_losses', 'tournament_points',
                     'championships', 'runner_ups', 'tournament_appearances', 'third_places', 'fourth_places', 'podiums')


def song_performance(data):
    """Derive achievements from saved matches; final placements require completion."""
    result = {s['id']: {key: 0 for key in TOURNAMENT_TOTALS} for s in data['songs']}
    brackets = {t['id']: t for t in data.get('tournaments', [])}
    appearances = defaultdict(set)
    placements = {key: set() for key in ('championships', 'runner_ups', 'third_places', 'fourth_places')}
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
    for key, finishes in placements.items():
        for _, song_id in finishes:
            result[song_id][key] += 1
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
        'voting': summarize_votes([s.get('voting',{}) for s in songs]),
        'recognition_attempts': attempts,
        'recognition_correct': correct,
        'tested_tracks': sum(int(s.get('attempts') or 0) > 0 for s in songs),
        'recognition_score': 100 * correct / available if available else None,
    }


def voting_records(conn):
    """Combined public preference results, retaining origin and mode breakdowns."""
    from songranker.elo_history import source_sql
    keys=('standard_wins','standard_losses','blind_wins','blind_losses')
    result={r['id']:dict.fromkeys(keys,0) for r in conn.execute('SELECT id FROM songs')}
    sources={sid:{origin:dict.fromkeys(keys,0) for origin in ('ordinary','tournament','raw')} for sid in result}
    source=source_sql(conn)
    query=f"""SELECT song_id,mode,origin,SUM(won*rating_weight) wins,SUM((1-won)*rating_weight) losses, SUM(won) raw_wins,COUNT(*)-SUM(won) raw_losses FROM (
        SELECT h.winner_id song_id,h.mode,h.origin,h.rating_weight,1 won FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.mode IN ('standard','blind') AND h.winner_id!=h.loser_id
        UNION ALL
        SELECT h.loser_id song_id,h.mode,h.origin,h.rating_weight,0 won FROM {source} h
        JOIN songs w ON w.id=h.winner_id JOIN songs l ON l.id=h.loser_id
        WHERE h.mode IN ('standard','blind') AND h.winner_id!=h.loser_id
    ) GROUP BY song_id,mode,origin"""
    for row in conn.execute(query):
        origin='tournament' if row['origin']=='tournament' else 'ordinary'
        for name in ('wins','losses'):
            key=row['mode']+'_'+name;result[row['song_id']][key]+=row[name];sources[row['song_id']][origin][key]+=row[name]
            sources[row['song_id']]['raw'][key]+=row['raw_'+name]
    return {sid:summarize_votes([dict(counts,**sources[sid])]) for sid,counts in result.items()}


def summarize_votes(records):
    records=list(records)
    keys=('standard_wins','standard_losses','blind_wins','blind_losses')
    def project(rows):
        rows=list(rows);totals={key:sum(record.get(key,0) for record in rows) for key in keys}
        totals.update(wins=totals['standard_wins']+totals['blind_wins'],losses=totals['standard_losses']+totals['blind_losses'])
        for prefix in ('','standard_','blind_'):
            wins,losses=totals[prefix+'wins'],totals[prefix+'losses'];totals[prefix+'matches']=wins+losses
            totals[prefix+'win_rate']=100*wins/(wins+losses) if wins+losses else None
        return totals
    totals=project(records)
    totals['ordinary']=project(r.get('ordinary',r) for r in records)
    totals['tournament']=project(r.get('tournament',{}) for r in records)
    totals['raw']=project(r.get('raw',r) for r in records)
    return totals


def collection(include_overall_sources=False):
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')  # Read one consistent snapshot, including optional Overall inputs.
        data = {'songs':[dict(r) for r in conn.execute('SELECT s.*,COALESCE(ts.attempts,0) AS attempts,COALESCE(ts.correct,0) AS correct,COALESCE(ts.available_points,0) AS available_points,COALESCE(ts.new_attempts,0) AS new_attempts,COALESCE(ts.title_correct,0) AS title_correct,COALESCE(ts.artist_correct,0) AS artist_correct,COALESCE(ts.album_attempts,0) AS album_attempts,COALESCE(ts.album_correct,0) AS album_correct FROM songs s LEFT JOIN trivia_stats ts ON ts.song_id=s.id')]}
        for key, table in [('artists','artists'),('albums','albums'),('tags','genres'),('history','history'),('tournaments','tournaments'),('tournament_entries','tournament_entries'),('tournament_matches','tournament_matches')]:
            data[key]=[dict(r) for r in conn.execute(f'SELECT * FROM {table}')]
        data['trivia_rounds']=[dict(r) for r in conn.execute('SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 100')]
        data['global_stats']=dict(conn.execute('SELECT key,value FROM global_stats'))
        from songranker.modes.challenges import records as challenge_records
        data['challenge_records']={'trivia':challenge_records(conn,'trivia')}
        artist_links, tag_links = defaultdict(list), defaultdict(list)
        for row in conn.execute('SELECT * FROM song_artists'):artist_links[row['song_id']].append(row['artist_id'])
        for row in conn.execute('SELECT * FROM song_genres ORDER BY rowid'):tag_links[row['song_id']].append(row['genre_id'])
        for song in data['songs']:
            song.update(artist_ids=artist_links[song['id']],tag_ids=tag_links[song['id']])
        data['history'].sort(key=lambda r:r['id'],reverse=True)
        from songranker.elo_history import source_sql
        data['elo_history']=[dict(row) for row in conn.execute(f'SELECT * FROM {source_sql(conn)} ORDER BY id DESC')]
        data['tournaments'].sort(key=lambda r:r['id'],reverse=True)
        from songranker.modes.special_modes import special_records
        special,summary,_,_=special_records(conn)
        data['special_modes']=summary
        performance = song_performance(data)
        voting = voting_records(conn)
        from songranker.modes.mode_ratings import (song_mode_ratings, coverage)
        modes = song_mode_ratings(conn)
        data['rating_coverage'] = coverage(conn)
        from songranker.listening import song_summaries
        listening=song_summaries(conn)
        added={r['song_id']:r['added_at'] for r in conn.execute('SELECT song_id,added_at FROM song_details')}
        for song in data['songs']:
            song.update(added_at=added.get(song['id'],0),listening=listening.get(song['id'],dict(samples=0,seconds=0,mean=None)),**performance[song['id']], voting=voting[song['id']], elo_matches_played=voting[song['id']]['raw']['matches'], mode_ratings=modes[song['id']], **special[song['id']])
        if include_overall_sources:
            data['overall_sources']={
                'trivia_stats':[dict(r) for r in conn.execute('SELECT * FROM trivia_stats')],
                'trivia_rounds':[dict(r) for r in conn.execute('SELECT song_id,album_available,title_correct,artist_correct,album_correct FROM trivia_rounds WHERE completed_at IS NOT NULL')],
            }
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='mode_exposures' AND type='view'").fetchone():
            from songranker.modes.preferences import exposure_totals
            exposures = exposure_totals(conn)
            from songranker.elo_history import tournament_appearances
            for sid,values in tournament_appearances(conn).items():
                for mode,value in values.items():exposures[sid][mode]+=value
            for song in data['songs']:
                song['exposures'] = exposures[song['id']]
        data['competition']=dict(conn.execute('SELECT generation,started_at FROM competition_state WHERE id=1').fetchone() or {})
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
    from songranker.impact import (calibrate, measure)
    related_groups=[([s for s in songs if row['id'] in s['artist_ids']] if kind=='artists' else
        [s for s in songs if s['album_id']==row['id']] if kind=='albums' else
        [s for s in songs if row['id'] in s['tag_ids']]) for row in data[kind]]
    context=calibrate(songs,[group for row,group in zip(data[kind],related_groups) if kind!='albums' or proper_album(row)])
    result=[]
    for row,related in zip(data[kind],related_groups):
        result.append({**row,**aggregate_performance(related),'name':row.get('name',row.get('title')),'title':row.get('title',row.get('name')),
            'song_count':len(related),'avg_elo':sum(s['elo_score'] for s in related)/len(related) if related else 0,
            **measure(related,context),
            'artist':', '.join(dict.fromkeys(s['artist'] for s in related if s['artist']))})
    return sorted(result,key=lambda r:(r['impact_score'] is None,-(r['impact_score'] or 0),r['name'].casefold()))

