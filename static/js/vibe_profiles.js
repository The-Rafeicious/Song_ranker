/* Independent descriptive cards; Overall and hero playback keep their own owners. */
window.VibeProfiles=(()=>{
 'use strict';
 let active=null,reload=null;
 function mount(info){
  if(!['song','album','artist','tag'].includes(info.kind)||!Number.isSafeInteger(info.id)||info.id<=0)return;
  const anchor=document.querySelector('.profile-key-stats');if(!anchor)return;
  active?.abort();document.querySelector('#profile-vibe')?.remove();
  const panel=document.createElement('section');panel.id='profile-vibe';panel.hidden=true;panel.className='panel profile-mode-panel mode-stats-panel vibe-profile-panel dashboard-surface vibe';panel.setAttribute('aria-labelledby','profile-vibe-title');
  panel.innerHTML='<div class="section-head"><h2 class="vibe" id="profile-vibe-title">Vibe Map</h2><div class="profile-stat-links"><a class="vibe" href="/vibe_map_stats">Stats ↗</a></div></div><div class="vibe-profile-content mode-stats-page"></div>';
  anchor.after(panel);const body=panel.querySelector('.vibe-profile-content');
  async function load(){
   active?.abort();const request=new AbortController();active=request;
   const timeout=setTimeout(()=>request.abort(),15000);
   panel.setAttribute('aria-busy','true');body.innerHTML='<p class="empty" role="status">Loading Vibe Map…</p>';
   try{
    const path=info.kind==='song'?'inspect/'+info.id+'?context=profile':'entity/'+info.kind+'/'+info.id;
    const response=await fetch('/api/vibe-map/'+path,{cache:'no-store',signal:request.signal});
    if(!response.ok)throw Error(response.status===404?'Vibe Map data is no longer available.':'Vibe Map could not load.');
    const data=await response.json();if(request.signal.aborted||!panel.isConnected||active!==request)return;
    panel.hidden=!data.profile_ready;
    if(!data.profile_ready){body.replaceChildren();return;}
    body.innerHTML=data.html; // Same-origin, autoescaped reusable server component.
    if(info.kind==='song')body.querySelector('[data-vibe-song-radar]').innerHTML=window.VibeCharts.radar(data.profile.radar,data.song.title+' · average vibe',true);
   }catch(error){
    if(!panel.isConnected||active!==request)return;
    panel.hidden=false;
    const text=document.createElement('p');text.className='empty';text.setAttribute('role','alert');text.textContent=error.name==='AbortError'?'Vibe Map timed out.':error.message;
    const retry=document.createElement('button');retry.className='btn vibe';retry.type='button';retry.dataset.vibeProfileRetry='';retry.textContent='Retry Vibe Map';body.replaceChildren(text,retry);
   }finally{clearTimeout(timeout);if(active===request){active=null;panel.setAttribute('aria-busy','false')}}
  }
  panel.addEventListener('click',event=>{if(event.target.closest('[data-vibe-profile-retry]'))void load()});
  reload=()=>{if(panel.isConnected)void load()};
  void load();
 }
 window.addEventListener('pagehide',()=>{const request=active;active=null;request?.abort();document.querySelector('#profile-vibe')?.setAttribute('aria-busy','false')});
 window.addEventListener('pageshow',event=>{if(event.persisted)reload?.()});
 return Object.freeze({mount});
})();
