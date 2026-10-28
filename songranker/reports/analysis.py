"""Read-only entity comparisons from the shared, consistently hydrated snapshot."""
from collections import Counter, defaultdict
from math import ceil, isfinite
from statistics import fmean, median
from songranker.catalog import ranked, song_performance
from songranker.overall import evaluate, features, METRICS
from songranker.reports.stats_activity import timestamp

# Key, label, semantic colour, numerator, denominator. Rates pool opportunities.
RATES=[('win_rate','Voting win rate','voting','wins','matches'),
 ('standard_rate','Non-blind win rate','standard','standard_wins','standard_matches'),
 ('blind_rate','Blind win rate','blind','blind_wins','blind_matches'),
 ('recognition','All-field recognition','recognition','correct','available_points'),
 ('title_rate','Title recognition','recognition','title_correct','new_attempts'),
 ('artist_rate','Artist recognition','recognition','artist_correct','new_attempts'),
 ('album_rate','Album recognition','recognition','album_correct','album_attempts'),
 ('shelf_order','Shelf order','shelves','shelf_order_right','shelf_order_pairs'),
 ('shelf_album','Shelf album placement','shelves','shelf_album_correct','shelf_attempts'),
 ('guess_rate','Guesser accuracy','guesser','guess_correct','guess_attempts')]


def ratio(a,b):
    """Return a pooled percentage, preserving absent evidence as unavailable."""
    return round(100*a/b,2) if b else None


