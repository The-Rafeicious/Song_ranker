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
  const rows=await page.locator('.mode-card').evaluateAll(nodes=>nodes.map(e=>e.offsetTop));
  assert.deepEqual(rows.slice(0,3),[rows[0],rows[0],rows[0]]);
  assert.deepEqual(rows.slice(3),[rows[3],rows[3],rows[3]]);assert.ok(rows[3]>rows[0]);
  await page.screenshot({path:folder+'/home-desktop.png',fullPage:true});
  await page.setViewportSize({width:430,height:844});
  const widths=await page.locator('.mode-card').evaluateAll(nodes=>nodes.map(e=>Math.round(e.getBoundingClientRect().width)));
  assert.ok(widths.every(w=>w===widths[0]),'All six phone cards have equal width');
  assert.deepEqual(errors,[]);console.log('Vibe Map browser integration passed: saves, manual Finish, clean results, Next song, centred card, 3+3 home, 320–1365 px.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
