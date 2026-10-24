/* Polling/navigation and saved-versus-refresh outcomes; mocked requests. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const dom=new JSDOM('<body data-page="dev"><main id="dev-main"></main></body>',{runScripts:'outside-only',url:'http://localhost/dev/dashboard'});
const w=dom.window,d=w.document;let assertions=0,calls=[],handler=async()=>({state:'idle'}),notices=[],refreshFails=false;
const check=(v,label)=>{assert.ok(v,label);assertions++},flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve()};
w.eval(fs.readFileSync('static/js/ui.js','utf8'));w.eval(fs.readFileSync('static/js/dev_metadata.js','utf8'));
w.DevMetadata.bindUI({root:()=>d.querySelector('#dev-main'),title:t=>'<h2>'+t+'</h2>',api:async(url,data)=>{calls.push({url,data});return handler(url,data)},toast:s=>notices.push(s),refresh:async()=>{if(refreshFails)throw Error('refresh failed')}});
const click=s=>d.querySelector(s).click();
(async()=>{
 w.DevMetadata.render();await flush();check(d.querySelector('#metadata-country').value==='gb','store starts GB');
 d.querySelector('#metadata-country').value='bad';click('[data-metadata="scan"]');await flush();check(calls.length===1,'invalid store sends no scan');check(d.querySelector('#metadata-error').textContent.includes('two-letter'),'store error visible');
 d.querySelector('#metadata-country').value='US';handler=async()=>({state:'ready',token:'reviewed',fields:1,field_changes:[{entity:'songs',id:7,title:'Blank preview',label:'Preview URL',value:'https://example.test/a.m4a',evidence:'Saved Apple track 123'}],inventory:{missing:{'songs.release_date':228,'albums.release_date':12,'songs.track_number':1},saved_dates:227}});click('[data-metadata="scan"]');await flush();
 check(calls.at(-1).data.country==='us','store normalised');check(!d.querySelector('[data-metadata="apply"]').disabled,'new-field-only plan can apply');
 check(d.querySelector('#metadata-inventory').textContent.includes('227 missing song dates'),'saved-source opportunities visible');check(d.querySelector('.metadata-review').textContent.includes('https://example.test/a.m4a'),'field value review visible');check(d.querySelector('.metadata-review').textContent.includes('Saved Apple track 123'),'field evidence visible');
 refreshFails=true;handler=async()=>({state:'applied',token:'reviewed',tracks:1});click('[data-metadata="apply"]');await flush();
 check(notices.at(-1).startsWith('Metadata filled.'),'refresh failure reports confirmed save');check(d.querySelector('#metadata-status').textContent.includes('Matched blanks filled'),'applied state retained');
 let resolve;handler=()=>new Promise(r=>resolve=r);w.DevMetadata.render();await flush();w.DevMetadata.viewChanged('songs');d.querySelector('#dev-main').innerHTML='<h2>Songs</h2>';resolve({state:'scanning',token:'old'});await flush();check(d.querySelector('h2').textContent==='Songs','late metadata reply cannot replace new page');
 handler=async()=>{throw Error('Offline')};w.DevMetadata.render();await flush();check(!d.querySelector('#metadata-retry').hidden,'load error exposes retry');
 handler=async()=>({state:'idle'});click('[data-metadata="retry"]');await flush();check(d.querySelector('#metadata-error').hidden,'retry clears failure');
 console.log(assertions+' metadata UI assertions passed');dom.window.close();
})().catch(e=>{console.error(e);dom.window.close();process.exitCode=1});
