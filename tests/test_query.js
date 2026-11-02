/* Exercise the actual builder, custom selectors, compact records and paging. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<main><section data-mode-query><nav data-query-entity></nav><form><div data-query-controls></div><p data-query-error></p><button type="submit">Apply</button><button type="button" data-query-reset>Reset</button></form><div data-query-results></div></section></main>',{url:'https://example.test/query',runScripts:'outside-only'}),w=dom.window;
 w.structuredClone=structuredClone;
 const metrics=['elo','matches','win_rate','trivia_rounds','trivia_accuracy','guess_accuracy','vibe_maps'].map(key=>({key,label:key,family:key.startsWith('guess')?'Elo Guesser':key.startsWith('vibe')?'Vibe':'Voting',unit:key==='win_rate'?'percent':'count'}));
 let calls=[],fail=false;
 w.fetch=async url=>{calls.push(url);if(url.includes('schema'))return {ok:true,json:async()=>({metrics})};if(url.includes('lookup='))return {ok:true,json:async()=>({items:[{id:2,name:'Chosen <song>',kind:'songs',cover:'/cover',artists:[{id:8,name:'Artist A',kind:'artists',url:'/artist/A'}],album:{id:9,name:'Full album',kind:'albums',proper_album:true,url:'/album/Full'},related:[{kind:'tags',name:'Hidden lookup tag'}]}],total:1})};if(fail)return {ok:false,json:async()=>({error:'Try again'})};const spec=JSON.parse(new URL(url,'https://example.test').searchParams.get('spec'));return {ok:true,json:async()=>({spec,total:21,pages:2,page:spec.page,items:[{id:1,name:'<img src=x onerror=bad()>',kind:spec.entity,url:'/song/1',cover:'/cover',track_count:1,artist_count:1,album_count:1,values:{elo:1234,matches:1001},artists:[{id:2,name:'Artist & A',kind:'artists',url:'/artist/A'}],album:{id:3,name:'Album One',kind:'albums',proper_album:true,url:'/album/One'},related:[{id:2,name:'Artist & A',kind:'artists',url:'/artist/A',cover:'/artist'}]}]})};};
 for(const name of ['ui','gameplay','query'])w.eval(fs.readFileSync('static/js/'+name+'.js','utf8'));
 w.document.dispatchEvent(new w.Event('DOMContentLoaded'));await new Promise(r=>setTimeout(r,30));
 const root=w.document.querySelector('[data-mode-query]');const change=(id,value)=>{const el=w.document.getElementById(id);el.value=value;el.dispatchEvent(new w.Event('change',{bubbles:true}));};
 assert.equal(root.querySelectorAll('.query-result').length,1);assert.equal(root.querySelector('.query-name b').textContent,'<img src=x onerror=bad()>');assert.equal(root.querySelectorAll('[onerror]').length,0);assert.equal(root.querySelector('.query-result').dataset.queryResultKind,'songs');assert.match(root.querySelector('.query-metadata').textContent,/Artist & A.*Album One/);
 root.querySelector('.query-result summary').click();assert.equal(root.querySelector('.query-expanded h2 a').getAttribute('href'),'/song/1');
 root.querySelector('[data-query-kind="tags"]').click();await new Promise(r=>setTimeout(r,20));
 assert.equal(root.querySelector('.query-result .tag-cover').textContent,'#');assert.equal(root.querySelector('.query-result summary img'),null);
 root.querySelector('[data-query-kind="songs"]').click();await new Promise(r=>setTimeout(r,20));
 root.querySelector('[data-add]').click();change('field-0','won_against');assert.ok(w.document.getElementById('source-0'));assert.equal(w.document.getElementById('op-0'),null);
 change('field-0','elo');change('op-0','missing');assert.equal(root.querySelector('[data-number]'),null);assert.equal(w.document.getElementById('source-0'),null);
 change('sort-1','matches');assert.ok(![...w.document.getElementById('sort-2').options].some(o=>o.value==='matches'));
 change('sort-1','');assert.deepEqual([...w.document.getElementById('sort-2').options].map(o=>o.value),['']);
 root.querySelector('[data-page="2"]').click();await new Promise(r=>setTimeout(r,20));assert.equal(root.querySelector('[data-page-input]').value,'2');assert.ok(new URL(w.location.href).searchParams.has('spec'));
 fail=true;root.querySelector('form').dispatchEvent(new w.Event('submit',{cancelable:true,bubbles:true}));await new Promise(r=>setTimeout(r,20));assert.equal(root.querySelector('[data-query-error]').textContent,'Try again');fail=false;
 root.querySelector('[data-query-reset]').click();await new Promise(r=>setTimeout(r,20));assert.equal(root.querySelector('[data-page-input]').value,'1');

 // Filter discovery searches descriptions and Enter adds a matching relationship.
 root.querySelector('.query-filter-picker').open=true;
 let filterFind=root.querySelector('[data-filter-search]');filterFind.value='opponent';filterFind.dispatchEvent(new w.Event('input',{bubbles:true}));
 assert.equal(root.querySelectorAll('[data-filter-choice]:not([hidden])').length,2);
 filterFind.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
 assert.ok(root.querySelector('[data-target-search="0"]'));assert.ok(w.document.activeElement.matches('[data-target-search="0"]'),w.document.activeElement.outerHTML);
 root.querySelector('[data-remove="0"]').click();
 root.querySelector('[data-add-field="elo"]').click();
 assert.equal(root.querySelector('[data-number="0"]').value,'1200');assert.equal(root.querySelector('[data-max="0"]').value,'1250');
 root.querySelector('[data-remove="0"]').click();
 // Search updates without submitting, preserves the active field, and can be cleared.
 let input=root.querySelector('[data-search]');input.focus();input.value='Artist One';input.dispatchEvent(new w.Event('input',{bubbles:true}));
 await new Promise(r=>setTimeout(r,420));
 assert.equal(JSON.parse(new URL(calls.at(-1),'https://example.test').searchParams.get('spec')).q,'Artist One');
 assert.ok(w.document.activeElement.matches('[data-search]'));
 root.querySelector('[data-search-clear]').click();await new Promise(r=>setTimeout(r,20));assert.equal(root.querySelector('[data-search]').value,'');
 // Six includes mandatory sort fields, and search/filter only change the local chooser.
 const chooser=root.querySelector('.query-columns');chooser.open=true;
 const required=root.querySelector('[data-column="elo"]');assert.ok(required.checked&&required.disabled);
 let check=root.querySelector('[data-column="guess_accuracy"]');check.checked=true;check.dispatchEvent(new w.Event('change',{bubbles:true}));
 assert.equal(root.querySelector('[data-column-count]').textContent,'6 / 6');assert.ok(root.querySelector('[data-column="vibe_maps"]').disabled);
 root.querySelector('[data-column-remove="guess_accuracy"]').click();assert.ok(!root.querySelector('[data-column="vibe_maps"]').disabled);
 const beforeSearch=calls.length,find=root.querySelector('[data-column-search]');find.value='guesser';find.dispatchEvent(new w.Event('input',{bubbles:true}));
 assert.equal(root.querySelectorAll('[data-column-option]:not([hidden])').length,1);assert.equal(calls.length,beforeSearch);
 change('query-column-family','Vibe');assert.match(root.querySelector('[data-column-status]').textContent,/No statistics/);
 find.value='';find.dispatchEvent(new w.Event('input',{bubbles:true}));assert.equal(root.querySelectorAll('[data-column-option]:not([hidden])').length,1);
 // Suggestions expose identities and support arrow/Enter selection and clearing.
 root.querySelector('[data-add]').click();change('field-0','won_against');
 input=root.querySelector('[data-target-search]');input.value='Chosen';input.dispatchEvent(new w.Event('input',{bubbles:true}));
 await new Promise(r=>setTimeout(r,290));assert.equal(root.querySelector('[data-target] b').textContent,'Chosen <song>');assert.match(root.querySelector('[data-target] small').textContent,/Artist A.*Full album/);assert.ok(!root.querySelector('[data-target]').textContent.includes('Hidden lookup tag'));
 input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));assert.ok(w.document.activeElement.matches('[data-target]'));
 w.document.activeElement.click();assert.equal(root.querySelector('[data-target-search]').value,'Chosen <song>');
 root.querySelector('[data-target-clear]').click();assert.equal(root.querySelector('[data-target-search]').value,'');
 const beforeBlank=calls.length;input=root.querySelector('[data-target-search]');input.dispatchEvent(new w.Event('input',{bubbles:true}));
 await new Promise(r=>setTimeout(r,280));assert.equal(calls.length,beforeBlank);
 // A dismissed response must never replace the current list.
 let finish;w.fetch=async()=>({ok:true,json:()=>new Promise(resolve=>{finish=resolve;})});
 input.value='late';input.dispatchEvent(new w.Event('input',{bubbles:true}));await new Promise(r=>setTimeout(r,280));
 input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));finish({items:[{id:99,name:'Late',kind:'songs'}],total:1});await new Promise(r=>setTimeout(r,20));
 assert.equal(root.querySelector('[data-target]'),null);
 assert.ok(calls.every(url=>url.startsWith('/api/query?')));w.dispatchEvent(new w.Event('pagehide'));dom.window.close();console.log('Query builder: filters, compatibility, unique sorting, pagination, escaping, errors and reset passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
