"""Read-only cross-mode query engine. Missing rates remain distinct from zero."""
import math
import unicodedata
from functools import cmp_to_key
from songranker.catalog import summarize_votes, song_performance
from urllib.parse import quote

KINDS = ('songs', 'artists', 'albums', 'tags')
METRICS = {}

def metric(key, label, family, unit='count'):
    METRICS[key] = dict(key=key, label=label, family=family, unit=unit)

for key, label, family, unit in [
    ('overall_score','Overall score','Overall','rating'), ('overall_evidence','Overall evidence','Overall','percent'), ('overall_modes','Overall modes with evidence','Overall','count'),
    ('tracks','Tracks','Catalogue','count'), ('elo','Elo · rated-track mean for collections','Voting','rating'),
    ('standard_elo','Non-blind Elo','Voting','rating'), ('blind_elo','Blind Elo','Voting','rating'),
    ('elo_gap','Blind minus Non-blind Elo · shared rated tracks','Voting','rating'),
    ('ordinary_matches','Ordinary voting match credit','Voting','count'), ('first_round_matches','Tournament first-round match credit','Voting','count'),
    ('trivia_correct','Recognition correct fields','Recognition','count'), ('trivia_available','Recognition available fields','Recognition','count'),
    ('trivia_rounds','Recognition rounds','Recognition','count'),
    ('trivia_accuracy','Recognition field accuracy','Recognition','percent'),
    ('title_accuracy','Title accuracy','Recognition','percent'), ('artist_accuracy','Artist accuracy','Recognition','percent'),
    ('album_accuracy','Album accuracy','Recognition','percent'),
    ('guess_rounds','Guesser appearances','Elo Guesser','count'), ('guess_accuracy','Guesser accuracy','Elo Guesser','percent'),
    ('shelf_rounds','Shelves track appearances','Album Shelves','count'),
    ('shelf_album','Shelves album accuracy','Album Shelves','percent'), ('shelf_order','Shelves order accuracy','Album Shelves','percent'),
    ('shelf_accuracy','Shelves points earned','Album Shelves','percent'),
    ('vibe_maps','Mapped Vibe selections','Vibe','count'), ('vibe_samples','Vibe samples','Vibe','count'),
    ('vibe_passes','Completed Vibe passes','Vibe','count'),
]: metric(key,label,family,unit)
for prefix, label in [('', 'All voting'), ('standard_', 'Non-blind'), ('blind_', 'Blind')]:
    for key, suffix in [('matches','matches'),('wins','wins'),('losses','losses'),('win_rate','win percentage')]:
        metric(prefix+key,label+' '+suffix,'Voting','percent' if key=='win_rate' else 'count')
for prefix,label in [('tournament_','Competition tournaments'),('local_','Local tournaments')]:
    for key,suffix in [('appearances','entry credit'),('wins','win credit'),('losses','loss credit'),('points','points'),('championships','championships'),('win_rate','win percentage')]:
        metric(prefix+key,label+' '+suffix,'Tournament','percent' if key=='win_rate' else 'count')


def normal(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)).casefold() if not unicodedata.combining(c))


def validate(spec):
    """Validate bounded public input before reading the catalogue; never execute SQL from it."""
    if not isinstance(spec,dict): raise ValueError('Query must be an object.')
    kind=spec.get('entity','songs')
    if kind not in KINDS: raise ValueError('Choose songs, artists, albums or tags.')
    filters=spec.get('filters',[])
    if not isinstance(filters,list) or len(filters)>8: raise ValueError('Use at most eight filters.')
    clean=[]
    for f in filters:
        if not isinstance(f,dict): raise ValueError('Invalid filter.')
        field=f.get('field')
        if field in ('won_against','lost_to','artist','album','tag'):
            target=int(f.get('target_id',0))
            if target<1: raise ValueError('Choose a saved target for each relationship.')
            source=f.get('source','all'); mode=f.get('mode','all')
            if source not in ('all','voting','first_round','tournament','local') or mode not in ('all','standard','blind'): raise ValueError('Invalid match source or visibility.')
            clean.append(dict(field=field,target_id=target,source=source,mode=mode)); continue
        if field not in METRICS: raise ValueError('Unknown statistic.')
        op=f.get('op','min')
        if op not in ('min','max','between','eq','has','missing'): raise ValueError('Invalid comparison.')
        row=dict(field=field,op=op)
        if op not in ('has','missing'):
            for k in (('value','max') if op=='between' else ('value',)):
                n=float(f.get(k,''))
                if not math.isfinite(n): raise ValueError('Enter a finite number.')
                if METRICS[field]['unit']=='percent' and not 0<=n<=100: raise ValueError('Percentages must be between 0 and 100.')
                if METRICS[field]['unit']=='count' and n<0: raise ValueError('Counts cannot be negative.')
                row[k]=n
            if op=='between' and row['max']<row['value']: raise ValueError('Range end must be at least its start.')
        clean.append(row)
    sorts=spec.get('sort',[dict(field='elo',direction='desc')])
    if not isinstance(sorts,list) or not 1<=len(sorts)<=3: raise ValueError('Choose one to three sort levels.')
    seen=set()
    for sort in sorts:
        if not isinstance(sort,dict) or sort.get('field') not in (*METRICS,'name') or sort.get('direction') not in ('asc','desc') or sort['field'] in seen: raise ValueError('Sort fields must be valid and different.')
        seen.add(sort['field'])
    columns=spec.get('columns',['elo','matches','win_rate','trivia_rounds','trivia_accuracy'])
    if not isinstance(columns,list) or len(columns)>6 or any(c not in METRICS for c in columns): raise ValueError('Choose up to six statistics.')
    columns=list(dict.fromkeys([s['field'] for s in sorts if s['field']!='name']+columns))[:6]
    return dict(entity=kind,q=str(spec.get('q',''))[:200],filters=clean,sort=sorts,columns=columns,page=max(1,int(spec.get('page',1))))


