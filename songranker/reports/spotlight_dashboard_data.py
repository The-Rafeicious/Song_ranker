"""Read-only Spotlight dashboard records, using the established voting layout."""
from collections import defaultdict

from songranker.reports.tournament_stats_data import saved_time


def enrich_spotlight(conn, data, songs):
    details = data['details']
    rows = list(details['songs'].values())
    for row in rows:
        row['song'] = songs[row['song_id']]
    details['records'] = [
        dict(title='Most supported tracks',metric='support',rows=details['leaders']),
        dict(title='Highest mean points · 3+ rounds',metric='points',
             rows=sorted((r for r in rows if r['offers']>=3),
                         key=lambda r:(-r['mean_points'],-r['offers'],r['song_id']))[:5]),
        dict(title='Most judged tracks',metric='offers',
             rows=sorted(rows,key=lambda r:(-r['offers'],-r['adjusted_support'],r['song_id']))[:5]),
        dict(title='Strongest connection · 3+ placements',metric='connection',
             rows=sorted((r for r in rows if r['connection_offers']>=3),
                         key=lambda r:(-r['mean_connection'],-r['connection_offers'],r['song_id']))[:5]),
    ]
    groups = {kind:{} for kind in ('artist','album','tag')}
    tags = defaultdict(list)
    for r in conn.execute('SELECT sg.song_id,g.id,g.name FROM song_genres sg JOIN genres g ON g.id=sg.genre_id'):
        tags[r['song_id']].append(dict(id=r['id'],name=r['name']))
    for row in rows:
        song=row['song']
        memberships = dict(artist=song['artist_links'],
            album=[dict(id=song['album_link']['id'],name=song['album_link']['title'])] if song['album_link'] else [],
            tag=tags[row['song_id']])
        for kind,entities in memberships.items():
            for entity in entities:
                group=groups[kind].setdefault(entity['id'],dict(id=entity['id'],name=entity['name'],
                    tracks=0,offers=0,points=0,support_total=0,
                    cover_url=song['cover_url'] if kind=='album' else None))
                group['tracks']+=1;group['offers']+=row['offers'];group['points']+=row['points']
                group['support_total']+=row['support_total']
    details['categories']=[]
    for kind,title in [('artist','Artist records'),('album','Album records'),('tag','Tag records')]:
        values=list(groups[kind].values())
        for row in values:
            row['mean_points']=row['points']/row['offers']
            row['mean_support']=row['support_total']/row['offers']
        details['categories'].append(dict(kind=kind,title=title,
            most=sorted(values,key=lambda r:(-r['offers'],-r['tracks'],r['id']))[:5],
            best=sorted((r for r in values if r['offers']>=5),
                        key=lambda r:(-r['mean_support'],-r['offers'],r['id']))[:5]))
    dates = conn.execute("""SELECT MIN(closed_at) first,MAX(closed_at) latest
        FROM judgement_rounds WHERE mode='spotlight' AND status='answered'""").fetchone()
    busiest=conn.execute("""SELECT date(closed_at,'unixepoch') day,COUNT(*) rounds
        FROM judgement_rounds WHERE mode='spotlight' AND status='answered'
        GROUP BY day ORDER BY rounds DESC,day DESC LIMIT 1""").fetchone()
    summary=data['summary']
    details['activity']=dict(first=saved_time(dates['first']),latest=saved_time(dates['latest']),
        busiest_day=busiest['day'] if busiest else None,busiest_rounds=busiest['rounds'] if busiest else 0,
        mean_day=summary['rounds']/summary['active_days'] if summary['active_days'] else None)
