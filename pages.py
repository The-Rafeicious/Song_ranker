from flask import render_template, request, jsonify, abort

from services import app, get_db_connection, fetch_match_history
from catalog import collection, ranked, proper_album, song_performance
@app.route('/')
def home():
    return render_template('app_page.html', page='home')


@app.route('/leaderboard')
def leaderboard():
    return render_template('app_page.html', page='rankings_songs')


@app.route('/artists')
def artists_leaderboard():
    return render_template('app_page.html', page='rankings_artists')


@app.route('/albums')
def albums_leaderboard():
    return render_template('app_page.html', page='rankings_albums')


@app.route('/api/library')
def api_library():
    kind=request.args.get('type','songs')
    if kind not in ('songs','artists','albums','tags'):return jsonify({'error':'Invalid type.'}),400
    try: limit=max(1,min(int(request.args.get('limit',60)),200));offset=max(0,int(request.args.get('offset',0)))
    except ValueError:return jsonify({'error':'Invalid pagination.'}),400
    data=collection();items=ranked(data,kind)
    q=request.args.get('q','').casefold().strip()
    if q: items=[r for r in items if q in ' '.join(str(r.get(k,'')) for k in ('title','name','artist','album','genres')).casefold()]
    if kind=='albums':items=[r for r in items if proper_album(r)]
    return jsonify(type=kind,items=items[offset:offset+limit],total=len(items),offset=offset,limit=limit,has_more=offset+limit<len(items))

@app.route('/api/collection')
def api_collection():
    return jsonify(collection())


@app.route('/search')
def search():
    return render_template('app_page.html', page='search')


@app.route('/artist_stats')
def artist_performance():
    return render_template('app_page.html', page='performance_artists')


@app.route('/album_stats')
def album_performance():
    return render_template('app_page.html', page='performance_albums')


@app.route('/history')
def history():
    conn = get_db_connection()
    history_data = fetch_match_history(conn, limit=50)
    conn.close()
    return render_template('history.html', history=history_data)


def global_mode_details(conn):
    """Current field accuracy and saved podiums, derived without extra counters."""
    fields = []
    for key, label, denominator in [('title', 'Song', 'new_attempts'),
                                     ('artist', 'Artist', 'new_attempts'),
                                     ('album', 'Album', 'album_attempts')]:
        row = conn.execute(f'SELECT COALESCE(SUM({key}_correct),0) correct, '
                           f'COALESCE(SUM({denominator}),0) attempts FROM trivia_stats').fetchone()
        fields.append(dict(label=label, correct=row['correct'], attempts=row['attempts'],
                           accuracy=round(100*row['correct']/row['attempts'],1) if row['attempts'] else None))
    tournaments = [dict(row) for row in conn.execute('SELECT * FROM tournaments')]
    matches = [dict(row) for row in conn.execute('SELECT * FROM tournament_matches')]
    songs = [dict(row) for row in conn.execute('SELECT id,title FROM songs')]
    performance = song_performance(dict(songs=songs, tournaments=tournaments, tournament_matches=matches))
    leaders = sorted([dict(song, **performance[song['id']]) for song in songs
                      if performance[song['id']]['championships']],
                     key=lambda row: (-row['championships'], -row['tournament_points'], row['title']))[:3]
    completed = [t for t in tournaments if t['status']=='completed']
    latest = max(completed, key=lambda t:(t.get('completed_at') or t.get('created_at') or '',t['id']), default=None)
    by_id = {song['id']:song for song in songs}
    podium = [dict(place=place, **by_id[latest[column]])
              for place,column in [(1,'champion_id'),(2,'runner_up_id'),(3,'third_place_id')]
              if latest and latest.get(column) in by_id]
    return dict(trivia_fields=fields,
                trivia_tested=conn.execute('SELECT COUNT(*) FROM trivia_stats WHERE attempts>0').fetchone()[0],
                trivia_over_ninety=conn.execute('SELECT COUNT(*) FROM trivia_stats WHERE 100.0*correct/NULLIF(available_points,0)>90').fetchone()[0],
                tournaments_completed=len(completed),
                tournament_matches=sum(row['tournament_wins'] for row in performance.values()),
                tournament_points=round(sum(row['tournament_points'] for row in performance.values()),2),
                tournament_places=[dict(label=label, count=sum(row[key] for row in performance.values()))
                                   for key,label in [('championships','First place'),('runner_ups','Second place'),('third_places','Third place')]],
                tournament_leaders=leaders, latest_podium=podium,
                latest_tournament_id=latest['id'] if latest else None)


