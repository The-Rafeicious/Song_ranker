/* Served templates, feature scripts and real DB routes; disposable fixture only. */
const {JSDOM,CookieJar,VirtualConsole}=require('jsdom'),fs=require('fs');
(async()=>{
 const base=process.env.SONG_RANKER_QA_URL;if(!base)throw Error('Run through python tools/validate_dev_pages.py');const first=await fetch(base+'/dev/login'),html=await first.text(),csrf=html.match(/name="csrf_token" value="([^"]+)"/)[1];
 const login=await fetch(base+'/dev/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded',Cookie:first.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ')},body:new URLSearchParams({pin:'qa-test-pin',csrf_token:csrf}),redirect:'manual'});
 const cookie=login.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ');if(login.status!==302)throw Error('Login failed');
 const views=['overview','explorer','songs','artists','albums','tags','import','tag_workbench','bulk','metadata','history','trivia','tournaments','guesser_records','shelves_records','vibe_records','overall','selection_health','database','export'],results=[],errors=[];
 for(const width of [390,1280])for(const view of views){
  let pendingFetches=0;const jar=new CookieJar();await jar.setCookie(cookie,base);const vc=new VirtualConsole(),pageErrors=[];vc.on('jsdomError',e=>{if(!e.message.includes('HTMLMediaElement'))pageErrors.push(e.message)});
  const dom=await JSDOM.fromURL(base+'/dev/dashboard?view='+view,{cookieJar:jar,runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.innerWidth=width;w.scrollTo=()=>{};w.matchMedia=()=>({matches:true});w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.load=function(){};w.HTMLMediaElement.prototype.play=function(){return Promise.resolve()};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};w.fetch=async(url,o={})=>{pendingFetches++;try{const response=await fetch(new URL(url,base),{...o,headers:{...o.headers,Cookie:await jar.getCookieString(base)}});for(const c of response.headers.getSetCookie())await jar.setCookie(c,base);return response}finally{pendingFetches--}}}});
  await new Promise(resolve=>dom.window.addEventListener('load',resolve));await new Promise(r=>setTimeout(r,120));const d=dom.window.document;
  for(let i=0;i<250&&!d.querySelector('#dev-main h1,#dev-main h2,#dev-main h3');i++)await new Promise(r=>setTimeout(r,20));
  const title=d.querySelector('#dev-main h1')?.textContent||d.querySelector('#dev-main h2')?.textContent||d.querySelector('#dev-main h3')?.textContent;results.push({width,view,title,errors:pageErrors});if(!title||pageErrors.length)errors.push({width,view,title,errors:pageErrors});
  if(view==='overview'&&width===1280){
   const card=d.querySelector('.dev-home-tag-workshop');
   if(!card||card.querySelector('[data-dev="tag_workbench"]')?.textContent!=='Tag Workshop ↗'||card.querySelectorAll('.dev-service-metrics > div').length!==2)errors.push({issue:'Tag Workshop Home card/link'});
  }
  if(view==='tag_workbench'&&width===1280){
   const single=d.querySelector('.tag-single .tag-song-row');
   if(!single?.querySelector('.tag-art')||!single.querySelector('.tag-copy .album'))errors.push({issue:'single-song card missing artwork or album'});
   d.querySelector('[data-tags-mode="bulk"]').click();
   const bulk=d.querySelector('.tag-bulk'),row=bulk?.querySelector('.tag-song-row');
   if(!bulk?.querySelector('.tag-queue #tag-song-rows')||!bulk.querySelector('.tag-editor #tag-now-playing')||!bulk.querySelector('.tag-editor #tag-review')||!row?.querySelector('[data-tags-select]')||!row.querySelector('.tag-art')||bulk.querySelector('#tag-action')?.options.length!==3)errors.push({issue:'bulk bench structure or selection controls'});
   else{const box=row.querySelector('[data-tags-select]');box.checked=true;box.dispatchEvent(new dom.window.Event('change',{bubbles:true}));if(!bulk.querySelector(`[data-tag-song="${box.dataset.tagsSelect}"]`)?.classList.contains('tag-selected'))errors.push({issue:'bulk selection highlight'});}
  }
  if(view==='import'&&width===1280){if(!d.querySelector('#apple-query'))throw Error(JSON.stringify({view,title,pageErrors,body:d.querySelector('#main').textContent}));d.querySelector('#apple-query').value='https://music.apple.com/us/album/test/8001';await dom.window.DevCatalog.search();if(d.querySelectorAll('#editor-error').length!==1)errors.push({issue:'duplicate error nodes'});d.querySelector('[data-album-import-none]').click();const input=d.querySelector('[data-album-import-id="1"]');input.checked=true;d.querySelector('[data-album-import-save]').click();for(let i=0;i<250&&!d.querySelector('#toast').textContent;i++)await new Promise(r=>setTimeout(r,20));if(d.querySelector('#editor').open||!d.querySelector('#toast').textContent.includes('1 of 1'))errors.push({issue:'real album save failed',toast:d.querySelector('#toast').textContent});else results.push({albumImport:true,receipt:d.querySelector('#toast').textContent});}
  if(view==='vibe_records'&&width===1280){
   const wait=async predicate=>{for(let i=0;i<100;i++){if(predicate())return;await new Promise(r=>setTimeout(r,20))}throw Error('Vibe Dev UI timed out')};
   await wait(()=>d.querySelector('[data-vibe-edit]'));d.querySelector('[data-vibe-edit]').click();await wait(()=>d.querySelector('#dev-vibe-save'));
   const form=d.querySelector('#dev-vibe-save');for(const select of form.querySelectorAll('select')){select.value='placed';select.dispatchEvent(new dom.window.Event('change',{bubbles:true}))}
   form.elements.namedItem('pace_mood:x').value='2.5';form.elements.namedItem('completed_passes').value='1';form.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
   await wait(()=>d.querySelector('#toast').textContent.includes('Vibe data saved'));await wait(()=>!d.querySelector('#dev-vibe-search button').disabled);
   const saved=await (await dom.window.fetch('/api/dev/vibe/1')).json();if(saved.maps.find(m=>m.id==='pace_mood').x!==.5)errors.push({issue:'Vibe averaged edit failed'});
   d.querySelector('[data-vibe-clear-map="pace_mood"]').click();if(d.querySelector('#dev-vibe-save').elements.namedItem('completed_passes').value!=='0')errors.push({issue:'Vibe map clear did not reset pass counter'});
   const deletion=d.querySelector('#dev-vibe-delete');deletion.elements.namedItem('confirmation').value='DELETE VIBE';deletion.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
   await wait(()=>d.querySelector('#toast').textContent.includes('Vibe data deleted'));await wait(()=>!d.querySelector('#dev-vibe-search button').disabled);
   results.push({vibeEditDelete:true});
  }
  for(let i=0;i<200;i++){await new Promise(r=>setTimeout(r,20));if(!pendingFetches)break}
  dom.window.DevSelection?.viewChanged('');dom.window.DevSystem?.viewChanged('');dom.window.DevTags?.viewChanged('');dom.window.DevDatabase?.close();dom.window.DevVibe?.viewChanged('overview');dom.window.DevControls?.dispose();dom.window.close();
 }
 console.log(JSON.stringify({checks:results.length,errors},null,2));if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
