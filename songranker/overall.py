"""A personal composite score, derived on demand. No database writes or schema.

Display the existing composite directly, with category rank kept separate.
Participation adapts weights/evidence on each snapshot; ineligible inputs never count.
"""

from collections import defaultdict, OrderedDict
import hashlib
import json
import math
import statistics
import threading
import time
from flask import abort, jsonify, render_template, request, session, has_request_context
from songranker import services
from songranker.services import app, admin_required
from songranker.catalog import collection, proper_album


VERSION=6
# Five equally based game families. Voting's three correlated views share 20%.
MODE_SPECS=[('elo','Elo',8),('standard','Non-blind voting',6),('blind','Blind voting',6),
            ('trivia','Recognisability',20),('tournament','Tournament',20),
            ('guesser','Elo Guesser',20),('shelves','Album Shelves',20)]
FAMILIES={'voting':('elo','standard','blind'),'trivia':('trivia',),
          'tournament':('tournament',),'guesser':('guesser',),'shelves':('shelves',)}
# Within-mode policy weights. Derived duplicate totals are explained in Dev.
METRICS=[('elo_current','elo','Current Elo',.85,'elo'),('elo_peak','elo','Peak Elo',.15,'elo'),
 ('standard_wins','standard','Win rate',1,'rate'),('blind_wins','blind','Win rate',1,'rate'),
 ('trivia_title','trivia','Song recognition',.45,'rate'),('trivia_artist','trivia','Artist recognition',.15,'rate'),
 ('trivia_album','trivia','Album recognition',.25,'rate'),('trivia_perfect','trivia','Perfect rounds',.15,'rate'),
 ('tournament_wins','tournament','Match win rate',.30,'rate'),
 ('tournament_podium','tournament','Podium achievement',.45,'rate'),
 ('tournament_points','tournament','Points per completed entry / 7',.25,'rate'),
 ('guess_accuracy','guesser','Correct comparisons',1,'rate'),
 ('shelf_order','shelves','Relative track order',5/6,'rate'),
 ('shelf_album','shelves','Album placement',1/6,'rate')]
NEUTRAL=50.0
RATE_MIX=dict(actual=.6,population=.4)
_models=OrderedDict()
_lock=threading.RLock()

def number(value,default=0):
    """Coerce a finite numeric value, returning the requested default for invalid
    input.
    """
    try:
        value=float(value)
        return value if math.isfinite(value) else default
    except (TypeError,ValueError):return default

def feature(value,n,applicable=True):
    """Represent one Overall metric with its measured value, evidence count and
    eligibility flag.
    """
    n=max(0,number(n))
    return dict(value=number(value,None) if value is not None and n else None,n=n,applicable=applicable)

def ratio(right,total,evidence=None,applicable=True):
    """Build a bounded success-rate feature with explicit evidence and eligibility."""
    total=max(0,number(total))
    return feature(max(0,min(1,number(right)/total)) if total else None,
                   total if evidence is None else evidence,applicable)

def shelf_eligible_ids(data):
    """Match the game's per-track pool: real album, unique slot, >=2 tracks."""
    albums={a['id']:a for a in data.get('albums',[])}
    occupied=defaultdict(list)
    for song in data.get('songs',[]):
        position=song.get('track_number');disc=song.get('disc_number',1)
        if type(position) is int and position>0 and type(disc) is int and disc>0:
            occupied[(song.get('album_id'),disc,position)].append(song['id'])
    groups=defaultdict(list)
    for (album_id,_,_),ids in occupied.items():
        if len(ids)==1 and proper_album(albums.get(album_id,{})) and not albums[album_id].get('shelves_excluded',0):
            groups[album_id].extend(ids)
    return {sid for ids in groups.values() if len(ids)>=2 for sid in ids}


