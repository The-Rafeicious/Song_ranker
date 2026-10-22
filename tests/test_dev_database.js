const assert=require('node:assert/strict'),{harness,flush}=require('./test_dev_system.js');
(async()=>{
 const h=await harness('database');let oldResolve,cellResolve;
 const table=name=>({object:{name,sql:'CREATE TABLE '+name+' (id INTEGER)'},columns:[{name:'id',type:'INTEGER',pk:1,notnull:0}],rows:[{cells:[{type:'integer',value:'9223372036854775807',truncated:false}],review_token:name+'-row'}],total:60,offset:0,limit:25,foreign_keys:[],indexes:[]});
 h.handler(url=>{if(url.startsWith('/api/dev/database/inspect?')){const params=new URL('http://localhost'+url).searchParams;if(params.get('name')==='preference_mode_ratings')return new Promise(r=>oldResolve=r);return {...table(params.get('name')),offset:Number(params.get('offset'))};}
 if(url.startsWith('/api/dev/database/cell?'))return new Promise(r=>cellResolve=r);
 if(url==='/api/dev/stop')return {state:'idle',supported:false,target:{available:false},review_token:'stop'};});
 h.click('[data-db-object="preference_mode_ratings"]');await flush();h.click('[data-db-object="songs"]');await flush();oldResolve(table('preference_mode_ratings'));await flush();
 assert.equal(h.d.querySelector('.db-inspection h3').textContent,'songs');assert.ok(h.d.querySelector('.db-rows').textContent.includes('9223372036854775807'));
 h.click('[data-db-page="1"]');await flush();assert.ok(h.requests.some(r=>r.url.includes('offset=25')));
 h.click('[data-db-cell="0"]');await flush();assert.ok(h.d.querySelector('#editor-submit').hidden);
 h.click('[data-system-stop]');await flush();assert.ok(h.d.querySelector('#stop-pin'));
 cellResolve({column:'id',type:'integer',value:'should not replace stop',total:1,start:0,limit:4096,truncated:false});await flush();assert.ok(h.d.querySelector('#stop-pin'));assert.ok(!h.d.querySelector('.db-cell-detail'));
 assert.equal(h.requests.filter(r=>r.url.startsWith('/api/dev/database/')&&r.options.method==='POST').length,0);h.close();console.log('Database UI: read-only paging, exact integers, stale table and cell replies, dialog ownership passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