def build_analysis(data, args):
    """Analyse one entity and optional peer; keep denominators and scopes explicit.

    Entity aggregates count distinct linked tracks; internal group votes count as
    two track appearances. History and daily charts count each event once. Local
    tournaments have their own raw record and never enter competition metrics.
    """
    kind=args.get('kind','song')
    if kind not in ('song','artist','album','tag'):raise ValueError('Invalid entity type')
    charts=('bars','scatter','activity','elo')
    chart=args.get('chart','bars')
    if chart not in charts:raise ValueError('Invalid chart type')
    songs={s['id']:dict(s) for s in ranked(data,'songs')}
    overall=evaluate(data,details=True)
    scores={s['id']:s for s in overall['entities']['songs']}
    facts=features(data)
    local_data={**data,'tournaments':[t for t in data['tournaments'] if t.get('scope_type') in ('artist','album') and t.get('status')=='completed']}
    local=song_performance(local_data,competitive=False)
    for sid,s in songs.items():
        s['overall']=scores[sid]['score'];s['families']=scores[sid]['mode_count']
        s['elo']=s['elo_score'] if s.get('elo_matches_played',0) else None
        v=s.get('voting',{})
        for key,label,tone,a,b in RATES:
            source=v if key in ('win_rate','standard_rate','blind_rate') else s
            s[key]=ratio(source.get(a,0),source.get(b,0))
        s['entries']=s['tournament_appearances'];s['titles']=s['championships']
        s['points']=s['tournament_points'];s['votes']=s.get('elo_matches_played',0)
        s['tournament_rate']=ratio(s['tournament_wins'],s['tournament_wins']+s['tournament_losses'])
    metrics=[('overall','Mean measured Overall','overall'),('elo','Public Elo','voting'),('votes','Elo appearances','voting'),('families','Scored modes','overall')]+[(a,b,c) for a,b,c,_,_ in RATES]+[('tournament_rate','Competition match wins','tournament'),('entries','Competition entries','tournament'),('titles','Competition titles','tournament'),('points','Competition points','tournament')]
    metric=args.get('metric','overall');y_metric=args.get('y','win_rate')
    metric_map={m[0]:m for m in metrics}
    if metric not in metric_map or y_metric not in metric_map:raise ValueError('Invalid chart metric')
    try:
        selected=int(args.get('id','') or 0);peer=int(args.get('compare','') or 0)
        page=max(1,int(args.get('page',1)));minimum=max(0,int(args.get('minimum',0)))
    except (ValueError,TypeError):raise ValueError('Invalid record or pagination')
    entities={'song':list(songs.values()),'artist':data['artists'],'album':data['albums'],'tag':data['tags']}
    choices=sorted([dict(id=e['id'],name=e.get('name',e.get('title','')),cover_url=e.get('cover_url','')) for e in entities[kind]],key=lambda e:(e['name'].casefold(),e['id']))
    if not selected and choices:selected=choices[0]['id']
    identity=next((e for e in entities[kind] if e['id']==selected),None)
    if identity is None and choices:raise ValueError('Record unavailable')
    if peer and not any(e['id']==peer for e in entities[kind]):raise ValueError('Comparison unavailable')

    def members(key):
        """Return distinct current entity members; collaboration links can overlap."""
        return [s for s in songs.values() if (s['id']==key if kind=='song' else key in s.get('artist_ids',[]) if kind=='artist' else s.get('album_id')==key if kind=='album' else key in s.get('tag_ids',[]))]

    def summary(rows):
        """Pool rates by opportunities; average measured scores without fake zeros."""
        result={};v={k:sum(s.get('voting',{}).get(k,0) for s in rows) for k in ('wins','matches','standard_wins','standard_matches','blind_wins','blind_matches')}
        for key,label,tone,a,b in RATES:
            n=v.get(a,0) if key in ('win_rate','standard_rate','blind_rate') else sum(s.get(a,0) for s in rows)
            d=v.get(b,0) if key in ('win_rate','standard_rate','blind_rate') else sum(s.get(b,0) for s in rows)
            result[key]=dict(label=label,tone=tone,value=ratio(n,d),detail=f'{n:g} / {d:g}',unit='%')
        for key,label,tone in metrics:
            if key in result:continue
            values=[s[key] for s in rows if s.get(key) is not None]
            value=fmean(values) if values and key in ('overall','elo','families') else sum(values) if values else None
            result[key]=dict(label=label,tone=tone,value=value,detail=f'{len(values)} measured tracks',unit='')
        wins=sum(s['tournament_wins'] for s in rows);played=wins+sum(s['tournament_losses'] for s in rows)
        result['tournament_rate'].update(value=ratio(wins,played),detail=f'{wins:g} / {played:g}',unit='%')
        return result

    rows=members(selected);ids={s['id'] for s in rows};peer_rows=members(peer) if peer else []
    primary=summary(rows);comparison=summary(peer_rows) if peer else {}
    coverage=[]
    for mode,label,tone in [('elo','Voting','voting'),('trivia','Trivia','recognition'),('tournament','Competition tournament','tournament'),('shelves','Shelves','shelves'),('guesser','Guesser','guesser')]:
        counts=[facts[s['id']]['mode_appearances'].get(mode,0) for s in rows]
        coverage.append(dict(label=label,tone=tone,tested=sum(n>0 for n in counts),repeated=sum(n>1 for n in counts),appearances=sum(counts),total=len(rows)))
    breadth=Counter(sum(any(facts[s['id']]['mode_appearances'].get(m,0)>0 for m in modes) for modes in [('elo',),('trivia',),('tournament',),('shelves',),('guesser',)]) for s in rows)
    events=[h for h in data['elo_history'] if h.get('winner_id') in ids or h.get('loser_id') in ids]
    opponents=defaultdict(lambda:dict(wins=0,losses=0,weight=0))
    days=Counter();sources=Counter();upsets=eligible=0
    for h in events:
        a,b=h.get('winner_id'),h.get('loser_id');sources[(h.get('origin','ordinary'),h['mode'])]+=1
        date=timestamp(h.get('created_at'))
        if date:days[date.date().isoformat()]+=1
        if a in ids and b not in ids:opponents[b]['wins']+=1;opponents[b]['weight']+=h.get('rating_weight',1)
        if b in ids and a not in ids:opponents[a]['losses']+=1;opponents[a]['weight']+=h.get('rating_weight',1)
        before_a,before_b=h.get('winner_before'),h.get('loser_before')
        if a in ids and b not in ids and isinstance(before_a,(int,float)) and isinstance(before_b,(int,float)) and before_a!=before_b:
            eligible+=1;upsets+=before_a<before_b
    opponent_rows=[dict(song=songs[sid],**v) for sid,v in opponents.items() if sid in songs]
    opponent_rows.sort(key=lambda r:-(r['wins']+r['losses']))
    brackets={t['id']:t for t in data['tournaments']}
    matches=[m for m in data['tournament_matches'] if m.get('status')=='completed' and m.get('winner_id')!=m.get('loser_id') and (m.get('winner_id') in ids or m.get('loser_id') in ids)]
    local_record={key:sum(local[sid][key] for sid in ids) for key in ('championships','podiums','tournament_wins','tournament_losses','tournament_points','tournament_appearances')}
    # Unfinished Blind bracket identities never leave this private aggregation.
    routes=[dict(match=m,bracket=brackets[m['tournament_id']],winner=songs.get(m.get('winner_id')),loser=songs.get(m.get('loser_id'))) for m in matches if m['tournament_id'] in brackets and (not brackets[m['tournament_id']].get('is_blind') or brackets[m['tournament_id']]['status']=='completed')]
    trivia=[r for r in data.get('analysis_trivia',[]) if r['song_id'] in ids]
    timings=[]
    for field in ('title','artist','album'):
        values=[r.get(field+'_seconds') for r in trivia if r.get(field+'_correct')==1 and isinstance(r.get(field+'_seconds'),(int,float)) and isfinite(r[field+'_seconds']) and r[field+'_seconds']>=0]
        timings.append(dict(label=field.title(),n=len(values),mean=fmean(values) if values else None,median=median(values) if values else None))
    relationships=[]
    for relation,key in [('artist','artist_ids'),('album','album_id'),('tag','tag_ids')]:
        counts=Counter(i for s in rows for i in ([s.get(key)] if relation=='album' else set(s.get(key,[]))))
        lookup={r['id']:r for r in data[relation+'s' if relation!='tag' else 'tags']}
        relationships.append(dict(kind=relation,rows=[dict(lookup[i],name=lookup[i].get('name',lookup[i].get('title')),count=n) for i,n in counts.most_common() if i in lookup]))
    pool=[s for s in {s['id']:s for s in rows+peer_rows}.values() if s['votes']>=minimum]
    measured=sorted([s for s in pool if s[metric] is not None],key=lambda s:(-s[metric],s['title'].casefold()))
    chart_rows=measured[:10]+([s for s in measured[-10:] if s not in measured[:10]] if len(measured)>10 else [])
    max_value=max([abs(s[metric]) for s in chart_rows]+[1])
    bars=[dict(song=s,value=s[metric],width=100*abs(s[metric])/max_value) for s in chart_rows]
    scatter=[s for s in pool if s[metric] is not None and s[y_metric] is not None]
    x_values=[s[metric] for s in scatter];y_values=[s[y_metric] for s in scatter]
    xmin=min(x_values,default=0);xmax=max(x_values,default=1);ymin=min(y_values,default=0);ymax=max(y_values,default=1)
    points=[dict(song=s,x=45+710*(s[metric]-xmin)/(xmax-xmin or 1),y=270-230*(s[y_metric]-ymin)/(ymax-ymin or 1)) for s in scatter]
    elo_events=sorted([h for h in events if kind=='song'],key=lambda h:h['id'])
    elo_values=[h.get('winner_after') if h.get('winner_id')==selected else h.get('loser_after') for h in elo_events]
    elo_values=[v for v in elo_values if isinstance(v,(int,float)) and isfinite(v)]
    low=min(elo_values,default=0);high=max(elo_values,default=1)
    line=' '.join(f'{45+710*i/max(1,len(elo_values)-1):.2f},{270-230*(v-low)/(high-low or 1):.2f}' for i,v in enumerate(elo_values))
    population=[]
    for key,label,tone in metrics:
        values=sorted(s[key] for s in songs.values() if s[key] is not None)
        selected_values=[s[key] for s in rows if s[key] is not None]
        population.append(dict(label=label,tone=tone,n=len(values),mean=fmean(values) if values else None,median=median(values) if values else None,low=values[int((len(values)-1)*.1)] if values else None,high=values[int((len(values)-1)*.9)] if values else None,percentile=ratio(sum(v<=fmean(selected_values) for v in values),len(values)) if values and selected_values else None))
    pages=max(1,ceil(len(measured)/30));page=min(page,pages)
    return dict(population=population,event_count=len(events),official=next((r for r in overall['entities'][kind+'s' if kind!='song' else 'songs'] if r['id']==selected),None),kind=kind,identity=identity,selected=selected,peer=peer,choices=choices,rows=rows,primary=primary,comparison=comparison,peer_identity=next((e for e in entities[kind] if e['id']==peer),None),metrics=metrics,metric=metric,metric_label=metric_map[metric][1],metric_tone=metric_map[metric][2],y_metric=y_metric,y_label=metric_map[y_metric][1],chart=chart,minimum=minimum,bars=bars,points=points,xmin=xmin,xmax=xmax,ymin=ymin,ymax=ymax,line=line,low=low,high=high,elo_values=elo_values,coverage=coverage,breadth=sorted(breadth.items()),opponents=opponent_rows[:20],events=events[:30],sources=[dict(origin=o,mode=m,count=n) for (o,m),n in sources.items()],upsets=upsets,upset_opportunities=eligible,days=sorted(days.items())[-90:],day_max=max(days.values(),default=1),routes=routes[-20:],local_record=local_record,timings=timings,relationships=relationships,facts=facts,scores=scores,table=measured[(page-1)*30:page*30],page=page,pages=pages,total=len(measured),snapshot=overall['calibration']['id'])
