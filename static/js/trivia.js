window.songRankerTriviaLoaded=true;
(async()=>{
const $=s=>document.querySelector(s),root=$('#trivia-root');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const order=['title','artist','album'],names={title:'Song',artist:'Artist',album:'Album'},colours={title:'song',artist:'artist',album:'album'},weights={title:50,artist:20,album:30};
let state,active=false,busy=false,paused=false,tick,nextTimer,anchor=0,baseElapsed=0,generation=0;
const pending=new Map(),animations=new Set();
async function api(path,data){
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
 try{const r=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),signal:controller.signal});let result;
 try{result=await r.json()}catch{throw Error(`Trivia request failed (HTTP ${r.status}). Check the app terminal, then retry.`)}
 if(!r.ok)throw Error(result.message||'Could not save this round.');return result;
 }catch(e){if(e.name==='AbortError')throw Error('Trivia request timed out. Retry the round.');throw e}
 finally{clearTimeout(timeout)}
}
const path=action=>'/api/trivia/'+state.token+'/'+action;
const audio=()=>$('#trivia-audio');
const previewPlay=a=>window.PreviewPlayback?window.PreviewPlayback.play(a):a.play();
const fields=()=>order.filter(f=>state.fields[f]);
function error(e){const n=$('#trivia-error');if(n){n.textContent=e.message;n.hidden=false}}
function volume(){const value=Number($('#volume-range')?.value??.5);if(audio())audio().volume=value}
function remaining(){return Math.max(0,30-baseElapsed-(paused?0:(performance.now()-anchor)/1000))}
function answerLinks(f,v){const links=v.links?.length?v.links:[{name:v.actual,url:f==='title'?'/song/'+state.song_id:f==='album'?'/album/'+encodeURIComponent(v.actual):'/artist/'+encodeURIComponent(v.actual)}];return links.map(link=>`<a class="${colours[f]}" href="${esc(link.url)}" title="${esc(link.name)}">${esc(link.name)}</a>`).join('<span class="muted">, </span>')}
function flip(f,input,v){
 if(input.dataset.graded)return;input.dataset.graded='true';input.value=v.actual||'';
 const host=input.parentElement.querySelector('.answer-flip'),links=input.parentElement.querySelector('.answer-links');
 links.innerHTML=answerLinks(f,v);
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const reveal=()=>{if(!input.isConnected)return;host.hidden=true;links.hidden=false;input.classList.remove('flipping');input.classList.add('linked-answer');input.tabIndex=-1};
 if(reduced){reveal();return}
 host.innerHTML=Array.from(v.actual||'').map((c,i)=>`<span style="--delay:${Math.min(i*45,800)}ms">${esc(c===' '?'\u00a0':c)}</span>`).join('');host.hidden=false;input.classList.add('flipping');
 const timer=setTimeout(()=>{animations.delete(timer);reveal()},1550);animations.add(timer);
}
function sync(s,timing=true){
 if(state?.completed&&!s.completed)return;
 for(const [f,v] of Object.entries(state?.fields||{}))if(v.correct!==null&&s.fields[f]?.correct===null)s.fields[f]=v;
 if(!timing)s={...state,fields:s.fields,round_points:Math.max(state.round_points,s.round_points)};
 state=s;if(timing){baseElapsed=s.elapsed;anchor=performance.now();paused=s.paused}
 $('#trivia-score').textContent=Number(s.score).toFixed(2);$('#trivia-streak').textContent=s.streak+' 🔥';$('#trivia-best').textContent=Number(s.high_score).toFixed(2);$('#trivia-best-streak').textContent=s.high_streak+' 🔥';
 for(const f of fields()){const v=s.fields[f],n=$('#guess-'+f);if(v.correct===null)continue;n.readOnly=true;n.classList.remove('checking');n.classList.add(v.correct?'correct':'wrong');$('#mark-'+f).textContent=v.correct?'✓':'×';flip(f,n,v)}
 $('#round-points').textContent='+'+Number(s.round_points).toFixed(2);
}
function guesses(){return Object.fromEntries(fields().map(f=>[f,$('#guess-'+f).value]))}
function setEnabled(){for(const f of order){const n=$('#guess-'+f);n.disabled=!state.fields[f]||((!active||paused)&&state.fields[f].correct===null)}const b=$('#trivia-start');b.textContent=paused?'Resume':active?'Pause':'Start round';b.disabled=busy||state.completed}
function record(label,id,kind){return `<div class="stat ${kind}"><span class="stat-label">${label}</span><strong class="stat-value" id="${id}"></strong></div>`}
async function load(auto=false){
 clearInterval(tick);clearTimeout(nextTimer);animations.forEach(clearTimeout);animations.clear();audio()?.pause();generation++;pending.clear();active=false;busy=false;paused=false;
 try{
  state=await api('/api/trivia/round');
  root.innerHTML=`<div class="page-head trivia-heading"><h1 class="recognition">Trivia</h1></div><section class="panel recognition-panel trivia-round"><div class="trivia-clock" role="timer"><div><span id="trivia-timer-bar"></span></div><b id="trivia-seconds">30s</b></div><div class="trivia-stage"><div class="trivia-current" aria-label="Current run">${record('Current score','trivia-score','recognition')}${record('Streak','trivia-streak','recognition')}</div><div class="trivia-centre"><button id="trivia-start" class="mystery-cover" aria-label="Start or pause trivia">Start round</button><img id="trivia-cover" class="mystery-cover" alt="Album artwork" hidden><strong class="recognition" id="round-points" aria-live="polite">+0.00</strong></div><div class="trivia-best" aria-label="Personal best">${record('Best score','trivia-best','recognition')}${record('Best streak','trivia-best-streak','recognition')}</div></div><audio id="trivia-audio" src="${esc(window.PreviewPlayback?.source(state.song_id,state.audio_url)||state.audio_url)}" preload="none"></audio><form id="trivia-guesses">${order.map(f=>{const available=!!state.fields[f];return `<div class="field trivia-field ${available?'':'not-applicable'}"><label for="guess-${f}">${names[f]}${available?` <small>${state.album_available?weights[f]:Math.round(weights[f]/.7)}% of round points</small>`:''}</label><div class="guess-wrap"><input id="guess-${f}" name="${f}" autocomplete="off" placeholder="${available?'Guess the '+names[f].toLowerCase()+'…':''}" ${available?'':'disabled aria-label="Album, not applicable"'}><span class="field-mark" id="mark-${f}" aria-live="polite"></span><div class="answer-flip" aria-hidden="true" hidden></div><div class="answer-links" hidden></div></div></div>`}).join('')}</form><p class="error" id="trivia-error" role="alert" hidden></p><div id="trivia-result" aria-live="polite" hidden></div></section>`;
  window.PreviewPlayback?.bind(audio());volume();sync(state);active=state.started&&!state.completed;setEnabled();
  for(const f of fields()){const n=$('#guess-'+f);n.addEventListener('blur',()=>{if(active&&!paused&&n.value.trim())mark(f)});n.addEventListener('keydown',async e=>{if(e.key!=='Enter')return;e.preventDefault();await mark(f);if(!active)return;const next=fields().find(k=>state.fields[k].correct===null);if(next)$('#guess-'+next).focus();else await finish()})}
  $('#trivia-start').onclick=()=>active?pause():start();$('#trivia-guesses').onsubmit=e=>e.preventDefault();
  audio().addEventListener('ended',()=>{if(active&&!paused&&remaining()<=0)finish()});audio().addEventListener('error',()=>{if(active&&!paused)pause();error(Error('Preview unavailable. Try resuming this round.'))});
  tick=setInterval(updateTimer,100);if(active&&!paused){state=await api(path('pause'),{paused:true});sync(state);setEnabled()}if(auto)await start();
 }catch(e){clearInterval(tick);root.innerHTML='<div class="panel recognition-panel trivia-load-error"><p class="error" role="alert">'+esc(e.message)+'</p><button class="btn recognition" id="trivia-retry">Retry trivia ↻</button></div>';$('#trivia-retry').onclick=()=>load(false)}
}
function updateTimer(){if(!active||paused||busy)return;const left=remaining();$('#trivia-seconds').textContent=Math.ceil(left)+'s';$('#trivia-timer-bar').style.width=100*left/30+'%';if(left<=0)finish()}
async function start(){if(busy||state.completed)return;busy=true;setEnabled();try{volume();await previewPlay(audio());audio().pause();const s=await api(path(paused?'pause':'start'),paused?{paused:false}:{});sync(s);active=true;paused=false;await previewPlay(audio());setEnabled();fields().map(f=>$('#guess-'+f)).find(n=>!n.readOnly)?.focus()}catch(e){audio().pause();if(state.started){try{sync(await api(path('pause'),{paused:true}));active=true}catch(_){}}error(e)}finally{busy=false;setEnabled()}}
async function pause(){if(busy||!active)return;if(paused){await start();return}busy=true;audio().pause();try{sync(await api(path('pause'),{paused:true}))}catch(e){error(e)}finally{busy=false;setEnabled()}}
async function mark(f){
 if(!active||paused||busy||state.fields[f].correct!==null||!$('#guess-'+f).value.trim())return;if(pending.has(f))return pending.get(f);
 const token=state.token,gen=generation;$('#guess-'+f).classList.add('checking');
 const job=(async()=>{try{const s=await api('/api/trivia/'+token+'/field',{field:f,guess:$('#guess-'+f).value});if(gen!==generation)return;sync(s,false);if(active&&fields().every(k=>state.fields[k].correct!==null))await finish()}catch(e){if(gen!==generation)return;error(e);$('#guess-'+f).classList.remove('checking')}finally{if(gen===generation)pending.delete(f)}})();pending.set(f,job);return job;
}
async function finish(){
 if(busy||!active||paused)return;const snapshot=guesses();busy=true;audio().pause();setEnabled();
 try{const s=await api(path('finish'),{guesses:snapshot});sync(s);active=false;setEnabled();$('#trivia-start').hidden=true;$('#trivia-cover').src=s.cover_url||'';$('#trivia-cover').hidden=!s.cover_url;if(!s.cover_url){$('#trivia-start').hidden=false;$('#trivia-start').textContent='♫'}$('#trivia-result').hidden=false;$('#trivia-result').innerHTML=`<span class="${s.game_over?'wrong':'recognition'}">${s.game_over?'Streak finished':'Round complete'}</span><button class="btn" id="trivia-next">${s.game_over?'Restart':'Next round'} →</button>`;$('#trivia-next').onclick=()=>load(true);audio().currentTime=0;previewPlay(audio()).catch(()=>{});nextTimer=setTimeout(()=>{audio()?.pause();if(!s.game_over)load(true)},5500)}catch(e){error(e)}finally{busy=false;setEnabled()}
}
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&active){e.preventDefault();pause()}else if(e.key==='Enter'&&!active&&!state?.completed&&!e.target.closest('input,form,a')){e.preventDefault();start()}});
document.addEventListener('input',e=>{if(e.target.id==='volume-range')volume()});
window.addEventListener('pagehide',()=>{clearInterval(tick);clearTimeout(nextTimer);animations.forEach(clearTimeout);audio()?.pause();if(active&&!paused)fetch(path('pause'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paused:true}),keepalive:true}).catch(()=>{})});
await load();
})();
