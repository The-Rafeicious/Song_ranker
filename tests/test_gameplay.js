/* Run with Node + jsdom (QA dependency only). Uses fake clocks/media/HTTP. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const source=name=>fs.readFileSync(path.join(__dirname,'../static/js',name),'utf8');
let assertions=0;const snapshots={};
function capture(h,name,page,tone){h.d.body.dataset.page=page;h.d.body.dataset.tone=tone;snapshots[name]=h.d.documentElement.outerHTML}
const check=(condition,message)=>{assert.ok(condition,message);assertions++};
async function flush(){for(let i=0;i<40;i++)await Promise.resolve()}
const albumRows=[{id:1,title:'Album <one>',cover_url:''},{id:2,title:'Album two',cover_url:''},{id:3,title:'Album three',cover_url:''}];
const collection={songs:Array.from({length:40},(_,i)=>({id:i+1,title:'Song <'+(i+1)+'>',album_id:1+i%3,artist_ids:[1],tag_ids:[1],elo_score:1200+i,highest_elo:1300,matches_played:0,audio_url:i<20?'':'sample.m4a',attempts:0})),artists:[{id:1,name:'Name, With Comma',cover_url:''}],albums:albumRows,tags:[{id:1,name:'Tag <one>'}],history:[],tournaments:[],tournament_matches:[],special_modes:{}};
function harness(reduced=false){
 const dom=new JSDOM('<body class="site-style-baseline gameplay-page" data-page="qa"><main id="main"><div id="loading"></div></main><input id="volume-range" value=".5"><span id="volume-value"></span><button id="volume-btn"></button><div id="volume-panel" hidden></div><dialog id="editor"><form id="editor-form"></form></dialog><div id="toast" hidden></div></body>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document,timers=new Map(),requests=[];let now=0,id=0;
 w.performance.now=()=>now;w.matchMedia=()=>({matches:reduced});w.scrollTo=()=>{};
 w.setTimeout=(fn,delay=0)=>{const n=++id;timers.set(n,{fn,at:now+Number(delay)});return n};w.clearTimeout=n=>timers.delete(n);
 w.setInterval=(fn,delay)=>{const n=++id;timers.set(n,{fn,at:now+delay,interval:delay});return n};w.clearInterval=w.clearTimeout;
 w.requestAnimationFrame=fn=>w.setTimeout(()=>fn(now),16);w.cancelAnimationFrame=w.clearTimeout;
 w.HTMLMediaElement.prototype.play=function(){return Promise.resolve()};w.HTMLMediaElement.prototype.pause=function(){};w.HTMLMediaElement.prototype.load=function(){};
 const respond=data=>({ok:true,status:200,json:async()=>structuredClone(data)});
 let handler=()=>undefined;
 w.fetch=async(url,options={})=>{
  requests.push({url:String(url),options});
  if(url==='/api/collection')return respond(collection);
  const result=await handler(String(url),options);if(result!==undefined)return respond(result);
  if(url==='/api/tournaments')return respond({tournaments:[]});
  if(String(url).startsWith('/api/matchup'))return respond({songs:collection.songs.slice(0,2)});
  throw Error('Unexpected fixture request '+url);
 };
 w.Overall={bindUI(){}};
 w.eval(source('ui.js'));w.eval(source('gameplay.js'));
 w.eval(source('special_modes.js').replace(' return {bindUI:ui=>U=ui,',` window.testSpecial={setShelf:value=>shelf=value,shelf:()=>shelf,renderShelfBoard,revealShelfRound,checkShelf,cancelReveal,reveal,moveShelf,shiftShelf,loadShelf,setGuess:value=>guess=value,renderGuess,answerGuess};\n return {bindUI:ui=>U=ui,`));
 const ready=w.eval(source('site.js').replace('window.SpecialModes.bindUI(',`window.testSite={renderTournamentSetup,renderScope,generateBracket,gameCard,renderGame,vote,nextMatch,bracketCard,renderBracketMatch,scopeOptions,setPair:value=>pair=value,setBlind:value=>blind=value,setBracket:value=>bracketState=value,bracket:()=>bracketState};\nwindow.SpecialModes.bindUI(`));
 async function advance(ms){const end=now+ms;let steps=0;while(true){await flush();let next;for(const entry of timers)if(entry[1].at<=end&&(!next||entry[1].at<next[1].at))next=entry;if(!next)break;if(++steps>50000)throw Error('Clock runaway');const[n,t]=next;now=t.at;timers.delete(n);if(t.interval)timers.set(n,{...t,at:now+t.interval});t.fn()}now=end;await flush()}
 const key=(element,value)=>element.dispatchEvent(new w.KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true}));
 return {dom,w,d,requests,ready,advance,key,handler:fn=>handler=fn};
}
async function tournamentChecks(){
 const h=harness(),{w,d,key}=h;await h.ready;await w.testSite.renderTournamentSetup();
 check(d.querySelectorAll('[name="t-size"]').length===3,'three direct bracket sizes');
 check(d.querySelectorAll('[name="t-visibility"]').length===2,'two explicit bracket types');
 check(!d.querySelector('#generate-btn').disabled,'valid global bracket starts enabled');capture(h,'tournament-setup','tournament_play','tournament');
 d.querySelector('[name="t-size"][value="32"]').click();d.querySelector('#t-blind').click();
 check(d.querySelector('#generate-btn').disabled,'blind size uses only tracks with previews');
 check(d.querySelector('#tournament-ready').textContent.includes('20 eligible tracks'),'readiness explains ineligible bracket');
 d.querySelector('[name="t-size"][value="8"]').click();
 check(!d.querySelector('#generate-btn').disabled,'smaller blind bracket is available');
 const trigger=d.querySelector('.game-select-trigger'),menu=d.querySelector('.game-select-menu');
 trigger.getBoundingClientRect=()=>({top:500,bottom:550});Object.defineProperty(menu,'scrollHeight',{value:300});w.innerHeight=600;
 trigger.click();check(!menu.hidden&&trigger.getAttribute('aria-expanded')==='true','custom menu opens');
 check(d.activeElement.dataset.gameOption==='global','selected scope focused');
 check(d.querySelector('.game-select').classList.contains('opens-up'),'menu opens up near viewport bottom');
 key(d.activeElement,'End');check(d.activeElement.dataset.gameOption==='tag','End focus');
 key(d.activeElement,'Home');check(d.activeElement.dataset.gameOption==='global','Home focus');
 key(d.activeElement,'ArrowDown');check(d.activeElement.dataset.gameOption==='artist','ArrowDown focus');
 key(d.activeElement,' ');check(d.querySelector('#t-scope').value==='artist'&&menu.hidden,'Space selects scope');
 check(!d.querySelector('#t-scope-picker').hidden&&d.querySelector('#generate-btn').disabled,'scope needs a selection');
 d.querySelector('[data-scope-id="1"]').click();check(!d.querySelector('#generate-btn').disabled,'eligible artist selected');
 check(d.querySelector('[data-scope-id="1"]').getAttribute('aria-pressed')==='true','chosen artist state');
 trigger.click();key(d.activeElement,'a');check(d.activeElement.dataset.gameOption==='album','letter navigation cycles matching scopes');key(d.activeElement,'l');check(d.activeElement.dataset.gameOption==='album','multi-letter navigation');
 key(d.activeElement,'Escape');check(menu.hidden&&d.activeElement===trigger,'Escape returns focus');
 trigger.click();key(d.activeElement,'Tab');check(menu.hidden&&d.activeElement===trigger,'Tab exits from trigger');
 trigger.click();d.querySelector('#scope-query').focus();check(menu.hidden,'outside focus closes');
 trigger.click();d.body.click();check(menu.hidden,'outside click closes');
 trigger.click();w.dispatchEvent(new w.Event('resize'));check(menu.hidden,'resize closes');
 let generated;
 h.handler((url)=>{if(url.startsWith('/api/generate_bracket?')){generated=new URL('http://localhost'+url).searchParams;throw Error('fixture network failure')}return undefined});
 await w.testSite.generateBracket();
 check(generated.get('size')==='8'&&generated.get('is_blind')==='true'&&generated.get('scope_id')==='1','control values reach unchanged API');
 check(!d.querySelector('#generate-btn').disabled&&d.querySelector('#setup-error').textContent.includes('failure'),'failed generation restores retry');
 h.dom.window.close();
}
function shelfFixture(count){
 const slots=count===3?[3,1,2]:[2,1],lengths=count===3?[4,3,3]:[5,5];let n=0;
 const albums=slots.map((slot,i)=>({slot,title:'Album <'+i+'>',cover_url:''})),songs=[],answers=[],items=[],placements={};
 albums.forEach((album,index)=>{placements[album.slot]=[];for(let j=0;j<lengths[index];j++){
  const slot=++n,points=index===0?0:j===0?1/3:3;
  songs.push({id:slot,slot,title:'Track <'+slot+'>',audio_url:''});answers.push({slot,album_slot:album.slot,track_number:2*j+1});
  items.push({item_slot:slot,answer_slot:album.slot,answer_position:j+1,album_correct:true,order_right:index===0?0:4,order_pairs:4,points,available:3});placements[album.slot].push(slot);
 }});
 return {albums,songs,pool:[],placements,answered:true,revealed:new Set(),result:{answers,items,points:items.reduce((a,b)=>a+b.points,0),available:30,order_right:20,order_pairs:40}};
}
function shelfMarkup(d){d.querySelector('#main').innerHTML='<div class="shelf-actions"><button data-shelf-check></button><button data-shelf-next hidden></button><div id="shelf-order-score" hidden></div><span id="shelf-reveal-progress" class="shelf-reveal-progress"></span></div><button data-shelf-play></button><div id="shelf-board"></div>'}
async function shelfChecks(count,reduced){
 const h=harness(reduced),{w,d}=h;await h.ready;const S=w.testSpecial,fixture=shelfFixture(count);S.setShelf(fixture);shelfMarkup(d);S.renderShelfBoard();
 capture(h,'shelves-'+count+'-pending','shelves','shelves');const task=S.revealShelfRound();let transfers=0;const running=[];
 for(let albumIndex=0;albumIndex<count;albumIndex++){
  const album=fixture.albums[albumIndex],rows=fixture.result.answers.filter(a=>a.album_slot===album.slot);
  check(d.querySelector('[data-shelf-album="'+album.slot+'"]').dataset.revealActive==='true','albums reveal in visible order');
  const before=Number(d.querySelector('#shelf-running-score').textContent);
  for(let j=0;j<rows.length;j++){
   await h.advance(420);
   check(fixture.revealed.has(rows[j].slot),'track revealed');
   check(Number(d.querySelector('#shelf-running-score').textContent)===before,'main score waits for album completion');
   check(d.querySelector('#shelf-album-label-'+album.slot).textContent==='Album points','album accumulates locally first');
   check(d.querySelector('[data-shelf-slot="'+rows[j].slot+'"] .shelf-position-actual').textContent===String(rows[j].track_number),'correct true track number is displayed');
   if(j===0&&albumIndex===0)check(!!d.querySelector('[data-shelf-slot="'+rows[j].slot+'"] del'),'wrong order retains submitted position');
   await h.advance(2600);
  }
  check(d.querySelector('#shelf-album-label-'+album.slot).textContent==='Adding to total','album subtotal transfers after its final track');
  const subtotal=fixture.result.items.filter(i=>rows.some(a=>a.slot===i.item_slot)).reduce((sum,i)=>sum+i.points,0);
  check(d.querySelector('#shelf-album-score-'+album.slot).textContent===subtotal.toFixed(2),'album counter finishes accurately');
  await h.advance(reduced?350:1250);transfers++;
  check(fixture.scoredAlbums.has(album.slot),'each album marked transferred');running.push(Number(d.querySelector('#shelf-running-score').textContent));
 }
 await task;
 check(transfers===count&&fixture.revealComplete,'two/three album reveal completes');
 check(d.querySelector('#shelf-running-score').textContent===fixture.result.points.toFixed(2),'final total equals saved score without rounded subtotal drift');
 check(!d.querySelector('[data-shelf-next]').hidden&&!d.querySelector('#shelf-order-score').hidden,'completion exposes next and order rate');
 check(d.querySelector('#shelf-running-score').textContent!=='NaN','finite scores');
 check(running[0]===0,'zero-point album still transfers and finishes');
 check(d.querySelectorAll('[data-score-added="true"]').length===count,'completed board preserves album state');
 check(d.querySelector('[data-shelf-slot="1"] a.song').textContent==='Track <1>','escaped track name');capture(h,'shelves-'+count+'-result','shelves','shelves');
 h.dom.window.close();
}
async function cancelChecks(){
 for(const duringTransfer of [false,true]){
  const h=harness(),{w,d}=h;await h.ready;const S=w.testSpecial,fixture=shelfFixture(2);S.setShelf(fixture);shelfMarkup(d);S.renderShelfBoard();const task=S.revealShelfRound();
  await h.advance(duringTransfer?5*3020+100:100);S.cancelReveal();await task;
  const revealed=fixture.revealed.size,total=d.querySelector('#shelf-running-score').textContent;
  await h.advance(20000);
  check(fixture.revealed.size===revealed&&!fixture.revealComplete,'cancel prevents later rows and finalisation');
  check(d.querySelector('[data-shelf-next]').hidden,'cancel cannot expose next round');
  check(d.querySelector('#shelf-running-score').textContent===total,'cancelled pre-reveal score does not change');
  h.dom.window.close();
 }
}
async function placementAndGuessChecks(){
 const h=harness(),{w,d}=h;await h.ready;const S=w.testSpecial,fixture=shelfFixture(2);fixture.answered=false;fixture.pool=fixture.songs.map(s=>s.slot);fixture.placements={1:[],2:[]};S.setShelf(fixture);shelfMarkup(d);S.renderShelfBoard();
 check(d.querySelector('[data-shelf-check]').disabled,'unsorted tracks disable check');
 d.querySelector('[data-shelf-pick="1"][data-shelf-target="2"]').click();
 check(fixture.placements[2].includes(1)&&!fixture.pool.includes(1),'non-drag album menu moves track');
 S.moveShelf(2,'2');S.shiftShelf(2,-1);check(fixture.placements[2].join()==='2,1','non-drag reorder');
 check(d.activeElement.dataset.shelfSlot==='2','reorder restores keyboard focus');capture(h,'shelves-placement','shelves','shelves');
 const picker=d.querySelector('[data-shelf-slot="1"] .shelf-picker');picker.querySelector('summary').getBoundingClientRect=()=>({top:500,bottom:546});Object.defineProperty(picker.querySelector('.shelf-picker-options'),'scrollHeight',{value:220});w.innerHeight=600;h.key(picker.querySelector('summary'),'ArrowDown');check(picker.open&&d.activeElement.dataset.shelfTarget==='2','shelf picker keyboard opens on selected album');
 check(picker.querySelector('.shelf-picker-options').style.top==='auto','shelf menu opens upward near bottom');h.key(d.activeElement,'Escape');check(!picker.open&&d.activeElement===picker.querySelector('summary'),'shelf Escape');
 const song={id:1,title:'Track <one>',artists:[{name:'Artist, Name'}],album:'Unknown Album',audio_url:''};
 S.setGuess({songs:[song,{...song,id:2,title:'Track two'}],records:{},answered:true,chosen:1,result:{correct:false,ratings:[1100,1300]}});S.renderGuess();
 check(d.querySelectorAll('[data-guess-pick]:disabled').length===2,'revealed guess cannot resubmit');
 check(d.querySelector('.guess-wrong-card')&&d.querySelector('.guess-right-card'),'guess feedback identifies both outcomes');
 check(!!d.querySelector('[data-guess-next]'),'manual next pair available');
 check(![...d.querySelectorAll('a.album')].length,'unknown album omitted');capture(h,'guesser-result','guesser','guesser');
 h.dom.window.close();
}
async function votingChecks(){
 const h=harness(),{w,d}=h;await h.ready;const S=w.testSite;S.setPair(structuredClone(collection.songs.slice(0,2)));S.setBlind(true);S.renderGame();
 check(d.querySelector('h2').textContent==='Track A'&&!d.querySelector('.game-meta a'),'blind vote hides identities');
 check(d.querySelector('.cover-button').getAttribute('aria-label')==='Play anonymous track','blind playback label is anonymous');capture(h,'blind-pending','standard','blind');
 S.setBlind(false);S.renderGame();check(d.querySelector('a.artist').textContent==='Name, With Comma','whole artist name on visible vote');capture(h,'standard-pending','standard','standard');
 let saves=0;h.handler(url=>{if(url==='/api/vote'){saves++;return {winner:{elo_before:1200,elo_score:1216},loser:{elo_before:1201,elo_score:1185}}}});
 await Promise.all([S.vote(0),S.vote(0)]);await flush();
 check(saves===1,'one vote on duplicate activation');check(d.querySelectorAll('[data-vote]:disabled').length===2,'votes locked after result');
 check(d.querySelector('.winner .elo-delta').textContent.includes('+16')&&d.querySelector('.loser .elo-delta').textContent.includes('-16'),'saved rating deltas displayed');capture(h,'standard-result','standard','standard');
 d.querySelector('[data-next]').click();await flush();await h.advance(5000);
 check(h.requests.filter(r=>r.url.startsWith('/api/matchup')).length===1,'manual next cancels auto transition');check(!d.querySelector('.score-reveal'),'next pair clears result');
 const entries=collection.songs.slice(0,2).map(song=>({...song,name:song.title,album:'Album <one>'}));
 S.setBracket({tournament:{id:1,size:8,is_blind:1},tracks:new Map(entries.map(song=>[song.id,song])),matches:[{id:1,song1_id:1,song2_id:2,round_number:1,status:'pending'}],active:{id:1,song1_id:1,song2_id:2,round_number:1}});S.renderBracketMatch();
 check(d.querySelector('h2').textContent==='Track A','blind tournament hides identities');capture(h,'tournament-match','tournament_play','tournament');h.dom.window.close();
}
async function triviaChecks(){
 const h=harness(),{w,d}=h;await h.ready;d.querySelector('#main').innerHTML='<div id="trivia-root"></div>';
 let state={token:'test',song_id:1,audio_url:'sample.m4a',cover_url:'',started:false,paused:false,completed:false,elapsed:0,score:0,streak:0,high_score:0,high_streak:0,round_points:0,album_available:true,fields:Object.fromEntries(['title','artist','album'].map(f=>[f,{correct:null,actual:f+' <answer>'}]))};let finishes=0;
 h.handler((url,options)=>{
  if(url==='/api/trivia/round')return state;
  if(url.endsWith('/start')){state.started=true;return state}
  if(url.endsWith('/pause')){state.paused=JSON.parse(options.body).paused;return state}
  if(url.endsWith('/finish')){finishes++;state.completed=true;state.game_over=true;for(const v of Object.values(state.fields))v.correct=false;return state}
 });
 await w.eval(source('trivia.js').replace('await load();','window.testTrivia={start,pause,finish};await load();'));await flush();
 check(d.querySelector('#trivia-finish').disabled,'reveal unavailable until round starts');check(d.querySelector('label.song')&&d.querySelector('label.artist')&&d.querySelector('label.album'),'entity field labels');capture(h,'trivia-ready','trivia','recognition');
 await w.testTrivia.start();check(!d.querySelector('#trivia-finish').disabled&&!d.querySelector('#guess-title').disabled,'start enables answers and reveal');
 await w.testTrivia.pause();check(d.querySelector('#trivia-finish').disabled&&d.querySelector('#trivia-start').textContent==='Resume','pause disables reveal');
 await w.testTrivia.start();d.querySelector('#trivia-finish').click();await flush();await h.advance(1600);
 check(finishes===1&&d.querySelectorAll('.answer-links:not([hidden])').length===3,'touch reveal uses existing finish and linked answers');
 check(d.querySelector('#trivia-next')&&d.querySelector('#trivia-finish').disabled,'finished trivia next action');capture(h,'trivia-result','trivia','recognition');h.dom.window.close();
}
(async()=>{await votingChecks();await triviaChecks();await tournamentChecks();await shelfChecks(2,false);await shelfChecks(3,true);await cancelChecks();await placementAndGuessChecks();if(process.env.GAMEPLAY_SNAPSHOTS)fs.writeFileSync(process.env.GAMEPLAY_SNAPSHOTS,JSON.stringify(snapshots));console.log(assertions+' gameplay assertions passed')})().catch(error=>{console.error(error);process.exitCode=1});