def features(data):
    """Derive per-song Overall metric values and mode appearances from saved
    catalogue/result facts.
    """
    albums={a['id']:a for a in data.get('albums',[])}
    shelf_ids=shelf_eligible_ids(data)
    trivia={s['song_id']:s for s in data.get('overall_sources',{}).get('trivia_stats',[])}
    perfect=defaultdict(lambda:[0,0])
    for row in data.get('overall_sources',{}).get('trivia_rounds',[]):
        sid=row['song_id'];perfect[sid][1]+=1
        perfect[sid][0]+=int(bool(row['title_correct']) and bool(row['artist_correct']) and
                             (not row['album_available'] or bool(row['album_correct'])))
    brackets={t['id']:t for t in data.get('tournaments',[])}
    entries=defaultdict(set)
    for row in data.get('tournament_entries',[]):entries[row['song_id']].add(row['tournament_id'])
    tournament_points=defaultdict(float)
    for row in data.get('tournament_matches',[]):
        if row.get('status')!='completed':continue
        for sid in (row.get('song1_id'),row.get('song2_id')):
            if sid:entries[sid].add(row['tournament_id'])
        if brackets.get(row['tournament_id'],{}).get('status')=='completed':
            tournament_points[row.get('winner_id')]+=number(row.get('points_awarded'))
    # Legacy completed brackets can lack entry rows but still contain placements.
    for t in brackets.values():
        if t.get('status')=='completed':
            for key in ('champion_id','runner_up_id','third_place_id'):
                if t.get(key):entries[t[key]].add(t['id'])
    result={}
    for song in data.get('songs',[]):
        sid=song['id'];v=song.get('voting',{});t=trivia.get(sid,song)
        elo_n=max(number(song.get('matches_played')),number(v.get('matches')))
        completed=[brackets[id] for id in entries[sid] if brackets.get(id,{}).get('status')=='completed']
        podium=0
        for b in completed:
            credit=1 if b.get('champion_id')==sid else .65 if b.get('runner_up_id')==sid else .35 if b.get('third_place_id')==sid else 0
            difficulty=math.log2(max(2,number(b.get('size'),8)))/3
            podium+=1-(1-credit)**difficulty
        title_n=max(0,number(t.get('new_attempts')))
        audio_available=bool(str(song.get('audio_url') or '').strip())
        result[sid]={
          'elo_current':feature(song.get('elo_score'),elo_n),
          'elo_peak':feature(song.get('highest_elo'),elo_n),
          'standard_wins':ratio(v.get('standard_wins'),v.get('standard_matches')),
          'blind_wins':ratio(v.get('blind_wins'),v.get('blind_matches'),applicable=audio_available),
          'trivia_title':ratio(t.get('title_correct'),title_n,applicable=audio_available),
          'trivia_artist':ratio(t.get('artist_correct'),title_n,applicable=audio_available),
          'trivia_album':ratio(t.get('album_correct'),t.get('album_attempts'),applicable=audio_available and proper_album(albums.get(song.get('album_id'),{})) and not albums.get(song.get('album_id'),{}).get('shelves_excluded',0)),
          'trivia_perfect':ratio(*perfect[sid],applicable=audio_available),
          'tournament_wins':ratio(song.get('tournament_wins'),number(song.get('tournament_wins'))+number(song.get('tournament_losses'))),
          'tournament_podium':ratio(podium,len(completed)),
          'tournament_points':ratio(tournament_points[sid],7*len(completed),evidence=len(completed)),
          'guess_accuracy':ratio(song.get('guess_correct'),song.get('guess_attempts')),
          'shelf_order':ratio(song.get('shelf_order_right'),song.get('shelf_order_pairs'),evidence=song.get('shelf_attempts',0),applicable=sid in shelf_ids),
          'shelf_album':ratio(song.get('shelf_album_correct'),song.get('shelf_attempts'),applicable=sid in shelf_ids),
        }
        result[sid]['mode_appearances']=dict(elo=elo_n,standard=number(v.get('standard_matches')),
            blind=number(v.get('blind_matches')),trivia=max(title_n,perfect[sid][1]),
            tournament=max(len(entries[sid]),number(song.get('tournament_appearances'))),
            guesser=number(song.get('guess_attempts')),shelves=number(song.get('shelf_attempts')))
    return result

def quantile(values,fraction):
    """Interpolate a population quantile, returning zero for an empty distribution."""
    if not values:return 0.0
    rows=sorted(values);position=(len(rows)-1)*fraction;lower=int(position)
    upper=min(len(rows)-1,lower+1)
    return rows[lower]+(rows[upper]-rows[lower])*(position-lower)


