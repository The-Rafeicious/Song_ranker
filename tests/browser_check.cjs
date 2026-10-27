/* Real served assets + Python saves. Screenshots are CI artifacts, not source data. */
const {chromium}=require('playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
async function bounded(page,width,phase,folder){
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
 if(overflow){
  await page.screenshot({path:folder+'/'+phase+'-overflow-'+width+'.png',fullPage:true});
  console.log(await page.evaluate(()=>[...document.querySelectorAll('body *')].map(e=>({tag:e.tagName,id:e.id,class:e.className?.baseVal??e.className,left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right})).filter(e=>e.right>innerWidth+1||e.left< -1).slice(0,20)));
 }
 assert.ok(!overflow,phase+' overflow at '+width);
}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.VIBE_TEST_CHROME,headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1365,height:1050}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const base=process.env.VIBE_TEST_URL,folder='artifacts/vibe-map';fs.mkdirSync(folder,{recursive:true});
  await page.goto(base+'/');await page.locator('#volume-btn').waitFor();
  await page.goto(base+'/vibe-map');await page.locator('#vibe-plane').waitFor();
  assert.match(await page.locator('#vibe-tag-count').textContent(),/^\d+ tags?$/);
  assert.ok(await page.locator('#vibe-tag-count').evaluate(e=>e.previousElementSibling.classList.contains('album')));
  assert.ok(await page.locator('#vibe-forward').isDisabled());
  assert.ok(await page.locator('#vibe-finish').isDisabled());
  await page.screenshot({path:folder+'/map-desktop.png',fullPage:true});
  for(let index=0;index<4;index++){
   await page.locator('#vibe-plane').click({position:{x:90+index*20,y:110+index*15}});
   if(index<3)await page.waitForFunction(index=>document.querySelector('.vibe-step').textContent.includes(`Map ${index+2}`),index);
   else await page.locator('#vibe-finish').waitFor({state:'visible'});
  }
  await page.waitForFunction(()=>!document.querySelector('#vibe-finish').disabled);
  assert.equal(await page.locator('.vibe-radar').count(),0);
  assert.equal(await page.locator('.vibe-axis-center').textContent(),'Present');
  await page.screenshot({path:folder+'/perspective-desktop.png',fullPage:true});
  await page.locator('#vibe-back').click();
  await page.locator('#vibe-plane').press('ArrowRight');
  await page.waitForFunction(()=>document.querySelector('#vibe-save-status').textContent==='All maps saved · finish when ready.');
  assert.equal(await page.locator('audio').count(),1);
  for(const width of [320,360,390,430,768]){
   await page.setViewportSize({width,height:900});await bounded(page,width,'map',folder);
  }
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:folder+'/map-phone.png',fullPage:true});
  await page.setViewportSize({width:1365,height:1050});
  await page.evaluate(()=>window.scrollTo(0,0));
  // ResizeObserver measures the newly responsive card on the next layout frame.
  try{
   await page.waitForFunction(()=>{
    const card=document.querySelector('#vibe-song').getBoundingClientRect(),map=document.querySelector('#vibe-workspace').getBoundingClientRect();
    return Math.abs(card.y+card.height/2-map.y-map.height/2)<8;
   },null,{timeout:5000});
  }catch(error){
   await page.screenshot({path:folder+'/card-placement-failure.png',fullPage:true});
   console.log(await page.locator('#vibe-song').evaluate(e=>({card:e.getBoundingClientRect().toJSON(),map:document.querySelector('#vibe-workspace').getBoundingClientRect().toJSON(),measured:e.style.getPropertyValue('--vibe-card-height'),top:getComputedStyle(e).top,scrollY})));
   throw error;
  }
  await page.locator('#vibe-save-status').scrollIntoViewIfNeeded();
  assert.ok(await page.locator('#vibe-finish').isVisible());
  await page.locator('#vibe-finish').click();await page.locator('.vibe-match').first().waitFor();
  assert.equal(await page.locator('.vibe-match').count(),2);
  assert.equal(await page.locator('.radar-axis').count(),8);
  await page.screenshot({path:folder+'/results-desktop.png',fullPage:true});
  for(const width of [320,360,390,430,768]){
   await page.setViewportSize({width,height:900});
   await bounded(page,width,'results',folder);
  }
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:folder+'/results-phone.png',fullPage:true});
  assert.equal(await page.locator('#vibe-finish').textContent(),'Next song →');
  assert.equal(await page.locator('.vibe-radar-key,#vibe-edit-results').count(),0);
  await page.locator('#vibe-finish').click();
  await page.waitForFunction(()=>document.querySelector('.vibe-song h2').textContent.endsWith('2'));
  assert.ok(await page.locator('#vibe-finish').isDisabled());
  await page.setViewportSize({width:1365,height:1050});await page.goto(base+'/');await page.locator('.mode-card.vibe').waitFor();
  assert.equal(await page.locator('.mode-card').count(),6);
  await page.locator('#home-vibe[aria-busy="false"]').waitFor();await page.locator('#home-vibe-banner').waitFor();
  assert.equal(await page.locator('#overall-highlights + #home-vibe').count(),1);
  assert.equal(await page.locator('#home-vibe .vibe-mini-dot').count(),24);
  assert.ok(await page.locator('#home-vibe-banner').evaluate(e=>e===e.parentElement.lastElementChild));
  assert.equal(await page.locator('[data-vibe-banner-entity]').count(),0);
  assert.equal(await page.locator('#home-vibe-banner').evaluate(e=>getComputedStyle(e).getPropertyValue('--shelf-rgb').replace(/\s/g,'')),'237,101,115');
  for(const entity of ['albums','artists','tags']){
   const cards=page.locator('[data-vibe-banner-kind="'+entity+'"]');
   assert.ok(await cards.count()>0);assert.ok(await cards.count()<=20);
   const colours={albums:'rgb(191, 119, 255)',artists:'rgb(91, 155, 255)',tags:'rgb(255, 184, 51)'};
   assert.equal(await cards.first().locator('h3').evaluate(e=>getComputedStyle(e).color),colours[entity]);
  }
  const scores=await page.locator('[data-vibe-banner-row] strong').allTextContents();
  assert.deepEqual(scores.map(parseFloat),scores.map(parseFloat).sort((a,b)=>b-a));
  await page.locator('#home-vibe').screenshot({path:folder+'/library-home-desktop.png'});
  await page.locator('#home-vibe-banner').screenshot({path:folder+'/vibe-banner-desktop.png'});

  const rows=await page.locator('.mode-card').evaluateAll(nodes=>nodes.map(e=>e.offsetTop));
  assert.deepEqual(rows.slice(0,3),[rows[0],rows[0],rows[0]]);
  assert.deepEqual(rows.slice(3),[rows[3],rows[3],rows[3]]);assert.ok(rows[3]>rows[0]);
  await page.screenshot({path:folder+'/home-desktop.png',fullPage:true});
  await page.setViewportSize({width:430,height:844});
  const widths=await page.locator('.mode-card').evaluateAll(nodes=>nodes.map(e=>Math.round(e.getBoundingClientRect().width)));
  assert.ok(widths.every(w=>w===widths[0]),'All six phone cards have equal width');
  await page.setViewportSize({width:1365,height:1050});await page.goto(base+'/vibe_map_stats');
  await page.locator('[data-vibe-chart]').first().waitFor();
  assert.equal(await page.locator('[data-vibe-chart]').count(),4);
  for(const width of [390,1365]){
   await page.setViewportSize({width,height:1050});
   assert.ok(await page.locator('.vibe-coverage .mode-stats-progress').evaluate(e=>{const a=e.getBoundingClientRect(),b=e.firstElementChild.getBoundingClientRect();return Math.abs(a.top-b.top)<1&&Math.abs(a.height-b.height)<1}),'Coverage fill must occupy full track height');
  }
  await page.locator('.vibe-coverage').screenshot({path:folder+'/coverage-desktop.png'});

  assert.equal(await page.locator('[data-vibe-point]').count(),24);
  assert.equal(await page.locator('.vibe-balance-row').count(),8);
  assert.equal(await page.locator('.vibe-stats-pair').count(),4);
  assert.equal(await page.locator('.vibe-consistency-list').count(),6);
  assert.equal(await page.locator('.vibe-stats-page details,.vibe-stats-page select').count(),0);
  const report=await (await page.request.get(base+'/api/vibe-map/stats')).json();
  assert.equal(report.overview.full,6);assert.ok(report.maps.every(m=>m.points.length===6));
  assert.ok(report.groups.every(g=>g.most.length>0));
  const chart=page.locator('[data-vibe-chart]').first(),svg=chart.locator('svg');
  await svg.focus();await svg.press('Home');
  assert.ok(await chart.locator('[data-vibe-point]').first().evaluate(e=>e===document.activeElement));
  await page.keyboard.press('ArrowRight');
  assert.ok(await chart.locator('.vibe-chart-selection a').isVisible());
  await page.keyboard.press('Enter');
  await page.locator('#vibe-song-inspector .vibe-radar').waitFor();
  assert.equal(new URL(page.url()).pathname,'/vibe_map_stats');
  assert.equal(await page.locator('#vibe-song-inspector .radar-axis').count(),8);
  assert.equal(await page.locator('#vibe-song-inspector .vibe-song-matches .mode-stats-row').count(),2);
  assert.ok(await page.locator('#vibe-song-inspector .vibe-song-identity .song').getAttribute('href'));
  assert.ok(await page.locator('#vibe-song-inspector .vibe-song-identity .artist').getAttribute('href'));
  assert.ok(await page.locator('#vibe-song-inspector .vibe-song-identity .album').getAttribute('href'));
  await page.locator('#vibe-song-inspector').screenshot({path:folder+'/inspector-desktop.png'});
  await page.screenshot({path:folder+'/stats-desktop.png',fullPage:true});
  for(const width of [320,360,390,430,768,1365]){
   await page.setViewportSize({width,height:900});await bounded(page,width,'stats',folder);
   const axisSize=await page.locator('.vibe-map-pole').first().evaluate(e=>parseFloat(getComputedStyle(e).fontSize)*e.ownerSVGElement.getBoundingClientRect().width/540);
   assert.ok(axisSize>=12,'Readable heatmap labels at '+width);
   if(width===1365){const height=await page.locator('#vibe-song-inspector').evaluate(e=>e.getBoundingClientRect().height);assert.ok(height<450,'Compact desktop song panel');}

  }
  await page.setViewportSize({width:390,height:844});
  const nextPoint=page.locator('[data-vibe-point][data-song-id="3"]').first();
  await nextPoint.locator('circle').click();
  await page.waitForFunction(()=>document.querySelector('#vibe-song-inspector .vibe-song-identity .song')?.getAttribute('href')==='/song/3');
  assert.equal(new URL(page.url()).pathname,'/vibe_map_stats');
  await page.locator('#vibe-song-inspector').screenshot({path:folder+'/inspector-phone.png'});
  await page.screenshot({path:folder+'/stats-phone.png',fullPage:true});
  // Dedicated profiles keep Vibe directly above Overall, independently of loading order.
  for(const [kind,path,count] of [['song','/song/2',0],['album','/album/A%20long%20album%20title%20for%20responsive%20testing',12],['artist','/artist/Artist%20with%20a%20longer%20name',24],['tag','/tag/Melancholy',12]]){
   await page.setViewportSize({width:1365,height:1050});await page.goto(base+path);
   await page.locator('#profile-vibe[aria-busy="false"]').waitFor();await page.locator('#overall-profile').waitFor();
   assert.equal(await page.locator('#profile-vibe + #overall-profile').count(),1,kind+' above Overall');
   assert.equal(await page.locator('#profile-vibe .vibe-radar').count(),kind==='song'?1:0);
   if(kind==='song'){
    assert.equal(await page.locator('#profile-vibe .vibe-song-matches .mode-stats-row').count(),2);
    assert.equal(await page.locator('#profile-vibe .vibe-song-identity').count(),0,'No repeated profile identity');
   }else{
    assert.equal(await page.locator('#profile-vibe .vibe-mini-dot').count(),count);
    assert.equal(await page.locator('#profile-vibe .vibe-mini-map').count(),4);
    assert.equal(await page.locator('#profile-vibe .vibe-mini-dot').first().evaluate(e=>e.getBoundingClientRect().width),11);
   }
   await page.locator('#profile-vibe').screenshot({path:folder+'/profile-'+kind+'-desktop.png'});
   for(const width of [320,390,768,1365]){
    await page.setViewportSize({width,height:900});await bounded(page,width,'profile-'+kind,folder);
    if(kind!=='song'){
     const rows=await page.locator('#profile-vibe .vibe-mini-map').evaluateAll(nodes=>nodes.map(e=>e.offsetTop));
     if(width>760)assert.ok(rows.every(top=>top===rows[0]),kind+' four maps in one row');
     else{assert.deepEqual(rows,[rows[0],rows[0],rows[2],rows[2]]);assert.ok(rows[2]>rows[0],kind+' responsive two rows');}
     const plotOffsets=await page.locator('#profile-vibe .vibe-mini-plot').evaluateAll(nodes=>nodes.map(e=>e.getBoundingClientRect().y-e.parentElement.getBoundingClientRect().y));
     assert.ok(Math.max(...plotOffsets)-Math.min(...plotOffsets)<2,'Aligned map captions at '+width);
    }
   }
   await page.setViewportSize({width:390,height:844});await page.locator('#profile-vibe').screenshot({path:folder+'/profile-'+kind+'-phone.png'});
  }
  for(const path of ['/song/7','/album/Unmapped%20album','/artist/Unmapped%20artist','/tag/Unmapped%20tag']){
   await page.goto(base+path);await page.waitForFunction(()=>document.querySelector('#profile-vibe')?.getAttribute('aria-busy')==='false');
   await page.locator('#overall-profile').waitFor();assert.ok(await page.locator('#profile-vibe').isHidden(),'Unmapped profile stays compact');
   assert.equal(await page.locator('#profile-vibe .vibe-profile-content').textContent(),'');
  }
  await page.goto(base+'/global_stats');
  assert.ok(await page.locator('.pulse-bar i.vibe').count()>0);
  assert.ok(await page.locator('#global-activity [data-activity-kind=vibe]').count()>0);
  assert.ok((await page.locator('#global-activity').getAttribute('data-current-modes')).includes('vibe'));
