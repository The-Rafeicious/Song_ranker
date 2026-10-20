/* Tag/preview workbench. Shared catalogue, media and JSON helpers remain owners. */
window.DevTags=(()=>{
 'use strict';
 const {$,$$,esc}=window.SongRankerUI,P=()=>window.PreviewPlayback;
 const norm=v=>String(v??'').normalize('NFKC').toLocaleLowerCase().replace(/\s+/g,' ').trim();
 let U,active=false,page=0,selection=new Set(),chosen=new Set(),action='add_tags',newNames='',tagQuery='';
 let query='',status='all',previewFilter='all',artistFilter='',albumFilter='',tagFilter='',tagMatch='has',sort='needs_tags',selectedOnly=false;
 let target=null,bulkDraft=null,dirty=false,pendingTarget=null,review=null,reviewPage=0,request=0,pending=false,busy=false;
 let audio=null,previewId=null,previewState='idle',playRequest=0;
 const bound=new WeakSet(),PAGE=20;
 const songs=()=>U.records('songs'),tags=()=>U.records('tags'),song=id=>songs().find(s=>s.id===Number(id));
 const hasPreview=s=>!!String(s.audio_url||'').trim();
 const tagName=id=>tags().find(t=>t.id===id)?.name||'Missing tag #'+id;
 const names=ids=>ids.map(tagName).join(', ')||'No tags';
 const selectedIds=()=>target?[target]:[...selection].sort((a,b)=>a-b);
 const LIMIT=8;
 function tagCapacity(){
  const keys=new Map(tags().map(t=>[t.id,norm(t.name)])),byId=new Map(songs().map(s=>[s.id,s]));
  const wanted=new Set([...chosen].map(id=>keys.get(id)).concat(action==='remove_tags'?[]:newNames.split(',').map(name=>norm(name.trim().replace(/^#+/,'')))).filter(Boolean));
  const current=(selectedIds().length?selectedIds():[null]).map(id=>new Set((byId.get(id)?.tag_ids||[]).map(id=>keys.get(id))));
  const counts=current.map(row=>action==='replace_tags'?wanted.size:action==='remove_tags'?[...row].filter(name=>!wanted.has(name)).length:new Set([...row,...wanted]).size);
  const over=action==='remove_tags'?0:counts.filter(n=>n>LIMIT).length;
  const canAdd=id=>action==='remove_tags'||(!over&&(wanted.has(keys.get(id))||(action==='replace_tags'?wanted.size<LIMIT:current.every((row,i)=>counts[i]<LIMIT||row.has(keys.get(id))))));
  return {counts,over,canAdd};
 }
 function overLimit(){return tagCapacity().over>0}

 function matches(){
  const terms=norm(query).split(' ').filter(Boolean);
  return songs().filter(s=>terms.every(q=>norm([s.title,s.artist,s.album,s.tag_names,'#'+s.id].join(' ')).includes(q))
   &&(status==='all'||(status==='untagged'?!s.tag_ids.length:s.tag_ids.length>0))
   &&(previewFilter==='all'||(previewFilter==='has'?hasPreview(s):!hasPreview(s)))
   &&(!artistFilter||s.artist_ids.includes(Number(artistFilter)))&&(!albumFilter||s.album_id===Number(albumFilter))
   &&(!tagFilter||(tagMatch==='has')===s.tag_ids.includes(Number(tagFilter)))&&(!selectedOnly||selection.has(s.id)))
   .sort((a,b)=>(sort==='needs_tags'?a.tag_ids.length-b.tag_ids.length:sort==='most_tags'?b.tag_ids.length-a.tag_ids.length:0)
    ||(sort==='artist'?a.artist.localeCompare(b.artist):sort==='album'?a.album.localeCompare(b.album):0)
    ||a.title.localeCompare(b.title)||a.id-b.id);
 }
 function message(text,error=false){const n=$('#tag-message');if(n){n.textContent=text;n.classList.toggle('error',error)}}
 function invalidate(){++request;pending=false;review=null;renderReview();drawButtons()}
 function stats(){
  const all=songs();$('#tag-stats').innerHTML=`<div class="joined-metrics" data-columns="3">${[[all.length,'Songs'],[all.filter(s=>!s.tag_ids.length).length,'Untagged'],[all.filter(hasPreview).length,'With previews']].map(([n,label])=>`<div><b>${n}</b><span>${label}</span></div>`).join('')}</div>`;
 }
 function options(type,value,label){return `<option value="">${label}</option>`+U.records(type).slice().sort((a,b)=>a.name.localeCompare(b.name)||a.id-b.id).map(r=>`<option value="${r.id}" ${String(r.id)===value?'selected':''}>${esc(r.name)} (${r.song_count})</option>`).join('')}
 function render(){
  stopPreview(true);active=true;
  U.root().innerHTML=U.title('Tag & preview workbench')+`<div class="tag-workbench">
   <section class="panel dashboard-surface"><div id="tag-stats"></div>
    <form id="tag-filters"><div class="tag-filters tag-filter-primary"><label>Find songs<input id="tag-query" type="search" value="${esc(query)}" placeholder="Title, artist, album, tag or #ID…"></label>
    <label>Tags<select id="tag-status"><option value="all">All songs</option><option value="untagged">Untagged</option><option value="tagged">Has tags</option></select></label>
    <label>Preview<select id="tag-preview-filter"><option value="all">Any preview status</option><option value="has">Has preview</option><option value="missing">Missing preview</option></select></label>
    <label>Sort<select id="tag-sort"><option value="needs_tags">Fewest tags first</option><option value="most_tags">Most tags first</option><option value="title">Song title</option><option value="artist">Artist</option><option value="album">Album</option></select></label></div>
    <details class="tag-extra-filters" ${artistFilter||albumFilter||tagFilter?'open':''}><summary>Artist, release & tag filters <span id="tag-filter-count"></span></summary><div class="tag-filters">
    <label>Artist<select id="tag-artist">${options('artists',artistFilter,'All artists')}</select></label>
    <label>Album / Single<select id="tag-album">${options('albums',albumFilter,'All releases')}</select></label>
    <label>Tag<select id="tag-filter">${options('tags',tagFilter,'Any tag')}</select></label>
    <label>Tag match<select id="tag-match"><option value="has">Has this tag</option><option value="missing">Missing this tag</option></select></label></div></details>
    <div class="tag-toolbar"><button class="btn" type="button" data-tags-reset-filters>Clear filters</button></div></form>
    <div class="tag-toolbar"><button class="btn" type="button" data-tags-page-select>Select this page</button><button class="btn" type="button" data-tags-all-select>Select all matches</button><button class="btn" type="button" data-tags-clear>Clear selection</button><label class="tag-check"><input id="tag-selected-only" type="checkbox" ${selectedOnly?'checked':''}>Selected only</label></div>
    <p id="tag-count" role="status" aria-live="polite"></p>
   </section>
   <section class="panel dashboard-surface"><div class="section-head"><h3>Songs</h3></div><div id="tag-song-rows" tabindex="0" role="region" aria-label="Matching songs"></div><div class="tag-toolbar"><button class="btn" type="button" data-tags-page="-1">Previous page</button><span id="tag-page-label"></span><button class="btn" type="button" data-tags-page="1">Next page</button></div></section>
   <section class="panel tag-player dashboard-surface" aria-label="Workbench preview player"><div id="tag-now-playing"><p class="muted">Choose a Preview or Tag & listen button. Nothing plays automatically.</p></div>
    <div class="tag-toolbar"><button class="btn" type="button" data-tags-preview-step="-1">Previous preview</button><button class="btn" type="button" data-tags-player-toggle disabled>Play preview</button><button class="btn" type="button" data-tags-stop disabled>Stop</button><button class="btn" type="button" data-tags-preview-step="1">Next preview</button></div><audio id="tag-audio" preload="none"></audio></section>
   <section class="panel tag-editor dashboard-surface" aria-labelledby="tag-edit-title"><div class="section-head"><h3 id="tag-edit-title">Tags for selection</h3><button class="btn" type="button" data-tags-bulk-scope hidden>Use selection</button></div><p id="tag-edit-context"></p>
    <div id="tag-discard" class="tag-discard" hidden></div>
    <form id="tag-edit-form"><div class="tag-edit-fields"><label>Change<select id="tag-action"><option value="add_tags">Add tags; keep other tags</option><option value="remove_tags">Remove chosen tags</option><option value="replace_tags">Replace all tags</option></select></label>
    <label>Find a tag<input type="search" id="tag-choice-query" value="${esc(tagQuery)}" placeholder="Name or description…"></label></div><p id="tag-chosen-count" class="muted"></p><p id="tag-limit-status" role="status" aria-live="polite"></p><div id="tag-choices" class="tag-choices"></div>
    <label class="tag-new">New tags, separated by commas<input id="tag-new-names" value="${esc(newNames)}" placeholder="e.g. Road trip, Late night"><span class="muted">Existing names are reused. New names are created only when the reviewed changes save.</span></label>
    <div class="tag-toolbar"><button class="btn primary" type="submit" id="tag-review-button">Review tag changes</button><button class="btn" type="button" data-tags-reset-draft>Reset choices</button></div></form>
    <p id="tag-message" role="status" aria-live="polite"></p><div id="tag-review"></div>
   </section>

  </div>`;
  for(const [id,value] of [['tag-status',status],['tag-preview-filter',previewFilter],['tag-match',tagMatch],['tag-sort',sort],['tag-action',action]])$('#'+id).value=value;
  audio=$('#tag-audio');bindAudio(audio);stats();renderRows();renderEditor();renderReview();drawPlayer();
 }
 function renderRows(){
  if(!active||!$('#tag-song-rows'))return;
  const existing=new Set(songs().map(s=>s.id));selection=new Set([...selection].filter(id=>existing.has(id)));
  const rows=matches();page=Math.min(page,Math.max(0,Math.ceil(rows.length/PAGE)-1));const visible=rows.slice(page*PAGE,(page+1)*PAGE),matching=new Set(rows.map(s=>s.id));
  const hidden=[...selection].filter(id=>!matching.has(id)).length;
  const advanced=[artistFilter,albumFilter,tagFilter].filter(Boolean).length;if($('#tag-filter-count'))$('#tag-filter-count').textContent=advanced?'· '+advanced+' active':'';
  $('#tag-count').textContent=`${rows.length} matching · ${selection.size} selected${hidden?' · '+hidden+' outside this filter':''}`;
  $('[data-tags-all-select]').textContent=`Select all ${rows.length} matches`;
  $('#tag-song-rows').innerHTML=visible.map(s=>`<article class="tag-song-row ${previewId===s.id?'tag-current':''}" data-tag-song="${s.id}">
   <label class="tag-select"><input type="checkbox" data-tags-select="${s.id}" ${selection.has(s.id)?'checked':''} aria-label="Select ${esc(s.title)}"></label><div class="tag-art">${U.artwork(s)}</div>
   <div class="tag-copy"><a class="song" href="/song/${s.id}" title="${esc(s.title)}">${esc(s.title)}</a><p class="artist" title="${esc(s.artist)}">${esc(s.artist)}</p><p class="album" title="${esc(s.album)}">${esc(s.album||'No release')}</p><p class="tag" title="${esc(names(s.tag_ids))}">${esc(names(s.tag_ids))}</p><small>#${s.id} · ${s.tag_ids.length} tags · ${hasPreview(s)?'Preview available':'No preview URL'}</small></div>
   <div class="tag-row-actions"><button class="btn" type="button" data-tags-play="${s.id}" ${hasPreview(s)?'':'disabled'} aria-pressed="${previewId===s.id&&previewState==='playing'}">${previewId===s.id&&previewState==='playing'?'Pause':'Preview'}</button><button class="btn" type="button" data-tags-edit="${s.id}">${hasPreview(s)?'Tag & listen':'Tag song'}</button><button class="btn" type="button" data-catalog-source="${s.id}">Source</button></div></article>`).join('')||'<div class="empty">No matching songs. Try clearing a filter.</div>';
  $('#tag-page-label').textContent=`Page ${rows.length?page+1:0} / ${Math.ceil(rows.length/PAGE)}`;
  $('[data-tags-page="-1"]').disabled=page===0;$('[data-tags-page="1"]').disabled=(page+1)*PAGE>=rows.length;
  drawContext();drawButtons();drawPlayer();
 }
 function drawContext(){
  if(!active||!$('#tag-edit-context'))return;
  const item=song(target);
  $('#tag-edit-title').textContent=item?'Tags for '+item.title:'Tags for selection';
  $('#tag-edit-context').textContent=item?`${item.artist} · ${item.album||'No release'} · #${item.id} · Current: ${names(item.tag_ids)}`:`${selection.size} selected songs. Use the checkboxes or Select all matches.`;
  $('[data-tags-bulk-scope]').hidden=!target;$('[data-tags-bulk-scope]').textContent=`Use ${selection.size} selected songs`;
 }
 function renderEditor(){
  if(!active||!$('#tag-action'))return;
  $('#tag-action').value=action;$('#tag-choice-query').value=tagQuery;$('#tag-new-names').value=newNames;
  drawContext();renderChoices();drawButtons();
 }
 function renderChoices(){
  if(!active||!$('#tag-choices'))return;
  chosen=new Set([...chosen].filter(id=>tags().some(t=>t.id===id)));
  const found=tags().filter(t=>norm(t.name+' '+(t.description||'')).includes(norm(tagQuery))).sort((a,b)=>Number(chosen.has(b.id))-Number(chosen.has(a.id))||a.name.localeCompare(b.name)||a.id-b.id);
  $('#tag-chosen-count').textContent=`${chosen.size} tags chosen · ${found.length} shown${target?' · Replace starts with the song’s current tags':''}`;
  $('#tag-choices').innerHTML=found.map(t=>`<label class="tag-choice"><input type="checkbox" data-tags-choice="${t.id}" ${chosen.has(t.id)?'checked':''}><span><b class="tag">${esc(t.name)}</b><small>${esc(t.description||'No description')}</small></span><small>${t.song_count} songs</small></label>`).join('')||'<p class="empty">No matching tags. Add a new name below.</p>';
  drawButtons();
 }
 function drawButtons(){
  if(!active||!$('#tag-review-button'))return;
  $$('#tag-edit-form input, #tag-edit-form select, [data-tags-select], [data-tags-choice]').forEach(n=>n.disabled=busy);
  $('#tag-new-names').disabled=busy||action==='remove_tags';
  const capacity=tagCapacity(),{counts,over}=capacity;
  $('#tag-limit-status').textContent=over?`Over the 8-tag limit on ${over} song${over===1?'':'s'}. Remove tags or use Replace.`:`Up to ${Math.max(0,...counts)} / 8 tags per song after this change`;
  $('#tag-limit-status').classList.toggle('error',over>0);
  $$('[data-tags-choice]').forEach(n=>n.disabled=busy||(!n.checked&&!capacity.canAdd(Number(n.dataset.tagsChoice))));
  $('#tag-review-button').disabled=busy||pending||!selectedIds().length||overLimit();
  $('#tag-review-button').textContent=pending?'Preparing review…':target?'Review this song’s tags':'Review tag changes';
  $$('[data-tags-apply], [data-tags-reset-draft], [data-tags-bulk-scope], [data-tags-edit], [data-tags-page-select], [data-tags-all-select], [data-tags-clear]').forEach(n=>n.disabled=busy);
 }
 function renderReview(){
  if(!active||!$('#tag-review'))return;
  if(!review){$('#tag-review').innerHTML='';return}
  const r=review;reviewPage=Math.min(reviewPage,Math.max(0,Math.ceil(r.rows.length/PAGE)-1));
  const badges=list=>list.length?list.map(t=>`<span class="tag" title="${esc(t.description||t.name)}"># ${esc(t.name)}</span>`).join(' '):'<span class="muted">No tags</span>';
  $('#tag-review').innerHTML=`<section class="tag-review"><h3>Review before saving</h3><p><strong>${r.changed_songs} songs change</strong> · ${r.unchanged_songs} unchanged · ${r.added_links} tags added · ${r.removed_links} removed</p>${r.new_tags.length?`<p>New tag names: <strong class="tag">${esc(r.new_tags.join(', '))}</strong></p>`:''}${r.action==='replace_tags'?'<p class="tag-replace-note">Replace removes every tag not shown in After for each reviewed song.</p>':''}
   ${r.rows.slice(reviewPage*PAGE,(reviewPage+1)*PAGE).map(row=>`<article class="tag-review-row"><strong class="song">${esc(row.title)} <small>#${row.song_id}</small></strong><p class="artist">${esc(row.artist)}</p><p class="album">${esc(row.album||'No release')}</p><div class="tag-diff"><div><b>Before</b><p>${badges(row.before)}</p></div><div><b>After</b><p>${badges(row.after)}</p></div></div>${!row.added.length&&!row.removed.length?'<small class="muted">Unchanged</small>':''}</article>`).join('')}
   <div class="tag-toolbar"><button class="btn" type="button" data-tags-review-page="-1" ${reviewPage?'':'disabled'}>Previous review page</button><span>${reviewPage+1} / ${Math.max(1,Math.ceil(r.rows.length/PAGE))}</span><button class="btn" type="button" data-tags-review-page="1" ${(reviewPage+1)*PAGE>=r.rows.length?'disabled':''}>Next review page</button></div>
   <div class="tag-toolbar"><button class="btn primary" type="button" data-tags-apply ${busy?'disabled':''}>${r.changed_songs?'Save tags':'Confirm no changes'}</button><button class="btn" type="button" data-tags-cancel-review>Back to choices</button></div></section>`;
 }
 async function reviewChanges(){
  if(!active||busy||pending)return;
  if(overLimit()){message('A song can have at most 8 tags. Remove tags or use Replace.',true);return}
  const ids=selectedIds();if(!ids.length){message('Select a song or a group first.',true);return}
  const serial=++request;pending=true;review=null;renderReview();drawButtons();message('Checking current song tags…');
  try{
   const r=await U.api('/api/dev/tags/review',{song_ids:ids,action,tag_ids:[...chosen],new_tags:action==='remove_tags'?[]:newNames.split(',').map(t=>t.trim()).filter(Boolean)});
   if(serial!==request||!active)return;
   review=r;reviewPage=0;message('Review the Before and After tags, then save.');renderReview();
  }catch(e){if(serial===request&&active)message(e.message,true)}
  finally{if(serial===request){pending=false;drawButtons()}}
 }
 async function apply(){
  if(!active||!review||busy)return;
  const accepted=review;busy=true;drawButtons();message('Saving reviewed tags…');let result;
  try{result=await U.api('/api/dev/tags/apply',{review_token:accepted.review_token})}
  catch(e){if(e.status===409)invalidate();if(active)message(e.message,true);else U.toast(e.message);busy=false;drawButtons();return}
  // A failed refresh is reported separately from the successful database save.
  invalidate();let refreshed=true;
  try{await U.refresh()}catch(e){refreshed=false;U.toast(result.message+' Reload to refresh the catalogue.')}
  if(refreshed){
   if(target&&song(target)){chosen=new Set(song(target).tag_ids);newNames='';dirty=false}
   else{
    // Recover canonical target IDs even when the first successful reply was lost.
    chosen=new Set((accepted.target_tags||[]).map(t=>t.id||tags().find(x=>norm(x.name)===norm(t.name))?.id).filter(Boolean));
    newNames='';dirty=false;
   }
   if(active){stats();renderRows();renderEditor();drawPlayer();message(result.message)}else U.toast(result.message);
  }
  busy=false;drawButtons();
 }
 function resetDraft(){
  if(busy)return;invalidate();chosen=new Set(target?(song(target)?.tag_ids||[]):[]);action=target?'replace_tags':'add_tags';newNames='';dirty=false;pendingTarget=null;
  $('#tag-discard').hidden=true;renderEditor();message('Choices reset.');
 }
 function focusSong(id,discard=false){
  if(busy||!song(id))return;
  if(!active)U.navigate();
  if(dirty&&!discard&&target!==id){pendingTarget=id;$('#tag-discard').hidden=false;$('#tag-discard').innerHTML=`<p>Unsaved tag choices. Review them, or discard them to open <strong>${esc(song(id).title)}</strong>.</p><button class="btn" type="button" data-tags-discard-open>Discard choices & open song</button>`;return}
  if(target!==id){
   if(!target)bulkDraft=discard?null:{chosen:new Set(chosen),action,newNames};
   target=id;action='replace_tags';chosen=new Set(song(id).tag_ids);newNames='';dirty=false;pendingTarget=null;invalidate();$('#tag-discard').hidden=true;renderEditor();message('Choose tags, then review. Other songs are unaffected.');
  }
  if(hasPreview(song(id)))startPreview(id,true);
  else{stopPreview();if(audio){audio.removeAttribute('src');audio.load()}previewId=id;previewState='missing';drawPlayer();message('No preview URL for this song. You can still tag it or check Source.')}
  $('#tag-edit-title')?.scrollIntoView?.({block:'nearest'});
 }
 function useSelection(){
  if(busy)return;
  if(dirty){message('Review this song’s changes or reset choices before using the bulk selection.',true);return}
  target=null;chosen=bulkDraft?.chosen||new Set();action=bulkDraft?.action||'add_tags';newNames=bulkDraft?.newNames||'';bulkDraft=null;invalidate();renderEditor();message('Editing the selected group.');
 }
 function bindAudio(node){
  if(!node||bound.has(node))return;bound.add(node);P()?.bind(node);
  for(const event of ['play','pause','ended','error'])node.addEventListener(event,()=>{
   if(node!==audio)return;previewState=event==='play'?'playing':event==='ended'?'finished':event==='error'?'error':'paused';drawPlayer();
   if(event==='error')message('This preview could not play. Try again or review its Apple source.',true);
  });
 }
 function drawPlayer(){
  if(!active||!$('#tag-now-playing'))return;
  const s=song(previewId),playing=previewState==='playing',loading=previewState==='loading';
  if(s)$('#tag-now-playing').innerHTML=`<div class="tag-player-copy"><strong class="song" title="${esc(s.title)}">${esc(s.title)}</strong><span class="artist">${esc(s.artist)}</span><span class="tag">${esc(names(s.tag_ids))}</span><small role="status">${esc({playing:'Playing',loading:'Loading preview…',paused:'Paused',finished:'Preview finished',error:'Preview unavailable',missing:'No preview URL — check Source',idle:'Stopped'}[previewState])}</small></div>`;
  const b=$('[data-tags-player-toggle]');b.disabled=!s||!hasPreview(s);b.textContent=loading?'Cancel loading':playing?'Pause preview':'Play preview';b.setAttribute('aria-pressed',String(playing));$('[data-tags-stop]').disabled=!s||!hasPreview(s);
  const available=matches().some(hasPreview);$$('[data-tags-preview-step]').forEach(n=>n.disabled=!available);
  $$('[data-tags-play]').forEach(n=>{const own=Number(n.dataset.tagsPlay)===previewId;n.setAttribute('aria-pressed',String(own&&playing));n.textContent=own&&loading?'Cancel loading':own&&playing?'Pause':'Preview'});
  $$('[data-tag-song]').forEach(n=>n.classList.toggle('tag-current',Number(n.dataset.tagSong)===previewId));
 }
 async function startPreview(id,force=false){
  if(!active||!hasPreview(song(id)))return;
  if(previewId===id&&['playing','loading'].includes(previewState)){
   if(!force)stopPreview();return;
  }
  const serial=++playRequest;previewId=id;previewState='loading';
  const s=song(id),url=P()?.source(id,s.audio_url)||s.audio_url;
  if(!audio?.isConnected)return;
  if(audio.getAttribute('src')!==url){if(P())audio=P().replace(audio,url);else{audio.pause();audio.src=url}}
  if(audio.ended)audio.currentTime=0;bindAudio(audio);drawPlayer();
  try{await(P()?P().play(audio):audio.play());if(serial!==playRequest||!active)return;previewState='playing';drawPlayer()}
  catch(e){if(serial!==playRequest||!active)return;previewState=e.name==='AbortError'?'idle':'error';drawPlayer();if(e.name!=='AbortError')message(e.name==='NotAllowedError'?'Press Play preview to allow audio in this browser.':e.message||'Preview could not play. Try again or check Source.',true)}
 }
 function stopPreview(release=false){
  ++playRequest;
  if(audio){if(P())P().stopAll();else audio.pause();if(release){if(P())P().release(audio);else{audio.removeAttribute('src');audio.load()};audio=null;previewId=null}}
  previewState='idle';drawPlayer();
 }
 function stepPreview(direction){
  const available=matches().filter(hasPreview);if(!available.length)return;
  const i=available.findIndex(s=>s.id===previewId),next=i<0?(direction>0?0:available.length-1):(i+direction+available.length)%available.length;startPreview(available[next].id,true);
 }
 function viewChanged(next){if(active&&next!=='tag_workbench'){stopPreview(true);active=false;invalidate();pendingTarget=null}}
 async function reviewSelection(ids,kind,tagIds){
  if(busy)return;selection=new Set(ids);target=null;chosen=new Set(tagIds);action=kind;newNames='';dirty=false;bulkDraft=null;U.navigate();return reviewChanges();
 }
 function filterChanged(){page=0;renderRows();drawPlayer()}
 document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!U||!b||b.disabled)return;
  if(b.dataset.tagsEdit){focusSong(Number(b.dataset.tagsEdit));return}
  if(!active)return;
  if(b.dataset.tagsPlay)startPreview(Number(b.dataset.tagsPlay));
  if(b.hasAttribute('data-tags-player-toggle')&&previewId)startPreview(previewId);
  if(b.hasAttribute('data-tags-stop'))stopPreview();
  if(b.dataset.tagsPreviewStep)stepPreview(Number(b.dataset.tagsPreviewStep));
  if(b.dataset.tagsPage){page+=Number(b.dataset.tagsPage);renderRows()}
  if(b.dataset.tagsReviewPage){reviewPage+=Number(b.dataset.tagsReviewPage);renderReview()}
  if(b.hasAttribute('data-tags-page-select')||b.hasAttribute('data-tags-all-select')){const rows=matches();(b.hasAttribute('data-tags-all-select')?rows:rows.slice(page*PAGE,(page+1)*PAGE)).forEach(s=>selection.add(s.id));if(!target)invalidate();renderRows()}
  if(b.hasAttribute('data-tags-clear')){selection.clear();if(!target)invalidate();renderRows()}
  if(b.hasAttribute('data-tags-reset-filters')){
   query='';status=previewFilter='all';artistFilter=albumFilter=tagFilter='';tagMatch='has';sort='needs_tags';selectedOnly=false;
   for(const [id,value] of [['tag-query',query],['tag-status',status],['tag-preview-filter',previewFilter],['tag-artist',artistFilter],['tag-album',albumFilter],['tag-filter',tagFilter],['tag-match',tagMatch],['tag-sort',sort]])$('#'+id).value=value;
   $('#tag-selected-only').checked=false;filterChanged();
  }
  if(b.hasAttribute('data-tags-reset-draft'))resetDraft();
  if(b.hasAttribute('data-tags-cancel-review')){invalidate();message('Adjust the choices, then review again.')}
  if(b.hasAttribute('data-tags-apply'))apply();
  if(b.hasAttribute('data-tags-bulk-scope'))useSelection();
  if(b.hasAttribute('data-tags-discard-open'))focusSong(pendingTarget,true);
 });
 document.addEventListener('input',e=>{
  if(!active)return;const n=e.target;
  if(n.id==='tag-query'){query=n.value;filterChanged()}
  if(n.id==='tag-choice-query'){tagQuery=n.value;renderChoices()}
  if(n.id==='tag-new-names'){newNames=n.value;dirty=true;invalidate()}
 });
 document.addEventListener('change',e=>{
  if(!active||busy)return;const n=e.target;
  if(n.dataset.tagsSelect){n.checked?selection.add(Number(n.dataset.tagsSelect)):selection.delete(Number(n.dataset.tagsSelect));if(!target)invalidate();renderRows()}
  if(n.dataset.tagsChoice){const id=Number(n.dataset.tagsChoice);if(n.checked&&!tagCapacity().canAdd(id)){n.checked=false;message('A song can have at most 8 tags.',true);return}n.checked?chosen.add(id):chosen.delete(id);dirty=true;invalidate();renderChoices()}
  if(n.id==='tag-action'){action=n.value;dirty=true;invalidate();drawButtons()}
  if(n.id==='tag-selected-only'){selectedOnly=n.checked;filterChanged()}
  if(n.id==='tag-status'){status=n.value;filterChanged()}
  if(n.id==='tag-preview-filter'){previewFilter=n.value;filterChanged()}
  if(n.id==='tag-artist'){artistFilter=n.value;filterChanged()}
  if(n.id==='tag-album'){albumFilter=n.value;filterChanged()}
  if(n.id==='tag-filter'){tagFilter=n.value;filterChanged()}
  if(n.id==='tag-match'){tagMatch=n.value;filterChanged()}
  if(n.id==='tag-sort'){sort=n.value;filterChanged()}
 });
 document.addEventListener('submit',e=>{if(e.target.id==='tag-edit-form'){e.preventDefault();reviewChanges()}if(e.target.id==='tag-filters'){e.preventDefault();filterChanged()}});
 window.addEventListener('pagehide',()=>viewChanged(''));
 function openFilter(kind){
  if(busy)return;query='';status=kind==='untagged'?'untagged':'all';previewFilter=kind==='missing'?'missing':'all';
  artistFilter=albumFilter=tagFilter='';tagMatch='has';sort='needs_tags';selectedOnly=false;page=0;U.navigate();
 }
 function resetAfterRestore(){
  stopPreview(true);selection.clear();chosen.clear();target=bulkDraft=pendingTarget=review=null;dirty=pending=false;
  action='add_tags';newNames=tagQuery=query='';status=previewFilter='all';artistFilter=albumFilter=tagFilter='';tagMatch='has';sort='needs_tags';selectedOnly=false;++request;page=0;
 }
 return {bindUI:ui=>U=ui,render,viewChanged,focusSong,reviewSelection,openFilter,resetAfterRestore};
})();

