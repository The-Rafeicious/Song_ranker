/* Profile composition, thresholds and preview ownership; mocked catalogue/media. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8');
let assertions=0;const check=(value,message)=>{assert.ok(value,message);assertions++};
const flush=async()=>{for(let i=0;i<100;i++)await Promise.resolve()};
function fixture(size=75){
 const albums=Array.from({length:9},(_,i)=>({id:i+1,title:'Album '+(i+1),cover_url:'',release_date:'2026-01-01'}));
 const songs=Array.from({length:size},(_,i)=>({id:i+1,title:'Song '+(i+1),album_id:i<35?1:Math.floor((i-35)/5)+2,track_number:i<35?i+1:(i-35)%5+1,
  artist_ids:[1],tag_ids:[1],audio_url:'https://audio.example.test/'+(i+1),elo_score:1200+i,matches_played:2,
  attempts:2,new_attempts:2,correct:4,available_points:6,title_correct:1,artist_correct:2,album_correct:1,album_attempts:2,
  shelves_eligible:true,guess_attempts:2,guess_correct:1,shelf_attempts:1,shelf_album_correct:1,shelf_order_right:2,shelf_order_pairs:3,shelf_points:.8,shelf_available:1,
  tournament_points:1.25,tournament_wins:1,tournament_losses:1,championships:i===0?1:0,podiums:i===0?1:0,
  voting:{standard_wins:1,standard_losses:0,blind_wins:0,blind_losses:1,raw:{standard_wins:1,standard_losses:0,blind_wins:0,blind_losses:1}},
  mode_ratings:{standard:{elo:1210+i,matches:1},blind:{elo:1190+i,matches:1}},listening:{samples:1,seconds:12}}));
 return {songs,albums,artists:[{id:1,name:'Artist'}],tags:[{id:1,name:'Tag',description:'Tag notes'}],history:[],elo_history:[],tournaments:[{id:1,size:8,status:'completed'},{id:2,size:8,status:'completed',scope_type:'artist',scope_id:1,champion_id:1},{id:3,size:8,status:'in_progress',scope_type:'album',scope_id:1}],tournament_matches:[],tournament_entries:songs.map(s=>({song_id:s.id,tournament_id:1})),global_stats:{}};
}
function songDetails(){return {song_id:1,
 voting:{opponents:1,best_run:8,current_run:2,net:23.2,snapshots:12,matches:13,recent_wins:7,recent_matches:10,sources:[{key:'ordinary',wins:8,matches:10},{key:'tournament',wins:2,matches:3}],opponents_list:[{id:2,wins:6,losses:2}]},
 trivia:{rounds:12,graded:12,perfect:3,missed:2,latest:{rounds:5,correct:8,available:10},previous:{rounds:5,correct:3,available:10},timing:[{key:'title',samples:8,mean:4.2,fastest:2}],recent:[{date:{iso:'2026-10-31T10:00:00Z'},correct:2,available:2,fields:{title:1,artist:1}}]},
 tournament:{completed:3,first_exits:1,groups:[{key:'competition',wins:2,losses:1,entries:2},{key:'local',wins:0,losses:1,entries:1}],recent:[{id:9,date:{iso:'2026-10-31T10:00:00Z'},size:8,mode:'blind',scope:'tag',finish:'2nd',wins:2,losses:1}]},
 guesser:{selected:3,graded:5,unknown:0,bands:[{label:'Under 50 Elo apart',correct:2,graded:3},{label:'50+ Elo apart',correct:1,graded:2}],recent:[{opponent_id:2,correct:0,selected:true,gap:31,date:null}]},
 shelves:{graded:4,perfect:2,wrong_album:1,unknown:0,recent:[{date:null,grade:{album_correct:1,order_right:2,order_pairs:3,points:2.17,available:3}}]},
 songs:{2:{id:2,title:'Opponent <img src=x onerror=bad()>',cover_url:'/cover-2',artists:[{id:1,name:'Artist & One'}],album:'Album <Two>',album_id:2}}};}
async function harness(page,width=1280,size=75,eligible=true,detailState={}){
 const data=fixture(size),kind={artist:'artists',album:'albums',tag:'tags'}[page],name=page==='album'?'Album 1':page==='artist'?'Artist':'Tag';
 if(!eligible)data.songs.forEach(s=>s.shelves_eligible=false);
 const html=`<body class="site-style-baseline" data-page="${page}" data-entity="1"><main id="main"><div id="loading"></div></main>${kind?`<script id="profile-data" type="application/json">${JSON.stringify({kind,name})}</script>`:''}<input id="volume-range" value=".5"><span id="volume-value"></span><button id="volume-btn"></button><div id="volume-panel" hidden></div><dialog id="editor"><form id="editor-form"><h2 id="editor-title"></h2><div id="editor-fields"></div><button id="editor-submit"></button></form></dialog><div id="toast"></div></body>`;
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(html,{url:'http://localhost/'+page,runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc}),w=dom.window,d=w.document;
 w.innerWidth=width;w.scrollTo=()=>{};w.matchMedia=()=>({matches:true});
 const playing=new WeakSet();w.HTMLMediaElement.prototype.play=function(){playing.add(this);this.dispatchEvent(new w.Event('play'));return Promise.resolve()};w.HTMLMediaElement.prototype.pause=function(){playing.delete(this);this.dispatchEvent(new w.Event('pause'))};w.HTMLMediaElement.prototype.load=function(){};
 Object.defineProperty(w.HTMLMediaElement.prototype,'paused',{get(){return !playing.has(this)}});
 w.fetch=async url=>({ok:true,json:async()=>{
  if(/^\/api\/song\/\d+\/stats$/.test(url)){
   detailState.calls=(detailState.calls||0)+1;
   if(detailState.pending)await new Promise(resolve=>{(detailState.resolvers ||= []).push(resolve)});
   if(detailState.fail)throw Error('Unavailable');
   return songDetails();
  }
  if(url==='/api/collection')return structuredClone(data);
  if(url==='/api/overall')return {entities:Object.fromEntries(['songs','artists','albums','tags'].map(type=>[type,[{id:1,name:'Entity',score:50,evidence:25,group_confidence:50,mode_count:1,tested_tracks:1,track_count:size,contributions:[{key:'standard',label:'Non-blind',score:50,weight:100,points:50,evidence:25}]}]]))};
  throw Error('Unexpected '+url);
 }});
 for(const file of ['ui.js','profiles.js','overall.js','special_modes.js'])w.eval(read('static/js/'+file));
 await w.eval(read('static/js/site.js'));await flush();
 return {dom,w,d,data,errors,click:async selector=>{const b=d.querySelector(selector);assert.ok(b,'Missing '+selector);b.click();await flush()}};
}
(async()=>{
 for(const type of ['song','artist','album','tag']){
  const h=await harness(type,390,75,false);
  check(!h.d.querySelector('[data-profile-panel="shelves"]'),type+' hides Shelves without an eligible album');
  check(h.d.querySelector('[data-profile-panel="guesser"]'),type+' retains other modes');
  h.dom.window.close();
 }
 const expected=['standard','recognition','tournament','guesser','shelves'];
 for(const width of [390,1280])for(const type of ['song','artist','album','tag']){
  const h=await harness(type,width),{d}=h;
  check(d.body.classList.contains('profile-page'),type+' profile class '+width);
  check(JSON.stringify([...d.querySelectorAll('[data-profile-panel]')].map(n=>n.dataset.profilePanel))===JSON.stringify(expected),type+' uses the five shared records');
  check(d.querySelectorAll('.song-sections details').length===(type==='song'?5:0),type+' bounded song detail disclosures only');
  check(d.querySelectorAll('#overall-profile details').length===1,type+' keeps Overall dropdown');
  check(!d.querySelector('#overall-profile .overall-balance-copy,#overall-profile .overall-mode-context'),type+' removes Overall explanation');
  check(d.querySelectorAll('#recognition > .profile-field-grid > .profile-inset').length===3,type+' fields shown inline');
  check(d.querySelectorAll('[data-profile-panel="shelves"] .profile-inset').length===2,type+' placement and points inline');
  check(!d.querySelector('.profile-listening,.profile-extra,.profile-bracket'),type+' has no extra diagnostic/nested panels');
  check(d.querySelectorAll('[data-profile-panel] > .joined-metrics').length===5,type+' summaries share one structure');
  check(h.errors.length===0,type+' loads without errors');
  if(['artist','album'].includes(type)){check(d.querySelector('a[href="/tournament/'+(type==='artist'?2:3)+'/bracket"]'),type+' has its own selective replay link');check(d.querySelector('#tournament').nextElementSibling.id==='local-tournaments',type+' local tournaments have a separate box below the main record');check(d.querySelector('#local-tournaments .joined-metrics').textContent.includes('Completed brackets'),type+' local box shows compact summary statistics');check(d.querySelector('#local-tournaments a[href^="/tournament_local_stats?scope="]'),type+' links to filtered local comparisons');check(!d.querySelector('#tournament').textContent.includes('Scope-weighted competition results'),type+' omits the repeated policy note');}
  if(type!=='song'){
   check(d.querySelectorAll('.profile-track-row').length===30,type+' starts with thirty songs');
   const audio=d.querySelector('.profile-track-row audio'),row=audio.parentElement;
   await h.click('.profile-track-row [data-audio]');check(!audio.paused,type+' row preview starts');
   await h.click('[data-profile-more="tracks"]');
   check(d.querySelector('#'+audio.id)===audio&&row.isConnected&&!audio.paused,type+' more preserves playing preview');
   check(d.querySelectorAll('.profile-track-row').length===(type==='album'?35:60),type+' reveals the next songs');
   if(type==='album'){
    check(!d.querySelector('[data-profile-more="tracks"]'),'album hides exhausted control');
    await h.click('[data-profile-sort="track"]');check(d.querySelector('.profile-track-row').dataset.profileTrack==='1','album track sort retained');
   }else{
    await h.click('[data-profile-more="tracks"]');check(d.querySelectorAll('.profile-track-row').length===75,type+' reveals all songs');
    check(!d.querySelector('[data-profile-more="tracks"]'),type+' hides exhausted control');
    check(d.querySelector('.profile-track-row:last-child .compact-rank').textContent==='75',type+' numbering continues');
   }
   if(type==='tag'){
    check(d.querySelectorAll('.profile-album-card').length===6,'tag starts with six albums');
    await h.click('[data-profile-more="albums"]');check(d.querySelectorAll('.profile-album-card').length===9,'tag shows remaining albums');
    check(!d.querySelector('[data-profile-more="albums"]'),'tag hides exhausted albums control');
   }
  }else check(d.querySelector('#song-audio').hasAttribute('loop'),'song hero retains looping preview');
  h.dom.window.close();
 }
 for(const size of [0,30]){
  const h=await harness('tag',1280,size);
  check(!h.d.querySelector('[data-profile-more="tracks"]'),'no redundant button at '+size+' tracks');
  check(!h.d.querySelector('[data-profile-more="albums"]'),'no album button below threshold');
  check(!h.d.querySelector('.song-sections').textContent.includes('NaN'),'empty/boundary stats stay valid');h.dom.window.close();
 }
 const detail=await harness('song');
 check(detail.d.querySelector('[data-song-details="voting"]').textContent.includes('Different opponents'),'song shows opponents away from leaderboards');
 check(detail.d.querySelector('.profile-vote-mode').textContent.includes('of 75 rated tracks'),'mode standings use all rated songs');
 const middle=detail.d.createElement('div');middle.innerHTML=detail.w.ProfileUI.stats([detail.data.songs[37]]);
 check(middle.querySelector('.profile-vote-mode').textContent.includes('Rank #38 of 75 rated tracks'),'middle-ranked songs use the whole cohort rather than a top/bottom slice');
 check(detail.d.querySelector('[data-song-details="trivia"]').textContent.includes('Previous · 5 rounds'),'recall comparison windows are explicit');
 check(detail.d.querySelector('[data-song-details="tournament"] a[href="/tournament/9/bracket"]'),'saved finishes link directly to bracket');
 check(detail.d.querySelector('.profile-opponent a.artist')?.getAttribute('href').includes('Artist'),'opponent has linked artists');
 check(detail.d.querySelector('.profile-opponent a.album')?.getAttribute('href').includes('Album'),'opponent has linked album');
 check(detail.d.querySelectorAll('.profile-opponent img').length===2,'only artwork is markup; hostile song title stays escaped');
 check(!detail.d.querySelector('[data-song-details][aria-busy]'),'loading state is cleared');
 detail.dom.window.close();
 const state={fail:true},failed=await harness('song',390,75,true,state);
 check(failed.d.querySelector('[data-song-details-retry]'),'request failure has retry');
 const failedHero=failed.d.querySelector('#song-audio');await failed.click('[data-audio="song-audio"]');state.fail=false;await failed.click('[data-song-details-retry]');
 check(state.calls===2&&!failed.d.querySelector('[data-song-details-retry]'),'retry fills existing panels');
 check(failed.d.querySelector('#song-audio')===failedHero&&!failedHero.paused,'retry preserves hero and playback');failed.dom.window.close();
 const pendingState={pending:true},pending=await harness('song',1280,75,true,pendingState);
 const hero=pending.d.querySelector('#song-audio');await pending.click('[data-audio="song-audio"]');
 pending.w.ProfileUI.loadSongDetails(1,pending.d.querySelector('main'));await flush();
 pendingState.resolvers[1]();await flush();
 check(pending.d.querySelector('[data-song-details="voting"]').textContent.includes('Different opponents'),'newer detail response renders');
 const rendered=pending.d.querySelector('[data-song-details="voting"]').innerHTML;
 pendingState.fail=true;pendingState.resolvers[0]();await flush();
 check(pending.d.querySelector('[data-song-details="voting"]').innerHTML===rendered,'stale failure cannot replace newer details');
 check(pending.d.querySelector('#song-audio')===hero&&!hero.paused,'background details leave cover player stable');pending.dom.window.close();
 const css=read('static/css/profiles.css').replace(/\s+/g,'');
 check(css.includes('.profile-artist.profile-media{--profile-cover-radius:50%;}'),'artist owns circular cover radius');
 check(css.includes(':is(.album-cover-player,.cover-button,.art-wrap,.art-fallback,.play-overlay){border-radius:var(--profile-cover-radius);}'),'artwork and audio layers share one radius');
 check(css.includes('.profile-list-actions{display:flex;justify-content:center;'),'show-more actions centred');
 console.log(assertions+' profile assertions passed');
})().catch(e=>{console.error(e);process.exitCode=1});
