/* Shared, PIN-confirmed backup and acknowledged shutdown. */
window.AppStop=(()=>{
 'use strict';
 const {$,esc}=window.SongRankerUI;let integrated=false;
 // Header shutdown remains usable while the collection is loading or unavailable.
 let U={api:async(url,body)=>{const r=await fetch(url,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(data.message||'Could not complete the stop request.');return data},openDialog:(title,html)=>{$('#editor-title').textContent=title;$('#editor-fields').innerHTML=html;if(!$('#editor').open)$('#editor').showModal()}};
 let stopDialog=false,stopState=null,stopTimer=null,stopBusy=false,stopAcknowledged=false;
 function stopResults(s){return `<div class="health-row"><span>Local database backup</span><strong class="${s.backup?'song':''}">${esc(s.backup||'Not completed')}</strong></div><div class="health-row"><span>Git database upload</span><strong class="${s.git?.ok?'song':s.git?.ok===false?'error':''}">${esc(s.git?.message||'Not completed')}</strong></div>`}
 function drawStop(){
  if(!stopDialog)return;const s=stopState,active=['draining','backup','git','ready','stopping'].includes(s.state);
  $('#editor-submit').hidden=true;
  $('#editor-fields').innerHTML=`<div class="catalog-dialog"><p id="stop-message" role="status" aria-live="polite" class="${s.state==='failed'?'error':''}">${esc(s.message||'Save a rotating backup and stop this app.')}</p>${active||s.backup?stopResults(s):''}${!active?`<p>${esc(s.target?.available?`${s.target.branch} → ${s.target.remote}/${s.target.target} · ${s.target.destination}`:s.target?.message||'Git is not configured.')}</p><label class="catalog-check"><input id="stop-sync-git" type="checkbox" ${s.target?.available?'checked':'disabled'}>Upload the database snapshot to Git before stopping</label><div class="field"><label for="stop-pin">Developer PIN</label><input id="stop-pin" type="password" inputmode="numeric" autocomplete="off" maxlength="128"></div><button class="btn danger" type="button" data-stop-prepare ${s.supported?'':'disabled'}>Back up & stop app</button>${!s.supported?'<p class="error">Website shutdown requires the normal python main.py launcher. This server is managed externally.</p>':''}`:''}${s.state==='ready'?'<p class="song">Backup results confirmed. Stopping in four seconds…</p>':''}${active&&s.state!=='stopping'?'<button class="btn" type="button" data-stop-cancel>Cancel stop · keep app running</button>':''}<a class="btn" href="/dev/dashboard?view=export">Review in Dev</a><p id="stop-error" class="error" role="alert" hidden></p></div>`;
 }
 async function openStop(){
  if(stopBusy||window.DevSystem?.busy())return;
  clearTimeout(stopTimer);U.openDialog('Stop app','<p role="status">Checking shutdown and Git status…</p>');stopDialog=true;stopAcknowledged=false;$('#editor-submit').hidden=true;
  try{stopState=await U.api('/api/dev/stop');if(!stopDialog)return;drawStop();if(['draining','backup','git','ready'].includes(stopState.state))pollStop()}
  catch(e){if(stopDialog)$('#editor-fields').innerHTML=`<p class="error" role="alert">${esc(e.message)}</p>`}
 }
 async function prepareStop(){
  if(stopBusy||!stopDialog)return;stopBusy=true;
  const pin=$('#stop-pin')?.value||'',sync=!!$('#stop-sync-git')?.checked;
  if($('#stop-pin'))$('#stop-pin').value='';const b=$('[data-stop-prepare]');if(b)b.disabled=true;
  try{stopState=await U.api('/api/dev/stop/prepare',{pin,sync_git:sync,review_token:stopState.review_token});if(stopDialog){drawStop();pollStop()}}
  catch(e){if(stopDialog){$('#stop-error').hidden=false;$('#stop-error').textContent=e.message;if(b?.isConnected)b.disabled=false}}
  finally{stopBusy=false}
 }
 async function pollStop(){
  clearTimeout(stopTimer);if(!stopDialog)return;
  try{stopState=await U.api('/api/dev/stop');if(!stopDialog)return;drawStop();
   if(stopState.state==='ready'){stopTimer=setTimeout(confirmStop,4000);return}
   if(['draining','backup','git','stopping'].includes(stopState.state))stopTimer=setTimeout(pollStop,500);
   else if(stopState.state==='stopped')stoppedReceipt();
  }catch(e){if(stopAcknowledged)stoppedReceipt();else if(stopDialog){const n=$('#stop-error');if(n){n.hidden=false;n.textContent=e.message+' Reopen Stop app to check the task.'}}}
 }
 async function confirmStop(){
  if(!stopDialog||stopState.state!=='ready')return;
  if(document.hidden){stopTimer=setTimeout(confirmStop,4000);return}
  try{await U.api('/api/dev/stop/confirm',{job_id:stopState.id});stopAcknowledged=true;stopState.state='stopping';stopState.message='Backups confirmed. Stopping the app…';drawStop();stopTimer=setTimeout(pollStop,500)}
  catch(e){if(stopDialog){$('#stop-error').hidden=false;$('#stop-error').textContent=e.message}}
 }
 function stoppedReceipt(){
  if(!stopDialog)return;clearTimeout(stopTimer);
  $('#editor-fields').innerHTML=`<div class="catalog-dialog"><h3 class="song">Shutdown requested · server connection closed</h3>${stopResults(stopState)}<p>You can close this tab. Run python main.py again to restart the app.</p></div>`;
 }
 async function cancelStop(){
  clearTimeout(stopTimer);if(!stopState?.id)return;
  try{await U.api('/api/dev/stop/cancel',{job_id:stopState.id});if(stopDialog){stopState.message='Cancelling stop…';drawStop();stopTimer=setTimeout(pollStop,300)}}
  catch(e){if(stopDialog){$('#stop-error').hidden=false;$('#stop-error').textContent=e.message}}
 }
 document.addEventListener('visibilitychange',()=>{if(stopDialog&&stopState?.state==='ready'){clearTimeout(stopTimer);if(!document.hidden)stopTimer=setTimeout(confirmStop,4000)}});
 document.addEventListener('submit',e=>{if(stopDialog&&e.target.id==='editor-form'){e.preventDefault();e.stopImmediatePropagation();if($('#stop-pin'))prepareStop()}},true);
 document.addEventListener('close',e=>{if(e.target.id!=='editor'||!stopDialog)return;stopDialog=false;clearTimeout(stopTimer);if(!stopAcknowledged&&['draining','backup','git','ready'].includes(stopState?.state))cancelStop()},true);
 document.addEventListener('click',e=>{const b=e.target.closest('button');if(!U||!b||b.disabled)return;if(b.id==='editor-close'&&!integrated)$('#editor').close();if(b.hasAttribute('data-system-stop'))openStop();if(b.hasAttribute('data-stop-prepare'))prepareStop();if(b.hasAttribute('data-stop-cancel'))cancelStop();});
 return {bindUI:ui=>{U=ui;integrated=true},open:openStop};
})();