@app.route('/global_stats')
def global_stats():
    conn = get_db_connection()

    # 1. Core Totals
    total_songs = conn.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
    total_artists = conn.execute('SELECT COUNT(*) FROM artists').fetchone()[0]
    total_albums = conn.execute('''
                                SELECT COUNT(*)
                                FROM albums
                                WHERE LOWER(TRIM(title)) != 'unknown album' AND TRIM(title) != ''
                                  AND LOWER(TRIM(title)) NOT LIKE '% - single'
                                ''').fetchone()[0]
    total_matches = conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]

    # 2. Most Frequent Matchups (Rivalries)
    frequent_matchups = conn.execute('''
                                     SELECT CASE WHEN winner_id < loser_id THEN winner_id ELSE loser_id END as s1_id,
                                            CASE WHEN winner_id < loser_id THEN loser_id ELSE winner_id END as s2_id,
                                            COUNT(*)                                                        as encounters
                                     FROM history
                                     GROUP BY s1_id, s2_id
                                     ORDER BY encounters DESC
                                     LIMIT 5
                                     ''').fetchall()

    matchups_data = []
    for m in frequent_matchups:
        # Join albums for cover_url, and subquery artists for the artist name
        s1 = conn.execute('''
                          SELECT s.id,
                                 s.title,
                                 al.cover_url,
                                 (SELECT GROUP_CONCAT(a.name, ', ')
                                  FROM song_artists sa
                                           JOIN artists a ON sa.artist_id = a.id
                                  WHERE sa.song_id = s.id) as artist
                          FROM songs s
                                   LEFT JOIN albums al ON s.album_id = al.id
                          WHERE s.id = ?
                          ''', (m['s1_id'],)).fetchone()

        s2 = conn.execute('''
                          SELECT s.id,
                                 s.title,
                                 al.cover_url,
                                 (SELECT GROUP_CONCAT(a.name, ', ')
                                  FROM song_artists sa
                                           JOIN artists a ON sa.artist_id = a.id
                                  WHERE sa.song_id = s.id) as artist
                          FROM songs s
                                   LEFT JOIN albums al ON s.album_id = al.id
                          WHERE s.id = ?
                          ''', (m['s2_id'],)).fetchone()

        if s1 and s2:
            matchups_data.append({'s1': s1, 's2': s2, 'encounters': m['encounters']})

    # 3. Fun Superlatives
    # Join albums for cover_url, and subquery artists for the artist name
    most_played = conn.execute('''
                               SELECT s.id,
                                      s.title,
                                      s.matches_played,
                                      al.cover_url,
                                      (SELECT GROUP_CONCAT(a.name, ', ')
                                       FROM song_artists sa
                                                JOIN artists a ON sa.artist_id = a.id
                                       WHERE sa.song_id = s.id) as artist
                               FROM songs s
                                        LEFT JOIN albums al ON s.album_id = al.id
                               ORDER BY s.matches_played DESC
                               LIMIT 1
                               ''').fetchone()

    prolific_artist = conn.execute('''
                                   SELECT a.name as artist, a.cover_url, COUNT(sa.song_id) as track_count
                                   FROM artists a
                                            JOIN song_artists sa ON a.id = sa.artist_id
                                   GROUP BY a.id
                                   ORDER BY track_count DESC
                                   LIMIT 1
                                   ''').fetchone()

    top_genre = conn.execute('''
                             SELECT g.name, COUNT(sg.song_id) as tag_count
                             FROM genres g
                                      JOIN song_genres sg ON g.id = sg.genre_id
                             GROUP BY g.id
                             ORDER BY tag_count DESC
                             LIMIT 1
                             ''').fetchone()

    extra_stats = {
        'genres_count': conn.execute('SELECT COUNT(*) FROM genres').fetchone()[0],
        'songs_never_voted': conn.execute('SELECT COUNT(*) FROM songs WHERE COALESCE(matches_played,0)=0').fetchone()[0],
        'songs_with_audio': conn.execute("SELECT COUNT(*) FROM songs WHERE COALESCE(audio_url,'') != ''").fetchone()[0],
        'average_elo': round(conn.execute('SELECT COALESCE(AVG(elo_score),1200) FROM songs').fetchone()[0]),
        'highest_elo': conn.execute('SELECT id,title,elo_score FROM songs ORDER BY elo_score DESC,title LIMIT 1').fetchone(),
        'lowest_elo': conn.execute('SELECT id,title,elo_score FROM songs ORDER BY elo_score ASC,title LIMIT 1').fetchone(),
        'most_wins': conn.execute("SELECT s.id,s.title,COUNT(h.id) AS wins FROM songs s JOIN history h ON h.winner_id=s.id WHERE h.mode IN ('standard','blind') GROUP BY s.id ORDER BY wins DESC LIMIT 1").fetchone(),
        'trivia_attempts': conn.execute('SELECT COALESCE(SUM(attempts),0) FROM trivia_stats').fetchone()[0],
        'trivia_available': conn.execute('SELECT COALESCE(SUM(available_points),0) FROM trivia_stats').fetchone()[0],
        'trivia_high_score': conn.execute("SELECT COALESCE(MAX(value),0) FROM global_stats WHERE key='trivia_high_score'").fetchone()[0],
        'trivia_high_streak': conn.execute("SELECT COALESCE(MAX(value),0) FROM global_stats WHERE key='trivia_high_streak'").fetchone()[0],
        'trivia_correct': conn.execute('SELECT COALESCE(SUM(correct),0) FROM trivia_stats').fetchone()[0],
        'tournaments_total': conn.execute('SELECT COUNT(*) FROM tournaments').fetchone()[0],
        'recent_votes': conn.execute("SELECT COUNT(*) FROM history WHERE created_at >= datetime('now','-7 days')").fetchone()[0],
        
        'top_trivia': conn.execute('''SELECT s.id,s.title,ts.attempts,ts.correct,ROUND(100.0*ts.correct/NULLIF(ts.available_points,0)) AS accuracy
            FROM trivia_stats ts JOIN songs s ON s.id=ts.song_id WHERE ts.attempts>0 ORDER BY accuracy DESC,ts.attempts DESC LIMIT 1''').fetchone()
    }
    elo_distribution = [dict(r) for r in conn.execute('''SELECT CASE WHEN elo_score < 1000 THEN '< 1000'
        WHEN elo_score < 1100 THEN '1000-1099' WHEN elo_score < 1200 THEN '1100-1199'
        WHEN elo_score < 1300 THEN '1200-1299' WHEN elo_score < 1400 THEN '1300-1399' ELSE '1400+' END AS band,
        COUNT(*) AS count FROM songs GROUP BY band ORDER BY MIN(elo_score)''').fetchall()]
    genre_leaders = [dict(r) for r in conn.execute('SELECT g.name,COUNT(DISTINCT sg.song_id) AS songs FROM genres g JOIN song_genres sg ON sg.genre_id=g.id GROUP BY g.id ORDER BY songs DESC,g.name LIMIT 8').fetchall()]
    top_albums_stats = [dict(r) for r in conn.execute('''SELECT al.id,al.title,al.cover_url,COUNT(s.id) AS songs,ROUND(AVG(s.elo_score)) AS avg_elo
        FROM albums al JOIN songs s ON s.album_id=al.id WHERE LOWER(TRIM(al.title)) != 'unknown album' AND TRIM(al.title) != '' AND LOWER(TRIM(al.title)) NOT LIKE '% - single'
        GROUP BY al.id HAVING COUNT(s.id)>0 ORDER BY avg_elo DESC,songs DESC LIMIT 5''').fetchall()]
    recent_activity = [dict(r) for r in conn.execute('''SELECT h.id,h.created_at,w.id AS winner_id,w.title AS winner_title,l.id AS loser_id,l.title AS loser_title
        FROM history h LEFT JOIN songs w ON w.id=h.winner_id LEFT JOIN songs l ON l.id=h.loser_id ORDER BY h.id DESC LIMIT 8''').fetchall()]
    from catalog import voting_records, summarize_votes
    song_votes = voting_records(conn)
    voting = summarize_votes(list(song_votes.values()))
    titles = {row['id']: row['title'] for row in conn.execute('SELECT id,title FROM songs')}
    voting_leaders = {}
    for mode,prefix in [('overall',''),('standard','standard_'),('blind','blind_')]:
        eligible = [(sid,v) for sid,v in song_votes.items() if v[prefix+'matches']]
        eligible.sort(key=lambda pair:(-pair[1][prefix+'win_rate'],-pair[1][prefix+'matches'],titles[pair[0]]))
        voting_leaders[mode]=[dict(id=sid,title=titles[sid],wins=v[prefix+'wins'],
            losses=v[prefix+'losses'],win_rate=round(v[prefix+'win_rate'],1)) for sid,v in eligible[:3]]
    extra_stats.update(global_mode_details(conn))
    conn.close()

    return render_template('global_stats.html',
                           extra_stats=extra_stats, elo_distribution=elo_distribution, voting=voting, voting_leaders=voting_leaders,
                           genre_leaders=genre_leaders, top_albums_stats=top_albums_stats,
                           recent_activity=recent_activity,
                           total_songs=total_songs,
                           total_artists=total_artists,
                           total_albums=total_albums,
                           total_matches=total_matches,
                           matchups=matchups_data,
                           most_played=most_played,
                           prolific_artist=prolific_artist,
                           top_genre=top_genre)


