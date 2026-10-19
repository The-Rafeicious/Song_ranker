/* Recoverable preference corrections. Reuses the developer dialog/components. */
window.PreferenceAdmin={create(context){
 const {$,esc}=window.SongRankerUI;
 const {api,openDialog,field,toast,requestToken,refresh,hasSong}=context;
 let offset=0,editing=null,busy=false;
 const mode=value=>value==='standard'?'Non-blind':value==='blind'?'Blind':'Unknown';
 const title=song=>song?.title||'Unavailable song';
 async function review(next=offset){
  const data=await api('/api/dev/preferences?limit=25&offset='+Math.max(0,next));offset=data.offset;editing=null;
  const body=data.items.map(item=>{const winner=item.songs.find(s=>s.id===item.winner_id)||item.songs[0],other=item.songs.find(s=>s!==winner)||item.songs[1];return `<div class="health-row"><div class="compact-copy"><strong class="song" title="${esc(title(winner))}">#${item.id} · ${esc(title(winner))}</strong><small title="${esc(title(other))}">vs ${esc(title(other))}</small><small>${esc(mode(item.mode))}${item.origin==='tournament'?' · Tournament #'+esc(item.tournament_id)+' · '+(item.rating_weight===0.5?'Half':'Full')+' Elo influence':''} · ${item.active?'Active':'Voided'} · ${esc(item.created_at||'Date unavailable')}</small></div><button class="btn" type="button" data-preference-edit="${item.id}">Review</button></div>`}).join('')||'<div class="empty">No saved votes</div>';
  openDialog('Saved votes','<div class="preference-admin">'+body+`<div class="preference-pager"><button class="btn" type="button" data-preference-page="${Math.max(0,offset-25)}" ${offset?'':'disabled'}>Previous</button><span>${data.total?offset+1:0}–${Math.min(offset+data.items.length,data.total)} of ${data.total}</span><button class="btn" type="button" data-preference-page="${offset+25}" ${offset+25<data.total?'':'disabled'}>Next</button></div></div>`,'Done');
 }
 async function edit(id){
  const detail=await api('/api/dev/preferences/'+id);editing={...detail,requestToken:requestToken()};
  const current=detail.effective,available=detail.songs.every(song=>hasSong(song.id));
  const original=detail.original;
  const protectedReason=original.origin==='tournament'?'This Elo result follows tournament #'+original.tournament_id+'. Delete/reset that bracket to remove its influence. Ordinary-vote corrections cannot change bracket results.':'The older rating history is protected because its original Elo cannot be reconstructed safely.';
  const actions=[['replace','Set winner / mode'],...(current.active?[['void','Void vote']]:[['restore','Restore vote']])];
  const body=`<div class="preference-admin"><p class="preference-context">${detail.songs.map(song=>`<span class="song">${esc(title(song))}</span>`).join(' vs ')} · ${current.active?'Active':'Voided'}</p><input type="hidden" name="preference_event_id" value="${id}"><div class="form-grid"><div class="field"><label for="preference-action">Action</label><select id="preference-action" name="action">${actions.map(([key,label])=>`<option value="${key}">${label}</option>`).join('')}</select></div><div class="field"><label for="preference-winner">Winner</label><select id="preference-winner" name="winner_id">${detail.songs.map(song=>`<option value="${song.id}" ${song.id===current.winner_id?'selected':''}>${esc(title(song))}</option>`).join('')}</select></div><div class="field"><label for="preference-mode">Mode</label><select id="preference-mode" name="mode"><option value="standard" ${current.mode==='standard'?'selected':''}>Non-blind</option><option value="blind" ${current.mode==='blind'?'selected':''}>Blind</option></select></div>${field('reason','Correction note','','text','maxlength="1000"')}</div><details><summary>Original result and corrections</summary><p>Original winner: <span class="song">${esc(title(detail.songs[0]))}</span> · ${esc(mode(original.mode))}</p>${detail.corrections.map(row=>`<p>#${row.id} · ${esc(row.action)} · ${esc(row.created_at)}${row.reason?' · '+esc(row.reason):''}</p>`).join('')||'<p>No corrections</p>'}</details><div class="table-actions"><button class="btn" type="button" data-preference-back>Back to saved votes</button></div>${available?'':'<p class="dialog-error">A song was removed. Its original vote remains saved; recover the song from backup before restoring this vote.</p>'}`;
  openDialog('Review vote #'+id,body+(detail.correctable?'':'<p class="dialog-error">'+esc(protectedReason)+'</p>')+'</div>','Save correction');$('#editor-submit').disabled=!available||!detail.correctable;
  if(!detail.correctable)for(const id of ['preference-action','preference-winner','preference-mode'])$('#'+id).disabled=true;
 }
 async function save(values){
  if(busy||!editing||Number(values.preference_event_id)!==editing.id)return;
  busy=true;$('#editor-submit').disabled=true;
  try{
   const result=await api('/api/dev/preferences/'+editing.id,{request_token:editing.requestToken,expected_revision:editing.effective.revision,fingerprint:editing.fingerprint,action:values.action,winner_id:Number(values.winner_id),mode:values.mode,reason:values.reason});
   await refresh();await review();toast(result.message);
  }catch(error){const node=$('#editor-error');node.textContent=error.message;node.hidden=false;node.focus()}
  finally{busy=false;$('#editor-submit').disabled=false}
 }
 document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button||busy)return;let action;
  if(button.dataset.preferenceEdit)action=()=>edit(Number(button.dataset.preferenceEdit));
  else if(button.hasAttribute('data-preference-page'))action=()=>review(Number(button.dataset.preferencePage));
  else if(button.hasAttribute('data-preference-back'))action=()=>review();
  if(action){button.disabled=true;action().catch(error=>{button.disabled=false;toast(error.message)})}
 });
 document.addEventListener('change',event=>{if(event.target.id==='preference-action')for(const id of ['preference-winner','preference-mode'])$('#'+id).disabled=event.target.value!=='replace'});
 return {review,edit,save};
}};
