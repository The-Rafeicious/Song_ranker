/* Focused subjective games. The server owns offers, selection and saved facts. */
(() => {
  'use strict';
  const root = document.querySelector('[data-judgement-mode]');
  if (!root) return;
  const {$, $$, esc} = window.SongRankerUI;
  const config = JSON.parse($('#judgement-config').textContent), mode = config.mode;
  document.body.dataset.tone = mode;
  const stage = $('#judgement-round'), errorBox = $('#judgement-error');
  const recovery = $('#judgement-recovery'), retry = $('#judgement-retry');
  const flow = window.RoundFlow, playback = window.PreviewPlayback;
  const draftKey = 'songRankerJudgement:' + mode, requests = new Set();
  let round, state = 'loading', generation = 0, closed = false, pending = null;
  let allocations = [0, 0, 0, 0], placements = {}, themes = new Set();
  let positions = [null, null, null, null], selectedSlot = 0, rotation, rotationOrder = [0,1,2,3];
  let selectTimer, selectSerial = 0, dragging = false, placementDirty = false, resultBlocked = false;
  let themesReviewed = false, activeMap = config.maps[0].key, cancelNext, retryKind = 'load';

  async function post(path, payload, signal) {
    const controller = new AbortController(), cancel = () => controller.abort();
    requests.add(controller);
    signal?.addEventListener('abort', cancel, {once: true});
    if (signal?.aborted) controller.abort();
    const timer = setTimeout(cancel, 12000);
    try {
      const response = await fetch(path, {method: 'POST', credentials: 'same-origin',
        cache: 'no-store', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload), signal: controller.signal});
      let data;
      try { data = await response.json(); }
      catch { throw Error('The server response could not be read. Please retry.'); }
      if (!response.ok) throw Object.assign(Error(data.message || 'The request could not be saved.'), {status: response.status});
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw Error('The request timed out. Please retry.');
      throw error;
    } finally {
      clearTimeout(timer); requests.delete(controller);
      signal?.removeEventListener('abort', cancel);
    }
  }
  function message(text, kind) {
    errorBox.textContent = text; errorBox.hidden = !text;
    recovery.hidden = !kind; retryKind = kind || 'load';
    retry.textContent = kind === 'save' ? 'Retry same save' : 'Load round';
  }
  function persist() {
    if (!round) return;
    try { sessionStorage.setItem(draftKey, JSON.stringify({token: round.token,
      allocations, positions, selectedSlot, placements, themes: [...themes], themesReviewed, activeMap, pending})); } catch {}
  }
  function restore() {
    let draft;
    try { draft = JSON.parse(sessionStorage.getItem(draftKey)); } catch {}
    if (!draft || draft.token !== round.token) return;
    if (mode === 'spotlight') {
      if (Array.isArray(draft.positions) && draft.positions.length === 4 &&
          draft.positions.every(x => x === null || (Number.isInteger(x) && x >= 0 && x <= 100))) {
        positions = draft.positions;
        allocations = window.Spotlight.allocate(positions, round.rules_version) || [0, 0, 0, 0];
      }
      if (Number.isInteger(draft.selectedSlot) && draft.selectedSlot >= 0 && draft.selectedSlot < 4) selectedSlot = draft.selectedSlot;
      // Old unconfirmed point receipts must still retry exactly as submitted.
      if (Array.isArray(draft.pending?.allocations)) allocations = [...draft.pending.allocations];
    }
    for (const definition of config.maps) {
      const p = draft.placements?.[definition.key];
      if (p && [p.x, p.y].every(n => Number.isInteger(n) && n >= 0 && n <= 4)) placements[definition.key] = {x: p.x, y: p.y};
    }
    themes = new Set((Array.isArray(draft.themes) ? draft.themes : [])
      .filter(id => config.tags.some(t => t.id === id)).slice(0, config.max_themes));
    themesReviewed = draft.themesReviewed === true;
    if (config.maps.some(m => m.key === draft.activeMap)) activeMap = draft.activeMap;
    if (draft.pending?.token === round.token) pending = draft.pending;
  }
  function artwork(song) {
    return `<span class="judgement-cover-art"><span class="judgement-cover-fallback" aria-hidden="true">🎵</span>${song.cover_url ? `<img src="${esc(song.cover_url)}" alt="" onerror="this.hidden=true">` : ''}</span><span class="play-overlay judgement-play-icon" aria-hidden="true">▶</span>`;
  }
  function track(song) {
    const audioId = 'judgement-audio-' + song.slot;
    const artists = song.artists.map(a => `<a class="artist" title="${esc(a.name)}" href="/artist/${encodeURIComponent(a.name)}">${esc(a.name)}</a>`).join(', ');
    // Match Standard Vote: proper albums link by title; Singles/unknown stay out.
    const album = typeof song.album === 'string' ? song.album.trim() : '';
    const properAlbum = album && album.toLocaleLowerCase() !== 'unknown album' && !/\s-\s*single\s*$/i.test(album);
    const albumLink = properAlbum ? `<a class="album judgement-album" title="${esc(album)}" href="/album/${encodeURIComponent(album)}">${esc(album)}</a>` : '';
    const player = `<button type="button" class="cover-button judgement-play" data-judgement-play="${audioId}" aria-label="Play ${esc(song.title)}" aria-pressed="false" data-playing="false">${artwork(song)}</button>`;
    const cover = mode === 'spotlight' ? `<div class="spotlight-cover">${player}<output class="spotlight-points" data-spotlight-points="${song.slot}" hidden aria-label="Track ${song.slot+1} points"><strong>—</strong><span>/ 12</span></output></div>` : player;
    return `${cover}<audio id="${audioId}" data-song-id="${song.id}" src="${esc(playback?.source(song.id, song.audio_url) || song.audio_url)}" preload="none" loop></audio><div class="judgement-track-copy"><a class="song" title="${esc(song.title)}" href="/song/${song.id}">${esc(song.title)}</a><div class="judgement-artists game-artists">${artists}</div>${albumLink}${mode === 'spotlight' ? `<button type="button" class="spotlight-select" data-spotlight-select="${song.slot}" aria-label="Place track ${song.slot+1}: ${esc(song.title)}" aria-pressed="false"><b>${song.slot+1}</b><span class="spotlight-select-state">Place on bar</span></button>` : ''}<span class="judgement-audio-note" role="status"></span></div>`;
  }
  function controls() {
    const left = mode === 'spotlight' ? '<strong id="spotlight-budget" role="status">Place all four songs</strong>' : '<button type="button" class="btn" data-j-skip>Skip</button>';
    return '<div class="judgement-actions">' + left + (mode === 'spotlight' ? '<button type="button" class="btn" data-spotlight-loop aria-pressed="false">Loop previews</button>' : '') + '<button type="button" class="btn judgement-primary" id="judgement-save" disabled>Save</button></div><div id="judgement-result" class="judgement-result" role="status" hidden></div>';
  }
  function render() {
    if (mode === 'spotlight') {
      stage.innerHTML = `<div class="judgement-cards spotlight-cards">${round.songs.map(s => `<article class="panel dashboard-surface judgement-card spotlight-card" data-spotlight-card="${s.slot}" aria-label="Track ${s.slot+1}: ${esc(s.title)}">${track(s)}</article>`).join('')}</div><section class="spotlight-placement" aria-label="Connection with each preview"><span id="spotlight-selected" class="judgement-sr"></span><div class="spotlight-axis-labels"><span>Not connecting</span><span>Some connection</span><span>Really connecting</span></div><div class="spotlight-line-board"><input type="range" id="spotlight-line" min="0" max="100" step="1" value="50" aria-label="Place selected track from not connecting to really connecting" aria-describedby="spotlight-selected"><div class="spotlight-markers">${round.songs.map(s => `<button type="button" class="spotlight-marker" data-spotlight-select="${s.slot}" style="--slot:${s.slot}" aria-label="Select track ${s.slot+1}: ${esc(s.title)}" hidden><span class="spotlight-marker-fallback" aria-hidden="true">🎵</span>${markerArtwork(s)}</button>`).join('')}</div></div></section>${controls()}`;
    } else if (mode === 'vibe') {
      stage.innerHTML = `<div class="vibe-play-layout"><article class="panel dashboard-surface judgement-card vibe-track">${track(round.songs[0])}</article><section class="panel dashboard-surface vibe-workspace"><div class="vibe-tabs" role="tablist" aria-label="Vibe tables">${config.maps.map((m, i) => `<button type="button" role="tab" id="vibe-tab-${m.key}" aria-controls="vibe-panel" aria-selected="${m.key === activeMap}" tabindex="${m.key === activeMap ? 0 : -1}" data-vibe-tab="${m.key}">${esc(['Mood & energy', 'Sound & delivery', 'Build & hook'][i])}<span class="vibe-tab-state" aria-hidden="true"></span></button>`).join('')}</div><div id="vibe-panel" role="tabpanel"></div></section></div><details class="panel vibe-tag-panel"><summary>Tags <span id="vibe-tag-count">Optional</span></summary><div class="vibe-tag-body"><div class="vibe-tag-tools"><label>Find a tag<input id="vibe-tag-search" type="search" placeholder="Search tags and descriptions"></label><button type="button" class="btn" data-theme-none>None fit</button><button type="button" class="btn" data-theme-clear>Clear review</button></div><p class="vibe-tag-status" id="vibe-tag-status" role="status"></p><div class="vibe-tag-list">${config.tags.map(t => `<label class="vibe-tag-option" data-tag-search="${esc((t.name + ' ' + (t.description || '')).toLocaleLowerCase())}" title="${esc(t.description || t.name)}"><input type="checkbox" value="${t.id}" data-theme><span class="tag">${esc(t.name)}</span></label>`).join('') || '<p class="empty">No catalogue tags yet.</p>'}</div><p id="vibe-tags-empty" class="empty" hidden>No matching tags.</p></div></details>${controls()}`;
      renderMap();
    }
    attachAudio();
    if (mode === 'spotlight') setupRotation();
    update();
  }
  function renderMap() {
    const definition = config.maps.find(m => m.key === activeMap), p = placements[activeMap];
    const panel = $('#vibe-panel');
    panel.setAttribute('aria-labelledby', 'vibe-tab-' + activeMap);
    panel.innerHTML = `<div class="vibe-map-head"><h2>${esc(definition.label)}</h2><button type="button" class="btn" data-vibe-clear ${!p ? 'disabled' : ''}>Clear placement</button></div><div class="vibe-y-label">${esc(definition.y.high)} ↑</div><div class="vibe-grid" role="radiogroup" aria-label="${esc(definition.label)}: ${esc(definition.x.label)} across, ${esc(definition.y.label)} upwards">${[4, 3, 2, 1, 0].map(y => [0, 1, 2, 3, 4].map(x => `<button type="button" class="vibe-cell" role="radio" aria-checked="${p?.x === x && p?.y === y}" tabindex="${p ? (p.x === x && p.y === y ? 0 : -1) : (x === 2 && y === 2 ? 0 : -1)}" data-vibe-x="${x}" data-vibe-y="${y}" aria-label="${esc(definition.x.label)} ${x} of 4, ${esc(definition.y.label)} ${y} of 4"><span aria-hidden="true">${p?.x === x && p?.y === y ? '●' : '+'}</span></button>`).join('')).join('')}</div><div class="vibe-y-label">↓ ${esc(definition.y.low)}</div><div class="judgement-axis-ends"><span>${esc(definition.x.low)}</span><span>${esc(definition.x.high)} →</span></div><p id="vibe-placement-status" class="vibe-placement-status" role="status">${p ? `${esc(definition.x.label)} ${p.x} / 4 · ${esc(definition.y.label)} ${p.y} / 4` : 'Not placed'}</p>`;
    updateTabs();
  }
  function updateTabs() {
    $$('[data-vibe-tab]', root).forEach(button => {
      const key = button.dataset.vibeTab, selected = key === activeMap;
      button.setAttribute('aria-selected', selected); button.tabIndex = selected ? 0 : -1;
      $('.vibe-tab-state', button).textContent = placements[key] ? ' ✓' : '';
      button.setAttribute('aria-label', config.maps.find(m => m.key === key).label + (placements[key] ? ', placed' : ', not placed'));
    });
  }
  function valid() {
    return mode === 'spotlight' ? window.Spotlight.allocate(positions, round.rules_version) !== null : Object.keys(placements).length > 0;
  }
  function selectSlot(slot, followAudio = true) {
    if (state !== 'playing' || !Number.isInteger(slot) || slot < 0 || slot > 3) return;
    cancelAutoSelect();selectedSlot = slot;update();
    if (followAudio && rotation?.active) {
      const index = rotationOrder.indexOf(slot);
      if (rotation.index !== index) rotation.jump(index);
    }
  }
  function place(value) {
    if (state !== 'playing') return;
    const x = Number(value);
    if (!Number.isInteger(x) || x < 0 || x > 100) return;
    const changed = positions[selectedSlot] !== x;
    positions[selectedSlot] = x;
    allocations = window.Spotlight.allocate(positions, round.rules_version) || [0, 0, 0, 0];
    update();
    if (changed) {
      placementDirty = true;
      const bar = $('.spotlight-placement');bar.dataset.pulse = bar.dataset.pulse === 'a' ? 'b' : 'a';
      if (!dragging) scheduleAutoSelect();
    }
  }
  function cancelAutoSelect() {clearTimeout(selectTimer);selectTimer = null;selectSerial++;placementDirty = false;}
  function scheduleAutoSelect() {
    clearTimeout(selectTimer);
    const serial = ++selectSerial, slot = selectedSlot, token = round.token;
    selectTimer = setTimeout(() => {
      if (closed || state !== 'playing' || dragging || serial !== selectSerial || slot !== selectedSlot || token !== round.token) return;
      const next = [1,2,3].map(offset => (slot+offset)%4).find(index => positions[index] === null);
      selectSlot(next ?? (slot+1)%4);
    }, 1500);
  }
  function markerArtwork(song) {
    return song.cover_url ? `<img src="${esc(song.cover_url)}" alt="" onerror="this.hidden=true">` : '';
  }
  function layoutMarkers() {
    const result = state === 'saved';
    const locations = result && round.rules_version === 1 ? window.Spotlight.resultPositions(allocations) : positions;
    const width = Math.max(160, ($('#spotlight-line').clientWidth || 600)-28);
    const visible = [];
    $$('.spotlight-marker', root).forEach(button => {
      const slot = Number(button.dataset.spotlightSelect);
      button.hidden = locations[slot] === null;
      if (!button.hidden) visible.push({button, slot, x:width*locations[slot]/100});
      button.title = `${round.songs[slot].title}${result ? ' · '+allocations[slot]+' points' : ''}`;
    });
    visible.sort((a,b) => a.x-b.x || a.slot-b.slot);
    const groups = [];
    for (const item of visible) {
      const group = groups.at(-1);
      if (group && item.x-group.at(-1).x < 48) group.push(item);else groups.push([item]);
    }
    for (const group of groups) {
      const centre = group.reduce((sum,item)=>sum+item.x,0)/group.length;
      const first = Math.max(0,Math.min(width-14*(group.length-1),centre-7*(group.length-1)));
      group.forEach((item,i)=>item.button.style.setProperty('--rest-x',`${first+14*i}px`));
    }
    const expanded = visible.map(item=>item.x);
    for (let i=1;i<expanded.length;i++) expanded[i] = Math.max(expanded[i],expanded[i-1]+52);
    if (expanded.length) {
      let shift = expanded.reduce((sum,x,i)=>sum+x-visible[i].x,0)/expanded.length;
      shift = Math.max(expanded.at(-1)-width,Math.min(expanded[0],shift));
      visible.forEach((item,i)=>item.button.style.setProperty('--fan-x',`${expanded[i]-shift}px`));
    }
  }
  function paintRotation() {
    const button = $('[data-spotlight-loop]', root);
    if (!button) return;
    button.textContent = rotation?.active ? 'Stop previews' : 'Loop previews';
    button.setAttribute('aria-pressed', String(!!rotation?.active));
  }
  function setupRotation() {
    rotation?.destroy();
    rotationOrder = [0,1,2,3];
    rotation = window.Spotlight.createRotation({
      players: rotationOrder.map(slot => document.getElementById('judgement-audio-'+slot)),
      play: audio => playback ? playback.play(audio) : audio.play(),
      stop: () => {if (playback) playback.stopAll();else $$('audio', root).forEach(a => a.pause());},
      duration: () => flow?.duration('spotlightPreview') || 20000,
      onState: (active, index) => {
        if (active && state === 'playing') selectSlot(rotationOrder[index], false);
        paintRotation();
      },
      onError: (error, slot) => {
        const card = $(`[data-spotlight-card="${slot}"]`, root);
        $('.judgement-audio-note', card).textContent = error.name === 'NotAllowedError' ? 'Press play to retry' : 'Preview unavailable';
      }
    });
  }
  function finishSpotlightResults() {
    if (closed || state !== 'saved' || mode !== 'spotlight') return;
    cancelNext?.();
    $$('[data-spotlight-card]',root).forEach(card=>card.classList.remove('is-result-playing'));
    if (flow && !resultBlocked) cancelNext = flow.after(loadRound, flow.duration('spotlightSettle') || 1200);
  }
  function startSpotlightResults() {
    cancelNext?.();cancelNext = null;rotation?.destroy();resultBlocked = false;
    rotationOrder = window.Spotlight.resultOrder(allocations);
    rotation = window.Spotlight.createRotation({
      players: rotationOrder.map(slot=>document.getElementById('judgement-audio-'+slot)),
      play: audio=>playback ? playback.play(audio) : audio.play(),
      stop: ()=>{if (playback) playback.stopAll();else $$('audio',root).forEach(a=>a.pause());},
      duration: ()=>flow?.duration('spotlightResult') || 3500,
      repeat:false,onComplete:finishSpotlightResults,
      onState: (active,index)=>{
        $$('[data-spotlight-card]',root).forEach(card=>card.classList.toggle('is-result-playing',active && Number(card.dataset.spotlightCard)===rotationOrder[index]));
        $$('.spotlight-marker',root).forEach(marker=>marker.classList.toggle('is-result-playing',active && Number(marker.dataset.spotlightSelect)===rotationOrder[index]));
        paintRotation();
      },
      onError: (error,index)=>{
        if (error.name === 'NotAllowedError') resultBlocked = true;
        const note=$('.judgement-audio-note',$(`[data-spotlight-card="${rotationOrder[index]}"]`,root));
        note.textContent=error.name==='NotAllowedError' ? 'Press play to hear preview' : 'Preview unavailable';
      }
    });
    rotation.start(0);
  }
  function update() {
    const save = $('#judgement-save');
    if (!save) return;
    const editable = state === 'playing';root.dataset.phase = state;
    $$('[data-spotlight-select], [data-spotlight-loop], #spotlight-line, [data-vibe-x], [data-vibe-tab], [data-theme], [data-theme-none], [data-theme-clear], [data-j-skip]', root)
      .forEach(button => button.disabled = !editable && !(button.hasAttribute('data-spotlight-loop') && state === 'saved'));
    if (save) {
      save.disabled = !editable || !valid();
      save.textContent = state === 'saving' ? 'Saving…' : mode === 'spotlight' ? 'Next round' :
        `Save ${Object.keys(placements).length || ''} ${Object.keys(placements).length === 1 ? 'map' : 'maps'}`.replace('  ', ' ');
    }
    if (mode === 'spotlight') {
      const ready = valid() || !!pending?.allocations || state === 'saved';
      $('#spotlight-budget').textContent = state === 'saved'
        ? 'Points awarded: ' + allocations.reduce((a,b) => a+b, 0)
        : ready ? 'Ready to save' : 'Place all four songs';
      $$('[data-spotlight-points]', root).forEach(output => {
        const slot = Number(output.dataset.spotlightPoints);
        output.hidden = state !== 'saved';
        $('strong', output).textContent = state === 'saved' ? allocations[slot] : '—';
        output.setAttribute('aria-label', `Track ${slot+1}: ${state === 'saved' ? allocations[slot]+' of 12 points' : 'points hidden until results'}`);
      });
      $$('[data-spotlight-card]', root).forEach(card => card.classList.toggle('is-active', editable && Number(card.dataset.spotlightCard) === selectedSlot));
      $$('[data-spotlight-select]', root).forEach(button => {
        const slot = Number(button.dataset.spotlightSelect), selected = editable && slot === selectedSlot;
        button.setAttribute('aria-pressed', String(selected));
        if (button.classList.contains('spotlight-select')) $('.spotlight-select-state',button).textContent = selected ? 'Selected ✓' : 'Place on bar';
      });
      layoutMarkers();
      const slider = $('#spotlight-line');
      slider.value = positions[selectedSlot] ?? 50;
      slider.setAttribute('aria-valuetext', positions[selectedSlot] === null ? 'Not placed' : `${positions[selectedSlot]} of 100 from not connecting to really connecting`);
      $('#spotlight-selected').textContent = `${selectedSlot+1} · ${round.songs[selectedSlot].title}`;
      paintRotation();
    } else {
      const clear = $('[data-vibe-clear]', root);
      if (clear) clear.disabled = !editable || !placements[activeMap];
      $$('[data-theme]', root).forEach(input => {
        input.checked = themes.has(Number(input.value));
        input.disabled = !editable || (!input.checked && themes.size >= config.max_themes);
      });
      $('#vibe-tag-count').textContent = themesReviewed ? (themes.size ? `${themes.size} selected` : 'None selected') : 'Optional';
      $('#vibe-tag-status').textContent = themesReviewed ? `${themes.size} / ${config.max_themes} selected · tags reviewed` : `Not reviewed · up to ${config.max_themes} tags`;
      updateTabs();
    }
    if (state !== 'saved') persist();
  }
  function attachAudio() {
    $$('audio', root).forEach(audio => {
      playback?.bind(audio);
      const button = $(`[data-judgement-play="${audio.id}"]`, root), note = $('.judgement-audio-note', audio.closest('.judgement-card'));
      const paint = () => {
        const playing = !audio.paused;
        button.setAttribute('aria-pressed', playing);
        button.dataset.playing = String(playing);
        button.setAttribute('aria-label', (playing ? 'Pause ' : 'Play ') + round.songs.find(s => 'judgement-audio-' + s.slot === audio.id).title);
        $('.judgement-play-icon', button).textContent = playing ? 'Ⅱ' : '▶';
        button.dataset.previewState = audio.dataset.previewState || 'idle';
        button.setAttribute('aria-busy', String(['loading', 'buffering'].includes(button.dataset.previewState)));
      };
      for (const name of ['playing', 'pause', 'waiting', 'canplay', 'loadstart']) audio.addEventListener(name, paint);
      audio.addEventListener('playing', () => {
        note.textContent = '';
        if (mode === 'spotlight' && state === 'playing')
          selectSlot(Number(audio.id.split('-').at(-1)), false);
      });
      audio.addEventListener('error', () => { note.textContent = 'Preview unavailable'; paint(); });
    });
  }
  async function play(id) {
    const audio = document.getElementById(id);
    if (!audio) return;
    if (!audio.paused || audio.dataset.previewWanted === 'true') { playback ? playback.cancel(audio) : audio.pause(); return; }
    try { if (playback) await playback.play(audio); else await audio.play(); }
    catch (error) {
      if (closed || error.name === 'AbortError') return;
      $('.judgement-audio-note', audio.closest('.judgement-card')).textContent = error.name === 'NotAllowedError' ? 'Press play to retry' : 'Preview unavailable';
    }
  }
  async function loadRound() {
    if (closed || state === 'saving') return;
    cancelAutoSelect();dragging = false;
    cancelNext?.(); cancelNext = null;rotation?.destroy();rotation = null;
    const id = ++generation;
    state = 'loading'; message(''); stage.setAttribute('aria-busy', 'true'); update();
    const next = $('[data-j-next]', root); if (next) { next.disabled = true; next.textContent = 'Loading…'; }
    try {
      const loader = signal => post('/api/' + mode + '/round', {}, signal);
      const offered = await (flow ? flow.take('judgement-' + mode, loader) : loader());
      if (closed || id !== generation) return;
      const old = $$('audio', root);
      if (playback) playback.forgetPair(old)?.catch(() => {}); else old.forEach(a => a.pause());
      positions = [null, null, null, null];selectedSlot = 0;
      round = offered; allocations = [0, 0, 0, 0]; placements = {};
      themes = new Set(); themesReviewed = false; pending = null;
      activeMap = offered.suggested_maps?.[0] || config.maps[0].key;
      restore(); state = pending ? 'retry' : 'playing';
      window.Listening?.start(mode, round.token, round.songs.map(s => s.id));
      render();
      if (pending) message('A previous save was not confirmed. Retry the same save to check it.', 'save');
    } catch (error) {
      if (closed || id !== generation) return;
      state = 'unavailable'; message(error.message, 'load');
      if (!round) stage.innerHTML = '<div class="panel judgement-loading">A round is not available yet.</div>';
    } finally {
      if (!closed && id === generation) stage.setAttribute('aria-busy', 'false');
    }
  }
  async function commit() {
    if (closed || !pending || state === 'saving') return;
    const id = generation, submitted = pending;
    state = 'saving'; message(''); update();
    try {
      const receipt = await post('/api/' + mode + '/answer', submitted);
      if (closed || id !== generation) return;
      if (mode === 'spotlight' && receipt.allocations) allocations = [...receipt.allocations];
      pending = null;
      try { sessionStorage.removeItem(draftKey); } catch {}
      state = 'saved'; update();
      if (receipt.status === 'skipped') { await loadRound(); return; }
      if (mode === 'spotlight') {
        const result = $('#judgement-result');result.hidden = false;
        result.innerHTML = '<span class="judgement-sr" role="status">Round saved. Previewing songs in point order.</span>';
        $('#judgement-save').hidden = true;
        const next = document.createElement('button');next.type='button';next.className='btn judgement-primary';
        next.dataset.jNext='';next.textContent='Next round →';$('.judgement-actions',root).append(next);
        next.focus({preventScroll:true});
        if (flow) flow.prepare('judgement-'+mode,signal=>post('/api/'+mode+'/round',{},signal));
        startSpotlightResults();return;
      }
      const result = $('#judgement-result'), duration = flow?.duration('pairResult') || 4500;
      const text = mode === 'spotlight' ? 'Split saved' : `${receipt.maps.length} ${receipt.maps.length === 1 ? 'map' : 'maps'} saved`;
      result.hidden = false;
      result.innerHTML = `<strong>${esc(text)}</strong><button type="button" class="btn judgement-primary" data-j-next>Next round →</button><div class="judgement-countdown" style="--result-ms:${duration}ms" aria-hidden="true"><span></span></div>`;
      $('#judgement-save').hidden = true; const skip = $('[data-j-skip]', root);if (skip) skip.hidden = true;
      $('[data-j-next]', root).focus({preventScroll: true});
      if (flow) {
        flow.prepare('judgement-' + mode, signal => post('/api/' + mode + '/round', {}, signal));
        cancelNext = flow.after(loadRound, duration);
      }
    } catch (error) {
      if (closed || id !== generation) return;
      if (error.status >= 400 && error.status < 500) {
        pending = null;
        state = error.status === 400 || /tag/i.test(error.message) ? 'playing' : 'unavailable';
        message(error.message, state === 'unavailable' ? 'load' : undefined);
      } else {
        state = 'retry'; message(error.message + ' Retry the same save to confirm it.', 'save');
      }
      update();
    }
  }
  function submit(skip = false) {
    if (state !== 'playing' || (!skip && !valid())) return;
    cancelAutoSelect();rotation?.stop(false);
    pending = {token: round.token, rules_version: round.rules_version};
    if (skip) pending.skip = true;
    else {
      if (mode === 'spotlight') {
        if (round.rules_version === 2) pending.positions = [...positions];
        else pending.allocations = [...allocations];
      }
      else if (mode === 'vibe') {
        pending.maps = Object.entries(placements).map(([map, p]) => ({map, x: p.x, y: p.y}));
        if (themesReviewed) pending.themes = [...themes].sort((a, b) => a - b);
      }
      const sample = window.Listening?.sample(); if (sample) pending.listening = sample;
    }
    persist(); commit();
  }
  root.addEventListener('click', event => {
    if (mode === 'spotlight' && event.target.id === 'spotlight-line') {place(event.target.value);return;}
    if (event.target.closest('a')) cancelAutoSelect();
    const button = event.target.closest('button');
    if (!button || button.disabled) return;
    if (button.dataset.judgementPlay) {
      const audio = document.getElementById(button.dataset.judgementPlay);
      if (rotation?.active) {
        const slot = rotationOrder.indexOf($$('audio', root).indexOf(audio));
        if (rotation.index === slot && !audio.paused) {rotation.stop();if (state === 'saved') finishSpotlightResults();}else rotation.jump(slot);
      } else if (mode === 'spotlight' && state === 'playing') {
        rotation.start(rotationOrder.indexOf(Number(audio.id.split('-').at(-1))));
      } else play(button.dataset.judgementPlay);
      return;
    }
    if (button === retry) { retryKind === 'save' ? commit() : loadRound(); return; }
    if (button.hasAttribute('data-j-next')) { loadRound(); return; }
    if (button.hasAttribute('data-spotlight-loop') && ['playing','saved'].includes(state)) {
      if (rotation.active) {rotation.stop();if (state === 'saved') finishSpotlightResults();}
      else if (state === 'saved') startSpotlightResults();else rotation.start(selectedSlot);
      return;
    }
    if (state !== 'playing') return;
    if (button.id === 'judgement-save') { submit(); return; }
    if (button.hasAttribute('data-j-skip')) { submit(true); return; }
    if (button.hasAttribute('data-spotlight-select')) {selectSlot(Number(button.dataset.spotlightSelect));return;}
    if (button.dataset.vibeTab) { activeMap = button.dataset.vibeTab; renderMap(); }
    if (button.hasAttribute('data-vibe-x')) {
      placements[activeMap] = {x: Number(button.dataset.vibeX), y: Number(button.dataset.vibeY)};
      renderMap(); $(`[data-vibe-x="${placements[activeMap].x}"][data-vibe-y="${placements[activeMap].y}"]`, root).focus({preventScroll: true});
    }
    if (button.hasAttribute('data-vibe-clear')) {
      delete placements[activeMap]; renderMap();
      $('[data-vibe-x="2"][data-vibe-y="2"]', root).focus({preventScroll: true});
    }
    if (button.hasAttribute('data-theme-none')) { themes.clear(); themesReviewed = true; }
    if (button.hasAttribute('data-theme-clear')) { themes.clear(); themesReviewed = false; }
    update();
  });
  root.addEventListener('input', event => {
    if (event.target.id === 'vibe-tag-search') {
      const text = event.target.value.trim().toLocaleLowerCase(); let visible = 0;
      $$('[data-tag-search]', root).forEach(label => { label.hidden = !label.dataset.tagSearch.includes(text); if (!label.hidden) visible++; });
      $('#vibe-tags-empty').hidden = visible > 0; return;
    }
    if (state !== 'playing') return;
    if (event.target.id === 'spotlight-line') place(event.target.value);
  });
  root.addEventListener('change', event => {
    if (state !== 'playing' || !event.target.hasAttribute('data-theme')) return;
    const input = event.target, id = Number(input.value);
    if (input.checked && themes.size < config.max_themes) themes.add(id); else themes.delete(id);
    themesReviewed = true; update();
  });
  root.addEventListener('keydown', event => {
    if (event.target.id === 'spotlight-line' && state === 'playing') {
      const changes = {ArrowLeft:-1, ArrowDown:-1, ArrowRight:1, ArrowUp:1, PageDown:-10, PageUp:10};
      if (event.key in changes || ['Home', 'End'].includes(event.key)) {
        event.preventDefault();
        place(event.key === 'Home' ? 0 : event.key === 'End' ? 100 : Math.max(0, Math.min(100,
          Number(event.target.value) + changes[event.key]*(event.shiftKey && Math.abs(changes[event.key]) === 1 ? 10 : 1))));
      }
      return;
    }
    const tab = event.target.closest('[data-vibe-tab]');
    if (tab && state === 'playing' && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const tabs = $$('[data-vibe-tab]', root), at = tabs.indexOf(tab);
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (at + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[index].click(); tabs[index].focus(); return;
    }
    const cell = event.target.closest('[data-vibe-x]');
    if (!cell || state !== 'playing' || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault(); let x = Number(cell.dataset.vibeX), y = Number(cell.dataset.vibeY);
    if (event.key === 'ArrowLeft') x = Math.max(0, x - 1);
    if (event.key === 'ArrowRight') x = Math.min(4, x + 1);
    if (event.key === 'ArrowUp') y = Math.min(4, y + 1);
    if (event.key === 'ArrowDown') y = Math.max(0, y - 1);
    if (event.key === 'Home') x = 0;
    if (event.key === 'End') x = 4;
    $(`[data-vibe-x="${x}"][data-vibe-y="${y}"]`, root).click();
  });
  root.addEventListener('pointerdown', event => {
    if (event.target.id === 'spotlight-line' && state === 'playing') {dragging=true;cancelAutoSelect();}
  });
  const releasePlacement = () => {if (dragging) {dragging=false;if (placementDirty && state==='playing') scheduleAutoSelect();}};
  window.addEventListener('pointerup',releasePlacement);window.addEventListener('pointercancel',releasePlacement);
  window.addEventListener('resize', () => {if (mode === 'spotlight' && round) update();});
  document.addEventListener('visibilitychange', () => {if (document.hidden) {cancelAutoSelect();rotation?.stop();if (state === 'saved') finishSpotlightResults();}});
  document.addEventListener('preview-blocked', () => {rotation?.stop();if (state === 'saved') finishSpotlightResults();});
  document.addEventListener('change', event => {if (event.target.id === 'round-pace') rotation?.paceChanged();});
  window.addEventListener('storage', event => {if (event.key === 'songRankerPlaySettings') rotation?.paceChanged();});
  window.addEventListener('pagehide', () => {
    cancelAutoSelect();rotation?.destroy();rotation = null;
    closed = true; generation++; cancelNext?.(); flow?.clear();
    for (const controller of requests) controller.abort();
    playback?.stopAll();
  });
  window.addEventListener('pageshow', event => { if (event.persisted) { closed = false; state = 'loading'; loadRound(); } });
  loadRound();
})();
