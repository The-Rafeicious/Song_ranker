"""Read-only opponent networks from effective votes and decided tournament matches."""
from collections import defaultdict
from songranker.catalog import source_sql, versus_metadata


def network_songs(conn):
    """Read current public identities once; no preview/private or pending state."""
    from songranker.modes.voting import finite
    artists = defaultdict(list)
    for r in conn.execute('SELECT sa.song_id,a.id,a.name FROM song_artists sa JOIN artists a ON a.id=sa.artist_id'):
        artists[r['song_id']].append(dict(id=r['id'],name=r['name']))
    songs = {}
    for r in conn.execute('SELECT s.id,s.title,s.elo_score,a.id album_id,a.title album,a.cover_url FROM songs s LEFT JOIN albums a ON a.id=s.album_id'):
        songs[r['id']] = dict(id=r['id'],title=r['title'],elo=finite(r['elo_score']),**versus_metadata(dict(id=r['album_id'],title=r['album'],cover_url=r['cover_url']),artists[r['id']]))
    ratings = sorted({s['elo'] for s in songs.values() if s['elo'] is not None},reverse=True)
    ranks = {}; standing = 1
    counts = defaultdict(int)
    for s in songs.values():
        if s['elo'] is not None:
            counts[s['elo']] += 1
    for elo in ratings:
        ranks[elo] = standing; standing += counts[elo]
    for s in songs.values():
        s['rank'] = ranks.get(s['elo'])
    return songs


def network_records(conn, songs, mode='all', source='all', include_local=False):
    """Deduplicate public first-round projections; show points-only rounds honestly."""
    from songranker.modes.voting import finite, saved_date
    from songranker.modes.tournament import recorded_result, stage_name
    brackets = {r['id']:dict(r) for r in conn.execute("SELECT id,size,is_blind,scope_type,status FROM tournaments WHERE status='completed'")
                if include_local or r['scope_type'] in ('global','tag')}
    rows, linked, omitted = [], set(), 0
    for raw in conn.execute(f'SELECT * FROM {source_sql(conn)}'):
        r = dict(raw)
        tournament = r.get('origin')=='tournament'
        if tournament and r.get('tournament_id') not in brackets:
            continue
        a,b = r['winner_id'],r['loser_id']
        if a not in songs or b not in songs or a==b:
            omitted += 1; continue
        wb,wa,lb,la = [finite(r.get(k)) for k in ('winner_before','winner_after','loser_before','loser_after')]
        valid = all(v is not None for v in (wb,wa,lb,la)) and wa>=wb and la<=lb and finite(wa-wb) is not None and finite(la-lb) is not None
        date = saved_date(r.get('created_at'))
        rows.append(dict(key='v'+str(r['id']),winner_id=a,loser_id=b,mode=r['mode'],source='first_round' if tournament else 'voting',
                         scope=brackets[r['tournament_id']]['scope_type'] if tournament else None,tournament_id=r.get('tournament_id'),
                         stage=stage_name(brackets[r['tournament_id']]['size'],1) if tournament else None,
                         time=date['iso'] if date else None,seconds=date['seconds'] if date else -1e30,
                         winner_before=wb if valid else None,winner_after=wa if valid else None,
                         loser_before=lb if valid else None,loser_after=la if valid else None,
                         rating_weight=finite(r.get('rating_weight')),points=None))
        if tournament and r.get('tournament_match_id') is not None:
            linked.add(r['tournament_match_id'])
    for raw in conn.execute("SELECT * FROM tournament_matches WHERE status='completed'"):
        r = dict(raw)
        if r['tournament_id'] not in brackets or r['id'] in linked:
            continue
        if not recorded_result(r) or r['winner_id'] not in songs or r['loser_id'] not in songs:
            omitted += 1; continue
        t = brackets[r['tournament_id']]; date = saved_date(r.get('played_at'))
        rows.append(dict(key='t'+str(r['id']),winner_id=r['winner_id'],loser_id=r['loser_id'],mode='blind' if t['is_blind'] else 'standard',
                         source='first_round' if r['round_number']==1 and r['match_type']=='bracket' else 'tournament',scope=t['scope_type'],
                         tournament_id=t['id'],stage=stage_name(t['size'],r['round_number'],r['match_type']),time=date['iso'] if date else None,
                         seconds=date['seconds'] if date else -1e30,winner_before=None,winner_after=None,loser_before=None,loser_after=None,
                         rating_weight=None,points=finite(r.get('points_awarded'))))
    rows = [r for r in rows if (mode=='all' or r['mode']==mode) and (source=='all' or r['source']==source)]
    rows.sort(key=lambda r:(r['seconds'],int(r['key'][1:]),r['key'][0]))
    return rows,omitted


