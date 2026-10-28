/* Entity analysis smoke and responsive checks against an isolated test server. */
const {chromium}=require('playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.ANALYSIS_CHROME,headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage(),base=process.env.ANALYSIS_URL,errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  async function choose(name,value){const root=page.locator('.analysis-picker[data-control='+name+']');await root.locator('summary').click();await root.locator('button[data-value="'+value+'"]').click();}
  for(const kind of ['song','artist','album','tag']){
   await page.goto(base+'/analysis?kind='+kind+(kind==='song'?'&compare=2':''));await page.locator('.analysis-page').waitFor();
   await choose('chart','scatter');await page.locator('#analysis-controls button[type=submit]').click();await page.locator('.analysis-chart').waitFor();assert.ok(await page.locator('.analysis-chart circle').count()>0,'Measured tracks produce chart points');
   for(const width of [390,768,1365]){
    await page.setViewportSize({width,height:1050});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Analysis fits '+width);
    fs.mkdirSync('artifacts/vibe-map',{recursive:true});
    await page.screenshot({path:'artifacts/vibe-map/analysis-'+kind+'-'+width+'.png',fullPage:true});
   }
  }
  await page.locator('.analysis-visual summary').first().click();assert.ok(await page.locator('.analysis-visual[open]').count()>0);
  for(const label of ['Games','Relationships','Records','Overview']){await page.getByRole('button',{name:label,exact:true}).click();assert.equal(await page.getByRole('button',{name:label,exact:true}).getAttribute('aria-pressed'),'true');}
  await page.goto(base+'/analysis');await choose('kind','album');await page.waitForURL('**kind=album**');assert.ok(await page.locator('select[name=id] option').count()>0);
  await page.goto(base+'/analysis?kind=song&id=1&chart=scatter&metric=win_rate&y=win_rate');await page.locator('.analysis-notice').waitFor();assert.equal(await page.locator('select[name=chart]').inputValue(),'bars');
  await page.goto(base+'/analysis/guide');await page.locator('.analysis-guide h1').waitFor();
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
