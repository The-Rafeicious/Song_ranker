/* Heatmap links remain server-rendered; script adds safe keyboard/hover exploration. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
const dom=new JSDOM(`<body data-page="vibe_stats"><figure data-vibe-chart><svg tabindex="0"><a href="/song/1" tabindex="-1" data-vibe-point data-song-title="First" data-song-artist="Artist"><circle/></a><a href="/song/2" tabindex="-1" data-vibe-point data-song-title="&lt;img src=x onerror=alert(1)&gt;" data-song-artist="Second artist"><circle/></a></svg><span class="vibe-chart-selection">2 placed</span></figure><figure data-vibe-chart><svg tabindex="0"></svg><span class="vibe-chart-selection">0 placed</span></figure>`,{runScripts:'outside-only',url:'http://localhost'});
const w=dom.window,d=w.document;
w.eval(fs.readFileSync('static/js/vibe_stats.js','utf8'));
const charts=d.querySelectorAll('[data-vibe-chart]'),svg=charts[0].querySelector('svg'),points=[...svg.querySelectorAll('a')],caption=charts[0].querySelector('.vibe-chart-selection');
// jsdom does not implement SVG focus; emulate the browser's focus event.
points.forEach(p=>p.focus=()=>p.dispatchEvent(new w.FocusEvent('focusin',{bubbles:true})));
const key=(target,value)=>target.dispatchEvent(new w.KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true}));
key(svg,'ArrowLeft');assert.equal(caption.querySelector('a').getAttribute('href'),'/song/2');
assert.equal(caption.querySelector('img'),null);assert.ok(caption.textContent.includes('<img src=x onerror=alert(1)>'));
key(svg,'ArrowRight');assert.equal(caption.querySelector('a').textContent,'First');
key(svg,'End');assert.equal(caption.querySelector('a').getAttribute('href'),'/song/2');
key(svg,'Home');assert.equal(caption.querySelector('a').getAttribute('href'),'/song/1');
let clicked=0;points[0].addEventListener('click',e=>{e.preventDefault();clicked++});key(svg,'Enter');assert.equal(clicked,1);
points[1].querySelector('circle').dispatchEvent(new w.Event('pointerover',{bubbles:true}));assert.ok(caption.textContent.includes('Second artist'));
charts[0].dispatchEvent(new w.Event('pointerleave'));assert.equal(caption.textContent,'2 placed');
for(const value of ['ArrowLeft','Home','End','Enter'])key(charts[1].querySelector('svg'),value);
assert.equal(charts[1].querySelector('.vibe-chart-selection').textContent,'0 placed');
console.log('Vibe stats: keyboard wrap, first reverse movement, links, hover, escaped titles and empty charts passed.');dom.window.close();
