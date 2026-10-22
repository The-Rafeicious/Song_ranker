/* Developer task dashboard, local recovery and explicit Git controls. */
window.DevSystem=(()=>{
 'use strict';
 const {$,$$,esc}=window.SongRankerUI,managed=new Set(['overview','database','export']);
 let U,view=null,data=null,gitState=null,loadId=0,reviewId=0,loadError='',loading=false;
 let gitBusy=false,backupBusy=false,restoreBusy=false,restoreReview=null,localReview=null,backupQuery='',backupLimit=10,inventoryQuery='',inventoryKind='all',note='';
 const bytes=n=>n>=1048576?(n/1048576).toFixed(1)+' MB':n>=1024?(n/1024).toFixed(1)+' KB':n+' B';
 const date=s=>{const d=new Date(s);return Number.isFinite(d.getTime())?d.toLocaleString():s||'Not recorded'};
 const button=(label,attr,kind='')=>`<button class="btn ${kind}" type="button" ${attr}>${label}</button>`;
 const tile=(label,detail,attr,kind='song')=>`<button class="system-task" type="button" ${attr}><strong class="${kind}">${label}</strong><span>${detail}</span></button>`;
 const header=()=>'';
 function viewChanged(next){if(next!==view){view=managed.has(next)?next:null;++loadId;++reviewId;restoreReview=null;localReview=null;loadError='';window.DevDatabase?.close()}}
 function render(next){view=next;draw();load(next==='export')}
 function controls(){
  $$('[data-system-git-open]').forEach(b=>{b.disabled=restoreBusy;b.textContent=gitBusy?'Git task running…':'Review Git'});
  $$('[data-system-backup]').forEach(b=>{b.disabled=backupBusy||restoreBusy;b.textContent=backupBusy?'Backing up…':b.hasAttribute('data-dev-header')?'Local backup':'Create backup'});
  $$('[data-system-check],[data-system-upload]').forEach(b=>b.disabled=b.disabled||gitBusy||restoreBusy);
 }
 function status(){return `<p id="system-note" role="status" aria-live="polite">${esc(note)}</p>${loadError?`<p class="error" role="alert">${esc(loadError)}</p>${button('Retry status','data-system-retry')}`:''}`}
 function draw(){
  if(!view||!U.root())return;
  const title={overview:'Developer home',database:'Database & backups',export:'Git upload & updates'}[view];
  U.root().innerHTML=U.title(title)+`<div class="dev-system">${status()}<div id="system-content">${data?content():'<section class="panel"><p role="status">Loading local status…</p></section>'}</div></div>`;
  if(view==='database'&&data){drawBackups();drawInventory();drawRestore()}
  if(view==='export')drawLocalChoice();
  controls();
 }
 function content(){return view==='overview'?overview():view==='database'?database():sync()}
 function overview(){
  const t=data.totals,inventory=data.inventory||[];
  const count=name=>inventory.find(r=>r.name===name)?.rows||0;
  const metric=(n,label,c='song')=>`<div><b class="${c}">${n}</b><span>${label}</span></div>`;
  const row=(label,value,tone='')=>`<div class="health-row"><span>${label}</span><strong class="${tone}">${esc(value)}</strong></div>`;
  return `<div class="dev-home-grid"><section class="panel dashboard-surface dev-home-library"><div class="section-head"><h2>Library</h2></div><div class="joined-metrics" data-columns="4">${[[t.songs,'Songs','song'],[t.artists,'Artists','artist'],[t.releases,'Releases','album'],[t.tags,'Tags','tag']].map(([n,label,c])=>`<button type="button" class="dev-library-link" data-dev="${{song:'songs',artist:'artists',album:'albums',tag:'tags'}[c]}"><b class="${c}">${n}</b><span>${label}</span></button>`).join('')}</div></section><section class="panel dashboard-surface dev-home-summary"><div class="section-head"><h2><button type="button" class="dev-title-link" data-tool="Database integrity">Database health ↗</button></h2></div>${row('App / schema','V'+data.version+' / '+data.schema)}${row('SQLite integrity',data.integrity,data.integrity==='ok'?'song':'error')}${row('Foreign-key errors',data.foreign_key_errors,data.foreign_key_errors?'error':'song')}</section><section class="panel dashboard-surface dev-home-summary"><div class="section-head"><h2><button type="button" class="dev-title-link" data-dev="export">Git sync ↗</button></h2></div>${gitOverview(row)}</section><section class="panel dashboard-surface dev-home-summary"><div class="section-head"><h2><button type="button" class="dev-title-link" data-dev="database">Local backups ↗</button></h2></div>${row('Saved copies',data.backups.length)}${row('Latest backup',data.backups[0]?date(data.backups[0].modified):'None yet')}${row('Database size',bytes(data.database_bytes||0))}</section><section class="panel dashboard-surface dev-home-summary dev-home-tag-workshop"><div class="section-head"><h2><button type="button" class="dev-title-link" data-dev="tag_workbench">Tag Workshop ↗</button></h2></div><div class="dev-service-metrics">${metric(t.songs-t.untagged,'Tagged songs','song')}${metric(t.tags,'Available tags','tag')}</div></section><section class="panel dashboard-surface"><div class="section-head"><h2>Catalogue coverage</h2></div>${row('Untagged songs',t.untagged,'tag')}${row('Missing previews',t.missing_previews,'artist')}${row('Missing Apple links',t.missing_sources,'album')}</section><section class="panel dashboard-surface"><div class="section-head"><h2>Stored rounds & votes</h2></div><div class="dev-service-metrics">${metric(count('history'),'Votes','standard')}${metric(count('trivia_rounds'),'Trivia rounds','recognition')}${metric(count('tournaments'),'Tournaments','tournament')}${metric(count('elo_guess_rounds'),'Elo guesses','guesser')}${metric(count('album_shelf_rounds'),'Shelves rounds','shelves')}${metric(t.vibe_mapped??'—','Fully mapped songs','vibe')}</div></section></div>`;
 }
 function gitOverview(row){const g=gitState||data?.git;if(!g?.available)return `<p class="muted">${esc(g?.message||'Git unavailable')}</p>`;return row('Branch',g.branch)+row('Commit',g.head?.slice(0,10)||'Unknown')+row('Cached code',labels[g.state]||g.state,g.state==='up_to_date'?'song':'');}
 function health(){return `<div class="health-row"><span>App / schema</span><strong>V${esc(data.version)} / ${data.schema}</strong></div><div class="health-row"><span>SQLite integrity</span><strong class="${data.integrity==='ok'?'song':'error'}">${esc(data.integrity)}</strong></div><div class="health-row"><span>Foreign-key errors</span><strong>${data.foreign_key_errors}</strong></div><div class="health-row"><span>Local database backups</span><strong>${data.backups.length}</strong></div>`}
 function database(){return `<div class="dev-maintenance-grid"><section class="panel dashboard-surface"><div class="section-head"><h2>Local backups</h2><a href="/api/dev/help/dev">Dev guide</a></div><div class="system-actions">${button('Create backup','data-system-backup')}<a class="btn" href="/api/dev/database/export">Full export</a></div><label class="system-search">Find a backup<input id="system-backup-query" type="search" value="${esc(backupQuery)}" placeholder="Date, name or purpose…"></label><div class="backup-workspace"><div id="system-backups" class="system-bounded"></div><div id="system-restore"></div></div></section><section class="panel dashboard-surface"><div class="section-head"><h2>Database</h2></div><div class="health-row"><span>Version / schema</span><strong>V${esc(data.version)} / ${data.schema}</strong></div><div class="health-row"><span>Size</span><strong>${bytes(data.database_bytes||0)}</strong></div><div class="health-row"><span>Integrity</span><strong class="${data.integrity==='ok'?'song':'error'}">${esc(data.integrity)}</strong></div><div class="system-actions">${button('Integrity details','data-tool="Database integrity"')}<a class="btn" href="/api/dev/help/technical">Technical guide</a></div></section></div>
 <section class="panel dashboard-surface" id="system-inventory-panel"><div class="section-head"><h2>What is stored</h2><span class="muted">Read-only SQLite inspector</span></div><div id="system-inventory"></div></section>
 <section class="panel dashboard-surface"><details><summary>Resets & advanced tools</summary><div class="system-actions">${['Reset match history','Reset trivia history','Reset tournament history','Reset Elo Guesser history','Reset Album Shelves history','Reset Vibe Map','Reset competition'].map(label=>button(label,`data-tool="${label}"`,'danger')).join('')}</div><div class="system-actions">${button('Duplicate finder','data-tool="Duplicate finder"')}${button('Readable text report','data-tool="Export snapshot"')}</div></details></section>`}
 const labels={up_to_date:'Up to date',ahead:'Local commits waiting',behind:'Incoming updates',diverged:'Diverged history',not_checked:'Remote not checked',operation_in_progress:'Git operation in progress'};
 function gitSummary(){
  const g=gitState||data?.git;
  if(!g?.available)return `<p>${esc(g?.message||'Git status unavailable.')}</p><p class="muted">Local backups and full exports remain available. Git setup is explained in the technical guide.</p>`;
  return `<div class="health-row"><span>Current branch → upload target</span><strong>${esc(g.branch)} → ${esc(g.remote)}/${esc(g.target)}</strong></div><div class="health-row"><span>Destination</span><strong>${esc(g.destination)}</strong></div><div class="health-row"><span>Saved remote view</span><strong>${esc(labels[g.state]||g.state)}</strong></div><div class="health-row"><span>Local / incoming commits</span><strong>${g.ahead??'—'} / ${g.behind??'—'}</strong></div>${g.database_sync?`<p class="${['database_conflict','database_check_failed','database_remote_ahead'].includes(g.database_sync.code)?'error':'muted'}" role="status"><b>Last database check:</b> ${esc(g.database_sync.message)}</p>`:''}${g.code_changes?`<p class="muted">${g.code_changes} local code edits remain on this computer. A backup upload does not publish them.</p>`:''}`;
 }
 function sync(){
  const g=gitState||data.git,d=g?.database_sync,checked=g?.status_source==='checked';
  const canUpload=checked&&g?.available&&g.review_token&&g.tracking_head&&!g.in_progress&&!g.pending_code&&!g.behind&&g.upload_ready!==false;
  const pair=(label,value,tone='')=>`<div class="health-row"><span>${label}</span><strong class="${tone}">${esc(value??'—')}</strong></div>`;
  const databaseLabels={database_matches:'Matches Git snapshot',database_local_ahead:'Local data ready to upload',database_remote_ahead:'Remote data is newer',database_conflict:'Copies need review',no_remote_snapshot:'First snapshot ready',database_uploaded:'Snapshot uploaded',database_updated:'Remote snapshot loaded',database_check_failed:'Comparison failed'};
  return `<section class="panel dashboard-surface"><div class="section-head"><h2>Git & database sync</h2><a href="/api/dev/help/dev">Dev guide</a></div><div class="system-actions">${button(gitBusy?'Checking…':'Refresh status','data-system-check'+(!g?.available||gitBusy?' disabled':''))}${button('Upload backup','data-system-upload aria-label="Upload database backup"'+(!canUpload||gitBusy?' disabled':''),'primary')}${button('Keep local…','data-system-local-review aria-label="Keep local database"'+(!g?.available||!g.review_token||!g.tracking_head||g.in_progress||gitBusy?' disabled':''))}</div><p class="muted" role="status">${checked?'Checked '+esc(date(g.checked_at)):'Not freshly checked · cached results below'}</p><div class="git-status-grid"><section><h3>Code commits</h3>${g?.available?pair('Branch',g.branch)+pair('Target',g.remote+'/'+g.target)+pair('Local commit',g.head?.slice(0,10))+pair('Remote commit',g.tracking_head?.slice(0,10))+pair(checked?'Code status':'Cached code status',labels[g.state]||g.state,g.behind||g.pending_code?'error':'')+pair('Local / incoming',String(g.ahead??'—')+' / '+String(g.behind??'—')):`<p class="error">${esc(g?.message||'Git unavailable')}</p>`}</section><section><h3>Live database</h3>${pair(checked?'Comparison':'Last comparison',databaseLabels[d?.code]||'Not checked',!checked||['database_conflict','database_remote_ahead','database_check_failed'].includes(d?.code)?'error':'song')}<p class="${d&&['database_conflict','database_remote_ahead','database_check_failed'].includes(d.code)?'error':'muted'}" role="status">${esc(d?.message||'Refresh to compare the live database with the committed snapshot.')}</p>${d?.local_songs!=null?pair('Local / remote songs',d.local_songs+' / '+d.remote_songs):''}${g?.behind?'<p class="error">Incoming code commits: restart to update code before uploading.</p>':''}${g?.pending_code?'<p class="error">Publish or resolve local code commits first.</p>':''}${g?.in_progress?'<p class="error">Finish the active Git operation first.</p>':''}${d?.local_changes||d?.remote_changes?`<div class="db-scroll"><table class="data-table"><thead><tr><th>Table</th><th>Local + / − / edited</th><th>Remote + / − / edited</th></tr></thead><tbody>${[...new Set([...Object.keys(d.local_changes||{}),...Object.keys(d.remote_changes||{})])].map(name=>{const fmt=v=>v?[v.added,v.removed,v.edited].join(' / '):'0 / 0 / 0';return `<tr><td>${esc(name)}</td><td>${fmt(d.local_changes?.[name])}</td><td>${fmt(d.remote_changes?.[name])}</td></tr>`}).join('')}</tbody></table></div>`:''}</section></div><div id="system-local-choice"></div></section>
 <section class="panel dashboard-surface"><div class="section-head"><h2>Recent outcomes</h2><a href="/api/dev/help/technical">Technical guide</a></div><div class="system-bounded">${g?.history?.length?g.history.slice(0,8).map(r=>`<article class="system-outcome"><strong class="${r.ok?'song':'error'}">${esc(r.action)} · ${esc(r.code)}</strong><p>${esc(r.message)}</p><small>${esc(date(r.at))}</small></article>`).join(''):'<p class="muted">No recorded outcomes.</p>'}</div></section>`;
 }
 function drawBackups(){
  const root=$('#system-backups');if(!root)return;
  const q=backupQuery.toLocaleLowerCase(),rows=data.backups.filter(r=>(r.name+' '+r.purpose+' '+r.modified).toLocaleLowerCase().includes(q));
  root.innerHTML=`<p>${rows.length} matching backups</p>`+rows.slice(0,backupLimit).map(r=>`<article class="system-backup"><div><strong>${esc(r.purpose)}</strong><p>${esc(r.name)}</p><small>${esc(date(r.modified))} · ${bytes(r.bytes)}</small></div><div class="system-actions">${button('Review restore',`data-system-review="${esc(r.name)}"${restoreBusy?' disabled':''}`)}<a class="btn" href="/api/dev/backups/${encodeURIComponent(r.name)}/download">Download .db</a></div></article>`).join('')+(rows.length>backupLimit?button('Show ten more backups','data-system-more-backups'):'')+(rows.length?'':'<p class="empty">No matching local backups.</p>');
 }
 function drawInventory(){window.DevDatabase?.mount(data.inventory)}
 function drawRestore(){
  const root=$('#system-restore');if(!root)return;if(!restoreReview){root.innerHTML='';return}
  const r=restoreReview,keys=[...new Set([...Object.keys(r.live),...Object.keys(r.backup)])];
  root.innerHTML=`<section class="system-restore-review"><h3>Review whole-database restore</h3><p><strong>${esc(r.filename)}</strong> · ${esc(r.purpose)}</p><p>Backup schema ${r.source_schema} → current schema ${r.target_schema}. Restoring replaces the live catalogue and competition data; a pre-restore backup is made first. New activity since this review requires another review.</p><div class="data-scroll"><table class="data-table"><thead><tr><th>Records</th><th>Live now</th><th>Backup</th></tr></thead><tbody>${keys.map(key=>`<tr><td>${esc(key)}</td><td>${r.live[key]??'—'}</td><td>${r.backup[key]??'—'}</td></tr>`).join('')}</tbody></table></div><div class="system-actions">${button(restoreBusy?'Restoring…':'Back up & restore','data-system-restore'+(restoreBusy?' disabled':''),'danger')}${button('Cancel review','data-system-cancel-restore'+(restoreBusy?' disabled':''))}</div></section>`;
 }
 async function load(freshGit=false){
  const id=++loadId;loading=true;
  try{const r=await U.api('/api/dev/system');if(id!==loadId)return;data=r;gitState=r.git;loadError='';if(view)draw();if(freshGit&&view==='export')await gitTask('check')}
  catch(e){if(id===loadId){loadError=e.message;if(view)draw();else U.toast(e.message)}}finally{if(id===loadId)loading=false}
 }
 async function makeBackup(){
  if(backupBusy||restoreBusy)return;backupBusy=true;controls();
  try{const r=await U.api('/api/dev/backup',{});note='Created '+r.backup;U.toast(note);if(view)await load()}
  catch(e){note=e.message;U.toast(e.message)}finally{backupBusy=false;if(view)draw();controls()}
 }
 async function gitTask(kind){
  if(gitBusy||restoreBusy)return;const g=gitState||data?.git;if(!g?.available)return;
  localReview=null;gitBusy=true;note=kind==='check'?'Checking remote…':'Checking remote, saving snapshot and uploading…';draw();
  try{
   const r=await U.api('/api/dev/git/'+kind,kind==='check'?{}:{review_token:g.review_token});
   ++loadId;gitState=r.git;if(data)data.git=r.git;note=r.message;
  }catch(e){if(e.details?.git){++loadId;gitState=e.details.git;if(data)data.git=e.details.git}note=e.message}
  finally{gitBusy=false;if(view)draw();else U.toast(note);controls()}
 }

 function drawLocalChoice(){
  const node=$('#system-local-choice');if(!node||!localReview)return;
  const r=localReview;
  node.innerHTML=`<section class="system-restore-review"><h3>Keep this computer’s database</h3><p>The local catalogue and results stay active. A verified copy of each database is kept before recording this choice. Upload will publish the local copy using normal Git checks.</p><div class="data-scroll"><table class="data-table"><thead><tr><th>Records</th><th>Local · keep</th><th>Git snapshot</th></tr></thead><tbody>${Object.keys(r.local).map(k=>`<tr><td>${esc(k)}</td><td>${r.local[k]}</td><td>${r.remote[k]??'—'}</td></tr>`).join('')}</tbody></table></div><label>Type KEEP LOCAL<input id="system-local-confirmation" autocomplete="off" ${gitBusy?'disabled':''}></label><div class="system-actions">${button(gitBusy?'Keeping local…':'Keep local database','data-system-local-apply disabled','danger')}${button('Cancel','data-system-local-cancel'+(gitBusy?' disabled':''))}</div></section>`;
 }
 async function reviewLocalChoice(){
  if(gitBusy||restoreBusy)return;const g=gitState||data?.git;if(!g?.review_token)return;
  gitBusy=true;localReview=null;note='Comparing local and Git databases…';draw();
  try{const r=await U.api('/api/dev/git/keep-local/review',{review_token:g.review_token});++loadId;gitState=r.git;if(data)data.git=r.git;localReview=r;note=r.message}
  catch(e){if(e.details?.git){gitState=e.details.git;if(data)data.git=e.details.git}note=e.message}
  finally{gitBusy=false;if(view)draw();controls()}
 }
 async function keepLocalChoice(){
  if(gitBusy||restoreBusy||!localReview||$('#system-local-confirmation')?.value!=='KEEP LOCAL')return;
  const reviewed=localReview;gitBusy=true;note='Backing up both copies and keeping local…';draw();
  try{const r=await U.api('/api/dev/git/keep-local',{choice_token:reviewed.choice_token,confirmation:'KEEP LOCAL'});++loadId;gitState=r.git;if(data)data.git=r.git;localReview=null;note=r.message;U.toast(note)}
  catch(e){localReview=null;if(e.details?.git){gitState=e.details.git;if(data)data.git=e.details.git}note=e.message}
  finally{gitBusy=false;if(view)draw();controls()}
 }
 async function inspectBackup(name){
  if(restoreBusy)return;const id=++reviewId;restoreReview=null;note='Validating '+name+'…';draw();
  try{const r=await U.api('/api/dev/backups/review',{filename:name});if(id!==reviewId||view!=='database')return;restoreReview=r;note='Compare the saved backup with the live database before restoring.';draw();$('#system-restore')?.scrollIntoView?.({block:'nearest'})}
  catch(e){if(id===reviewId){note=e.message;if(view)draw();else U.toast(e.message)}}
 }
 async function restore(){
  if(restoreBusy||!restoreReview)return;const accepted=restoreReview;++loadId;restoreBusy=true;note='Restoring the reviewed backup…';draw();
  try{
   const r=await U.api('/api/dev/backups/restore',{review_token:accepted.review_token});restoreReview=null;++reviewId;
   note=r.message+' Safety backup: '+r.safety_backup;
   try{await U.afterRestore()}catch(e){note+=' Reload this dashboard to refresh its catalogue.'}
   await load();
  }catch(e){note=e.message;if(e.status===409)restoreReview=null}
  finally{restoreBusy=false;if(view)draw();else U.toast(note);controls()}
 }

 async function handleTool(name){
  if(!U)return false;
  if(name==='Sync database'){U.navigate('export');return true}
  if(name==='Create backup'){await makeBackup();return true}
  if(name==='Restore backup'||name==='Database overview'){U.navigate('database');return true}
  return false;
 }
 document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!U||!b||b.disabled)return;
  if(b.hasAttribute('data-system-git-open'))U.navigate('export');
  if(b.hasAttribute('data-system-backup'))makeBackup();
  if(b.hasAttribute('data-system-retry'))load();
  if(b.hasAttribute('data-system-check'))gitTask('check');
  if(b.hasAttribute('data-system-upload'))gitTask('upload');
  if(b.hasAttribute('data-system-local-review'))reviewLocalChoice();
  if(b.hasAttribute('data-system-local-apply'))keepLocalChoice();
  if(b.hasAttribute('data-system-local-cancel')){localReview=null;note='Database choice cancelled.';draw()}
  if(b.dataset.systemReview)inspectBackup(b.dataset.systemReview);
  if(b.hasAttribute('data-system-restore'))restore();
  if(b.hasAttribute('data-system-cancel-restore')){++reviewId;restoreReview=null;note='Restore cancelled.';draw()}
  if(b.hasAttribute('data-system-more-backups')){backupLimit+=10;drawBackups()}
  if(b.dataset.systemFilter)window.DevTags.openFilter(b.dataset.systemFilter);
  if(b.hasAttribute('data-system-sources'))U.showMissingSources();
 });
 document.addEventListener('input',e=>{if(e.target.id==='system-local-confirmation'){$('[data-system-local-apply]').disabled=gitBusy||e.target.value!=='KEEP LOCAL';}if(e.target.id==='system-backup-query'){backupQuery=e.target.value;backupLimit=10;drawBackups()}if(e.target.id==='system-inventory-query'){inventoryQuery=e.target.value;drawInventory()}});
 document.addEventListener('change',e=>{if(e.target.id==='system-inventory-kind'){inventoryKind=e.target.value;drawInventory()}});
 return {busy:()=>restoreBusy||gitBusy||backupBusy,bindUI:ui=>U=ui,header,viewChanged,render,handleTool,canNavigate:()=>!restoreBusy};
})();
