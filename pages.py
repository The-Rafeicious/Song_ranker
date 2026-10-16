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
    mode='trivia' if request.args.get('metric','recognition')=='recognition' else 'tournament'
    return render_template('app_page.html', page='mode_rankings_'+mode,ranking_entity='artists')


@app.route('/album_stats')
def album_performance():
    mode='trivia' if request.args.get('metric','recognition')=='recognition' else 'tournament'
    return render_template('app_page.html', page='mode_rankings_'+mode,ranking_entity='albums')


@app.route('/history')
def history():
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        history_data = fetch_match_history(conn, limit=50)
    finally:
        conn.close()
    return render_template('history.html', history=history_data)


@app.route('/voting_stats')
def voting_stats():
    from voting_stats_data import build_voting_stats
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        data = build_voting_stats(conn, history_mode=request.args.get('history_mode', 'all'),
                                  history_page=request.args.get('history_page', 1))
        return render_template('voting_stats.html', **data)
    finally:
        conn.close()


@app.route('/global_stats')
def global_stats():
    from global_stats_data import build_global_stats
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        data = build_global_stats(conn)
        return render_template('global_stats.html', **data)
    finally:
        conn.close()


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
    from recognition_stats_data import build_recognition_stats
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        data = build_recognition_stats(conn)
    finally:
        conn.close()
    return render_template('trivia_stats.html', **data)
