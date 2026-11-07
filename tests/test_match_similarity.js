/* Real head-to-head controllers: similarity staging, privacy and cancellation. */
const fs=require('node:fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const flush=async()=>{for(let n=0;n<80;n++)await Promise.resolve()};
async function harness({tournament=false,similarity={similarity:82.4,shared_maps:2,total_maps:4},reduced=false,quick=false,blind=false,elo=true,fail=false}={}){
 const page=tournament?'tournament_play':'standard';
 const dom=new JSDOM(`<body data-page="${page}"><main id="main"><div id="loading"></div></main><input id="volume-range" value=".5"><span id="volume-value"></span><button id="volume-btn"></button><div id="volume-panel" hidden></div><dialog id="editor"><form id="editor-form"><h2 id="editor-title"></h2><div id="editor-fields"></div><button id="editor-submit"></button></form></dialog><div id="toast"></div></body>`,{url:'http://localhost/'+(tournament?'tournament?tournament=1':'game?mode='+(blind?'blind':'standard')),runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document;let now=0,serial=0;const timers=new Map(),requests=[];
 w.scrollTo=()=>{};w.matchMedia=()=>({matches:reduced});w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.load=function(){};
 w.requestAnimationFrame=()=>0; // Observe phase changes independently of score animation frames.
 const tracks=Array.from({length:4},(_,i)=>({id:i+1,title:'Song '+(i+1),artist_ids:[],tag_ids:[],album_id:null,elo_score:1200,audio_url:''}));
 const matches=[1,2].map((n,i)=>({id:n,tournament_id:1,round_number:1,match_number:n,match_type:'bracket',song1_id:2*i+1,song2_id:2*i+2,status:'pending'}));
 const bracket={tournament:{id:1,size:8,status:'in_progress',is_blind:blind,scope_type:'global'},entries:tracks,matches};
 const receipt=(a,b)=>({winner:{...tracks[a-1],elo_before:1200,elo_score:1216},loser:{...tracks[b-1],elo_before:1200,elo_score:1184}});
 w.fetch=async(url,options={})=>{requests.push(url);let data={};
  if(url==='/api/collection')data={songs:tracks,albums:[],artists:[],tags:[]};
  else if(url.startsWith('/api/matchup'))data={token:'round-'+serial++,rules_version:1,songs:tracks.slice(0,2)};
  else if(url==='/api/vote'){if(fail)return {ok:false,status:400,json:async()=>({message:'Vote failed'})};const body=JSON.parse(options.body);data={...receipt(body.winner_id,body.loser_id),match_similarity:similarity};}
  else if(url==='/api/tournaments')data={tournaments:[]};
  else if(url.startsWith('/api/tournaments/'))data=bracket;
  else if(url==='/api/tournament_vote'){const body=JSON.parse(options.body),match=matches.find(m=>m.id===body.match_id);match.status='completed';data={points_awarded:1,matches,elo_result:elo?receipt(body.winner_id,body.loser_id):null,match_similarity:similarity};}
  else throw Error('Unexpected '+url);
  return {ok:true,json:async()=>data};
 };
 w.eval(fs.readFileSync('static/js/ui.js','utf8'));w.eval(fs.readFileSync('static/js/gameplay.js','utf8'));
 w.RoundFlow={take:(_key,fn)=>fn(),prepare(){},duration:name=>({pairResult:quick?2200:4500,similarity:quick?250:700,tournamentFirst:7500,tournamentPoints:2800,score:1100}[name]||0),after:(fn,delay)=>{const id=++serial;timers.set(id,{fn,at:now+delay});return ()=>timers.delete(id)}};
 await w.eval(fs.readFileSync('static/js/site.js','utf8'));await flush();
 const tick=async ms=>{const end=now+ms;while(true){const next=[...timers].filter(([,v])=>v.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;timers.delete(next[0]);now=next[1].at;next[1].fn();await flush()}now=end};
 const click=async selector=>{assert.ok(d.querySelector(selector),'Missing '+selector+' '+d.querySelector('#loading')?.textContent);d.querySelector(selector).click();await flush()};
 return {dom,w,d,tick,click,requests,timers};
}
(async()=>{
 for(const tournament of [false,true]){
  const h=await harness({tournament,blind:true}),{d}=h;
  assert.equal(d.querySelector('.match-similarity'),null,'no similarity before voting');
  assert.ok(d.querySelector('.matchup'),d.body.innerHTML);assert.ok(d.querySelector('.matchup').textContent.includes('Track A'),'blind identities remain hidden');
  await h.click(tournament?'[data-tournament-vote="0"]':'[data-vote="0"]');
  const badge=d.querySelector('.match-similarity');assert.ok(badge.textContent.includes('82.4%'));assert.ok(badge.textContent.includes('2/4 maps'));
  assert.equal(d.querySelectorAll('.score-reveal:not([hidden])').length,0,'similarity appears before scores');
  await h.tick(699);assert.equal(d.querySelectorAll('.score-reveal:not([hidden])').length,0);
  await h.tick(1);assert.equal(d.querySelectorAll('.score-reveal:not([hidden])').length,2,'scores reveal after similarity pause');
  assert.equal(d.querySelector('.match-similarity'),badge,'badge remains in place');
  if(tournament){assert.ok(d.querySelector('#bracket-points'));await h.tick(2800);assert.ok(d.querySelector('#bracket-elo-0'));assert.equal(d.querySelector('.match-similarity'),badge,'badge remains through points→Elo');}
  await h.click(tournament?'[data-bracket-next]':'[data-next]');assert.equal(d.querySelector('.match-similarity'),null,'next match clears similarity');h.dom.window.close();
 }
 for(const options of [{similarity:null},{reduced:true},{similarity:{similarity:0,shared_maps:1,total_maps:4},quick:true}]){
  const h=await harness(options);await h.click('[data-vote="0"]');
  if(options.quick){assert.ok(h.d.querySelector('.match-similarity').textContent.includes('0%'));await h.tick(250);}
  assert.equal(h.d.querySelectorAll('.score-reveal:not([hidden])').length,2,'missing evidence/reduced motion adds no pause');h.dom.window.close();
 }
 const cancelled=await harness();await cancelled.click('[data-vote="0"]');await cancelled.click('[data-next]');await cancelled.tick(700);assert.equal(cancelled.d.querySelector('.score-reveal'),null,'stale timer cannot reveal a new round');cancelled.dom.window.close();
 const failed=await harness({fail:true});await failed.click('[data-vote="0"]');assert.equal(failed.d.querySelector('.match-similarity'),null,'failed vote reveals nothing');failed.dom.window.close();
 const local=await harness({tournament:true,elo:false});await local.click('[data-tournament-vote="0"]');await local.tick(700);assert.ok(local.d.querySelector('#bracket-points'));await local.tick(2800);assert.equal(local.d.querySelector('#bracket-elo-0'),null,'points-only matches retain their normal scoring');local.dom.window.close();
 console.log('Match similarity: staged ordinary/blind/tournament reveals, missing data, Quick, reduced motion, failures and cancellation passed.');
})().catch(error=>{console.error(error);process.exit(1)});
