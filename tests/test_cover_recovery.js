/* Transient cover errors recover without changing URLs, layout or game visibility. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
const dom=new JSDOM('<main></main>',{url:'https://example.test/',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;
w.eval(fs.readFileSync('static/js/ui.js','utf8'));w.SongRankerUI.coverRecovery.dispose();
let tasks=new Map(),id=0,delays=[],online=true;
Object.defineProperty(w.navigator,'onLine',{get:()=>online,configurable:true});
const manager=w.SongRankerUI.manageCoverImages(w.document,{setTimer(fn,delay){tasks.set(++id,fn);delays.push(delay);return id;},clearTimer(key){tasks.delete(key);}});
function image(src,hidden=false){const img=w.document.createElement('img');img.setAttribute('data-cover','');if(src)img.setAttribute('src',src);img.setAttribute('loading','lazy');img.hidden=hidden;w.document.querySelector('main').append(img);return img;}
function event(img,type){img.dispatchEvent(new w.Event(type));}
function tick(){const todo=[...tasks.values()];tasks.clear();todo.forEach(fn=>fn());}
function loaded(img){Object.defineProperty(img,'naturalWidth',{value:64,configurable:true});event(img,'load');}
const a=image('/cover?token=original'),b=image('/cover?token=original');
event(a,'error');event(b,'error');assert.equal(tasks.size,1,'one timer for duplicate artwork');assert.ok(a.classList.contains('failed'));assert.equal(a.hidden,false,'fallback preserves the slot');
tick();assert.equal(a.getAttribute('src'),'/cover?token=original');assert.equal(b.getAttribute('src'),'/cover?token=original');assert.equal(a.loading,'eager');
event(a,'error');event(b,'error');assert.equal(tasks.size,1);tick();
event(a,'error');event(b,'error');assert.equal(tasks.size,0,'permanent failures stop after two retries');assert.deepEqual(delays,[800,2400]);
loaded(a);assert.ok(!a.classList.contains('failed'));assert.equal(a.getAttribute('src'),'/cover?token=original');assert.equal(a.getAttribute('loading'),'lazy');
const hidden=image('/blind',true);event(hidden,'error');tick();loaded(hidden);assert.equal(hidden.hidden,true,'loading must not reveal a hidden game image');
const replaced=image('/old');event(replaced,'error');replaced.setAttribute('src','/new');tick();assert.equal(replaced.getAttribute('src'),'/new','a stale retry never replaces new artwork');loaded(replaced);assert.ok(!replaced.classList.contains('failed'));
const removed=image('/gone');event(removed,'error');removed.remove();let calls=0;removed.setAttribute=()=>{calls++;};tick();assert.equal(calls,0,'removed rows make no retry requests');
online=false;const offline=image('/offline');event(offline,'error');assert.equal(tasks.size,0);online=true;w.dispatchEvent(new w.Event('online'));assert.equal(tasks.size,1);tick();loaded(offline);
const plain=w.document.createElement('img');plain.src='/not-art';w.document.querySelector('main').append(plain);event(plain,'error');assert.equal(tasks.size,0);assert.ok(!plain.classList.contains('failed'));
const empty=image('');event(empty,'error');assert.equal(tasks.size,0,'missing covers are not retried');
const early=image('/early');Object.defineProperty(early,'complete',{value:true});manager.scan();assert.equal(tasks.size,1,'cover failures before deferred scripts are recovered');loaded(early);assert.equal(tasks.size,0,'a late success cancels its retry');
const paused=image('/paused');event(paused,'error');w.dispatchEvent(new w.Event('pagehide'));assert.equal(tasks.size,0);w.dispatchEvent(new w.Event('pageshow'));assert.ok(tasks.size);manager.dispose();assert.equal(tasks.size,0);w.close();
console.log('Cover recovery: bounded retries, URL batching, late success, stale nodes, offline resume, hidden reveals and disposal passed.');
