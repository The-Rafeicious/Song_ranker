/* Listening credit requires actual media movement and both opponents. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const dom=new JSDOM('<audio src="/a"></audio><audio src="/b"></audio><button></button><button></button>',{url:'http://localhost',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,d=w.document;
let now=0;
w.performance.now=()=>now;
w.setInterval=()=>0;
w.clearInterval=()=>{};
w.eval(fs.readFileSync('static/js/ui.js','utf8'));
w.eval(fs.readFileSync('static/js/gameplay.js','utf8'));
const audios=[...d.querySelectorAll('audio')],buttons=[...d.querySelectorAll('button')];
for(const audio of audios){
 Object.defineProperties(audio,{paused:{get:()=>false},readyState:{get:()=>4},seeking:{get:()=>false}});
}
const gate=w.GameplayUI.listeningLock(audios,buttons,5);
function advance(audio,seconds,position=seconds){
 now+=seconds*1000;audio.currentTime+=position;
 audio.dispatchEvent(new w.Event('timeupdate'));
}
try{
 assert.ok(buttons.every(b=>b.disabled));
 advance(audios[0],1,20);
 assert.ok(buttons[0].textContent.includes('5s'),'Seeking forward earns no credit');
 for(let i=0;i<5;i++)advance(audios[0],1);
 assert.ok(buttons.every(b=>b.disabled),'One ready opponent cannot unlock voting');
 assert.equal(buttons[0].textContent,'Ready · listen to opponent');
 audios[1].muted=true;
 advance(audios[1],5);
 assert.ok(!gate.ready(),'Muted audio earns no credit');
 audios[1].muted=false;
 for(let i=0;i<5;i++)advance(audios[1],1);
 assert.ok(gate.ready());
 assert.ok(buttons.every(b=>!b.disabled));
 gate.dispose();
 console.log('Listening lock passed seek, mute, independent progress and pair unlock checks.');
}finally{dom.window.close();}
