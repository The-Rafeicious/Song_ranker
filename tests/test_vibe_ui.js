/* Continuous placement, recovery, review, visibility and shared preview ownership. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8');
const flush=async()=>{for(let i=0;i<100;i++)await Promise.resolve()};
let count=0;const check=(value,message)=>{assert.ok(value,message);count++};
async function harness(){
 const vc=new VirtualConsole(),errors=[];vc.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(`<body data-page="vibe_map"><div id="vibe-error" hidden><span></span><button id="vibe-retry"></button><button id="vibe-reload"></button></div><div id="vibe-loading"></div><div id="vibe-layout" hidden><section id="vibe-song"></section><section id="vibe-workspace"></section></div></body>`,{url:'http://localhost/vibe-map',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
 const w=dom.window,d=w.document;let now=0,tick,hidden=false,playCount=0,warmCount=0,forgetCount=0,failDraft=false,failAdvance=false,server=null,seq=0;
 Object.defineProperty(w.performance,'now',{value:()=>now});w.setInterval=fn=>{tick=fn;return 1};w.clearInterval=()=>{};
 Object.defineProperty(d,'hidden',{get:()=>hidden});
 const playing=new WeakSet(),ended=new WeakSet();
 Object.defineProperty(w.HTMLMediaElement.prototype,'paused',{get(){return !playing.has(this)}});
 Object.defineProperty(w.HTMLMediaElement.prototype,'ended',{get(){return ended.has(this)}});
 w.HTMLMediaElement.prototype.pause=function(){playing.delete(this);this.dispatchEvent(new w.Event('pause'))};
 w.HTMLMediaElement.prototype.load=function(){};
 const play=audio=>{playCount++;playing.add(audio);ended.delete(audio);audio.dispatchEvent(new w.Event('play'));return Promise.resolve()};
 w.PreviewPlayback={source:(id,url)=>'/api/previews/'+id,bind:()=>{},syncVolume:()=>{},play,
  preloadPair:async audios=>{warmCount+=audios.length},forgetPair:async audios=>{forgetCount+=audios.length;audios.forEach(a=>{a.pause();a.remove()})}};
 const maps=['pace_mood','sound_impact','connection','perspective'].map((id,i)=>({id,title:'Map '+(i+1),x_low:'Low X',x_high:'High X',y_low:'Low Y',y_high:'High Y',x_center:i===3?'Present':null}));
 const newRound=()=>({token:'token-'+(++seq),song:{id:seq,title:'Song '+seq,album:'Album',artist:'Artist',artist_links:[{name:'Artist'}],cover_url:'/art.jpg',audio_url:'https://audio-ssl.itunes.apple.com/test.m4a'},maps,map_index:0,revision:0,status:'active',saved_maps:[],draft:null,remaining_ms:null});
 function summary(){const spokes=Array.from({length:8},(_,i)=>({key:''+i,low:'Sad',high:'Happy',label:'Happy',radius:i/8,value:i-4}));server.summary={selection_radar:{spokes},aggregate:{radar:{spokes},completed_passes:1}};}
 const calls=[];w.fetch=async(url,options={})=>{
  const body=options.body?JSON.parse(options.body):null;calls.push({url,body});let replay=false;
  if(url.endsWith('/round')){if(!server||body.previous_token===server.token)server=newRound();}
  else if(url.endsWith('/draft')){
   if(failDraft){failDraft=false;throw Error('Offline')}
   assert.equal(body.revision,server.revision);server.draft={...body};server.revision++;server.remaining_ms=5000;
  }else if(url.endsWith('/advance')){
   const existing=server.saved_maps.find(p=>p.map_id===body.map_id);
   if(existing?.receipt===body.request_id)replay=true;
   else{
    assert.equal(body.revision,server.revision);
    const saved={...server.draft,receipt:body.request_id};if(existing)server.saved_maps.splice(server.saved_maps.indexOf(existing),1,saved);else{server.saved_maps.push(saved);server.map_index++;}
    server.draft=null;server.revision++;server.remaining_ms=null;
    if(server.map_index===4){server.status='complete';summary();}
   }
   if(failAdvance){failAdvance=false;throw Error('Response lost')}
  }else if(url.includes('/similar/'))return {ok:true,json:async()=>({matches:[1,2].map(i=>({song:{id:i+5,title:'Match '+i,artist:'Artist',cover_url:''},similarity:90-i,shared_maps:4}))})};
  else throw Error('Unexpected '+url);
  return {ok:true,json:async()=>({round:structuredClone(server),replayed:replay})};
 };
 for(const file of ['ui.js','vibe_charts.js','vibe_map.js'])w.eval(read('static/js/'+file));await flush();
 const click=async selector=>{const element=d.querySelector(selector);assert.ok(element,selector);element.click();await flush()};
 const place=async(x=2,y=-3)=>{
  const plane=d.querySelector('#vibe-plane');plane.getBoundingClientRect=()=>({left:0,top:0,width:100,height:100});
  const e=new w.MouseEvent('pointerdown',{bubbles:true,clientX:(x+5)*10,clientY:(5-y)*10,button:0});plane.dispatchEvent(e);
  plane.dispatchEvent(new w.MouseEvent('pointerup',{bubbles:true}));await flush();
 };
 const advance=async(ms=5100)=>{now+=ms;tick();await flush()};
 return {dom,w,d,calls,errors,click,place,advance,setHidden:value=>{hidden=value;d.dispatchEvent(new w.Event('visibilitychange'))},end:()=>{const a=d.querySelector('audio');playing.delete(a);ended.add(a);a.dispatchEvent(new w.Event('ended'))},failDraft:()=>{failDraft=true},failAdvance:()=>{failAdvance=true},stats:()=>({playCount,warmCount,forgetCount,server})};
}
(async()=>{
 const h=await harness(),{d}=h;
 check(d.querySelector('#vibe-back').disabled&&d.querySelector('#vibe-forward').disabled&&d.querySelector('#vibe-finish').disabled,'incomplete maps cannot be skipped or finished');
 check(h.stats().warmCount===1,'current preview automatically warmed once');
 const audio=d.querySelector('audio');await h.click('#vibe-play');check(!audio.paused,'preview plays');
 h.setHidden(true);check(!audio.paused,'tab change keeps current clip playing');h.end();await flush();check(h.stats().playCount===1,'hidden tab never starts a loop');
 h.setHidden(false);await flush();check(h.stats().playCount===2,'return resumes requested loop');
 await h.click('#vibe-play');h.setHidden(true);h.setHidden(false);await flush();check(h.stats().playCount===2,'explicit pause survives tab return');
 h.failDraft();await h.place(1.2345,-2.3456);
 check(!d.querySelector('#vibe-error').hidden&&d.querySelector('#vibe-forward').disabled,'failed draft remains visible and blocks navigation');
 await h.click('#vibe-retry');
 const drafts=h.calls.filter(c=>c.url.endsWith('/draft'));
 check(drafts[0].body.request_id===drafts[1].body.request_id,'retry uses the same idempotent draft');
 check(Math.abs(drafts[1].body.x-1.2345)<1e-12&&Math.abs(drafts[1].body.y+2.3456)<1e-12,'pointer keeps continuous precision');
 check(d.querySelector('#vibe-plane').getAttribute('aria-label').includes('X 1.23'),'accessible position rounds to two decimals');
 check(d.querySelector('#vibe-save-status').closest('#vibe-song'),'save timer is below the song controls');
 check(!d.querySelector('.vibe-hint,input[type=range],#vibe-na,.contour'),'map removes subtitle, sliders, skip and contour circles');
 check(d.querySelector('.vibe-x-pole.low').closest('#vibe-plane'),'X labels sit on the graph beside its axis');
 check(d.querySelector('#vibe-axis-pulse').classList.contains('pulsing'),'pin adjustment pulses the axes');
 h.failAdvance();await h.advance();check(!d.querySelector('#vibe-error').hidden,'lost save acknowledgement exposes retry');
 await h.click('#vibe-retry');check(d.querySelector('.vibe-step').textContent.includes('Map 2'),'idempotent retry advances once');
 const saves=h.calls.filter(c=>c.url.endsWith('/advance'));check(saves[0].body.request_id===saves[1].body.request_id,'advance receipt stable across lost response');
 await h.click('#vibe-back');check(d.querySelector('#vibe-plane').getAttribute('aria-label').includes('X 1.23'),'back arrow restores this round’s pin');
 await h.click('#vibe-forward');
 for(let i=0;i<3;i++){await h.place(0,0);await h.advance();}
 check(!d.querySelector('#vibe-finish').disabled&&!d.querySelector('.vibe-radar'),'all saved maps wait for Finish');
 check(d.querySelector('.vibe-axis-center').textContent==='Present','Perspective labels the present midpoint');
 check(d.querySelector('audio')===audio,'audio element survives every map');
 h.setHidden(true);await h.advance(10000);check(!d.querySelector('.vibe-radar'),'hidden tab does not open results');h.setHidden(false);
 await h.advance(10000);check(!d.querySelector('.vibe-radar'),'results never open automatically');
 await h.click('#vibe-back');await h.place(4,4);await h.advance();
 check(h.stats().server.saved_maps.length===4,'review edits existing map rather than adding another');
 await h.click('#vibe-finish');check(d.querySelectorAll('.vibe-match').length===2,'results show two similarity matches');
 check(d.querySelectorAll('.radar-axis').length===8,'radar retains eight continuous dimensions');
 check(d.querySelector('.vibe-match strong').textContent.includes('4/4 maps'),'similarity displays comparison evidence');
 check(!d.querySelector('.vibe-radar-key,#vibe-edit-results,[data-vibe-next-song]'),'results remove raw figures and duplicate action buttons');
 check(d.querySelector('#vibe-finish').textContent==='Next song →'&&!d.querySelector('#vibe-finish').disabled,'Finish becomes the enabled Next song control');
 await h.click('#vibe-finish');
 check(h.stats().forgetCount===1&&h.stats().warmCount===2,'next song clears old cache before warming new preview');
 check(d.querySelector('audio')!==audio&&d.querySelector('.vibe-step').textContent.includes('Map 1'),'next song starts a fresh player and maps');
 check(h.errors.length===0,'no browser runtime errors');h.dom.window.close();
 const g=await harness();for(let i=0;i<4;i++){await g.place();await g.advance();}await g.advance(5100);check(!g.d.querySelector('.vibe-radar'),'completed song stays on its last map until Finish');await g.click('#vibe-finish');check(!!g.d.querySelector('.vibe-radar'),'Finish opens results explicitly');g.dom.window.close();
 console.log(`Vibe Map UI: ${count} checks passed`);
})().catch(error=>{console.error(error);process.exitCode=1});