def rate(n,d):
    return 100*n/d if d else None


def facts(songs, competition, local, song=False):
    """Pool numerators/denominators, counting each current track once per entity."""
    def total(key): return sum(s.get(key,0) or 0 for s in songs)
    def mean(rows,key): return sum(r[key] for r in rows)/len(rows) if rows else None
    tested=[s for s in songs if s.get('elo_matches_played',0)>0]
    pooled=summarize_votes(s.get('voting',{}) for s in songs)
    votes=pooled['raw']
    result={k:votes.get(k) for k in METRICS if k in votes}
    result.update(ordinary_matches=pooled['ordinary']['matches'],first_round_matches=pooled['tournament']['matches'],trivia_correct=total('correct'),trivia_available=total('available_points'),tracks=len(songs),elo=mean(songs if song else tested,'elo_score'),
        trivia_rounds=total('attempts'),trivia_accuracy=rate(total('correct'),total('available_points')),
        title_accuracy=rate(total('title_correct'),total('new_attempts')),artist_accuracy=rate(total('artist_correct'),total('new_attempts')),
        album_accuracy=rate(total('album_correct'),total('album_attempts')),
        guess_rounds=total('guess_attempts'),guess_accuracy=rate(total('guess_correct'),total('guess_attempts')),
        shelf_rounds=total('shelf_attempts'),shelf_album=rate(total('shelf_album_correct'),total('shelf_attempts')),
        shelf_order=rate(total('shelf_order_right'),total('shelf_order_pairs')),shelf_accuracy=rate(total('shelf_points'),total('shelf_available')),
        vibe_maps=sum(v.get('status')=='mapped' for s in songs for v in s.get('vibe_maps',{}).values()),
        vibe_samples=sum(v.get('sample_count',0) for s in songs for v in s.get('vibe_maps',{}).values()),vibe_passes=total('vibe_completed_passes'))
    shared=[]
    for mode in ('standard','blind'):
        ratings=[s.get('mode_ratings',{}).get(mode,{}) for s in songs]
        result[mode+'_elo']=mean([r for r in ratings if r.get('matches',0)>0],'elo')
    for s in songs:
        modes=s.get('mode_ratings',{})
        if all(modes.get(m,{}).get('matches',0)>0 for m in ('standard','blind')):
            shared.append(modes['blind']['elo']-modes['standard']['elo'])
    result['elo_gap']=sum(shared)/len(shared) if shared else None
    for prefix, records in [('tournament_',competition),('local_',local)]:
        for key in ('appearances','wins','losses','points','championships'):
            source='championships' if key=='championships' else 'tournament_'+key
            result[prefix+key]=sum(records[s['id']].get(source,0) for s in songs)
        result[prefix+'win_rate']=rate(result[prefix+'wins'],result[prefix+'wins']+result[prefix+'losses'])
    return result


