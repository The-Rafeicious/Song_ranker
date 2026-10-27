/* Shared game controls, pacing and visual tournament bracket presentation. */
window.GameplayUI = (() => {
  "use strict";
  const { $, $$, esc } = window.SongRankerUI;
  let opened = null,
    letters = "",
    letterTimer;
  function select(id, label, options, value) {
    const selected = options.find((o) => o.value === value) || options[0];
    return `<div class="game-select" data-game-select="${esc(id)}"><span id="${id}-label" class="game-control-label">${esc(label)}</span><select id="${id}" hidden tabindex="-1" aria-label="${esc(label)}">${options.map((o) => `<option value="${esc(o.value)}" ${o.value === selected.value ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select><button type="button" class="game-select-trigger" aria-haspopup="listbox" aria-expanded="false" aria-controls="${id}-menu" aria-labelledby="${id}-label ${id}-value"><span id="${id}-value">${esc(selected.label)}</span><span aria-hidden="true">⌄</span></button><div class="game-select-menu" id="${id}-menu" role="listbox" aria-labelledby="${id}-label" hidden>${options.map((o) => `<button type="button" role="option" tabindex="-1" aria-selected="${o.value === selected.value}" data-game-option="${esc(o.value)}"><span><b>${esc(o.label)}</b>${o.detail ? `<small>${esc(o.detail)}</small>` : ""}</span><span class="game-select-check" aria-hidden="true">✓</span></button>`).join("")}</div></div>`;
  }
  function close(focus = false) {
    if (!opened) return;
    const root = opened;
    opened = null;
    $(".game-select-menu", root).hidden = true;
    $(".game-select-trigger", root).setAttribute("aria-expanded", "false");
    root.classList.remove("opens-up");
    clearTimeout(letterTimer);
    letters = "";
    if (focus) $(".game-select-trigger", root).focus();
  }
  function open(root) {
    close();
    opened = root;
    const menu = $(".game-select-menu", root),
      trigger = $(".game-select-trigger", root);
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    const rect = trigger.getBoundingClientRect(),
      below = window.innerHeight - rect.bottom - 12;
    const up = below < Math.min(menu.scrollHeight, 260) && rect.top > below;
    root.classList.toggle("opens-up", up);
    menu.style.bottom = up
      ? root.getBoundingClientRect().bottom - rect.top + 8 + "px"
      : "auto";
    menu.style.maxHeight =
      Math.max(60, Math.min(360, up ? rect.top - 12 : below)) + "px";
    $('[aria-selected="true"]', menu)?.focus();
  }
  function choose(option) {
    const root = option.closest(".game-select"),
      control = $("select", root);
    control.value = option.dataset.gameOption;
    $(".game-select-trigger > span", root).textContent = $(
      "b",
      option,
    ).textContent;
    $$('[role="option"]', root).forEach((o) =>
      o.setAttribute("aria-selected", String(o === option)),
    );
    close(true);
    control.dispatchEvent(new Event("change", { bubbles: true }));
  }
  document.addEventListener("click", (event) => {
    const root = event.target.closest(".game-select");
    if (!root) {
      close();
      return;
    }
    const option = event.target.closest("[data-game-option]");
    if (option) choose(option);
    else if (event.target.closest(".game-select-trigger"))
      opened === root ? close() : open(root);
  });
  document.addEventListener("keydown", (event) => {
    const root = event.target.closest(".game-select");
    if (!root) return;
    const options = $$('[role="option"]', root),
      at = options.indexOf(document.activeElement);
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
      return;
    }
    if (event.key === "Tab") {
      if (opened) close(true);
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      if (opened !== root) {
        open(root);
        return;
      }
      const index =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? options.length - 1
            : (at + (event.key === "ArrowUp" ? -1 : 1) + options.length) %
              options.length;
      options[index]?.focus();
      return;
    }
    if (opened !== root) return;
    if ((event.key === "Enter" || event.key === " ") && at >= 0) {
      event.preventDefault();
      choose(options[at]);
      return;
    }
    if (
      event.key.length === 1 &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey
    ) {
      event.preventDefault();
      clearTimeout(letterTimer);
      letters += event.key.toLocaleLowerCase();
      const after = [...options.slice(at + 1), ...options.slice(0, at + 1)];
      let next = after.find((o) =>
        $("b", o).textContent.toLocaleLowerCase().startsWith(letters),
      );
      if (!next) {
        letters = event.key.toLocaleLowerCase();
        next = after.find((o) =>
          $("b", o).textContent.toLocaleLowerCase().startsWith(letters),
        );
      }
      next?.focus();
      letterTimer = setTimeout(() => (letters = ""), 700);
    }
  });
  document.addEventListener("focusout", (event) => {
    if (opened && !opened.contains(event.relatedTarget)) close();
  });
  window.addEventListener("resize", () => close());
  window.addEventListener("pagehide", () => close());
  return Object.freeze({ select, close });
})();

/* Shared result pacing and one speculative JSON question. No scoring or audio. */
window.RoundFlow = (() => {
  "use strict";
  const key = "songRankerPlaySettings",
    TTL = 60000,
    clock = () => performance.now();
  const durations = {
    pairResult: [4500, 2200],
    tournamentPoints: [2800, 1600],
    tournamentFirst: [7500, 4400],
    triviaResult: [5500, 2800],
    guessClip: [2800, 1700],
    shelfClose: [420, 160],
    shelfTrack: [2600, 1000],
    shelfTransfer: [1250, 450],
    score: [1100, 320],
    triviaFlip: [1550, 600],
  };
  let settings = { pace: "standard", prepare: true },
    entry = null,
    closed = false;
  const timers = new Set(),
    aborted = () =>
      Object.assign(Error("Next round cancelled"), { name: "AbortError" });
  function parse(value) {
    try {
      const s = JSON.parse(value);
      return {
        pace: s?.pace === "quick" ? "quick" : "standard",
        prepare: s?.prepare !== false,
      };
    } catch {
      return { pace: "standard", prepare: true };
    }
  }
  try {
    settings = parse(localStorage.getItem(key));
  } catch {}
  const duration = (name) =>
    durations[name]?.[settings.pace === "quick" ? 1 : 0] ?? 0;
  function paint() {
    document.documentElement.dataset.roundPace = settings.pace;
    document.documentElement.dataset.roundPaused = String(document.hidden);
    const pace = document.getElementById("round-pace"),
      prepare = document.getElementById("round-prepare"),
      label = document.getElementById("round-pace-label");
    if (pace) pace.value = settings.pace;
    if (prepare) prepare.checked = settings.prepare;
    if (label)
      label.textContent = settings.pace === "quick" ? "Quick" : "Standard";
    const toggle = document.querySelector(".game-settings > summary");
    if (toggle) {
      toggle.title =
        "Result speed: " + (settings.pace === "quick" ? "Quick" : "Standard");
      toggle.setAttribute("aria-label", toggle.title);
    }
  }
  function clear() {
    if (entry) {
      entry.cancelled = true;
      clearTimeout(entry.timeout);
      entry.controller.abort();
      entry = null;
    }
  }
  function update(next, persist = true) {
    settings = parse(JSON.stringify({ ...settings, ...next }));
    if (!settings.prepare && entry && !entry.consumed) clear();
    if (persist)
      try {
        localStorage.setItem(key, JSON.stringify(settings));
      } catch {}
    paint();
  }
  function permitted() {
    return (
      !closed &&
      !document.hidden &&
      settings.prepare &&
      navigator.onLine !== false &&
      !navigator.connection?.saveData &&
      !/^(slow-)?2g$/.test(navigator.connection?.effectiveType || "")
    );
  }
  function create(name, load, quiet) {
    clear();
    const job = {
      name,
      quiet,
      consumed: false,
      at: clock(),
      controller: new AbortController(),
      cancelled: false,
    };
    entry = job;
    job.timeout = setTimeout(() => job.controller.abort(), 12000);
    job.promise = Promise.resolve()
      .then(() => {
        if (job.cancelled || closed) throw aborted();
        return load(job.controller.signal);
      })
      .then((value) => {
        if (job.cancelled || closed) throw aborted();
        job.at = clock();
        return value;
      })
      .catch((error) => {
        if (job.controller.signal.aborted && !job.cancelled && !closed)
          throw Error(
            "Loading the next round timed out. Retry when the connection is ready.",
          );
        throw error;
      })
      .finally(() => clearTimeout(job.timeout));
    job.promise.catch(() => {
      if (entry === job) entry = null;
    });
    return job;
  }
  function prepare(name, load) {
    if (!permitted() || entry?.consumed) return;
    if (entry?.name === name && !entry.cancelled && clock() - entry.at < TTL)
      return;
    const job = create(name, load, true);
    job.promise.catch(() => {});
  }
  async function take(name, load) {
    if (closed) throw aborted();
    let job =
      entry?.name === name && !entry.cancelled && clock() - entry.at < TTL
        ? entry
        : create(name, load, false);
    job.consumed = true;
    try {
      return await job.promise;
    } catch (error) {
      if (!job.quiet || closed) throw error;
      job = create(name, load, false);
      job.consumed = true;
      return await job.promise;
    } finally {
      if (entry === job) entry = null;
    }
  }
  function after(callback, ms) {
    const task = { left: Math.max(0, ms), started: 0, id: null, cancel: null };
    task.cancel = () => {
      clearTimeout(task.id);
      task.id = null;
      timers.delete(task);
    };
    task.resume = () => {
      if (closed || document.hidden || task.id !== null || !timers.has(task))
        return;
      task.started = clock();
      task.id = setTimeout(() => {
        task.cancel();
        callback();
      }, task.left);
    };
    task.pause = () => {
      if (task.id !== null) {
        clearTimeout(task.id);
        task.id = null;
        task.left = Math.max(0, task.left - (clock() - task.started));
      }
    };
    timers.add(task);
    task.resume();
    return task.cancel;
  }
  function positionSettings() {
    const settings = document.querySelector(".game-settings");
    if (!settings?.open) return;
    const panel = settings.querySelector(".game-settings-body"),
      rect = settings.querySelector("summary").getBoundingClientRect();
    if (!panel) return;
    const width = Math.min(300, innerWidth - 24),
      top = Math.max(12, rect.bottom + 10);
    Object.assign(panel.style, {
      width: width + "px",
      left:
        Math.max(12, Math.min(rect.right - width, innerWidth - width - 12)) +
        "px",
      top: top + "px",
      maxHeight: Math.max(80, innerHeight - top - 12) + "px",
    });
  }
  document.addEventListener(
    "toggle",
    (e) => {
      if (e.target.matches?.(".game-settings")) positionSettings();
    },
    true,
  );
  window.addEventListener("resize", positionSettings);
  window.addEventListener("scroll", positionSettings, { passive: true });
  document.addEventListener("click", (e) => {
    const settings = document.querySelector(".game-settings");
    if (settings?.open && !settings.contains(e.target)) settings.open = false;
  });
  document.addEventListener(
    "keydown",
    (e) => {
      const settings = document.querySelector(".game-settings");
      if (e.key === "Escape" && settings?.open) {
        e.preventDefault();
        e.stopPropagation();
        settings.open = false;
        settings.querySelector("summary").focus();
      }
    },
    true,
  );
  document.addEventListener("change", (e) => {
    if (e.target.id === "round-pace") update({ pace: e.target.value });
    if (e.target.id === "round-prepare") update({ prepare: e.target.checked });
  });
  window.addEventListener("storage", (e) => {
    if (e.key === key) {
      settings = parse(e.newValue);
      if (!settings.prepare && entry && !entry.consumed) clear();
      paint();
    }
  });
  document.addEventListener("visibilitychange", () => {
    paint();
    if (document.hidden) {
      if (entry && !entry.consumed) clear();
      for (const task of timers) task.pause();
    } else for (const task of timers) task.resume();
  });
  window.addEventListener("pagehide", () => {
    closed = true;
    clear();
    for (const task of [...timers]) task.cancel();
  });
  window.addEventListener("pageshow", () => {
    closed = false;
    paint();
  });
  paint();
  return Object.freeze({ duration, prepare, take, after, clear });
})();

/* One visual tournament tree for saved brackets and the post-game replay. */
window.TournamentBracket = (() => {
  "use strict";
  const {esc} = window.SongRankerUI;
  let activeReplay = null, mapInstance = 0;
  const label = (size, round) => ({2:"Final",4:"Semi-finals",8:"Quarter-finals"}[size / 2 ** (round - 1)] || "Round of " + size / 2 ** (round - 1));
  function replayOrder(matches, size) {
    const final = Math.log2(size), regular = matches.filter(m=>m.match_type !== "third_place");
    const result=[];
    for (const side of [0,1]) for (let round=1;round<final;round++) {
      const half=size / 2 ** round / 2;
      result.push(...regular.filter(m=>m.round_number===round && (m.match_number>half?1:0)===side).sort((a,b)=>a.match_number-b.match_number));
    }
    return result.concat(matches.filter(m=>m.match_type==="third_place"),regular.filter(m=>m.round_number===final));
  }
  function soundtrack(data) {
    const round=Math.max(1,Math.log2(data.tournament.size)-1), ids=[];
    for(const m of [...data.matches].sort((a,b)=>a.match_number-b.match_number)) if(m.round_number===round && m.match_type!=="third_place") for(const id of [m.song1_id,m.song2_id]) if(id && !ids.includes(id)) ids.push(id);
    return ids.slice(0,4);
  }
  function mount(root,data,options={}) {
    const instance=++mapInstance, size=Number(data.tournament.size), rounds=Math.log2(size);
    if(![8,16,32].includes(size)){root.textContent="This saved bracket has an unsupported size.";return {cancel(){}};}
    const tracks=new Map(data.entries.map(s=>[Number(s.id),s])), byKey=new Map(data.matches.filter(m=>m.match_type!=="third_place").map(m=>[`${m.round_number}:${m.match_number}`,m]));
    const height=Math.max(480,size/4*160), width=2*(rounds-1)*260+292, shown=new Set(), order=replayOrder(data.matches,size).filter(m=>m.status==="completed"), playlist=soundtrack(data);
    let completed=false, timer=null, index=0, closed=false, playing=false, revealing=!!options.animate, lastRevealed=null, selected=null, selectedMatch=null, sound=options.sound!==false, cue=null, audio=null, serial=0;
    const failed=new Set(), tails=new Set();
    const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if(!options.animate || reduced) order.forEach(m=>shown.add(m.id));
    root.innerHTML=`<div class="bracket-toolbar"><span class="bracket-hint">Drag to explore · Select a track for details</span><div class="bracket-actions"><button type="button" class="btn tournament" data-map-replay>Replay</button><button type="button" class="btn" data-map-sound aria-pressed="${sound}">Sound ${sound?'on':'off'}</button><button type="button" class="btn" data-map-skip>${options.onDone?'Skip to podium':'Show results'}</button></div><p class="bracket-status" role="status" aria-live="polite"></p></div><div class="bracket-viewport" tabindex="0" aria-label="Tournament bracket; scroll or click and drag to explore rounds"><div class="bracket-canvas" style="width:${width}px;height:${height+65}px"><svg class="bracket-lines" width="${width}" height="${height}" aria-hidden="true"></svg><div class="bracket-nodes"></div></div></div>`;
    const viewport=root.querySelector('.bracket-viewport'), canvas=root.querySelector('.bracket-canvas'), nodes=root.querySelector('.bracket-nodes'), svg=root.querySelector('svg'), status=root.querySelector('.bracket-status');
    const workspace=root.id==='tournament-replay'||root.hasAttribute('data-tournament-map');
    function releaseClip(clip){if(!clip)return;window.PreviewPlayback?.abandon?.(clip);clip.pause();if(window.PreviewPlayback?.release)window.PreviewPlayback.release(clip);else clip.remove();}
    function stopSound(){serial++;releaseClip(audio);audio=null;tails.forEach(releaseClip);tails.clear();cue=null;}
    function playCue(side){
      if(!sound||closed||document.hidden)return;
      const available=playlist.filter(id=>!failed.has(id)&&tracks.get(id)?.audio_url), pool=available.filter(id=>(playlist.indexOf(id)<playlist.length/2?0:1)===side), choices=pool.length?pool:available;
      const id=choices[Math.floor(index/6)%Math.max(1,choices.length)];
      if(id===cue)return;
      const track=tracks.get(id);if(!track?.audio_url)return;
      // Keep one outgoing clip alive until the shared ready-only crossfade starts.
      tails.forEach(releaseClip);tails.clear();
      if(audio){tails.add(audio);window.PreviewPlayback?.retire?.(audio);}
      cue=id; const token=++serial;audio=document.createElement('audio');audio.id='bracket-map-audio';audio.preload='none';audio.src=window.PreviewPlayback?.source(id,track.audio_url)||track.audio_url;audio.loop=false;root.append(audio);
      const current=audio;
      current.addEventListener('timeupdate',()=>{if(!closed&&audio===current&&current.currentTime>=6)current.currentTime=0;});
      current.addEventListener('ended',()=>{if(!closed&&audio===current&&sound){current.currentTime=0;window.PreviewPlayback?.play(current).catch(()=>{if(audio===current)stopSound();});}});
      Promise.resolve(window.PreviewPlayback?.play(current)).then(()=>{if(closed||token!==serial)current.pause();}).catch(error=>{if(token===serial){failed.add(id);stopSound();if(['PreviewBlockedError','NotAllowedError'].includes(error.name))blocked();}});
    }
    function participant(m,slot){
      if(m?.[slot])return m[slot];
      if(!m || m.round_number===1)return null;
      const parent=byKey.get(`${m.round_number-1}:${(m.match_number-1)*2+(slot==='song1_id'?1:2)}`);
      return parent&&shown.has(parent.id)?parent.winner_id:null;
    }
    function position(round,n,bronze=false){
      const pad=Math.max(0,(viewport.clientHeight-height)/2);
      if(round===rounds)return {x:(width-(bronze?212:260))/2,y:pad+height/2+(bronze?115:-80),w:bronze?212:260};
      const half=size/2**round/2, side=n>half, local=side?n-half:n;
      return {x:side?width-228-(round-1)*260:(round-1)*260+16,y:pad+(local-.5)*height/half-63,w:212};
    }
    function pan(round,n,bronze=false){const p=position(round,n,bronze);viewport.scrollTo?.({left:Math.max(0,p.x+p.w/2-viewport.clientWidth/2),top:Math.max(0,p.y-viewport.clientHeight/2+63),behavior:reduced?'instant':'smooth'});}
    function inspection(){
      const song=tracks.get(selected), appearances=data.matches.filter(m=>shown.has(m.id)&&(m.song1_id===selected||m.song2_id===selected)), wins=appearances.filter(m=>m.winner_id===selected).length, eliminated=appearances.find(m=>m.loser_id===selected&&m.match_type!=='third_place'), champion=data.matches.find(m=>shown.has(m.id)&&m.round_number===rounds&&m.match_type!=='third_place')?.winner_id===selected, points=appearances.filter(m=>m.winner_id===selected).reduce((n,m)=>Number.isFinite(m.points_awarded)?n+m.points_awarded:NaN,0);
      return `<section class="bracket-inspector" id="bracket-detail-${instance}-${selectedMatch}" aria-label="Selected track details"><div class="bracket-detail-heading"><strong class="song">${esc(song?.title||'Track unavailable')}</strong><button type="button" class="btn" data-map-close aria-label="Close match details">Close</button></div><span>${esc(song?.artist||'')} · ${wins} wins · ${appearances.filter(m=>m.status==='completed').length} played matches · ${Number.isFinite(points)?points.toFixed(2)+' points':'Points unavailable'}</span><span>${champion?'Champion':eliminated?'Eliminated · '+label(size,eliminated.round_number):'Saved progress'}</span><a class="song" href="/song/${selected}">Open song ↗</a><ol class="bracket-match-details">${appearances.map(m=>`<li>${m.match_type==='third_place'?'Third place':label(size,m.round_number)} · ${m.status==='completed'?(m.winner_id===selected?'Won':'Lost'):'Pending'} vs ${esc(tracks.get(m.song1_id===selected?m.song2_id:m.song1_id)?.title||'Track unavailable')}${Number.isFinite(m.points_awarded)?' · '+m.points_awarded+' points to winner':''}</li>`).join('')}</ol></section>`;
    }
    function closeInspection(){const id=selected,match=selectedMatch;selected=null;selectedMatch=null;draw();nodes.querySelector(`[data-map-match="${match}"] [data-map-track="${id}"]`)?.focus({preventScroll:true});}
    function draw(){
      let html='', paths='';
      canvas.style.height=Math.max(height+(selectedMatch?440:65),viewport.clientHeight)+'px';svg.setAttribute('height',Math.max(height,viewport.clientHeight));
      const cells=[];
      for(let round=1;round<=rounds;round++)for(let n=1;n<=size/2**round;n++)cells.push({round,n,saved:byKey.get(`${round}:${n}`)});
      const bronze=data.matches.find(m=>m.match_type==='third_place');
      if(bronze)cells.push({round:rounds,n:1,saved:bronze,bronze:true});
      for(const cell of cells){
          const {round,n,saved,bronze}=cell, m=saved||{round_number:round,match_number:n}, resolved=saved&&shown.has(saved.id), {x,y,w}=position(round,n,bronze);
          const progress=bronze ? .65 : (round-1)/(rounds-1), tone=`--round-light:${38+62*progress}%;--round-halo:${4+22*progress}%;--round-radius:${6+22*progress}px`, open=String(saved?.id)===selectedMatch;
          if(round<rounds){const next=position(round+1,Math.ceil(n/2)),right=n>size/2**round/2,from=right?x:x+w,to=right?next.x+next.w:next.x,mid=(from+to)/2;paths+=`<path style="${tone}" class="${resolved?'bracket-line-done':''}" d="M${from},${y+63} H${mid} V${next.y+63} H${to}"/>`;}
          html+=`<article class="bracket-node ${open?'has-details':''} ${x>width/2?'is-right':''} ${round===rounds&&!bronze?'bracket-final':''} ${bronze?'bracket-third':''} ${resolved?'is-resolved':''} ${resolved&&saved.id===lastRevealed?'is-advancing':''}" data-map-match="${saved?.id||''}" style="${tone};left:${x}px;top:${y}px;width:${w}px"><small>${bronze?'Third place':label(size,round)+' · '+n}</small>`;
          for(const [slot,side] of [['song1_id',0],['song2_id',1]]){
            let id=participant(m,slot);
            // An advancing identity only appears after its feeder has resolved.
            if(round>1&&revealing&&!reduced&&(bronze?![1,2].every(n=>shown.has(byKey.get(`${rounds-1}:${n}`)?.id)):!shown.has(byKey.get(`${round-1}:${(n-1)*2+side+1}`)?.id)))id=null;
            const hidden=data.tournament.is_blind&&data.tournament.status!=='completed'&&!resolved, song=tracks.get(Number(id));
            const name=hidden?'Hidden track':song?.title||(id?'Track unavailable':'Awaiting winner'), won=resolved&&m.winner_id===id, lost=resolved&&m.loser_id===id;
            html+=`<button type="button" class="bracket-track ${won?'is-winner':''} ${lost?'is-eliminated':''} ${id&&id===selected?'is-route':''}" data-map-track="${hidden||!song?'':id||''}" title="${esc(name)}" aria-pressed="${!!id&&id===selected}" aria-expanded="${open&&id===selected}" ${open&&id===selected?`aria-controls="bracket-detail-${instance}-${selectedMatch}"`:""} aria-label="${esc(name)}, ${won?'Winner':lost?'Eliminated':'Pending'}" ${!id||hidden||!song?'disabled':''}>${!hidden&&song?.cover_url?`<img src="${esc(song.cover_url)}" alt="" loading="lazy">`:""}<span>${esc(name)}</span><b>${won?'✓':lost?'×':'·'}</b></button>`;
          }
          if(open)html+=inspection();
          html+='</article>';
      }
      nodes.innerHTML=html;svg.innerHTML=paths;lastRevealed=null;
    }
    function halt(keepAudio=false){playing=false;clearTimeout(timer);if(!keepAudio)stopSound();if(activeReplay===halt)activeReplay=null;}
    function finish(soft=false){
      if(closed||completed)return;completed=true;halt(soft);revealing=false;order.forEach(m=>shown.add(m.id));draw();
      const done=()=>{timer=null;if(closed)return;stopSound();root.querySelector('[data-map-replay]').textContent='Replay';status.textContent=data.tournament.status==='completed'?'Bracket complete':'Saved results';if(options.onDone)options.onDone({sound:sound&&!reduced});};
      if(soft&&audio&&window.PreviewPlayback?.fadeOut){window.PreviewPlayback.fadeOut(audio,600);tails.forEach(a=>window.PreviewPlayback.fadeOut(a,600));timer=setTimeout(done,650);}else done();
    }

    function step(){
      if(closed||!playing)return;
      if(document.hidden){stopSound();timer=setTimeout(step,500);return;}
      const m=order[index++];if(!m){finish(true);return;}
      shown.add(m.id);lastRevealed=m.id;draw();status.textContent=`${label(size,m.round_number)} · ${index} / ${order.length} results`;
      const half=size/2**m.round_number/2, side=m.match_number>half?1:0;playCue(side);
      pan(m.round_number,m.match_number,m.match_type==='third_place');
      timer=setTimeout(step,options.stepMs||3500);
    }
    function replay(){if(closed)return;selected=null;selectedMatch=null;completed=false;activeReplay?.();activeReplay=halt;clearTimeout(timer);stopSound();if(reduced||!order.length){order.forEach(m=>shown.add(m.id));draw();queueMicrotask(finish);return;}shown.clear();index=0;playing=true;revealing=true;root.querySelector('[data-map-replay]').textContent='Restart';draw();step();}

    function handleClick(event){if(closed)return;
      const button=event.target.closest('button');if(!button)return;
      if(button.hasAttribute('data-map-replay'))replay();
      if(button.hasAttribute('data-map-sound')){sound=!sound;button.textContent='Sound '+(sound?'on':'off');button.setAttribute('aria-pressed',String(sound));if(!sound)stopSound();else if(playing)playCue(0);}
      if(button.hasAttribute('data-map-skip'))finish();
      if(button.hasAttribute('data-map-close')){closeInspection();return;}
      if(button.dataset.mapTrack){
        if(playing){halt();status.textContent='Paused · Restart to replay';}
        const matchId=button.closest('[data-map-match]')?.dataset.mapMatch, id=Number(button.dataset.mapTrack);
        if(selected===id&&selectedMatch===matchId){closeInspection();return;}
        selected=id;selectedMatch=matchId;draw();
        const node=nodes.querySelector(`[data-map-match="${matchId}"]`), detail=node?.querySelector('.bracket-inspector');
        node?.querySelector(`[data-map-track="${id}"]`)?.focus({preventScroll:true});
        if(detail){const x=parseFloat(node.style.left)+detail.offsetLeft;viewport.scrollTo?.({left:Math.max(0,x+detail.offsetWidth/2-viewport.clientWidth/2),top:Math.max(0,parseFloat(node.style.top)-16),behavior:reduced?'instant':'smooth'});}
      }
    }
    // Mouse/pen panning leaves native touch scrolling and keyboard navigation intact.
    let drag=null, suppressClick=false;
    function pointerDown(event){if(event.button!==0||event.pointerType==='touch'||event.target.closest('.bracket-inspector'))return;drag={id:event.pointerId,x:event.clientX,y:event.clientY,left:viewport.scrollLeft,top:viewport.scrollTop,moved:false};suppressClick=false;}
    function pointerMove(event){if(!drag||event.pointerId!==drag.id)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(!drag.moved&&Math.hypot(dx,dy)<6)return;if(!drag.moved){drag.moved=true;if(playing){halt();status.textContent='Paused · Restart to replay';}viewport.setPointerCapture?.(drag.id);viewport.classList.add('is-dragging');}event.preventDefault();viewport.scrollLeft=drag.left-dx;viewport.scrollTop=drag.top-dy;}
    function pointerUp(event){if(!drag||event.pointerId!==drag.id)return;suppressClick=drag.moved&&event.type==='pointerup';const id=drag.id;drag=null;viewport.classList.remove('is-dragging');if(viewport.hasPointerCapture?.(id))viewport.releasePointerCapture(id);}
    function dragClick(event){if(suppressClick){suppressClick=false;event.preventDefault();event.stopImmediatePropagation();}}
    function preventImageDrag(event){event.preventDefault();}
    viewport.addEventListener('pointerdown',pointerDown);viewport.addEventListener('pointermove',pointerMove);viewport.addEventListener('pointerup',pointerUp);viewport.addEventListener('pointercancel',pointerUp);viewport.addEventListener('lostpointercapture',pointerUp);viewport.addEventListener('click',dragClick,true);viewport.addEventListener('dragstart',preventImageDrag);
    function keyDown(event){if(event.key==='Escape'&&selectedMatch){event.preventDefault();closeInspection();}}
    root.addEventListener('keydown',keyDown);
    function fit(){
      if(closed||!workspace)return;
      const footer=document.querySelector('.footer'), top=viewport.getBoundingClientRect().top+window.scrollY, available=Math.max(300,window.innerHeight-top-(footer?.getBoundingClientRect().height||0));
      if(root.style.getPropertyValue('--bracket-view-height')===available+'px')return;
      const focused=document.activeElement, track=focused?.dataset.mapTrack, match=focused?.closest('[data-map-match]')?.dataset.mapMatch, close=focused?.hasAttribute('data-map-close');
      root.style.setProperty('--bracket-view-height',available+'px');draw();
      if(track)nodes.querySelector(`[data-map-match="${match}"] [data-map-track="${track}"]`)?.focus({preventScroll:true});else if(close)nodes.querySelector('[data-map-close]')?.focus({preventScroll:true});
    }
    window.addEventListener('resize',fit);
    const observer=workspace&&window.ResizeObserver?new ResizeObserver(fit):null;
    for(const node of [document.querySelector('.navbar'),document.querySelector('.footer'),root.querySelector('.bracket-toolbar'),document.querySelector('.bracket-page-header')])if(node)observer?.observe(node);
    root.addEventListener('click',handleClick);
    function visibility(){if(document.hidden)stopSound();}
    function blocked(){sound=false;stopSound();const button=root.querySelector('[data-map-sound]');button.textContent='Sound off';button.setAttribute('aria-pressed','false');}
    const cancel=()=>{closed=true;halt();observer?.disconnect();window.removeEventListener('resize',fit);root.removeEventListener('keydown',keyDown);drag=null;viewport.classList.remove('is-dragging');viewport.removeEventListener('pointerdown',pointerDown);viewport.removeEventListener('pointermove',pointerMove);viewport.removeEventListener('pointerup',pointerUp);viewport.removeEventListener('pointercancel',pointerUp);viewport.removeEventListener('lostpointercapture',pointerUp);viewport.removeEventListener('click',dragClick,true);viewport.removeEventListener('dragstart',preventImageDrag);root.removeEventListener('click',handleClick);document.removeEventListener('visibilitychange',visibility);document.removeEventListener('preview-blocked',blocked);window.removeEventListener('pagehide',pauseForPage);};
    function pauseForPage(){const wasPlaying=playing;halt();if(wasPlaying)status.textContent='Paused · Restart to replay';}
    window.addEventListener('pagehide',pauseForPage);
    document.addEventListener('visibilitychange',visibility);
    document.addEventListener('preview-blocked',blocked);
    draw();status.textContent=data.tournament.status==='completed'?'Completed bracket':'Saved bracket progress';
    fit();pan(rounds,1);
    if(options.animate)replay();
    return {cancel};
  }
  document.addEventListener('DOMContentLoaded',()=>{
    for(const root of document.querySelectorAll('[data-tournament-map]')){
      const start=()=>{if(root.dataset.mounted)return;root.dataset.mounted='true';mount(root,JSON.parse(document.getElementById(root.dataset.tournamentMap).textContent));root.parentElement.querySelector('.ts-bracket-fallback')?.setAttribute('hidden','');};
      const details=root.closest('details');if(!details||details.open)start();details?.addEventListener('toggle',()=>{if(details.open)start();});
    }
  });
  return Object.freeze({mount,replayOrder,soundtrack});
})();
