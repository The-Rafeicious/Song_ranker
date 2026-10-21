/* Library Vibe surfaces reuse existing dashboard, banner and ranking components. */
window.VibeLibrary=(()=>{
 'use strict';
 const {esc,modeRankingControls,modeRankingRow,shelfHead}=window.SongRankerUI;
 const categories=['albums','artists','tags'];let U,controller=null,generation=0,library=null,ranking={entity:'albums',view:'top'},lastPage=null;
 const pct=value=>value==null?'—':Number(value).toFixed(1)+'%';
 function placeHome(){const card=document.querySelector('#home-vibe'),anchor=document.querySelector('#overall-highlights');if(card&&anchor)anchor.after(card)}
 async function read(url){
  controller?.abort();const own=new AbortController();controller=own;const ticket=++generation,timer=setTimeout(()=>own.abort(),15000);
  try{const response=await fetch(url,{cache:'no-store',signal:own.signal});if(!response.ok)throw Error('Vibe Map could not load.');const data=await response.json();return ticket===generation&&!own.signal.aborted?data:null}
  catch(error){if(ticket!==generation)return null;if(error.name==='AbortError')throw Error('Vibe Map timed out.');throw error}
  finally{clearTimeout(timer);if(controller===own)controller=null}
 }
 function error(root,action){root.hidden=false;root.innerHTML='<p class="empty" role="alert">Vibe Map could not load.</p><button class="btn vibe" data-vibe-library-retry="'+action+'">Retry Vibe Map</button>'}
 function drawBanner(){
  let root=document.querySelector('#home-vibe-banner');
  if(!root){root=document.createElement('section');root.id='home-vibe-banner';root.className='shelf-section home-records vibe vibe-library-banner';U.main.append(root);root.innerHTML=shelfHead('Vibe Map · consistency','vibe','/mode_rankings/vibe','Rankings')+'<div class="scroller" id="shelf-vibe" tabindex="0" aria-label="Top twenty albums, artists and tags by consistency"></div>';U.attachAutoScroll(root.querySelector('.scroller'))}
  const rows=categories.flatMap(type=>library.banner[type].map(row=>({...row,entity:type})));
  rows.sort((a,b)=>b.consistency-a.consistency||a.rank-b.rank||categories.indexOf(a.entity)-categories.indexOf(b.entity));
  root.hidden=!rows.length;
  const scroller=root.querySelector('.scroller');scroller.innerHTML=rows.map(row=>{const type=row.entity;return `<a class="shelf-card vibe ${U.colour(type)}" href="${U.urlFor(type,row)}" data-vibe-banner-row="${row.id}" data-vibe-banner-kind="${type}"><span class="shelf-rank">${row.rank}</span><div class="shelf-art">${U.artwork(row,type)}</div><div class="shelf-info"><h3 class="${U.colour(type)}" title="${esc(row.name)}">${esc(row.name)}</h3><p class="song">${row.mapped} / ${row.total} tracks mapped</p><strong class="vibe">${pct(row.consistency)} consistency</strong></div></a>`}).join('');scroller.scrollLeft=0;
 }
 async function mount(page){
  lastPage=page;const home=page==='home',id=home?'home-vibe':'global-vibe';let root=document.getElementById(id);
  if(!root){root=document.createElement('section');root.id=id;root.className='panel mode-stats-panel dashboard-surface vibe vibe-library-panel';root.dataset.globalSection='vibe';const anchor=document.querySelector(home?'#overall-highlights':'#overall-global');if(!anchor)return;anchor.after(root)}
  root.hidden=home;root.setAttribute('aria-busy','true');root.innerHTML='<div class="section-head"><h2 class="vibe">Vibe Map</h2><div class="vibe-library-links"><a class="vibe" href="/vibe_map_stats">Stats ↗</a><a class="vibe" href="/mode_rankings/vibe">Rankings ↗</a></div></div><div class="mode-stats-page vibe-library-content"><p class="empty" role="status">Loading Vibe Map…</p></div>';
  try{const data=await read('/api/vibe-map/library');if(!data||!root.isConnected)return;library=data;root.querySelector('.vibe-library-content').innerHTML=home?data.html:data.global_html;root.hidden=home&&!data.profile_ready;if(home){placeHome();drawBanner()}}
  catch(e){if(e.name!=='AbortError'&&root.isConnected)error(root,page)}finally{root.setAttribute('aria-busy','false')}
 }
 async function mountRankings(){
  const params=new URLSearchParams(location.search);ranking={entity:categories.includes(params.get('entity'))?params.get('entity'):'albums',view:params.get('view')==='bottom'?'bottom':'top'};
  U.pageTone('vibe');document.body.classList.add('rankings-page','standard-rankings-page','mode-rankings-page','vibe-rankings');document.body.style.setProperty('--rank-color','var(--vibe)');
  const bottom=ranking.view==='bottom';history.replaceState({},'',`/mode_rankings/vibe?entity=${ranking.entity}&view=${ranking.view}`);
  U.main.innerHTML='<div class="page-head"><h1 class="vibe">Vibe Map Rankings</h1></div>'+modeRankingControls('/mode_rankings/vibe',ranking.entity,bottom,'vibe',categories)+'<div class="leaderboard" id="vibe-ranking-rows"><p class="empty" role="status">Loading consistency…</p></div>';
  const root=document.querySelector('#vibe-ranking-rows');
  try{const data=await read(`/api/vibe-map/rankings?entity=${ranking.entity}&view=${ranking.view}`);if(!data||!root.isConnected)return;
   root.innerHTML=data.items.map((row,i)=>modeRankingRow(U,row,ranking.entity,i,data.total,bottom,'vibe',pct(row.consistency),'Consistency',[`${row.mapped} / ${row.total} tracks mapped`],row.rank)).join('')||'<p class="empty">No ranked collections yet</p>';
  }catch(e){if(e.name!=='AbortError'&&root.isConnected)error(root,'rankings')}
 }
 document.addEventListener('click',event=>{
  const range=event.target.closest('[data-vibe-view]');if(range){history.replaceState({},'',`/mode_rankings/vibe?entity=${ranking.entity}&view=${range.dataset.vibeView}`);void mountRankings()}
  const retry=event.target.closest('[data-vibe-library-retry]');if(retry){if(retry.dataset.vibeLibraryRetry==='rankings')void mountRankings();else void mount(retry.dataset.vibeLibraryRetry)}
 });
 window.addEventListener('pagehide',()=>{generation++;controller?.abort();controller=null});
 window.addEventListener('pageshow',event=>{if(event.persisted&&U){if(document.body.classList.contains('vibe-rankings'))void mountRankings();else if(lastPage)void mount(lastPage)}});
 return Object.freeze({bindUI:ui=>U=ui,mount,mountRankings,placeHome});
})();