def identities(data):
    """Public identity projection excludes preview URLs and private source metadata."""
    result={}
    for kind in KINDS:
        result[kind]={r['id']:dict(id=r['id'],name=r.get('name',r.get('title','')),kind=kind,
            cover=r.get('image_url',r.get('cover_url','')) or '',url='/'+{'songs':'song','artists':'artist','albums':'album','tags':'tag'}[kind]+'/'+(str(r['id']) if kind=='songs' else quote(r.get('name',r.get('title','')),safe=''))) for r in data[kind]}
    for s in data['songs']:
        r=result['songs'][s['id']]
        r['cover']=result['albums'].get(s.get('album_id'),{}).get('cover','')
        r['related']=[result[k][i] for k,ids in [('artists',s.get('artist_ids',[])),('albums',[s.get('album_id')]),('tags',s.get('tag_ids',[]))] for i in ids if i in result[k]]
    for kind in ('artists','albums','tags'):
        for r in result[kind].values():
            if not r['cover']:
                r['cover']=next((result['songs'][s['id']]['cover'] for s in data['songs'] if (r['id'] in s.get('artist_ids',[]) if kind=='artists' else s.get('album_id')==r['id'] if kind=='albums' else r['id'] in s.get('tag_ids',[]))), '')
    return result


def execute(data,spec):
    """Filter and stably sort a full snapshot, returning exactly twenty rows per page."""
    spec=validate(spec); ids=identities(data); kind=spec['entity']
    from songranker.overall import evaluate
    overall={r['id']:r for r in evaluate(data)['entities'][kind]}
    for f in spec['filters']:
        if 'target_id' in f:
            target_kind={'artist':'artists','album':'albums','tag':'tags'}.get(f['field'],'songs')
            target=ids[target_kind].get(f['target_id'])
            if not target: raise ValueError('The selected relationship target no longer exists.')
            f['target_name']=target['name']
    completed={**data,'tournaments':[t for t in data['tournaments'] if t.get('status')=='completed']}
    competition=song_performance(completed)
    local=song_performance({**completed,'tournaments':[t for t in completed['tournaments'] if t.get('scope_type') in ('artist','album')]},competitive=False)
    rows=[]
    for identity in ids[kind].values():
        group=[s for s in data['songs'] if (s['id']==identity['id'] if kind=='songs' else identity['id'] in s.get('artist_ids',[]) if kind=='artists' else s.get('album_id')==identity['id'] if kind=='albums' else identity['id'] in s.get('tag_ids',[]))]
        values=facts(group,competition,local,kind=='songs')
        score=overall.get(identity['id'],{})
        values.update(overall_score=score.get('score'),overall_evidence=score.get('evidence',0),overall_modes=score.get('mode_count',0))
        song_ids={s['id'] for s in group}
        if spec['q'] and normal(spec['q']) not in normal(' '.join([identity['name']]+[ids['songs'][s['id']]['name'] for s in group]+[r['name'] for s in group for r in ids['songs'][s['id']]['related']])): continue
        keep=True
        for f in spec['filters']:
            field=f['field']
            if field in ('artist','album','tag'):
                keep=any(f['target_id'] in s.get(field+'_ids',[]) if field!='album' else s.get('album_id')==f['target_id'] for s in group)
            elif field in ('won_against','lost_to'):
                own,other=('winner_id','loser_id') if field=='won_against' else ('loser_id','winner_id')
                keep=any(m[own] in song_ids and m[other]==f['target_id'] and (f['mode']=='all' or m['mode']==f['mode']) and ((f['source']=='local' and m.get('scope') in ('artist','album')) or (m.get('scope') not in ('artist','album') and (f['source']=='all' or m['source']==f['source']))) for m in data.get('query_matches',[]))
            else:
                value=values.get(field); op=f['op']
                keep=(value is None) if op=='missing' else (value is not None) if op=='has' else value is not None and (value>=f['value'] if op=='min' else value<=f['value'] if op=='max' else value==f['value'] if op=='eq' else f['value']<=value<=f['max'])
            if not keep: break
        if keep: rows.append({**identity,'values':values,'related':identity.get('related',[]) if kind=='songs' else [ids['songs'][s['id']] for s in group[:5]]})
    def compare(a,b):
        for sort in spec['sort']:
            key=sort['field']; x=normal(a['name']) if key=='name' else a['values'].get(key); y=normal(b['name']) if key=='name' else b['values'].get(key)
            if x is None or y is None:
                if x is not y: return 1 if x is None else -1
            elif x!=y: return ((x>y)-(x<y))*(1 if sort['direction']=='asc' else -1)
        return (normal(a['name'])>normal(b['name']))-(normal(a['name'])<normal(b['name'])) or a['id']-b['id']
    rows.sort(key=cmp_to_key(compare)); total=len(rows); pages=max(1,math.ceil(total/20)); spec['page']=min(spec['page'],pages)
    return dict(spec=spec,total=total,pages=pages,page=spec['page'],items=rows[(spec['page']-1)*20:spec['page']*20])
