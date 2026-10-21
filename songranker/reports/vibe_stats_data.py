"""Read-only Vibe Map dashboard; one aggregate per song, never per-play histories."""
from collections import defaultdict
from heapq import heappush, heapreplace
from itertools import combinations
import math

from songranker.catalog import proper_album, versus_metadata
from songranker.modes.vibe_similarity import WIDTH, positions, compare_positions
from songranker.storage.vibe_state import MAPS, DISPLAY_MAPS
from songranker.vibe_maps import map_definitions, song_profiles, pass_counts

SIGNAL = .2  # One unit on the displayed -5..5 axes; neutral points are not poles.
DENSITY_RADIUS = .2


def percentage(numerator,denominator):
    return round(100*numerator/denominator,1) if denominator else None


def consistency(vectors):
    """Gaussian of mean squared pair distance, equally weighting four maps.

    Centred sums avoid an O(n²) group-pair loop. With two tracks this is exactly
    their public similarity. Repeats and group size do not multiply a song's vote.
    """
    n=len(vectors)
    if n<2:return None
    squared=0.0
    for key,*_ in MAPS:
        for axis in (0,1):
            mean=math.fsum(v[key][axis] for v in vectors)/n
            squared+=math.fsum((v[key][axis]-mean)**2 for v in vectors)
    mean_pair_distance=2*squared/((n-1)*len(MAPS))
    return 100*math.exp(-mean_pair_distance/(2*WIDTH**2))


def density(points):
    """Fixed-radius neighbours on a spatial grid; each point stays at its location."""
    bins=defaultdict(list)
    for i,p in enumerate(points):
        bins[(math.floor(p['x']/DENSITY_RADIUS),math.floor(p['y']/DENSITY_RADIUS))].append(i)
    for p in points:
        gx,gy=math.floor(p['x']/DENSITY_RADIUS),math.floor(p['y']/DENSITY_RADIUS)
        p['nearby']=sum((points[i]['x']-p['x'])**2+(points[i]['y']-p['y'])**2<=DENSITY_RADIUS**2+1e-12
            for x in range(gx-1,gx+2) for y in range(gy-1,gy+2) for i in bins.get((x,y),()))
    maximum=max((p['nearby'] for p in points),default=0)
    return maximum


def colour_points(points, maximum):
    for p in points:
        strength=math.sqrt(p['nearby']/maximum)
        p.update(cx=round(28+(p['x']+1)*242,4),cy=round(388-(p['y']+1)*180,4),
                 colour='rgb('+','.join(str(round(a+(b-a)*strength)) for a,b in zip((150,52,73),(255,211,188)))+')',
                 opacity=round(.35+.55*strength,3))


def paired_highlights(complete,songs,vectors):
    nearest=[];furthest=[]
    def retain(heap,rank,pair):
        item=(rank,pair)
        if len(heap)<2:heappush(heap,item)
        elif rank>heap[0][0]:heapreplace(heap,item)
    for i,a in enumerate(complete):
        for b in complete[i+1:]:
            value=compare_positions(vectors[a],vectors[b])['similarity']
            pair=dict(first=songs[a],second=songs[b],similarity=round(value,1),shared_maps=len(MAPS))
            retain(nearest,(value,-a,-b),pair)
            retain(furthest,(-value,-a,-b),pair)
    return ([p for _,p in sorted(nearest,reverse=True)], [p for _,p in sorted(furthest,reverse=True)])


def common_patterns(vectors):
    axes=[dict(id=key+'_'+axis,map_id=key,axis=index,low=low,high=high)
          for key,_,xl,xh,yl,yh in DISPLAY_MAPS for axis,index,low,high in (('x',0,xl,xh),('y',1,yl,yh))]
    balances=[]
    for a in axes:
        values=[v[a['map_id']][a['axis']] for v in vectors.values() if a['map_id'] in v]
        low=sum(v < -SIGNAL for v in values);high=sum(v>SIGNAL for v in values);middle=len(values)-low-high
        balances.append(dict(a,low_count=low,high_count=high,middle_count=middle,total=len(values),
            low_share=percentage(low,len(values)) or 0,high_share=percentage(high,len(values)) or 0,
            middle_share=percentage(middle,len(values)) or 0,
            centre='Present' if a['id']=='perspective_x' else 'Balanced'))
    patterns=[]
    for a,b in combinations(axes,2):
        common=[v for v in vectors.values() if a['map_id'] in v and b['map_id'] in v]
        for sign_a,label_a in ((-1,a['low']),(1,a['high'])):
            for sign_b,label_b in ((-1,b['low']),(1,b['high'])):
                count=sum(v[a['map_id']][a['axis']]*sign_a>SIGNAL and v[b['map_id']][b['axis']]*sign_b>SIGNAL for v in common)
                if count:patterns.append(dict(label=label_a+' + '+label_b,count=count,total=len(common),share=percentage(count,len(common))))
    patterns.sort(key=lambda p:(-p['count'],-p['share'],p['label']))
    return balances,patterns[:8]


