/* Relative placements become the existing 12-point receipt; no stored coordinates. */
((scope) => {
  'use strict';
  const splits = [];
  for (let a = 0; a <= 12; a++) for (let b = 0; b <= 12-a; b++)
    for (let c = 0; c <= 12-a-b; c++) splits.push([a, b, c, 12-a-b-c]);

  function allocate(positions) {
    if (!Array.isArray(positions) || positions.length !== 4 ||
        !Array.from(positions).every(x => Number.isInteger(x) && x >= 0 && x <= 100)) return null;
    const mean = positions.reduce((a, b) => a+b, 0)/4;
    const targets = positions.map(x => 3 + 12*(x-mean)/100);
    const order = [0, 1, 2, 3].sort((a, b) => positions[b]-positions[a]);
    let best, bestError = Infinity;
    for (const split of splits) {
      if (order.some((slot, i) => i && (positions[order[i-1]] === positions[slot] ?
          split[order[i-1]] !== split[slot] : split[order[i-1]] < split[slot]))) continue;
      const error = split.reduce((sum, points, i) => sum + (points-targets[i])**2, 0);
      // Exact-cost rounding ties favour the better position, independently of card order.
      const firstDifference = best && order.find(i => split[i] !== best[i]);
      if (error < bestError-1e-9 || (Math.abs(error-bestError) < 1e-9 &&
          firstDifference !== undefined && split[firstDifference] > best[firstDifference])) {
        best = split;bestError = error;
      }
    }
    return [...best];
  }

  function resultOrder(points) {
    return [0,1,2,3].sort((a,b) => points[b]-points[a] || a-b);
  }
  function resultPositions(points) {
    const levels = [...new Set(points)].sort((a,b) => a-b);
    return points.map(value => levels.length === 1 ? 50 : 100*levels.indexOf(value)/(levels.length-1));
  }

  function createRotation({players, play, stop, duration, onState = () => {}, onError = () => {},
      repeat = true, onComplete = () => {},
      schedule = (fn, ms) => setTimeout(fn, ms), cancel = id => clearTimeout(id), now = () => performance.now()}) {
    let active = false, index = 0, serial = 0, timer, heard = 0, started = null, failures = 0;
    const listeners = [];
    function suspend() {
      if (started !== null) heard += Math.max(0, now()-started);
      started = null;cancel(timer);timer = undefined;
    }
    function stopRotation(pause = true) {
      active = false;serial++;suspend();
      if (pause) stop();
      onState(false, index);
    }
    function finish() {stopRotation();onComplete();}
    function advance() {
      if (!active) return;
      if (!repeat && index === players.length-1) finish();
      else jump((index+1)%players.length);
    }
    function failed(error, version) {
      if (!active || version !== serial) return;
      onError(error, index);
      if (error?.name === 'NotAllowedError' || ++failures >= players.length) finish();
      else advance();
    }
    function resume() {
      if (!active || players[index].paused || started !== null) return;
      started = now();
      timer = schedule(advance, Math.max(0, duration()-heard));
    }
    function jump(slot) {
      if (!active || !Number.isInteger(slot) || !players[slot]) return;
      const version = ++serial;
      suspend();stop();index = slot;heard = 0;
      onState(true, index);
      try {players[index].currentTime = 0;} catch {}
      Promise.resolve().then(() => {
        if (!active || version !== serial) return;
        return play(players[index]);
      }).then(() => {if (active && version === serial) resume();})
        .catch(error => failed(error, version));
    }
    players.forEach((audio, slot) => {
      const add = (event, fn) => {audio.addEventListener(event, fn);listeners.push(() => audio.removeEventListener(event, fn));};
      add('playing', () => {if (active && slot === index) {failures = 0;resume();}});
      for (const event of ['pause', 'waiting', 'seeking']) add(event, () => {if (active && slot === index) suspend();});
      add('seeked', () => {if (active && slot === index) resume();});
      add('error', () => {if (active && slot === index) failed(Error('Preview unavailable'), serial);});
    });
    return {
      get active() {return active;}, get index() {return index;},
      start(slot = index) {active = true;failures = 0;jump(slot);}, jump,
      stop: stopRotation,
      paceChanged() {if (active) {suspend();resume();}},
      destroy() {stopRotation();listeners.forEach(remove => remove());}
    };
  }
  const api = Object.freeze({allocate, resultOrder, resultPositions, createRotation});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else scope.Spotlight = api;
})(typeof window === 'undefined' ? globalThis : window);
