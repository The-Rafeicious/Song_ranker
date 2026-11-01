/* Exercise the actual builder, custom selectors, compact records and paging. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<main><section data-mode-query><nav data-query-entity></nav><form><div data-query-controls></div><p data-query-error></p><button type="submit">Apply</button><button type="button" data-query-reset>Reset</button></form><div data-query-results></div></section></main>',{url:'https://example.test/query',runScripts:'outside-only'}),w=dom.window;
 w.structuredClone=structuredClone;
 const metrics=['elo','matches','win_rate','trivia_rounds','trivia_accuracy'].map(key=>({key,label:key,family:'Voting',unit:key==='win_rate'?'percent':'count'}));
 let calls=[],fail=false;
 w.fetch=async url=>{calls.push(url);if(url.includes('schema'))return {ok:true,json:async()=>({metrics})};if(fail)return {ok:false,json:async()=>({error:'Try again'})};const spec=JSON.parse(new URL(url,'https://example.test').searchParams.get('spec'));return {ok:true,json:async()=>({spec,total:21,pages:2,page:spec.page,items:[{id:1,name:'<img src=x onerror=bad()>',kind:'songs',url:'/song/1',cover:'/cover',values:{elo:1234,matches:1001},related:[{id:2,name:'Artist & A',kind:'artists',url:'/artist/A',cover:'/artist'}]}]})};};
 for(const name of ['ui','gameplay','query'])w.eval(fs.readFileSync('static/js/'+name+'.js','utf8'));
 w.document.dispatchEvent(new w.Event('DOMContentLoaded'));await new Promise(r=>setTimeout(r,30));
 const root=w.document.querySelector('[data-mode-query]');const change=(id,value)=>{const el=w.document.getElementById(id);el.value=value;el.dispatchEvent(new w.Event('change',{bubbles:true}));};
 assert.equal(root.querySelectorAll('.query-result').length,1);assert.equal(root.querySelector('.query-name b').textContent,'<img src=x onerror=bad()>');assert.equal(root.querySelectorAll('[onerror]').length,0);
 root.querySelector('.query-result summary').click();assert.equal(root.querySelector('.query-expanded h2 a').getAttribute('href'),'/song/1');
 root.querySelector('[data-add]').click();change('field-0','won_against');assert.ok(w.document.getElementById('source-0'));assert.equal(w.document.getElementById('op-0'),null);
 change('field-0','elo');change('op-0','missing');assert.equal(root.querySelector('[data-number]'),null);assert.equal(w.document.getElementById('source-0'),null);
 change('sort-1','matches');assert.ok(![...w.document.getElementById('sort-2').options].some(o=>o.value==='matches'));
 change('sort-1','');assert.deepEqual([...w.document.getElementById('sort-2').options].map(o=>o.value),['']);
 root.querySelector('[data-page="2"]').click();await new Promise(r=>setTimeout(r,20));assert.equal(root.querySelector('[data-page-input]').value,'2');assert.ok(new URL(w.location.href).searchParams.has('spec'));
 fail=true;root.querySelector('form').dispatchEvent(new w.Event('submit',{cancelable:true,bubbles:true}));await new Promise(r=>setTimeout(r,20));assert.equal(root.querySelector('[data-query-error]').textContent,'Try again');fail=false;
 root.querySelector('[data-query-reset]').click();await new Promise(r=>setTimeout(r,20));assert.equal(root.querySelector('[data-page-input]').value,'1');
 assert.ok(calls.every(url=>url.startsWith('/api/query?')));w.dispatchEvent(new w.Event('pagehide'));dom.window.close();console.log('Query builder: filters, compatibility, unique sorting, pagination, escaping, errors and reset passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
