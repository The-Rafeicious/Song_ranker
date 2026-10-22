/* Actual workbench/site/shared-preview modules with mocked HTTP and native media. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=name=>fs.readFileSync(path.join(__dirname,'../static/js',name),'utf8');
let assertions=0;const snapshots={};const check=(v,label)=>{assert.ok(v,label);assertions++};
async function flush(){for(let i=0;i<100;i++)await Promise.resolve()}
function fixture(){return {songs:Array.from({length:45},(_,i)=>({id:i+1,title:`Song ${String(i+1).padStart(2,'0')} <long name>`,
 album_id:i%2+1,artist_ids:[i%2+1],tag_ids:(i+1)%3?[(i%2)+1]:[],audio_url:(i+1)%4?'https://audio-ssl.itunes.apple.com/qa/'+(i+1)+'.m4a':'',
 elo_score:1200,matches_played:0,track_number:null})),artists:[{id:1,name:'Artist, One'},{id:2,name:'Another <artist>'}],
 albums:[{id:1,title:'Album <one>'},{id:2,title:'A song - Single'}],tags:[{id:1,name:'Bright',description:'Playful <description>'},{id:2,name:'Night',description:'Late listening'},{id:3,name:'Calm',description:'Quiet'}],
 history:[],tournaments:[],tournament_matches:[],tournament_entries:[],global_stats:{},special_modes:{}};}
async function harness(width=1280,view='tag_workbench',configure=()=>{},editing='bulk'){
 const dom=new JSDOM('<body data-page="dev" class="site-style-baseline"><main id="main"><div id="loading"></div></main><input id="volume-range" value=".5"><span id="volume-value"></span><button id="volume-btn"></button><div id="volume-panel" hidden></div><div id="preview-status" hidden></div><dialog id="editor"><form id="editor-form"><h2 id="editor-title"></h2><div id="editor-fields"></div><button type="button" id="editor-close">Close</button><button id="editor-submit" type="submit">Save</button></form></dialog><div id="toast" hidden></div></body>',{url:'http://localhost/dev/dashboard?view='+view,runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document,data=fixture(),requests=[],plays=[],errors=[],paused=new WeakMap();let handler=()=>undefined,playHook=null,nextToken=0;
 configure(data);w.innerWidth=width;w.scrollTo=()=>{};w.matchMedia=()=>({matches:true});w.HTMLElement.prototype.scrollIntoView=function(){};
 Object.defineProperty(w.HTMLMediaElement.prototype,'paused',{get(){return paused.get(this)!==false}});
 Object.defineProperty(w.HTMLMediaElement.prototype,'readyState',{get:()=>4});Object.defineProperty(w.HTMLMediaElement.prototype,'duration',{get:()=>30});
 w.HTMLMediaElement.prototype.play=function(){plays.push({id:this.id,url:this.getAttribute('src')});paused.set(this,false);this.dispatchEvent(new w.Event('play'));return playHook?playHook(this):Promise.resolve()};
 w.HTMLMediaElement.prototype.pause=function(){const was=paused.get(this)===false;paused.set(this,true);if(was)this.dispatchEvent(new w.Event('pause'))};w.HTMLMediaElement.prototype.load=function(){};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};
 w.addEventListener('error',e=>errors.push(e.message));
 const respond=(body,status=200)=>({ok:status<400,status,json:async()=>structuredClone(body)}),plans=new Map();
 function makeReview(body){
  const wanted=body.tag_ids.map(id=>({...data.tags.find(t=>t.id===id),key:'id:'+id}));
  const newNames=body.new_tags||[];for(const name of newNames)wanted.push({id:null,name,description:'',key:'new:'+name});
  const rows=body.song_ids.map(id=>{
   const s=data.songs.find(s=>s.id===id),before=s.tag_ids.map(id=>({...data.tags.find(t=>t.id===id),key:'id:'+id}));
   const after=body.action==='replace_tags'?wanted:body.action==='remove_tags'?before.filter(t=>!body.tag_ids.includes(t.id)):[...before,...wanted.filter(t=>!s.tag_ids.includes(t.id))];
   return {song_id:id,title:s.title,artist:data.artists.find(a=>a.id===s.artist_ids[0]).name,album:data.albums.find(a=>a.id===s.album_id).title,before,after,
    added:after.filter(t=>!before.some(x=>x.key===t.key)),removed:before.filter(t=>!after.some(x=>x.key===t.key))};
  });
  const token='review-'+(++nextToken),r={review_token:token,target_tags:wanted,rows,action:body.action,new_tags:newNames,selected_count:rows.length,
   changed_songs:rows.filter(r=>r.added.length||r.removed.length).length,unchanged_songs:rows.filter(r=>!r.added.length&&!r.removed.length).length,
   added_links:rows.reduce((n,r)=>n+r.added.length,0),removed_links:rows.reduce((n,r)=>n+r.removed.length,0)};
  plans.set(token,r);return r;
 }
 function save(body){
  const r=plans.get(body.review_token);if(r.saved)return {status:'success',already_matches:true,updated:0,created_tags:[],message:'Tags already match this review. Nothing changed.'};
  const created=[];for(const name of r.new_tags){const tag={id:10+data.tags.length,name,description:''};data.tags.push(tag);created.push(tag)}
  for(const row of r.rows)data.songs.find(s=>s.id===row.song_id).tag_ids=row.after.map(t=>t.id||created.find(x=>x.name===t.name).id);
  r.saved=true;return {status:'success',updated:r.changed_songs,created_tags:created,message:`Updated tags on ${r.changed_songs} songs. Backup saved.`};
 }
 w.fetch=async(url,options={})=>{
  url=String(url);requests.push({url,options});const intercepted=await handler(url,options);
  if(intercepted!==undefined)return typeof intercepted.status==='number'?respond(intercepted.body,intercepted.status):respond(intercepted);
  if(url==='/api/collection')return respond(data);
  if(url==='/api/dev/song-sources')return respond({songs:Object.fromEntries(data.songs.map(s=>[s.id,{status:'needs_link',content_label:'Unknown'}]))});
  if(url==='/api/dev/tags/review')return respond(makeReview(JSON.parse(options.body)));
  if(url==='/api/dev/tags/apply')return respond(save(JSON.parse(options.body)));
  if(url.startsWith('/api/previews/'))return respond({});
  if(url.startsWith('/api/dev/song-source/')){const id=Number(url.split('/').pop()),s=data.songs.find(s=>s.id===id);return respond({song:{...s,artist:'Artist, One',album:'Album',genres:'Bright'},fingerprint:'source-'+id,current:null,history:[]})}
  throw Error('Unexpected request '+url);
 };
 w.Overall={bindUI(){}};for(const file of ['ui.js','preview.js','special_modes.js','dev_catalog.js','dev_metadata.js','dev_records.js','dev_tags.js'])w.eval(source(file));
 const expose="window.testDev={setView:v=>{devView=v;renderDevView()},applyBulk,setBulk:ids=>{bulkSelection=new Set(ids);devView='bulk';renderDevView()}};window.DevTags?.bindUI(";
 await w.eval(source('site.js').replace('window.DevTags?.bindUI(',expose));await flush();if(view==='tag_workbench'&&editing==='bulk'){d.querySelector('[data-tags-mode="bulk"]')?.click();await flush()}
 const click=selector=>{const n=d.querySelector(selector);assert.ok(n,'missing '+selector);n.click();return n};
 const change=(selector,value)=>{const n=d.querySelector(selector);assert.ok(n,'missing '+selector);if(n.type==='checkbox')n.checked=value;else n.value=value;n.dispatchEvent(new w.Event('change',{bubbles:true}))};
 const input=(selector,value)=>{const n=d.querySelector(selector);assert.ok(n,'missing '+selector);n.value=value;n.dispatchEvent(new w.Event('input',{bubbles:true}))};
 const review=async()=>{d.querySelector('#tag-edit-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await flush()};
 const close=()=>{w.dispatchEvent(new w.Event('pagehide'));dom.window.close()};
 return {w,d,dom,data,requests,plays,errors,click,change,input,review,close,handler:fn=>handler=fn,playHook:fn=>playHook=fn,makeReview,save};
}
async function filterChecks(){
 const h=await harness(),{d}=h;
 check(d.querySelectorAll('[data-tag-song]').length===20,'song list paged at twenty');check(d.querySelector('#tag-count').textContent.startsWith('45 matching'),'queue count uses all songs');
 check(!!d.querySelector('.tag-bulk .tag-queue #tag-song-rows')&&!!d.querySelector('.tag-bulk .tag-editor #tag-now-playing'),'bulk queue and editor share the single bench layout');
 check(h.plays.length===0,'workbench never autoplays on entry');check(d.querySelectorAll('[data-tags-choice]').length===3,'all existing tags available');
 check(!d.querySelector('.tag-choice script'),'descriptions escaped');
 h.change('#tag-status','untagged');check(d.querySelectorAll('[data-tag-song]').length===15,'untagged filter exact');
 h.change('#tag-preview-filter','missing');check(d.querySelectorAll('[data-tag-song]').length===3,'missing previews combined with untagged');
 h.click('[data-tags-all-select]');check(d.querySelector('#tag-count').textContent.includes('3 selected'),'select all matches uses filtered IDs');
 h.click('[data-tags-reset-filters]');check(d.querySelector('#tag-count').textContent.includes('3 selected'),'clearing filters preserves deliberate selection');
 h.change('#tag-status','tagged');check(d.querySelector('#tag-count').textContent.includes('3 outside this filter'),'hidden selections explicitly counted');
 h.click('[data-tags-clear]');h.change('#tag-status','all');h.change('#tag-filter','1');check(d.querySelector('#tag-count').textContent.startsWith('15 matching'),'specific tag membership filter');
 h.change('#tag-match','missing');check(d.querySelector('#tag-count').textContent.startsWith('30 matching'),'missing-specific-tag filter');
 h.click('[data-tags-reset-filters]');h.change('#tag-artist','1');h.change('#tag-album','1');check(d.querySelector('#tag-count').textContent.startsWith('23 matching'),'artist/release filters use IDs');
 h.input('#tag-query','#45');check(d.querySelectorAll('[data-tag-song]').length===1,'exact ID usable in search');
 h.click('[data-tags-reset-filters]');h.click('[data-tags-page="1"]');check(d.querySelector('#tag-page-label').textContent==='Page 2 / 3','pagination advances');
 h.click('[data-tags-page-select]');check(d.querySelector('#tag-count').textContent.includes('20 selected'),'select page excludes other pages');
 h.change('#tag-selected-only',true);check(d.querySelector('#tag-count').textContent.startsWith('20 matching'),'selected-only view');check(h.errors.length===0,'filter flows have no script errors');h.close();
}
async function bulkChecks(){
 const h=await harness(),{d,requests}=h;h.click('[data-tags-all-select]');h.change('[data-tags-choice="3"]',true);h.input('#tag-new-names','Road trip');await h.review();
 const req=JSON.parse(requests.find(r=>r.url==='/api/dev/tags/review').options.body);
 check(req.song_ids.length===45&&req.tag_ids.join()==='3'&&req.new_tags[0]==='Road trip','review binds explicit entire selection/tags/new names');
 check(!requests.some(r=>r.url==='/api/dev/tags/apply'),'review does not apply');
 check(d.querySelector('#tag-review').textContent.includes('45 songs change'),'review summary covers all selected songs');
 check(d.querySelectorAll('.tag-review-row').length===20,'review itself paginated');h.click('[data-tags-review-page="1"]');check(d.querySelector('#tag-review').textContent.includes('2 / 3'),'all review pages accessible');
 check(d.querySelector('.tag-review-row .album').textContent.length>0,'review identifies the release as well as title/artist');
 h.input('#tag-choice-query','Quiet');check(d.querySelectorAll('[data-tags-choice]').length===1,'tag descriptions searchable');check(d.querySelector('#tag-review .tag-review'),'searching choices does not change reviewed targets');
 h.change('[data-tags-choice="3"]',false);check(!d.querySelector('.tag-review'),'changing a chosen tag invalidates review');
 h.change('[data-tags-choice="3"]',true);await h.review();h.click('[data-tags-apply]');h.click('[data-tags-apply]');await flush();
 check(requests.filter(r=>r.url==='/api/dev/tags/apply').length===1,'double save activation posts once');
 const body=JSON.parse(requests.find(r=>r.url==='/api/dev/tags/apply').options.body);check(Object.keys(body).join()==='review_token','apply only sends signed review identity');
 check(h.data.songs.every(s=>s.tag_ids.includes(3)),'bulk update refreshes memberships');check(d.querySelector('#tag-message').textContent.includes('Backup saved'),'saved outcome visible');
 check(!d.querySelector('.tag-review'),'saved review cleared');check(d.querySelector('#tag-count').textContent.includes('45 selected'),'selection retained for follow-up changes');h.close();
}
async function singleAndPreviewChecks(){
 const h=await harness(),{d,w,requests,plays}=h;h.change('#tag-sort','title');h.click('[data-tags-all-select]');
 w.DevTags.focusSong(1);await flush();check(d.querySelector('#tag-edit-title').textContent.includes('Song 01'),'single-song context explicit');
 check(d.querySelector('#tag-action').value==='replace_tags'&&d.querySelector('[data-tags-choice="1"]').checked,'single edit starts with actual tags');
 h.handler(url=>url==='/api/dev/song-quality/1'?{preview_bad:false,preview_note:'Review this clip'}:undefined);
 check(d.querySelector('[data-preview-quality]').dataset.previewQuality==='1','quality review follows the selected preview');
 h.click('[data-preview-quality]');await flush();
 check(d.querySelector('#editor').open&&d.querySelector('#editor-fields').textContent.includes('Review this clip'),'workbench opens the shared preview quality editor');
 d.querySelector('#editor').close();
 check(plays.length===1&&plays[0].url.startsWith('/api/previews/1?'),'Tag & listen uses shared Apple proxy/ownership');
 check(d.querySelector('[data-tags-player-toggle]').textContent==='Pause preview','play state visible');
 Object.defineProperty(d,'hidden',{configurable:true,value:true});d.dispatchEvent(new w.Event('visibilitychange'));check(!d.querySelector('#tag-audio').paused,'tab switching preserves workbench preview');Object.defineProperty(d,'hidden',{configurable:true,value:false});d.dispatchEvent(new w.Event('visibilitychange'));
 const original=d.querySelector('#tag-audio');h.change('[data-tags-choice="3"]',true);await h.review();
 check(JSON.parse(requests.find(r=>r.url==='/api/dev/tags/review').options.body).song_ids.join()==='1','single edit cannot accidentally affect bulk selection');
 check(d.querySelector('#tag-audio')===original&&!original.paused,'preview continues during choices and review');
 h.click('[data-tags-reset-filters]');check(d.querySelector('#tag-audio')===original&&!original.paused,'clearing list filters preserves the active preview');h.change('#tag-sort','title');
 h.click('[data-tags-apply]');await flush();check(d.querySelector('#tag-audio')===original&&!original.paused,'saving tags does not rebuild/interrupt audio');
 check(h.data.songs[0].tag_ids.includes(3),'single result refreshed');h.click('[data-tags-bulk-scope]');check(d.querySelector('#tag-edit-title').textContent==='Tags for selection','return to bulk selection');
 check(d.querySelector('#tag-count').textContent.includes('45 selected'),'single editing preserves bulk selection');
 h.click('[data-tags-player-toggle]');await flush();check(original.paused,'pause stops audio');h.click('[data-tags-player-toggle]');await flush();check(!original.paused,'manual resume works');
 h.click('[data-tags-preview-step="1"]');await flush();const after=d.querySelector('#tag-audio');check(d.querySelector('#tag-now-playing').textContent.includes('Song 02'),'next preview follows active sort/filter');
 check(d.querySelector('#tag-edit-title').textContent==='Tags for selection','preview stepping never silently changes edit target');
 h.click('[data-tags-stop]');check(after.paused,'stop also cancels shared media tails');
 const count=plays.length;w.DevTags.focusSong(4);await flush();check(d.querySelector('#tag-edit-title').textContent.includes('Song 04'),'missing preview song still editable');
 check(plays.length===count&&d.querySelector('[data-tags-player-toggle]').disabled,'missing preview never invents audio');check(d.querySelector('#tag-now-playing').textContent.includes('No preview URL'),'missing song cannot keep another track’s preview playing');
 w.testDev.setView('songs');check(after.paused&&!d.querySelector('#tag-audio'),'leaving workbench stops/releases owned player');
 check(requests.filter(r=>r.url==='/api/collection').length===2,'one shared catalogue refresh after save, no row-level data requests');check(h.errors.length===0,'preview/edit flows have no browser errors');h.close();
}
async function draftChecks(){
 const h=await harness(),{w,d}=h;w.DevTags.focusSong(1);await flush();h.change('[data-tags-choice="3"]',true);w.DevTags.focusSong(2);await flush();
 check(!d.querySelector('#tag-discard').hidden&&d.querySelector('#tag-edit-title').textContent.includes('Song 01'),'unsaved choices need review or explicit discard before switching song');
 h.click('[data-tags-discard-open]');await flush();check(d.querySelector('#tag-edit-title').textContent.includes('Song 02'),'explicit discard opens requested song');
 h.change('#tag-action','remove_tags');check(d.querySelector('#tag-new-names').disabled,'remove accepts existing tags only');
 h.click('[data-tags-reset-draft]');check(d.querySelector('#tag-action').value==='replace_tags','reset restores single-song membership choices');
 h.change('[data-tags-choice="2"]',false);await h.review();check(d.querySelector('#tag-review').textContent.includes('No tags'),'empty replacement is visible');
 check(d.querySelector('.tag-replace-note').textContent.includes('removes every tag'),'replace explains full removal scope');h.close();
 const bulk=await harness();bulk.click('[data-tags-all-select]');bulk.change('[data-tags-choice="3"]',true);bulk.w.DevTags.focusSong(1);await flush();bulk.click('[data-tags-discard-open]');await flush();bulk.click('[data-tags-bulk-scope]');
 check(!bulk.d.querySelector('[data-tags-choice="3"]').checked,'explicitly discarded bulk choices do not return when leaving single-song scope');bulk.close();
}
async function failureChecks(){
 const h=await harness(),{d,requests}=h;h.click('[data-tags-page-select]');h.change('[data-tags-choice="3"]',true);await h.review();
 h.handler(url=>url==='/api/dev/tags/apply'?{status:409,body:{message:'Tags changed. Review again.'}}:undefined);h.click('[data-tags-apply]');await flush();
 check(d.querySelector('#tag-message').textContent.includes('Review again'),'stale response remains visible');check(!d.querySelector('.tag-review'),'stale diff discarded');check(!d.querySelector('#tag-review-button').disabled,'fresh review available');
 h.handler(()=>undefined);await h.review();h.handler((url,opts)=>{
  if(url==='/api/dev/tags/apply'){h.save(JSON.parse(opts.body));h.handler(()=>undefined);throw Error('Lost response')}
 });h.click('[data-tags-apply]');await flush();check(d.querySelector('[data-tags-apply]')&&!d.querySelector('[data-tags-apply]').disabled,'lost response permits retry of the same signed review');
 h.click('[data-tags-apply]');await flush();check(d.querySelector('#tag-message').textContent.includes('already match'),'retry reconciles saved state without claiming another update');
 h.input('#tag-new-names','Night drive');await h.review();h.handler(url=>url==='/api/collection'?{status:503,body:{message:'Offline'}}:undefined);h.click('[data-tags-apply]');await flush();
 check(d.querySelector('#toast').textContent.includes('Reload to refresh'),'refresh failure distinguished from successful database save');check(!d.querySelector('.tag-review'),'committed review cannot be submitted again after refresh failure');
 check(requests.filter(r=>r.url==='/api/dev/tags/apply').length===4,'each intentional recovery call accounted for');h.close();
}
async function navigationChecks(){
 const h=await harness(),{d,w}=h;h.click('[data-tags-page-select]');h.change('[data-tags-choice="3"]',true);let resolve;
 h.handler((url,opts)=>url==='/api/dev/tags/review'?new Promise(r=>resolve=()=>r(h.makeReview(JSON.parse(opts.body)))):undefined);
 const waiting=h.review();await flush();w.testDev.setView('songs');resolve();await waiting;await flush();check(!d.querySelector('.tag-review')&&d.querySelector('#manage-rows'),'late review cannot replace another panel');
 w.testDev.setView('tag_workbench');check(!d.querySelector('.tag-review'),'returning does not activate a stale pending review');
 h.handler(()=>undefined);await h.review();let saveResolve;h.handler((url,opts)=>url==='/api/dev/tags/apply'?new Promise(r=>saveResolve=()=>r(h.save(JSON.parse(opts.body)))):undefined);
 h.click('[data-tags-apply]');await flush();w.testDev.setView('songs');saveResolve();await flush();check(d.querySelector('#manage-rows')&&!d.querySelector('#tag-song-rows'),'late save refresh keeps current navigation');
 check(d.querySelector('#toast').textContent.includes('Updated tags'),'completed off-panel save reports outcome');h.close();
}
async function recoveredNewTagChecks(){
 const h=await harness(),{d}=h;h.click('[data-tags-page-select]');h.change('#tag-action','replace_tags');h.input('#tag-new-names','Road trip');await h.review();
 h.handler((url,opts)=>{if(url==='/api/dev/tags/apply'){h.save(JSON.parse(opts.body));h.handler(()=>undefined);throw Error('Lost saved reply')}});
 h.click('[data-tags-apply]');await flush();h.click('[data-tags-apply]');await flush();
 const newTag=h.data.tags.find(t=>t.name==='Road trip');check(d.querySelector('[data-tags-choice="'+newTag.id+'"]').checked,'lost new-tag response recovers chosen canonical ID on retry');
 await h.review();check(d.querySelector('#tag-review').textContent.includes('0 songs change'),'repeat Replace retains recovered new tags');h.close();
}
async function mediaFailureChecks(){
 const h=await harness(),{w,d}=h;h.playHook(()=>Promise.reject(Object.assign(Error('blocked'),{name:'NotAllowedError'})));
 w.DevTags.focusSong(1);await flush();check(d.querySelector('#tag-message').textContent.includes('Press Play preview'),'autoplay rejection gives manual recovery');
 h.playHook(null);h.click('[data-tags-player-toggle]');await flush();check(!d.querySelector('#tag-audio').paused,'retry after browser rejection works');
 d.querySelector('#tag-audio').dispatchEvent(new w.Event('ended'));check(d.querySelector('#tag-now-playing').textContent.includes('finished'),'ended preview does not auto-advance');
 const count=h.plays.length;await flush();check(h.plays.length===count,'no loop/next play after end');h.close();
}
async function bulkBridgeCheck(){
 const h=await harness(),{w,d,requests}=h;w.testDev.setBulk([1,2]);
 check(![...d.querySelectorAll('#bulk-action option')].some(n=>n.value.includes('tags')),'bulk editor no longer duplicates tag editing');
 check(!!d.querySelector('#bulk-action option[value="review_sources"]'),'bulk source review replaces tag actions');
 check(!requests.some(r=>r.url==='/api/dev/bulk_songs'),'opening bulk editor does not change tags');h.close();
}
async function viewportChecks(width){
 const h=await harness(width),{d}=h;h.w.DevTags.focusSong(1);await flush();h.change('[data-tags-choice="3"]',true);await h.review();
 check(d.querySelector('[data-tags-apply]')&&d.querySelector('[data-tags-player-toggle]'),'save and playback controls at '+width);
 check(d.querySelector('#tag-edit-title').textContent.includes('Song 01'),'explicit edit scope at '+width);
 check(d.querySelectorAll('.tag-diff > div').length===2,'before/after both present at '+width);
 check(d.querySelector('#tag-query').type==='search'&&d.querySelector('#tag-action'),'filter/operation controls at '+width);
 snapshots[width]={songRows:d.querySelectorAll('[data-tag-song]').length,controls:d.querySelectorAll('.tag-workbench button').length,review:d.querySelector('#tag-review').textContent};h.close();
}

async function tagLimitChecks(){
 const h=await harness(390,'tag_workbench',data=>{
  data.tags=Array.from({length:11},(_,i)=>({id:i+1,name:'Tag '+(i+1),description:''}));
  data.songs[0].tag_ids=[1,2,3,4,5,6,7,8];data.songs[1].tag_ids=[1,2,3,4,5,6,7];
 });const {w,d}=h;
 w.DevTags.focusSong(1);await flush();
 check(d.querySelector('#tag-limit-status').textContent.includes('8 / 8'),'single song displays capacity');
 check(d.querySelector('[data-tags-choice="9"]').disabled,'ninth unchecked choice disabled');
 check(!d.querySelector('[data-tags-choice="8"]').disabled,'checked tags removable at capacity');
 h.change('[data-tags-choice="8"]',false);check(!d.querySelector('[data-tags-choice="9"]').disabled,'removal frees a slot');
 h.change('[data-tags-choice="9"]',true);check(d.querySelector('[data-tags-choice="10"]').disabled,'replacement fills freed slot');
 h.input('#tag-new-names','New');check(d.querySelector('#tag-review-button').disabled,'typed new tag cannot bypass capacity');
 const sent=h.requests.filter(r=>r.url==='/api/dev/tags/review').length;await h.review();
 check(h.requests.filter(r=>r.url==='/api/dev/tags/review').length===sent,'overflow blocked before review request');
 h.input('#tag-new-names','Tag 9, Ｔａｇ 9');check(!d.querySelector('#tag-review-button').disabled,'duplicate existing/new names count once');
 h.click('[data-tags-reset-draft]');h.change('#tag-action','remove_tags');check(!d.querySelector('[data-tags-choice="9"]').disabled,'remove allows arbitrary choices');
 h.change('[data-tags-choice="9"]',true);check(!d.querySelector('#tag-review-button').disabled,'removing more than eight targets is allowed');
 h.click('[data-tags-reset-draft]');h.click('[data-tags-bulk-scope]');h.change('#tag-sort','title');
 h.change('[data-tags-select="1"]',true);h.change('[data-tags-select="2"]',true);
 check(d.querySelector('[data-tags-choice="9"]').disabled,'mixed bulk add checks fullest song');
 check(!d.querySelector('[data-tags-choice="8"]').disabled,'bulk add existing tag on full song is allowed');
 h.change('[data-tags-choice="8"]',true);check(!d.querySelector('#tag-review-button').disabled,'union count permits filling only second song');
 h.change('#tag-action','replace_tags');check(!d.querySelector('[data-tags-choice="9"]').disabled,'replace capacity counts replacement rather than existing tags');
 w.testDev.setView('songs');h.click('[data-edit="songs"][data-id="1"]');await flush();
 check(d.querySelector('#tag-limit-edit').textContent.includes('8 / 8'),'song editor shows tag counter');
 check(d.querySelector('[data-pick-tag="9"]').disabled,'song editor disables ninth tag');
 h.change('[data-pick-tag="8"]',false);check(!d.querySelector('[data-pick-tag="9"]').disabled,'song editor removal frees slot');
 h.input('#field-tags',Array.from({length:9},(_,i)=>'Tag '+(i+1)).join(', '));
 check(!d.querySelector('#field-tags').checkValidity(),'typed ninth tag marks song field invalid');
 h.input('#field-tags','Tag 1, Tag 1');check(d.querySelector('#field-tags').checkValidity(),'duplicate text names count once');
 check(h.errors.length===0,'no script errors with limit controls');h.close();
}

module.exports={harness,flush};
if(require.main===module)(async()=>{await tagLimitChecks();await filterChecks();await bulkChecks();await singleAndPreviewChecks();await draftChecks();await failureChecks();await navigationChecks();await recoveredNewTagChecks();await mediaFailureChecks();await bulkBridgeCheck();for(const w of [320,360,390,430,568,768,1280])await viewportChecks(w);if(process.env.SNAPSHOT_OUTPUT)fs.writeFileSync(process.env.SNAPSHOT_OUTPUT,JSON.stringify(snapshots,null,2));console.log(assertions+' tag workbench assertions passed')})().catch(error=>{console.error(error);process.exitCode=1});