def exposure_reference(values):
    """Average = 50% evidence; robust high (90th percentile) = 100%."""
    if not values:return dict(average_appearances=0,high_appearances=0,max_appearances=0)
    average=statistics.fmean(values);high=quantile(values,.9)
    # Flat/very skewed populations have no upper span: use twice the average.
    if high<=average:high=2*average
    return dict(average_appearances=average,high_appearances=high,max_appearances=max(values))


def relative_evidence(n,reference):
    """Scale a song's appearances against the population average and high-exposure
    reference.
    """
    average=reference['average_appearances'];high=reference['high_appearances']
    if n<=0 or average<=0:return 0.0
    if n<=average:return .5*n/average
    return min(1,.5+.5*(n-average)/(high-average))


def population(facts):
    """Build metric calibration statistics from eligible songs with measured
    evidence.
    """
    result={}
    for key,mode,label,weight,kind in METRICS:
        applicable=[f[key] for f in facts.values() if f[key]['applicable']]
        rows=[r for r in applicable if r['value'] is not None and r['n']>0]
        n=sum(r['n'] for r in rows)
        mean=(statistics.fmean(r['value'] for r in rows) if kind=='elo' else sum(r['value']*r['n'] for r in rows)/n) if rows else None
        spread=statistics.pstdev(r['value'] for r in rows) if len(rows)>1 else 0
        result[key]=dict(key=key,mode=mode,label=label,policy_share=weight,kind=kind,
                         mean=mean,spread=max(40,spread) if kind=='elo' else spread,
                         appearances=n,tested_songs=len(rows),eligible_songs=len(applicable),active=bool(rows),
                         **exposure_reference([r['n'] for r in rows]))
    return result


def topology(data):
    """Hash catalogue eligibility and membership so Overall calibration detects
    structural changes.
    """
    rows=[(s['id'],s.get('album_id'),s.get('disc_number',1),s.get('track_number'),bool(str(s.get('audio_url') or '').strip()),sorted(set(s.get('artist_ids',[]))),sorted(set(s.get('tag_ids',[])))) for s in data.get('songs',[])]
    structure=[sorted(rows),[(kind,sorted((r['id'],(proper_album(r),bool(r.get('shelves_excluded',0))) if kind=='albums' else True) for r in data.get(kind,[]))) for kind in ('artists','albums','tags')]]
    return hashlib.sha256(json.dumps(structure).encode()).hexdigest()


def capped_shares(strengths,cap):
    """Proportional shares with a family cap; release excess to other families."""
    pending={key:value for key,value in strengths.items() if value>0};result={};remaining=1.0
    while pending:
        total=sum(pending.values())
        over=[key for key,value in pending.items() if remaining*value/total>cap+1e-12]
        if not over:
            result.update({key:remaining*value/total for key,value in pending.items()});break
        for key in over:
            result[key]=cap;remaining-=cap;del pending[key]
    return result


