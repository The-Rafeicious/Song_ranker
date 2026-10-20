/* Developer history/archive lists; mutations stay with the existing reviewed tools. */
window.DevRecords=(()=>{
 'use strict';
 const {$,esc}=window.SongRankerUI;
 let U,view='',query='',filter='all',limit=30;
 const norm=v=>String(v??'').toLocaleLowerCase();
 const song=id=>U.records('songs').find(s=>s.id===id)?.title||'—';
 function render(next){
  if(view!==next){query='';filter='all';limit=30}view=next;
  const tournaments=view==='tournaments',options=tournaments?[['all','All statuses'],['in_progress','In progress'],['completed','Completed']]:[['all','All visibility'],['standard','Non-blind'],['blind','Blind']];
  U.root().innerHTML=U.title(tournaments?'Tournaments':'Match history',tournaments?'<button class="btn danger" data-tool="Reset tournament history">Reset tournaments</button>':'<button class="btn" data-tool="Review saved votes">Review saved votes</button><button class="btn danger" data-tool="Reset match history">Reset matches / Elo</button>')+`<section class="panel dev-records"><div class="system-filters"><label>Find ${tournaments?'a tournament':'a match'}<input id="dev-record-query" type="search" value="${esc(query)}" placeholder="Song, #ID or mode…"></label><label>${tournaments?'Status':'Visibility'}<select id="dev-record-filter">${options.map(([key,label])=>`<option value="${key}" ${key===filter?'selected':''}>${label}</option>`).join('')}</select></label></div><p id="dev-record-count" role="status"></p><div id="dev-record-list"></div><button class="btn" type="button" data-dev-record-more hidden>Show 30 more</button></section>`;
  draw();
 }
 function draw(){
  if(!$('#dev-record-list'))return;
  const data=U.data(),isTournament=view==='tournaments';
  const rows=(isTournament?data.tournaments||[]:data.elo_history||data.history||[]).filter(r=>{
   const state=r.status==='active'?'in_progress':r.status;
   const text=isTournament?[r.id,'#'+r.id,state,r.scope_type,song(r.champion_id),song(r.runner_up_id),song(r.third_place_id)]:[r.id,'#'+r.id,r.mode,r.origin,song(r.winner_id),song(r.loser_id),r.winner,r.loser,r.tournament_id];
   return (filter==='all'||(isTournament?state:r.mode)===filter)&&norm(text.join(' ')).includes(norm(query).trim());
  });
  $('#dev-record-count').textContent=rows.length+' matching '+(isTournament?'tournaments':'matches')+' · showing '+Math.min(limit,rows.length);
  $('[data-dev-record-more]').hidden=rows.length<=limit;
  $('#dev-record-list').innerHTML=isTournament?`<div class="data-scroll"><table class="data-table"><thead><tr><th>ID</th><th>Size</th><th>Scope</th><th>Status</th><th>Champion</th><th>Runner-up</th><th>Third</th><th>Actions</th></tr></thead><tbody>${rows.slice(0,limit).map(t=>`<tr><td>#${t.id}</td><td>${t.size}</td><td>${esc(t.scope_type)}</td><td>${esc(t.status==='in_progress'||t.status==='active'?'In progress':t.status)}</td><td>${U.clipped(song(t.champion_id))}</td><td>${U.clipped(song(t.runner_up_id))}</td><td>${U.clipped(song(t.third_place_id))}</td><td><div class="catalog-actions">${t.status==='completed'?`<button class="btn" data-edit-podium="${t.id}">Edit podium</button>`:''}<button class="btn" data-bracket="${t.id}">View</button><button class="btn danger" data-delete-tournament="${t.id}">Delete</button></div></td></tr>`).join('')||'<tr><td colspan="8">No matching tournaments.</td></tr>'}</tbody></table></div>`:rows.slice(0,limit).map(U.matchRow).join('')||'<div class="empty">No matching matches.</div>';
 }
 document.addEventListener('input',e=>{if(e.target.id==='dev-record-query'){query=e.target.value;limit=30;draw()}});
 document.addEventListener('change',e=>{if(e.target.id==='dev-record-filter'){filter=e.target.value;limit=30;draw()}});
 document.addEventListener('click',e=>{if(e.target.closest('[data-dev-record-more]')){limit+=30;draw()}});
 return {bindUI:ui=>U=ui,render};
})();
