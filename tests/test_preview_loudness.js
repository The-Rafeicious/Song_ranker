/* Live loudness balancing must preserve native playback, fades and master volume. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const dom=new JSDOM('<body><input id="preview-loudness-balance" type="checkbox"><div id="preview-status" hidden></div></body>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,d=w.document;
const timers=new Map(),contexts=[];let serial=0,amplitude=.05,sourceCount=0;
w.setTimeout=(fn,ms)=>{timers.set(++serial,{fn,ms});return serial;};w.clearTimeout=id=>timers.delete(id);
class Param{constructor(value=1){this.value=value;}setValueAtTime(v){this.value=v;}setTargetAtTime(v){this.value=v;}}
class Node{constructor(){this.gain=new Param();this.connections=[];this.disconnected=false;}connect(n){this.connections.push(n);return n;}disconnect(){this.disconnected=true;}getFloatTimeDomainData(a){a.fill(amplitude);}}
class Context{constructor(){this.state='running';this.currentTime=0;this.destination={};this.nodes=[];contexts.push(this);}resume(){return Promise.resolve();}node(){const n=new Node();this.nodes.push(n);return n;}createGain(){return this.node();}createAnalyser(){return this.node();}createDynamicsCompressor(){const n=this.node();for(const p of ['threshold','knee','ratio','attack','release'])n[p]=new Param();return n;}createMediaElementSource(){sourceCount++;return this.node();}}
w.AudioContext=Context;
w.HTMLMediaElement.prototype.play=function(){this._paused=false;this.dispatchEvent(new w.Event('play'));this.dispatchEvent(new w.Event('playing'));return Promise.resolve();};
w.HTMLMediaElement.prototype.pause=function(){this._paused=true;this.dispatchEvent(new w.Event('pause'));};w.HTMLMediaElement.prototype.load=function(){};
Object.defineProperty(w.HTMLMediaElement.prototype,'paused',{get(){return this._paused!==false;}});Object.defineProperty(w.HTMLMediaElement.prototype,'readyState',{get(){return 4;}});
w.eval(fs.readFileSync('static/js/preview.js','utf8'));const P=w.PreviewPlayback;
let checks=0;const check=(v,m)=>{assert.ok(v,m);checks++;};
const audio=src=>{const a=d.createElement('audio');a.src=src;d.body.append(a);return a;};
const tick=async()=>{const entry=[...timers].find(([id,t])=>t.ms===100);if(entry){timers.delete(entry[0]);entry[1].fn();}await Promise.resolve();};
(async()=>{
 check(P.balanceTarget(Array(10).fill(.05))===2,'quiet clips get a bounded boost');
 check(Math.abs(P.balanceTarget(Array(10).fill(.25))-.4)<.001,'loud clips are attenuated towards the same RMS');
 check(P.balanceTarget(Array(30).fill(0))===null,'silence is never boosted');
 check(P.balanceTarget([NaN,Infinity,...Array(8).fill(.1)])===null,'invalid and insufficient samples cannot calibrate');
 const a=audio('/api/previews/1?play=first&page=first&rev=v1');await P.play(a);await Promise.resolve();
 for(let i=0;i<12;i++)await tick();
 const graph=contexts[0].nodes.slice(0,5);check(sourceCount===1,'one media source per element');check(Math.abs(graph[1].gain.value-2)<.001,'measured quiet preview reaches its bounded target');
 check(a.volume===1&&graph[3].gain.value===.5,'master volume is applied once after analysis');
 P.setVolume(.2);check(graph[3].gain.value===.2&&Math.abs(graph[1].gain.value-2)<.001,'master adjustment does not change learned loudness');
 P.setVolume(0);check(graph[3].gain.value===0,'master mute remains absolute');P.setVolume(.5);
 P.setBalance(false);check(graph[1].gain.value===1&&graph[2].ratio.value===1,'off bypasses normalization and peak compression');P.setBalance(true);
 a.pause();const b=audio('/api/previews/1?play=second&page=second&rev=v1');await P.play(b);await Promise.resolve();
 check(Math.abs(contexts[0].nodes[6].gain.value-2)<.001,'same clip reuses calibration across session tokens');
 b.pause();amplitude=.25;const loud=audio('/api/previews/2?rev=v1');await P.play(loud);await Promise.resolve();for(let i=0;i<12;i++)await tick();
 check(Math.abs(contexts[0].nodes[11].gain.value-.4)<.001,'a different recording has its own level');
 loud.pause();const revised=audio('/api/previews/1?rev=v2');await P.play(revised);await Promise.resolve();check(contexts[0].nodes[16].gain.value===1,'changed source revision starts fresh');revised.pause();
 const before=sourceCount,foreign=audio('https://cdn.example.test/preview.mp3');await P.play(foreign);check(sourceCount===before&&foreign.volume===.5,'foreign URLs keep audible native playback');foreign.pause();
 const replacement=P.replace(a,'https://cdn.example.test/new.mp3');check(replacement!==a,'changing a graphed element clones it before external playback');
 check(graph.every(n=>n.disconnected),'retired graph disconnects all nodes');
 P.stopAll();await tick();check(![...timers.values()].some(t=>t.ms===100),'idle player leaves no metering timer');
 check(w.sessionStorage.getItem('previewLoudnessLevels').includes('rev=v1'),'only calibration numbers persist for the tab');
 console.log(checks+' preview loudness checks passed');dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;dom.window.close();});
