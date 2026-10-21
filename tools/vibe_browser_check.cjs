/* Real served assets + Python saves. Screenshots are CI artifacts, not source data. */
const {chromium}=require('playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
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
   else await page.locator('#vibe-review').waitFor({state:'visible'});
  }
  await page.locator('#vibe-readjust').click();await page.locator('#vibe-back').click();
  await page.locator('#vibe-plane').press('ArrowRight');
  await page.waitForFunction(()=>document.querySelector('#vibe-save-status').textContent==='Saved · adjust or finish.');
  assert.equal(await page.locator('audio').count(),1);
  await page.locator('#vibe-finish').click();await page.locator('.vibe-match').first().waitFor();
  assert.equal(await page.locator('.vibe-match').count(),2);
  assert.equal(await page.locator('.radar-axis').count(),8);
  await page.screenshot({path:folder+'/results-desktop.png',fullPage:true});
  for(const width of [320,360,390,430,768]){
   await page.setViewportSize({width,height:900});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Results overflow at '+width);
  }
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:folder+'/results-phone.png',fullPage:true});
  await page.locator('#vibe-edit-results').click();
  for(const width of [320,360,390,430,768]){
   await page.setViewportSize({width,height:900});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Map overflow at '+width);
  }
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:folder+'/map-phone.png',fullPage:true});
  await page.locator('#vibe-finish').click();await page.locator('[data-vibe-next-song]').click();
  await page.waitForFunction(()=>document.querySelector('.vibe-song h2').textContent.endsWith('2'));
  assert.ok(await page.locator('#vibe-finish').isDisabled());
  await page.setViewportSize({width:1365,height:1050});await page.goto(base+'/');await page.locator('.mode-card.vibe').waitFor();
  assert.equal(await page.locator('.mode-card').count(),6);
  const rows=await page.locator('.mode-card').evaluateAll(nodes=>nodes.map(e=>Math.round(e.getBoundingClientRect().top)));
  assert.deepEqual(rows.slice(0,3),[rows[0],rows[0],rows[0]]);
  assert.deepEqual(rows.slice(3),[rows[3],rows[3],rows[3]]);assert.ok(rows[3]>rows[0]);
  await page.screenshot({path:folder+'/home-desktop.png',fullPage:true});
  await page.setViewportSize({width:430,height:844});
  const widths=await page.locator('.mode-card').evaluateAll(nodes=>nodes.map(e=>Math.round(e.getBoundingClientRect().width)));
  assert.ok(widths.every(w=>w===widths[0]),'All six phone cards have equal width');
  assert.deepEqual(errors,[]);console.log('Vibe Map browser integration passed: saves, review, results, next song, 3+3 home, 320–1365 px.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
