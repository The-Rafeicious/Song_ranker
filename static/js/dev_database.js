/* Read-only SQLite browser. Object names are selected server-side; no SQL editor. */
window.DevDatabase=(()=>{
 'use strict';const {$,esc}=window.SongRankerUI;
 let U,items=[],chosen='',offset=0,tab='rows',data=null,error='',busy=false,objectQuery='',ticket=0,cellTicket=0;
 const btn=(label,attrs)=>`<button type="button" class="btn" ${attrs}>${label}</button>`;
 function close(){++ticket;++cellTicket;data=null;busy=false;}
 function mount(rows){items=rows;if(!items.some(r=>r.name===chosen))chosen=items.find(r=>r.kind==='table')?.name||'';draw();if(chosen)load()}
 function draw(){const node=$('#system-inventory');if(!node)return;const scroll=node.querySelector('.db-objects')?.scrollTop||0;
  node.innerHTML=`<div class="db-browser"><aside><label>Find an object<input id="db-object-query" type="search" value="${esc(objectQuery)}" placeholder="Table or view…"></label><div class="db-objects">${items.map(r=>`<button type="button" class="db-object ${chosen===r.name?'active':''}" data-db-object="${esc(r.name)}" ${r.name.toLowerCase().includes(objectQuery.toLowerCase())?'':'hidden'} aria-pressed="${chosen===r.name}"><code>${esc(r.name)}</code><small>${esc(r.kind)} · ${r.rows??'—'} rows</small></button>`).join('')}</div></aside><div class="db-inspection"><div class="section-head"><h3>${esc(chosen||'Choose a table')}</h3><span class="muted">Read only</span></div><div class="system-actions db-tabs">${['rows','columns','definition'].map(t=>btn(t[0].toUpperCase()+t.slice(1),`data-db-tab="${t}" aria-pressed="${tab===t}"`)).join('')}${btn('Refresh',`data-db-refresh ${busy?'disabled':''}`)}</div><p role="status" class="${error?'error':'muted'}">${esc(error|| (busy?'Loading…':data?data.total+' rows · '+data.columns.length+' columns':''))}</p><div id="db-content">${content()}</div></div></div>`;node.querySelector('.db-objects').scrollTop=scroll;
 }
 function content(){if(!data)return '';if(tab==='definition')return `<pre class="db-definition">${esc(data.object.sql||'SQLite internal object')}</pre><h4>Foreign keys</h4><pre>${esc(JSON.stringify(data.foreign_keys,null,2))}</pre><h4>Indexes</h4><pre>${esc(JSON.stringify(data.indexes,null,2))}</pre>`;
 if(tab==='columns')return `<div class="db-scroll"><table class="data-table"><thead><tr>${['Column','Type','Not null','Default','Primary key','Hidden / generated'].map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${data.columns.map(c=>`<tr><td><code>${esc(c.name)}</code></td><td>${esc(c.type||'Unspecified')}</td><td>${c.notnull?'Yes':'No'}</td><td>${c.dflt_value==null?'—':esc(c.dflt_value)}</td><td>${c.pk||'—'}</td><td>${({1:'Hidden',2:'Generated (virtual)',3:'Generated (stored)'})[c.hidden]||'—'}</td></tr>`).join('')}</tbody></table></div>`;
 return `<div class="db-scroll"><table class="data-table db-rows"><thead><tr><th>Row</th>${data.columns.map(c=>`<th>${esc(c.name)}</th>`).join('')}</tr></thead><tbody>${data.rows.map((r,i)=>`<tr><th>${data.offset+i+1}</th>${r.cells.map((c,j)=>`<td><button type="button" data-db-cell="${i}" data-db-column="${j}" title="Inspect ${esc(data.columns[j].name)}"><small>${esc(c.type)}${c.encoding?' · '+esc(c.encoding):''}</small><span>${c.type==='null'?'NULL':esc(c.value)}${c.truncated?'…':''}</span></button></td>`).join('')}</tr>`).join('')}</tbody></table>${!data.rows.length?'<p class="empty">No rows.</p>':''}</div><div class="db-pager">${btn('Previous',`data-db-page="-1" ${!offset||busy?'disabled':''}`)}<span>${data.total?data.offset+1:0}–${Math.min(data.offset+data.rows.length,data.total)} of ${data.total}</span>${btn('Next',`data-db-page="1" ${offset+data.limit>=data.total||busy?'disabled':''}`)}</div>`;
 }
 async function load(){const own=++ticket;busy=true;error='';data=null;draw();try{const r=await U.api('/api/dev/database/inspect?name='+encodeURIComponent(chosen)+'&offset='+offset);if(own!==ticket||!$('#system-inventory'))return;data=r;const item=items.find(v=>v.name===chosen);if(item)item.rows=r.total}catch(e){if(own===ticket)error=e.message}finally{if(own===ticket){busy=false;draw()}}}
 async function inspectCell(row,column,start=0){const own=++cellTicket;U.openDialog('Stored value',`<p data-db-cell-owner="${own}" role="status">Loading value…</p>`);$('#editor-submit').hidden=true;
 try{const r=await U.api('/api/dev/database/cell?review_token='+encodeURIComponent(row.review_token)+'&column='+column+'&start='+start);if(own!==cellTicket||!$('#editor').open||!$('[data-db-cell-owner="'+own+'"]'))return;
 $('#editor-fields').innerHTML=`<div class="db-cell-detail" data-db-cell-owner="${own}"><strong>${esc(r.column)}</strong><p>${esc(r.type)}${r.encoding?' · '+esc(r.encoding):''} · ${r.total} ${esc(r.unit||'values')}</p><pre>${r.value===null?'NULL':esc(r.value)}</pre><div class="db-pager">${btn('Previous',`data-db-chunk="${Math.max(0,start-r.limit)}" ${!start?'disabled':''}`)}<span>${start}–${Math.min(start+r.limit,r.total)}</span>${btn('Next',`data-db-chunk="${start+r.limit}" ${!r.truncated?'disabled':''}`)}</div></div>`;
 $('#editor-fields').querySelectorAll('[data-db-chunk]').forEach(b=>b.onclick=()=>inspectCell(row,column,Number(b.dataset.dbChunk)));
 }catch(e){if(own===cellTicket&&$('[data-db-cell-owner="'+own+'"]'))$('#editor-fields').innerHTML=`<p class="error" role="alert">${esc(e.message)}</p>`}}
 document.addEventListener('click',e=>{const b=e.target.closest('button');if(!U||!b||b.disabled)return;
 if(b.dataset.dbObject){chosen=b.dataset.dbObject;offset=0;load()}
 if(b.dataset.dbTab){tab=b.dataset.dbTab;draw()}
 if(b.hasAttribute('data-db-refresh'))load();
 if(b.dataset.dbPage){offset=Math.max(0,offset+Number(b.dataset.dbPage)*data.limit);load()}
 if(b.hasAttribute('data-db-cell'))inspectCell(data.rows[Number(b.dataset.dbCell)],Number(b.dataset.dbColumn));
 });
 document.addEventListener('input',e=>{if(e.target.id==='db-object-query'){objectQuery=e.target.value;const q=objectQuery.toLowerCase();document.querySelectorAll('[data-db-object]').forEach(b=>b.hidden=!b.dataset.dbObject.toLowerCase().includes(q))}});
 document.addEventListener('close',e=>{if(e.target.id==='editor')++cellTicket},true);
 window.addEventListener('pagehide',e=>{if(!e.persisted)close()});
 return {bindUI:ui=>U=ui,mount,close};
})();