await page.locator('#global-vibe[aria-busy="false"]').waitFor();
  assert.equal(await page.locator('#overall-global + #global-vibe').count(),1);
  assert.equal(await page.locator('#global-vibe .vibe-global-leaders > div').count(),3);
  await page.setViewportSize({width:1365,height:1050});await page.locator('#global-vibe').screenshot({path:folder+'/vibe-global-desktop.png'});
  for(const width of [320,390,768,1365]){await page.setViewportSize({width,height:900});await bounded(page,width,'global-vibe',folder);}
  await page.setViewportSize({width:390,height:844});await page.locator('#global-vibe').screenshot({path:folder+'/vibe-global-phone.png'});
  for(const entity of ['albums','artists','tags']){
   await page.goto(base+'/mode_rankings/vibe?entity='+entity);await page.locator('#vibe-ranking-rows .leader-row').first().waitFor();
   assert.equal(await page.locator('.rank-links a').count(),3);assert.equal(await page.locator('.rank-links a[href*="entity=songs"]').count(),0);
   assert.ok(await page.locator('.leader-row').count()<=20);
   if(entity==='albums')assert.ok(!(await page.locator('.leader-title').first().getAttribute('href')).includes('undefined'));
   await page.locator('[data-vibe-view="bottom"]').click();await page.waitForFunction(()=>document.querySelector('#vibe-ranking-rows .leader-row'));
   assert.ok(page.url().includes('view=bottom'));assert.ok(await page.locator('.leader-row').count()<=20);
   for(const width of [320,390,768,1365]){await page.setViewportSize({width,height:900});await bounded(page,width,'vibe-ranking-'+entity,folder);}
   if(entity==='tags'){await page.screenshot({path:folder+'/vibe-ranking-desktop.png',fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:folder+'/vibe-ranking-phone.png',fullPage:true});}
  }
  await page.goto(base+'/');await page.locator('#home-vibe[aria-busy="false"]').waitFor();
  await page.setViewportSize({width:390,height:844});await bounded(page,390,'home-vibe',folder);
  await page.locator('#home-vibe').screenshot({path:folder+'/library-home-phone.png'});await page.locator('#home-vibe-banner').screenshot({path:folder+'/vibe-banner-phone.png'});
  await page.goto(base+'/dev/login');await page.locator('input[name="pin"]').fill('vibe-test-pin');
  await Promise.all([page.waitForURL('**/dev/dashboard'),page.locator('.login-panel button[type="submit"]').click()]);
  await page.goto(base+'/dev/dashboard?view=vibe_records');await page.locator('[data-vibe-edit="1"]').waitFor();
  await page.locator('[data-vibe-edit="1"]').click();await page.locator('#dev-vibe-save').waitFor();
  await page.locator('[name="pace_mood:x"]').fill('4.25');
  assert.equal(await page.locator('[data-vibe-map-tab]').count(),4);await page.locator('[name="pace_mood:x"]').fill('');await page.locator('[data-vibe-map-tab]').nth(1).click();assert.equal(await page.locator('[data-vibe-map-tab="pace_mood"]').getAttribute('aria-pressed'),'true');await page.locator('[name="pace_mood:x"]').fill('4.25');await page.locator('[data-vibe-map-tab]').nth(1).click();await page.locator('[data-vibe-map-tab="pace_mood"]').click();assert.equal(await page.locator('[name="pace_mood:x"]').inputValue(),'4.25');
  await page.locator('#dev-vibe-save button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Vibe data saved'));await page.locator('#dev-vibe-search button:enabled').waitFor();
  const maintained=await (await page.request.get(base+'/api/dev/vibe/1')).json();
  assert.equal(maintained.maps.find(m=>m.id==='pace_mood').x,.85);
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-vibe',folder);await page.locator('#dev-vibe-editor').screenshot({path:folder+'/dev-vibe-'+width+'.png'});}
  await page.locator('[data-vibe-clear-map="pace_mood"]').click();await page.locator('#dev-vibe-save button[type="submit"]').click();
  await page.locator('#dev-vibe-search button:enabled').waitFor();
  await page.locator('.dev-vibe-delete > summary').click();
  await page.locator('#dev-vibe-delete [name="confirmation"]').fill('DELETE VIBE');await page.locator('#dev-vibe-delete button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Vibe data deleted'));
  const removed=await (await page.request.get(base+'/api/dev/vibe/1')).json();assert.ok(removed.maps.every(m=>m.status==='unmapped'));assert.equal(removed.completed_passes,0);
  // Real tag review/apply and native 30-second preview; all data is disposable.
  await page.request.post(base+'/tag-test-enable');await page.goto(base+'/dev/dashboard?view=tag_workbench');await page.locator('.tag-single').waitFor();
  assert.equal(await page.locator('[data-tags-mode="single"]').getAttribute('aria-pressed'),'true');
  await page.locator('#tag-sort').selectOption('title',{force:true});await page.locator('[data-tags-edit="1"]').click();
  await page.waitForFunction(()=>{const a=document.querySelector('#tag-audio');return a&&!a.paused&&a.readyState>=2});
  assert.ok(await page.locator('[data-tags-choice="1"]').isChecked());assert.ok(await page.locator('#tag-audio').evaluate(a=>a.loop));
  await page.locator('#tag-seek').evaluate(e=>{e.value='15';e.dispatchEvent(new Event('input',{bubbles:true}))});
  await page.waitForFunction(()=>document.querySelector('#tag-audio').currentTime>=14.9);
  await page.locator('#tag-audio').evaluate(a=>a.currentTime=29.8);await page.waitForFunction(()=>document.querySelector('#tag-audio').currentTime<2);
  await page.locator('[data-tags-choice="2"]').check();await page.locator('#tag-new-names').fill('Bench test tag');await page.locator('#tag-review-button').click();
  await page.waitForFunction(()=>document.querySelector('[data-tag-song="2"]')?.classList.contains('tag-selected'));
  const tagged=await (await page.request.get(base+'/api/collection')).json(),taggedSong=tagged.songs.find(s=>s.id===1);
  assert.ok(taggedSong.tag_ids.includes(tagged.tags.find(t=>t.name==='Bench test tag').id));assert.ok(taggedSong.tag_ids.includes(2));
  assert.ok(await page.locator('[data-tags-choice="1"]').isChecked());assert.ok(!(await page.locator('[data-tags-choice="2"]').isChecked()));
  await page.locator('[data-tags-next-song]').click();await page.waitForFunction(()=>document.querySelector('[data-tag-song="3"]')?.classList.contains('tag-selected'));
  await page.locator('#tag-count-rule').selectOption('less',{force:true});await page.locator('#tag-count-value').fill('2');
  assert.equal(await page.locator('[data-tag-song="1"]').count(),0);
  for(const width of [320,390,768,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'tag-bench',folder);await page.screenshot({path:folder+'/tag-bench-'+width+'.png',fullPage:true});}
  await page.locator('[data-tags-mode="bulk"]').click();assert.equal(await page.locator('[data-tags-mode="bulk"]').getAttribute('aria-pressed'),'true');
  // Isolate only the Git transport: real served Dev markup/scripts and confirmation UI.
  const gitChoice={available:true,state:'behind',branch:'main',remote:'origin',target:'main',destination:'example.org/owner/app',tracking_head:'abc',ahead:0,behind:1,pending_code:false,code_changes:0,in_progress:false,review_token:'browser-git-review',history:[],snapshot:{exists:true,name:'database_backup.sql',bytes:20}};
  await page.route('**/api/dev/system',async route=>{const response=await route.fetch();const body=await response.json();body.git=gitChoice;await route.fulfill({json:body});});
  const gitDetails={code:'database_conflict',reason:'different_device',message:'Device 2 changed the remote database; compare copies.',local_hash:'a'.repeat(64),remote_hash:'b'.repeat(64),baseline_hash:'c'.repeat(64),local_device:1,remote_device:2,remote_time:'2026-10-23T10:00:00Z',snapshot_commit:'d'.repeat(40),local_songs:7,remote_songs:7,different_rows:{song_vibe_positions:{added:0,removed:24,edited:4}},local_changes:{songs:{added:0,removed:0,edited:1}},remote_changes:{song_vibe_positions:{added:24,removed:0,edited:0}}};
  await page.route('**/api/dev/git/check',route=>route.fulfill({json:{ok:true,message:'Fresh comparison complete',git:{...gitChoice,status_source:'checked',checked_at:'2026-10-22T12:00:00Z',upload_ready:false,database_sync:gitDetails}}}));
  await page.route('**/api/dev/git/keep-local/review',route=>route.fulfill({json:{ok:true,local:{Songs:7,'Vibe positions':0},remote:{Songs:7,'Vibe positions':24},choice_token:'browser-choice',details:gitDetails,git:gitChoice,message:'Compare both copies.'}}));
  let kept=0,remoteApplied=0,compacted=0;
  await page.route('**/api/dev/git/use-remote',async route=>{assert.deepEqual(route.request().postDataJSON(),{choice_token:'browser-choice',confirmation:'USE REMOTE'});remoteApplied++;await route.fulfill({json:{ok:true,git:gitChoice,message:'Reviewed remote database loaded.'}});});
  await page.route('**/api/dev/git/compact',async route=>{assert.deepEqual(route.request().postDataJSON(),{review_token:'browser-git-review'});compacted++;await route.fulfill({json:{ok:true,git:{...gitChoice,storage:{object_bytes:1024,loose_objects:0,packs:1}},before:{object_bytes:4096},after:{object_bytes:1024},message:'Git storage compacted.'}});});
  await page.route('**/api/dev/git/keep-local',async route=>{assert.deepEqual(route.request().postDataJSON(),{choice_token:'browser-choice',confirmation:'KEEP LOCAL'});kept++;await route.fulfill({json:{ok:true,git:gitChoice,message:'Local database kept. Restart then upload.'}});});
  await page.goto(base+'/dev/dashboard?view=export');await page.locator('[data-system-local-review]:enabled').waitFor();await page.waitForFunction(()=>document.querySelector('#system-note').textContent.includes('Fresh comparison'));for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-git',folder);await page.screenshot({path:folder+'/dev-git-'+width+'.png',fullPage:true});}
  assert.ok(await page.locator('[data-system-upload]').isDisabled());
  await page.locator('[data-system-local-review]').click();await page.locator('#system-local-confirmation').waitFor();
  assert.ok(await page.locator('[data-system-local-apply]').isDisabled());assert.equal(await page.locator('.git-comparison-summary').getAttribute('open'),null);
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-keep-local',folder);await page.locator('#system-local-choice').screenshot({path:folder+'/dev-keep-local-'+width+'.png'});}
  await page.locator('#system-local-confirmation').fill('KEEP LOCAL');await page.locator('[data-system-local-apply]').click();
  await page.waitForFunction(()=>document.querySelector('#system-note').textContent.includes('Local database kept'));
  assert.equal(kept,1);
  await page.locator('[data-system-local-review]').click();await page.locator('#system-local-confirmation').waitFor();
  assert.ok((await page.locator('.git-hashes').allTextContents()).some(text=>text.includes(gitDetails.remote_hash)));
  await page.locator('#system-local-confirmation').fill('KEEP LOCAL');await page.locator('#system-database-choice').selectOption('remote');
  assert.equal(await page.locator('#system-local-confirmation').inputValue(),'');assert.ok(await page.locator('[data-system-local-apply]').isDisabled());
  await page.locator('.git-row-differences summary').last().click();
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-remote-choice',folder);await page.locator('#system-local-choice').screenshot({path:folder+'/dev-remote-choice-'+width+'.png'});}
  await page.locator('#system-local-confirmation').fill('USE REMOTE');await page.locator('[data-system-local-apply]').click();await page.waitForFunction(()=>document.querySelector('#system-note').textContent.includes('Reviewed remote database loaded'));assert.equal(remoteApplied,1);
  await page.locator('[data-system-compact]').click();await page.waitForFunction(()=>document.querySelector('#system-note').textContent.includes('Git storage compacted'));assert.equal(compacted,1);
