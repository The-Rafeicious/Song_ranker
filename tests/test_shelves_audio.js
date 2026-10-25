/* Real Shelves + shared preview owner with deterministic native-media races. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const flush=async()=>{for(let i=0;i<50;i++)await Promise.resolve()};
let assertions=0;const check=(v,label)=>{assert.ok(v,label);assertions++};
async function harness(){
 const dom=new JSDOM('<body data-page="shelves"><main id="main"></main><div id="preview-status"></div></body>',{url:'http://localhost/album_shelves',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document;let now=0,id=0,defer=false,pending=[];const timers=new Map(),states=new WeakMap(),plays=[],requests=[],notes=[];
 w.setTimeout=(fn,delay=0)=>{timers.set(++id,{fn,at:now+delay});return id};w.clearTimeout=n=>timers.delete(n);Object.defineProperty(w.performance,'now',{value:()=>now});w.Date.now=()=>100000+now;
 const state=a=>{if(!states.has(a))states.set(a,{playing:false,time:0,seeking:false,ended:false});return states.get(a)};
 for(const [key,get] of Object.entries({paused:a=>!state(a).playing,currentTime:a=>state(a).time,seeking:a=>state(a).seeking,ended:a=>state(a).ended,readyState:a=>state(a).ready??4}))Object.defineProperty(w.HTMLMediaElement.prototype,key,{configurable:true,get(){return get(this)},...(key==='currentTime'?{set(v){state(this).time=v}}:{})});
 w.HTMLMediaElement.prototype.load=function(){};
 w.HTMLMediaElement.prototype.pause=function(){const s=state(this),was=s.playing;s.playing=false;if(was)this.dispatchEvent(new w.Event('pause'))};
 w.HTMLMediaElement.prototype.play=function(){const a=this;plays.push(a.getAttribute('src'));const start=()=>{state(a).playing=true;state(a).ended=false;a.dispatchEvent(new w.Event('playing'))};if(defer){defer=false;return new Promise(resolve=>pending.push(()=>{start();resolve()}))}start();return Promise.resolve()};
 w.fetch=async(url)=>{requests.push(url);return {ok:true,json:async()=>({}),body:null}};
 for(const file of ['ui.js','preview.js','special_modes.js'])w.eval(fs.readFileSync('static/js/'+file,'utf8'));
 const songs=Array.from({length:10},(_,i)=>({id:i+1,slot:i+1,title:'Song '+(i+1),audio_url:'https://audio-ssl.itunes.apple.com/'+(i+1)+'.m4a'}));
 w.SpecialModes.bindUI({main:d.querySelector('#main'),api:async()=>({token:'round',songs,albums:[{slot:1,title:'Album',cover_url:''}]}),pageTone(){},holdHeight:()=>()=>{},stopAudio:()=>w.PreviewPlayback.stopAll(),artwork:()=>'',toast:t=>notes.push(t)});
 await w.SpecialModes.loadShelf();await flush();
 const click=async selector=>{d.querySelector(selector).click();await flush()};
 const tick=async ms=>{const end=now+ms;let loops=0;while(true){const next=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;if(++loops>10000)throw Error('Timer runaway');timers.delete(next[0]);now=next[1].at;next[1].fn();await flush()}now=end;await flush()};
 return {dom,w,d,plays,requests,notes,state,tick,click,flush,delay:()=>{defer=true},resolve:async()=>{pending.shift()();await flush()},active:()=>[...d.querySelectorAll('audio')].filter(a=>!a.paused),audio:()=>d.querySelector('#shelf-preview-audio')};
}
(async()=>{
 const h=await harness(),{w,d}=h;
 check(h.plays.length===0&&d.querySelectorAll('audio[src]').length===0,'loading a round does not load or play any media');
 await h.click('[data-shelf-preview="1"]');const audio=h.audio();
 await h.tick(650);check(d.querySelectorAll('audio[src]').length===1,'only the selected song is loaded; no ahead player');
 h.state(audio).time=4;await h.tick(3350);await h.click('[data-shelf-preview="7"]');
 check(h.active().length===1&&h.audio()===audio,'manual skip uses one audible player');
 check(d.querySelector('#shelf-preview-info').textContent==='Song 7','manual selection owns the sequence');
 // Simulate a timer already queued before clearTimeout was processed.
 h.state(audio).time=6;await h.tick(6000);check(h.plays.length===2,'old song deadline cannot advance the new selection');
 h.state(audio).time=10;audio.dispatchEvent(new w.Event('timeupdate'));audio.dispatchEvent(new w.Event('ended'));await flush();
 check(h.plays.length===3&&d.querySelector('#shelf-preview-info').textContent==='Song 8','time/ended events advance exactly once from the selected song');
 h.state(audio).time=3;audio.dispatchEvent(new w.Event('seeking'));h.state(audio).seeking=true;await h.tick(12000);check(h.plays.length===3,'seeking suspends the sample deadline');
 h.state(audio).seeking=false;h.state(audio).time=2;audio.dispatchEvent(new w.Event('seeked'));await h.tick(3000);check(h.plays.length===3,'seek-back preserves the remaining media time');
 h.state(audio).time=11;audio.dispatchEvent(new w.Event('seeked'));await flush();check(h.plays.length===4,'seeking beyond the sample advances once');
 audio.dispatchEvent(new w.Event('waiting'));await h.tick(15000);check(h.plays.length===4,'buffering cannot advance a song that has not played its sample');
 audio.dispatchEvent(new w.Event('playing'));h.state(audio).time=10;audio.dispatchEvent(new w.Event('timeupdate'));await flush();
 check(h.active().length===1,'resume still has one audible player');
 await h.click('[data-shelf-play]');const stopped=h.plays.length;h.state(audio).time=12;audio.dispatchEvent(new w.Event('timeupdate'));await h.tick(20000);check(h.active().length===0&&h.plays.length===stopped,'pause cancels timers and late advance events');
 h.delay();await h.click('[data-shelf-preview="2"]');await h.click('[data-shelf-preview="6"]');await h.resolve();
 check(h.active().length===1&&d.querySelector('#shelf-preview-info').textContent==='Song 6','late native play completion cannot reclaim a newer manual selection');
 h.delay();await h.click('[data-shelf-preview="3"]');await h.click('[data-shelf-play]');await h.resolve();check(h.active().length===0,'pausing a pending play silences its late native resolution');
 // Cross-page shared owner: a cancelled, detached element may resolve play late.
 w.PreviewPlayback.stopAll();const old=d.createElement('audio'),next=d.createElement('audio');old.src='/old';h.state(old).ready=0;next.src='/new';d.body.append(old,next);h.delay();const late=w.PreviewPlayback.play(old).catch(e=>e.name);await flush();w.PreviewPlayback.release(old);await w.PreviewPlayback.play(next);await h.resolve();await late;
 check(old.paused&&!next.paused,'late play on an obsolete element is silenced without pausing its replacement');
 w.dispatchEvent(new w.Event('pagehide'));await h.tick(20000);check(h.active().length===0,'page exit leaves no audio running');
 check(h.requests.every(url=>!/^\/api\/previews\/\d/.test(url)),'Shelves never starts a quiet preload fetch');
 check(h.notes.length===0,'ordinary playback races produce no error toast');
 h.dom.window.close();
 const cycle=await harness();await cycle.click('[data-shelf-play]');for(let i=0;i<10;i++){cycle.state(cycle.audio()).time=10;await cycle.tick(10000)}
 check(cycle.plays.length===11&&cycle.d.querySelector('#shelf-preview-info').textContent==='Song 1','100-second ten-song rotation returns to the first track exactly once');
 check(cycle.active().length===1&&cycle.d.querySelectorAll('audio[src]').length===1,'a full round retains only its one selected media element');cycle.dom.window.close();
 console.log(assertions+' Shelves/shared audio assertions passed');
})().catch(e=>{console.error(e);process.exitCode=1});