@app.route('/song/<int:song_id>')
def song_page(song_id):
    conn=get_db_connection()
    found=conn.execute('SELECT 1 FROM songs WHERE id=?',(song_id,)).fetchone()
    conn.close()
    if not found: abort(404)
    return render_template('app_page.html', page='song', entity_id=song_id)


@app.route('/artist/<path:artist_name>')
def artist_page(artist_name):
    conn = get_db_connection()
    artist_data = conn.execute('SELECT id, cover_url FROM artists WHERE name = ? COLLATE NOCASE',
                               (artist_name,)).fetchone()

    songs = conn.execute('''
                         SELECT s.*,
                                al.cover_url,
                                al.title                   as album,
                                (SELECT GROUP_CONCAT(a2.name, ', ')
                                 FROM song_artists sa2
                                          JOIN artists a2 ON sa2.artist_id = a2.id
                                 WHERE sa2.song_id = s.id) as artist,
                                (SELECT GROUP_CONCAT(g2.name, ', ')
                                 FROM song_genres sg2
                                          JOIN genres g2 ON sg2.genre_id = g2.id
                                 WHERE sg2.song_id = s.id) as genres
                         FROM songs s
                                  JOIN song_artists sa ON s.id = sa.song_id
                                  JOIN artists a ON sa.artist_id = a.id
                                  LEFT JOIN albums al ON s.album_id = al.id
                         WHERE a.name = ? COLLATE NOCASE
                         ORDER BY s.elo_score DESC
                         ''', (artist_name,)).fetchall()

    albums = []
    if artist_data:
        albums = conn.execute('''
                              SELECT DISTINCT al.*, COUNT(s.id) as song_count
                              FROM albums al
                                       JOIN songs s ON al.id = s.album_id
                                       JOIN song_artists sa ON s.id = sa.song_id
                              WHERE sa.artist_id = ?
                                AND al.title != 'Unknown Album'
                                AND al.title NOT LIKE '% - Single'
                              GROUP BY al.id
                              ORDER BY al.release_date DESC, al.title ASC
                              ''', (artist_data['id'],)).fetchall()

    conn.close()

    if not artist_data:
        return "Artist not found.", 404

    song_count = len(songs)
    best_song = songs[0] if songs else None
    worst_song = songs[-1] if songs else None
    avg_elo = sum(s['elo_score'] for s in songs) / song_count if song_count else 1200
    impact_score = 1200 + sum(s['elo_score'] - 1200 for s in songs)

    pfp_url = artist_data['cover_url'] or (best_song['cover_url'] if best_song else None)

    return render_template('artist_page.html',
                           artist_name=artist_name,
                           pfp_url=pfp_url,
                           song_count=song_count,
                           impact_score=impact_score,
                           best_song=best_song,
                           worst_song=worst_song,
                           songs=songs,
                           albums=albums)