def calibrate(facts,data,force=False):
    """Build and cache current Overall metric/mode calibration from result evidence
    and catalogue eligibility.
    """
    observed=population(facts);shape=topology(data);key=str(services.DB_NAME);modes=[]
    for mode,label,weight in MODE_SPECS:
        keys=[m['key'] for m in observed.values() if m['mode']==mode]
        eligible=[fact for fact in facts.values() if any(fact[k]['applicable'] for k in keys)]
        tested=[fact for fact in eligible if any(fact[k]['applicable'] and fact[k]['value'] is not None and fact[k]['n']>0 for k in keys)]
        # One appearance total per game, never a sum of duplicated metric fields.
        counts=[max(1,fact['mode_appearances'][mode]) for fact in tested]
        family=next(name for name,members in FAMILIES.items() if mode in members)
        modes.append(dict(key=mode,label=label,family=family,base_weight=weight,active=bool(tested),
                          eligible_songs=len(eligible),tested_songs=len(tested),
                          participation=len(tested)/len(eligible) if eligible else 0,
                          appearances=sum(counts),**exposure_reference(counts)))
    family_depths=[]
    for members in FAMILIES.values():
        active=[m for m in modes if m['key'] in members and m['active']]
        if active:family_depths.append(sum(m['base_weight']*m['average_appearances'] for m in active)/sum(m['base_weight'] for m in active))
    depth_reference=math.exp(statistics.fmean(math.log(n) for n in family_depths)) if family_depths else 0
    for mode in modes:
        average=mode['average_appearances']
        mode['depth_factor']=average/(average+depth_reference) if average else 0
        mode['support']=math.sqrt(mode['participation'])*mode['depth_factor']
    family_strengths={family:sum(m['base_weight']*m['support'] for m in modes if m['key'] in members)/20 for family,members in FAMILIES.items()}
    active_families=sum(value>0 for value in family_strengths.values())
    cap=min(1,1/active_families+.1) if active_families else 1
    shares=capped_shares(family_strengths,cap)
    for mode in modes:
        members=[m for m in modes if m['family']==mode['family']]
        total=sum(m['base_weight']*m['support'] for m in members)
        mode['weight']=100*shares.get(mode['family'],0)*mode['base_weight']*mode['support']/total if total else 0
        metric_total=sum(m['policy_share'] for m in observed.values() if m['mode']==mode['key'] and m['active'])
        for metric in observed.values():
            if metric['mode']==mode['key']:
                metric['mode_share']=metric['policy_share']/metric_total if metric['active'] and metric_total else 0
                metric['overall_weight']=mode['weight']*metric['mode_share']
    families=[dict(key=family,base_weight=20,weight=100*shares.get(family,0),support=strength,active=strength>0)
              for family,strength in family_strengths.items()]
    identity=hashlib.sha256(json.dumps([VERSION,RATE_MIX,observed,modes,shape],sort_keys=True).encode()).hexdigest()[:16]
    with _lock:
        previous=_models.get(key)
        if previous and previous['id']==identity and not force:return previous
        model=dict(id=identity,version=VERSION,generated_at=time.time(),topology=shape,modes=modes,metrics=observed,
                   families=families,rate_mix=RATE_MIX,group_prior_songs=2,neutral_score=NEUTRAL,
                   depth_reference=depth_reference,family_cap=100*cap,score_scale='composite percentage',
                   refresh_after_seconds=0,refresh_threshold='every change to saved results or eligibility')
        _models[key]=model;_models.move_to_end(key)
        while len(_models)>8:_models.popitem(last=False)
        return model


def metric_score(value,calibration):
    """Normalise an observed metric against its population and shrink it toward
    neutral by evidence.
    """
    if value['value'] is None or not value['n']:return .5,0
    raw=value['value'];confidence=relative_evidence(value['n'],calibration)
    if calibration['kind']=='elo':
        z=max(-35,min(35,(raw-calibration['mean'])/(1.5*calibration['spread'])))
        normalized=1/(1+math.exp(-z))
    else:
        mean=max(.05,min(.95,calibration['mean']))
        relative=.5+.5*(raw-mean)/(1-mean) if raw>=mean else .5*raw/mean
        normalized=RATE_MIX['actual']*raw+RATE_MIX['population']*relative
    return .5+(normalized-.5)*confidence,confidence

