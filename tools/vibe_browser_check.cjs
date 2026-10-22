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
  await page.locator('#dev-vibe-save button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Vibe data saved'));
  const maintained=await (await page.request.get(base+'/api/dev/vibe/1')).json();
  assert.equal(maintained.maps.find(m=>m.id==='pace_mood').x,.85);
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-vibe',folder);await page.locator('#dev-vibe-editor').screenshot({path:folder+'/dev-vibe-'+width+'.png'});}
  await page.locator('[data-vibe-clear-map="pace_mood"]').click();await page.locator('#dev-vibe-save button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#dev-vibe-save button[type=submit]')?.disabled===false);
  await page.locator('#dev-vibe-delete [name="confirmation"]').fill('DELETE VIBE');await page.locator('#dev-vibe-delete button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Vibe data deleted'));
  const removed=await (await page.request.get(base+'/api/dev/vibe/1')).json();assert.ok(removed.maps.every(m=>m.status==='unmapped'));assert.equal(removed.completed_passes,0);
  // Isolate only the Git transport: real served Dev markup/scripts and confirmation UI.
  const gitChoice={available:true,state:'behind',branch:'main',remote:'origin',target:'main',destination:'example.org/owner/app',tracking_head:'abc',ahead:0,behind:1,pending_code:false,code_changes:0,in_progress:false,review_token:'browser-git-review',history:[],snapshot:{exists:true,name:'database_backup.sql',bytes:20}};
  await page.route('**/api/dev/system',async route=>{const response=await route.fetch();const body=await response.json();body.git=gitChoice;await route.fulfill({json:body});});
  await page.route('**/api/dev/git/keep-local/review',route=>route.fulfill({json:{ok:true,local:{Songs:7,'Vibe positions':0},remote:{Songs:7,'Vibe positions':24},choice_token:'browser-choice',git:gitChoice,message:'Compare both copies.'}}));
  let kept=0;
  await page.route('**/api/dev/git/keep-local',async route=>{assert.deepEqual(route.request().postDataJSON(),{choice_token:'browser-choice',confirmation:'KEEP LOCAL'});kept++;await route.fulfill({json:{ok:true,git:gitChoice,message:'Local database kept. Restart then upload.'}});});
  await page.goto(base+'/dev/dashboard?view=export');await page.locator('[data-system-local-review]:enabled').waitFor();
  assert.ok(await page.locator('[data-system-upload]').isDisabled());
  await page.locator('[data-system-local-review]').click();await page.locator('#system-local-confirmation').waitFor();
  assert.ok(await page.locator('[data-system-local-apply]').isDisabled());
  for(const width of [390,1365]){await page.setViewportSize({width,height:1050});await bounded(page,width,'dev-keep-local',folder);await page.locator('#system-local-choice').screenshot({path:folder+'/dev-keep-local-'+width+'.png'});}
  await page.locator('#system-local-confirmation').fill('KEEP LOCAL');await page.locator('[data-system-local-apply]').click();
  await page.waitForFunction(()=>document.querySelector('#system-note').textContent.includes('Local database kept'));
  assert.equal(kept,1);assert.ok(await page.locator('[data-system-upload]').isDisabled());
  await page.goto(base+'/global_stats');assert.equal(await page.locator('.listening-panel,script[src*="/listening.js"]').count(),0);
  assert.deepEqual(errors,[]);console.log('Vibe Map browser integration passed: saves, manual Finish, clean results, Next song, centred card, 3+3 home, read-only stats, four all-song heatmaps, compact in-page song radar, metadata links, two matches, mouse/keyboard activation, four profile cards above Overall, compact responsive map rows, Home library maps and consistency banner, Global summary and three collection ranking categories, 320–1365 px.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
