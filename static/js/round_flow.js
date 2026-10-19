/* Shared result pacing and one speculative JSON question. No scoring or audio. */
window.RoundFlow=(()=>{
 'use strict';
 const key='songRankerPlaySettings',TTL=60000,clock=()=>performance.now();
 const durations={pairResult:[4500,2200],tournamentPoints:[2800,1600],tournamentFirst:[7500,4400],triviaResult:[5500,2800],guessClip:[2800,1700],
  shelfClose:[420,160],shelfTrack:[2600,1000],shelfTransfer:[1250,450],score:[1100,320],triviaFlip:[1550,600]};
 let settings={pace:'standard',prepare:true},entry=null,closed=false;
 const timers=new Set(),aborted=()=>Object.assign(Error('Next round cancelled'),{name:'AbortError'});
 function parse(value){try{const s=JSON.parse(value);return {pace:s?.pace==='quick'?'quick':'standard',prepare:s?.prepare!==false}}catch{return {pace:'standard',prepare:true}}}
 try{settings=parse(localStorage.getItem(key))}catch{}
 const duration=name=>durations[name]?.[settings.pace==='quick'?1:0]??0;
 function paint(){
  document.documentElement.dataset.roundPace=settings.pace;
  document.documentElement.dataset.roundPaused=String(document.hidden);
  const pace=document.getElementById('round-pace'),prepare=document.getElementById('round-prepare'),label=document.getElementById('round-pace-label');
  if(pace)pace.value=settings.pace;if(prepare)prepare.checked=settings.prepare;
  if(label)label.textContent=settings.pace==='quick'?'Quick':'Standard';
  const toggle=document.querySelector('.game-settings > summary');if(toggle){toggle.title='Result speed: '+(settings.pace==='quick'?'Quick':'Standard');toggle.setAttribute('aria-label',toggle.title)}
 }
 function clear(){if(entry){entry.cancelled=true;clearTimeout(entry.timeout);entry.controller.abort();entry=null}}
 function update(next,persist=true){
  settings=parse(JSON.stringify({...settings,...next}));if(!settings.prepare&&entry&&!entry.consumed)clear();
  if(persist)try{localStorage.setItem(key,JSON.stringify(settings))}catch{}
  paint();
 }
 function permitted(){return !closed&&!document.hidden&&settings.prepare&&navigator.onLine!==false&&!navigator.connection?.saveData&&!/^(slow-)?2g$/.test(navigator.connection?.effectiveType||'')}
 function create(name,load,quiet){
  clear();const job={name,quiet,consumed:false,at:clock(),controller:new AbortController(),cancelled:false};entry=job;
  job.timeout=setTimeout(()=>job.controller.abort(),12000);
  job.promise=Promise.resolve().then(()=>{if(job.cancelled||closed)throw aborted();return load(job.controller.signal)})
   .then(value=>{if(job.cancelled||closed)throw aborted();job.at=clock();return value})
   .catch(error=>{if(job.controller.signal.aborted&&!job.cancelled&&!closed)throw Error('Loading the next round timed out. Retry when the connection is ready.');throw error})
   .finally(()=>clearTimeout(job.timeout));
  job.promise.catch(()=>{if(entry===job)entry=null});return job;
 }
 function prepare(name,load){
  if(!permitted()||entry?.consumed)return;
  if(entry?.name===name&&!entry.cancelled&&clock()-entry.at<TTL)return;
  const job=create(name,load,true);job.promise.catch(()=>{});
 }
 async function take(name,load){
  if(closed)throw aborted();
  let job=entry?.name===name&&!entry.cancelled&&clock()-entry.at<TTL?entry:create(name,load,false);
  job.consumed=true;
  try{return await job.promise}
  catch(error){
   if(!job.quiet||closed)throw error;
   job=create(name,load,false);job.consumed=true;return await job.promise;
  }finally{if(entry===job)entry=null}
 }
 function after(callback,ms){
  const task={left:Math.max(0,ms),started:0,id:null,cancel:null};
  task.cancel=()=>{clearTimeout(task.id);task.id=null;timers.delete(task)};
  task.resume=()=>{if(closed||document.hidden||task.id!==null||!timers.has(task))return;task.started=clock();task.id=setTimeout(()=>{task.cancel();callback()},task.left)};
  task.pause=()=>{if(task.id!==null){clearTimeout(task.id);task.id=null;task.left=Math.max(0,task.left-(clock()-task.started))}};
  timers.add(task);task.resume();return task.cancel;
 }
 function positionSettings(){
  const settings=document.querySelector('.game-settings');if(!settings?.open)return;
  const panel=settings.querySelector('.game-settings-body'),rect=settings.querySelector('summary').getBoundingClientRect();if(!panel)return;
  const width=Math.min(300,innerWidth-24),top=Math.max(12,rect.bottom+10);
  Object.assign(panel.style,{width:width+'px',left:Math.max(12,Math.min(rect.right-width,innerWidth-width-12))+'px',top:top+'px',maxHeight:Math.max(80,innerHeight-top-12)+'px'});
 }
 document.addEventListener('toggle',e=>{if(e.target.matches?.('.game-settings'))positionSettings()},true);
 window.addEventListener('resize',positionSettings);window.addEventListener('scroll',positionSettings,{passive:true});
 document.addEventListener('click',e=>{const settings=document.querySelector('.game-settings');if(settings?.open&&!settings.contains(e.target))settings.open=false});
 document.addEventListener('keydown',e=>{const settings=document.querySelector('.game-settings');if(e.key==='Escape'&&settings?.open){e.preventDefault();e.stopPropagation();settings.open=false;settings.querySelector('summary').focus()}},true);
 document.addEventListener('change',e=>{if(e.target.id==='round-pace')update({pace:e.target.value});if(e.target.id==='round-prepare')update({prepare:e.target.checked})});
 window.addEventListener('storage',e=>{if(e.key===key){settings=parse(e.newValue);if(!settings.prepare&&entry&&!entry.consumed)clear();paint()}});
 document.addEventListener('visibilitychange',()=>{
  paint();if(document.hidden){if(entry&&!entry.consumed)clear();for(const task of timers)task.pause()}
  else for(const task of timers)task.resume();
 });
 window.addEventListener('pagehide',()=>{closed=true;clear();for(const task of [...timers])task.cancel()});
 window.addEventListener('pageshow',()=>{closed=false;paint()});
 paint();
 return Object.freeze({duration,prepare,take,after,clear});
})();
