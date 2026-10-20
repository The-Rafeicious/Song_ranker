/* Real shared picker: native state, keyboard and dialog/reset ownership. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const dom=new JSDOM('<body data-page="dev"><main id="dev-main"><form id="pick-form"><label for="tag-artist">Artist</label><select id="tag-artist"><option value="">All artists</option><option value="1">Beyoncé</option><option value="2">Another artist</option></select></form></main><dialog id="editor"></dialog></body>',{runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,d=w.document;let assertions=0;const check=(v,m)=>{assert.ok(v,m);assertions++},flush=async()=>{for(let i=0;i<15;i++)await Promise.resolve()};
w.eval(fs.readFileSync('static/js/ui.js','utf8'));w.eval(fs.readFileSync('static/js/dev_controls.js','utf8'));
(async()=>{
 const select=d.querySelector('select'),trigger=d.querySelector('.dev-select-trigger');
 check(select.hidden&&trigger.textContent.includes('All artists'),'native owner has visible replacement');
 d.querySelector('label').click();check(d.activeElement===trigger,'label focuses replacement');trigger.click();
 check(trigger.getAttribute('aria-controls')==='dev-picker-popup','trigger names active popup');
 const input=d.querySelector('[role=combobox]');input.value='beyonce';input.dispatchEvent(new w.Event('input'));
 check(d.querySelectorAll('[role=option]').length===1,'accent-insensitive search');
 input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));check(select.value==='1'&&!d.querySelector('#dev-picker-popup'),'keyboard choice updates native select and closes');
 trigger.click();d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check(d.activeElement===trigger&&!trigger.hasAttribute('aria-controls'),'Escape returns focus and clears popup reference');
 d.querySelector('form').reset();await flush();check(trigger.textContent.includes('All artists'),'form reset syncs selected caption');
 select.disabled=true;await flush();check(trigger.disabled,'disabled state syncs');
 console.log(assertions+' shared picker assertions passed');w.DevControls.dispose();dom.window.close();
})().catch(e=>{console.error(e);w.DevControls.dispose();dom.window.close();process.exitCode=1});
