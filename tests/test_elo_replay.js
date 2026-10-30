const {JSDOM} = require('jsdom'), fs = require('node:fs'), assert = require('node:assert/strict');
const read = name => fs.readFileSync('static/js/' + name + '.js', 'utf8');
const flush = async () => { for(let i=0;i<100;i++)await Promise.resolve(); };
const song = id => ({id,title:id===1?'One <img src=x onerror=bad()>':'Track '+id,cover_url:'',audio_url:'/preview-'+id,artist_links:[{name:'Artist & One'}],album_link:{title:'Album <one>'}});
const data = {total_matches:5,focus_id:null,anchored:false,omitted:0,reconciled:false,songs:{1:song(1),2:song(2),3:song(3),4:song(4),5:song(5)},frames:[
 {kind:'start',board:[{id:1,elo:1200},{id:2,elo:1200}],changes:[],ordinal:0},
 {kind:'vote',board:[{id:2,elo:1216},{id:1,elo:1184}],changes:[{id:2,before:1200,after:1216,opponent_id:1},{id:1,before:1200,after:1184,opponent_id:2}],ordinal:1,time:'2026-10-30T12:00:00+00:00',mode:'blind'},
 {kind:'current',board:[{id:3,elo:1232},{id:2,elo:1216}],changes:[],ordinal:5,time:'2026-10-30T12:30:00+00:00'}
]};
function focused(){
 const d=structuredClone(data);d.focus_id=1;
 d.frames.forEach((f,i)=>{f.focus={id:1,elo:i?1184:1200,rank:i?6:3};f.board=i===2?[{id:4,elo:1210,rank:4,slot:0},{id:5,elo:1200,rank:5,slot:1},{id:1,elo:1184,rank:6,slot:2}]:[{id:2,elo:i?1216:1220,rank:2,slot:1},{id:1,elo:i?1184:1200,rank:i?3:3,slot:2},{id:3,elo:1180,rank:4,slot:3}];});return d;
}
function harness(focus=false,motion=false){
 const dom=new JSDOM(`<body data-page="${focus?'song':'voting_stats'}"><main id="main"><div data-elo-replay${focus?' data-song-id="1"':''}></div></main></body>`,{url:'http://localhost/voting_stats',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,timers=new Map(),calls=[],animations=[],audioCalls=[];let next=0;
 w.matchMedia=()=>({matches:!motion});
 w.HTMLElement.prototype.animate=function(frames,options){animations.push({frames,options});return{finished:Promise.resolve(),cancel(){}};};
 const playing=new WeakSet();
 Object.defineProperty(w.HTMLMediaElement.prototype,'paused',{get(){return !playing.has(this);}});
 w.HTMLMediaElement.prototype.play=function(){playing.add(this);return Promise.resolve();};
 w.HTMLMediaElement.prototype.pause=function(){playing.delete(this);};
 w.HTMLMediaElement.prototype.load=function(){};
 w.PreviewPlayback={source:(id,url)=>url,play:async a=>{audioCalls.push(['play',Number(a.dataset.songId)]);await a.play();},abandon:a=>a.pause(),retire:a=>audioCalls.push(['retire',Number(a.dataset.songId)]),release:a=>{a.pause();a.remove();}};
 w.setTimeout=(fn,delay)=>{timers.set(++next,{fn,delay});return next;};w.clearTimeout=id=>timers.delete(id);
 const payload=focus?focused():structuredClone(data);
 w.fetch=async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>payload};};
 w.eval(read('ui'));w.eval(read('gameplay'));w.eval(read('elo_replay'));w.EloReplay.mountAll();
 const root=w.document.querySelector('[data-elo-replay]');
 return{dom,w,root,timers,calls,animations,audioCalls,$:s=>root.querySelector(s),tick(){const [id,t]=[...timers][0];timers.delete(id);t.fn();},close(){w.dispatchEvent(new w.Event('pagehide'));dom.window.close();}};
}
(async()=>{
 const h=harness(true),{$,w}=h;
 assert.equal(h.calls.length,0);
 $('[data-replay-play]').click();await flush();
 assert.equal(h.calls[0].url,'/api/voting-replay?song_id=1');
 assert.equal(h.root.querySelectorAll('.elo-replay-row').length,3);
 assert.equal(h.root.querySelectorAll('img').length,0,'text stays escaped');
 assert.equal(h.root.querySelectorAll('[data-replay-focus],[data-replay-opponent],[data-replay-sound]').length,0,'focused view has no top-five summary, points card or leader audio');
 assert.equal($('.is-focus-track').style.transform,'translateY(224px)');
 assert.equal(h.root.querySelectorAll('.elo-replay-gap').length,2);
 assert.equal($('[data-replay-seek]').parentElement.previousElementSibling.className,'elo-replay-clock','clock sits directly above timeline');
 assert.deepEqual(h.audioCalls,[]);
 h.tick();assert.equal($('[data-replay-time]').dateTime,'2026-10-30T12:00:00+00:00');
 assert.match($('[data-replay-cue]').textContent,/−16 Elo to Track 2/);
 assert.equal($('.is-focus-track').style.transform,'translateY(224px)');
 $('[data-replay-play]').click();assert.equal(h.timers.size,0);
 $('[data-replay-seek]').value=2;$('[data-replay-seek]').dispatchEvent(new w.Event('input'));
 assert.equal($('.is-focus-track .elo-replay-rank').textContent,'6');
 assert.equal($('.is-focus-track').style.transform,'translateY(224px)');
 assert.equal(h.root.querySelectorAll('.elo-replay-row').length,3);
 $('[data-replay-play]').click();await flush();assert.equal($('[data-replay-seek]').value,'0');
 const trigger=$('.game-select-trigger');trigger.click();
 assert.equal(trigger.getAttribute('aria-expanded'),'true');
 $('[data-game-option="1000"]').click();assert.equal($('[data-replay-speed]').value,'1000');
 assert.equal(trigger.getAttribute('aria-expanded'),'false');assert.equal([...h.timers.values()][0].delay,1000);
 h.tick();h.tick();h.tick();assert.equal(h.timers.size,0);assert.equal($('[data-replay-play]').textContent,'Replay again');
 h.close();
 const moving=harness(false,true);
 moving.$('[data-replay-play]').click();await flush();assert.deepEqual(moving.audioCalls,[['play',1]]);
 moving.tick();await flush();assert.ok(moving.audioCalls.some(c=>c[0]==='retire'&&c[1]===1));assert.ok(moving.audioCalls.some(c=>c[0]==='play'&&c[1]===2));
 assert.ok(moving.animations.some(a=>a.frames[0].transform==='translateY(112px)'&&a.frames[1].transform==='translateY(0px)'));
 assert.match(moving.$('[data-replay-opponent]').textContent,/\+16 Elo for Track 2/);
 assert.match(moving.$('[data-replay-opponent]').textContent,/Artist & One/);
 assert.equal(moving.$('.is-featured .song').textContent,'Track 2');
 moving.$('[data-replay-sound]').click();assert.ok([...moving.root.querySelectorAll('audio')].every(a=>a.paused));
 moving.$('[data-replay-sound]').click();await flush();
 moving.$('[data-replay-play]').click();assert.ok([...moving.root.querySelectorAll('audio')].every(a=>a.paused));
 moving.$('[data-replay-play]').click();await flush();moving.tick();await flush();
 assert.ok(moving.audioCalls.some(c=>c[0]==='play'&&c[1]===3),'leader changes follow the board');
 moving.tick();assert.ok([...moving.root.querySelectorAll('audio')].every(a=>a.paused),'audio stops after the final dwell');
 assert.equal(h.animations.length,0);moving.close();
 const integrated=harness();
 integrated.w.localStorage.setItem('siteVolume','0.31');
 Object.defineProperty(integrated.w.HTMLMediaElement.prototype,'readyState',{get(){return 4;},configurable:true});
 integrated.w.eval(read('preview'));
 integrated.$('[data-replay-play]').click();await flush();
 const actual=integrated.root.querySelector('audio');assert.ok(actual && !actual.paused);assert.equal(actual.volume,.31,'leader uses the shared persisted master volume');assert.equal(actual.loop,true);
 integrated.$('[data-replay-play]').click();assert.ok(actual.paused);integrated.close();
 const blocked=harness();blocked.w.PreviewPlayback.play=()=>Promise.reject(Object.assign(Error('gesture'),{name:'NotAllowedError'}));
 blocked.$('[data-replay-play]').click();await flush();assert.equal(blocked.$('[data-replay-sound]').textContent,'Enable sound');assert.equal(blocked.$('[data-replay-play]').textContent,'Pause');blocked.close();
 const missing=harness();missing.w.fetch=async()=>{const d=structuredClone(data);d.songs[1].audio_url='';return{ok:true,json:async()=>d};};
 missing.$('[data-replay-play]').click();await flush();assert.equal(missing.audioCalls.length,0);assert.match(missing.$('[data-replay-audio-status]').textContent,/unavailable/);missing.close();
 const pending=harness();let finishAudio, pendingClip;
 pending.w.PreviewPlayback.play=a=>new Promise(resolve=>{pendingClip=a;finishAudio=async()=>{await a.play();resolve();};});
 pending.$('[data-replay-play]').click();await flush();pending.$('[data-replay-sound]').click();
 await finishAudio();await flush();assert.ok(pendingClip.paused,'late native playback is silenced after mute');pending.close();
 const hidden=harness();hidden.$('[data-replay-play]').click();await flush();
 Object.defineProperty(hidden.w.document,'hidden',{value:true,configurable:true});hidden.w.document.dispatchEvent(new hidden.w.Event('visibilitychange'));
 assert.ok([...hidden.root.querySelectorAll('audio')].every(a=>a.paused));assert.equal(hidden.timers.size,0);hidden.close();
 const retry=harness();let attempts=0;
 retry.w.fetch=async()=>{if(++attempts===1)throw Error('network');return{ok:true,json:async()=>structuredClone(data)};};
 retry.$('[data-replay-play]').click();await flush();assert.equal(retry.$('[data-replay-cue]').getAttribute('role'),'alert');retry.$('[data-replay-play]').click();await flush();assert.equal(attempts,2);retry.close();
 const stale=harness();let resolve;
 stale.w.fetch=(url,options)=>new Promise(r=>{resolve=r;stale.signal=options.signal;});
 stale.$('[data-replay-play]').click();stale.w.dispatchEvent(new stale.w.Event('pagehide'));assert.equal(stale.signal.aborted,true);
 resolve({ok:true,json:async()=>structuredClone(data)});await flush();assert.equal(stale.root.querySelectorAll('.elo-replay-row').length,0);stale.dom.window.close();
 console.log('Elo replay: centred neighbours, styled pace, timeline, points card, leader audio, mute/pause/end, blocked/missing previews and cancellation passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
