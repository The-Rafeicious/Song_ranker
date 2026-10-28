/* Analysis-only navigation, searchable selectors and evidence-aware chart controls. */
(()=>{
 'use strict';
 const form=document.getElementById('analysis-controls');if(!form)return;
 const config=JSON.parse(document.getElementById('analysis-evidence').textContent);
 const pickers=new Map();
 let opened=null;
 function close(){if(opened){opened.open=false;opened=null;}}
 function refresh(control){
  const root=pickers.get(control);if(!root)return;
  const menu=root.querySelector('.analysis-picker-options');menu.replaceChildren();
  const value=root.querySelector('.analysis-picker-value');value.textContent=control.selectedOptions[0]?.textContent||'Choose';
  for(const option of control.options){
   const button=document.createElement('button');button.type='button';button.disabled=option.disabled;
   button.dataset.value=option.value;button.setAttribute('aria-pressed',String(option.selected));
   const cover=option.dataset.cover;
   if(cover){const img=document.createElement('img');img.src=cover;img.alt='';img.loading='lazy';img.addEventListener('error',()=>img.hidden=true);button.append(img);}
   const copy=document.createElement('span');copy.textContent=option.textContent;
   if(option.dataset.subtitle){const sub=document.createElement('small');sub.textContent=option.dataset.subtitle;copy.append(sub);}
   if(option.disabled){button.title='Not enough compatible evidence';const sub=document.createElement('small');sub.textContent='Unavailable for this evidence';copy.append(sub);}
   button.append(copy);menu.append(button);
   button.addEventListener('click',()=>{control.value=option.value;control.dispatchEvent(new Event('change',{bubbles:true}));refresh(control);close();root.querySelector('summary').focus();});
  }
  root.querySelector('input').value='';
 }
 for(const control of form.querySelectorAll('select')){
  const label=control.closest('label'),text=label.firstChild.textContent.trim();
  const group=document.createElement('div');group.className='analysis-control';
  const caption=document.createElement('span');caption.textContent=text;group.append(caption);
  control.id='analysis-'+control.name;control.hidden=true;control.setAttribute('aria-label',text);group.append(control);
  const root=document.createElement('details');root.className='analysis-picker';root.dataset.control=control.name;
  const summary=document.createElement('summary');summary.setAttribute('aria-label',text);summary.innerHTML='<span class="analysis-picker-value"></span><span aria-hidden="true">⌄</span>';
  const body=document.createElement('div');body.className='analysis-picker-body';
  const search=document.createElement('input');search.type='search';search.placeholder='Find '+text.toLowerCase()+'…';search.setAttribute('aria-label','Search '+text);
  const menu=document.createElement('div');menu.className='analysis-picker-options';
  body.append(search,menu);root.append(summary,body);group.append(root);label.replaceWith(group);pickers.set(control,root);refresh(control);
  search.addEventListener('input',()=>{for(const b of menu.children)b.hidden=!b.textContent.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase());});
  search.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();menu.querySelector('button:not([hidden]):not(:disabled)')?.click();}if(e.key==='ArrowDown'){e.preventDefault();menu.querySelector('button:not([hidden]):not(:disabled)')?.focus();}});
  root.addEventListener('toggle',()=>{if(root.open){if(opened&&opened!==root)opened.open=false;opened=root;search.focus();}});
 }
 document.addEventListener('click',e=>{if(opened&&!opened.contains(e.target))close();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&opened){const root=opened;close();root.querySelector('summary').focus();}});
 function restrictions(){
  const chart=form.elements.chart.value,x=form.elements.metric,y=form.elements.y;
  for(const option of x.options)option.disabled=chart==='scatter'?!(config.pairs[option.value]||[]).length:!config.counts[option.value];
  if(x.selectedOptions[0]?.disabled)x.value=Array.from(x.options).find(o=>!o.disabled)?.value||x.value;
  for(const option of y.options)option.disabled=chart==='scatter'&&!(config.pairs[x.value]||[]).includes(option.value);
  if(y.selectedOptions[0]?.disabled)y.value=Array.from(y.options).find(o=>!o.disabled)?.value||y.value;
  pickers.get(x).parentElement.hidden=!['bars','scatter'].includes(chart);
  pickers.get(y).parentElement.hidden=chart!=='scatter';refresh(x);refresh(y);
 }
 form.elements.chart.addEventListener('change',restrictions);form.elements.metric.addEventListener('change',restrictions);restrictions();
 for(const name of ['id','compare','minimum'])form.elements[name].addEventListener('change',()=>form.requestSubmit());
 // View navigation reduces page length without dropping any report section.
 const nav=document.querySelector('.analysis-tabs'),groups={Overview:[],Games:[],Relationships:[],Records:[]};
 for(const panel of document.querySelectorAll('.analysis-page > section')){
  if(panel.contains(form)||panel.querySelector('.analysis-identity'))continue;
  const title=panel.querySelector('h2')?.textContent||'';
  const group=/relationships|Vibe coordinates/.test(title)?'Relationships':/Recent preference|Track explorer|Tournament routes/.test(title)?'Records':/Opponents|bracket record|Recognition timing|Overall contribution/.test(title)?'Games':'Overview';
  groups[group].push(panel);
 }
 for(const [name,panels] of Object.entries(groups)){
  const b=document.createElement('button');b.type='button';b.className='pill';b.textContent=name;nav.append(b);
  b.addEventListener('click',()=>{for(const [key,items] of Object.entries(groups))for(const item of items)item.hidden=key!==name;for(const n of nav.children)n.setAttribute('aria-pressed',String(n===b));});
 }
 nav.hidden=false;nav.firstElementChild?.click();
})();
