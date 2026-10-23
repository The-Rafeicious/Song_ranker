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
  await page.goto(base+'/vibe-map');await page.locator('#vibe-plane').waitFor();
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
  await page.goto(base+'/dev/library/songs');await page.locator('#manage-rows [data-edit]').first().waitFor();
  await page.locator('.table-filter-panel > summary').click();assert.equal(await page.locator('.table-filter-panel .table-popover-content').evaluate(e=>getComputedStyle(e).position),'static');await page.locator('.table-filter-panel > summary').click();
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
  await page.locator('.dev-nav-actions input[name=q]').fill('long title');await page.locator('.dev-nav-actions form button').click();await page.locator('#dev-query').waitFor();assert.equal(await page.locator('#dev-query').inputValue(),'long title');
  await page.locator('.dev-lock').click();await page.waitForURL(base+'/');
  // Main-header shutdown needs a PIN once and does not unlock Dev.
  await page.locator('.app-stop-button').click();await page.locator('#stop-pin').waitFor();
  assert.ok(await page.locator('[data-stop-prepare]').isDisabled(),'Externally served browser fixture cannot terminate its host');
  await page.locator('#editor-close').click();
  await page.goto(base+'/global_stats');assert.equal(await page.locator('.listening-panel,script[src*="/listening.js"]').count(),0);
  // Disc answers stay hidden while playing; repeated within-disc numbers grade in disc order.
  const discData=await (await page.request.post(base+'/shelves-test-enable')).json();
  const offeredRequest=page.waitForResponse(r=>r.url().endsWith('/api/album-shelves/round')&&r.request().method()==='POST');
  await page.goto(base+'/album_shelves');
  const offered=await (await offeredRequest).json();await page.locator('.shelf-track').first().waitFor();
  assert.equal(offered.songs.length,10);assert.ok(offered.albums.some(a=>a.disc_count===2));
  assert.ok(offered.songs.every(s=>!('disc_number' in s)&&!('track_number' in s)));
  assert.equal(await page.locator('.shelf-position-actual').count(),0);
  const order=[...discData.songs].sort((a,b)=>a.album_id-b.album_id||a.disc_number-b.disc_number||a.track_number-b.track_number);
  for(const song of order){
    const item=offered.songs.find(s=>s.id===song.id),album=offered.albums.find(a=>a.id===song.album_id);
    await page.locator(`[data-shelf-slot="${item.slot}"] summary`).click();
    await page.locator(`[data-shelf-pick="${item.slot}"][data-shelf-target="${album.slot}"]`).click();
  }
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'shelves-discs-play',folder);await page.screenshot({path:folder+'/shelves-discs-play-'+width+'.png',fullPage:true});}
  await page.locator('[data-shelf-check]').click();await page.locator('[data-shelf-next]').waitFor({state:'visible'});
  assert.equal(await page.locator('#shelf-running-score').textContent(),'30.00');
  assert.ok((await page.locator('.shelf-position-actual').allTextContents()).some(t=>t.includes('2·')));
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'shelves-discs-result',folder);await page.screenshot({path:folder+'/shelves-discs-result-'+width+'.png',fullPage:true});}
  await page.goto(base+'/album_shelves_stats');
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'shelves-discs-stats',folder);await page.screenshot({path:folder+'/shelves-discs-stats-'+width+'.png',fullPage:true});}
  assert.deepEqual(errors,[]);console.log('Multi-disc Shelves: hidden positions, one shelf per album, disc-first perfect grade, responsive reveal and history passed.');console.log('Vibe Map browser integration passed: saves, manual Finish, clean results, Next song, centred card, 3+3 home, read-only stats, four all-song heatmaps, compact in-page song radar, metadata links, two matches, mouse/keyboard activation, four profile cards above Overall, compact responsive map rows, Home library maps and consistency banner, Global summary and three collection ranking categories, 320–1365 px.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