assert.ok(await page.locator('[data-system-upload]').isDisabled());
  await page.goto(base+'/dev/dashboard');await page.locator('.dev-home-areas').waitFor();
  assert.equal(await page.locator('.dev-navbar').count(),1);assert.equal(await page.locator('.nav-matches,.dev-sidebar,.dev-taskbar,.dev-category').count(),0);
  assert.equal(await page.locator('#dev-page-menu > a').count(),4);assert.equal(await page.locator('.dev-home-status > section').count(),3);assert.equal(await page.locator('.dev-home-areas [data-dev]').count(),27);
  for(const width of [390,768,1365,1800]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-home',folder);if(width>1100){const sizes=await page.locator('.dev-home-status > section').evaluateAll(nodes=>nodes.map(e=>({y:e.getBoundingClientRect().y,h:e.getBoundingClientRect().height})));assert.ok(sizes.every(s=>Math.abs(s.y-sizes[0].y)<2&&Math.abs(s.h-sizes[0].h)<2),'Aligned equal service cards');const bottoms=await page.locator('.dev-home-status > section').evaluateAll(nodes=>nodes.map(node=>(node.querySelector('.system-actions')||node.querySelector(':scope > .btn')).getBoundingClientRect().bottom));assert.ok(bottoms.every(y=>Math.abs(y-bottoms[0])<2),'Home status actions align');assert.ok(await page.locator('.dev-home-areas h2 a').evaluateAll(nodes=>nodes.every(node=>parseFloat(getComputedStyle(node).fontSize)>=26)),'Home section headings follow shared typography');}await page.screenshot({path:folder+'/dev-home-'+width+'.png',fullPage:true});}
  for(const area of ['library','modes','tools']) {
    await page.locator('#dev-page-menu [data-dev="'+area+'"]').click();await page.locator('.dev-destinations').waitFor();
    for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-'+area,folder);await page.screenshot({path:folder+'/dev-'+area+'-'+width+'.png',fullPage:true});}
  }
  await page.goto(base+'/dev/library/albums');await page.locator('[data-edit="albums"][data-id="1"]').click();
  await page.locator('#field-shelves_excluded').waitFor();assert.ok(!(await page.locator('#field-shelves_excluded').isChecked()));
  await page.locator('#field-shelves_excluded').check();const excludeSaved=page.waitForResponse(r=>r.url().endsWith('/api/dev/edit_album/1')&&r.request().method()==='POST');await page.locator('#editor-submit').click();assert.equal((await excludeSaved).status(),200);await page.locator('#field-shelves_excluded').waitFor({state:'hidden'});
  await page.goto(base+'/song/1');await page.locator('#overall-profile').waitFor();assert.equal(await page.locator('[data-profile-panel="shelves"]').count(),0,'Excluded song has no Shelves panel');
  await page.goto(base+'/dev/library/albums');
  await page.locator('[data-edit="albums"][data-id="1"]').click();await page.locator('#field-shelves_excluded').waitFor();assert.ok(await page.locator('#field-shelves_excluded').isChecked(),'Saved exclusion is reflected when reopened');
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'album-shelves-flag',folder);await page.screenshot({path:folder+'/album-shelves-flag-'+width+'.png',fullPage:true})}
  await page.locator('#field-shelves_excluded').uncheck();const includeSaved=page.waitForResponse(r=>r.url().endsWith('/api/dev/edit_album/1')&&r.request().method()==='POST');await page.locator('#editor-submit').click();assert.equal((await includeSaved).status(),200);await page.locator('#field-shelves_excluded').waitFor({state:'hidden'});
  await page.goto(base+'/dev/library/songs');await page.locator('#manage-rows [data-edit]').first().waitFor();
  for(const type of ['songs','artists','albums','tags']) {
    if(type!=='songs'){await page.goto(base+'/dev/library/'+type);await page.locator('#manage-rows [data-edit]').first().waitFor();}
    for(const width of [390,1365]) {
      await page.setViewportSize({width,height:850});
      await page.locator('[data-table-panel="filters"]').first().click();
      assert.equal(await page.locator('#table-filters').evaluate(e=>getComputedStyle(e).position),'static');
      await page.locator('#table-filter-field').selectOption('id');await page.locator('#table-filter-op').selectOption('gte');await page.locator('#table-filter-value').fill('1');await page.locator('#table-filter-form [type="submit"]').click();
      assert.ok(await page.locator('[data-remove-table-filter="id"]').isVisible());
      await page.locator('[data-remove-table-filter="id"]').click();
      await page.locator('[data-table-panel="columns"]').first().click();assert.ok(await page.locator('#table-columns').isVisible());await page.locator('[data-table-panel="columns"]').first().click();
      assert.ok(await page.locator('.dev-catalog-scroll').evaluate(e=>e.scrollHeight<=e.clientHeight+1),'Catalogue has no inner vertical scrolling');
      const more=page.locator('[data-record-more]').last();await more.click();await page.locator('#dev-record-menu').waitFor();
      assert.ok(await page.locator('#dev-record-menu').evaluate(e=>e.parentElement===document.body));
      assert.ok(await page.locator('#dev-record-menu').evaluate(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1}),'More stays inside viewport');
      await bounded(page,width,'dev-table-'+type,folder);await page.screenshot({path:folder+'/dev-table-'+type+'-'+width+'.png'});
      await page.keyboard.press('Escape');await page.locator('#dev-record-menu').waitFor({state:'detached'});assert.equal(await more.getAttribute('aria-expanded'),'false');
    }
  }
  await page.goto(base+'/dev/library/songs');await page.locator('#manage-rows [data-edit]').first().waitFor();
  await page.locator('[data-edit="songs"][data-id="1"]').first().click();await page.locator('#dev-editor-slot #field-title').waitFor();assert.ok(!(await page.locator('#editor').evaluate(e=>e.matches(':modal'))));
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-editor',folder);await page.screenshot({path:folder+'/dev-editor-'+width+'.png',fullPage:true});}
  await page.locator('#field-title').fill('Unsaved draft');await page.locator('#dev-page-menu [data-dev="tools"]').click();await page.locator('#dev-unsaved:not([hidden])').waitFor();assert.equal(await page.locator('#field-title').inputValue(),'Unsaved draft');assert.ok(page.url().endsWith('/dev/library/songs'));
  await page.locator('[data-workspace-stay]').click();assert.equal(await page.locator('#field-title').inputValue(),'Unsaved draft');await page.locator('#dev-page-menu [data-dev="tools"]').click();await page.locator('[data-workspace-discard]').click();await page.locator('.dev-destinations').waitFor();assert.ok(page.url().endsWith('/dev/tools'));
  await page.locator('.dev-destinations [data-dev="database"]').click();await page.locator('[data-db-object="songs"]').click();await page.locator('.db-rows').waitFor();assert.equal(await page.locator('#system-backups').count(),0);
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-database',folder);await page.screenshot({path:folder+'/dev-database-'+width+'.png',fullPage:true});}
  await page.locator('[data-db-tab="columns"]').click();assert.ok((await page.locator('#db-content').textContent()).includes('Primary key'));
  await page.locator('[data-db-tab="definition"]').click();assert.ok((await page.locator('.db-definition').textContent()).includes('CREATE TABLE'));
  await page.locator('[data-db-tab="rows"]').click();await page.locator('[data-db-cell="0"][data-db-column="1"]').click();await page.locator('.db-cell-detail').waitFor();assert.ok(await page.locator('#editor-submit').isHidden());await page.locator('#editor-close').click();
  await page.locator('#dev-section-nav [data-dev="backups"]').click();await page.locator('#system-backups').waitFor();assert.equal(await page.locator('#system-inventory').count(),0);
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-backups',folder);await page.screenshot({path:folder+'/dev-backups-'+width+'.png',fullPage:true});}
  await page.locator('#dev-section-nav [data-dev="guides"]').click();await page.locator('.dev-guide-article h1').waitFor();await page.locator('[data-dev-guide="technical"]').click();await page.waitForFunction(()=>document.querySelector('.dev-guide-article h1')?.textContent.includes('technical'));assert.ok((await page.locator('.dev-guide-contents a').count())>10);
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await page.evaluate(()=>window.scrollTo(0,0));await bounded(page,width,'dev-guide',folder);await page.screenshot({path:folder+'/dev-guide-'+width+'.png'});}
  // Guide rendering stays usable when the host's Markdown dependency is absent.
  const plainGuide='# Developer guide\n\nC:\\Song_ranker\\'+('long_folder_'.repeat(30))+'\n\n<script>shown as text</script>';
  const safeGuide=plainGuide.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  await page.route('**/api/dev/help/dev?format=html',route=>route.fulfill({json:{html:'<pre class="dev-guide-source">'+safeGuide+'</pre>',toc:'',warning:'Formatted rendering is unavailable because the Markdown package could not be loaded. The guide is shown as plain text.',install_command:'python -m pip install -r requirements.txt'}}));
  await page.locator('[data-dev-guide="dev"]').click();await page.locator('.dev-guide-source').waitFor();
  assert.equal(await page.locator('.dev-guide-contents').count(),0);assert.ok((await page.locator('.dev-guide-notice').textContent()).includes('python -m pip install -r requirements.txt'));
  assert.equal(await page.locator('.dev-guide-source script').count(),0);assert.equal(await page.locator('.dev-guide-source').textContent(),plainGuide);
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-guide-plain',folder);assert.equal(await page.locator('.dev-guide-source').evaluate(e=>getComputedStyle(e).whiteSpace),'pre-wrap');await page.screenshot({path:folder+'/dev-guide-plain-'+width+'.png',fullPage:true});}
  await page.unroute('**/api/dev/help/dev?format=html');await page.locator('[data-dev-guide="technical"]').click();await page.locator('.dev-guide-contents').waitFor();assert.equal(await page.locator('.dev-guide-notice').count(),0);
  await page.locator('.dev-nav-actions input[name=q]').fill('long title');await page.locator('.dev-nav-actions form button').click();await page.locator('#dev-query').waitFor();assert.equal(await page.locator('#dev-query').inputValue(),'long title');
  await page.locator('.dev-lock').click();await page.waitForURL(base+'/');
  // Main-header shutdown needs a PIN once and does not unlock Dev.
  await page.locator('.app-stop-button').click();await page.locator('#stop-pin').waitFor();
  assert.ok(await page.locator('[data-stop-prepare]').isDisabled(),'Externally served browser fixture cannot terminate its host');
  await page.locator('#editor-close').click();
  await page.goto(base+'/global_stats');assert.equal(await page.locator('.listening-panel,script[src*="/listening.js"]').count(),0);
  await page.request.post(base+'/voting-test-enable');await page.goto(base+'/voting_stats');await page.locator('.voting-stats-page').waitFor();
  assert.equal(await page.locator('.voting-stats-page details').count(),1,'Only the useful daily-figures disclosure remains');
  assert.ok((await page.locator('[aria-labelledby="vote-distribution"]').textContent()).includes('4 voted-track ratings · 3 tracks without matches excluded'));
  assert.ok(!(await page.locator('[aria-labelledby="vote-distribution"]').textContent()).includes('9000'),'Unplayed high Elo is excluded');
  assert.equal(await page.locator('.voting-mode-blind .mode-stats-small-metrics dd').first().evaluate(e=>getComputedStyle(e).color),'rgb(85, 214, 194)');
  for(const [kind,colour] of [['artist','rgb(91, 155, 255)'],['album','rgb(191, 119, 255)'],['tag','rgb(255, 184, 51)']])assert.equal(await page.locator('#vote-'+kind).evaluate(e=>getComputedStyle(e).color),colour);
  for(const width of [390,768,1365]){
    await page.setViewportSize({width,height:1050});await bounded(page,width,'voting-stats',folder);
    for(const id of ['vote-overview','vote-modes','vote-coverage','vote-distribution'])await page.locator(`[aria-labelledby="${id}"]`).screenshot({path:folder+'/'+id+'-'+width+'.png'});
  }
  await page.locator('.voting-history-filter .pill.tournament').click();await page.locator('.voting-history-filter .pill.tournament.active').waitFor();
  assert.equal(await page.locator('.voting-history-filter .pill.tournament.active').evaluate(e=>getComputedStyle(e).color),'rgb(255, 120, 166)');
  // Disc answers stay hidden while playing; repeated within-disc numbers grade in disc order.
  const discData=await (await page.request.post(base+'/shelves-test-enable')).json();
  const shelfMedia=[];page.on('request',r=>{if(r.url().includes('/tag-test-audio.wav?shelf='))shelfMedia.push(r.url())});
  const offeredRequest=page.waitForResponse(r=>r.url().endsWith('/api/album-shelves/round')&&r.request().method()==='POST');
  await page.goto(base+'/album_shelves');
  const offered=await (await offeredRequest).json();await page.locator('.shelf-track').first().waitFor();
  assert.equal(offered.songs.length,10);assert.ok(offered.albums.some(a=>a.disc_count===2));
  assert.ok(offered.songs.every(s=>!('disc_number' in s)&&!('track_number' in s)));
  assert.equal(await page.locator('.shelf-position-actual').count(),0);
  assert.ok(await page.locator('#shelf-perfect').isHidden(),'No celebration while arranging');
  assert.equal(shelfMedia.length,0,'Shelves round loading requests no audio');
  const playSlot=async song=>{await page.locator(`[data-shelf-preview="${song.slot}"]`).click();await page.waitForFunction(title=>document.querySelector('#shelf-preview-info').textContent===title,song.title);await page.waitForFunction(()=>{const a=document.querySelector('#shelf-preview-audio');return a&&!a.paused&&a.currentTime>0})};
  await playSlot(offered.songs[0]);
  await page.evaluate(slots=>{for(const slot of slots)document.querySelector(`[data-shelf-preview="${slot}"]`).click()},[offered.songs[6].slot,offered.songs[2].slot]);
  await page.waitForFunction(title=>document.querySelector('#shelf-preview-info').textContent===title,offered.songs[2].title);
  await page.waitForFunction(()=>[...document.querySelectorAll('audio')].filter(a=>!a.paused).length===1);
  await page.waitForTimeout(800);
  assert.equal(await page.locator('audio[src]').count(),1,'No retired loop or ahead-loaded media');
  assert.ok(shelfMedia.every(url=>[offered.songs[0],offered.songs[6],offered.songs[2]].some(s=>new URL(url).searchParams.get('shelf')===String(s.id))),'Only explicitly selected songs loaded');
  await page.locator('#shelf-preview-audio').evaluate(a=>a.currentTime=8);
  await page.waitForFunction(()=>document.querySelector('#shelf-preview-audio').currentTime>=8);
  await page.locator('#shelf-preview-audio').evaluate(a=>a.currentTime=10.2);
  await page.waitForFunction(title=>document.querySelector('#shelf-preview-info').textContent===title,offered.songs[3].title);
  assert.equal(await page.locator('audio').evaluateAll(nodes=>nodes.filter(a=>!a.paused).length),1,'Seek advances once from the user-selected song');
  await page.locator('[data-shelf-play]').click();await page.waitForFunction(()=>[...document.querySelectorAll('audio')].every(a=>a.paused));
  const order=[...discData.songs].sort((a,b)=>a.album_id-b.album_id||a.disc_number-b.disc_number||a.track_number-b.track_number);
  for(const song of order){
    const item=offered.songs.find(s=>s.id===song.id),album=offered.albums.find(a=>a.id===song.album_id);
    await page.locator(`[data-shelf-slot="${item.slot}"] summary`).click();
    await page.locator(`[data-shelf-pick="${item.slot}"][data-shelf-target="${album.slot}"]`).click();
  }
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'shelves-discs-play',folder);await page.screenshot({path:folder+'/shelves-discs-play-'+width+'.png',fullPage:true});}
  await page.locator('[data-shelf-check]').click();await page.locator('[data-shelf-next]').waitFor({state:'visible',timeout:90000});
  assert.equal(await page.locator('#shelf-running-score').textContent(),'30.00');
  assert.ok(await page.locator('#shelf-perfect').isVisible(),'Perfect round gets compact feedback after reveal');
  await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('#shelf-perfect').evaluate(e=>getComputedStyle(e).animationName),'none');await page.emulateMedia({reducedMotion:'no-preference'});
  assert.ok((await page.locator('.shelf-position-actual').allTextContents()).some(t=>t.includes('2·')));
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'shelves-discs-result',folder);await page.screenshot({path:folder+'/shelves-discs-result-'+width+'.png',fullPage:true});}
  // Actual grading: one adjacent swap is a near miss; the other album is reversed.
  await page.route('**/api/album-shelves/round',async route=>{const response=await route.fetch(),data=await response.json();data.songs.forEach(s=>s.audio_url='');await route.fulfill({response,json:data})});
  const partialRequest=page.waitForResponse(r=>r.url().endsWith('/api/album-shelves/round')&&r.request().method()==='POST');await page.goto(base+'/album_shelves');const partial=await(await partialRequest).json();await page.locator('.shelf-track').first().waitFor();
  assert.ok(await page.locator('#shelf-perfect').isHidden(),'Next round resets celebration');
  for(const [index,album] of partial.albums.entries()){
    const tracks=order.filter(s=>s.album_id===album.id);if(index===0)[tracks[0],tracks[1]]=[tracks[1],tracks[0]];else tracks.reverse();
    for(const song of tracks){const item=partial.songs.find(s=>s.id===song.id);await page.locator(`[data-shelf-slot="${item.slot}"] summary`).click();await page.locator(`[data-shelf-pick="${item.slot}"][data-shelf-target="${album.slot}"]`).click()}
  }
  await page.locator('[data-shelf-check]').click();await page.locator('[data-shelf-next]').waitFor({state:'visible',timeout:90000});
  assert.ok(await page.locator('#shelf-perfect').isHidden(),'Partial round does not celebrate');
  const shades=await page.locator('.shelf-track.answer-wrong').evaluateAll(rows=>rows.map(e=>({depth:Number(e.style.getPropertyValue('--shelf-error-depth')),fill:getComputedStyle(e).backgroundColor})));
  assert.ok(shades.some(s=>s.depth>0&&s.depth<1)&&shades.some(s=>s.depth===1),'Near and complete order errors use different severity');assert.ok(new Set(shades.map(s=>s.fill)).size>=2,'Browser renders distinct red shades');
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'shelves-error-depth',folder);await page.screenshot({path:folder+'/shelves-error-depth-'+width+'.png',fullPage:true})}
  await page.goto(base+'/album_shelves_stats');
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'shelves-discs-stats',folder);await page.screenshot({path:folder+'/shelves-discs-stats-'+width+'.png',fullPage:true});}
  // Saved visual brackets and the real final -> replay -> podium handoff.
  await page.request.post(base+'/tournament-test-enable');
  for(const [mode,path] of [['vote','/game'],['guesser','/elo_guesser'],['tournament','/tournament?tournament=77']]){
   await page.goto(base+path);await page.locator('.matchup .match-cover .cover-button').first().waitFor();
   const covers=page.locator('.matchup .match-cover');
   assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::before').animationName),'none','Idle cover stays soft');
   await covers.first().locator('.cover-button').click();await covers.first().locator('.cover-button[data-playing="true"][data-preview-state="playing"]').waitFor();
   assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::before').animationName),'cover-glow-orbit',mode+' playing rim orbits');
   assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::after').animationName),'cover-glow-wave',mode+' playing cover emits a wave');
   assert.equal(await covers.nth(1).evaluate(e=>getComputedStyle(e,'::before').animationName),'none','Other cover stays soft');
   assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::after').pointerEvents),'none','Glow never blocks the cover');
   for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'cover-glow-'+mode,folder);await page.screenshot({path:folder+'/cover-glow-'+mode+'-'+width+'.png',fullPage:true});}
   await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::before').animationName),'none','Reduced motion keeps a stationary rim');assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::after').animationName),'none','Reduced motion suppresses the wave');await page.emulateMedia({reducedMotion:'no-preference'});
   await covers.first().evaluate(e=>e.querySelector('audio').dispatchEvent(new Event('waiting')));assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::before').animationName),'none','Buffering stops the orbit');
   await covers.first().evaluate(e=>e.querySelector('audio').pause());await covers.first().locator('.cover-button[data-playing="false"]').waitFor();assert.equal(await covers.first().evaluate(e=>getComputedStyle(e,'::after').animationName),'none','Pause stops the wave');
  }

  assert.equal(await page.locator('#preview-loudness-balance').count(),0,'Loudness balancing control is removed');
  await page.locator('[data-audio="bracket-audio-0"]').click();await page.locator('[data-audio="bracket-audio-0"][data-preview-state="playing"]').waitFor();
  await page.waitForTimeout(1600);assert.equal(await page.locator('#bracket-audio-0').evaluate(a=>a.volume),await page.evaluate(()=>window.PreviewPlayback.getVolume()),'Native preview follows the site volume');
  await page.locator('[data-audio="bracket-audio-0"]').click();
  const localCatalog=await (await page.request.get(base+'/api/collection')).json();
  for(const [kind,entity,id] of [['artist',localCatalog.artists.find(a=>a.id===1),77],['album',localCatalog.albums.find(a=>a.id===1),78]]){
   await page.goto(base+'/'+kind+'/'+encodeURIComponent(entity.name||entity.title));await page.locator('#tournament').waitFor();
   const history=page.locator('#tournament details').filter({has:page.locator('a[href="/tournament/'+id+'/bracket"]')});await history.locator('summary').click();
   await history.locator('a[href="/tournament/'+id+'/bracket"]').waitFor();assert.ok((await history.textContent()).includes('matches'),'Local history has raw match summaries');
   for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'local-brackets-'+kind,folder);await page.locator('#tournament').screenshot({path:folder+'/local-brackets-'+kind+'-'+width+'.png'});}
  }
  await page.goto(base+'/tournament_stats?tournament=77');
  assert.equal(await page.locator('[data-tournament-map]').count(),0);
  assert.equal(await page.locator('.ts-entity-artist h2').evaluate(e=>getComputedStyle(e).color),'rgb(91, 155, 255)');
  assert.equal(await page.locator('.ts-blind-and-non-blind > span').first().evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(85, 214, 194)');
  await page.locator('#tournament-77 a[href="/tournament/77/bracket"]').click();await page.locator('#tournament-77 .bracket-node').first().waitFor();
  assert.equal(await page.locator('#tournament-77 .bracket-node').count(),8);
  assert.equal(await page.locator('[data-map-round],[data-map-half]').count(),0,'Stage selectors are removed');
  assert.ok(await page.locator('#tournament-77 .bracket-track').first().evaluate(e=>e.getBoundingClientRect().height>=44),'Bracket tracks keep touch-sized targets');
  const pan=page.locator('#tournament-77 .bracket-viewport');await pan.evaluate(e=>{e.style.width='min(100%, 600px)';e.style.height='300px';e.scrollLeft=100;e.scrollTop=0;});const panBox=await pan.boundingBox();const beforePan=await pan.evaluate(e=>({x:e.scrollLeft,y:e.scrollTop}));
  await page.mouse.move(panBox.x+180,panBox.y+180);await page.mouse.down();await page.mouse.move(panBox.x+100,panBox.y+120,{steps:8});await page.mouse.up();
  const afterPan=await pan.evaluate(e=>({x:e.scrollLeft,y:e.scrollTop}));assert.ok(afterPan.x>beforePan.x&&afterPan.y>beforePan.y,'Mouse drag pans both axes');assert.equal(await page.locator('#tournament-77 .is-route').count(),0,'Dragging does not select a track');await pan.evaluate(e=>{e.style.removeProperty('width');e.style.removeProperty('height');});
  await page.locator('#tournament-77 [data-map-track="20"]').first().click();assert.ok((await page.locator('#tournament-77 .bracket-inspector').textContent()).includes('Bracket track 20'));
  assert.equal(await page.locator('#tournament-77 .is-route').count(),3);
  assert.ok(await page.locator('.bracket-inspector').evaluate(e=>e.parentElement.classList.contains('bracket-node')),'Details drop from the chosen match');
  await page.keyboard.press('Escape');assert.equal(await page.locator('.bracket-inspector').count(),0);await page.locator('#tournament-77 [data-map-track="20"]').first().click();
  for(const width of [390,768,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'tournament-map',folder);const frame=await page.locator('.bracket-viewport').boundingBox();assert.ok(Math.abs(frame.x)<1&&Math.abs(frame.width-width)<1,'Bracket spans the full page width');assert.equal(await page.locator('.bracket-viewport').evaluate(e=>getComputedStyle(e).borderTopWidth),'0px');assert.ok(frame.height>=950,'Bracket gets nearly a full viewport of height');await page.evaluate(()=>scrollTo(0,document.querySelector('.bracket-viewport').getBoundingClientRect().top+scrollY));assert.ok(await page.locator('.bracket-viewport').evaluate(e=>Math.abs(e.getBoundingClientRect().top)<2),'Page can scroll the banner out of view');await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:folder+'/tournament-map-'+width+'.png',fullPage:true})}
  await page.goto(base+'/tournament?tournament=77');await page.locator('[data-tournament-vote="0"]').waitFor();assert.equal(await page.locator('#main a[href="/tournament/77/bracket"]').count(),0,'Active matches omit the archive bracket link');await page.locator('[data-tournament-vote="0"]').click();
  await page.locator('#tournament-replay .bracket-node').first().waitFor({timeout:30000});
  assert.equal(await page.locator('.winner-podium').count(),0,'Bracket replay precedes podium');
  assert.ok(await page.locator('#tournament-replay audio').count()<=2,'Only the incoming clip and fading tail can exist');
  assert.equal(await page.locator('[data-map-sound]').getAttribute('aria-pressed'),'true','Replay starts with sound enabled');
  await page.locator('[data-map-sound]').click();await page.locator('[data-map-skip]').click();await page.locator('.winner-podium').waitFor();
  assert.equal(await page.locator('#tournament-replay').count(),0);assert.equal(await page.locator('audio').evaluateAll(a=>a.filter(x=>!x.paused).length),0,'Sound off remains off on the podium');
  await page.locator('[data-replay-bracket]').click();await page.locator('#tournament-replay').waitFor();await page.locator('[data-map-skip]').click();await page.locator('.winner-podium').waitFor();
  await page.emulateMedia({reducedMotion:'reduce'});await page.locator('[data-replay-bracket]').click();await page.locator('.winner-podium').waitFor();assert.equal(await page.locator('#tournament-replay').count(),0,'Reduced motion skips staged animation');await page.emulateMedia({reducedMotion:'no-preference'});
  assert.deepEqual(errors,[]);console.log('Multi-disc Shelves: hidden positions, one shelf per album, disc-first perfect grade, responsive reveal and history passed.');console.log('Vibe Map browser integration passed: saves, manual Finish, clean results, Next song, centred card, 3+3 home, read-only stats, four all-song heatmaps, compact in-page song radar, metadata links, two matches, mouse/keyboard activation, four profile cards above Overall, compact responsive map rows, Home library maps and consistency banner, Global summary and three collection ranking categories, 320–1365 px.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
