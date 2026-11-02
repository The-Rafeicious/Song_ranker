/* Cross-mode query builder. Server owns validation, pooling, sorting and paging. */
window.ModeQuery = (() => {
  'use strict';
  const U=window.SongRankerUI, esc=U.esc;
  const defaults=()=>({entity:'songs',q:'',filters:[],sort:[{field:'elo',direction:'desc'}],columns:['elo','matches','win_rate','trivia_rounds','trivia_accuracy'],page:1});
  const presets={
    'Most played':{sort:[{field:'matches',direction:'desc'},{field:'elo',direction:'desc'},{field:'name',direction:'asc'}]},
    'Highest recognised':{filters:[{field:'trivia_rounds',op:'min',value:1}],sort:[{field:'trivia_accuracy',direction:'desc'},{field:'trivia_rounds',direction:'desc'},{field:'elo',direction:'desc'}]},
    'Recognition by rounds':{sort:[{field:'trivia_rounds',direction:'desc'},{field:'trivia_accuracy',direction:'desc'},{field:'elo',direction:'desc'}]},
    'Blind versus Non-blind':{filters:[{field:'elo_gap',op:'has'}],sort:[{field:'elo_gap',direction:'desc'}],columns:['standard_elo','blind_elo','elo_gap','standard_matches','blind_matches']},
    'Tournament leaders':{sort:[{field:'tournament_championships',direction:'desc'},{field:'tournament_wins',direction:'desc'},{field:'elo',direction:'desc'}],columns:['tournament_appearances','tournament_wins','tournament_win_rate','elo']},
    'Unplayed recognition':{filters:[{field:'trivia_rounds',op:'eq',value:0}]},
    'Vibe coverage':{sort:[{field:'vibe_maps',direction:'desc'},{field:'vibe_samples',direction:'desc'}],columns:['vibe_maps','vibe_samples','vibe_passes','elo']}
  };
  function mount(root){
    if(root.dataset.queryMounted)return;root.dataset.queryMounted='true';
    let spec=defaults(),metrics=[],result=null,controller=null,serial=0,lookupSerial=0,revision=0,searchTimer=null,lookupController=null,columnSearch='',columnFamily='',filterSearch='',filterFamily='';
    const controls=root.querySelector('[data-query-controls]'),output=root.querySelector('[data-query-results]'),error=root.querySelector('[data-query-error]');
    const select=(id,label,options,value)=>window.GameplayUI.select(id,label,options.map(o=>typeof o==='string'?{value:o,label:o.replaceAll('_',' ')}:o),value);
    const commonKeys=['elo','matches','win_rate','trivia_rounds','trivia_accuracy','tournament_championships'];
    function metricView(m){
      const names={overall_score:'Score',overall_evidence:'Evidence',overall_modes:'Modes',tracks:'Tracks',elo:'Elo',standard_elo:'Non-blind Elo',blind_elo:'Blind Elo',elo_gap:'Elo gap',ordinary_matches:'Ordinary matches',first_round_matches:'First-round matches',trivia_correct:'Correct fields',trivia_available:'Available fields',trivia_rounds:'Rounds',trivia_accuracy:'Recognition rate',title_accuracy:'Title accuracy',artist_accuracy:'Artist accuracy',album_accuracy:'Album accuracy',guess_rounds:'Appearances',guess_accuracy:'Accuracy',shelf_rounds:'Appearances',shelf_album:'Album accuracy',shelf_order:'Order accuracy',shelf_accuracy:'Points earned',vibe_maps:'Mapped selections',vibe_samples:'Samples',vibe_passes:'Completed passes'};
      let label=names[m.key],detail=m.family;
      if(!label){const prefix=m.key.startsWith('tournament_')?'tournament_':m.key.startsWith('local_')?'local_':m.key.startsWith('standard_')?'standard_':m.key.startsWith('blind_')?'blind_':'';const base=m.key.slice(prefix.length);label=({matches:'Matches',wins:'Wins',losses:'Losses',win_rate:'Win rate',appearances:'Entries',points:'Points',championships:'Titles'})[base]||m.label;if(prefix==='local_')label='Local '+label.toLowerCase();if(prefix==='standard_')label='Non-blind '+label.toLowerCase();if(prefix==='blind_')label='Blind '+label.toLowerCase();if(prefix==='tournament_')detail='Tournament · Library + tags';}
      if(m.key==='elo')detail='Voting · Rated-track mean for collections';
      if(m.key==='elo_gap')detail='Voting · Blind − Non-blind, shared rated tracks';
      if(m.key==='ordinary_matches'||m.key==='first_round_matches')detail='Voting · Weighted credit';
      if(m.key==='shelf_rounds')detail='Album Shelves · Track appearances';
      return {label,detail,common:commonKeys.includes(m.key)};
    }
    const metricOptions=()=>metrics.map(m=>({value:m.key,...metricView(m)}));
    const relation=f=>['won_against','lost_to','artist','album','tag'].includes(f.field);
    const shownColumns=()=>[...new Set([...spec.sort.filter(s=>s.field!=='name').map(s=>s.field),...spec.columns])].slice(0,6);
    const relations=[{key:'won_against',label:'Won against',family:'Relationships',detail:'Choose an opponent'},{key:'lost_to',label:'Lost to',family:'Relationships',detail:'Choose an opponent'},{key:'artist',label:'Artist',family:'Relationships',detail:'Tracks by an artist'},{key:'album',label:'Album',family:'Relationships',detail:'Tracks from an album'},{key:'tag',label:'Tag',family:'Relationships',detail:'Tracks with a tag'}];
    const fieldOptions=()=>[...metricOptions(),...relations.map(r=>({value:r.key,label:r.label,detail:r.detail}))];
    function readURL(){try{spec={...defaults(),...JSON.parse(new URL(location.href).searchParams.get('spec')||'{}')};}catch{spec=defaults();}}
    function draw(){
      spec.columns=shownColumns();
      const searchFocus=document.activeElement?.matches('[data-search]'),columnFocus=document.activeElement?.matches('[data-column-search]'),caret=document.activeElement?.selectionStart;
      const columnsOpen=controls.querySelector('.query-columns')?.open;
      const focused=document.activeElement?.closest('[data-game-select]')?.dataset.gameSelect,focusedKind=document.activeElement?.dataset.queryKind;
      lookupSerial++;lookupController?.abort();
      root.querySelector('[data-query-entity]').innerHTML=['songs','artists','albums','tags'].map(kind=>`<button type="button" data-query-kind="${kind}" class="${kind.slice(0,-1)}" aria-pressed="${spec.entity===kind}">${kind[0].toUpperCase()+kind.slice(1)}</button>`).join('');
      controls.innerHTML=`<div class="query-grid"><label class="query-search-label">Search library<div class="query-search-field"><span aria-hidden="true">⌕</span><input type="search" data-search value="${esc(spec.q)}" placeholder="Search names, artists, albums or tags" autocomplete="off" maxlength="200" aria-label="Search library"><button type="button" data-search-clear aria-label="Clear library search" ${spec.q?'':'hidden'}>×</button></div></label>${select('query-preset','Quick start',[{value:'',label:'Choose a preset'},...Object.keys(presets).map(k=>({value:k,label:k}))],'')}</div><h2>Filters</h2>${filterChooser()}<div data-filters>${spec.filters.map((f,i)=>`<div class="query-filter" data-filter="${i}">${select('field-'+i,'Filter',fieldOptions(),f.field)}${relation(f)?`<label>Find ${['artist','album','tag'].includes(f.field)?f.field:'opponent song'}<div class="query-search-field"><span aria-hidden="true">⌕</span><input type="search" data-target-search="${i}" placeholder="Search by name or artist" value="${esc(f.target_name||'')}" autocomplete="off" maxlength="200" aria-controls="query-targets-${i}" aria-expanded="false"><button type="button" data-target-clear="${i}" aria-label="Clear selected record" ${f.target_name?'':'hidden'}>×</button></div></label><div class="query-targets" id="query-targets-${i}" data-targets="${i}" aria-label="Matching records">${f.target_id?`<span>Selected: ${esc(f.target_name||'#'+f.target_id)}</span>`:''}</div>${['won_against','lost_to'].includes(f.field)?`${select('source-'+i,'Match source',[{value:'all',label:'All competition matches'},{value:'voting',label:'Ordinary voting'},{value:'first_round',label:'Tournament first round'},{value:'tournament',label:'Tournament later rounds'},{value:'local',label:'Local tournaments'}],f.source||'all')}${select('mode-'+i,'Visibility',[{value:'all',label:'Both modes'},{value:'standard',label:'Non-blind'},{value:'blind',label:'Blind'}],f.mode||'all')}`:''}`:`${select('op-'+i,'Comparison',[{value:'min',label:'At least'},{value:'max',label:'At most'},{value:'between',label:'Between'},{value:'eq',label:'Exactly'},{value:'has',label:'Available'},{value:'missing',label:'Unavailable'}],f.op||'min')}${!['has','missing'].includes(f.op)?`<label>${f.op==='between'?'From':'Value'}<input type="number" step="any" data-number="${i}" value="${esc(f.value??'')}" required></label>${f.op==='between'?`<label>To<input type="number" step="any" data-max="${i}" value="${esc(f.max??'')}" required></label>`:''}`:''}`}<button type="button" data-remove="${i}" aria-label="Remove filter ${i+1}">Remove</button></div>`).join('')}</div><h2>Sort results</h2><div class="query-grid">${[0,1,2].map(i=>{const chosen=spec.sort[i];const available=[{value:'name',label:'Alphabetical'},...metricOptions()].filter(o=>!spec.sort.some((s,j)=>j!==i&&s.field===o.value));return `<div>${select('sort-'+i,['Primary','Secondary','Third'][i],i?[{value:'',label:i===2&&!spec.sort[1]?'Choose secondary first':'None'},...(i===2&&!spec.sort[1]?[]:available)]:available,chosen?.field||'')}${chosen?select('direction-'+i,'Order',[{value:'desc',label:chosen.field==='name'?'Z–A':'Highest first'},{value:'asc',label:chosen.field==='name'?'A–Z':'Lowest first'}],chosen.direction):''}</div>`;}).join('')}</div>${columnChooser(columnsOpen)}`;
      updateColumns();updateFilterChoices();decorateLabels();
      if(searchFocus){const input=controls.querySelector('[data-search]');input.focus();input.setSelectionRange(caret,caret);}
      if(columnFocus){const input=controls.querySelector('[data-column-search]');input.focus();input.setSelectionRange(caret,caret);}
      if(focused)controls.querySelector(`[data-game-select="${focused}"] .game-select-trigger`)?.focus();
      if(focusedKind)root.querySelector(`[data-query-kind="${focusedKind}"]`)?.focus();
    }
    function decorateLabels(){
      controls.querySelectorAll('label').forEach(label=>{
        if(label.classList.contains('query-column-option'))return;
        const text=[...label.childNodes].find(n=>n.nodeType===3&&n.textContent.trim());
        if(text){const caption=document.createElement('span');caption.className='query-field-label';caption.textContent=text.textContent.trim();text.replaceWith(caption);}
      });
      controls.querySelectorAll('[data-game-select]').forEach(select=>{
        const id=select.dataset.gameSelect,field=select.querySelector('select'),m=metrics.find(m=>m.key===field.value);
        if((id.startsWith('field-')||id.startsWith('sort-'))&&m){
          const trigger=select.querySelector('.game-select-trigger'),copy=document.createElement('small');copy.className='query-selected-detail';copy.textContent=metricView(m).detail;trigger.querySelector('span').appendChild(copy);trigger.title=m.label;
        }
      });
    }
    function filterChooser(){
      const choices=[...metrics.map(m=>({key:m.key,family:m.family,...metricView(m),full:m.label})),...relations];
      const families=[...new Set(choices.map(m=>m.family))];
      return `<details class="query-filter-picker"><summary>+ Add filter <small>${spec.filters.length} / 8</small></summary><div class="query-picker-body"><div class="query-quick-filters" aria-label="Common filters">${commonKeys.filter(k=>metrics.some(m=>m.key===k)).map(key=>{const m=metrics.find(m=>m.key===key);return `<button type="button" ${key==='matches'?'data-add':`data-add-field="${key}"`} ${spec.filters.length>=8?'disabled':''}>${esc(metricView(m).label)}<small>${esc(m.family)}</small></button>`;}).join('')}<button type="button" data-add-field="won_against" ${spec.filters.length>=8?'disabled':''}>Won against</button><button type="button" data-add-field="lost_to" ${spec.filters.length>=8?'disabled':''}>Lost to</button></div><div class="query-grid"><label>Find a filter<div class="query-search-field"><span aria-hidden="true">⌕</span><input type="search" data-filter-search placeholder="Elo, blind, rounds, opponent…" autocomplete="off" value="${esc(filterSearch)}"></div></label>${select('query-filter-family','Category',[{value:'',label:'All categories'},...families.map(f=>({value:f,label:f}))],filterFamily)}</div><p data-filter-status class="query-chooser-status" role="status"></p><div class="query-filter-choices">${families.map(f=>`<section data-filter-group><h3>${esc(f)}</h3>${choices.filter(m=>m.family===f).map(m=>`<button type="button" data-add-field="${esc(m.key)}" data-filter-choice data-family="${esc(m.family)}" data-find="${esc([m.label,m.detail,m.full,m.family,m.key].join(' ').toLowerCase())}" ${spec.filters.length>=8?'disabled':''} title="${esc(m.full||m.detail)}"><b>${esc(m.label)}</b><small>${esc(m.detail)}</small>${m.common?'<span class="query-common">Common</span>':''}</button>`).join('')}</section>`).join('')}</div></div></details>`;
    }
    function updateFilterChoices(){
      const terms=filterSearch.toLowerCase().trim().split(/\s+/).filter(Boolean);let visible=0;
      controls.querySelectorAll('[data-filter-group]').forEach(group=>{let count=0;group.querySelectorAll('[data-filter-choice]').forEach(button=>{button.hidden=Boolean(filterFamily&&button.dataset.family!==filterFamily)||!terms.every(t=>button.dataset.find.includes(t));if(!button.hidden){count++;visible++;}});group.hidden=!count;});
      controls.querySelector('[data-filter-status]').textContent=spec.filters.length>=8?'Eight filters added · remove one to add another.':visible?'Choose a filter to add.':'No matching filters.';
    }
    function addFilter(key){
      if(spec.filters.length>=8)return;
      const m=metrics.find(m=>m.key===key);
      spec.filters.push(relation({field:key})?{field:key}:{field:key,op:key==='elo'?'between':'min',value:key==='elo'?1200:m?.unit==='percent'?50:1,...(key==='elo'?{max:1250}:{})});
      filterSearch='';filterFamily='';draw();
      const index=spec.filters.length-1;
      (controls.querySelector(`[data-target-search="${index}"]`)||controls.querySelector(`[data-game-select="field-${index}"] .game-select-trigger`))?.focus();
    }
    function columnChooser(open){
      const families=[...new Set(metrics.map(m=>m.family))];
      return `<details class="query-columns" ${open?'open':''}><summary><span>Statistics to show</span><span data-column-count></span></summary><div class="query-column-body"><div class="query-column-selected" data-column-selected aria-label="Selected statistics"></div><div class="query-grid"><label>Find a statistic<div class="query-search-field"><span aria-hidden="true">⌕</span><input type="search" data-column-search placeholder="Search statistics" value="${esc(columnSearch)}" autocomplete="off"></div></label>${select('query-column-family','Mode',[{value:'',label:'All modes'},...families.map(f=>({value:f,label:f}))],columnFamily)}</div><p class="query-chooser-status" data-column-status role="status"></p><div class="query-column-groups">${families.map(family=>`<fieldset data-column-group><legend>${esc(family)}</legend>${metrics.filter(m=>m.family===family).map(m=>`<label class="query-column-option" data-column-option data-find="${esc((m.family+' '+m.label+' '+metricView(m).label+' '+m.unit).toLowerCase())}"><input type="checkbox" data-column="${esc(m.key)}"><span><b>${esc(metricView(m).label)}</b><small>${esc(metricView(m).detail)} · ${esc(m.unit==='percent'?'Percentage':m.unit==='rating'?'Rating / score':'Count')}<span data-sort-required hidden> · Required for sorting</span></small></span></label>`).join('')}</fieldset>`).join('')}</div></div></details>`;
    }
    function updateColumns(){
      const keys=shownColumns(),locked=new Set(spec.sort.map(s=>s.field)),terms=columnSearch.toLowerCase().trim().split(/\s+/).filter(Boolean);
      controls.querySelector('[data-column-count]').textContent=`${keys.length} / 6`;
      controls.querySelector('[data-column-selected]').innerHTML=keys.map(key=>{const m=metrics.find(m=>m.key===key);return `<span class="query-column-chip">${esc(m?metricView(m).label:key)}${locked.has(key)?'<small>Sort</small>':`<button type="button" data-column-remove="${esc(key)}" aria-label="Remove ${esc(m?.label||key)}">×</button>`}</span>`;}).join('');
      let visible=0;
      controls.querySelectorAll('[data-column-group]').forEach(group=>{
        let count=0;
        group.querySelectorAll('[data-column-option]').forEach(label=>{
          const input=label.querySelector('input'),m=metrics.find(m=>m.key===input.dataset.column),selected=keys.includes(m.key),required=locked.has(m.key);
          input.checked=selected;input.disabled=required||(!selected&&keys.length>=6);
          label.classList.toggle('is-selected',selected);label.querySelector('[data-sort-required]').hidden=!required;
          label.hidden=(columnFamily&&m.family!==columnFamily)||!terms.every(t=>label.dataset.find.includes(t));
          if(!label.hidden){count++;visible++;}
        });group.hidden=!count;
      });
      controls.querySelector('[data-column-status]').textContent=!visible?'No statistics match this search.':keys.length>=6?'Six selected · remove a field to choose another.':'Choose up to six · sorting fields stay selected.';
    }
    function queueSearch(){
      clearTimeout(searchTimer);
      if(spec.filters.some(f=>relation(f)&&!f.target_id))return;
      const version=revision;
      searchTimer=setTimeout(()=>{if(version!==revision||spec.filters.some(f=>relation(f)&&!f.target_id))return;spec.page=1;load('replace');},350);
    }
    async function lookup(input){
      const i=+input.dataset.targetSearch,f=spec.filters[i],term=input.value.trim(),token=++lookupSerial,box=controls.querySelector(`[data-targets="${i}"]`);
      lookupController?.abort();delete f.target_id;f.target_name=input.value;
      input.closest('.query-search-field').querySelector('button').hidden=!input.value;
      input.setAttribute('aria-expanded','false');
      if(!term){box.innerHTML='<span class="query-search-status" role="status">Type a name to find a record.</span>';return;}
      box.innerHTML='<span class="query-search-status" role="status">Searching…</span>';
      await new Promise(r=>setTimeout(r,250));if(token!==lookupSerial||!input.isConnected)return;
      const active=new AbortController();lookupController=active;const timeout=setTimeout(()=>active.abort(),15000);
      const kind={artist:'artists',album:'albums',tag:'tags'}[f.field]||'songs';
      try{
        const data=await request('/api/query?lookup='+kind+'&q='+encodeURIComponent(term),active.signal);
        if(token!==lookupSerial||!input.isConnected)return;
        box.innerHTML=data.items.map(r=>`<button type="button" data-target="${r.id}" data-index="${i}" data-target-name="${esc(r.name)}">${art(r)}<span><b>${esc(r.name)}</b><small>${esc([r.subtitle,...(r.related||[]).map(x=>x.name)].filter(Boolean).join(' · '))}</small></span></button>`).join('')+`<span class="query-search-status" role="status">${data.total>25?'First 25 matches · keep typing to narrow them.':data.total?data.total+' matching records':'No matching records. Try another name.'}</span>`;
        input.setAttribute('aria-expanded',String(data.items.length>0));
      }catch(e){if(token===lookupSerial&&input.isConnected)box.innerHTML='<span class="query-search-status" role="status">Search unavailable. Type again to retry.</span>';}
      finally{clearTimeout(timeout);}
    }
    function format(key,value){if(value==null)return '—';const m=metrics.find(m=>m.key===key);if(m?.unit==='count')return U.countText(Number(value));return Number(value).toLocaleString(undefined,{maximumFractionDigits:1})+(m?.unit==='percent'?'%':'');}
    function art(r){return r.cover?`<img class="query-art ${esc(r.kind)}" src="${esc(r.cover)}" alt="" loading="lazy">`:'<span class="query-art" aria-hidden="true">♫</span>';}
    function link(r){return `<a class="${esc(r.kind.slice(0,-1))}" href="${esc(r.url)}">${esc(r.name)}</a>`;}
    function stat(key,value){const m=metrics.find(m=>m.key===key);return `<div class="query-stat" aria-label="${esc(m?.label||key)}: ${esc(value??'Unavailable')}" title="${esc(m?.label||key)}: ${esc(value??'Unavailable')}"><span><b>${esc(m?metricView(m).label:key)}</b><small>${esc(m?.family||'')}</small></span><strong>${format(key,value)}</strong></div>`;}
    function pager(){return `<nav class="query-pager" aria-label="Query result pages"><button type="button" data-page="1" ${result.page===1?'disabled':''}>First</button><button type="button" data-page="${result.page-1}" ${result.page===1?'disabled':''}>Previous</button><label>Page <input type="number" data-page-input min="1" max="${result.pages}" value="${result.page}" aria-label="Result page"></label><span>of ${result.pages}</span><button type="button" data-page="${result.page+1}" ${result.page===result.pages?'disabled':''}>Next</button><button type="button" data-page="${result.pages}" ${result.page===result.pages?'disabled':''}>Last</button></nav>`;}
    function render(){output.innerHTML=`<p>${result.total.toLocaleString()} results · ${result.total?(result.page-1)*20+1:0}–${Math.min(result.page*20,result.total)} shown</p>${pager()}${result.items.map((r,i)=>`<details class="query-result"><summary>${art(r)}<span class="query-name" title="${esc(r.name)}"><b>${esc(r.name)}</b><small>${esc(r.kind)} · Expand stats</small></span><div class="query-values">${result.spec.columns.map(k=>stat(k,r.values[k])).join('')}</div></summary><div class="query-expanded"><h2>${link(r)}</h2><p><a href="${esc(r.url)}">Open full ${esc(r.kind.slice(0,-1))} page →</a></p><div class="query-grid">${[...new Set(metrics.map(m=>m.family))].map(family=>`<section><h3>${esc(family)}</h3>${metrics.filter(m=>m.family===family).slice(0,4).map(m=>stat(m.key,r.values[m.key])).join('')}</section>`).join('')}</div><h3>${r.kind==='songs'?'Artists, album and tags':'Some tracks in this collection'}</h3><div class="query-related">${(r.related||[]).map(x=>`<div>${art(x)}<div>${link(x)}${(x.related||[]).map(link).join(' · ')}</div></div>`).join('')||'<p>No linked records.</p>'}</div></div></details>`).join('')||'<p>No records match. Adjust or remove a filter.</p>'}${pager()}`;}
    async function request(url,signal){const response=await fetch(url,{signal});const data=await response.json();if(!response.ok)throw Error(data.error||'Could not load query.');return data;}
    async function load(push=true){clearTimeout(searchTimer);controller?.abort();controller=new AbortController();const id=++serial,version=revision,active=controller;const timeout=setTimeout(()=>active.abort(),20000);error.textContent='';output.setAttribute('aria-busy','true');try{const data=await request('/api/query?spec='+encodeURIComponent(JSON.stringify(spec)),controller.signal);if(id!==serial)return;result=data;if(revision===version){spec=data.spec;draw();}render();if(push){const url=new URL(location.href);url.searchParams.set('spec',JSON.stringify(data.spec));history[push==='replace'?'replaceState':'pushState'](null,'',url);} }catch(e){if(id===serial){error.textContent=e.name==='AbortError'?'Query timed out. Apply again to retry.':e.message;}}finally{clearTimeout(timeout);if(id===serial)output.removeAttribute('aria-busy');}}
    controls.addEventListener('input',e=>{
      const t=e.target;
      if(t.matches('[data-filter-search]')){filterSearch=t.value;updateFilterChoices();return;}
      if(t.matches('[data-column-search]')){columnSearch=t.value;updateColumns();return;}
      revision++;
      if(t.matches('[data-search]')){spec.q=t.value;controls.querySelector('[data-search-clear]').hidden=!t.value;queueSearch();}
      if(t.dataset.number!==undefined)spec.filters[+t.dataset.number].value=t.value;
      if(t.dataset.max!==undefined)spec.filters[+t.dataset.max].max=t.value;
      if(t.dataset.targetSearch!==undefined)lookup(t);
    });
    controls.addEventListener('keydown',e=>{
      const t=e.target;
      if(t.matches('[data-filter-search]')&&e.key==='Enter'){e.preventDefault();controls.querySelector('[data-filter-choice]:not([hidden])')?.click();return;}
      if(t.matches('[data-column-search]')&&e.key==='Enter'){e.preventDefault();return;}
      if(t.dataset.targetSearch!==undefined){
        const box=controls.querySelector(`[data-targets="${t.dataset.targetSearch}"]`);
        if(e.key==='ArrowDown'){e.preventDefault();box.querySelector('button')?.focus();}
        if(e.key==='Enter'){e.preventDefault();box.querySelector('button')?.click();}
        if(e.key==='Escape'){e.preventDefault();lookupSerial++;lookupController?.abort();box.innerHTML='';t.setAttribute('aria-expanded','false');}
      }
      const target=t.closest('[data-target]');
      if(target&&['ArrowDown','ArrowUp','Escape'].includes(e.key)){
        e.preventDefault();const buttons=[...target.parentElement.querySelectorAll('button')],i=buttons.indexOf(target),input=controls.querySelector(`[data-target-search="${target.dataset.index}"]`);
        if(e.key==='Escape'){input?.focus();target.parentElement.innerHTML='';input?.setAttribute('aria-expanded','false');}
        else if(e.key==='ArrowUp'&&i===0)input?.focus();
        else buttons[(i+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();
      }
    });
    controls.addEventListener('change',e=>{revision++;const t=e.target,id=t.id;let redraw=true;
      if(id==='query-filter-family'){filterFamily=t.value;updateFilterChoices();return;}
      if(id==='query-column-family'){columnFamily=t.value;updateColumns();return;}
      if(id==='query-preset'){if(!t.value)return;spec={...defaults(),entity:spec.entity,...structuredClone(presets[t.value])};draw();load();return;}
      else if(id.startsWith('field-'))spec.filters[+id.slice(6)]={field:t.value,op:'min',value:0};
      else if(id.startsWith('op-'))spec.filters[+id.slice(3)].op=t.value;
      else if(id.startsWith('source-'))spec.filters[+id.slice(7)].source=t.value;
      else if(id.startsWith('mode-'))spec.filters[+id.slice(5)].mode=t.value;
      else if(id.startsWith('sort-')){const i=+id.slice(5);if(!t.value)spec.sort=spec.sort.slice(0,i);else spec.sort[i]={field:t.value,direction:t.value==='name'?'asc':'desc'};}
      else if(id.startsWith('direction-'))spec.sort[+id.slice(10)].direction=t.value;
      else if(t.dataset.column){
        const key=t.dataset.column,locked=spec.sort.some(s=>s.field===key);
        if(locked){updateColumns();return;}
        spec.columns=t.checked?[...new Set([...shownColumns(),key])].slice(0,6):spec.columns.filter(k=>k!==key);
        updateColumns();redraw=false;
      }
      else redraw=false;
      if(redraw)draw();
    });
    root.addEventListener('click',e=>{const t=e.target.closest('button');if(!t)return;revision++;if(t.hasAttribute('data-search-clear')){spec.q='';spec.page=1;draw();controls.querySelector('[data-search]').focus();queueSearch();}if(t.dataset.targetClear!==undefined){const f=spec.filters[+t.dataset.targetClear];delete f.target_id;f.target_name='';draw();controls.querySelector(`[data-target-search="${t.dataset.targetClear}"]`)?.focus();}if(t.dataset.columnRemove){spec.columns=spec.columns.filter(k=>k!==t.dataset.columnRemove);updateColumns();controls.querySelector('[data-column-search]')?.focus();}if(t.dataset.queryKind){spec.entity=t.dataset.queryKind;spec.page=1;draw();root.querySelector(`[data-query-kind="${spec.entity}"]`)?.focus();load();}if(t.hasAttribute('data-add'))addFilter('matches');if(t.dataset.addField)addFilter(t.dataset.addField);if(t.dataset.remove!==undefined){spec.filters.splice(+t.dataset.remove,1);draw();}if(t.dataset.target){const f=spec.filters[+t.dataset.index];f.target_id=+t.dataset.target;f.target_name=t.dataset.targetName;draw();controls.querySelector(`[data-target-search="${t.dataset.index}"]`)?.focus();}if(t.hasAttribute('data-query-reset')){spec=defaults();columnSearch='';columnFamily='';filterSearch='';filterFamily='';draw();load();}if(t.dataset.page){spec.page=+t.dataset.page;load();}});
    output.addEventListener('change',e=>{if(e.target.matches('[data-page-input]')){spec.page=+e.target.value||1;load();}});
    root.querySelector('form').addEventListener('submit',e=>{e.preventDefault();spec.page=1;load();});
    window.addEventListener('popstate',()=>{readURL();draw();load(false);});
    window.addEventListener('pagehide',()=>{controller?.abort();lookupController?.abort();clearTimeout(searchTimer);lookupSerial++;});
    async function init(){try{metrics=(await request('/api/query?schema=1')).metrics;readURL();draw();await load(false);}catch(e){error.textContent=e.message;output.innerHTML='<button type="button" data-query-retry>Retry loading options</button>';output.querySelector('button').onclick=init;}}
    init();
  }
  document.addEventListener('DOMContentLoaded',()=>{const root=document.querySelector('[data-mode-query]');if(root)mount(root);});
  return {defaults,presets,mount};
})();
