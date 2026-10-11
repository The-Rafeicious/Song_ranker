/* Shared, non-persistent preview feedback. Apple audio is streamed, never saved. */
(()=>{
 const bound=new WeakSet(),problems=new WeakMap();let cooldown=0,blockedMessage='',hideTimer;
 const token=Date.now().toString(36)+'_'+Math.random().toString(36).slice(2);
 const notice=()=>document.getElementById('preview-status');
 function show(message,state='loading',seconds=0){const node=notice();if(!node)return;clearTimeout(hideTimer);node.textContent=message;node.dataset.state=state;node.hidden=false;if(seconds)hideTimer=setTimeout(()=>node.hidden=true,seconds*1000)}
 function paint(audio,state){audio.dataset.previewState=state;document.querySelectorAll('[data-audio]').forEach(button=>{if(button.dataset.audio!==audio.id)return;button.dataset.previewState=state;button.setAttribute('aria-busy',String(state==='loading'||state==='buffering'))})}
 function source(id,url){try{const parsed=new URL(url,location.href),host=parsed.hostname.toLowerCase();if(id&&['https:','http:'].includes(parsed.protocol)&&!parsed.username&&!parsed.password&&['','80','443'].includes(parsed.port)&&(host.endsWith('.itunes.apple.com')||host.endsWith('.mzstatic.com')))return '/api/previews/'+encodeURIComponent(id)+'?play='+token}catch{}return url||''}
 function clipId(audio){return /^\/api\/previews\/(\d+)$/.exec(new URL(audio.getAttribute('src')||'',location.href).pathname)?.[1]}
 async function problem(audio){
  if(problems.has(audio))return problems.get(audio);
  const work=(async()=>{let info={state:'unavailable',message:'Preview could not load. Check the connection or refresh its URL in Dev.',retry_after:0};const id=clipId(audio);
   if(id){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),4000);try{const response=await fetch('/api/previews/'+id+'/status',{signal:controller.signal,cache:'no-store'});if(response.ok){const status=await response.json();if(status.state!=='unknown'&&status.state!=='streaming')info=status;else if(status.state==='streaming')info.message='Preview stream started but could not play. Check the connection or audio format.'}}catch{}finally{clearTimeout(timer)}}
   const seconds=Number(info.retry_after)||0,blocked=['rate_limited','refused','throttled'].includes(info.state)||seconds>0;
   if(blocked){cooldown=Math.max(cooldown,Date.now()+seconds*1000);blockedMessage=info.message||'Preview access paused. Try again shortly.';document.dispatchEvent(new CustomEvent('preview-blocked',{detail:info}))}
   paint(audio,blocked?'blocked':'error');show(info.message||blockedMessage,blocked?'blocked':'error');return {...info,blocked};
  })();problems.set(audio,work);try{return await work}finally{problems.delete(audio)}
 }
 function bind(audio){if(bound.has(audio))return;bound.add(audio);
  audio.addEventListener('loadstart',()=>{if(audio.dataset.previewWanted==='true'){paint(audio,'loading');show('Loading preview…')}});
  audio.addEventListener('waiting',()=>{if(audio.dataset.previewWanted==='true'){paint(audio,'buffering');show('Buffering preview…')}});
  audio.addEventListener('canplay',()=>{if(audio.dataset.previewWanted==='true'){paint(audio,audio.paused?'ready':'playing');show(audio.paused?'Preview ready':'Preview playing','ready',2)}});
  audio.addEventListener('playing',()=>{paint(audio,'playing');show('Preview playing','ready',2)});
  audio.addEventListener('pause',()=>{audio.dataset.previewWanted='false';if(!['blocked','error'].includes(audio.dataset.previewState))paint(audio,'idle')});
  audio.addEventListener('error',()=>{problem(audio)});
 }
 async function play(audio){bind(audio);if(Date.now()<cooldown){paint(audio,'blocked');show(blockedMessage,'blocked');throw Object.assign(Error(blockedMessage),{name:'PreviewBlockedError'})}
  if(audio.error){audio.load()}
  audio.dataset.previewWanted='true';paint(audio,audio.readyState>=2?'ready':'loading');if(audio.readyState<2)show('Loading preview…');
  try{await audio.play();paint(audio,'playing');show('Preview playing','ready',2)}catch(error){if(error.name==='NotAllowedError'){paint(audio,'idle');show('Press a cover or Play previews to start audio.','error');throw error}if(error.name==='AbortError'){paint(audio,'idle');throw error}const info=await problem(audio);if(info.blocked)throw Object.assign(Error(info.message),{name:'PreviewBlockedError'});throw error}
 }
 window.PreviewPlayback={source,bind,play,problem,blocked:()=>Date.now()<cooldown};
 window.addEventListener('pagehide',()=>clearTimeout(hideTimer));
})();