def search_network_songs(conn, query):
    """Search the full current catalogue, including disconnected or capped-out songs."""
    import unicodedata
    def normal(value):
        """Ignore accents/case in public title and artist lookup."""
        return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))
    needle = normal(query.strip())
    songs = network_songs(conn)
    matches = [s for s in songs.values() if needle in normal(s['title']+' '+' '.join(a['name'] for a in s['artist_links']))]
    matches.sort(key=lambda s:(not normal(s['title']).startswith(needle),s['title'].casefold(),s['id']))
    return dict(songs=matches[:25],total=len(matches))


def build_match_network(conn, song_id=None, depth=4, branches=4, mode='all', source='all', include_local=False, through=None, pair=None, page=1):
    """Aggregate first, then bound drawing; pair histories retain all filtered results."""
    songs = network_songs(conn)
    rows,omitted = network_records(conn,songs,mode,source,include_local)
    total = len(rows); position = total if through is None else min(total,through)
    rows = rows[:position]
    timeline = dict(total=total,position=position,time=rows[-1]['time'] if rows else None)
    if pair:
        a,b = pair
        history = [r for r in rows if {r['winner_id'],r['loser_id']}=={a,b}]
        pages = max(1,(len(history)+19)//20); page = min(pages,max(1,page))
        return dict(pair=list(pair),songs={sid:songs[sid] for sid in pair},total=len(history),page=page,pages=pages,
                    history=list(reversed(history))[20*(page-1):20*page],timeline=timeline)
    pairs,adjacency = {},defaultdict(list)
    for i,r in enumerate(rows):
        a,b = sorted((r['winner_id'],r['loser_id']))
        edge = pairs.setdefault((a,b),dict(id=f'{a}-{b}',a=a,b=b,count=0,a_wins=0,b_wins=0,modes={},sources={},local=0,last=0))
        edge['count']+=1; edge['a_wins' if r['winner_id']==a else 'b_wins']+=1
        edge['modes'][r['mode']]=edge['modes'].get(r['mode'],0)+1
        edge['sources'][r['source']]=edge['sources'].get(r['source'],0)+1
        edge['local']+=r['scope'] in ('artist','album'); edge['last']=i
    for edge in pairs.values():
        adjacency[edge['a']].append(edge); adjacency[edge['b']].append(edge)
    levels = {}
    if song_id is not None:
        selected = {song_id}; levels[song_id]=0; frontier = [song_id]
        for level in range(1,depth+1):
            following = []
            for sid in frontier:
                added = 0
                for e in sorted(adjacency[sid],key=lambda e:(-e['count'],-e['last'],e['id'])):
                    other = e['b'] if e['a']==sid else e['a']
                    if other in selected:
                        continue
                    if added>=branches or len(selected)>=180:
                        break
                    selected.add(other); levels[other]=level; following.append(other); added+=1
            frontier = following
    else:
        selected = set(sorted(adjacency,key=lambda sid:(-len(adjacency[sid]),sid))[:1400])
    if song_id is not None:
        # Cross-links can shorten a discovery branch: show actual visible hops.
        levels = {song_id:0}; queue=[song_id]
        for sid in queue:
            for e in adjacency[sid]:
                other=e['b'] if e['a']==sid else e['a']
                if other in selected and other not in levels:
                    levels[other]=levels[sid]+1; queue.append(other)
    edges = sorted((e for e in pairs.values() if e['a'] in selected and e['b'] in selected),key=lambda e:(-e['count'],-e['last'],e['id']))
    candidate_edges = len(edges); edges = edges[:6000]
    nodes = [dict(songs[sid],level=levels.get(sid),opponents=len(adjacency[sid]),matches=sum(e['count'] for e in adjacency[sid])) for sid in sorted(selected)]
    return dict(nodes=nodes,edges=edges,focus_id=song_id,depth=depth,branches=branches,timeline=timeline,
                totals=dict(catalogue=len(songs),connected=len(adjacency),connections=len(pairs),matches=len(rows),shown_matches=sum(e['count'] for e in edges)),
                limits=dict(nodes=180 if song_id else 1400,edges=6000,limited=len(selected)<len(adjacency) if song_id is None else len(selected)>=180 and len(selected)<len(adjacency),edges_limited=candidate_edges>6000),omitted=omitted)
