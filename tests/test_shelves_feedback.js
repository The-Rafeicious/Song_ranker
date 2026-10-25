/* Exercise staged result feedback through the real Shelves controller. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve()};let assertions=0;
const check=(v,label)=>{assert.ok(v,label);assertions++};
async function harness(perfect){
 const dom=new JSDOM('<body data-page="shelves"><main id="main"></main></body>',{url:'http://localhost/album_shelves',runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.HTMLMediaElement.prototype.pause=function(){};
 const timers=[];w.matchMedia=()=>({matches:false});w.RoundFlow={take:(key,load)=>load(),duration:()=>1,after:fn=>{const job={fn,live:true};timers.push(job);return ()=>{job.live=false}},prepare(){}};
 const songs=Array.from({length:5},(_,i)=>({id:i+1,slot:i+1,title:'Track '+(i+1),audio_url:''}));
 const items=songs.map((s,i)=>{const right=perfect?4:[4,3,2,0,0][i],album=perfect||i!==4;return {item_slot:s.slot,album_correct:album,order_pairs:4,order_right:right,answer_slot:1,answer_position:s.slot,points:(album?.5:0)+2.5*right/4,available:3}});
 const result={items,answers:songs.map(s=>({slot:s.slot,album_slot:1,track_number:s.slot,disc_number:1})),available:15,points:items.reduce((n,r)=>n+r.points,0),order_right:items.reduce((n,r)=>n+r.order_right,0),order_pairs:20};
 for(const file of ['ui.js','special_modes.js'])w.eval(fs.readFileSync('static/js/'+file,'utf8'));
 w.SpecialModes.bindUI({main:d.querySelector('#main'),api:async url=>url.endsWith('/answer')?result:{token:'round',songs,albums:[{slot:1,title:'Album'}]},pageTone(){},holdHeight:()=>()=>{},stopAudio(){},artwork:()=>'',toast:t=>{throw Error(t)},animateScore:(node,a,b)=>node.textContent=Number(b).toFixed(2)});
 await w.SpecialModes.loadShelf();await flush();
 for(const song of songs){d.querySelector(`[data-shelf-pick="${song.slot}"][data-shelf-target="1"]`).click();await flush()}
 const tick=async()=>{const job=timers.shift();if(job?.live)job.fn();await flush()};
 return {dom,w,d,result,timers,tick,finish:async()=>{let n=0;while(d.querySelector('[data-shelf-next]').hidden){assert.ok(n++<100);await tick()}}};
}
(async()=>{
 const h=await harness(false),{d}=h;
 check(d.querySelector('#shelf-perfect').hidden,'no celebration while arranging');
 check([...d.querySelectorAll('[data-shelf-slot]')].every(n=>!n.style.getPropertyValue('--shelf-error-depth')),'no answer severity leaks before submit');
 d.querySelector('[data-shelf-check]').click();await flush();check(d.querySelector('#shelf-perfect').hidden,'no celebration during the reveal');
 await h.tick();
 check(d.querySelector('[data-shelf-slot="1"]').classList.contains('answer-correct'),'a fully correct track stays green');
 check(!d.querySelector('[data-shelf-slot="2"]').style.getPropertyValue('--shelf-error-depth'),'unrevealed track has no severity');
 await h.finish();
 const depth=id=>Number(d.querySelector(`[data-shelf-slot="${id}"]`).style.getPropertyValue('--shelf-error-depth'));
 check(depth(2)===.25&&depth(3)===.5&&depth(4)===1,'red depth follows the proportion of wrong comparisons');
 check(depth(5)===1&&d.querySelector('[data-shelf-slot="5"]').textContent.includes('Wrong album'),'wrong album uses deepest red and keeps explicit correction');
 check(d.querySelector('#shelf-perfect').hidden,'partial result never celebrates');
 check(d.querySelector('[data-shelf-slot="2"]').textContent.includes('3 / 4 order comparisons'),'numeric and text evidence remains available');h.dom.window.close();
 const p=await harness(true);p.d.querySelector('[data-shelf-check]').click();await flush();check(p.d.querySelector('#shelf-perfect').hidden,'perfect answer stays unannounced until reveal completes');await p.finish();
 check(!p.d.querySelector('#shelf-perfect').hidden&&p.d.querySelector('#shelf-perfect').textContent.includes('Perfect shelves'),'perfect completed round gets one compact badge');
 check(p.d.querySelectorAll('.shelf-perfect').length===1,'one result badge per round');
 await p.w.SpecialModes.loadShelf(true);check(p.d.querySelector('#shelf-perfect').hidden,'new round clears perfect feedback');p.dom.window.close();
 console.log(assertions+' Shelves result feedback assertions passed');
})().catch(e=>{console.error(e);process.exitCode=1});
