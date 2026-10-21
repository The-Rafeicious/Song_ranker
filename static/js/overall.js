/* Shared Overall cards. Calculation and calibration remain on the server. */
window.Overall=(()=>{
 'use strict';let U,current,ranking={type:'songs',bottom:false},devType='songs',requestId=0,loadId=0,inspectId=0;
 const {$,$$,esc}=window.SongRankerUI;
 const rounded=v=>(Math.round((Number(v)+Number.EPSILON)*100)/100).toFixed(2),pct=v=>v==null?'—':rounded(v)+'%';
 const types=window.SongRankerUI.entityTypes,labels=window.SongRankerUI.entityLabels;
 async function load(){const id=++loadId,data=await U.api('/api/overall');if(id===loadId)current=data;return data;}
 function bar(value,label){const width=value==null?0:Math.max(0,Math.min(100,value));return `<div class="overall-progress" ${value==null?'aria-hidden="true"':`role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${width}"`}><span style="width:${width}%"></span></div>`;}
 function breakdown(row,type,compact=false){
   const collection=type!=='songs',known=row.score!=null;
   const tones={elo:'standard',standard:'standard',blind:'blind',trivia:'recognition',tournament:'tournament',guesser:'guesser',shelves:'shelves',neutral:'overall'};
   const modes=(row.contributions||[]).map(c=>({...c,adjusted:c.display_score??c.score,allocated:c.display_weight??c.weight,contribution:c.display_points??c.points,relative:c.display_evidence??c.evidence}));
   if(row.neutral_balance)modes.push({...row.neutral_balance,key:'neutral',label:'Neutral share',adjusted:row.neutral_balance.score,allocated:row.neutral_balance.weight,contribution:row.neutral_balance.points,relative:null});
   const pointText=value=>value==null?'—':rounded(value)+' pts';
   return `<details class="overall-breakdown"><summary>Mode balance</summary>${compact?'':`<p class="overall-balance-copy">Adjusted score × effective weight ÷ 100 gives the contribution in Overall points. Unrounded contributions add to Overall.${collection?' Weights include collection confidence; the remaining share stays at a neutral 50%.':''}</p><p class="overall-balance-copy">Relative evidence compares plays with current typical and high exposure; it is separate from performance.${known?'':' No Overall score is assigned until there are measured, eligible results.'}</p>`}<div class="overall-mode-grid">${modes.map(c=>`<div data-overall-mode="${esc(c.key)}" style="--section-color:var(--${tones[c.key]||'overall'})"><h3 class="overall-mode-title">${esc(c.label)}</h3>${compact?'':`<p class="overall-mode-context">${c.key==='neutral'?'Keeps sparse collections near neutral':collection?`${c.applicable_tracks||0} / ${row.track_count||0} tracks eligible`:c.relative===0?'Unplayed · neutral input':'Evidence-adjusted input'}</p>`}<dl class="overall-mode-facts">${[[pct(c.adjusted),'Adjusted score'],[pct(c.allocated),'Effective weight'],[pointText(known?c.contribution:null),'Contribution'],[pct(c.relative),'Relative evidence']].map(([value,label])=>`<div><dt>${label}</dt><dd>${value}</dd></div>`).join('')}</dl>${bar(c.adjusted,c.label+' adjusted score')}</div>`).join('')||'<div class="empty">No tested modes</div>'}</div></details>`;
 }
 function card(row,type='songs',title='Overall',id=''){
   const name=row?.name||'',noData=row?.score==null;
   return `<section ${id?`id="${id}"`:''} class="panel overall-panel overall-card dashboard-surface"><div class="section-head"><h2 class="overall">${esc(title)}</h2><a class="overall" href="/overall_rankings?entity=${type}">Rankings ↗</a></div><div class="overall-card-body"><span class="overall-meta">${noData?(row?.eligible===false?'Unranked album':'Not tested'):type==='songs'?pct(row.evidence)+' relative evidence':pct(row.group_confidence||0)+' collection confidence'}${row?.rank!=null?`<span class="overall-standing">Rank ${row.rank} / ${row.rank_population}</span>`:''}</span><strong class="overall-value">${pct(row?.score)}</strong><span class="overall-meta overall-meta-right">${row?.mode_count||0} modes${type==='songs'?'':` · ${row?.tested_tracks||0} / ${row?.track_count||0} tracks tested`}</span></div>${bar(row?.score,name+' Overall score')}${row?breakdown(row,type,id==='overall-profile'):''}</section>`;
 }
 function highlights(data,title='Overall Leaders',id='overall-highlights',showLink=true){
   return `<section class="panel overall-panel" id="${id}"><div class="section-head"><h2 class="overall">${title}</h2>${showLink?'<a class="overall" href="/overall_rankings">Rankings ↗</a>':''}</div><div class="overall-highlights">${types.map(type=>{const row=data.highlights[type];return row?`<a class="overall-highlight" href="${U.urlFor(type,row)}"><span class="overall-highlight-art">${U.artwork(row,type)}</span><strong class="${U.colour(type)}" title="${esc(row.name)}">${esc(row.name)}</strong><b class="overall">${pct(row.score)}</b>${bar(row.score,row.name+' Overall score')}</a>`:`<div class="overall-highlight empty"><span>${labels[type]}</span><small>Not tested</small></div>`;}).join('')}</div></section>`;
 }
 async function mount(page){
   const profile=['song','artist','album','tag'].includes(page),root=profile?($('#profile-vibe')||$('.profile-key-stats')):page==='home'?$('.home-record-stats'):$('#overall-global');
   if(!root)return;let placeholder;
   if(profile){$('#overall-profile')?.remove();$('[data-overall-loading]')?.remove();}else if(page==='home'){$('#overall-highlights')?.remove();$('[data-overall-loading]')?.remove();}
   if(page==='global_stats')placeholder=root;
   else{placeholder=document.createElement('section');placeholder.className='panel overall-panel';placeholder.dataset.overallLoading='true';placeholder.innerHTML='<h2 class="overall">Overall</h2><div class="empty" role="status">Calculating…</div>';if(profile)root.after(placeholder);else root.before(placeholder);}
   try{
     const data=await load();if(!placeholder.isConnected)return;
     if(page==='home'){placeholder.outerHTML=highlights(data);window.VibeLibrary?.placeHome();return;}
     if(page==='global_stats'){
       placeholder.outerHTML=`<section class="panel overall-panel" id="overall-global" data-global-section="overall"><div class="section-head"><h2 class="overall">Overall Stats</h2><a class="overall" href="/overall_rankings">Overall rankings ↗</a></div><div class="overall-global-summary joined-metrics"><div><b>${data.summary.tested_songs} / ${data.summary.songs}</b><small>Tested songs</small></div><div><b>${pct(data.summary.evidence)}</b><small>Library relative evidence</small></div><div><b>${data.summary.active_modes}</b><small>Active modes</small></div></div>${highlights(data,'Overall Leaders','overall-global-leaders',false)}</section>`;return;
     }
     let type,id;
     if(page==='song'){type='songs';id=Number(document.body.dataset.entity)||Number(new URLSearchParams(location.search).get('id'))||U.records('songs')[0]?.id;}
     else{const info=U.profile();type=info.type;id=info.item.id;}
     const row=data.entities[type]?.find(r=>r.id===id);placeholder.outerHTML=card(row,type,'Overall','overall-profile');
   }catch(error){placeholder.innerHTML=`<h2 class="overall">Overall</h2><div class="empty error">${esc(error.message)}</div><button class="btn" data-overall-retry="${page}">Retry</button>`;}
 }
 async function renderRankings(init=false){
   const id=++requestId;U.pageTone('overall');document.body.classList.add('rankings-page','standard-rankings-page','mode-rankings-page');document.body.style.setProperty('--rank-color','var(--overall)');
   if(init){const params=new URLSearchParams(location.search);ranking={type:types.includes(params.get('entity'))?params.get('entity'):'songs',bottom:params.get('view')==='bottom'};}
   U.main.innerHTML='<div class="page-head"><h1 class="overall">Overall Rankings</h1></div><div class="empty" role="status">Calculating…</div>';
   try{await load();if(id===requestId)drawRankings();}catch(error){if(id===requestId)U.main.innerHTML=`<div class="empty error">${esc(error.message)}</div><button class="btn" data-overall-retry="rankings">Retry</button>`;}
 }
 function drawRankings(){
   const type=ranking.type,all=current.entities[type].filter(r=>r.score!=null&&r.eligible!==false),rows=(ranking.bottom?[...all].reverse():all).slice(0,20);
   const facts=row=>[type==='songs'?pct(row.evidence)+' relative evidence':pct(row.group_confidence||0)+' collection confidence',`${row.mode_count} modes`,...(type==='songs'?[]:[`${row.tested_tracks} / ${row.track_count} tracks tested`])];
   U.main.innerHTML=`<div class="page-head"><h1 class="overall">Overall Rankings</h1></div><p class="overall-score-note">Overall combines mode results on a 0–100 scale. Rank shows category standing.</p>${window.SongRankerUI.modeRankingControls('/overall_rankings',type,ranking.bottom,'overall',types)}<div class="leaderboard overall-leaderboard">${rows.map((row,i)=>window.SongRankerUI.modeRankingRow(U,row,type,i,all.length,ranking.bottom,'overall',pct(row.score),'Overall',facts(row),row.rank)).join('')||'<div class="empty">No tested records yet</div>'}</div>`;

   history.replaceState({},'',`/overall_rankings?entity=${type}&view=${ranking.bottom?'bottom':'top'}`);
 }
 async function renderDev(){
   const root=$('#dev-main');if(!root)return;const id=++requestId;++inspectId;
   root.innerHTML='<div class="page-head"><h2 class="overall">Overall Calculator</h2></div><div class="empty" role="status">Calculating…</div>';
   try{
     const data=await load();if(id!==requestId||!root.isConnected||!$('[data-dev="overall"].active'))return;
     const m=data.calibration;
     root.innerHTML=`<div class="page-head"><h2 class="overall">Overall Calculator</h2><button class="btn" data-overall-recalibrate>Refresh ratios</button></div>
       <p class="overall-dev-intro">Overall shows the existing evidence-adjusted composite as a percentage. Rank gives category standing separately. The lookup traces saved inputs, allocated weights and contributions to that score. A 90% score means a 90-point composite; its rank depends on the other records.</p>
       <section class="panel overall-panel"><div class="section-head"><h3 class="overall">Current balance</h3><small>Calibrated ${new Date(m.generated_at*1000).toLocaleString()}</small></div>
         <p class="overall-dev-copy">Five game families start equally: voting, recognisability, tournament, Elo Guesser and Album Shelves. Elo, non-blind and blind voting share one family, with base shares of 8%, 6% and 6%. Allocated weights adjust to eligible-song participation and average plays. With ${m.families.filter(f=>f.active).length} active families, each family is capped at ${pct(m.family_cap)}; with all five active, voting's three views together cannot exceed 30%.</p>
         <p class="overall-dev-copy">Participation is tested songs ÷ eligible songs. Depth is average plays ÷ (average plays + ${rounded(m.depth_reference)}), using the geometric mean of active families' average plays as the current reference. Support = square root of participation × depth. Family shares follow support subject to the cap; voting then divides its share between its three views using their base shares and support. When a song cannot enter a family, its remaining shares are rescaled with the same cap rule: 100 ÷ playable family count + 10 percentage points, capped at 100%.</p>
         <div class="data-scroll"><table class="overall-table"><thead><tr><th>Mode</th><th>Family</th><th>Base</th><th>Tested / eligible</th><th>Participation</th><th>Avg plays</th><th>Depth</th><th>Support</th><th>Allocated</th></tr></thead><tbody>${m.modes.map(mode=>`<tr><td>${esc(mode.label)}</td><td>${esc(mode.family==='voting'?'Voting':mode.label)}</td><td>${pct(mode.base_weight)}</td><td>${mode.tested_songs} / ${mode.eligible_songs}</td><td>${pct(100*mode.participation)}</td><td>${rounded(mode.average_appearances)}</td><td>${pct(100*mode.depth_factor)}</td><td>${pct(100*mode.support)}</td><td class="overall">${pct(mode.weight)}</td></tr>`).join('')}</tbody></table></div>
       </section>
       <section class="panel overall-panel"><h3 class="overall">Metric ratios & averages</h3>
         <p class="overall-dev-copy">These baselines and exposure references are rebuilt from each fresh snapshot. Unavailable metrics release their share to the available metrics in that mode. Ineligible modes are omitted for that song and its remaining mode shares are rescaled; an eligible but unplayed mode stays neutral with zero evidence.</p>
         <dl class="overall-dev-definitions">
           <div><dt>Overall weight</dt><dd>The metric's global share of the composite score. The lookup shows the actual per-song allocation after unavailable fields or modes are omitted.</dd></div>
           <div><dt>Population average</dt><dd>Rates pool effective appearances across tested songs. Elo uses one current or peak value per tested song. This baseline calibrates performance before the weighted composite.</dd></div>
           <div><dt>Relative evidence</dt><dd>Zero plays gives 0%; the tested-song average gives 50%; the high reference gives 100%. The high reference is the 90th percentile of plays, or twice the average when that percentile is not above the average. Counts below or above the average interpolate linearly and stop at 100%.</dd></div>
           <div><dt>Appearances / eligible songs</dt><dd>Matches, field attempts, completed tournament entries and offered Shelves tracks supply different evidence units. Each game counts its own appearances once. Album-only inputs exclude ineligible tracks; blind voting and trivia require an audio preview. Repeated plays increase evidence and the game's participation depth.</dd></div>
         </dl>
         <div class="data-scroll"><table class="overall-table"><thead><tr><th>Metric</th><th>Overall weight</th><th>Population average</th><th>Avg plays (50%)</th><th>High reference (100%)</th><th>Most plays</th><th>Appearances</th><th>Tested / eligible</th></tr></thead><tbody>${Object.values(m.metrics).map(metric=>`<tr><td>${esc(m.modes.find(mode=>mode.key===metric.mode)?.label)} · ${esc(metric.label)}</td><td class="overall">${pct(metric.overall_weight)}</td><td>${metric.mean==null?'—':metric.kind==='elo'?rounded(metric.mean):pct(100*metric.mean)}</td><td>${rounded(metric.average_appearances)}</td><td>${rounded(metric.high_appearances)}</td><td>${rounded(metric.max_appearances)}</td><td>${rounded(metric.appearances)}</td><td>${metric.tested_songs} / ${metric.eligible_songs}</td></tr>`).join('')}</tbody></table></div>
       </section>
       <section class="panel overall-panel"><h3 class="overall" id="overall-dev-lookup-title">Inspect ${devType==='artists'||devType==='albums'?'an':'a'} ${labels[devType].toLowerCase()}</h3>
         <div class="pill-nav overall-tabs overall-dev-types" role="group" aria-label="Overall lookup category">${types.map(type=>`<button class="pill ${U.colour(type)} ${type===devType?'active':''}" data-overall-dev-type="${type}" aria-pressed="${type===devType}">${labels[type]}s</button>`).join('')}</div>
         <input id="overall-dev-query" type="search" placeholder="Find ${labels[devType].toLowerCase()}…" aria-label="Find ${labels[devType].toLowerCase()} for Overall breakdown"><div id="overall-dev-results"></div><div id="overall-dev-detail" aria-live="polite"></div>
       </section>
       <details class="panel overall-panel overall-method"><summary>How the score is balanced</summary>
         <p><b>1. Adapt the game balance.</b> The five families each have a 20% base. Breadth measures the fraction of eligible songs played, and depth compares that game's average appearances to current typical use across families. Support combines breadth and depth. Sparse games receive less weight and gain influence as they are used. The family cap prevents one heavily played game from taking over; Elo and both voting rates remain one family rather than three independent games.</p>
         <p><b>2. Normalise performance and relative evidence.</b> Rates blend 60% actual success with 40% performance against the population average; Elo uses its tested-song distribution. Evidence compares a song's appearances to that metric's current average and high reference. Average exposure gives 50% evidence. At half the average it gives 25%; at the high reference it reaches 100%. The same relative exposure produces the same evidence whether typical counts are 1–2 or 10–20. If the rest of the library gets more plays, a song left behind loses evidence. A calibrated input is 50 + (normalised percentage − 50) × evidence fraction, so lightly tested results move towards neutral.</p>
         <p><b>3. Form the song's composite.</b> Add allocated weight × calibrated percentage ÷ 100 across eligible metrics. The composite is a weighted average; there is no extra coverage multiplier pushing the whole library below 50. Evidence is averaged with the same allocations. Missing results in a playable mode stay neutral; modes the song cannot enter are omitted and the family cap is reapplied across its playable families. No album means no album-recognition field or Shelves input. Shelves additionally needs a positive unique track position in a proper album with at least two eligible tracks.</p>
         <p><b>4. Display the composite directly.</b> Overall equals the evidence-adjusted composite on its existing 0–100 scale. No minimum, maximum or percentile stretch is applied. A lone 63% composite stays 63%; equal composites keep equal scores and rank. Rank is one plus the number of higher composites in that category. An unknown score stays unknown. Values display to two decimals; standings use full precision. Close scores can look tied after rounding.</p>
         <p><b>5. Combine artists, albums and tags.</b> Average distinct linked songs' composites equally, substituting a neutral 50 for untested songs. Effective songs is the sum of their relative evidence fractions. Collection confidence = effective songs ÷ (effective songs + 2). Overall = 50 + (song mean − 50) × confidence. Singles and unknown albums stay outside rankings. Empty or entirely untested collections remain unknown.</p>
         <p><b>Reading Mode balance.</b> A song's adjusted mode score includes its relative evidence. Effective weight × adjusted score ÷ 100 gives its contribution in Overall points. For collections, mode inputs are averaged using each song's actual allocation; collection confidence reduces their effective weights, and the remaining weight uses a neutral 50. This makes all unrounded contributions, including the neutral share, add to the final composite. Relative evidence is separate from performance and is not a statistical confidence interval.</p>
         <p><b>Reading the lookup.</b> Raw is the saved rate or Elo value. Allocated is the per-song weight. Adjusted is the normalised, evidence-adjusted input; metric contributions sum to the song composite. Linked songs show their actual Overall and the value counted in the collection mean, including neutral priors for untested songs. The original family, metric, evidence and collection calculations are unchanged.</p>
         <p><b>Freshness.</b> Every Overall request reads a consistent current snapshot and recalculates participation, exposure references, averages, weights, composites and ranks. An unchanged calibration is reused in memory; there is no 30-minute or 25-appearance delay. Refresh ratios forces it to rebuild. The session stores only a compact version marker, and no score fields or migrations are written to the database.</p>
         <p><b>What is counted.</b> Win/loss counts supply rates and exposure. Tournament podium and points use completed entries, while match win rates can count during a bracket. Shelves order uses offered-track appearances for evidence. Derived totals, artwork, dates, tag descriptions and global user streaks do not add extra achievement weight.</p>
       </details>`;
     devResults('');
   }catch(error){if(root.isConnected&&id===requestId)root.innerHTML=`<div class="empty error">${esc(error.message)}</div>`;}
 }
 function devResults(query){
   const root=$('#overall-dev-results');if(!root||!current)return;const q=query.trim().toLocaleLowerCase();
   const found=current.entities[devType].filter(r=>(r.name+' #'+r.id).toLocaleLowerCase().includes(q));root.innerHTML=found.slice(0,12).map(row=>`<button class="btn small" data-overall-inspect="${row.id}" data-overall-inspect-type="${devType}"><span class="${U.colour(devType)}" title="${esc(row.name)}">${esc(row.name)}</span><b class="overall">${pct(row.score)}</b></button>`).join('')||`<div class="empty">No ${devType}</div>`;if(found.length>12)root.insertAdjacentHTML('beforeend','<p class="overall-dev-copy">Showing 12 of '+found.length+'. Search by name or #ID to narrow the list.</p>');
 }
 function selectDevType(type){
   if(!types.includes(type))return;devType=type;++inspectId;
   $$('[data-overall-dev-type]').forEach(b=>{b.classList.toggle('active',b.dataset.overallDevType===type);b.setAttribute('aria-pressed',String(b.dataset.overallDevType===type));});
   const query=$('#overall-dev-query');if(!query)return;query.value='';query.placeholder=`Find ${labels[type].toLowerCase()}…`;query.setAttribute('aria-label',`Find ${labels[type].toLowerCase()} for Overall breakdown`);
   $('#overall-dev-lookup-title').textContent=`Inspect ${type==='artists'||type==='albums'?'an':'a'} ${labels[type].toLowerCase()}`;
   $('#overall-dev-detail').innerHTML='';devResults('');
 }
 function songDetail(entity){
   return `<p class="overall-dev-copy">Each row shows a saved input, its effective appearances and the adjusted percentage used in the weighted score. Unplayed eligible inputs stay neutral at 50%, with zero evidence. Ineligible fields and modes are omitted.</p>
     <div class="data-scroll"><table class="overall-table"><thead><tr><th>Mode</th><th>Metric</th><th>Raw</th><th>Appearances</th><th>Allocated</th><th>Adjusted score</th><th>Relative evidence</th><th>Contribution (pts)</th></tr></thead><tbody>${entity.contributions.flatMap(c=>(c.metrics||[]).map(m=>`<tr><td>${esc(c.label)}</td><td>${esc(m.label)}</td><td>${m.raw==null?'—':m.key.startsWith('elo_')?rounded(m.raw):pct(100*m.raw)}</td><td>${rounded(m.appearances)}</td><td>${pct(m.weight)}</td><td>${pct(m.adjusted)}</td><td>${pct(m.evidence)}</td><td class="overall">${rounded(m.weight*m.adjusted/100)}</td></tr>`)).join('')||'<tr><td colspan="8">No active metrics</td></tr>'}</tbody></table></div>
     ${entity.composite_score==null?'<p class="overall-dev-copy">No measured evidence yet, so this song has no Overall score.</p>':`<div class="overall-dev-formula">Σ metric contributions = <b class="overall">${pct(entity.score)} Overall</b></div><p class="overall-dev-copy">Rank ${entity.rank} / ${entity.rank_population} measured songs. Relative evidence: ${pct(entity.evidence)}. The displayed score equals the existing composite; ranking retains full precision.</p>`}`;
 }
 function collectionDetail(entity,type){
   const tracks=entity.linked_songs||[];
   return `${entity.eligible===false?'<p class="overall-dev-copy">This album is excluded from rankings and leaders because it is a single or an unknown album.</p>':''}
     <p class="overall-dev-copy">${entity.tested_tracks} of ${entity.track_count} distinct linked songs have measured results. Each song contributes equally to the mean; an untested song contributes the ${pct(entity.prior_score)} prior. Mode balance weights each song’s adjusted inputs by its actual allocation, then applies collection confidence and the neutral share.</p>
     <dl class="overall-dev-definitions"><div><dt>Composite mean, including priors</dt><dd class="overall">${pct(entity.mean_score)}</dd></div><div><dt>Effective songs</dt><dd class="overall">${rounded(entity.effective_songs)} = sum of song evidence fractions</dd></div><div><dt>Collection confidence</dt><dd class="overall">${pct(entity.group_confidence||0)} = effective songs ÷ (effective songs + ${entity.group_prior_songs})</dd></div><div><dt>Average song evidence</dt><dd class="overall">${pct(entity.evidence)} across all linked songs</dd></div></dl>
     ${entity.composite_score==null?'<p class="overall-dev-copy">No measured evidence yet, so this collection has no Overall score.</p>':`<div class="overall-dev-formula">${pct(entity.prior_score)} + (${pct(entity.mean_score)} − ${pct(entity.prior_score)}) × ${pct(entity.group_confidence)} confidence = <b class="overall">${pct(entity.composite_score)} ${entity.eligible===false?'unranked composite':'Overall'}</b></div><p class="overall-dev-copy">${entity.rank==null?'Outside the ranked population.':`Rank ${entity.rank} / ${entity.rank_population} tested, eligible ${type}.`} Confidence is applied as a fraction. All calculations retain full precision.</p>`}
     <h3 class="overall">Linked songs</h3><p class="overall-dev-copy">Select a song to inspect its individual metrics. Counted composite is the value included in this ${labels[type].toLowerCase()}’s mean.</p>
     <div class="data-scroll"><table class="overall-table"><thead><tr><th>Song / ID</th><th>Song Overall</th><th>Counted composite</th><th>Evidence</th><th>Tested modes</th></tr></thead><tbody>${tracks.map(song=>`<tr><td><button class="overall-linked-song song" data-overall-inspect="${song.id}" data-overall-inspect-type="songs">${esc(song.name)}</button><small class="overall-record-id">#${song.id}</small></td><td class="overall">${pct(song.score)}</td><td>${pct(song.counted_score)}${song.score==null?' (prior)':''}</td><td>${pct(song.evidence)}</td><td>${song.mode_count}</td></tr>`).join('')||'<tr><td colspan="5">No linked songs</td></tr>'}</tbody></table></div>`;
 }
 async function inspect(type,id){
   if(!types.includes(type))return;if(type!==devType)selectDevType(type);
   const root=$('#overall-dev-detail');if(!root)return;const generation=++inspectId;root.innerHTML='<div class="empty" role="status">Calculating…</div>';
   try{const {entity}=await U.api(`/api/overall/details?type=${type}&id=${id}`);if(!root.isConnected||generation!==inspectId)return;
     root.innerHTML=card(entity,type,entity.name)+`<p class="overall-dev-copy">${labels[type]} ID: ${entity.id}</p>`+(type==='songs'?songDetail(entity):collectionDetail(entity,type));
   }catch(error){if(root.isConnected&&generation===inspectId)root.textContent=error.message;}
 }
 document.addEventListener('click',async e=>{
   const b=e.target.closest('button');if(!U||!b||b.disabled)return;
   if(b.dataset.overallEntity){ranking.type=b.dataset.overallEntity;drawRankings();}
   if(b.dataset.overallView){ranking.bottom=b.dataset.overallView==='bottom';drawRankings();}
   if(b.dataset.overallRetry){if(b.dataset.overallRetry!=='global_stats')b.closest('.overall-panel')?.remove();if(b.dataset.overallRetry==='rankings')await renderRankings();else await mount(b.dataset.overallRetry);}
   if(b.dataset.overallDevType)selectDevType(b.dataset.overallDevType);
   if(b.dataset.overallInspect)await inspect(b.dataset.overallInspectType||'songs',Number(b.dataset.overallInspect));
   if(b.hasAttribute('data-overall-recalibrate')){b.disabled=true;try{await U.api('/api/dev/overall/recalibrate',{});if($('[data-dev="overall"].active'))await renderDev();}catch(error){U.toast(error.message);b.disabled=false;}}
 });
 window.addEventListener('pageshow',e=>{if(!e.persisted||!U)return;const page=document.body.dataset.page;if(['home','song','artist','album','tag','global_stats'].includes(page))mount(page);if(page==='overall_rankings')renderRankings();if(page==='dev'&&$('[data-dev="overall"].active'))renderDev();});
 document.addEventListener('input',e=>{if(e.target.id==='overall-dev-query')devResults(e.target.value);});
 return {bindUI:ui=>U=ui,mount,renderRankings,renderDev};
})();