def build_vibe_stats(conn):
    albums={r['id']:dict(r) for r in conn.execute('SELECT id,title,cover_url FROM albums ORDER BY id')}
    artists={r['id']:dict(r) for r in conn.execute('SELECT id,name,cover_url FROM artists ORDER BY id')}
    tags={r['id']:dict(r) for r in conn.execute('SELECT id,name FROM genres ORDER BY id')}
    artist_members=defaultdict(set);tag_members=defaultdict(set);album_members=defaultdict(set);song_artists=defaultdict(set)
    for row in conn.execute('SELECT song_id,artist_id FROM song_artists'):
        if row['artist_id'] in artists:artist_members[row['artist_id']].add(row['song_id']);song_artists[row['song_id']].add(row['artist_id'])
    for row in conn.execute('SELECT song_id,genre_id FROM song_genres'):
        if row['genre_id'] in tags:tag_members[row['genre_id']].add(row['song_id'])
    songs={}
    for row in conn.execute('SELECT id,title,album_id FROM songs ORDER BY id'):
        song=dict(row);aa=[artists[aid] for aid in song_artists[song['id']]];album=albums.get(song['album_id'])
        song.update(versus_metadata(album,aa));song['artist']=', '.join(a['name'] for a in song['artist_links'])
        songs[song['id']]=song
        if album:album_members[album['id']].add(song['id'])
    profiles=song_profiles(conn,songs);passes=pass_counts(conn,songs)
    vectors={sid:positions({'vibe_maps':profile}) for sid,profile in profiles.items()}
    complete=[sid for sid in songs if len(vectors[sid])==len(MAPS)]
    selected=sum(any(p['status']!='unmapped' for p in profile.values()) for profile in profiles.values())
    placed=sum(map(len,vectors.values()));samples=sum(max(p['sample_count'],int(p['status']=='placed')) for profile in profiles.values() for p in profile.values())
    overview=dict(total=len(songs),selected=selected,full=len(complete),partial=selected-len(complete),unselected=len(songs)-selected,
        passes=sum(passes.values()),repeated=sum(passes[sid]>1 or any(p['sample_count']>1 for p in profiles[sid].values()) for sid in songs),
        samples=samples,coverage=percentage(selected,len(songs)),placed=placed,slots=4*len(songs),
        map_coverage=percentage(placed,4*len(songs)),consistency=consistency([vectors[s] for s in complete]))
    maps=map_definitions(conn)
    for m in maps:
        points=[dict(song_id=sid,title=songs[sid]['title'],artist=songs[sid]['artist'],x=v[m['id']][0],y=v[m['id']][1])
                for sid,v in vectors.items() if m['id'] in v]
        m.update(points=points,count=len(points),unmapped=len(songs)-len(points),max_nearby=density(points),coverage=percentage(len(points),len(songs)))
    maximum=max((m['max_nearby'] for m in maps),default=0)
    for m in maps:colour_points(m['points'],maximum)
    balances,patterns=common_patterns(vectors)
    closest,contrasts=paired_highlights(complete,songs,vectors)
    groups=[]
    for kind,entities,members in (('album',albums,album_members),('artist',artists,artist_members),('tag',tags,tag_members)):
        rows=[]
        for eid,entity in entities.items():
            if kind=='album' and not proper_album(entity):continue
            ids=members[eid]&songs.keys();mapped=[sid for sid in sorted(ids) if len(vectors[sid])==len(MAPS)]
            if len(mapped)<2:continue
            value=consistency([vectors[sid] for sid in mapped])
            rows.append(dict(id=eid,name=entity.get('name',entity.get('title')),cover_url=entity.get('cover_url') or '',
                             mapped=len(mapped),total=len(ids),coverage=percentage(len(mapped),len(ids)),consistency=round(value,1),_score=value))
        high=sorted(rows,key=lambda r:(-r['_score'],-r['mapped'],-r['coverage'],r['id']))[:5]
        low=sorted(rows,key=lambda r:(r['_score'],-r['mapped'],-r['coverage'],r['id']))[:5]
        for row in rows:row.pop('_score')
        groups.append(dict(kind=kind,title=dict(album='Albums',artist='Artists',tag='Tags')[kind],eligible=len(rows),most=high,least=low))
    return dict(overview=overview,maps=maps,balances=balances,patterns=patterns,closest=closest,contrasts=contrasts,groups=groups)
