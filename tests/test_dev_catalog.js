/* Real developer frame/module in jsdom; mocked HTTP/media, no live Apple writes. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const source=name=>fs.readFileSync(path.join(__dirname,'../static/js',name),'utf8');
let assertions=0;const snapshots={};const check=(v,label)=>{assert.ok(v,label);assertions++};
async function flush(){for(let i=0;i<90;i++)await Promise.resolve()}
const norm=s=>String(s).toLowerCase();
function offer(id,title,flag='explicit',matches=[]){return {title,artist:'Artist, One',album:'Source <album>',cover_url:'',audio_url:'source.m4a',track_number:1,
 release_date:'2020-04-05',genres:'Apple genre',disc_number:1,disc_count:1,source_track_number:1,source_token:'signed-'+id,
 source:{track_id:String(id),collection_id:'8001',storefront:'gb',explicitness:flag,content_label:({explicit:'Explicit',cleaned:'Cleaned',notExplicit:'Not explicit'})[flag]||'Unknown',duration_ms:213000,release_date:'2020-04-05',radio_hint:false,track_url:'https://music.apple.com/gb/song/'+id,original_album:'Source <album>'},library_matches:matches};}
function fixture(){return {songs:[{id:1,title:'Existing <song>',album_id:1,artist_ids:[1],tag_ids:[1],audio_url:'old.m4a',track_number:3,release_date:null,elo_score:1250,matches_played:3},
 {id:2,title:'Linked song',album_id:1,artist_ids:[1],tag_ids:[],audio_url:'',track_number:1,release_date:'2001-01-01',elo_score:1200,matches_played:0}],
 artists:[{id:1,name:'Artist, One',cover_url:''}],albums:[{id:1,title:'Local <album>',cover_url:'',release_date:'1998-02-03'}],tags:[{id:1,name:'Custom tag'}],history:[],tournaments:[],tournament_matches:[],tournament_entries:[],global_stats:{},special_modes:{}};}
async function harness(view='import',width=1280){
 const dom=new JSDOM('<body data-page="dev" class="site-style-baseline"><main id="main"><div id="loading"></div></main><input id="volume-range" value=".5"><span id="volume-value"></span><button id="volume-btn"></button><div id="volume-panel" hidden></div><dialog id="editor"><form id="editor-form"><h2 id="editor-title"></h2><div id="editor-fields"></div><div class="dialog-actions"><button type="button" id="editor-close">Close</button><button id="editor-submit" type="submit">Save</button></div></form></dialog><div id="toast" hidden></div></body>',{url:'http://localhost/dev/dashboard?view='+view,runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document;w.innerWidth=width;w.scrollTo=()=>{};w.matchMedia=()=>({matches:true});
 w.HTMLMediaElement.prototype.play=function(){plays.push(this.src);return Promise.resolve()};w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.load=function(){};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};
 const data=fixture(),requests=[],plays=[],errors=[];let handler=()=>undefined;
 const candidates=[offer(9001,'Existing <song>','unknown',[{song_id:1,title:'Existing <song>',album:'Local <album>',kind:'title_artist'}]),offer(9002,'Linked song','cleaned',[{song_id:2,title:'Linked song',album:'Local <album>',kind:'source_id'}]),...Array.from({length:25},(_,i)=>offer(9100+i,'New <'+i+'>',i%3===0?'notExplicit':i%3===1?'explicit':'cleaned'))];
 let summaries={1:{status:'needs_link',content_label:'Unknown',source:null,preview_matches:false},2:{status:'linked',content_label:'Cleaned',source:candidates[1].source,preview_matches:false}};
 const local=id=>{const s=data.songs.find(s=>s.id===id),a=data.albums.find(a=>a.id===s.album_id);return {...s,artist:'Artist, One',album:a?.title,genres:'Custom tag'}};
 w.addEventListener('error',e=>errors.push(e.message));
 const respond=(body,status=200)=>({ok:status<400,status,json:async()=>structuredClone(body)});
 w.fetch=async(url,options={})=>{
  url=String(url);requests.push({url,options});const result=await handler(url,options);if(result!==undefined)return typeof result.status==='number'?respond(result.body,result.status):respond(result);
  if(url==='/api/collection')return respond(data);
  if(url==='/api/dev/song-sources')return respond({songs:summaries});
  if(url.startsWith('/api/dev/search_apple'))return respond(candidates);
  if(url==='/api/dev/song-sources/bulk'){
   const body=JSON.parse(options.body),saved=body.changes.map(c=>{const row=candidates.find(r=>r.source_token===c.source_token);summaries[c.song_id]={status:'linked',content_label:row.source.content_label,source:row.source};return {song_id:c.song_id,source_id:100+c.song_id,source:row.source}});
   return respond({songs:saved,count:saved.length,message:saved.length+' song sources saved.'});
  }
  if(url.startsWith('/api/dev/song-source/')){
   const id=Number(url.split('/').pop());if(options.method==='POST'){
    const body=JSON.parse(options.body),row=candidates.find(r=>r.source_token===body.source_token);
    summaries[id]={status:'linked',content_label:row.source.content_label,source:row.source,preview_matches:false};
    if(body.refresh_metadata){const s=data.songs.find(s=>s.id===id);s.title=row.title;s.audio_url=row.audio_url;s.release_date=row.release_date}
    return respond({status:'success',song_id:id,source_id:100+id,source:row.source,message:'Source saved'});
   }
   return respond({song:local(id),fingerprint:'fingerprint-'+id,source_id:summaries[id]?.source_id||100+id,current:summaries[id]?.source||null,history:[]});
  }
  if(url.startsWith('/api/dev/single/')){
   const id=Number(url.split('/').pop());if(options.method==='POST'){data.albums.push({id:101,title:local(id).title+' - Single'});const s=data.songs.find(s=>s.id===id);s.album_id=101;s.track_number=null;s.release_date='1998-02-03';return respond({message:'Moved',album_cleanup:{reason:'Empty previous album removed.'}})}
   return respond({song_id:id,title:local(id).title,artist:'Artist, One',source_album:{title:'Local <album>'},destination_title:local(id).title+' - Single',release_date:'1998-02-03',release_date_origin:'album',already_single:false,cleanup_possible:false,fingerprint:'move-'+id});
  }
  if(url.startsWith('/api/dev/album-tracks/'))return respond({album:data.albums[0],songs:[local(2),local(1)].map(s=>({...s,source_summary:summaries[s.id]}))});
  if(url==='/api/dev/add_song'){
   const body=JSON.parse(options.body),row=candidates.find(r=>r.source_token===body.source_token),id=10+data.songs.length;
   data.songs.push({id,title:row.title,album_id:1,artist_ids:[1],tag_ids:[1],elo_score:1200,matches_played:0,audio_url:row.audio_url,release_date:row.release_date});summaries[id]={status:'linked',content_label:row.source.content_label,source:row.source,preview_matches:true};return respond({status:'success',song_id:id,source_id:100+id,source:row.source,message:'Added'});
  }
  throw Error('Unexpected request '+url);
 };
 require('./dev_fixture.cjs')(w,view);
 w.Overall={bindUI(){}};w.eval(source('ui.js'));w.eval(source('dev_workspace.js'));w.eval(source('special_modes.js'));w.eval(source('dev_catalog.js'));w.eval(source('dev_metadata.js'));w.eval(source('dev_records.js'));
 await w.eval(source('site.js').replace('window.DevCatalog?.bindUI(',"window.testDev={refreshData,setView:v=>{devView=v;renderDevView()},editRecord};window.DevCatalog?.bindUI("));await flush();
 const click=s=>{const n=d.querySelector(s);assert.ok(n,'missing '+s);n.click();return n};
 const change=(selector,value)=>{const n=d.querySelector(selector);n.checked=value;n.dispatchEvent(new w.Event('change',{bubbles:true}))};
 const search=async(q='Artist query')=>{d.querySelector('#apple-query').value=q;await w.DevCatalog.search();await flush()};
 return {dom,w,d,data,requests,plays,errors,candidates,click,change,search,handler:fn=>handler=fn};
}
async function importChecks(){
 const h=await harness(),{w,d,requests}=h;await h.search();
 check(d.querySelector('#apple-country').value==='gb','GB store default');
 check(d.querySelectorAll('.catalog-card').length===20,'new results paged at twenty');
 check(d.querySelector('#apple-result-count').textContent.includes('2 library matches hidden'),'known and possible matches hidden with a count');
 check(!d.querySelector('[data-catalog-track="9001"]'),'unverified matching title hidden without becoming a source identity');
 h.click('[data-catalog-more]');check(d.querySelectorAll('.catalog-card').length===25,'more shows remaining new tracks');
 h.change('#show-apple-matches',true);check(d.querySelector('[data-catalog-track="9001"]').textContent.includes('version unverified'),'possible match labelled unverified');
 check(d.querySelector('[data-catalog-track="9002"]').textContent.includes('In library'),'exact source identity marked in library');
 check(!d.querySelector('[data-catalog-track="9002"] [data-import]'),'known Apple identity cannot add a duplicate');
 check(d.querySelector('[data-catalog-track="9100"]').textContent.includes('Not explicit'),'notExplicit remains its own label');
 check(!d.querySelector('.catalog-copy script'),'titles safely escaped');
 h.change('#show-apple-matches',false);h.change('#apple-as-single',true);h.change('[data-pick-tag="1"]',true);
 const id=Number(d.querySelector('[data-catalog-track="9100"] [data-import]').dataset.import);
 await Promise.all([w.DevCatalog.add(id),w.DevCatalog.add(id)]);await flush();
 const added=requests.filter(r=>r.url==='/api/dev/add_song');check(added.length===1,'double activation sends one add');
 const body=JSON.parse(added[0].options.body);check(body.source_token==='signed-9100'&&body.import_source==='apple'&&!('title' in body),'save uses a signed, explicitly marked Apple offer');
 check(body.genres==='Custom tag'&&body.placement==='single','selected tags and Single placement reach server');
 check(d.querySelector('#apple-query').value==='Artist query','search stays after add');
 check(!d.querySelector('[data-catalog-track="9100"]'),'added track hidden from new suggestions');
 check(requests.filter(r=>r.url==='/api/dev/song-sources').length===2,'source summaries fetched in batches, not per row');
 h.change('#keep-import',false);const next=Number(d.querySelector('[data-import]').dataset.import);await w.DevCatalog.add(next);await flush();
 check(d.querySelector('#apple-query').value===''&&!d.querySelector('.catalog-card'),'optional reset clears search after add');
 h.dom.window.close();
}
async function sourceChecks(){
 const h=await harness(),{w,d,requests}=h;await h.search();h.change('#show-apple-matches',true);
 h.click('[data-catalog-track="9001"] [data-catalog-review]');check(d.querySelector('#editor').open,'release review opens');
 check(d.querySelector('#editor-fields').textContent.includes('Title/artist match only'),'review does not claim a verified legacy match');
 h.click('[data-catalog-link="1"]');await flush();
 check(d.querySelector('#editor-fields').textContent.includes('Apple source unknown'),'legacy source stays unknown before saving');
 check(!d.querySelector('#catalog-refresh-source').checked&&d.querySelector('#catalog-use-album').disabled,'source-only save is default');
 h.change('#catalog-refresh-source',true);check(!d.querySelector('#catalog-use-album').disabled,'source album is a separate explicit option');
 h.change('#catalog-use-album',true);h.change('#catalog-refresh-source',false);check(!d.querySelector('#catalog-use-album').checked,'disabling refresh clears album override');
 h.click('[data-catalog-save-source]');await flush();
 const request=requests.find(r=>r.url==='/api/dev/song-source/1'&&r.options.method==='POST'),body=JSON.parse(request.options.body);
 check(body.fingerprint==='fingerprint-1'&&!body.refresh_metadata&&!body.use_source_album,'source-only post is bound to reviewed metadata');
 check(h.data.songs[0].title==='Existing <song>','source-only flow retains local title');
 check(!d.querySelector('#editor').open,'saved source closes its dialog');
 await w.DevCatalog.openSource(1);d.querySelector('#catalog-source-query').focus();
 d.querySelector('#editor-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await flush();
 check(requests.filter(r=>r.url.startsWith('/api/dev/search_apple')).length===2,'Enter in source search uses source lookup, not generic editor save');
 h.click('[data-catalog-source-select="2"]');h.change('#catalog-refresh-source',true);h.change('#catalog-use-album',true);
 h.handler((url,opts)=>url==='/api/dev/song-source/1'&&opts.method==='POST'?{status:409,body:{message:'Song changed. Review again.'}}:undefined);
 h.click('[data-catalog-save-source]');await flush();
 check(d.querySelector('#editor').open&&!d.querySelector('#editor-error').hidden,'stale write leaves the review open with an error');
 check(!d.querySelector('[data-catalog-save-source]').disabled,'failed write can be reviewed/retried');
 const refreshBody=JSON.parse(requests.filter(r=>r.url==='/api/dev/song-source/1'&&r.options.method==='POST').at(-1).options.body);check(refreshBody.refresh_metadata&&refreshBody.use_source_album,'refresh and album placement require the two explicit options');
 check(h.errors.length===0,'source form has no browser errors');h.dom.window.close();
}
async function navigationChecks(){
 const h=await harness(),{w,d}=h;let resolve;
 h.handler(url=>url.startsWith('/api/dev/search_apple')?new Promise(r=>resolve=r):undefined);
 d.querySelector('#apple-query').value='pending';const job=w.DevCatalog.search();await flush();
 w.testDev.setView('songs');w.testDev.setView('import');resolve(h.candidates);await job;await flush();
 check(!d.querySelector('#apple-search button').disabled&&d.querySelector('.catalog-card'),'returning during lookup finishes on the current panel');
 check(d.querySelector('#apple-query').value==='pending','lookup query retained across panels');
 let sourceResolve;h.handler(url=>url==='/api/dev/song-source/1'?new Promise(r=>sourceResolve=r):undefined);
 const opening=w.DevCatalog.openSource(1);await flush();await w.DevCatalog.openSingle(1);
 sourceResolve({song:{title:'Old response'},fingerprint:'old',history:[],current:null});await opening;await flush();
 check(d.querySelector('#editor-title').textContent==='Move to Single'&&d.querySelector('[data-catalog-save-single]'),'late source reply cannot replace a newer review');
 d.querySelector('#editor').close();check(!d.querySelector('#editor').open,'review close works');h.dom.window.close();
}
async function addNavigationCheck(){
 const h=await harness(),{w,d}=h;await h.search();let resolve;
 h.handler((url,options)=>url==='/api/dev/add_song'?new Promise(r=>resolve=r):undefined);
 const id=Number(d.querySelector('[data-import]').dataset.import),job=w.DevCatalog.add(id);await flush();
 await w.DevCatalog.openSource(1);check(d.querySelector('#editor').open,'another review can open during a saved import');
 resolve({status:'success',message:'Added',source_id:123,source:h.candidates.find(r=>r.id===id)?.source||h.candidates[2].source});await job;await flush();
 check(d.querySelector('#editor').open&&d.querySelector('#editor-title').textContent==='Apple source','finishing an older add cannot close the newer source review');h.dom.window.close();
}
async function sourcePersistenceChecks(){
 const h=await harness(),{w,d,requests}=h;
 h.candidates[2].source_token='';await h.search();
 await w.DevCatalog.add(3);await flush();
 check(!requests.some(r=>r.url==='/api/dev/add_song'),'missing source offer cannot submit a metadata-only import');
 check(d.querySelector('#toast').textContent.includes('source details are missing'),'missing offer asks for a fresh search');
 h.candidates[2].source_token='signed-9100';await h.search();
 h.handler(url=>url==='/api/dev/add_song'?{status:'success',song_id:999,message:'Added'}:undefined);
 await w.DevCatalog.add(3);await flush();
 check(d.querySelector('#toast').textContent.includes('could not be confirmed'),'a response without a saved source cannot claim a confirmed Apple add');
 check(d.querySelector('[data-catalog-track="9100"] [data-import]'),'unconfirmed receipt does not hide the result as linked');
 h.dom.window.close();
 const table=await harness('songs'),t=table.d;
 check(!t.querySelector('[data-sort="apple_track_id"]'),'Apple identity columns start optional to keep the table compact');
 table.change('[data-visible="apple_track_id"]',true);table.change('[data-visible="apple_track_url"]',true);await flush();
 check(t.querySelector('[data-sort="apple_track_id"]')&&t.querySelector('[data-sort="apple_track_url"]'),'saved identity and link columns are available');
 check(t.querySelector('#manage-rows').textContent.includes('9002'),'Apple ID uses saved source facts');
 check(t.querySelector('#manage-rows a[href="https://music.apple.com/gb/song/9002"]')?.rel.includes('noopener'),'Apple link opens the saved recording safely');
 table.click('[data-table-panel="filters"]');
 t.querySelector('#table-filter-field').value='apple_track_id';t.querySelector('#table-filter-field').dispatchEvent(new table.w.Event('change',{bubbles:true}));
 t.querySelector('#table-filter-value').value='9002';t.querySelector('#table-filter-form').dispatchEvent(new table.w.Event('submit',{bubbles:true,cancelable:true}));
 check(t.querySelectorAll('#manage-rows tr').length===1,'source ID participates in typed field filters');
 check(t.querySelector('#table-filters').hidden,'applying a field filter closes its panel');
 check(t.querySelector('[data-remove-table-filter="apple_track_id"]'),'active field filter has a removable chip');
 check(t.querySelector('#table-order')&&t.querySelector('[data-table-reset-order]'),'shared order controls stay available');
 table.dom.window.close();
}
async function sourceRefreshChecks(){
 const h=await harness('songs'),{w,d}=h;let resolve;
 h.handler(url=>url==='/api/dev/song-sources'?new Promise(r=>resolve=r):undefined);
 w.testDev.editRecord('songs',1);await flush();d.querySelector('[name="title"]').value='Unsaved title';
 resolve({songs:{1:{status:'linked',content_label:'Explicit',source:h.candidates[2].source,preview_matches:false}}});await flush();
 check(d.querySelector('.catalog-source-summary').textContent.includes('9100'),'open Edit source summary updates after its read finishes');
 check(d.querySelector('[name="title"]').value==='Unsaved title','source refresh preserves unsaved form fields');
 h.dom.window.close();
 const saved=await harness(),sd=saved.d,sw=saved.w;
 await sw.DevCatalog.openSource(1,saved.candidates[2]);
 saved.handler(url=>url==='/api/dev/song-sources'?{status:500,body:{message:'Injected refresh error'}}:undefined);
 saved.click('[data-catalog-save-source]');await flush();
 check(!sd.querySelector('#editor').open,'confirmed save closes despite a later refresh error');
 check(sd.querySelector('#toast').textContent.startsWith('Source saved.'),'refresh failure is reported as a saved source with a refresh notice');
 check(sw.DevCatalog.sourceText(1)==='Linked'&&sw.DevCatalog.sourceValue(1,'track_id')==='9100','save receipt updates cached source despite failed batch refresh');
 sw.testDev.editRecord('songs',1);await flush();
 check(sd.querySelector('.catalog-source-summary').textContent.includes('9100'),'Edit uses the confirmed source rather than stale unknown state');
 saved.dom.window.close();
}
async function bulkSourceChecks(){
 const h=await harness('bulk'),{w,d,requests}=h;
 const select=(id,value)=>{const n=d.querySelector(id);n.value=value;n.dispatchEvent(new w.Event('change',{bubbles:true}))};
 check(!d.querySelector('#bulk-filter-tag')&&!d.querySelector('#bulk-action option[value="add_tags"]'),'tags removed from bulk editor');
 select('#bulk-filter-source','missing');check(d.querySelectorAll('[data-bulk-song]').length===1,'missing source filter');
 h.click('[data-bulk-all]');select('#bulk-action','review_sources');h.click('[data-bulk-apply]');await flush();
 check(d.querySelector('.catalog-batch-bar').textContent.includes('Song 1 of 1'),'bulk selection opens a source queue');
 check(d.querySelectorAll('#catalog-source-offers > .catalog-match').length===5,'first five source choices');
 const extra=d.querySelector('.catalog-more-sources');check(extra&&!extra.open&&extra.querySelectorAll('.catalog-match').length===10,'ten extra choices collapsed');
 check(d.querySelectorAll('[data-catalog-source-select]').length===15,'source choices capped at fifteen');
 check(!d.querySelector('[data-catalog-source-select="15"]'),'additional versions require a refined search');
 h.click('[data-catalog-source-select="2"]');check(!d.querySelector('#catalog-source-choices').open,'choosing collapses other recordings');check(d.activeElement.hasAttribute('data-source-batch-choose'),'confirmation receives keyboard focus');check(d.querySelector('.catalog-selected').textContent.includes('✓ Selected recording'),'selection feedback is visible');check(d.querySelector('[data-catalog-source-select="2"]').getAttribute('aria-pressed')==='true','selected version remains marked when reopened');check(!requests.some(r=>r.url==='/api/dev/song-sources/bulk'),'choosing never saves without confirmation');check(!d.querySelector('#catalog-refresh-source'),'bulk changes only source identity');
 h.click('[data-source-batch-choose]');await flush();
 check(d.querySelector('#editor-title').textContent==='Review source group','last choice opens group review');
 check(!requests.some(r=>r.url==='/api/dev/song-sources/bulk'),'draft choices are not saved early');
 d.querySelector('#editor').close();h.click('[data-bulk-apply]');await flush();
 check(!!d.querySelector('[data-source-batch-save]'),'closing and reopening resumes reviewed draft');
 h.handler((url)=>url==='/api/dev/song-sources/bulk'?{status:409,body:{message:'Song changed; nothing saved'}}:undefined);
 h.click('[data-source-batch-save]');await flush();
 check(d.querySelector('#editor-error').textContent.includes('nothing saved')&&!d.querySelector('[data-source-batch-save]').disabled,'failed group save keeps draft and enables retry');
 h.handler(()=>undefined);h.click('[data-source-batch-save]');await flush();
 const post=requests.filter(r=>r.url==='/api/dev/song-sources/bulk').at(-1),body=JSON.parse(post.options.body);
 check(body.changes.length===1&&body.changes[0].fingerprint==='fingerprint-1'&&body.changes[0].source_token==='signed-9100','group save binds each manually reviewed offer');
 check(!d.querySelector('#editor').open&&w.DevCatalog.sourceValue(1,'track_id')==='9100','successful group save refreshes sources and closes');
 check(h.data.songs[0].title==='Existing <song>'&&h.data.songs[0].audio_url==='old.m4a','group source edit keeps local metadata');
 select('#bulk-filter-source','linked');check(d.querySelectorAll('[data-bulk-song]').length===2,'linked sources can be reviewed for mislabelling');
 await w.DevCatalog.startSourceBatch([1,2]);await flush();h.click('[data-catalog-source-select="3"]');h.click('[data-source-batch-choose]');await flush();
 check(d.querySelector('.catalog-batch-bar').textContent.includes('Song 2 of 2'),'choose automatically advances to next song');
 h.click('[data-catalog-source-select="3"]');h.click('[data-source-batch-choose]');await flush();
 check(d.querySelector('#editor-error').textContent.includes('already chosen'),'same recording cannot be staged twice');
 h.click('[data-source-batch-skip]');await flush();
 check(d.querySelector('#editor-fields').textContent.includes('1 chosen · 1 unchanged'),'skip leaves a source unchanged');
 h.click('[data-source-batch-edit="1"]');await flush();h.click('[data-source-batch-skip]');await flush();h.click('[data-source-batch-review]');await flush();
 check(d.querySelector('[data-source-batch-save]').disabled,'skipping a previously chosen source removes it from changes');
 h.click('[data-source-batch-discard]');await flush();check(!d.querySelector('#editor').open,'discard removes draft');
 const searches=requests.filter(r=>r.url.startsWith('/api/dev/search_apple')).length;
 await w.DevCatalog.startSourceBatch([1,2],'https://music.apple.com/gb/album/test/8001');await flush();
 check(d.querySelector('[data-catalog-source-select="0"]').closest('.catalog-match').textContent.includes('Existing <song>'),'release queue puts the current song title first');
 check(!d.querySelector('[data-source-batch-choose]'),'release matches are never auto-selected');
 h.click('[data-catalog-source-select="0"]');h.click('[data-source-batch-choose]');await flush();
 check(d.querySelector('[data-catalog-source-select="0"]').closest('.catalog-match').textContent.includes('Linked song'),'release list is reordered for the next song');
 check(requests.filter(r=>r.url.startsWith('/api/dev/search_apple')).length===searches+1,'one release lookup reused across the group');
 h.click('[data-source-batch-review]');h.click('[data-source-batch-discard]');await flush();
 check(h.errors.length===0,'bulk source flow has no browser errors');h.dom.window.close();
}
async function catalogueInteractionChecks(){
 const h=await harness('songs',390),{w,d,data}=h;
 for(let id=3;id<=72;id++)data.songs.push({id,title:'Song '+id,album_id:1,artist_ids:[1],tag_ids:[],audio_url:'',track_number:id,elo_score:1200+id,matches_played:0});
 await w.testDev.refreshData();w.testDev.setView('songs');
 check(d.querySelectorAll('#manage-rows tr').length===30,'default page has thirty rows');
 const change=(id,value)=>{const n=d.querySelector(id);n.value=value;n.dispatchEvent(new w.Event('change',{bubbles:true}))};
 change('#table-page-size','15');check(d.querySelectorAll('#manage-rows tr').length===15,'row count is adjustable');
 h.click('[data-table-next]');check(d.querySelector('.table-count').textContent.includes('16–30'),'both pagers use the selected row count');
 change('#table-page','5');check(d.querySelector('.table-count').textContent.includes('61–72'),'jump directly to a page');
 h.click('[data-table-panel="filters"]');change('#table-filter-field','id');change('#table-filter-op','gte');d.querySelector('#table-filter-value').value='70';
 d.querySelector('#table-filter-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 check(d.querySelectorAll('#manage-rows tr').length===3,'numeric field ranges apply');
 h.click('[data-remove-table-filter="id"]');check(d.querySelectorAll('#manage-rows tr').length===15,'removing a chip restores the page size');
 h.click('[data-table-panel="filters"]');change('#table-filter-field','release_date');change('#table-filter-op','missing');
 check(d.querySelector('#table-filter-value').disabled,'blank filters need no typed value');d.querySelector('#table-filter-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 check(!d.querySelector('#manage-rows').textContent.includes('Linked song'),'blank date filter excludes a filled date');
 h.click('[data-table-clear]');
 h.click('[data-table-panel="columns"]');const column=d.querySelector('[data-visible="preview"]');column.focus();column.click();
 check(d.activeElement?.dataset.visible==='preview','changing a column retains keyboard focus for rapid selection');
 h.click('[data-table-panel="columns"]');
 const more=d.querySelector('[data-record-more]');more.click();
 check(d.querySelector('#dev-record-menu').parentElement===d.body,'row menu escapes all table clipping');
 d.dispatchEvent(new w.Event('scroll'));check(!!d.querySelector('#dev-record-menu'),'delayed pre-open scroll event keeps the menu open');
 const items=[...d.querySelectorAll('#dev-record-menu [role=menuitem]')];check(d.activeElement===items[0],'menu opens at first action');
 items[0].dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));check(d.activeElement===items[1],'menu has arrow navigation');
 items[1].dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check(!d.querySelector('#dev-record-menu')&&d.activeElement===more,'Escape closes the menu and restores focus');
 more.click();w.scrollY=50;d.dispatchEvent(new w.Event('scroll'));check(!d.querySelector('#dev-record-menu'),'actual page scrolling dismisses stale menu geometry');w.scrollY=0;
 more.click();w.dispatchEvent(new w.Event('resize'));check(!d.querySelector('#dev-record-menu'),'resize dismisses stale popup geometry');
 w.testDev.setView('albums');w.testDev.setView('songs');check(d.querySelector('#table-page-size').value==='15','page size persists per entity');
 check(h.errors.length===0,'table operations have no runtime errors');h.dom.window.close();
}
async function moveAndTableChecks(width){
 const h=await harness('songs',width),{w,d}=h;
 h.click('[data-record-more="songs"][data-id="1"]');
 check(d.querySelector('#dev-record-menu [data-catalog-source="1"]')&&d.querySelector('[data-catalog-single="1"]'),'song actions present at '+width);
 h.change('#missing-apple-only',true);check(d.querySelectorAll('#manage-rows tr').length===1&&d.querySelector('[data-record-more="songs"][data-id="1"]'),'needs-link filter uses source facts at '+width);
 w.testDev.editRecord('songs',1);check(d.querySelector('label[for="field-release_date"]').textContent==='Song release date','per-song date editor at '+width);
 d.querySelector('#editor').close();await w.DevCatalog.openSingle(1);
 check(d.querySelector('#editor-fields').textContent.includes('1998-02-03')&&d.querySelector('#editor-fields').textContent.includes('carried from album'),'date carry explained before moving at '+width);
 check(d.querySelector('#catalog-remove-empty').checked,'safe empty cleanup offered at '+width);
 h.click('[data-catalog-save-single]');await flush();
 const request=h.requests.find(r=>r.url==='/api/dev/single/1'&&r.options.method==='POST'),body=JSON.parse(request.options.body);
 check(body.fingerprint==='move-1'&&body.remove_empty_album===true,'move binds reviewed plan at '+width);
 check(h.data.songs[0].id===1&&h.data.songs[0].album_id===101&&h.data.songs[0].release_date==='1998-02-03','same song ID/date after move at '+width);
 w.testDev.setView('albums');h.click('[data-record-more="albums"][data-id="1"]');check(d.querySelector('[data-catalog-album="1"]'),'quick album inspection action at '+width);
 await w.DevCatalog.openAlbum(1);check(d.querySelectorAll('[data-catalog-preview]').length===2,'all album tracks shown at '+width);
 check(d.querySelector('#field-disc_number')===null,'album inspection stays read-only at '+width);
 check(d.querySelector('[data-catalog-move-album="1"]'),'direct combine-disc workflow at '+width);
 check(d.querySelector('[data-edit="songs"][data-id="2"]'),'disc editor reachable from album at '+width);
 check(d.querySelector('[data-catalog-preview="2"]').disabled,'missing preview disabled at '+width);
 h.click('[data-catalog-preview="1"]');await flush();check(h.plays.length===1,'preview starts only on explicit click at '+width);
 snapshots['developer-album-'+width]=d.documentElement.outerHTML;
 check(h.errors.length===0,'no browser errors at '+width);h.dom.window.close();
}

async function albumImportChecks(){
 const h=await harness(),{w,d,requests}=h;
 await h.search('https://music.apple.com/us/album/example/8001');
 check(d.querySelector('#editor-title').textContent==='Add album','album link opens checklist');check(d.querySelectorAll('#editor-error').length===1,'album dialog has one error owner');
 check(!d.querySelector('[data-album-import-id="1"]').checked&&!d.querySelector('[data-album-import-id="2"]').checked,'library matches start unchecked');
 d.querySelectorAll('[data-album-import-id]').forEach(n=>n.checked=false);
 h.click('[data-album-import-save]');await flush();
 check(!requests.some(r=>r.url==='/api/dev/add_song'),'empty checklist sends no save');
 check(d.querySelector('#editor-error').textContent.includes('Select at least one'),'empty checklist shows an error');
 h.change('[data-album-import-id="3"]',true);h.change('[data-album-import-id="5"]',true);
 h.click('[data-album-import-save]');h.click('[data-album-import-save]');await flush();
 const posts=requests.filter(r=>r.url==='/api/dev/add_song').map(r=>JSON.parse(r.options.body));
 check(posts.length===2&&posts[0].source_token==='signed-9100'&&posts[1].source_token==='signed-9102','button saves only checked tracks once');
 check(posts.every(p=>p.placement==='keep'),'album imports keep album placement');
 check(h.data.songs.some(s=>s.title==='New <0>')&&h.data.songs.some(s=>s.title==='New <2>'),'selected songs reach the catalogue');
 check(!d.querySelector('#editor').open,'successful album import closes popup');
 check(d.querySelector('#toast').textContent.includes('2 of 2 songs saved'),'successful import confirms saved count');
 check(h.errors.length===0,'album click has no browser errors');h.dom.window.close();

 const retry=await harness(),rd=retry.d;await retry.search('https://music.apple.com/us/album/example/8001');
 rd.querySelectorAll('[data-album-import-id]').forEach(n=>n.checked=['3','4'].includes(n.dataset.albumImportId));
 retry.handler((url,opts)=>url==='/api/dev/add_song'&&JSON.parse(opts.body).source_token==='signed-9101'?{status:409,body:{message:'Track position conflict'}}:undefined);
 retry.click('[data-album-import-save]');await flush();
 check(rd.querySelector('#editor').open&&rd.querySelector('#editor-error').textContent.includes('1 of 2 songs saved'),'partial failure keeps popup with saved count');
 check(rd.querySelector('[data-album-import-id="3"]').disabled&&!rd.querySelector('[data-album-import-id="3"]').checked,'saved track disabled and unchecked for retry');
 check(!rd.querySelector('[data-album-import-id="4"]').disabled&&!rd.querySelector('[data-album-import-save]').disabled,'failed track and button enabled for retry');
 retry.handler(()=>undefined);retry.click('[data-album-import-save]');await flush();
 const retryPosts=retry.requests.filter(r=>r.url==='/api/dev/add_song').map(r=>JSON.parse(r.options.body));
 check(retryPosts.length===3&&retryPosts[2].source_token==='signed-9101','retry sends only failed track');
 check(!rd.querySelector('#editor').open,'successful retry closes popup');retry.dom.window.close();
}


async function polishChecks(){
 const h=await harness('bulk'),{w,d}=h;
 for(let id=3;id<=80;id++)h.data.songs.push({...h.data.songs[0],id,title:'Extra '+id});
 await w.testDev.refreshData();w.testDev.setView('bulk');
 check(d.querySelectorAll('[data-bulk-song]').length===50,'bulk selection starts at fifty rows');
 check(d.querySelector('[data-bulk-apply]').disabled,'bulk action disabled without selection');
 h.click('[data-bulk-more]');check(d.querySelectorAll('[data-bulk-song]').length===80,'more exposes remaining bulk rows');
 h.change('[data-bulk-song="1"]',true);check(!d.querySelector('[data-bulk-apply]').disabled,'selection enables bulk action');
 const q=d.querySelector('#bulk-query');q.value='Extra 80';q.dispatchEvent(new w.Event('input',{bubbles:true}));
 check(d.querySelector('#bulk-count').textContent.includes('1 selected outside filters'),'hidden selection count is explicit');
 w.testDev.editRecord('songs',1);
 h.handler((url,opts)=>url==='/api/dev/edit_song/1'?{status:'success',message:'Saved'}:url==='/api/collection'?{status:500,body:{message:'Refresh failed'}}:undefined);
 d.querySelector('#editor-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await flush();
 check(!d.querySelector('#editor').open&&d.querySelector('#toast').textContent.startsWith('Saved.'),'confirmed edit is distinguished from refresh failure');
 check(h.errors.length===0,'polished bulk/editor flows have no browser errors');h.dom.window.close();
}

async function activeSaveNavigationChecks(){
 const h=await harness('songs'),{w,d}=h;let finish;
 w.testDev.editRecord('songs',1);
 h.handler(url=>url==='/api/dev/edit_song/1'?new Promise(resolve=>finish=resolve):undefined);
 d.querySelector('#editor-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await flush();
 check(d.querySelector('#editor-form').dataset.saving==='true','record save is locked until its request and refresh finish');
 h.click('#dev-page-menu [data-dev="library"]');h.click('#editor-close');
 check(w.location.pathname==='/dev/library/songs'&&d.querySelector('#editor').open,'pending record save cannot navigate or close');
 check(d.querySelector('#dev-unsaved').hidden,'in-flight save cannot be discarded');
 finish({status:'success',message:'Saved'});await flush();
 check(!d.querySelector('#editor-form').dataset.saving&&!d.querySelector('#editor').open,'confirmed record save releases the navigation lock');
 h.handler(()=>undefined);await w.DevCatalog.openSingle(1);let complete;
 h.handler(url=>url==='/api/dev/single/1'?new Promise(resolve=>complete=resolve):undefined);h.click('[data-catalog-save-single]');await flush();
 check(w.DevCatalog.isBusy(),'catalogue write exposes its active lock');h.click('#dev-page-menu [data-dev="library"]');h.click('#editor-close');
 check(w.location.pathname==='/dev/library/songs'&&d.querySelector('#editor').open,'pending catalogue write cannot navigate or close');
 complete({message:'Moved',album_cleanup:{reason:'Previous album retained'}});await flush();
 check(!w.DevCatalog.isBusy(),'completed catalogue write releases its lock');h.click('#dev-page-menu [data-dev="library"]');check(w.location.pathname==='/dev/library','navigation resumes after save');h.dom.window.close();
}

(async()=>{await catalogueInteractionChecks();await activeSaveNavigationChecks();await polishChecks();await albumImportChecks();await importChecks();await sourceChecks();await navigationChecks();await addNavigationCheck();await sourcePersistenceChecks();await sourceRefreshChecks();await bulkSourceChecks();for(const width of [320,360,390,430,568,768,1280])await moveAndTableChecks(width);
 if(process.env.DEV_CATALOG_SNAPSHOTS)fs.writeFileSync(process.env.DEV_CATALOG_SNAPSHOTS,JSON.stringify(snapshots));console.log(assertions+' developer catalogue assertions passed');
})().catch(e=>{console.error(e);process.exitCode=1});

