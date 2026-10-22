/* Stop works without collection hydration or a Dev login/module. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<button data-system-stop>Stop</button><dialog id="editor"><form id="editor-form"><h2 id="editor-title"></h2><div id="editor-fields"></div><button id="editor-close" type="button">Close</button><button id="editor-submit">Save</button></form></dialog>',{url:'http://localhost/',runScripts:'outside-only'});
 const w=dom.window,d=w.document;let phase='idle',submitted;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'))};
 w.fetch=async(url,options={})=>{
  let status=200,body;
  if(url==='/api/dev/stop')body=phase==='idle'?{state:'idle',supported:true,target:{available:false,message:'Local backup only'},review_token:'stop-target'}:{state:'failed',message:'Backup failed; app still running.'};
  else if(url==='/api/dev/stop/prepare'){submitted=JSON.parse(options.body);if(submitted.pin==='correct'){phase='failed';body={state:'backup',id:'owned-job',message:'Backing up'}}else{status=403;body={message:'Incorrect developer PIN'}}}
  else throw Error(url);
  return {ok:status<400,status,json:async()=>body};
 };
 for(const n of ['ui.js','app_stop.js'])w.eval(fs.readFileSync('static/js/'+n,'utf8'));
 const flush=async()=>{for(let n=0;n<30;n++)await Promise.resolve()};
 d.querySelector('[data-system-stop]').click();await flush();assert.ok(d.querySelector('#editor').open);assert.ok(d.querySelector('#editor-submit').hidden);
 d.querySelector('#stop-pin').value='wrong';d.querySelector('[data-stop-prepare]').click();await flush();assert.match(d.querySelector('#stop-error').textContent,/Incorrect/);
 d.querySelector('#stop-pin').value='correct';d.querySelector('[data-stop-prepare]').click();await flush();assert.equal(submitted.review_token,'stop-target');assert.equal(submitted.sync_git,false);
 assert.match(d.querySelector('#stop-message').textContent,/app still running/);assert.ok(d.querySelector('a[href="/dev/dashboard?view=export"]'));
 d.querySelector('#editor-close').click();assert.ok(!d.querySelector('#editor').open);w.close();console.log('App Stop: header works before collection load, one PIN, backup failure review, close.');
})().catch(e=>{console.error(e);process.exitCode=1});
