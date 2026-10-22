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
 assert.equal(w.SongRankerUI.searchText(' Beyoncé '),'beyonce');
 assert.equal(w.SongRankerUI.identityText('  A   TAG  '),'a tag');
 w.dispatchEvent(new w.Event('pagehide'));w.close();
 console.log('Shared shell: independent report loading, persistent volume and common search/tag policies passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
