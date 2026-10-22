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
 function viewChanged(next){if(next!==view){view=managed.has(next)?next:null;++loadId;++reviewId;restoreReview=null;localReview=null;loadError=''}}
 function render(next){view=next;draw();load()}
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
  return `<div class="dev-home-grid"><section class="panel dashboard-surface dev-home-library"><div class="section-head"><h2>Library</h2></div><div class="joined-metrics" data-columns="4">${[[t.songs,'Songs','song'],[t.artists,'Artists','artist'],[t.releases,'Releases','album'],[t.tags,'Tags','tag']].map(([n,label,c])=>`<button type="button" class="dev-library-link" data-dev="${{song:'songs',artist:'artists',album:'albums',tag:'tags'}[c]}"><b class="${c}">${n}</b><span>${label}</span></button>`).join('')}</div></section><section class="panel dashboard-surface dev-home-summary"><div class="section-head"><h2><button type="button" class="dev-title-link" data-tool="Database integrity">Database health ↗</button></h2></div>${row('App / schema','V'+data.version+' / '+data.schema)}${row('SQLite integrity',data.integrity,data.integrity==='ok'?'song':'error')}${row('Foreign-key errors',data.foreign_key_errors,data.foreign_key_errors?'error':'song')}</section><section class="panel dashboard-surface dev-home-summary"><div class="section-head"><h2><button type="button" class="dev-title-link" data-dev="export">Git sync ↗</button></h2></div>${gitOverview(row)}</section><section class="panel dashboard-surface dev-home-summary"><div class="section-head"><h2><button type="button" class="dev-title-link" data-dev="database">Local backups ↗</button></h2></div>${row('Saved copies',data.backups.length)}${row('Latest backup',data.backups[0]?date(data.backups[0].modified):'None yet')}${row('Database size',bytes(data.database_bytes||0))}</section><section class="panel dashboard-surface"><div class="section-head"><h2>Catalogue coverage</h2></div>${row('Untagged songs',t.untagged,'tag')}${row('Missing previews',t.missing_previews,'artist')}${row('Missing Apple links',t.missing_sources,'album')}</section><section class="panel dashboard-surface"><div class="section-head"><h2>Stored rounds & votes</h2></div><div class="dev-service-metrics">${metric(count('history'),'Votes','standard')}${metric(count('trivia_rounds'),'Trivia rounds','recognition')}${metric(count('tournaments'),'Tournaments','tournament')}${metric(count('elo_guess_rounds'),'Elo guesses','guesser')}${metric(count('album_shelf_rounds'),'Shelves rounds','shelves')}${metric(t.vibe_mapped??'—','Fully mapped songs','vibe')}</div></section></div>`;
 }
 function gitOverview(row){const g=gitState||data?.git;if(!g?.available)return `<p class="muted">${esc(g?.message||'Git unavailable')}</p>`;return row('Branch',g.branch)+row('Commit',g.head?.slice(0,10)||'Unknown')+row('Status',labels[g.state]||g.state,g.state==='up_to_date'?'song':'');}
 function health(){return `<div class="health-row"><span>App / schema</span><strong>V${esc(data.version)} / ${data.schema}</strong></div><div class="health-row"><span>SQLite integrity</span><strong class="${data.integrity==='ok'?'song':'error'}">${esc(data.integrity)}</strong></div><div class="health-row"><span>Foreign-key errors</span><strong>${data.foreign_key_errors}</strong></div><div class="health-row"><span>Local database backups</span><strong>${data.backups.length}</strong></div>`}
 function database(){return `<section class="panel dashboard-surface"><div class="section-head"><h2>Backups & recovery</h2></div>${health()}<div class="system-actions">${button('Create backup','data-system-backup')}<a class="btn" href="/api/dev/database/export">Download full export</a><a class="btn" href="/api/dev/database/guide">Download technical guide</a></div><p class="muted">A local .db backup restores the whole database. The JSON export preserves every stored field for validation/rebuild. The Git SQL snapshot is a separate upload file.</p><div id="system-restore"></div><label class="system-search">Find a backup<input id="system-backup-query" type="search" value="${esc(backupQuery)}" placeholder="Date, filename or purpose…"></label><div id="system-backups"></div></section>
   <section class="panel dashboard-surface" id="system-inventory-panel"><div class="section-head"><h2>What is stored</h2></div><p class="muted">Stored facts, rebuildable projections and derived views are labelled separately. Counts come from one database snapshot.</p><div class="system-filters"><label>Find a table/view<input id="system-inventory-query" type="search" value="${esc(inventoryQuery)}"></label><label>Show<select id="system-inventory-kind"><option value="all">All objects</option><option value="table">Stored tables</option><option value="view">Derived views</option><option value="extensions">Extensions</option></select></label></div><div id="system-inventory"></div></section>
   <section class="panel dashboard-surface"><details><summary>Competition resets & advanced tools</summary><p class="muted">These tools retain the music catalogue. Each reset shows its scope and confirmation. Create a backup first if you want a restore point.</p><div class="system-actions">${['Reset match history','Reset trivia history','Reset tournament history','Reset Elo Guesser history','Reset Album Shelves history','Reset Vibe Map','Reset competition'].map(label=>button(label,`data-tool="${label}"`,'danger')).join('')}</div><div class="system-actions">${button('Duplicate finder','data-tool="Duplicate finder"')}${button('Readable text report','data-tool="Export snapshot"')}</div><p class="muted">The readable text report is saved in the project folder; use the full export or a .db backup for recovery.</p></details></section>`}
 const labels={up_to_date:'Up to date',ahead:'Local commits waiting',behind:'Incoming updates',diverged:'Diverged history',not_checked:'Remote not checked',operation_in_progress:'Git operation in progress'};
 function gitSummary(){
  const g=gitState||data?.git;
  if(!g?.available)return `<p>${esc(g?.message||'Git status unavailable.')}</p><p class="muted">Local backups and full exports remain available. Git setup is explained in the technical guide.</p>`;
  return `<div class="health-row"><span>Current branch → upload target</span><strong>${esc(g.branch)} → ${esc(g.remote)}/${esc(g.target)}</strong></div><div class="health-row"><span>Destination</span><strong>${esc(g.destination)}</strong></div><div class="health-row"><span>Saved remote view</span><strong>${esc(labels[g.state]||g.state)}</strong></div><div class="health-row"><span>Local / incoming commits</span><strong>${g.ahead??'—'} / ${g.behind??'—'}</strong></div>${g.database_sync?`<p class="${['database_conflict','database_check_failed','database_remote_ahead'].includes(g.database_sync.code)?'error':'muted'}" role="status"><b>Last database check:</b> ${esc(g.database_sync.message)}</p>`:''}${g.code_changes?`<p class="muted">${g.code_changes} local code edits remain on this computer. A backup upload does not publish them.</p>`:''}`;
 }
 function sync(){
  const g=gitState||data.git,canUpload=g?.available&&g.review_token&&g.tracking_head&&!g.in_progress&&!g.pending_code&&!g.behind;
  return `<section class="panel dashboard-surface"><div class="section-head"><h2>Upload database backup</h2></div>${gitSummary()}<p>The upload creates a consistent <code>database_backup.sql</code>, commits that file only, then pushes the configured branch. Your live database continues to save locally.</p><div class="system-actions">${button(gitBusy?'Git task running…':'Check remote','data-system-check'+(!g?.available||gitBusy?' disabled':''))}${button('Upload database backup','data-system-upload'+(!canUpload||gitBusy?' disabled':''),'primary')}${button('Keep local database…','data-system-local-review'+(!g?.available||!g.review_token||!g.tracking_head||g.in_progress||gitBusy?' disabled':''))}</div><div id="system-local-choice"></div>${g?.pending_code?'<p class="error">Unpublished code commits need review/publishing through Git first. The backup button will not publish them.</p>':''}${g?.behind?'<p class="muted">Incoming commits need a restart update, or manual resolution if history diverged. No database rows will be merged.</p>':''}${!g?.tracking_head&&g?.available?'<p class="muted">Check remote first to identify the target branch.</p>':''}${g?.snapshot?.exists?`<p class="muted">Local SQL snapshot: ${esc(g.snapshot.name)} · ${bytes(g.snapshot.bytes)}</p>`:''}</section>
   <section class="panel dashboard-surface"><div class="section-head"><h2>How updates keep your data</h2></div><div class="system-explanations"><p><b>Check remote</b> fetches Git information. It changes neither running code nor the live database.</p><p><b>Restart</b> stops the current app first; run <code>python main.py</code> again. A safe fast-forward installs before the app loads. Local edits, conflicts, diverged history and incoming protected files block automatic updates.</p><p><b>Database sync</b> runs before the normal launcher serves pages, even after a manual Git pull. A newer committed snapshot loads only after validation, a local archive and a shared-baseline comparison covering edits and deletions. A split keeps local data and saves an incoming backup for review; review the incoming backup to restore it, or use Keep local database to retain and publish your local copy. Both copies are backed up before a local choice is accepted.</p><p><b>Push failed or reply lost</b> keeps the local snapshot/commit. Check remote and retry. An unchanged snapshot creates no duplicate commit. Upload also rechecks the database baseline so an older laptop cannot overwrite newer remote data. There is no automatic row merge, rebase or force-push.</p></div><a class="btn" href="/api/dev/database/guide">Download Git & recovery guide</a></section>
   <section class="panel dashboard-surface"><div class="section-head"><h2>Recent Git outcomes</h2></div>${g?.history?.length?g.history.map(row=>`<article class="system-outcome"><strong class="${row.ok?'song':'error'}">${esc(row.action)} · ${esc(row.code)}</strong><p>${esc(row.message)}</p><small>${esc(date(row.at))}${row.commit?' · '+esc(row.commit.slice(0,10)):''}</small></article>`).join(''):'<p class="empty">No app Git outcome recorded yet. Opening this page does not contact the remote.</p>'}</section>`;
 }
 function drawBackups(){
  const root=$('#system-backups');if(!root)return;
  const q=backupQuery.toLocaleLowerCase(),rows=data.backups.filter(r=>(r.name+' '+r.purpose+' '+r.modified).toLocaleLowerCase().includes(q));
  root.innerHTML=`<p>${rows.length} matching backups</p>`+rows.slice(0,backupLimit).map(r=>`<article class="system-backup"><div><strong>${esc(r.purpose)}</strong><p>${esc(r.name)}</p><small>${esc(date(r.modified))} · ${bytes(r.bytes)}</small></div><div class="system-actions">${button('Review restore',`data-system-review="${esc(r.name)}"${restoreBusy?' disabled':''}`)}<a class="btn" href="/api/dev/backups/${encodeURIComponent(r.name)}/download">Download .db</a></div></article>`).join('')+(rows.length>backupLimit?button('Show ten more backups','data-system-more-backups'):'')+(rows.length?'':'<p class="empty">No matching local backups.</p>');
 }
 function drawInventory(){
  const root=$('#system-inventory');if(!root)return;$('#system-inventory-kind').value=inventoryKind;
  const q=inventoryQuery.toLocaleLowerCase(),rows=data.inventory.filter(r=>(r.name+' '+r.group+' '+r.role).toLocaleLowerCase().includes(q)&&(inventoryKind==='all'||inventoryKind==='extensions'&&r.group==='Extensions'||r.kind===inventoryKind));
  root.innerHTML=[...new Set(rows.map(r=>r.group))].map(group=>`<section class="system-store-group"><h3>${esc(group)}</h3>${rows.filter(r=>r.group===group).map(r=>`<div class="system-store-row"><div><code>${esc(r.name)}</code><small>${esc(r.kind)} · ${esc(r.role)}</small></div><strong>${r.rows??'Unavailable'}</strong></div>`).join('')}</section>`).join('')||'<p class="empty">No matching tables/views.</p>';
 }
 function drawRestore(){
  const root=$('#system-restore');if(!root)return;if(!restoreReview){root.innerHTML='';return}
  const r=restoreReview,keys=[...new Set([...Object.keys(r.live),...Object.keys(r.backup)])];
  root.innerHTML=`<section class="system-restore-review"><h3>Review whole-database restore</h3><p><strong>${esc(r.filename)}</strong> · ${esc(r.purpose)}</p><p>Backup schema ${r.source_schema} → current schema ${r.target_schema}. Restoring replaces the live catalogue and competition data; a pre-restore backup is made first. New activity since this review requires another review.</p><div class="data-scroll"><table class="data-table"><thead><tr><th>Records</th><th>Live now</th><th>Backup</th></tr></thead><tbody>${keys.map(key=>`<tr><td>${esc(key)}</td><td>${r.live[key]??'—'}</td><td>${r.backup[key]??'—'}</td></tr>`).join('')}</tbody></table></div><div class="system-actions">${button(restoreBusy?'Restoring…':'Back up & restore','data-system-restore'+(restoreBusy?' disabled':''),'danger')}${button('Cancel review','data-system-cancel-restore'+(restoreBusy?' disabled':''))}</div></section>`;
 }
 async function load(){
  const id=++loadId;loading=true;
  try{const r=await U.api('/api/dev/system');if(id!==loadId)return;data=r;gitState=r.git;loadError='';if(view)draw()}
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
