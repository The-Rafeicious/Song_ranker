/* Real page scripts; HTTP, pacing and native media are controlled test boundaries. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const source = name => fs.readFileSync(path.join(__dirname, '../static/js', name), 'utf8');
let assertions = 0;
const check = (value, label) => { assert.ok(value, label); assertions++; };
const equal = (a, b, label) => { assert.deepEqual(a, b, label); assertions++; };
async function settle() { for (let n = 0; n < 100; n++) await Promise.resolve(); }
const maps = ['mood', 'sound', 'craft'].map(key => ({key, label:key + ' table',
  x:{label:'X axis',low:'Low X',high:'High X'},y:{label:'Y axis',low:'Low Y',high:'High Y'}}));

async function harness(mode, {draft, hook} = {}) {
  const config = {mode,maps,max_themes:8,tags:Array.from({length:12},(_,i)=>({id:i+1,name:'Tag '+(i+1),description:'Description '+(i+1)}))};
  const dom = new JSDOM(`<body><div class="judgement-game" data-judgement-mode="${mode}"><div id="judgement-round" aria-busy="true"><p>Loading</p></div><p id="judgement-error" hidden></p><div id="judgement-recovery" hidden><button id="judgement-retry">Retry</button></div></div><script id="judgement-config" type="application/json">${JSON.stringify(config)}</script></body>`,
    {url:'http://localhost/'+mode,runScripts:'outside-only',pretendToBeVisual:true});
  const w = dom.window, d = w.document, requests = [], plays = [], errors = [], receipts = new Map();
  const paused = new WeakMap(), timers = [], scheduled = new Map();
  let clock=0,timerId=0;
  w.performance.now=()=>clock;
  w.setTimeout=(fn,ms=0)=>{const id=++timerId;scheduled.set(id,{fn,at:clock+ms});return id;};
  w.clearTimeout=id=>scheduled.delete(id);
  let offered = 0, prepared, sampleCount = 0, handler = hook || (()=>undefined);
  if (draft) w.sessionStorage.setItem('songRankerJudgement:'+mode,draft);
  Object.defineProperty(w.HTMLMediaElement.prototype,'paused',{get(){return paused.get(this)!==false}});
  w.HTMLMediaElement.prototype.pause = function(){paused.set(this,true);this.dispatchEvent(new w.Event('pause'));};
  w.HTMLMediaElement.prototype.load = function(){};
  w.PreviewPlayback = {
    source:(id,url)=>url,bind(){},
    async play(audio){for(const a of d.querySelectorAll('audio'))if(a!==audio)a.pause();paused.set(audio,false);plays.push(audio.id);audio.dispatchEvent(new w.Event('playing'));},
    cancel(audio){audio.pause();},stopAll(){for(const a of d.querySelectorAll('audio'))a.pause();},
    forgetPair(audios){audios.forEach(a=>a.pause());return Promise.resolve();}
  };
  w.Listening = {start(){},sample(){sampleCount++;return {version:1,decision_ms:1000,songs:[]};}};
  w.RoundFlow = {
    duration:name=>({spotlightPreview:20000,spotlightResult:2000,spotlightSettle:700}[name] || 4500),
    take(name,loader){const value=prepared;prepared=null;return value || loader();},
    prepare(name,loader){prepared=loader();prepared.catch(()=>{});},
    after(callback){const task={callback,cancelled:false};timers.push(task);return ()=>task.cancelled=true;},
    clear(){prepared=null;}
  };
  const respond = (body,status=200) => ({ok:status<400,status,json:async()=>structuredClone(body)});
  w.fetch = async(url,options) => {
    const payload = JSON.parse(options.body), request = {url,payload};requests.push(request);
    const custom = await handler(request);
    if (custom !== undefined) return respond(custom.body,custom.status || 200);
    if (url.endsWith('/round')) {
      offered++;
      return respond({token:'round-'+mode+'-'+offered+'-'.repeat(32),mode,rules_version:1,
        suggested_maps:['mood','sound','craft'],songs:Array.from({length:mode==='vibe'?1:4},(_,slot)=>({slot,id:slot+1,title:slot===0?'<img src=x onerror=bad()>':'Song '+slot,
          audio_url:'https://example.test/preview/'+slot,cover_url:'https://example.test/cover/'+slot,
          album:slot===2?'Unknown Album':slot===3?'Example - Single':'Album <one> & "two"',
          album_id:1,artists:[{id:1,name:'Artist <one>'}]}))});
    }
    if (url.endsWith('/answer')) {
      if (!receipts.has(payload.token)) receipts.set(payload.token,{id:requests.length,mode,
        status:payload.skip?'skipped':'answered',maps:payload.maps,allocations:payload.allocations});
      return respond(receipts.get(payload.token));
    }
    throw Error('Unexpected request '+url);
  };
  w.addEventListener('error',e=>errors.push(e.message));
  for (const file of ['ui.js','spotlight.js','judgement_game.js']) w.eval(source(file));
  await settle();
  const find = selector => {const node=d.querySelector(selector);assert.ok(node,'Missing '+selector);return node;};
  return {w,d,requests,plays,errors,timers,find,
    async advance(ms) {
      const end=clock+ms;
      for(let count=0;count<1000;count++) {
        const due=[...scheduled].filter(([,task])=>task.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];
        if(!due)break;
        clock=due[1].at;scheduled.delete(due[0]);due[1].fn();await settle();
      }
      clock=end;await settle();
    },
    click(selector){find(selector).click();},
    input(selector,value){const node=find(selector);node.value=value;node.dispatchEvent(new w.Event('input',{bubbles:true}));},
    change(selector,checked){const node=find(selector);node.checked=checked;node.dispatchEvent(new w.Event('change',{bubbles:true}));},
    key(selector,key){find(selector).dispatchEvent(new w.KeyboardEvent('keydown',{key,bubbles:true}));},
    hook(fn){handler=fn;},answers:()=>requests.filter(r=>r.url.endsWith('/answer')),
    draft:()=>w.sessionStorage.getItem('songRankerJudgement:'+mode),samples:()=>sampleCount,
    close(){w.dispatchEvent(new w.Event('pagehide'));w.close();}};
}

function place(h, slot, value) {
  h.click(`.spotlight-select[data-spotlight-select="${slot}"]`);
  h.input('#spotlight-line',String(value));
}
function equalSplit(h) {for(let slot=0;slot<4;slot++)place(h,slot,50);}
async function spotlight() {
  const h = await harness('spotlight');
  equal(h.errors,[],'Initial render has no errors');
  check(h.find('#judgement-save').disabled,'All four tracks must be placed');
  equal(h.plays,[],'No autoplay on entry');
  equal(h.find('#spotlight-budget').textContent,'12 available');
  equal(h.d.querySelectorAll('[data-share], [data-share-step], [data-j-equal], [data-j-skip]').length,0,'Manual points, equal-split and Skip controls are removed');
  equal(h.d.querySelectorAll('.spotlight-marker:not([hidden])').length,0,'No invented placements');
  check(h.find('[data-judgement-play]').classList.contains('cover-button'));
  equal(h.find('.play-overlay').parentElement,h.find('[data-judgement-play]'));
  equal(h.find('.judgement-album').textContent,'Album <one> & "two"');
  equal(h.find('.judgement-album').getAttribute('href'),'/album/'+encodeURIComponent('Album <one> & "two"'));
  equal(h.d.querySelectorAll('.judgement-album').length,2,'Singles/unknown omission retained');
  h.click('.spotlight-select[data-spotlight-select="2"]');
  check(h.find('[data-spotlight-card="2"]').classList.contains('is-active'),'Dedicated selector selects its track');
  check(h.find('.spotlight-select').parentElement.classList.contains('judgement-track-copy'),'Selector is below metadata');
  equal(h.plays,[],'Selecting a card does not start a preview');
  h.click('#spotlight-line');
  equal(h.d.querySelectorAll('.spotlight-marker:not([hidden])').length,1,'A centre click places a track even when slider value is unchanged');
  check(h.find('#judgement-save').disabled,'Partial placements cannot save');
  equalSplit(h);
  check(!h.find('#judgement-save').disabled);
  check([...h.d.querySelectorAll('[data-spotlight-points]')].every(output=>output.hidden),'Points stay hidden before results');
  equal(h.d.querySelectorAll('.spotlight-marker img').length,4,'Bar uses cover thumbnails');
  check(h.find('.spotlight-marker').style.getPropertyValue('--fan-x')!=='','Overlap has an expanded position');
  equal(h.find('[data-spotlight-loop]').parentElement,h.find('#spotlight-budget').parentElement,'Loop belongs in the footer');
  equal(h.find('[data-spotlight-loop]').previousElementSibling.id,'spotlight-budget');
  equal(h.find('[data-spotlight-loop]').nextElementSibling.id,'judgement-save');
  equal(h.find('#judgement-save').textContent,'Next round');
  equal(h.find('#spotlight-budget').textContent,'12 / 12 shared');
  const audio=h.find('audio');
  h.click('[data-judgement-play]');await settle();
  equal(h.plays.length,1);equal(h.find('[data-judgement-play]').dataset.playing,'true');
  h.click('.play-overlay');await settle();equal(h.find('[data-judgement-play]').dataset.playing,'false');
  h.click('.play-overlay');await settle();equal(h.find('[data-judgement-play]').getAttribute('aria-pressed'),'true');
  h.click('#judgement-save');h.click('#judgement-save');await settle();
  equal(h.answers().length,1);equal(h.answers()[0].payload.allocations,[3,3,3,3]);
  check(!('positions' in h.answers()[0].payload),'Only existing integer points are sent to the API');
  check(h.find('#judgement-result').textContent.includes('Round saved'));
  equal([...h.d.querySelectorAll('[data-spotlight-points] strong')].map(n=>Number(n.textContent)),[3,3,3,3]);
  check([...h.d.querySelectorAll('[data-spotlight-points]')].every(output=>!output.hidden),'Confirmed results reveal points');
  equal(h.find('audio'),audio,'Saving retains audio nodes');check(h.find('#spotlight-line').disabled);
  equal(h.samples(),1);equal(h.draft(),null);
  h.click('[data-j-next]');await settle();
  equal(h.requests.filter(r=>r.url.endsWith('/round')).length,2);const heard=h.plays.length;await h.advance(10000);equal(h.plays.length,heard,'Manual next cancels remaining result snippets');h.close();
}
async function relativeAndLoop() {
  let h=await harness('spotlight');
  [100,0,0,0].forEach((x,slot)=>place(h,slot,x));
  check([...h.d.querySelectorAll('[data-spotlight-points]')].every(output=>output.hidden));
  h.key('#spotlight-line','ArrowRight');
  equal(h.find('#spotlight-line').value,'1','Keyboard nudges selected placement');
  h.key('#spotlight-line','End');equal(h.find('#spotlight-line').value,'100');
  h.key('#spotlight-line','Home');equal(h.find('#spotlight-line').value,'0');
  h.click('#judgement-save');await settle();equal(h.answers()[0].payload.allocations,[12,0,0,0]);h.close();
  h=await harness('spotlight');
  h.click('[data-spotlight-loop]');await settle();
  equal(h.plays,['judgement-audio-0']);equal(h.find('[data-spotlight-loop]').getAttribute('aria-pressed'),'true');
  h.click('[data-judgement-play="judgement-audio-2"]');await settle();
  equal(h.plays.at(-1),'judgement-audio-2','Clicking ahead redirects the loop');
  equal(h.d.querySelectorAll('[data-playing=true]').length,1,'One current player');
  h.click('[data-spotlight-loop]');await settle();
  equal(h.find('[data-spotlight-loop]').getAttribute('aria-pressed'),'false');
  check([...h.d.querySelectorAll('audio')].every(a=>a.paused),'Stop loop pauses previews');
  h.click('[data-spotlight-loop]');await settle();
  Object.defineProperty(h.d,'hidden',{configurable:true,value:true});h.d.dispatchEvent(new h.w.Event('visibilitychange'));
  equal(h.find('[data-spotlight-loop]').getAttribute('aria-pressed'),'false','Hiding tab stops rotation');h.close();
  h=await harness('vibe');h.click('[data-j-skip]');await settle();
  check(h.answers()[0].payload.skip);check(!('listening' in h.answers()[0].payload),'Vibe skip remains unjudged');h.close();
}
async function delayedSelectionAndResults() {
  let h=await harness('spotlight');
  place(h,0,40);const pulse=h.find('.spotlight-placement').dataset.pulse;
  await h.advance(1000);h.input('#spotlight-line','45');
  check(h.find('.spotlight-placement').dataset.pulse!==pulse,'Placement pulses the rail');
  await h.advance(1499);equal(h.find('.spotlight-select[aria-pressed=true]').dataset.spotlightSelect,'0','Adjustment resets idle delay');
  await h.advance(1);equal(h.find('.spotlight-select[aria-pressed=true]').dataset.spotlightSelect,'1','Idle placement selects next unplaced song');
  h.click('.spotlight-select[data-spotlight-select="0"]');h.input('#spotlight-line','70');await h.advance(1500);
  equal(h.find('.spotlight-select[aria-pressed=true]').dataset.spotlightSelect,'1','Revisiting a placed song can auto-advance again');
  place(h,2,60);await h.advance(700);h.click('.spotlight-select[data-spotlight-select="0"]');await h.advance(2000);
  equal(h.find('.spotlight-select[aria-pressed=true]').dataset.spotlightSelect,'0','Manual selection cancels a pending automatic move');
  h.find('#spotlight-line').dispatchEvent(new h.w.Event('pointerdown',{bubbles:true}));h.input('#spotlight-line','80');
  await h.advance(3000);equal(h.find('.spotlight-select[aria-pressed=true]').dataset.spotlightSelect,'0','Dragging never changes the selected song mid-gesture');
  h.w.dispatchEvent(new h.w.Event('pointerup'));await h.advance(1500);
  equal(h.find('.spotlight-select[aria-pressed=true]').dataset.spotlightSelect,'1');h.close();
  h=await harness('spotlight');
  [0,100,60,40].forEach((x,slot)=>place(h,slot,x));
  const before=h.plays.length;h.click('#judgement-save');await settle();
  const receipt=h.answers()[0].payload.allocations;
  const order=[0,1,2,3].sort((a,b)=>receipt[b]-receipt[a]||a-b);
  equal(h.plays.slice(before),['judgement-audio-'+order[0]],'Result playback starts with the highest point score');
  check(h.find('[data-spotlight-card="'+order[0]+'"]').classList.contains('is-result-playing'));
  await h.advance(8000);
  equal(h.plays.slice(before),order.map(slot=>'judgement-audio-'+slot),'Results visit score order once');
  check([...h.d.querySelectorAll('audio')].every(audio=>audio.paused),'Results stop after the last snippet');
  check(h.timers.length===1,'Only completed result sequence schedules the next round');
  const resultPositions=h.w.Spotlight.resultPositions(receipt);
  const lefts=[...h.d.querySelectorAll('.spotlight-marker')].map(node=>parseFloat(node.style.getPropertyValue('--rest-x')));
  for(let i=0;i<4;i++)for(let j=0;j<4;j++)if(resultPositions[i]<resultPositions[j])check(lefts[i]<lefts[j],'Result thumbnails rearrange into point order');
  equal(h.samples(),1,'Result previews never resubmit listening');
  h.timers[0].callback();await settle();check(h.find('#judgement-save').disabled,'Next offer starts unplaced');h.close();
  h=await harness('spotlight');equalSplit(h);
  h.w.PreviewPlayback.play=async()=>{throw Object.assign(Error('Blocked'),{name:'NotAllowedError'});};
  h.click('#judgement-save');await settle();
  equal(h.timers.length,0,'Playback permission block retains results for manual Play/Next');
  check(!h.find('[data-j-next]').disabled);h.close();
}
async function retryAndDraft() {
  let failed=false;
  const h=await harness('spotlight',{hook:r=>{if(r.url.endsWith('/answer')&&!failed){failed=true;throw Error('Offline');}}});
  equalSplit(h);h.click('#judgement-save');await settle();
  check(!h.find('#judgement-recovery').hidden);check(h.find('#spotlight-line').disabled);
  const original=structuredClone(h.answers()[0].payload),draft=h.draft();
  h.click('#judgement-retry');await settle();
  equal(h.answers()[1].payload,original);equal(h.samples(),1);check(!h.find('#judgement-result').hidden);h.close();
  const restored=await harness('spotlight',{draft});
  check(restored.find('#spotlight-line').disabled);equal(restored.find('#judgement-retry').textContent,'Retry same save');
  restored.click('#judgement-retry');await settle();equal(restored.answers()[0].payload,original);equal(restored.samples(),0);restored.close();
  const oldDraft=JSON.stringify({token:'round-spotlight-1'+'-'.repeat(32),allocations:[6,4,2,0],pending:original});
  const legacy=await harness('spotlight',{draft:oldDraft});legacy.click('#judgement-retry');await settle();
  equal(legacy.answers()[0].payload,original,'Old unconfirmed manual receipts still retry unchanged');legacy.close();
}
async function vibeMaps() {
  const h=await harness('vibe');
  check(!!h.find('.judgement-album'),'Vibe track includes its album link');
  check(h.find('#judgement-save').disabled);
  equal(h.d.querySelectorAll('[role=radio][aria-checked=true]').length,0,'No default centre placement');
  h.click('[data-vibe-x="1"][data-vibe-y="4"]');
  check(!h.find('#judgement-save').disabled);
  equal(h.find('#judgement-save').textContent,'Save 1 map');
  h.click('[data-vibe-tab="sound"]');
  equal(h.d.querySelectorAll('[role=radio][aria-checked=true]').length,0,'Another table remains unknown');
  h.click('[data-vibe-x="0"][data-vibe-y="0"]');
  h.key('[data-vibe-x="0"][data-vibe-y="0"]','ArrowUp');
  equal(h.find('[role=radio][aria-checked=true]').dataset.vibeY,'1','Up increases Y');
  h.key('[data-vibe-tab="sound"]','ArrowRight');
  equal(h.find('[role=tab][aria-selected=true]').dataset.vibeTab,'craft','Keyboard tabs change tables');
  h.click('[data-vibe-x="4"][data-vibe-y="2"]');
  h.click('[data-vibe-clear]');
  equal(h.find('#judgement-save').textContent,'Save 2 maps','Clearing one table preserves others');
  h.click('#judgement-save');await settle();
  equal(h.answers()[0].payload.maps,[{map:'mood',x:1,y:4},{map:'sound',x:0,y:1}]);
  check(!('themes' in h.answers()[0].payload),'Unreviewed tags omitted');
  equal(h.d.querySelectorAll('[role=radio][aria-checked=true]').length,0,'Unplaced active table stays empty after save');
  h.close();
}
async function themes() {
  let h=await harness('vibe');h.click('[data-vibe-x="2"][data-vibe-y="2"]');
  for(let id=1;id<=8;id++) h.change(`[data-theme][value="${id}"]`,true);
  check(h.find('[data-theme][value="9"]').disabled,'Eight-tag limit blocks further tags');
  equal(h.d.querySelectorAll('[data-theme]:checked').length,8);
  check(h.find('#vibe-tag-status').textContent.includes('tags reviewed'));
  h.input('#vibe-tag-search','Description 12');
  equal(h.d.querySelectorAll('[data-tag-search]:not([hidden])').length,1,'Search includes descriptions');
  h.click('[data-theme-none]');
  equal(h.d.querySelectorAll('[data-theme]:checked').length,0);
  h.click('#judgement-save');await settle();
  equal(h.answers()[0].payload.themes,[],'None fit explicitly records an empty review');h.close();
  h=await harness('vibe');h.click('[data-vibe-x="2"][data-vibe-y="2"]');
  h.change('[data-theme][value="1"]',true);h.change('[data-theme][value="1"]',false);
  h.click('#judgement-save');await settle();
  equal(h.answers()[0].payload.themes,[],'Unchecking the final tag stays reviewed');h.close();
  h=await harness('vibe');h.click('[data-vibe-x="2"][data-vibe-y="2"]');h.click('[data-theme-none]');h.click('[data-theme-clear]');
  h.click('#judgement-save');await settle();
  check(!('themes' in h.answers()[0].payload),'Clear review restores unknown tags');h.close();
}
async function errorsAndExit() {
  let blocked=true;
  let h=await harness('vibe',{hook:r=>r.url.endsWith('/round')&&blocked?{status:409,body:{message:'Add a song with a preview.'}}:undefined});
  equal(h.find('#judgement-error').textContent,'Add a song with a preview.');
  check(!h.find('#judgement-recovery').hidden);blocked=false;h.click('#judgement-retry');await settle();
  check(!!h.find('.vibe-grid'),'Pool retry recovers the actual game');h.close();
  h=await harness('vibe',{hook:r=>r.url.endsWith('/answer')?{status:409,body:{message:'A chosen tag was removed. Review the tags again.'}}:undefined});
  h.click('[data-vibe-x="1"][data-vibe-y="1"]');h.change('[data-theme][value="1"]',true);h.click('#judgement-save');await settle();
  check(!h.find('[data-theme-clear]').disabled,'Definite tag validation failure can be corrected');
  check(!h.find('#judgement-error').hidden);h.close();
  let resolve;
  h=await harness('vibe',{hook:r=>r.url.endsWith('/answer')?new Promise(done=>resolve=done):undefined});
  h.click('[data-vibe-x="1"][data-vibe-y="1"]');h.click('#judgement-save');await settle();
  h.w.dispatchEvent(new h.w.Event('pagehide'));
  resolve({body:{status:'answered',maps:[{map:'mood',x:1,y:1}]}});await settle();
  check(h.find('#judgement-result').hidden,'Late acknowledgement cannot change an exited page');
  equal(h.timers.length,0,'Exit prevents delayed next-round timers');h.close();
}
async function escapingAndDraft() {
  const h=await harness('spotlight');
  equal(h.find('.judgement-track-copy .song').textContent,'<img src=x onerror=bad()>');
  equal(h.d.querySelectorAll('.judgement-track-copy img').length,0,'Song text cannot create markup');
  equal(h.find('.judgement-artists').textContent,'Artist <one>');
  place(h,0,75);const draft=h.draft();h.close();
  const restored=await harness('spotlight',{draft});
  equal(restored.find('#spotlight-line').value,'75','Placement draft resumes its offered token');
  equal(restored.requests.length,1,'Restoring a draft does not save an answer');restored.close();
}
async function actualPacing() {
  const dom=new JSDOM('<select id="round-pace"><option value="standard">Standard</option><option value="quick">Quick</option></select>',
    {url:'http://localhost/shared_spotlight',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window;w.eval(source('round_flow.js'));
  equal(w.RoundFlow.duration('spotlightPreview'),20000,'Real Standard pacing supplies twenty seconds');
  equal(w.RoundFlow.duration('spotlightResult'),2000);
  const select=w.document.getElementById('round-pace');select.value='quick';select.dispatchEvent(new w.Event('change',{bubbles:true}));
  equal(w.RoundFlow.duration('spotlightPreview'),10000,'Real Quick setting supplies ten seconds');
  equal(w.RoundFlow.duration('spotlightResult'),1000);
  w.dispatchEvent(new w.StorageEvent('storage',{key:'songRankerPlaySettings',newValue:'{"pace":"standard"}'}));
  equal(w.RoundFlow.duration('spotlightPreview'),20000,'Cross-tab setting changes update the duration');
  w.dispatchEvent(new w.Event('pagehide'));w.close();
}
(async()=>{
  for (const test of [spotlight,relativeAndLoop,delayedSelectionAndResults,retryAndDraft,vibeMaps,themes,errorsAndExit,escapingAndDraft,actualPacing]) await test();
  console.log(`Judgement gameplay: ${assertions} assertions passed.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