@app.route('/album/<path:album_title>')
def album_page(album_title):
    conn = get_db_connection()

    # Get album details
    album_data = conn.execute('SELECT * FROM albums WHERE title = ? COLLATE NOCASE', (album_title,)).fetchone()

    if not album_data:
        conn.close()
        return "Album not found.", 404

    # Fetch all songs on this album, ordered by highest Elo
    songs = conn.execute('''
                         SELECT s.*,
                                (SELECT GROUP_CONCAT(a2.name, ', ')
                                 FROM song_artists sa2
                                          JOIN artists a2 ON sa2.artist_id = a2.id
                                 WHERE sa2.song_id = s.id) as artist
                         FROM songs s
                         WHERE s.album_id = ?
                         ORDER BY s.elo_score DESC
                         ''', (album_data['id'],)).fetchall()
    conn.close()

    song_count = len(songs)

    # Calculate Impact Score: Average Elo + (Total Songs * 5)
    avg_elo = sum(s['elo_score'] for s in songs) / song_count if song_count else 1200
    impact_score = 1200 + sum(s['elo_score'] - 1200 for s in songs)

    # Use the primary artist of the highest-ranked song to represent the album's artist
    artist_name = songs[0]['artist'] if songs else ''

    return render_template('album_page.html',
                           album_name=album_data['title'],
                           cover_url=album_data['cover_url'],
                           release_date=album_data['release_date'] if 'release_date' in album_data.keys() else None,
                           artist_name=artist_name,
                           song_count=song_count,
                           avg_elo=avg_elo,
                           best_song=songs[0] if songs else None,
                           worst_song=songs[-1] if songs else None,
                           impact_score=impact_score,
                           songs=songs)


