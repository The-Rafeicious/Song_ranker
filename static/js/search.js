/* Catalogue search presentation. The header search and catalogue matching stay
   in site.js; this module only owns the main Search page. */
window.SearchPage=(()=>{
 'use strict';
 const {$,$$,esc,ratio,sumFields,entityTypes,entityLabels,entityColour}=window.SongRankerUI;
 let U,type='songs',query='',tag=null,limit=40,sort='random',observer,randomOrders=new Map();
 const keys=['championships','runner_ups','third_places','correct','available_points','guess_correct','guess_attempts','shelf_order_right','shelf_order_pairs'];
 function achievementCandidates(tracks){
   const sums=sumFields(tracks,keys),out=[];
   const add=(mode,text,priority,detail)=>out.push({mode,text,priority,detail});
   if(sums.championships)add('tournament',`🏆 ${sums.championships} ${sums.championships===1?'title':'titles'}`,100,'Completed tournament championships');
   else if(sums.runner_ups)add('tournament',`🥈 ${sums.runner_ups} ${sums.runner_ups===1?'runner-up':'runners-up'}`,85,'Completed tournament second places');
   else if(sums.third_places)add('tournament',`🥉 ${sums.third_places} third`,84,'Completed tournament third places');
   const rate=(mode,right,total,min,threshold,label)=>{
     if(total>=min&&right/total>=threshold)add(mode,`${label} ${ratio(right,total)}`,right===total?95:80,`${right} / ${total} ${mode==='recognition'?'eligible fields correct':mode==='guesser'?'correct track appearances':'relative-order comparisons correct'}`);
   };
   rate('recognition',sums.correct,sums.available_points,2,.9,'Trivia');
   rate('guesser',sums.guess_correct,sums.guess_attempts,2,.9,'Guesser');
   rate('shelves',sums.shelf_order_right,sums.shelf_order_pairs,6,.9,'Track order');
   for(const [prefix,mode,label] of [['standard_','standard','Vote wins'],['blind_','blind','Blind wins']]){
     const wins=tracks.reduce((n,s)=>n+Number(s.voting?.[prefix+'wins']||0),0),losses=tracks.reduce((n,s)=>n+Number(s.voting?.[prefix+'losses']||0),0),total=wins+losses;
     if(total>=5&&wins/total>=.9)add(mode,`${label} ${ratio(wins,total)}`,70,`${wins} wins from ${total} saved track appearances`);
   }
   return out.sort((a,b)=>b.priority-a.priority);
 }
 function badges(tracks){
   const candidates=achievementCandidates(tracks);
   return candidates.length?`<div class="search-achievements" aria-label="Top achievements">${candidates.map(b=>`<span class="achievement ${b.mode}" title="${esc(b.detail)}">${esc(b.text)}</span>`).join('')}</div>`:'';
 }
 function fitBadgeRow(row){
   // Keep whole badges, highest priority first; never crop text or add a second row.
   const items=[...row.children];items.forEach(item=>item.hidden=false);
   if(!row.clientWidth)return;
   let used=0,visible=0,full=false;const gap=parseFloat(getComputedStyle(row).columnGap)||0;
   for(const item of items){const width=item.getBoundingClientRect().width;
     const fits=!full&&visible<3&&used+(visible?gap:0)+width<=row.clientWidth;
     item.hidden=!fits;if(fits){used+=(visible?gap:0)+width;visible++;}else full=true;
   }
 }
 function fitBadges(){
   observer?.disconnect();
   const rows=$$('.search-page .search-achievements');
   if(typeof ResizeObserver!=='undefined'){observer??=new ResizeObserver(entries=>entries.forEach(entry=>fitBadgeRow(entry.target)));rows.forEach(row=>observer.observe(row));}
   rows.forEach(fitBadgeRow);
 }
 function card(r){
   const tracks=U.linkedSongs(type,r),kind=entityColour(type),info=type==='songs'||type==='albums'?U.rankingMetadata(type==='songs'&&!U.properAlbum(U.records('albums').find(a=>a.id===r.album_id))?{...r,album:''}:r,type):{html:`${tracks.length} songs`,text:`${tracks.length} songs`};
   return `<article class="result-card ${kind} dashboard-surface"><div class="search-art">${U.artwork(r,type)}</div><div class="result-info"><span class="badge ${kind}">${entityLabels[type]}</span><h2><a class="${kind}" href="${U.urlFor(type,r)}" title="${esc(r.name)}">${type==='tags'?'# ':''}${esc(r.name)}</a></h2><div class="search-metadata" title="${esc(info.text)}">${info.html}</div>${type==='tags'&&r.description?`<p class="search-description" title="${esc(r.description)}">${esc(r.description)}</p>`:''}</div><div class="result-score ${type==='songs'?'standard':kind}">${type==='songs'?Math.round(r.score):window.SongRankerUI.impactText(r.score)}<small>${type==='songs'?'Elo':'Impact'}</small></div>${badges(tracks)}</article>`;
 }
 function randomOrder(category){
   if(!randomOrders.has(category)){
     const ids=U.records(category).map(row=>row.id);
     for(let i=ids.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[ids[i],ids[j]]=[ids[j],ids[i]];}
     randomOrders.set(category,new Map(ids.map((id,index)=>[id,index])));
   }
   return randomOrders.get(category);
 }
 function updateQuery(value){
   if(value!==query){query=value;sort=query.trim()?'score':'random';}
   limit=40;render();
 }
 const sortOptions=[['score','Highest rating'],['name','Name A–Z'],['random','Random']];
 function closeSort(restoreFocus=false){
   $('#search-sort-menu').hidden=true;$('#search-sort').setAttribute('aria-expanded','false');
   $('#search-sort-control').classList.remove('opens-up');
   if(restoreFocus)$('#search-sort').focus();
 }
 function syncSort(){
   $('#search-sort-value').textContent=sortOptions.find(([value])=>value===sort)[1];
   $$('#search-sort-menu [role="option"]').forEach(option=>option.setAttribute('aria-selected',String(option.dataset.searchSort===sort)));
   closeSort();
 }
 function openSort(){
   const menu=$('#search-sort-menu'),control=$('#search-sort-control');
   menu.hidden=false;$('#search-sort').setAttribute('aria-expanded','true');control.classList.remove('opens-up');
   const trigger=$('#search-sort').getBoundingClientRect(),height=menu.getBoundingClientRect().height;
   control.classList.toggle('opens-up',trigger.bottom+height+10>window.innerHeight&&trigger.top>height+10);
   $$('#search-sort-menu [role="option"]').find(option=>option.dataset.searchSort===sort)?.focus();
 }
 function chooseSort(value){
   if(sort!==value&&sortOptions.some(([key])=>key===value)){
     sort=value;if(sort==='random')randomOrders.delete(type);limit=40;render();
   }
   closeSort(true);
 }
 function render(){
   U.pageTone(entityColour(type));
   const found=U.related(query),all=found[type].filter(r=>(type!=='albums'||U.properAlbum(r))&&(!tag||type!=='songs'||r.tag_ids.includes(tag)));
   const order=sort==='random'?randomOrder(type):null;
   all.sort(order?(a,b)=>(order.get(a.id)??Infinity)-(order.get(b.id)??Infinity)||a.id-b.id:sort==='name'?(a,b)=>a.name.localeCompare(b.name)||a.id-b.id:(a,b)=>(b.score??-Infinity)-(a.score??-Infinity)||a.name.localeCompare(b.name)||a.id-b.id);
   const host=$('#catalog-results');host.innerHTML=all.slice(0,limit).map(card).join('')||'<div class="empty">No '+type+' found. Try another name or category.</div>';
   $('#result-count').textContent=`${all.length} ${type} · ${Math.min(limit,all.length)} shown`;
   $('#search-more').hidden=limit>=all.length;syncSort();
   $$('.search-toolbar [data-search-type]').forEach(b=>{b.classList.toggle('active',b.dataset.searchType===type);b.setAttribute('aria-pressed',String(b.dataset.searchType===type));const count=found[b.dataset.searchType].filter(r=>b.dataset.searchType!=='albums'||U.properAlbum(r)).length;b.querySelector('small').textContent=count;});
   const selected=U.records('tags').find(t=>t.id===tag),filter=$('#search-tag-filter');filter.hidden=!selected||type!=='songs';
   const nearby=selected?U.records('tags').filter(t=>t.id!==tag&&U.records('songs').some(s=>s.tag_ids.includes(tag)&&s.tag_ids.includes(t.id))).slice(0,12):[];
   filter.innerHTML=selected?`<span class="tag-chip"># ${esc(selected.name)}</span><button class="btn" data-search-clear-tag>Clear tag</button>${nearby.length?`<details class="related-tags"><summary>Related tags</summary><div class="tag-cloud">${nearby.map(t=>`<a class="tag-chip" href="${U.urlFor('tags',t)}"># ${esc(t.name)}</a>`).join('')}</div></details>`:''}`:'';
   const params=new URLSearchParams({type});if(query)params.set('q',query);if(tag)params.set('tag',tag);params.set('sort',sort);
   history.replaceState(null,'','/search?'+params);fitBadges();
 }
 function init(ui){
   U=ui;const params=new URLSearchParams(location.search);type=entityTypes.includes(params.get('type'))?params.get('type'):'songs';query=params.get('q')||'';tag=Number(params.get('tag'))||null;sort=['score','name','random'].includes(params.get('sort'))?params.get('sort'):(query.trim()?'score':'random');limit=40;randomOrders=new Map();
   document.body.classList.add('search-page');
   U.main.innerHTML=`<div class="page-head"><h1>Search</h1></div><section class="panel search-controls dashboard-surface"><form class="search-form" id="catalog-search" role="search"><input id="catalog-query" name="q" type="search" value="${esc(query)}" placeholder="Songs, artists, albums, tags…" aria-label="Search collection"><button type="submit" aria-label="Search collection">↵</button></form><div class="search-toolbar"><div class="pill-nav" aria-label="Search category">${entityTypes.map(t=>`<button class="pill" style="--category-color:var(--${entityColour(t)})" data-search-type="${t}" aria-pressed="false">${t[0].toUpperCase()+t.slice(1)} <small>0</small></button>`).join('')}</div><p id="result-count" role="status" aria-live="polite" aria-atomic="true"></p><div class="search-sort"><span id="search-sort-label">Sort</span><div class="search-sort-select" id="search-sort-control"><button type="button" id="search-sort" aria-haspopup="listbox" aria-expanded="false" aria-controls="search-sort-menu" aria-labelledby="search-sort-label search-sort-value"><span id="search-sort-value"></span><span class="sort-chevron" aria-hidden="true"></span></button><div id="search-sort-menu" class="search-sort-menu" role="listbox" aria-labelledby="search-sort-label" hidden>${sortOptions.map(([value,label])=>`<button type="button" role="option" tabindex="-1" data-search-sort="${value}" aria-selected="false">${label}<span class="sort-check" aria-hidden="true">✓</span></button>`).join('')}</div></div></div></div><div id="search-tag-filter" class="search-tag-filter" hidden></div></section><div class="results" id="catalog-results"></div><div class="more-area"><button class="btn" id="search-more" data-search-more>Load more</button></div>`;
   render();
 }
 document.addEventListener('click',e=>{if(!U)return;
   if(!e.target.closest('#search-sort-control'))closeSort();
   const b=e.target.closest('button');if(!b)return;
   if(b.id==='search-sort'){$('#search-sort-menu').hidden?openSort():closeSort();return;}
   if(b.dataset.searchSort){chooseSort(b.dataset.searchSort);return;}
   if(b.dataset.searchType){type=b.dataset.searchType;tag=null;limit=40;render();}
   if(b.hasAttribute('data-search-more')){limit+=40;render();}
   if(b.hasAttribute('data-search-clear-tag')){tag=null;render();}
 });
 document.addEventListener('input',e=>{if(U&&e.target.id==='catalog-query'){updateQuery(e.target.value);}});
 document.addEventListener('keydown',e=>{
   if(!U||!e.target.closest('#search-sort-control'))return;
   const menu=$('#search-sort-menu'),options=$$('#search-sort-menu [role="option"]');
   if(e.key==='Escape'&&!menu.hidden){e.preventDefault();closeSort(true);return;}
   if(e.key==='Tab'){closeSort(true);return;}
   const moves=['ArrowDown','ArrowUp','Home','End'];
   if(e.target.id==='search-sort'&&moves.includes(e.key)){
     e.preventDefault();openSort();if(e.key==='Home')options[0].focus();if(e.key==='End')options.at(-1).focus();return;
   }
   if(menu.hidden)return;
   const index=options.indexOf(document.activeElement);
   if(moves.includes(e.key)){
     e.preventDefault();options[e.key==='Home'?0:e.key==='End'?options.length-1:(index+(e.key==='ArrowDown'?1:-1)+options.length)%options.length].focus();
   }else if((e.key==='Enter'||e.key===' ')&&options.includes(e.target)){
     e.preventDefault();chooseSort(e.target.dataset.searchSort);
   }else if(e.key.length===1&&/\S/.test(e.key)){
     const option=options.find(option=>option.textContent.trim().toLocaleLowerCase().startsWith(e.key.toLocaleLowerCase()));
     if(option){e.preventDefault();option.focus();}
   }
 });
 document.addEventListener('focusout',e=>{if(U&&e.target.closest('#search-sort-control')&&!$('#search-sort-control').contains(e.relatedTarget))closeSort();});
 document.addEventListener('submit',e=>{if(U&&e.target.id==='catalog-search'){e.preventDefault();updateQuery($('#catalog-query').value);}});
 window.addEventListener('resize',()=>{if(U){fitBadges();if(!$('#search-sort-menu').hidden)closeSort(true);}});
 return {init,achievementCandidates,fitBadgeRow};
})();
