/* Visual tree, privacy, progressive replay and bounded single-player audio. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
let checks=0;const check=(v,s)=>{assert.ok(v,s);checks++};
function fixture(size=8){
 const entries=Array.from({length:size},(_,i)=>({id:i+1,title:i===0?'Song <script> & long title':'Track '+(i+1),artist:'Artist',audio_url:'audio-'+(i+1)})),matches=[];
 let ids=entries.map(s=>s.id),mid=1,r=1;
 while(ids.length>1){const next=[];for(let i=0;i<ids.length;i+=2){matches.push({id:mid++,round_number:r,match_number:i/2+1,song1_id:ids[i],song2_id:ids[i+1],winner_id:ids[i],loser_id:ids[i+1],status:'completed',match_type:'bracket',points_awarded:1});next.push(ids[i]);}ids=next;r++;}
 return {tournament:{id:1,size,status:'completed',is_blind:0},entries,matches};
}
function harness(reduced=false){
 const dom=new JSDOM('<body><div id="root"></div><div id="second"></div></body>',{url:'http://localhost/tournament',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,d=w.document,timers=new Map(),plays=[],pauses=[],retired=[],fades=[];let seq=0;
 w.matchMedia=()=>({matches:reduced});w.HTMLElement.prototype.scrollTo=function(o){this.scrollLeft=o.left||0;this.scrollTop=o.top||0};
 const delays=[];w.setTimeout=(fn,ms)=>{delays.push(ms);timers.set(++seq,fn);return seq};w.clearTimeout=id=>timers.delete(id);
 w.HTMLMediaElement.prototype.pause=function(){pauses.push(this)};
 w.PreviewPlayback={source:(id,url)=>'/cached/'+id,play:async a=>{plays.push(a)},cancel:a=>pauses.push(a),retire:a=>retired.push(a),fadeOut:(a,ms)=>fades.push(ms)};
 for(const f of ['ui.js','gameplay.js'])w.eval(fs.readFileSync('static/js/'+f,'utf8'));
 const tick=async()=>{const [id,fn]=timers.entries().next().value||[];if(fn){timers.delete(id);fn();}await Promise.resolve();};
 return {w,d,dom,timers,plays,pauses,retired,fades,delays,tick};
}
(async()=>{
 const h=harness(),data=fixture(32),root=h.d.querySelector('#root');
 const tree=h.w.TournamentBracket.mount(root,data);
 check(root.querySelectorAll('.bracket-node').length===31,'32 songs form 31 main matches');
 check(Number.parseFloat(root.querySelector('.bracket-final').style.left)>Number.parseFloat(root.querySelector('[data-map-match="1"]').style.left),'final is inside the two halves');
 check(Number.parseFloat(root.querySelector('[data-map-match="16"]').style.left)>Number.parseFloat(root.querySelector('.bracket-final').style.left),'right half feeds inwards');
 check(root.querySelectorAll('svg path').length===30,'every feeder connects to its next round');
 check(root.querySelectorAll('script').length===0,'song names are escaped');
 root.querySelector('[data-map-track="1"]').click();check(root.querySelectorAll('.is-route').length===5,'selected champion route appears across five rounds');
 check(root.querySelector('.bracket-inspector').textContent.includes('5 wins'),'inspector reports path wins');
 check(!root.querySelector('[data-map-round],[data-map-half]'),'stage selectors are removed');
 check(root.querySelector('.bracket-inspector').closest('[data-map-match]')===root.querySelector('[data-map-match="1"]'),'details drop from the selected match');
 check(parseFloat(root.querySelector('.bracket-final').style.getPropertyValue('--round-light'))>parseFloat(root.querySelector('[data-map-match="1"]').style.getPropertyValue('--round-light')),'round shades brighten towards the final');
 root.querySelector('[data-map-close]').click();check(!root.querySelector('.bracket-inspector'),'details can close without leaving the map');
 check(h.plays.length===0,'viewing a saved bracket does not load audio');tree.cancel();
 const bronzeHarness=harness(),withBronze=fixture();withBronze.matches.push({id:8,round_number:3,match_number:0,match_type:'third_place',song1_id:3,song2_id:7,winner_id:3,loser_id:7,status:'completed',points_awarded:1});
 bronzeHarness.w.TournamentBracket.mount(bronzeHarness.d.querySelector('#root'),withBronze);
 check(bronzeHarness.d.querySelectorAll('.bracket-third .bracket-track').length===2,'third place is an interactive match');
 check(parseFloat(bronzeHarness.d.querySelector('.bracket-third').style.top)>parseFloat(bronzeHarness.d.querySelector('.bracket-final').style.top),'third place sits below the central final');
 bronzeHarness.dom.window.close();
 for(const size of [8,16,32]){const f=fixture(size),ids=[...h.w.TournamentBracket.soundtrack(f)];check(ids.length===4&&ids.every(id=>f.matches.some(m=>m.round_number===Math.log2(size)-1&&(m.song1_id===id||m.song2_id===id))),'soundtrack is exactly the semi-finalists for '+size);}
 const dragHarness=harness(),dragRoot=dragHarness.d.querySelector('#root'),dragTree=dragHarness.w.TournamentBracket.mount(dragRoot,fixture()),viewport=dragRoot.querySelector('.bracket-viewport');
 const pointer=(type,x,y)=>{const e=new dragHarness.w.MouseEvent(type,{bubbles:true,cancelable:true,clientX:x,clientY:y,button:0});Object.defineProperty(e,'pointerId',{value:1});Object.defineProperty(e,'pointerType',{value:'mouse'});viewport.dispatchEvent(e);};
 viewport.scrollLeft=100;viewport.scrollTop=100;pointer('pointerdown',100,100);pointer('pointermove',60,70);pointer('pointerup',60,70);
 check(viewport.scrollLeft===140&&viewport.scrollTop===130,'drag pans both axes');
 dragRoot.querySelector('[data-map-track="1"]').click();check(dragRoot.querySelectorAll('.is-route').length===0,'drag release does not select a track');
 dragRoot.querySelector('[data-map-track="1"]').click();check(dragRoot.querySelectorAll('.is-route').length===3,'ordinary clicks still select tracks');
 const beforeCancel=viewport.scrollLeft;dragTree.cancel();pointer('pointerdown',100,100);pointer('pointermove',0,0);check(viewport.scrollLeft===beforeCancel,'cancellation removes drag listeners');dragHarness.dom.window.close();
 const q=harness(),eight=fixture(),second=q.d.querySelector('#root');let done=0;
 const replay=q.w.TournamentBracket.mount(second,eight,{animate:true,onDone:()=>done++});
 check(second.querySelector('[data-map-sound]').getAttribute('aria-pressed')==='true','replay sound defaults on');
 check(q.delays.includes(3500),'replay holds each result for 3.5 seconds');
 check(second.querySelectorAll('.is-resolved').length===1,'replay reveals one result at a time');
 check(second.querySelector('[data-map-match="7"] [data-map-track="1"]')===null,'final identities wait for feeders');
 for(let i=0;i<15&&done===0;i++)await q.tick();
 check(q.retired.length>0,'cue changes retain an outgoing clip for the shared crossfade');
 check(q.fades.includes(600),'natural completion fades before the podium');
 check(done===1,'podium callback follows final resolution once');
 check(new Set(q.plays.map(a=>a.src)).size<=4,'soundtrack uses at most the four semi-finalists');
 check(q.d.querySelectorAll('audio').length===0,'finished replay removes its player');
 check(q.timers.size===0,'completion leaves no replay timers');replay.cancel();
 const pending=harness(),unfinished=fixture();unfinished.tournament.status='in_progress';const final=unfinished.matches.at(-1);final.status='pending';final.winner_id=null;final.loser_id=null;
 pending.w.TournamentBracket.mount(pending.d.querySelector('#root'),unfinished);pending.d.querySelector('[data-map-track="1"]').click();
 check(pending.d.querySelector('.bracket-inspector').textContent.includes('2 played matches'),'pending qualification is not counted as a played result');
 const b=harness(),blind=fixture();blind.tournament.status='in_progress';blind.tournament.is_blind=1;blind.matches.forEach(m=>{m.status='pending';m.winner_id=null;m.loser_id=null});
 b.w.TournamentBracket.mount(b.d.querySelector('#root'),blind);
 check(!b.d.querySelector('.bracket-nodes').textContent.includes('Track 2'),'unplayed blind identities remain hidden');
 check(!b.d.querySelector('[data-map-track="2"]'),'hidden identities are not interactive');
 const reduced=harness(true);let reducedDone=0;
 reduced.w.TournamentBracket.mount(reduced.d.querySelector('#root'),fixture(),{animate:true,sound:true,onDone:()=>reducedDone++});await Promise.resolve();await Promise.resolve();
 check(reducedDone===1&&reduced.plays.length===0,'reduced motion resolves immediately without soundtrack');
 const skip=harness();let skipped=0;
 skip.w.TournamentBracket.mount(skip.d.querySelector('#root'),fixture(),{animate:true,sound:true,onDone:()=>skipped++});skip.d.querySelector('[data-map-skip]').click();await Promise.resolve();
 check(skipped===1&&skip.timers.size===0&&skip.d.querySelectorAll('audio').length===0,'skip cancels timers and audio before podium');
 const away=harness();const controller=away.w.TournamentBracket.mount(away.d.querySelector('#root'),fixture(),{animate:true,sound:true});controller.cancel();await Promise.resolve();
 check(away.timers.size===0&&away.d.querySelectorAll('audio').length===0,'cancellation silences pending play and retires player');
 const back=harness();back.w.TournamentBracket.mount(back.d.querySelector('#root'),fixture());back.w.dispatchEvent(new back.w.PageTransitionEvent('pagehide',{persisted:true}));back.w.dispatchEvent(new back.w.PageTransitionEvent('pageshow',{persisted:true}));back.d.querySelector('[data-map-track="1"]').click();
 check(back.d.querySelectorAll('.is-route').length===3,'saved bracket stays interactive after browser-back restoration');
 for(const x of [h,q,b,reduced,skip,away,pending,back])x.dom.window.close();
 console.log(checks+' tournament map checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
