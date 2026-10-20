/* Allocation properties and real rotation state with a deterministic media clock. */
const assert = require('node:assert/strict');
const {allocate, resultOrder, resultPositions, createRotation} = require('../static/js/spotlight.js');
let checks = 0;
function equal(a, b, label) {assert.deepEqual(a, b, label);checks++;}
function check(value, label) {assert.ok(value, label);checks++;}
const settle = async () => {for (let i = 0; i < 100; i++) await Promise.resolve();};
function allocations() {
  for (const [position,points] of [[0,0],[20,1],[50,3],[80,5],[100,6]])
    equal(allocate(Array(4).fill(position)),Array(4).fill(points));
  equal(allocate([80,60,40,20]),[7,4,2,0]);
  equal(allocate([0,100,100,100],1),[0,4,4,4],'Legacy scoring remains available');
  equal(resultOrder([2,5,5,0]),[1,2,0,3]);
  equal(resultPositions([2,5,5,0]),[50,100,100,0]);
  equal(resultPositions([3,3,3,3]),[50,50,50,50]);
  equal(allocate([100,0,0,0]),[12,0,0,0]);
  equal(allocate([0,100,100,100]),[0,8,8,8]);
  equal(allocate([49,50,50,51]),[3,3,3,3],'Nearby placements keep similar shares');
  check(allocate([0,20,60,100])[3] > allocate([40,45,55,60])[3],'Larger distances express more strength');
  for (const invalid of [null,[],Array(4),[1,2,3],[1,2,3,null],[true,2,3,4],[NaN,2,3,4],[-1,2,3,4],[101,2,3,4],[1.5,2,3,4]]) equal(allocate(invalid),null);
  let cases = 0;
  const grid = Array.from({length:21},(_,i)=>i*5);
  for (const a of grid) for (const b of grid)
    for (const c of grid) for (const d of grid) {
      const positions = [a,b,c,d], points = allocate(positions);
      assert.ok(points.reduce((x,y)=>x+y)<=24);
      assert.ok(points.every(x=>Number.isInteger(x)&&x>=0&&x<=12));
      for(let i=0;i<4;i++)for(let j=0;j<4;j++) {
        if(positions[i]===positions[j])assert.equal(points[i],points[j]);
        if(positions[i]>positions[j])assert.ok(points[i]>=points[j]);
      }
      assert.deepEqual(allocate([...positions].reverse()),[...points].reverse(),'Card order cannot change shares');
      if(Math.max(...positions)<=75)assert.ok(allocate(positions.map(x=>x+25)).every((p,i)=>p>=points[i]),'Stronger connection never reduces points');
      cases++;
    }
  console.log(`Spotlight allocation: ${cases} distance/tie/order/translation cases passed.`);
}
class Audio extends EventTarget {
  constructor() {super();this.paused=true;this.currentTime=0;}
  pause() {this.paused=true;this.dispatchEvent(new Event('pause'));}
  playing() {this.paused=false;this.dispatchEvent(new Event('playing'));}
}
function harness(playHook, extra={}) {
  let clock=0, pace=20000, nextId=0;
  const timers=new Map(),players=Array.from({length:4},()=>new Audio()),plays=[],errors=[];
  const rotation=createRotation({players,
    play:async audio=>{plays.push(players.indexOf(audio));if(playHook)return playHook(audio);audio.playing();},
    stop:()=>players.forEach(a=>a.pause()),duration:()=>pace,
    onError:e=>errors.push(e),now:()=>clock,
    schedule:(fn,ms)=>{const id=++nextId;timers.set(id,{at:clock+ms,fn});return id;},cancel:id=>timers.delete(id),...extra});
  return {rotation,players,plays,errors,timers,setPace:ms=>{pace=ms;rotation.paceChanged();},
    async advance(ms) {
      const end=clock+ms;
      while(true) {
        const due=[...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];
        if(!due)break;
        clock=due[1].at;timers.delete(due[0]);due[1].fn();await settle();
      }
      clock=end;await settle();
    }};
}
async function rotationTests() {
  const h=harness();equal(h.plays,[],'No autoplay');
  h.rotation.start();await settle();equal(h.plays,[0]);
  await h.advance(19999);equal(h.plays,[0],'Standard segment lasts 20 seconds');
  await h.advance(1);equal(h.plays,[0,1]);
  h.rotation.jump(3);await settle();equal(h.plays,[0,1,3],'Manual jump starts its own segment');
  await h.advance(20000);equal(h.plays,[0,1,3,0],'Last song wraps to first');
  await h.advance(6000);h.setPace(10000);
  await h.advance(3999);equal(h.plays.at(-1),0);
  await h.advance(1);equal(h.plays.at(-1),1,'Pace change counts already heard time');
  await h.advance(2000);h.players[1].dispatchEvent(new Event('waiting'));
  await h.advance(50000);equal(h.plays.at(-1),1,'Buffering time does not consume preview time');
  h.players[1].playing();await h.advance(7999);equal(h.plays.at(-1),1);
  await h.advance(1);equal(h.plays.at(-1),2);
  equal(h.players.filter(a=>!a.paused).length,1,'Only one preview plays');
  h.rotation.stop(false);const count=h.plays.length;
  check(!h.players[2].paused,'Save can retain the current audio element');
  await h.advance(60000);equal(h.plays.length,count,'Stopping cancels further segments');
  h.rotation.destroy();check(h.players.every(a=>a.paused));equal(h.timers.size,0);
  const quick=harness();quick.setPace(10000);quick.rotation.start(2);await settle();
  await quick.advance(9999);equal(quick.plays,[2]);await quick.advance(1);equal(quick.plays,[2,3],'Quick is 10 seconds');quick.rotation.destroy();
  const bad=harness(async()=>{throw Error('Unavailable');});bad.rotation.start();await settle();
  equal(bad.plays,[0,1,2,3]);check(!bad.rotation.active,'Four failures stop instead of spinning forever');equal(bad.timers.size,0);bad.rotation.destroy();
  const blocked=harness(async()=>{throw Object.assign(Error('Press play'),{name:'NotAllowedError'});});
  blocked.rotation.start();await settle();equal(blocked.plays,[0]);check(!blocked.rotation.active);blocked.rotation.destroy();
  let completed=0;
  const finite=harness(undefined,{repeat:false,onComplete:()=>completed++});
  finite.rotation.start();await settle();await finite.advance(80000);
  equal(finite.plays,[0,1,2,3],'A results pass plays every song once');equal(completed,1);
  await finite.advance(80000);equal(finite.plays,[0,1,2,3]);equal(completed,1);check(!finite.rotation.active);finite.rotation.destroy();
  const cancelled=harness(undefined,{repeat:false,onComplete:()=>completed++});
  cancelled.rotation.start();await settle();cancelled.rotation.destroy();await cancelled.advance(80000);
  equal(completed,1,'Cancellation is not a completed results pass');
  const stale=harness();stale.rotation.start(0);stale.rotation.jump(2);await settle();
  equal(stale.plays,[2],'Superseded start cannot launch stale audio');stale.rotation.destroy();
  await stale.advance(30000);equal(stale.plays,[2],'Exit leaves no future playback');
}
(async()=>{allocations();await rotationTests();console.log(`Spotlight core: ${checks} assertions passed.`);})()
  .catch(error=>{console.error(error);process.exitCode=1;});
