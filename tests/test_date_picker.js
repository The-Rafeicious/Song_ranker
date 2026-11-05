/* Native date values and constraints survive the shared custom calendar. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<body><main id="main"><form><label>From<input type="date" name="from" value="2024-02-28" min="2024-02-10" max="2024-03-05" required></label><button type="submit">Apply</button></form></main></body>',{url:'https://example.test/history',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,d=w.document;
 w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
 w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
 w.eval(fs.readFileSync('static/js/ui.js','utf8'));d.dispatchEvent(new w.Event('DOMContentLoaded'));
 const input=d.querySelector('input[type=date]'),trigger=d.querySelector('.date-open'),flush=async()=>{for(let i=0;i<5;i++)await Promise.resolve();};
 let changes=0,inputs=0;input.addEventListener('change',()=>changes++);input.addEventListener('input',()=>inputs++);
 assert.equal(input.name,'from');assert.equal(input.required,true);assert.equal(d.querySelectorAll('.date-open').length,1);
 trigger.click();let popup=d.querySelector('dialog.date-picker');assert.ok(popup.open);assert.equal(trigger.getAttribute('aria-expanded'),'true');
 assert.equal(d.activeElement.dataset.dateDay,'2024-02-28');
 assert.ok(popup.querySelector('[data-date-day="2024-02-09"]').disabled);
 assert.equal(popup.querySelector('[data-date-day="2024-02-29"]').disabled,false);
 d.activeElement.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));assert.equal(d.activeElement.dataset.dateDay,'2024-02-29');
 d.activeElement.click();assert.equal(input.value,'2024-02-29');assert.equal(changes,1);assert.equal(inputs,1);assert.equal(popup.open,false);assert.equal(d.activeElement,trigger);
 assert.equal(new w.FormData(input.form).get('from'),'2024-02-29');
 trigger.click();popup.querySelector('[data-date-step="1"]').click();assert.equal(popup.querySelector('[data-date-month]').value,'2');assert.ok(popup.querySelector('[data-date-day="2024-03-06"]').disabled);
 popup.querySelector('[data-date-clear]').click();assert.equal(input.value,'');assert.equal(input.checkValidity(),false);
 trigger.click();popup.dispatchEvent(new w.Event('cancel',{cancelable:true}));assert.equal(popup.open,false);assert.equal(d.activeElement,trigger);
 input.readOnly=true;await flush();assert.equal(trigger.disabled,true);
 input.readOnly=false;await flush();assert.equal(trigger.disabled,false);
 // Dynamic date controls receive the same picker without changing their owners.
 const late=d.createElement('input');late.type='date';late.name='release';late.value='2000-12-31';d.querySelector('main').append(late);await flush();
 assert.equal(d.querySelectorAll('.date-open').length,2);
 late.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowDown',altKey:true,bubbles:true,cancelable:true}));assert.equal(popup.open,true);
 d.activeElement.dispatchEvent(new w.KeyboardEvent('keydown',{key:'PageDown',bubbles:true,cancelable:true}));assert.equal(d.activeElement.dataset.dateDay,'2001-01-31');
 d.activeElement.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Home',bubbles:true,cancelable:true}));assert.equal(d.activeElement.dataset.dateDay,'2001-01-29');
 const year=popup.querySelector('[data-date-year]');year.value='2028';year.dispatchEvent(new w.Event('change',{bubbles:true}));assert.ok(d.activeElement.dataset.dateDay.startsWith('2028-01'));
 popup.querySelector('[data-date-today]').click();assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(late.value));assert.equal(popup.open,false);
 d.querySelectorAll('.date-open')[1].click();late.remove();await flush();assert.equal(popup.open,false);
 w.SongRankerUI.dateInputs.dispose();assert.equal(d.querySelectorAll('.date-open').length,0);assert.equal(input.type,'date');assert.equal(input.name,'from');
 dom.window.close();console.log('Shared calendar: leap dates, limits, native form values, keyboard, focus, readonly, dynamic controls and cleanup passed');
})().catch(error=>{console.error(error);process.exitCode=1});