def song_score(fact,model,details=False):
    """Combine eligible mode contributions into a song's Overall score and evidence
    diagnostics.
    """
    weighted=0;evidence=0;contributions=[];mode_count=0
    # Structurally unavailable modes are omitted; merely unplayed modes stay neutral.
    eligible_modes=[mode for mode in model['modes'] if mode['active'] and any(
        metric['active'] and fact[metric['key']]['applicable'] for metric in model['metrics'].values() if metric['mode']==mode['key'])]
    family_totals={family:sum(mode['weight'] for mode in eligible_modes if mode['family']==family)
                   for family in FAMILIES}
    family_count=sum(total>0 for total in family_totals.values())
    shares=capped_shares(family_totals,min(1,1/family_count+.1)) if family_count else {}
    for mode in eligible_modes:
        mode_weight=100*shares[mode['family']]*mode['weight']/family_totals[mode['family']]
        metrics=[m for m in model['metrics'].values() if m['mode']==mode['key'] and m['active'] and fact[m['key']]['applicable']]
        weight_sum=sum(m['policy_share'] for m in metrics)
        score=0;confidence=0;parts=[]
        for m in metrics:
            share=m['policy_share']/weight_sum;value=fact[m['key']];adjusted,c=metric_score(value,m)
            score+=share*adjusted;confidence+=share*c
            if details:parts.append(dict(key=m['key'],label=m['label'],raw=value['value'],appearances=value['n'],
                                        adjusted=100*adjusted,evidence=100*c,weight=mode_weight*share))
        mode_count+=int(confidence>0);weighted+=mode_weight/100*score;evidence+=mode_weight/100*confidence
        contributions.append(dict(key=mode['key'],label=mode['label'],weight=mode_weight,score=100*score,
                                  evidence=100*confidence,points=mode_weight*score,
                                  **({'metrics':parts} if details else {})))
    composite=100*weighted if evidence else None
    return dict(score=composite,composite_score=composite,evidence=100*evidence,mode_count=mode_count,contributions=contributions,
                track_count=1,tested_tracks=int(evidence>0),raw_score=100*weighted)


def entity_score(ids,scores,details=False):
    """Aggregate member-song scores into an evidence-adjusted collection score with a
    neutral prior.
    """
    tracks=[scores[id] for id in sorted(set(ids)) if id in scores]
    tested=sum(s['composite_score'] is not None for s in tracks)
    evidence=sum(t['evidence']/100 for t in tracks);n=len(tracks)
    average=sum(t['composite_score'] if t['composite_score'] is not None else NEUTRAL for t in tracks)/n if n else None
    diagnostics=dict(mean_score=average,effective_songs=evidence,prior_score=NEUTRAL,group_prior_songs=2) if details else {}
    if not tracks or not tested:return dict(score=None,composite_score=None,evidence=0,mode_count=0,track_count=n,tested_tracks=0,contributions=[],**diagnostics)
    confidence=evidence/(evidence+2)
    composite=NEUTRAL+(average-NEUTRAL)*confidence
    contributions=[]
    # A no-album song can omit Shelves, so members need not share the same keys.
    indices=[{c['key']:c for c in track['contributions']} for track in tracks]
    for key,label,_ in MODE_SPECS:
        related=[index[key] for index in indices if key in index]
        if not related:continue
        count=len(related)
        contributions.append(dict(key=key,label=label,weight=sum(c['weight'] for c in related)/n,
                                  score=sum(c['score'] for c in related)/count,evidence=sum(c['evidence'] for c in related)/count,
                                  points=sum(c['points'] for c in related)/n,applicable_tracks=count))
        # Presentation only: mode inputs weighted by each song's actual allocation.
        # Confidence shrinks their final weight; the remaining share stays neutral.
        mode = contributions[-1]
        allocated = sum(c['weight'] for c in related)
        mode.update(display_score=100*mode['points']/mode['weight'] if mode['weight'] else NEUTRAL,
                    display_weight=mode['weight']*confidence,
                    display_points=mode['points']*confidence,
                    display_evidence=sum(c['weight']*c['evidence'] for c in related)/allocated if allocated else 0)
    neutral_weight=max(0,100-sum(c['display_weight'] for c in contributions))
    return dict(score=composite,composite_score=composite,evidence=100*evidence/n,
                mode_count=sum(c['evidence']>0 for c in contributions),track_count=n,tested_tracks=tested,
                contributions=contributions,group_confidence=100*confidence,
                neutral_balance=dict(score=NEUTRAL,weight=neutral_weight,points=NEUTRAL*neutral_weight/100),**diagnostics)


def apply_display_scores(rows):
    """Preserve raw distances/endpoints; category standing never rescales a score."""
    measured=sorted((r for r in rows if r['composite_score'] is not None and r.get('eligible',True)),key=lambda r:-r['composite_score'])
    count=len(measured);position=0
    for row in rows:
        row.update(score=None,rank=None,rank_population=count,rank_percentile=None,percentile_population=count)
    while position<count:
        end=position+1
        while end<count and measured[end]['composite_score']==measured[position]['composite_score']:end+=1
        # Retain this legacy diagnostic for API readers; it has no display role.
        percentile=100*(count-end+(end-position-1)/2)/(count-1) if count>1 else 50.0
        for row in measured[position:end]:
            row['rank_percentile']=percentile
            row.update(score=row['composite_score'],rank=position+1)
        position=end


