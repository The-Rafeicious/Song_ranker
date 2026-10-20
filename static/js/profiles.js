/* Shared entity-profile presentation; audio queues and game state stay in site.js. */
window.ProfileUI=(()=>{
 'use strict';
 const {$,$$,esc,ratio,sumFields}=window.SongRankerUI;
 let U,tagObserver;
 const count=(value,label)=>`<div><b>${esc(value)}</b><small>${esc(label)}</small></div>`;
 const joined=fields=>`<div class="mini-stats joined-metrics" data-columns="${fields.length}">${fields.map(([value,label])=>count(value,label)).join('')}</div>`;
 function rate(label,right,total){
   const shown=value=>Number(Number(value).toFixed(2));
   const pct=total?Math.max(0,Math.min(100,100*right/total)):0;
   return `<div class="profile-rate"><div class="profile-rate-caption"><span>${esc(label)}</span><strong>${ratio(right,total)}</strong></div><div class="overall-progress" ${total?`role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"`:'aria-hidden="true"'}><span style="width:${pct}%"></span></div><small>${total?`${shown(right)} / ${shown(total)}`:'No results yet'}</small></div>`;
 }
 function panel(tone,title,body,links=''){
   return `<section id="${tone==='standard'?'voting-record':tone==='recognition'||tone==='tournament'?tone:'profile-'+tone}" class="panel profile-mode-panel dashboard-surface ${tone}" data-profile-panel="${tone}" style="--section-color:var(--${tone});--surface-accent:var(--${tone})"><div class="section-head"><h2 class="${tone}">${title}</h2><div class="profile-stat-links">${links}</div></div>${body}</section>`;
 }
 const link=(tone,path,text)=>`<a class="${tone}" href="${path}">${text} ↗</a>`;
 function keyStats(fields){return `<div class="stats profile-key-stats" aria-label="Key statistics">${fields.map(([label,value,tone])=>U.stat(label,value,tone).replace('class="stat ', 'class="stat dashboard-surface ')).join('')}</div>`;}
 function queueInfo(queue,index=-1){
   const song=queue[index];
   return song?`<a class="song" title="${esc(song.title)}" href="${U.urlFor('songs',song)}">${esc(song.title)}</a><small class="profile-preview-position">${index+1} / ${queue.length}</small>`:'';
 }
 function tags(tracks,allTags){
   const counts=new Map();
   for(const song of new Map(tracks.map(song=>[song.id,song])).values())for(const id of new Set(song.tag_ids||[]))counts.set(id,(counts.get(id)||0)+1);
   return allTags.filter(tag=>counts.has(tag.id)).sort((a,b)=>counts.get(b.id)-counts.get(a.id)||a.name.localeCompare(b.name)||a.id-b.id).map(tag=>`<a class="badge tag" href="${U.urlFor('tags',tag)}" title="${esc(tag.name)} · ${counts.get(tag.id)} matching songs"><span class="profile-tag-name"># ${esc(tag.name)}</span><small>${counts.get(tag.id)}</small></a>`).join('');
 }
 function fitTagRows(container){
   const items=[...container.children];items.forEach(item=>item.hidden=false);
   if(!container.clientWidth)return;
   const positions=items.map(item=>item.offsetTop),rows=[...new Set(positions)].sort((a,b)=>a-b);
   items.forEach((item,index)=>item.hidden=rows.indexOf(positions[index])>=2);
 }
 function fitTags(){
   tagObserver?.disconnect();const containers=$$('.profile-tag-list');
   if(typeof ResizeObserver!=='undefined'){tagObserver??=new ResizeObserver(entries=>entries.forEach(entry=>fitTagRows(entry.target)));containers.forEach(container=>tagObserver.observe(container));}
   containers.forEach(fitTagRows);
 }
 window.addEventListener('resize',()=>{if(U)fitTags();});
 function stats(tracks,type='songs'){
   tracks=[...new Map(tracks.map(s=>[s.id,s])).values()];
   const sums=sumFields(tracks,['attempts','correct','championships','runner_ups','third_places','podiums','tournament_wins','tournament_losses','tournament_points','guess_attempts','guess_correct','shelf_attempts','shelf_album_correct','shelf_order_right','shelf_order_pairs','shelf_points','shelf_available']);
   const fields=tracks.reduce((n,s)=>n+U.available(s),0),votes=U.aggregateVotes(tracks),tested=tracks.filter(s=>U.available(s)>0).length;
   const ranking=(mode,tone)=>link(tone,`/mode_rankings/${mode}?entity=${type}`,'Rankings');
   const number=n=>Number(Number(n||0).toFixed(2));
   const paired=tracks.filter(s=>s.mode_ratings?.standard.matches>0&&s.mode_ratings?.blind.matches>0),cohort=type==='songs'?tracks:paired;
   const modeCards=['standard','blind'].map(mode=>{
     const prefix=mode+'_',rated=cohort.some(s=>s.mode_ratings?.[mode].matches>0);
     const elo=rated?cohort.reduce((n,s)=>n+Number(s.mode_ratings?.[mode].elo??1200),0)/cohort.length:null;
     return `<div class="profile-vote-mode profile-inset ${mode}" style="--section-color:var(--${mode})"><h3>${mode==='standard'?'Non-blind':'Blind'}</h3>${joined([[elo===null?'—':elo.toFixed(1),type==='songs'?'Mode Elo':'Shared-track Elo'],[votes.raw?.[prefix+'matches']??votes[prefix+'matches'],'Appearances']])}${rate('Win rate',votes[prefix+'wins'],votes[prefix+'matches'])}</div>`;
   }).join('');
   const outcomes=`<div class="mini-stats joined-metrics profile-vote-totals" data-columns="3">${count(number(votes.wins),'Win weight').replace('<div>','<div class="vote-win">')}${count(number(votes.losses),'Loss weight').replace('<div>','<div class="vote-loss">')}${count(votes.raw?.matches??votes.matches,type==='songs'?'Matches':'Track appearances')}</div>`;
   const voting=panel('standard','Voting Record',outcomes+rate('Weighted win rate',votes.wins,votes.matches)+`<div class="profile-detail-grid profile-vote-grid">${modeCards}</div>`,link('standard','/voting_stats','Stats')+link('standard','/history','History'));
   const fieldRows=[['title','Song'],['artist','Artist'],['album','Album']].map(([key,label])=>{
     const offered=tracks.reduce((n,s)=>n+Number(key==='album'?s.album_attempts||0:s.new_attempts??s.attempts??0),0);
     const correct=tracks.reduce((n,s)=>n+Number(s[key+'_correct']||0),0);
     return `<div class="profile-inset">${rate(label+' fields',correct,offered)}</div>`;
   }).join('');
   const recognition=panel('recognition','Recognisability',joined([[sums.attempts,'Rounds'],[tested,'Tested tracks'],[sums.correct,'Fields correct']])+rate('Fields correct',sums.correct,fields)+`<div class="profile-detail-grid profile-field-grid">${fieldRows}</div>`,ranking('trivia','recognition')+link('recognition','/trivia_stats','Stats'));
   const ids=new Set(tracks.map(s=>s.id)),db=U.data(),brackets=new Set((db.tournaments||[]).map(t=>t.id));
   const entries=(db.tournament_entries||[]).filter(e=>ids.has(e.song_id));
   const matches=(db.tournament_matches||[]).filter(m=>ids.has(m.song1_id)||ids.has(m.song2_id));
   const countBrackets=new Set([...entries.map(e=>e.tournament_id),...matches.map(m=>m.tournament_id)].filter(id=>brackets.has(id))).size;
   const tournament=panel('tournament','Tournament Record',joined([[sums.tournament_points.toFixed(2),'Points'],[countBrackets,'Brackets'],[sums.podiums,'Podiums']])+rate('Match wins',sums.tournament_wins,sums.tournament_wins+sums.tournament_losses)+`<div class="profile-secondary-metrics">${joined([[sums.championships,'First'],[sums.runner_ups,'Second'],[sums.third_places,'Third']])}</div>`,ranking('tournament','tournament')+link('tournament','/tournament_stats','Stats'));
   const guesser=panel('guesser','Elo Guesser',joined([[sums.guess_correct,'Correct'],[sums.guess_attempts-sums.guess_correct,'Wrong'],[sums.guess_attempts,'Track appearances']])+rate('Correct picks',sums.guess_correct,sums.guess_attempts),ranking('guesser','guesser')+link('guesser','/elo_guesser_stats','Stats'));
   const shelves=panel('shelves','Album Shelves',joined([[sums.shelf_attempts,'Track appearances'],[sums.shelf_album_correct,'Correct placements'],[sums.shelf_points.toFixed(2),'Points']])+rate('Relative track order',sums.shelf_order_right,sums.shelf_order_pairs)+`<div class="profile-detail-grid profile-field-grid"><div class="profile-inset">${rate('Album placement',sums.shelf_album_correct,sums.shelf_attempts)}</div><div class="profile-inset">${rate('Points earned',sums.shelf_points,sums.shelf_available)}</div></div>`,ranking('shelves','shelves')+link('shelves','/album_shelves_stats','Stats'));
   return voting+recognition+tournament+guesser+shelves;
 }
 return {bindUI:ui=>U=ui,keyStats,queueInfo,tags,fitTags,fitTagRows,stats};
})();

