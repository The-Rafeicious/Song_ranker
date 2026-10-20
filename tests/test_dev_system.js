/* Actual dashboard/site/tag modules; HTTP and native media are isolated mocks. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=n=>fs.readFileSync(path.join(__dirname,'../static/js',n),'utf8');
let assertions=0;const check=(v,label)=>{assert.ok(v,label);assertions++};
async function flush(){for(let i=0;i<120;i++)await Promise.resolve()}
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};
function git(extra={}){return {available:true,state:'up_to_date',branch:'main',remote:'origin',target:'main',destination:'example.org/owner/app',tracking_head:'abc',ahead:0,behind:0,pending_code:false,code_changes:0,in_progress:false,review_token:'git-review',history:[],snapshot:{exists:true,name:'database_backup.sql',bytes:20},...extra}}
function status(){return {version:'4.0.0.7.3',schema:13,integrity:'ok',foreign_key_errors:0,totals:{songs:4,artists:1,releases:1,tags:1,untagged:2,missing_previews:1,missing_sources:4},
 backups:Array.from({length:12},(_,i)=>({name:'manual_'+i+'.db',purpose:'Manual backup',modified:'2026-10-18T12:00:00Z',bytes:1024})),
 inventory:[{name:'songs',kind:'table',group:'Catalogue',role:'Stored facts',rows:4},{name:'preference_mode_ratings',kind:'table',group:'Voting',role:'Rebuildable projection',rows:8},{name:'v_history',kind:'view',group:'Derived views',role:'Derived / read-only',rows:2},{name:'extra <notes>',kind:'table',group:'Extensions',role:'Stored facts',rows:1}],git:git()}}
async function harness(view='',width=1280,session={}){
 const dom=new JSDOM('<body data-page="dev"><main id="main"><div id="loading"></div></main><input id="volume-range" value=".5"><span id="volume-value"></span><button id="volume-btn"></button><div id="volume-panel" hidden></div><div id="preview-status" hidden></div><dialog id="editor"><form id="editor-form"><h2 id="editor-title"></h2><div id="editor-fields"></div><button type="button" id="editor-close">Close</button><button id="editor-submit">Save</button></form></dialog><div id="toast" hidden></div></body>',{url:'http://localhost/dev/dashboard'+(view?'?view='+view:''),runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document,requests=[],errors=[],plays=[],data={songs:Array.from({length:4},(_,i)=>({id:i+1,title:'Song '+(i+1),artist_ids:[1],album_id:1,tag_ids:i%2?[1]:[],audio_url:i===3?'':'preview',elo_score:1200})),artists:[{id:1,name:'Artist'}],albums:[{id:1,title:'Album'}],tags:[{id:1,name:'Tag'}],history:[],tournaments:[],tournament_matches:[],tournament_entries:[],global_stats:{},special_modes:{}};
 let state=status(),handler=()=>undefined,backups=0;
 for(const [key,value] of Object.entries(session))w.sessionStorage.setItem(key,value);
 w.innerWidth=width;w.scrollTo=()=>{};w.matchMedia=()=>({matches:true});w.HTMLElement.prototype.scrollIntoView=function(){};
 w.HTMLMediaElement.prototype.play=function(){plays.push(this.id);return Promise.resolve()};w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.load=function(){};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
 w.console.error=(...v)=>errors.push(v.join(' '));w.addEventListener('error',e=>errors.push(e.message));
 const respond=(body,status=200)=>({ok:status<400,status,json:async()=>structuredClone(body)});
 w.fetch=async(url,options={})=>{requests.push({url,options});const custom=await handler(url,options);if(custom!==undefined)return custom.status?respond(custom.body,custom.status):respond(custom);
  if(url==='/api/collection')return respond(data);
  if(url==='/api/dev/song-sources')return respond({songs:Object.fromEntries(data.songs.map(s=>[s.id,{status:'needs_link',content_label:'Unknown'}]))});
  if(url==='/api/dev/system')return respond(state);
  if(url==='/api/dev/backup')return respond({backup:'manual_new_'+(++backups)+'.db'});
  if(url==='/api/dev/git/check')return respond({message:'Remote checked.',git:state.git});
  if(url==='/api/dev/git/upload')return respond({message:'Database backup uploaded.',git:state.git});
  if(url==='/api/dev/backups/review')return respond({filename:JSON.parse(options.body).filename,purpose:'Manual backup',source_schema:8,target_schema:13,live:{Songs:4,Preferences:8},backup:{Songs:3,Preferences:5},review_token:'restore-review'});
  if(url==='/api/dev/backups/restore')return respond({message:'Backup restored. Reload open game tabs before continuing.',safety_backup:'pre_restore_test.db'});
  throw Error('Unexpected request '+url);
 };
 w.Overall={bindUI(){}};
 for(const file of ['ui.js','preview.js','special_modes.js','dev_catalog.js','dev_metadata.js','dev_records.js','dev_tags.js','dev_system.js'])w.eval(source(file));
 const expose="window.testDev={refreshData,records,setView:v=>{devView=v;renderDevView()}};window.DevSystem?.bindUI(";
 await w.eval(source('site.js').replace('window.DevSystem?.bindUI(',expose));await flush();
 const click=sel=>{const n=d.querySelector(sel);assert.ok(n,'missing '+sel);n.click();return n};
 const input=(sel,value,event='input')=>{const n=d.querySelector(sel);assert.ok(n,'missing '+sel);n.value=value;n.dispatchEvent(new w.Event(event,{bubbles:true}))};
 return {w,d,requests,errors,plays,data,click,input,state,handler:fn=>handler=fn,close:()=>{w.dispatchEvent(new w.Event('pagehide'));w.close()}};
}
async function entryAndShortcuts(){
 const h=await harness();
 check(h.d.querySelector('h1').textContent==='Developer dashboard','shared visible dashboard title');
 check(h.d.querySelector('#dev-main h2').textContent==='Tasks & health','default lands on frequent tasks');
 check(h.d.querySelectorAll('.system-task').length===6,'six frequent tasks');
 check(h.requests.filter(r=>r.url==='/api/dev/system').length===1,'one local system load on entry');
 check(!h.requests.some(r=>r.url.includes('/git/')),'opening dashboard performs no remote Git task');
 check(h.d.querySelector('.dev-taskbar [data-system-git-open]'),'upload always in top bar');
 check(h.d.querySelector('.dev-taskbar a[href="/api/dev/database/export"]'),'full export visible');
 check(h.plays.length===0,'dashboard never autoplays');
 h.click('[data-system-filter="untagged"]');await flush();
 check(h.d.querySelector('#tag-status').value==='untagged','untagged shortcut applies filter');
 check(h.d.querySelectorAll('[data-tag-song]').length===2,'untagged shortcut exact rows');
 h.click('[data-dev="overview"]');await flush();h.click('[data-system-filter="missing"]');await flush();
 check(h.d.querySelector('#tag-preview-filter').value==='missing','preview shortcut applies filter');
 check(h.d.querySelector('#tag-status').value==='all','shortcut clears other filters');
 check(h.d.querySelectorAll('[data-tag-song]').length===1,'missing preview shortcut exact row');
 h.click('[data-dev="overview"]');await flush();h.click('[data-system-sources]');await flush();
 check(h.d.querySelector('#missing-apple-only').checked,'source shortcut shows missing-link filter');
 check(h.d.querySelector('.dev-taskbar [data-system-backup]'),'top bar survives all views');
 check(h.w.location.search.includes('view=songs'),'view bookmark stays current');
 check(h.errors.length===0,'entry and task navigation have no script errors');h.close();
 const unknown=await harness('unknown');check(unknown.d.querySelector('#dev-main h2').textContent==='Tasks & health','unknown view returns to tasks');unknown.close();
}
async function inventoryAndBackups(){
 const h=await harness('database');
 check(h.d.querySelectorAll('.system-backup').length===10,'backups initially limited to ten');h.click('[data-system-more-backups]');
 check(h.d.querySelectorAll('.system-backup').length===12,'more backups accessible');h.input('#system-backup-query','manual_11');
 check(h.d.querySelectorAll('.system-backup').length===1,'backup search exact');
 check(h.d.querySelector('.system-backup a').getAttribute('href').includes('manual_11.db/download'),'binary backup direct download');
 check(h.d.querySelectorAll('.system-store-row').length===4,'all stored/derived/extension objects shown');
 h.input('#system-inventory-kind','extensions','change');check(h.d.querySelectorAll('.system-store-row').length===1,'extension group filter');
 check(h.d.querySelector('.system-store-row code').textContent==='extra <notes>','untrusted object names escaped');
 check(!h.d.querySelector('.system-store-row notes'),'extension name never becomes markup');
 h.input('#system-inventory-kind','view','change');check(h.d.querySelector('.system-store-row').textContent.includes('Derived / read-only'),'views identified');
 h.input('#system-inventory-kind','all','change');h.input('#system-inventory-query','projection');check(h.d.querySelectorAll('.system-store-row').length===1,'role searchable');
 check(h.d.querySelector('.dev-system details summary').textContent.includes('Competition resets'),'destructive tools collapsed');
 check(!h.d.querySelector('details:has([data-tool="Reset competition"])').open,'reset tools not initially open');
 const pending=deferred();h.handler(async url=>url==='/api/dev/backup'?pending.promise:undefined);
 h.click('.dev-taskbar [data-system-backup]');h.click('.dev-taskbar [data-system-backup]');await flush();
 check(h.requests.filter(r=>r.url==='/api/dev/backup').length===1,'double click makes one backup');
 check(h.d.querySelector('.dev-taskbar [data-system-backup]').disabled,'backup button disabled while running');
 pending.resolve({backup:'manual_created.db'});await flush();
 check(h.d.querySelector('#system-note').textContent.includes('manual_created.db'),'backup result visible');
 check(!h.d.querySelector('.dev-taskbar [data-system-backup]').disabled,'backup action recovers');
 check(h.errors.length===0,'backup and inventory flows have no script errors');h.close();
}
async function gitFlows(){
 const h=await harness('export');
 check(!h.d.querySelector('[data-system-upload]').disabled,'safe cached target allows upload');
 check(h.requests.every(r=>!r.url.startsWith('/api/dev/git/')),'Git panel entry local only');
 const pending=deferred();h.handler(url=>url==='/api/dev/git/check'?pending.promise:undefined);
 h.click('[data-system-check]');h.click('[data-system-check]');await flush();
 check(h.requests.filter(r=>r.url==='/api/dev/git/check').length===1,'one Git task in flight');
 check(h.d.querySelector('[data-system-upload]').disabled,'upload disabled during check');
 pending.resolve({message:'Incoming updates found.',git:git({state:'behind',behind:2})});await flush();
 check(h.d.querySelector('[data-system-upload]').disabled,'incoming code blocks upload');
 check(h.d.querySelector('#system-note').textContent.includes('Incoming updates'),'remote result visible');
 h.handler(url=>url==='/api/dev/git/check'?{message:'Checked.',git:git({review_token:'fresh-target'})}:undefined);
 h.click('[data-system-check]');await flush();check(!h.d.querySelector('[data-system-upload]').disabled,'check resolves blocked state');
 h.handler(url=>url==='/api/dev/git/upload'?{status:502,body:{message:'Push failed. Local commit kept.',git:git({state:'ahead',ahead:1,review_token:'retry-target'})}}:undefined);
 h.click('[data-system-upload]');await flush();
 check(JSON.parse(h.requests.find(r=>r.url==='/api/dev/git/upload').options.body).review_token==='fresh-target','upload binds latest target review');
 check(h.d.querySelector('#system-note').textContent.includes('Local commit kept'),'failure action explained');
 check(!h.d.querySelector('[data-system-upload]').disabled,'failed push remains retryable');
 h.handler(url=>url==='/api/dev/git/upload'?{message:'Retry uploaded.',git:git()}:undefined);
 h.click('[data-system-upload]');await flush();
 check(JSON.parse(h.requests.filter(r=>r.url==='/api/dev/git/upload').at(-1).options.body).review_token==='retry-target','retry binds refreshed target');
 check(h.d.querySelector('#system-note').textContent==='Retry uploaded.','retry success visible');
 for(const extra of [{pending_code:true,ahead:1},{in_progress:true},{tracking_head:null}]){
  h.state.git=git(extra);h.w.testDev.setView('export');await flush();check(h.d.querySelector('[data-system-upload]').disabled,'unsafe Git state disables upload');
 }
 h.state.git={available:false,message:'Git unavailable',history:[]};h.w.testDev.setView('export');await flush();
 check(h.d.querySelector('[data-system-check]').disabled,'missing Git disables remote controls');
 check(h.d.querySelector('.dev-taskbar [data-system-backup]')&&!h.d.querySelector('.dev-taskbar [data-system-backup]').disabled,'local backups available without Git');
 check(h.errors.length===0,'Git flows have no script errors');h.close();
}
async function restoreFlows(){
 const h=await harness('database');h.click('[data-system-review]');await flush();
 check(h.d.querySelector('#system-restore').textContent.includes('Backup schema 8'),'schema change explained');
 check(h.d.querySelectorAll('#system-restore tbody tr').length===2,'restore compares exact record counts');
 check(!h.requests.some(r=>r.url==='/api/dev/backups/restore'),'review alone makes no restore');
 h.click('[data-system-cancel-restore]');check(!h.d.querySelector('[data-system-restore]'),'review can cancel');
 h.click('[data-system-review]');await flush();
 h.handler(url=>url==='/api/dev/backups/restore'?{status:409,body:{message:'Live database changed. Review again.'}}:undefined);
 h.click('[data-system-restore]');await flush();
 check(!h.d.querySelector('[data-system-restore]'),'stale review invalidated');check(h.d.querySelector('#system-note').textContent.includes('Review again'),'stale result actionable');
 h.handler(()=>undefined);h.click('[data-system-review]');await flush();const pending=deferred();h.handler(url=>url==='/api/dev/backups/restore'?pending.promise:undefined);
 h.click('[data-system-restore]');h.click('[data-dev="songs"]');await flush();
 check(h.d.querySelector('#system-restore'),'navigation waits for restore');
 check(h.d.querySelector('.dev-taskbar [data-system-backup]').disabled,'backup waits for restore');
 check(h.d.querySelector('[data-system-restore]').disabled,'restore cannot be double applied');
 pending.resolve({message:'Backup restored. Reload open game tabs.',safety_backup:'pre_restore_fixture.db'});await flush();
 const sent=JSON.parse(h.requests.filter(r=>r.url==='/api/dev/backups/restore').at(-1).options.body);
 check(sent.review_token==='restore-review'&&!sent.filename,'restore sends signed review only');
 check(h.d.querySelector('#system-note').textContent.includes('pre_restore_fixture.db'),'safety backup identified');
 check(h.requests.filter(r=>r.url==='/api/collection').length===2,'catalogue refreshed after restore');
 check(h.requests.filter(r=>r.url==='/api/dev/song-sources').length===2,'source cache refreshed after restore');
 check(!h.d.querySelector('[data-system-restore]'),'completed review cleared');
 check(!h.d.querySelector('.dev-taskbar [data-system-backup]').disabled,'dashboard usable after restore');
 check(h.errors.length===0,'restore flows have no script errors');h.close();
}
async function staleResponses(){
 const h=await harness('database'),review=deferred();h.handler(url=>url==='/api/dev/backups/review'?review.promise:undefined);
 h.click('[data-system-review]');h.click('[data-dev="explorer"]');await flush();review.resolve({filename:'late.db',purpose:'Manual',source_schema:13,target_schema:13,live:{},backup:{},review_token:'late'});await flush();
 check(h.d.querySelector('#dev-query')&&!h.d.querySelector('#system-restore'),'late backup review cannot replace another view');
 const old=deferred();let seen=0;
 h.handler(url=>url==='/api/collection'?(++seen===1?old.promise:{...h.data,songs:h.data.songs.map(s=>({...s,title:'New '+s.id}))}):undefined);
 const first=h.w.testDev.refreshData();await flush();await h.w.testDev.refreshData();old.resolve({...h.data,songs:h.data.songs.map(s=>({...s,title:'Old '+s.id}))});await first;
 check(h.w.testDev.records('songs')[0].title.startsWith('New'),'late pre-restore catalogue cannot overwrite newer fetch');
 check(h.errors.length===0,'late responses have no script errors');h.close();
 const bad=await harness('database');bad.handler(url=>url==='/api/dev/system'?{status:503,body:{message:'Temporarily unavailable'}}:undefined);bad.w.testDev.setView('overview');await flush();
 check(bad.d.querySelector('[data-system-retry]'),'status failure offers retry');bad.handler(()=>undefined);bad.click('[data-system-retry]');await flush();check(!bad.d.querySelector('[data-system-retry]'),'retry recovers');bad.close();
}
async function responsiveContracts(){
 const css=fs.readFileSync(path.join(__dirname,'../static/css/dev_system.css'),'utf8');
 check(css.includes('@media(max-width:800px)')&&css.includes('@media(max-width:520px)'),'phone/tablet breakpoints defined');
 check(css.includes('minmax(0,1fr)')&&css.includes('overflow-wrap:anywhere'),'long names/paths can wrap within grid');
 for(const width of [1440,768,390]){const h=await harness('database',width);
  check(h.d.querySelector('a[href="/api/dev/database/guide"]'),'guide available at '+width);
  check(h.d.querySelector('.dev-taskbar [data-system-git-open]'),'Git shortcut available at '+width);
  check(h.d.querySelectorAll('.system-store-row').length===4,'inventory accessible at '+width);
  check(h.plays.length===0&&h.errors.length===0,'no playback/errors at '+width);h.close();
 }
}
async function stopFlows(){
 const h=await harness(),{w,d,requests}=h;let phase='idle',confirmVisible=false;
 const readyTimers=[];const timeout=w.setTimeout.bind(w);
 w.setTimeout=(fn,ms,...args)=>{if(ms===4000){readyTimers.push(fn);return timeout(()=>{},100000)}return timeout(fn,ms,...args)};
 h.handler((url,options)=>{
  if(url==='/api/dev/stop')return phase==='idle'?{state:'idle',supported:true,target:git(),review_token:'stop-reviewed'}:{state:phase,supported:true,id:'stop-job',message:'Backup completed.',backup:'rolling_1.db',git:{ok:true,code:'uploaded',message:'Database backup uploaded.'}};
  if(url==='/api/dev/stop/prepare'){
   const body=JSON.parse(options.body);if(body.pin!=='9042')return {status:403,body:{message:'Incorrect developer PIN.'}};
   phase='ready';return {state:'backup',id:'stop-job',message:'Saving backup…'};
  }
  if(url==='/api/dev/stop/confirm'){confirmVisible=d.querySelector('#editor-fields').textContent.includes('rolling_1.db')&&d.querySelector('#editor-fields').textContent.includes('Database backup uploaded.');phase='stopping';return {status:'success'}}
  if(url==='/api/dev/stop/cancel'){phase='cancelled';return {status:'success'}}
 });
 check(!!d.querySelector('.dev-taskbar [data-system-stop]'),'Stop app stays easy to reach in dashboard header');
 h.click('[data-system-stop]');await flush();
 check(d.querySelector('#stop-pin').type==='password'&&d.querySelector('#stop-sync-git').checked,'fresh PIN and configured Git upload required in stop review');
 check(d.querySelector('#editor-fields').textContent.includes('main → origin/main'),'Git destination shown before request');
 h.input('#stop-pin','wrong');h.click('[data-stop-prepare]');await flush();
 check(d.querySelector('#stop-error').textContent.includes('Incorrect')&&phase==='idle','incorrect PIN leaves app running');
 h.input('#stop-pin','9042');h.click('[data-stop-prepare]');await flush();
 check(!d.querySelector('#stop-pin'),'PIN removed from active stop markup');
 check(d.querySelector('#editor-fields').textContent.includes('rolling_1.db')&&readyTimers.length===1,'backup receipt shown during four-second pause');
 check(!requests.some(r=>r.url==='/api/dev/stop/confirm'),'no shutdown before visible receipt');
 await readyTimers[0]();await flush();check(confirmVisible,'local backup and Git success shown before shutdown acknowledgement');
 const submitted=JSON.parse(requests.filter(r=>r.url==='/api/dev/stop/prepare').at(-1).options.body);
 check(submitted.pin==='9042'&&submitted.sync_git&&submitted.review_token==='stop-reviewed','PIN and reviewed Git target are submitted explicitly');
 check(h.errors.length===0,'stop UI flow has no script errors');h.close();
 const external=await harness();external.handler(url=>url==='/api/dev/stop'?{state:'idle',supported:false,target:{available:false,message:'No Git'},review_token:'stop-review'}:undefined);
 external.click('[data-system-stop]');await flush();check(external.d.querySelector('[data-stop-prepare]').disabled,'external WSGI shutdown is disabled');external.close();
}
module.exports={harness,flush};
if(require.main===module)(async()=>{await entryAndShortcuts();await inventoryAndBackups();await gitFlows();await restoreFlows();await staleResponses();await responsiveContracts();await stopFlows();console.log(JSON.stringify({suite:'Developer system',passed:true,assertions}));})().catch(error=>{console.error(error);process.exitCode=1});

