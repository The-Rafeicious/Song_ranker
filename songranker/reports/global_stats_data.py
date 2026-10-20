"""Read-only Global Stats projections from one SQLite snapshot."""
from songranker.reports.stats_activity import attach_reports
from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
from songranker.catalog import (proper_album, versus_metadata, voting_records, summarize_votes)
from songranker.modes.special_modes import special_records


def timestamp(value):
    if value is None:return 0
    try:
        if isinstance(value,(int,float)):return float(value)
        date=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError,TypeError,OverflowError):return 0


def percent(correct,total):
    return round(100*correct/total,1) if total else None


def build_global_stats(conn):
    songs={r['id']:dict(r) for r in conn.execute('SELECT * FROM songs')}
    artists={r['id']:dict(r) for r in conn.execute('SELECT * FROM artists')}
    albums={r['id']:dict(r) for r in conn.execute('SELECT * FROM albums')}
    tags={r['id']:dict(r) for r in conn.execute('SELECT * FROM genres')}
    artist_songs=defaultdict(set);tag_songs=defaultdict(set)
    song_artists=defaultdict(set);album_songs=defaultdict(list)
    for r in conn.execute('SELECT * FROM song_artists'):
        if r['song_id'] in songs and r['artist_id'] in artists:
            artist_songs[r['artist_id']].add(r['song_id']);song_artists[r['song_id']].add(r['artist_id'])
    for r in conn.execute('SELECT * FROM song_genres'):
        if r['song_id'] in songs and r['genre_id'] in tags:tag_songs[r['genre_id']].add(r['song_id'])
    for s in songs.values():
        s.update(versus_metadata(albums.get(s['album_id']), [artists[a] for a in song_artists[s['id']]]))
        s['artist']=', '.join(sorted(artists[a]['name'] for a in song_artists[s['id']]))
        album_songs[s['album_id']].append(s)
    proper={aid:a for aid,a in albums.items() if proper_album(a)}
    artist_rows=[];album_rows=[]
    for aid,a in artists.items():
        tracks=[songs[sid] for sid in artist_songs[aid]]
        if not tracks:continue
        best=max(tracks,key=lambda s:s['elo_score'])
        artist_rows.append(dict(a,title=a['name'],songs=len(tracks),
            albums=len({s['album_id'] for s in tracks if s['album_id'] in proper}),
            avg_elo=sum(s['elo_score'] for s in tracks)/len(tracks),
            artwork=a.get('cover_url') or best['cover_url']))
    for aid,a in proper.items():
        tracks=album_songs[aid]
        if not tracks:continue
        album_rows.append(dict(a,songs=len(tracks),avg_elo=sum(s['elo_score'] for s in tracks)/len(tracks),
            artist=', '.join(sorted({artists[x]['name'] for s in tracks for x in song_artists[s['id']]}))))
    from songranker.elo_history import source_sql
    history=[dict(r) for r in conn.execute(f"SELECT * FROM {source_sql(conn)} WHERE mode IN ('standard','blind')")]
    valid=[h for h in history if h['winner_id'] in songs and h['loser_id'] in songs and h['winner_id']!=h['loser_id']]
    votes=voting_records(conn);voting=summarize_votes(votes.values());leaders={}
    for key,prefix in [('overall',''),('standard','standard_'),('blind','blind_')]:
        eligible=sorted((sid for sid,v in votes.items() if v[prefix+'matches']),
            key=lambda sid:(-votes[sid][prefix+'win_rate'],-votes[sid][prefix+'matches'],songs[sid]['title'].casefold()))
        leaders[key]=[dict(songs[sid],wins=votes[sid][prefix+'wins'],losses=votes[sid][prefix+'losses'],
            win_rate=round(votes[sid][prefix+'win_rate'],1)) for sid in eligible[:3]]
    pairs=Counter(tuple(sorted((h['winner_id'],h['loser_id']))) for h in valid)
    matchups=[dict(s1=songs[a],s2=songs[b],encounters=n) for (a,b),n in sorted(pairs.items(),key=lambda r:(-r[1],r[0]))[:5]]
    # Extra rows are offered only when at least four pairs have repeat encounters.
    expandable=sum(m['encounters']>=2 for m in matchups)>3
    if not expandable:matchups=matchups[:3]
    def record(label,row,kind,key,unit=''):
        if row is None:return None
        name=row.get('title',row.get('name',''))
        href=f"/song/{row['id']}" if kind=='song' else None
        return dict(label=label,row=row,kind=kind,name=name,value=round(row[key],2) if key=='wins' else round(row[key]),unit=unit,href=href)
    srows=list(songs.values());most_wins=max(srows,key=lambda s:(votes[s['id']]['wins'],s['elo_score']),default=None)
    if most_wins:most_wins=dict(most_wins,wins=votes[most_wins['id']]['wins'])
    tag_rows=sorted([dict(t,songs=len(tag_songs[tid])) for tid,t in tags.items() if tag_songs[tid]],key=lambda t:(-t['songs'],t['name'].casefold()))
    records=[record('Highest Elo',max(srows,key=lambda s:s['elo_score'],default=None),'song','elo_score'),
        record('Lowest Elo',min(srows,key=lambda s:s['elo_score'],default=None),'song','elo_score'),
        record('Most wins',most_wins if most_wins and most_wins['wins'] else None,'song','wins','win weight'),
        record('Most voted track',max((dict(s,vote_count=votes[s['id']]['raw']['matches']) for s in srows),key=lambda s:s['vote_count'],default=None),'song','vote_count','votes'),
        record('Most tracks by an artist',max(artist_rows,key=lambda a:(a['songs'],a['name']),default=None),'artist','songs','tracks'),
        record('Most albums by an artist',max((a for a in artist_rows if a['albums']),key=lambda a:(a['albums'],a['songs']),default=None),'artist','albums','albums'),
        record('Biggest album',max(album_rows,key=lambda a:(a['songs'],a['avg_elo']),default=None),'album','songs','tracks'),
        record('Most used tag',tag_rows[0] if tag_rows else None,'tag','songs','tracks')]
    trivia={r['song_id']:dict(r) for r in conn.execute('SELECT * FROM trivia_stats')}
    fields=[]
    for field,label,denom in [('title','Song','new_attempts'),('artist','Artist','new_attempts'),('album','Album','album_attempts')]:
        total=sum(max(0,r[denom]) for r in trivia.values());correct=sum(max(0,min(r[denom],r[field+'_correct'])) for r in trivia.values())
        fields.append(dict(label=label,attempts=total,correct=correct,missed=total-correct,accuracy=percent(correct,total)))
    missed_artists=Counter();missed_albums=Counter();artist_attempts=Counter();album_attempts=Counter()
    for sid,r in trivia.items():
        if sid not in songs:continue
        for aid in song_artists[sid]:
            missed_artists[aid]+=max(0,r['new_attempts']-r['artist_correct']);artist_attempts[aid]+=max(0,r['new_attempts'])
        aid=songs[sid]['album_id']
        if aid in proper:
            missed_albums[aid]+=max(0,r['album_attempts']-r['album_correct']);album_attempts[aid]+=max(0,r['album_attempts'])
    def misses(counter,attempts,rows):
        return [dict(rows[key],misses=n,attempts=attempts[key]) for key,n in sorted(counter.items(),key=lambda r:(-r[1],r[0])) if n][:3]
    recognized=[dict(songs[sid],accuracy=percent(r['correct'],r['available_points'])) for sid,r in trivia.items() if sid in songs and r['available_points']>0]
    recognition=dict(fields=fields,correct=sum(f['correct'] for f in fields),available=sum(f['attempts'] for f in fields),
        tested=len([r for r in trivia.values() if r['new_attempts']>0]),missed=fields[0]['missed'],
        missed_tracks=sum(r['new_attempts']>r['title_correct'] for r in trivia.values()),
        above_ninety=sum((r['accuracy'] or 0)>90 for r in recognized),
        best=max(recognized,key=lambda r:(r['accuracy'],trivia[r['id']]['attempts']),default=None),
        missed_artists=misses(missed_artists,artist_attempts,artists),missed_albums=misses(missed_albums,album_attempts,albums))
    recognition['accuracy']=percent(recognition['correct'],recognition['available'])
    globals_=dict(conn.execute('SELECT key,value FROM global_stats'))
    recognition.update(best_score=globals_.get('trivia_high_score',0),best_streak=globals_.get('trivia_high_streak',0))
    from songranker.modes.challenges import records as challenge_records
    recognition['challenge']=challenge_records(conn,'trivia')
    brackets=[dict(r) for r in conn.execute('SELECT * FROM tournaments')]
    finished=sorted((t for t in brackets if t['status']=='completed'),key=lambda t:(timestamp(t['completed_at'] or t['created_at']),t['id']),reverse=True)
    bracket_matches=[dict(r) for r in conn.execute("SELECT * FROM tournament_matches WHERE status='completed'")]
    def saved_song(sid):return songs.get(sid,dict(id=None,title='Removed track',cover_url='',artist=''))
    latest=finished[0] if finished else None
    podium=[dict(saved_song(latest[column]),place=place) for place,column in [(1,'champion_id'),(2,'runner_up_id'),(3,'third_place_id')]
        if latest and latest.get(column) is not None]
    champions=[dict(saved_song(t['champion_id']),bracket_id=t['id'],size=t['size'],completed_at=t['completed_at']) for t in finished[:5]]
    tournament=dict(total=len(brackets),unfinished=len(brackets)-len(finished),sizes=Counter(t['size'] for t in brackets),
        matches=len(bracket_matches),points=round(sum(r['points_awarded'] or 0 for r in bracket_matches),2),
        podium=podium,latest_id=latest['id'] if latest else None,champions=champions)
    special,summary,_,recent_shelves=special_records(conn);guess=summary['guesser'];shelf=summary['shelves']
    guess.update(wrong=guess['rounds']-guess['correct'],tested=sum(r['guess_attempts']>0 for r in special.values()))
    def special_leader(key):
        eligible=[dict(songs[sid],value=r[key]) for sid,r in special.items() if r[key]>0]
        return max(eligible,key=lambda s:(s['value'],s['elo_score']),default=None)
    guess['most_tested']=special_leader('guess_attempts')
    missed_guesses=[dict(songs[sid],value=r['guess_attempts']-r['guess_correct']) for sid,r in special.items() if r['guess_attempts']>r['guess_correct']]
    guess['most_missed']=max(missed_guesses,key=lambda s:(s['value'],s['elo_score']),default=None)
    shelf_albums=[dict(r) for r in conn.execute('''SELECT a.*,COUNT(DISTINCT i.round_id) rounds,
        COUNT(*) placements,SUM(i.answer_slot!=i.album_slot) misses FROM album_shelf_items i
        JOIN album_shelf_rounds r ON r.id=i.round_id JOIN albums a ON a.id=i.album_id
        WHERE r.completed_at IS NOT NULL GROUP BY a.id''')]
    shelf.update(albums=len(shelf_albums),album_accuracy=percent(shelf['album_correct'],shelf['tracks']),
        order_accuracy=percent(shelf['order_right'],shelf['order_pairs']),
        most_played=max(shelf_albums,key=lambda a:(a['rounds'],a['placements']),default=None),
        most_missed=max((a for a in shelf_albums if a['misses']),key=lambda a:(a['misses'],a['placements']),default=None))
    bands=Counter(50*math.floor(s['elo_score']/50) for s in songs.values())
    bounds=list(range(min(bands),max(bands)+50,50)) if bands and (max(bands)-min(bands))/50<=60 else sorted(bands)
    elo=[dict(start=b,band=f'{b}–{b+49}',count=bands[b]) for b in bounds]
    activity=[]
    def event(kind,id,when,title,details,href,related,metrics=None,artwork=None,scope=None):
        moment=timestamp(when)
        date=datetime.fromtimestamp(moment,timezone.utc) if moment else None
        activity.append(dict(kind=kind,id=id,timestamp=moment,date=date.strftime('%d %b · %H:%M') if date else 'Date unavailable',
            iso=date.isoformat() if date else '',title=title,details=details,href=href,
            related=[dict(row,entity_kind=row.get('entity_kind','song')) for row in related],
            metrics=metrics or [],cover_url=artwork if artwork is not None else (related[0].get('cover_url','') if related else ''),scope=scope))
    def metric(value,label,state=''):
        return dict(value=value,label=label,state=state)
    def vote_participant(h,role):
        before=h.get(role+'_before');after=h.get(role+'_after')
        delta=round(after-before,1) if before is not None and after is not None else None
        return dict(saved_song(h[role+'_id']),role='Winner' if role=='winner' else 'Loser',
                    outcome=role,elo_delta=f'{delta:+g}' if delta is not None else None)
    from songranker.elo_history import (source_sql, summary as elo_summary)
    elo_feed=[dict(row) for row in conn.execute(f'SELECT * FROM {source_sql(conn)}')]
    for h in sorted(elo_feed,key=lambda h:(timestamp(h['created_at']),h['id']),reverse=True)[:10]:
        tournament_vote=h.get('origin')=='tournament'
        title=('Tournament #'+str(h['tournament_id'])+' · Round 1 Elo') if tournament_vote else ('Blind Audition' if h['mode']=='blind' else 'Standard Vote')
        href='/tournament_stats?tournament='+str(h['tournament_id']) if tournament_vote else '/history'
        event('tournament' if tournament_vote else h['mode'],h['id'],h['created_at'],title,('Half Elo' if h.get('rating_weight')==.5 else 'Full Elo') if tournament_vote else 'Vote recorded',href,
              [vote_participant(h,'winner'),vote_participant(h,'loser')])
    trivia_total=conn.execute('SELECT COUNT(*) FROM trivia_rounds WHERE completed_at IS NOT NULL').fetchone()[0]
    rounds=[dict(r) for r in conn.execute('SELECT * FROM trivia_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC LIMIT 10')]
    for r in rounds:
        right=sum(r[k+'_correct']==1 for k in ('title','artist','album'));denom=2+r['album_available']
        fields=[metric('Correct' if r[key+'_correct']==1 else 'Missed',label,'correct' if r[key+'_correct']==1 else 'missed')
            for key,label in [('title','Song'),('artist','Artist'),('album','Album')] if key!='album' or r['album_available']]
        event('recognition',r['id'],r['completed_at'],'Trivia',f'{right} / {denom} fields correct','/trivia_stats',
              [saved_song(r['song_id'])],[metric(f'{right} / {denom}','fields correct'),*fields])
    for r in conn.execute('SELECT * FROM elo_guess_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC LIMIT 10'):
        correct=(r['chosen_slot']==1)==(r['elo1']>r['elo2'])
        participants=[dict(saved_song(r[f'song{i}_id']),role='Your pick' if r['chosen_slot']==i else 'Other track',
            saved_elo=round(r[f'elo{i}']),higher=r[f'elo{i}']>r[f'elo{3-i}']) for i in (1,2)]
        event('guesser',r['id'],r['completed_at'],'Elo Guesser','Correct pick' if correct else 'Wrong pick','/elo_guesser_stats',
              participants,[metric('Correct pick' if correct else 'Wrong pick','result','correct' if correct else 'missed')],
              artwork=participants[r['chosen_slot']-1]['cover_url'])
    points_by_bracket=Counter();matches_by_bracket=Counter()
    for match in bracket_matches:
        matches_by_bracket[match['tournament_id']]+=1;points_by_bracket[match['tournament_id']]+=match['points_awarded'] or 0
    for t in finished[:10]:
        scope_kind=t['scope_type'];scope_rows={'artist':artists,'album':albums,'tag':tags}
        scope_row=scope_rows.get(scope_kind,{}).get(t['scope_id'])
        scope=dict(scope_row,entity_kind=scope_kind) if scope_row else None
        metrics=[metric(t['size'],'tracks'),metric(matches_by_bracket[t['id']],'matches'),
            metric(f"{points_by_bracket[t['id']]:.2f}",'points awarded')]
        if t.get('is_blind'):metrics.append(metric('Blind','bracket'))
        if scope_kind=='global':metrics.append(metric('Whole library','scope'))
        elif not scope:metrics.append(metric(scope_kind.capitalize(),'scope'))
        event('tournament',t['id'],t['completed_at'] or t['created_at'],'Tournament',f"{t['size']}-track bracket · champion",
              f"/tournament?tournament={t['id']}",[dict(saved_song(t['champion_id']),role='Champion')],metrics,scope=scope)
    shelf_times={r['id']:r['completed_at'] for r in conn.execute('SELECT id,completed_at FROM album_shelf_rounds WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC LIMIT 10')}
    shelf_membership=defaultdict(dict)
    for item in conn.execute('''SELECT round_id,album_slot,album_id FROM album_shelf_items
        WHERE round_id IN (SELECT id FROM album_shelf_rounds WHERE completed_at IS NOT NULL
            ORDER BY completed_at DESC,id DESC LIMIT 10) ORDER BY round_id,album_slot,item_slot'''):
        shelf_membership[item['round_id']].setdefault(item['album_slot'],item['album_id'])
    for r in recent_shelves:
        if r['id'] not in shelf_times:continue
        related=[dict(albums.get(aid,dict(id=None,title='Removed album',cover_url='')),
            entity_kind='album',role=f'Album {slot}') for slot,aid in shelf_membership[r['id']].items()]
        metrics=[metric(len(r['song_ids']),'tracks'),metric(len(related),'albums'),
            metric(f"{r['points']:.2f} / {r['available']:.2f}",'points'),
            metric(f"{r['accuracy']:.1f}%" if r['accuracy'] is not None else '—','points earned'),
            metric(f"{r['album_correct']} / {len(r['song_ids'])}",'correct album'),
            metric(f"{r['order_right']} / {r['order_pairs']}",'order comparisons')]
        if r['available']>0 and abs(r['points']-r['available'])<1e-8:metrics.append(metric('Perfect','round','correct'))
        event('shelves',r['id'],shelf_times[r['id']],'Album Shelves',f"{len(r['song_ids'])} tracks · {round(r['accuracy'],1) if r['accuracy'] is not None else 0}% points",
              '/album_shelves_stats',related,metrics)
    from songranker.modes.judgements import available, result, songs_for, MODES
    if available(conn):
        paths={'spotlight':'shared_spotlight','vibe':'vibe_map'}
        for r in conn.execute("SELECT * FROM judgement_rounds WHERE status='answered' ORDER BY closed_at DESC,id DESC LIMIT 10"):
            answer=result(conn,r); offered=songs_for(conn,r['id']); participants=[]
            for song in offered:
                participant=dict(saved_song(song['id']))
                if song['id'] is None:participant.update(title=song['title'])
                if r['mode']=='spotlight':participant['role']=str(answer['allocations'][song['slot']])+' points'
                participants.append(participant)
            detail=(str(sum(answer['allocations']))+' points awarded') if r['mode']=='spotlight' else str(len(answer['maps']))+' maps placed'
            event(r['mode'],r['id'],r['closed_at'],MODES[r['mode']].NAME,detail,
                '/'+paths[r['mode']]+'_stats#round-history',participants,[metric(detail,'result')])
    activity.sort(key=lambda e:(-e['timestamp'],e['kind'],-e['id']))
    from songranker.reports.judgement_stats_data import overview
    mode_updates={mode:overview(conn,mode) for mode in ('spotlight','vibe')}
    return attach_reports(conn, dict(elo_summary=elo_summary(conn),total_songs=len(songs),total_artists=len(artists),total_albums=len(proper),total_matches=len(history),
        mode_totals=[dict(label='Trivia rounds',value=trivia_total,kind='recognition'),dict(label='Tournaments',value=tournament['total'],kind='tournament'),
            dict(label='Elo Guesser rounds',value=guess['rounds'],kind='guesser'),dict(label='Shelves rounds',value=shelf['rounds'],kind='shelves')],
        collection_records=[r for r in records if r],voting=voting,voting_leaders=leaders,matchups=matchups,expand_matchups=expandable,
        elo_distribution=elo,average_elo=round(sum(s['elo_score'] for s in songs.values())/len(songs)) if songs else None,
        unplayed=sum(not votes[sid]['matches'] for sid in songs),audio_previews=sum(bool(str(s['audio_url'] or '').strip()) for s in songs.values()),
        week_votes=sum(timestamp(h['created_at'])>=datetime.now(timezone.utc).timestamp()-7*86400 for h in history),
        recognition=recognition,tournament=tournament,guess=guess,shelf=shelf,mode_updates=mode_updates,
        top_artists=sorted(artist_rows,key=lambda a:(-a['avg_elo'],-a['songs'],a['name'].casefold()))[:5],
        top_albums=sorted(album_rows,key=lambda a:(-a['avg_elo'],-a['songs'],a['title'].casefold()))[:5],
        top_tags=tag_rows[:10],tag_count=len(tags),recent_activity=activity[:10]), 'global')
