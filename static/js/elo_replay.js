/* One lazy, read-only public-Elo player for reports and individual songs. */
window.EloReplay = (() => {
  "use strict";
  const {esc} = window.SongRankerUI;
  const controllers = new Map();
  const number = value => Number(value).toLocaleString(undefined, {maximumFractionDigits: 1});
  const signed = value => `${value >= 0 ? "+" : "−"}${Math.abs(value) > 0 && Math.abs(value) < .01 ? "<0.01" : Math.abs(value).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
  const songLink = song => `<a class="song" href="/song/${song.id}" title="${esc(song.title)}">${esc(song.title)}</a>`;
  function panel(songId = null) {
    return `<section class="panel dashboard-surface mode-stats-panel elo-replay-panel"><div data-elo-replay${songId ? ` data-song-id="${Number(songId)}"` : ""}></div></section>`;
  }
  function mount(root) {
    if (controllers.has(root)) return controllers.get(root);
    const songId = Number(root.dataset.songId) || null;
    root.innerHTML = `<div class="section-head"><h2 class="voting">${songId ? "Elo journey" : "Top five replay"}</h2></div>
      <div class="elo-replay-clock"><time data-replay-time>Starting ratings → current</time><span data-replay-step>Saved public Elo</span></div>
      <div class="elo-replay-controls"><button class="btn voting" data-replay-play aria-pressed="false">Play replay</button><button class="btn" data-replay-restart disabled>Restart</button><label>Pace <select data-replay-speed aria-label="Replay pace"><option value="3200">Relaxed</option><option value="2000" selected>Normal</option><option value="1000">Quick</option></select></label></div>
      <label class="elo-replay-seek">Timeline <input data-replay-seek type="range" min="0" max="0" value="0" disabled aria-label="Replay position"></label>
      <div class="elo-replay-focus" data-replay-focus hidden></div><div class="elo-replay-stage" data-replay-stage hidden aria-label="Five highest public Elo ratings"></div>
      <div class="elo-replay-cue" data-replay-cue aria-live="polite" aria-atomic="true">${songId ? "Follow this song’s matches, Elo and rank." : "Watch the five leaders change with the saved votes."}</div>
      <p class="mode-stats-caption elo-replay-note" data-replay-note>Current collection · Quiet votes are skipped · Date/time shown in UTC</p>`;
    const $ = selector => root.querySelector(selector);
    const play = $("[data-replay-play]"), restart = $("[data-replay-restart]"), speed = $("[data-replay-speed]"), seek = $("[data-replay-seek]");
    const stage = $("[data-replay-stage]"), clock = $("[data-replay-time]"), step = $("[data-replay-step]"), cue = $("[data-replay-cue]"), focus = $("[data-replay-focus]");
    let data, index = 0, playing = false, timer, loading, request, disposed = false, generation = 0, focusValue;
    const rows = new Map(), animations = new Set();
    const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    function pause() {
      playing = false;
      clearTimeout(timer);
      play.textContent = data && index === data.frames.length - 1 ? "Replay again" : data ? "Play" : "Play replay";
      play.setAttribute("aria-pressed", "false");
    }
    function animate(node, frames) {
      if (reduced() || !node.animate) return;
      const animation = node.animate(frames, {duration: 460, easing: "cubic-bezier(.2,.8,.2,1)"});
      animations.add(animation);
      animation.finished.then(() => animations.delete(animation), () => animations.delete(animation));
    }
    function score(node, before, after, motion, token) {
      if (!motion || reduced() || before === after || !Number.isFinite(before)) {
        node.textContent = number(after);
        return;
      }
      const start = performance.now();
      function tick(now) {
        if (disposed || token !== generation) return;
        const t = Math.min(1, (now - start) / 460), eased = 1 - (1 - t) ** 3;
        node.textContent = number(before + (after - before) * eased);
        if (t < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    }
    function identity(song) {
      const artists = song.artist_links.map(a => `<a class="artist" href="/artist/${encodeURIComponent(a.name)}" title="${esc(a.name)}">${esc(a.name)}</a>`).join(" · ");
      const album = song.album_link ? `<a class="album" href="/album/${encodeURIComponent(song.album_link.title)}" title="${esc(song.album_link.title)}">${esc(song.album_link.title)}</a>` : "";
      return `<div class="elo-replay-copy">${songLink(song)}<div class="elo-replay-meta">${artists}${album ? " · " + album : ""}</div></div>`;
    }
    function render(motion = false) {
      const frame = data.frames[index], token = ++generation;
      stage.hidden = false;
      stage.classList.toggle("is-empty", !frame.board.length);
      for (const animation of animations) animation.cancel();
      animations.clear();
      const height = parseFloat(getComputedStyle(stage).getPropertyValue("--replay-row-height")) || 88;
      const kept = new Set(frame.board.map(row => row.id));
      for (const [id, row] of rows) if (!kept.has(id)) { row.node.remove(); rows.delete(id); }
      frame.board.forEach((entry, position) => {
        const song = data.songs[entry.id];
        let row = rows.get(entry.id), entering = !row;
        if (!row) {
          const node = document.createElement("article");
          node.className = "elo-replay-row";
          node.innerHTML = `<span class="elo-replay-rank"></span><a class="elo-replay-art" href="/song/${song.id}" aria-label="${esc(song.title)}">${song.cover_url ? `<img src="${esc(song.cover_url)}" alt="" loading="lazy">` : '<span aria-hidden="true">♫</span>'}</a>${identity(song)}<div class="elo-replay-value"><strong></strong><span class="elo-replay-delta"></span></div>`;
          const image = node.querySelector("img");
          if (image) image.addEventListener("error", () => { image.hidden = true; });
          row = {node, position, value: entry.elo}; rows.set(entry.id, row); stage.append(node);
        }
        const change = frame.changes.find(c => c.id === entry.id), delta = change ? change.after - change.before : 0;
        row.node.querySelector(".elo-replay-rank").textContent = position + 1;
        row.node.setAttribute("aria-label", `Rank ${position + 1}: ${song.title}, ${number(entry.elo)} Elo`);
        row.node.style.transform = `translateY(${position * height}px)`;
        row.node.classList.toggle("is-gain", delta > 0); row.node.classList.toggle("is-loss", delta < 0);
        const deltaNode = row.node.querySelector(".elo-replay-delta");
        deltaNode.textContent = delta ? signed(delta) : "Elo";
        deltaNode.title = change ? `${change.before} → ${change.after} Elo` : "";
        row.node.querySelector("strong").title = String(entry.elo);
        score(row.node.querySelector("strong"), change?.before ?? row.value, entry.elo, motion, token);
        if (motion) animate(row.node, entering ? [{opacity:0, transform:`translateY(${position * height + 12}px)`}, {opacity:1, transform:`translateY(${position * height}px)`}] : [{transform:`translateY(${row.position * height}px)`}, {transform:`translateY(${position * height}px)`}]);
        row.position = position; row.value = entry.elo;
      });
      // Keep visual and keyboard/assistive reading order aligned after a move.
      frame.board.forEach(entry => stage.append(rows.get(entry.id).node));
      if (!frame.board.length) stage.innerHTML = '<p class="empty">No saved ratings to replay yet.</p>';
      clock.textContent = frame.time ? new Intl.DateTimeFormat(undefined, {dateStyle:"medium", timeStyle:"medium", timeZone:"UTC"}).format(new Date(frame.time)) + " UTC" : frame.kind === "start" ? "Starting ratings" : "Current saved ratings";
      if (frame.time) clock.dateTime = frame.time; else clock.removeAttribute("datetime");
      step.textContent = `${index + 1} / ${data.frames.length} moments · ${frame.ordinal} / ${data.total_matches} votes`;
      seek.value = index;
      seek.setAttribute("aria-valuetext", `${index + 1} of ${data.frames.length}: ${clock.textContent}`);
      if (frame.focus) {
        focus.hidden = false;
        if (!focus.firstElementChild) focus.innerHTML = `${identity(data.songs[frame.focus.id])}<div><small>Rank</small><strong data-focus-rank></strong></div><div><small>Elo</small><strong data-focus-elo></strong></div>`;
        focus.querySelector("[data-focus-rank]").textContent = `#${frame.focus.rank}`;
        const ownChange = frame.changes.find(c => c.id === frame.focus.id);
        score(focus.querySelector("[data-focus-elo]"), ownChange?.before ?? focusValue, frame.focus.elo, motion, token);
        focus.querySelector("[data-focus-elo]").title = String(frame.focus.elo);
        focusValue = frame.focus.elo;
      }
      const change = songId ? frame.changes.find(c => c.id === songId) : frame.changes.find(c => kept.has(c.id));
      if (frame.kind === "vote" && change) {
        const delta = change.after - change.before, opponent = data.songs[change.opponent_id];
        cue.innerHTML = `<span class="${frame.mode === "blind" ? "blind" : "standard"}">${frame.mode === "blind" ? "Blind" : "Non-blind"}</span>${frame.origin === "tournament" ? ' · <span class="tournament">Tournament</span>' : ""} · ${songLink(data.songs[change.id])} <b class="${delta >= 0 ? "song" : "loss"}">${signed(delta)} Elo</b>${opponent ? ` ${delta >= 0 ? "from" : "to"} ${songLink(opponent)}` : ""}`;
      } else if (frame.kind === "vote") {
        const winner = frame.changes[0], loser = frame.changes[1];
        cue.innerHTML = winner && loser ? `Rank shifted after ${songLink(data.songs[winner.id])} beat ${songLink(data.songs[loser.id])}.` : "Rank updated.";
      } else cue.textContent = ({start: data.anchored ? "Starting from the saved rating anchor." : "The collection’s starting ratings.", adjustment:"Saved rating adjustment.", anchor:"Saved rating anchor · earlier detail is unavailable.", current:"Current saved leaderboard."})[frame.kind] || "Saved ratings.";
      if (index === data.frames.length - 1 && !playing) play.textContent = "Replay again";
    }
    function schedule() {
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (disposed || !root.isConnected || document.hidden) { pause(); return; }
        if (index >= data.frames.length - 1) { pause(); return; }
        index++; render(true);
        if (index === data.frames.length - 1) pause(); else schedule();
      }, Number(speed.value));
    }
    async function start() {
      if (loading) return loading;
      if (!data) {
        request = new AbortController(); play.disabled = true; play.textContent = "Loading…";
        cue.textContent = "Loading saved rating history…";
        cue.removeAttribute("role");
        loading = (async () => {
          try {
            const response = await fetch(`/api/voting-replay${songId ? `?song_id=${songId}` : ""}`, {signal:request.signal});
            if (!response.ok) throw Error("Replay could not load. Try again.");
            const payload = await response.json();
            if (!Array.isArray(payload.frames) || !payload.frames.length || !payload.songs) throw Error("Invalid replay response");
            if (disposed || !root.isConnected) return;
            data = payload; seek.max = Math.max(0, data.frames.length - 1); seek.disabled = data.frames.length < 2;
            restart.disabled = data.frames.length < 2;
            $("[data-replay-note]").textContent = `Current collection · Quiet votes skipped · UTC${data.anchored ? " · History starts at a saved anchor" : ""}${data.omitted ? ` · ${data.omitted} votes lack usable saved ratings` : ""}${data.reconciled ? " · Current endpoint includes saved rating adjustments" : ""}`;
            render();
          } catch (error) {
            if (disposed || error.name === "AbortError") return;
            cue.textContent = "Replay could not load. Try again."; cue.setAttribute("role", "alert"); play.textContent = "Retry replay";
          } finally { loading = null; if (!disposed) play.disabled = false; }
        })();
        await loading;
      }
      if (!data || disposed) return;
      if (songId && data.focus_available === false) {
        stage.hidden = true; focus.hidden = true;
        cue.textContent = "This song has no saved Elo to replay.";
        play.textContent = "No saved Elo"; play.disabled = true;
        restart.disabled = true; seek.disabled = true; return;
      }
      if (data.frames.length < 2) { play.textContent = "No changes yet"; play.disabled = true; return; }
      if (index === data.frames.length - 1) { index = 0; render(); }
      playing = true; play.textContent = "Pause"; play.setAttribute("aria-pressed", "true"); schedule();
    }
    play.addEventListener("click", () => playing ? pause() : start());
    restart.addEventListener("click", () => { pause(); index = 0; render(); });
    seek.addEventListener("input", () => { pause(); index = Number(seek.value); render(); });
    speed.addEventListener("change", () => { if (playing) schedule(); });
    const visibility = () => { if (document.hidden) pause(); };
    document.addEventListener("visibilitychange", visibility);
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => { if (data && !disposed) render(); }) : null;
    observer?.observe(stage);
    const controller = {pause, destroy() { disposed = true; generation++; pause(); request?.abort(); observer?.disconnect(); document.removeEventListener("visibilitychange", visibility); for (const animation of animations) animation.cancel(); controllers.delete(root); }};
    controllers.set(root, controller); return controller;
  }
  function mountAll(container = document) {
    for (const [root, controller] of controllers) if (!root.isConnected) controller.destroy();
    container.querySelectorAll("[data-elo-replay]").forEach(mount);
  }
  document.addEventListener("DOMContentLoaded", () => mountAll());
  window.addEventListener("pagehide", () => { for (const controller of [...controllers.values()]) controller.destroy(); });
  return Object.freeze({panel, mount, mountAll});
})();
