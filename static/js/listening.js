/* Playback-only listening before a submitted answer. Preloads and reveal audio add nothing. */
window.Listening=(()=>{
 'use strict';
 let current=null;const players=new Map();
 const clock=()=>performance.now();
 function flush(audio,now=clock()){
  const p=players.get(audio);if(!p)return;
  const position=Number(audio.currentTime)||0,elapsed=Math.max(0,(now-p.at)/1000),rate=Number(audio.playbackRate)||1;
  let delta=position-p.position;
  if(delta<0&&audio.loop&&Number.isFinite(audio.duration)&&p.position>audio.duration-2)delta=audio.duration-p.position+position;
  if(current&&p.running&&!audio.muted&&audio.volume>0&&current.seconds.has(p.id))current.seconds.set(p.id,current.seconds.get(p.id)+Math.max(0,Math.min(delta,elapsed*rate+.05)));
  p.at=now;p.position=position;
 }
 function bind(audio){
  if(!(audio instanceof HTMLMediaElement))return;
  let id=Number(audio.dataset.songId);
  if(!id)try{id=Number(new URL(audio.currentSrc||audio.getAttribute('src'),location.href).pathname.match(/^\/api\/previews\/(\d+)$/)?.[1])}catch{}
  if(!id||!current?.seconds.has(id))return;
  if(players.has(audio)&&players.get(audio).id!==id){flush(audio);players.delete(audio)}
  if(!players.has(audio))players.set(audio,{id,at:clock(),position:Number(audio.currentTime)||0,running:false});
 }
 function event(e){const a=e.target;bind(a);const p=players.get(a);if(!p)return;flush(a);p.running=e.type==='playing'||(e.type==='timeupdate'&&p.running);}
 for(const name of ['playing','timeupdate','pause','waiting','ended','seeking','emptied','error'])document.addEventListener(name,event,true);
 function start(mode,key,ids){
  if(current?.key===String(key)&&current.mode===mode)return;
  current={mode,key:String(key),at:clock(),seconds:new Map([...new Set(ids.filter(Number.isInteger))].map(id=>[id,0]))};players.clear();
 }
 function sample(){
  if(!current)return undefined;
  const now=clock();for(const a of players.keys())flush(a,now);
  const ms=Math.max(0,Math.min(7200000,now-current.at));
  return {version:1,decision_ms:Math.round(ms),songs:[...current.seconds].map(([song_id,seconds])=>({song_id,seconds:Math.round(Math.min(seconds,ms/1000,7200)*1000)/1000}))};
 }
 return {start,sample};
})();
