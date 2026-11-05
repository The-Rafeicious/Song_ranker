/* Leading live lookup, latest-query coalescing, top three and safe selection. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM(`<section class="history-search-panel"><form id="archive-filters"><label>Mode<select name="mode" id="archive-mode"><option value="all">All modes</option><option value="recognition">Trivia</option></select></label><label>Record type<select name="entity" id="archive-kind"><option value="songs">Songs</option><option value="tags">Tags</option></select></label><div class="archive-lookup"><input id="archive-search"><input id="archive-target"><button type="button" id="archive-clear">Clear</button><div id="archive-suggestions" hidden></div><p id="archive-selection"></p></div><p id="archive-error"></p></form></section>`,{url:'https://example.test/history',runScripts:'outside-only'}),w=dom.window;
 const calls=[],pending=[];w.fetch=url=>{calls.push(url);return new Promise(resolve=>pending.push(resolve));};
 for(const name of ['ui','gameplay','history'])w.eval(fs.readFileSync('static/js/'+name+'.js','utf8'));
 w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
 const $=id=>w.document.getElementById(id),flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve();};
 const input=text=>{$('archive-search').value=text;$('archive-search').dispatchEvent(new w.Event('input',{bubbles:true}));};
 const response=items=>({ok:true,json:async()=>({items})});
 assert.equal($('archive-kind').name,'entity');assert.ok($('archive-kind').hidden);
 input('t');assert.equal(calls.length,1,'first request starts synchronously, with no debounce');
 input('tw');input('two');assert.equal(calls.length,1,'rapid input coalesces behind the active request');
 pending[0](response(Array.from({length:6},(_,i)=>({id:i+1,name:'Two <Chosen> '+i,artists:[{name:'Artist'}],album:{name:'Album'},cover:'/cover'}))));await flush();
 assert.equal(calls.length,2);assert.ok(calls[1].endsWith('q=two'),'latest query starts while typing, without waiting for idle');
 assert.equal($('archive-suggestions').querySelectorAll('button').length,3);
 assert.equal($('archive-suggestions').querySelector('strong').textContent,'Two <Chosen> 0');
 pending[1](response([{id:20,name:'Two updated'}]));await flush();
 $('archive-search').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));assert.equal(w.document.activeElement,$('archive-suggestions').querySelector('button'));
 w.document.activeElement.click();assert.equal($('archive-target').value,'20');assert.equal($('archive-selection').textContent,'Selected: Two updated');assert.equal($('archive-suggestions').hidden,true);
 input('new');const event=new w.Event('submit',{cancelable:true});$('archive-filters').dispatchEvent(event);assert.equal(event.defaultPrevented,true);
 $('archive-clear').click();assert.equal($('archive-target').value,'');assert.equal($('archive-search').value,'');
 pending[2](response([{id:99,name:'New stale'}]));await flush();assert.equal($('archive-suggestions').hidden,true);
 input('tag');$('archive-kind').value='tags';$('archive-kind').dispatchEvent(new w.Event('change',{bubbles:true}));pending[3](response([{id:3,name:'Stale song'}]));await flush();assert.equal($('archive-suggestions').hidden,true);
 $('archive-mode').value='recognition';$('archive-mode').dispatchEvent(new w.Event('change',{bubbles:true}));assert.equal(w.document.querySelector('.history-search-panel').dataset.mode,'recognition');
 assert.ok(calls[0].includes('lookup=songs'));assert.equal($('archive-target').value,'');
 dom.window.close();console.log('History: immediate/coalesced lookup, top three, safe text, keyboard, stale replies, mode palette and form checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