def evaluate(data,force=False,details=False):
    """Compute and rank Overall songs, artists, albums and tags with calibration and
    summary diagnostics.
    """
    facts=features(data)
    model=calibrate(facts,data,force)
    if has_request_context():
        # Ratios live on the server. Keep only a compact version marker in cookies.
        compact=dict(id=model['id'],version=VERSION,generated_at=model['generated_at'])
        if session.get('overall_calibration')!=compact:session['overall_calibration']=compact
    scored={sid:song_score(fact,model,details) for sid,fact in facts.items()}
    by_album=defaultdict(list);by_artist=defaultdict(set);by_tag=defaultdict(set)
    album_lookup={a['id']:a for a in data.get('albums',[])}
    result={kind:[] for kind in ('songs','artists','albums','tags')}
    for song in data.get('songs',[]):
        sid=song['id'];album=album_lookup.get(song.get('album_id'),{})
        result['songs'].append(dict(id=sid,name=song['title'],title=song['title'],cover_url=album.get('cover_url'),**scored[sid]))
        by_album[song.get('album_id')].append(sid)
        for id in set(song.get('artist_ids',[])):by_artist[id].add(sid)
        for id in set(song.get('tag_ids',[])):by_tag[id].add(sid)
    apply_display_scores(result['songs'])
    for kind,index in [('artists',by_artist),('albums',by_album),('tags',by_tag)]:
        for entity in data.get(kind,[]):
            name=entity.get('name',entity.get('title',''))
            row=dict(id=entity['id'],name=name,title=name,cover_url=entity.get('cover_url'),eligible=kind!='albums' or proper_album(entity),**entity_score(index[entity['id']],scored,details))
            if details:
                linked_ids=set(index[entity['id']])
                row['linked_songs']=[dict(id=s['id'],name=s['name'],score=s['score'],
                                         composite_score=s['composite_score'],
                                         counted_score=s['composite_score'] if s['composite_score'] is not None else NEUTRAL,
                                         evidence=s['evidence'],mode_count=s['mode_count'])
                                     for s in result['songs'] if s['id'] in linked_ids]
            result[kind].append(row)
        apply_display_scores(result[kind])
    for rows in result.values():rows.sort(key=lambda r:(r['score'] is None,-(r['score'] or 0),-r['evidence'],r['name'].casefold(),r['id']))
    highlights={kind:next((r for r in rows if r['score'] is not None and r.get('eligible',True)),None) for kind,rows in result.items()}
    measured=[s for s in result['songs'] if s['score'] is not None]
    summary=dict(average=sum(s['score'] for s in measured)/len(measured) if measured else None,tested_songs=len(measured),songs=len(result['songs']),
                 evidence=sum(s['evidence'] for s in result['songs'])/len(result['songs']) if result['songs'] else 0,active_modes=sum(m['active'] for m in model['modes']))
    return dict(entities=result,highlights=highlights,summary=summary,calibration=model)

@app.route('/overall_rankings')
def overall_rankings():return render_template('app_page.html',page='overall_rankings')

@app.route('/api/overall')
def overall_api():
    response=jsonify(evaluate(collection(True)));response.headers['Cache-Control']='no-store';return response

@app.route('/api/overall/details')
def overall_details():
    kind=request.args.get('type','songs')
    try:id=int(request.args.get('id',''))
    except ValueError:abort(400)
    if kind not in ('songs','artists','albums','tags'):abort(400)
    result=evaluate(collection(True),details=True)
    row=next((r for r in result['entities'][kind] if r['id']==id),None)
    if not row:abort(404)
    response=jsonify(entity=row,calibration=result['calibration']);response.headers['Cache-Control']='no-store';return response

@app.route('/api/dev/overall/recalibrate',methods=['POST'])
@admin_required
def recalibrate_overall():return jsonify(evaluate(collection(True),force=True))
