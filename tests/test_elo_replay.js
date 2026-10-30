const {JSDOM} = require('jsdom'), fs = require('node:fs'), assert = require('node:assert/strict');
const read = name => fs.readFileSync('static/js/' + name + '.js', 'utf8');
const flush = async () => { for (let i=0;i<100;i++) await Promise.resolve(); };
const song = id => ({id,title:id===1?'One <img src=x onerror=bad()>':'Track '+id,cover_url:'',artist_links:[{name:'Artist & One'}],album_link:{title:'Album <one>'}});
const data = {total_matches:5,focus_id:1,anchored:false,omitted:0,reconciled:false,songs:{1:song(1),2:song(2),3:song(3)},frames:[
 {kind:'start',board:[{id:1,elo:1200},{id:2,elo:1200}],changes:[],ordinal:0,focus:{id:1,elo:1200,rank:1}},
 {kind:'vote',board:[{id:2,elo:1216},{id:1,elo:1184}],changes:[{id:2,before:1200,after:1216,opponent_id:1},{id:1,before:1200,after:1184,opponent_id:2}],ordinal:1,time:'2026-10-30T12:00:00+00:00',mode:'blind',focus:{id:1,elo:1184,rank:2}},
 {kind:'current',board:[{id:3,elo:1232},{id:2,elo:1216}],changes:[],ordinal:5,time:'2026-10-30T12:30:00+00:00',focus:{id:1,elo:1184,rank:3}}
]};
function harness(focus=false, motion=false) {
 const dom = new JSDOM(`<main id="main"><div data-elo-replay${focus?' data-song-id="1"':''}></div></main>`, {url:'http://localhost/voting_stats',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window, timers=new Map(), calls=[], animations=[]; let next=0;
 w.matchMedia=()=>({matches:!motion});
 w.HTMLElement.prototype.animate=function(frames,options){animations.push({frames,options});return {finished:Promise.resolve(),cancel(){}};};
 w.setTimeout=(fn,delay)=>{timers.set(++next,{fn,delay});return next;}; w.clearTimeout=id=>timers.delete(id);
 w.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>structuredClone(data)};};
 w.eval(read('ui'));w.eval(read('elo_replay'));w.EloReplay.mountAll();
 const root=w.document.querySelector('[data-elo-replay]');
 return {dom,w,root,timers,calls,animations,$:s=>root.querySelector(s),tick(){const [id,t]=[...timers][0];timers.delete(id);t.fn();}};
}
(async()=>{
 const h=harness(true), {$,w}=h;
 assert.equal(h.calls.length,0,'history is fetched only on play');
 $('[data-replay-play]').click();await flush();
 assert.equal(h.calls[0].url,'/api/voting-replay?song_id=1');
 assert.equal($('[data-replay-play]').textContent,'Pause');
 assert.equal(h.timers.size,1);
 assert.equal([...h.timers.values()][0].delay,2000);
 assert.equal(h.root.querySelectorAll('.elo-replay-row').length,2);
 assert.equal(h.root.querySelectorAll('img').length,0,'catalogue text is escaped');
 assert.equal($('[data-replay-focus]').hidden,false);
 h.tick();
 assert.equal($('[data-replay-time]').dateTime,'2026-10-30T12:00:00+00:00');
 assert.match($('[data-replay-cue]').textContent,/−16 Elo to Track 2/);
 assert.equal(h.root.querySelector('.elo-replay-row .song').textContent,'Track 2','DOM order follows rank');
 assert.equal(h.root.querySelector('.elo-replay-row strong').textContent,'1,216');
 $('[data-replay-play]').click(); assert.equal(h.timers.size,0,'pause stops advancement');
 $('[data-replay-seek]').value=2;$('[data-replay-seek]').dispatchEvent(new w.Event('input'));
 assert.equal(h.root.querySelector('.elo-replay-row .song').textContent,'Track 3');
 assert.match($('[data-replay-focus]').textContent,/#3/,'focused song remains visible outside top five');
 $('[data-replay-play]').click(); await flush();assert.equal($('[data-replay-seek]').value,'0','playing at the end restarts');
 $('[data-replay-speed]').value='1000';$('[data-replay-speed]').dispatchEvent(new w.Event('change'));
 assert.equal([...h.timers.values()][0].delay,1000);
 h.tick();h.tick();assert.equal(h.timers.size,0);assert.equal($('[data-replay-play]').textContent,'Replay again');
 $('[data-replay-restart]').click();assert.equal($('[data-replay-seek]').value,'0');
 $('[data-replay-play]').click();await flush();
 w.dispatchEvent(new w.Event('pagehide'));assert.equal(h.timers.size,0);
 h.dom.window.close();
 const moving=harness(false,true);
 moving.$('[data-replay-play]').click();await flush();moving.tick();
 assert.ok(moving.animations.some(a=>a.frames[0].transform==='translateY(88px)' && a.frames[1].transform==='translateY(0px)'), 'existing rows animate between rank lanes');
 assert.equal(h.animations.length,0,'reduced motion omits row animations');
 moving.w.dispatchEvent(new moving.w.Event('pagehide'));moving.dom.window.close();
 const retry=harness();let attempts=0;
 retry.w.fetch=async()=>{if(++attempts===1)throw Error('network');return {ok:true,json:async()=>structuredClone(data)};};
 retry.$('[data-replay-play]').click();await flush();
 assert.equal(retry.$('[data-replay-cue]').getAttribute('role'),'alert');
 assert.equal(retry.$('[data-replay-play]').textContent,'Retry replay');
 retry.$('[data-replay-play]').click();await flush();assert.equal(attempts,2);
 retry.w.dispatchEvent(new retry.w.Event('pagehide'));retry.dom.window.close();
 const stale=harness();let resolve;
 stale.w.fetch=(url,options)=>new Promise(r=>{resolve=r;stale.signal=options.signal;});
 stale.$('[data-replay-play]').click();stale.w.dispatchEvent(new stale.w.Event('pagehide'));
 assert.equal(stale.signal.aborted,true);
 resolve({ok:true,json:async()=>structuredClone(data)});await flush();
 assert.equal(stale.root.querySelectorAll('.elo-replay-row').length,0,'late responses cannot remount a disposed player');
 stale.dom.window.close();
 console.log('Elo replay: lazy fetch, controls, clock, rank order, focus, escaping, reduced motion, retry and cancellation passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