@app.route('/tags')
def tags_index():
    """The top ten tags, ranked by the shared library impact score."""
    return render_template('tags_index.html')


@app.route('/tag/<path:tag_name>')
def tag_page(tag_name):
    """A tag's profile and linked tracks, using the shared collection data."""
    conn = get_db_connection()
    try:
        tag = conn.execute(
            'SELECT id, name FROM genres WHERE name = ? COLLATE NOCASE',
            (tag_name,)
        ).fetchone()
    finally:
        conn.close()
    if not tag:
        return "Tag not found.", 404
    return render_template('tag_page.html', tag=tag)


@app.route('/trivia_stats')
def trivia_stats():
    from catalog import collection, ranked
    from trivia import round_points
    data=collection()
    rows=[{**r,'trivia_attempts':r['attempts'],'trivia_correct':r['correct'],
           'rec_score':round(100*r['correct']/r['available_points'])} for r in ranked(data,'songs') if r['available_points']>0]
    top=sorted(rows,key=lambda r:(-r['rec_score'],-r['attempts'],r['title']))[:10]
    bottom=sorted(rows,key=lambda r:(r['rec_score'],-r['attempts'],r['title']))[:10]
    lookup={s['id']:s for s in rows}
    recent=[{**r,'song':lookup.get(r['song_id']),'points':round_points(r)} for r in data['trivia_rounds']]
    fields=[]
    for name,label,attempts in [('title','Song','new_attempts'),('artist','Artist','new_attempts'),('album','Album','album_attempts')]:
        total=sum(s.get(attempts,0) for s in rows);correct=sum(s.get(name+'_correct',0) for s in rows)
        fields.append(dict(key=name,kind={'title':'song','artist':'artist','album':'album'}[name],name=label,attempts=total,correct=correct,missed=max(0,total-correct),accuracy=round(100*correct/total) if total else None))
    return render_template('trivia_stats.html',top_stats=top,bottom_stats=bottom,records=data['global_stats'],fields=fields,recent=recent,
                           summary=dict(rounds=sum(r['attempts'] for r in rows),tested=len(rows)),
                           artist_map={a['id']:a for a in data['artists']})
