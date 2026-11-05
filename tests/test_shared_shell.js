/* Independent reports retain navigation/audio without hydrating the catalogue. */
const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const dom=new JSDOM('<body data-page="voting_stats"><main id="main"></main><dialog id="editor"><form id="editor-form"><h2 id="editor-title"></h2><div id="editor-fields"></div><button id="editor-close"></button><button id="editor-submit"></button></form></dialog><div id="toast" hidden></div><audio id="preview"></audio></body>',{url:'http://localhost/voting_stats',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,calls=[];
 w.localStorage.setItem('siteVolume','0.23');
 w.fetch=url=>{calls.push(url);return Promise.reject(Error('Unexpected catalogue request'))};
 w.HTMLMediaElement.prototype.pause=function(){};
 w.HTMLMediaElement.prototype.load=function(){};
 for(const name of ['ui','preview','site'])await w.eval(fs.readFileSync('static/js/'+name+'.js','utf8'));
 for(let i=0;i<30;i++)await Promise.resolve();
 assert.deepEqual(calls,[]);
 assert.equal(w.PreviewPlayback.getVolume(),.23);
 const audio=w.document.querySelector('audio');w.PreviewPlayback.bind(audio);w.PreviewPlayback.syncVolume();
 assert.equal(audio.volume,.23,'saved volume is used even without a navbar range control');
 w.PreviewPlayback.setVolume(.72);assert.equal(audio.volume,.72);assert.equal(w.localStorage.getItem('siteVolume'),'0.72');
 w.PreviewPlayback.setVolume(4);assert.equal(audio.volume,1);
 w.PreviewPlayback.setVolume(-2);assert.equal(audio.volume,0);
 w.PreviewPlayback.setVolume('invalid');assert.equal(audio.volume,0);
 assert.equal(w.SongRankerUI.trackPosition({disc_number:2,track_number:1}), '2·1');
 assert.equal(w.SongRankerUI.trackPosition({track_number:3}), '3');
 assert.equal(w.SongRankerUI.trackPosition({disc_number:2,track_number:1},true), 'Disc 2 · Track 1');
 assert.equal(w.SongRankerUI.searchText(' Beyoncé '),'beyonce');
 assert.equal(w.SongRankerUI.identityText('  A   TAG  '),'a tag');
 const header=w.document.createElement('div'),UI=w.SongRankerUI;
 header.innerHTML=UI.rankingHeading('Query <safe>','query')+UI.modeRankingControls('/mode_rankings/trivia','artists',true,'special');
 assert.equal(header.querySelector('h1').textContent,'Query <safe>');assert.equal(header.querySelector('safe'),null);
 assert.equal(header.querySelectorAll('.rank-links a').length,4);
 assert.equal(header.querySelector('.rank-links [aria-current="page"]').textContent,'Artists');
 assert.equal(header.querySelector('.rank-links [aria-current="page"]').getAttribute('href'),'/mode_rankings/trivia?entity=artists&view=bottom');
 assert.equal(header.querySelector('[data-special-view="bottom"]').getAttribute('aria-pressed'),'true');
 header.innerHTML=UI.rankingCategories('tags',UI.entityTypes.map(entity=>({entity})),'query-kind');
 assert.equal(header.querySelector('[aria-pressed="true"]').dataset.queryKind,'tags');assert.equal(header.querySelectorAll('button').length,4);
 // F uses the native document fullscreen API without stealing typing/typeahead.
 let entered=0,exited=0,fullscreen=null,pendingResolve;
 Object.defineProperty(w.document,'fullscreenElement',{configurable:true,get:()=>fullscreen});
 w.document.documentElement.requestFullscreen=()=>{entered++;fullscreen=w.document.documentElement;return Promise.resolve();};
 w.document.exitFullscreen=()=>{exited++;fullscreen=null;return Promise.resolve();};
 const key=(node,options={})=>{const event=new w.KeyboardEvent('keydown',{key:'f',bubbles:true,cancelable:true,...options});node.dispatchEvent(event);return event;};
 const flush=async()=>{for(let i=0;i<5;i++)await Promise.resolve();};
 assert.equal(key(w.document.body).defaultPrevented,true);await flush();assert.equal(entered,1);
 key(w.document.body,{key:'F'});await flush();assert.equal(exited,1);
 for(const html of ['<input>','<textarea></textarea>','<select><option>First</option></select>','<div contenteditable="true"><span>Editor</span></div>','<div role="textbox"></div>','<div class="game-select"><button>Choose</button></div>','<div role="listbox"><button role="option">First</button></div>']){
  const host=w.document.createElement('div');host.innerHTML=html;w.document.body.append(host);
  assert.equal(key(host.querySelector('span,button')||host.firstElementChild).defaultPrevented,false);host.remove();
 }
 for(const options of [{ctrlKey:true},{altKey:true},{metaKey:true},{repeat:true},{isComposing:true},{key:'g'}])assert.equal(key(w.document.body,options).defaultPrevented,false);
 const prevented=new w.KeyboardEvent('keydown',{key:'f',bubbles:true,cancelable:true});prevented.preventDefault();w.document.body.dispatchEvent(prevented);assert.equal(entered,1);
 const dialog=w.document.createElement('dialog');dialog.setAttribute('open','');w.document.body.append(dialog);assert.equal(key(w.document.body).defaultPrevented,false);dialog.remove();
 w.document.documentElement.requestFullscreen=()=>{entered++;return new Promise(resolve=>pendingResolve=resolve);};
 key(w.document.body);key(w.document.body);assert.equal(entered,2);pendingResolve();await flush();
 w.document.documentElement.requestFullscreen=()=>Promise.reject(Error('Fullscreen blocked'));
 key(w.document.body);await flush();
 w.document.documentElement.requestFullscreen=()=>{throw Error('Unsupported context');};key(w.document.body);await flush();
 w.document.documentElement.requestFullscreen=undefined;assert.equal(key(w.document.body).defaultPrevented,false);
 w.dispatchEvent(new w.Event('pagehide'));w.close();
 console.log('Shared shell: independent report loading, persistent volume, guarded F fullscreen and common search/tag policies passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
