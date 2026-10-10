"""Shared library projections and aggregation. Each song contributes once."""
from collections import defaultdict
from services import app, get_db_connection


def proper_album(album):
    title = str(album.get('title') or '').strip().casefold()
    return bool(title) and title != 'unknown album' and not title.endswith(' - single')


def collection():
    conn = get_db_connection()
    try:
        data = {'songs':[dict(r) for r in conn.execute('SELECT s.*,COALESCE(ts.attempts,0) AS attempts,COALESCE(ts.correct,0) AS correct FROM songs s LEFT JOIN trivia_stats ts ON ts.song_id=s.id')]}
        for key, table in [('artists','artists'),('albums','albums'),('tags','genres'),('history','history'),('tournaments','tournaments'),('tournament_entries','tournament_entries'),('tournament_matches','tournament_matches')]:
            data[key]=[dict(r) for r in conn.execute(f'SELECT * FROM {table}')]
        artist_links, tag_links = defaultdict(list), defaultdict(list)
        for row in conn.execute('SELECT * FROM song_artists'):artist_links[row['song_id']].append(row['artist_id'])
        for row in conn.execute('SELECT * FROM song_genres'):tag_links[row['song_id']].append(row['genre_id'])
        for song in data['songs']:
            song.update(artist_ids=artist_links[song['id']],tag_ids=tag_links[song['id']])
        data['history'].sort(key=lambda r:r['id'],reverse=True)
        data['tournaments'].sort(key=lambda r:r['id'],reverse=True)
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
        result.append({**row,'name':row.get('name',row.get('title')),'title':row.get('title',row.get('name')),
            'song_count':len(related),'avg_elo':sum(s['elo_score'] for s in related)/len(related) if related else 0,
            'impact_score':1200+sum(s['elo_score']-1200 for s in related),
            'artist':', '.join(dict.fromkeys(s['artist'] for s in related if s['artist']))})
    return sorted(result,key=lambda r:(-r['impact_score'],r['name'].casefold()))
