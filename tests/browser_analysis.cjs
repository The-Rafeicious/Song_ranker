/* Entity analysis smoke and responsive checks against an isolated test server. */
const {chromium}=require('playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.ANALYSIS_CHROME,headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage(),base=process.env.ANALYSIS_URL,errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  for(const kind of ['song','artist','album','tag']){
   await page.goto(base+'/analysis?kind='+kind);await page.locator('.analysis-page').waitFor();
   await page.locator('select[name=chart]').selectOption('scatter');await page.locator('#analysis-controls button').click();await page.locator('.analysis-chart').waitFor();assert.ok(await page.locator('.analysis-chart circle').count()>0,'Measured tracks produce chart points');
   for(const width of [390,768,1365]){
    await page.setViewportSize({width,height:1050});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Analysis fits '+width);
    fs.mkdirSync('artifacts/vibe-map',{recursive:true});
    await page.screenshot({path:'artifacts/vibe-map/analysis-'+kind+'-'+width+'.png',fullPage:true});
   }
  }
  await page.goto(base+'/analysis');await page.locator('select[name=kind]').selectOption('album');await page.waitForURL('**kind=album**');assert.ok(await page.locator('select[name=id] option').count()>0);
  await page.goto(base+'/analysis/guide');await page.locator('.analysis-guide h1').waitFor();
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
