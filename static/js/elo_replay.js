/* One lazy, read-only public-Elo player for reports and individual songs. */
window.EloReplay = (() => {
  "use strict";
  const {esc} = window.SongRankerUI;
  const controllers = new Map();
  let instance = 0;
  const number = value => Number(value).toLocaleString(undefined, {maximumFractionDigits: 1});
  const signed = value => `${value >= 0 ? "+" : "−"}${Math.abs(value) > 0 && Math.abs(value) < .01 ? "<0.01" : Math.abs(value).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
  const songLink = song => `<a class="song" href="/song/${song.id}" title="${esc(song.title)}">${esc(song.title)}</a>`;
  function panel(songId = null) {
    return `<section class="panel dashboard-surface mode-stats-panel elo-replay-panel"><div data-elo-replay${songId ? ` data-song-id="${Number(songId)}"` : ""}></div></section>`;
  }
  function mount(root) {
    if (controllers.has(root)) return controllers.get(root);
    const songId = Number(root.dataset.songId) || null;
    const paceId = `elo-replay-pace-${++instance}`;
    root.classList.toggle("elo-replay-is-song", !!songId);
    root.innerHTML = `<div class="section-head"><h2 class="voting">${songId ? "Elo journey" : "Top five replay"}</h2></div>
      <div class="elo-replay-controls"><button class="btn voting" data-replay-play aria-pressed="false">Play replay</button><button class="btn" data-replay-restart disabled>Restart</button>${window.GameplayUI.select(paceId, "Pace", [{value:"3200",label:"Relaxed"},{value:"2000",label:"Normal"},{value:"1000",label:"Quick"}], "2000")}${songId ? "" : '<button class="btn" data-replay-sound aria-pressed="true">Sound on</button>'}</div>
      ${songId ? "" : '<p class="elo-replay-audio-status" data-replay-audio-status role="status"></p>'}
      <div class="elo-replay-clock"><time data-replay-time>Starting ratings → current</time><span data-replay-step>Saved public Elo</span></div>
      <label class="elo-replay-seek">Timeline <input data-replay-seek type="range" min="0" max="0" value="0" disabled aria-label="Replay position"></label>
      <div class="elo-replay-layout" data-replay-layout hidden><div class="elo-replay-stage" data-replay-stage aria-label="${songId ? "Two tracks above and two below the selected song" : "Five highest public Elo ratings"}"></div>${songId ? "" : '<aside class="elo-replay-opponent" data-replay-opponent aria-label="Latest leaderboard points gain"></aside>'}</div>
      <div class="elo-replay-cue" data-replay-cue aria-live="polite" aria-atomic="true">${songId ? "Follow this song and the tracks immediately around it." : "Watch the leaders change and hear the current top track."}</div>
      <p class="mode-stats-caption elo-replay-note" data-replay-note>Current collection · Quiet votes are skipped · Date/time shown in UTC</p>`;
    root.querySelector(`#${paceId}`).setAttribute("data-replay-speed", "");
    const $ = selector => root.querySelector(selector);
    const play = $("[data-replay-play]"), restart = $("[data-replay-restart]"), speed = $("[data-replay-speed]"), seek = $("[data-replay-seek]");
    const stage = $("[data-replay-stage]"), clock = $("[data-replay-time]"), step = $("[data-replay-step]"), cue = $("[data-replay-cue]"), layout = $("[data-replay-layout]"), opponent = $("[data-replay-opponent]"), soundButton = $("[data-replay-sound]"), audioStatus = $("[data-replay-audio-status]");
    let data, index = 0, playing = false, timer, loading, request, disposed = false, generation = 0;
    let sound = true, audio = null, leaderId = null, audioSerial = 0, leaderPending = null, causes = [], shownCause;
    const tails = new Set(), failedAudio = new Set();
    const rows = new Map(), animations = new Set();
    const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    function pause() {
      playing = false;
      clearTimeout(timer);
      stopAudio(false);
      if (audioStatus && audio && sound) audioStatus.textContent = "Preview paused";
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
    function releaseClip(clip) {
      if (!clip) return;
      window.PreviewPlayback?.abandon?.(clip);
      clip.pause();
      if (window.PreviewPlayback?.release) window.PreviewPlayback.release(clip);
      else clip.remove();
    }
    function stopAudio(dispose = true) {
      audioSerial++; leaderPending = null;
      if (audio) {
        if (dispose) releaseClip(audio);
        else { window.PreviewPlayback?.abandon?.(audio); audio.pause(); }
      }
      if (dispose) { audio = null; leaderId = null; }
      tails.forEach(releaseClip); tails.clear();
    }
    function playLeader() {
      if (songId || !playing || !sound || disposed || document.hidden) return;
      const id = data.frames[index].board[0]?.id, track = data.songs[id];
      if (!track?.audio_url || failedAudio.has(id)) {
        stopAudio(); audioStatus.textContent = "Leader preview unavailable"; return;
      }
      if (id === leaderId && audio && (!audio.paused || leaderPending === audio)) return;
      tails.forEach(releaseClip); tails.clear();
      if (id !== leaderId || !audio) {
        if (audio) {
          if (!audio.paused) { tails.add(audio); window.PreviewPlayback?.retire?.(audio); }
          else releaseClip(audio);
        }
        audio = document.createElement("audio");
        audio.preload = "none"; audio.loop = true;
        audio.dataset.songId = id; audio.dataset.replayAudio = "true";
        audio.src = window.PreviewPlayback?.source(id, track.audio_url) || track.audio_url;
        root.append(audio); leaderId = id;
      }
      const clip = audio, token = ++audioSerial;
      leaderPending = clip;
      audioStatus.textContent = "Loading leader preview…";
      Promise.resolve(window.PreviewPlayback ? window.PreviewPlayback.play(clip) : clip.play()).then(() => {
        if (leaderPending === clip && token === audioSerial) leaderPending = null;
        if (disposed || audio !== clip || !playing || !sound) { clip.pause(); return; }
        if (token === audioSerial) audioStatus.textContent = "Playing current leader";
      }).catch(error => {
        if (leaderPending === clip && token === audioSerial) leaderPending = null;
        if (disposed || token !== audioSerial || error.name === "AbortError") return;
        if (error.name !== "NotAllowedError") failedAudio.add(id);
        stopAudio();
        audioStatus.textContent = error.name === "NotAllowedError" ? "Press Sound to enable the leader preview" : "Leader preview unavailable";
        if (error.name === "NotAllowedError") { sound = false; soundButton.textContent = "Enable sound"; soundButton.setAttribute("aria-pressed", "false"); }
      });
    }
    function pointsCard() {
      if (!opponent || shownCause === causes[index]) return;
      shownCause = causes[index];
      if (!shownCause) { opponent.innerHTML = '<h3>Latest gain</h3><p class="mode-stats-caption">The opponent behind a leaderboard gain will appear here.</p>'; return; }
      const track = data.songs[shownCause.opponent_id], receiver = data.songs[shownCause.id];
      opponent.innerHTML = `<h3>Latest gain</h3><a class="elo-replay-opponent-art" href="/song/${track.id}" aria-label="${esc(track.title)}">${track.cover_url ? `<img src="${esc(track.cover_url)}" alt="" loading="lazy">` : '<span aria-hidden="true">♫</span>'}</a>${identity(track)}<p class="elo-replay-transfer"><b class="song">${signed(shownCause.after - shownCause.before)} Elo</b> for ${songLink(receiver)}</p>`;
      opponent.querySelector("img")?.addEventListener("error", event => { event.target.hidden = true; });
    }
    function render(motion = false) {
      const frame = data.frames[index], token = ++generation;
      layout.hidden = false;
      stage.classList.toggle("is-empty", !frame.board.length);
      for (const animation of animations) animation.cancel();
      animations.clear();
      const height = parseFloat(getComputedStyle(stage).getPropertyValue("--replay-row-height")) || 112;
      const kept = new Set(frame.board.map(row => row.id));
      for (const [id, row] of rows) if (!kept.has(id)) { row.node.remove(); rows.delete(id); }
      frame.board.forEach((entry, offset) => {
        const position = entry.slot ?? offset, standing = entry.rank ?? offset + 1;
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
        row.node.querySelector(".elo-replay-rank").textContent = standing;
        row.node.classList.toggle("is-featured", songId ? entry.id === songId : offset === 0);
        row.node.classList.toggle("is-focus-track", entry.id === songId);
        row.node.setAttribute("aria-label", `Rank ${standing}: ${song.title}, ${number(entry.elo)} Elo`);
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
      stage.querySelectorAll(".elo-replay-gap").forEach(node => node.remove());
      if (songId && frame.focus) {
        const occupied = new Set(frame.board.map(row => row.slot));
        for (let slot = 0; slot < 5; slot++) if (!occupied.has(slot)) {
          const gap = document.createElement("div"); gap.className = "elo-replay-gap";
          gap.style.transform = `translateY(${slot * height}px)`;
          gap.textContent = slot < 2 ? "No higher track" : "No lower track";
          gap.setAttribute("aria-hidden", "true"); stage.append(gap);
        }
      }
      pointsCard();
      playLeader();
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
        schedule();
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
            data = payload;
            let cause = null, previous = new Set();
            causes = data.frames.map(frame => {
              const kept = new Set(frame.board.map(row => row.id));
              const gain = frame.kind === "vote" && (frame.changes.find(c => c.opponent_id && c.after > c.before && kept.has(c.id) && !previous.has(c.id)) || frame.changes.find(c => c.opponent_id && c.after > c.before && kept.has(c.id)));
              if (gain) cause = gain;
              previous = kept; return cause;
            });
            seek.max = Math.max(0, data.frames.length - 1); seek.disabled = data.frames.length < 2;
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
        layout.hidden = true;
        cue.textContent = "This song has no saved Elo to replay.";
        play.textContent = "No saved Elo"; play.disabled = true;
        restart.disabled = true; seek.disabled = true; return;
      }
      if (data.frames.length < 2) { play.textContent = "No changes yet"; play.disabled = true; return; }
      if (index === data.frames.length - 1) { index = 0; render(); }
      playing = true; play.textContent = "Pause"; play.setAttribute("aria-pressed", "true"); playLeader(); schedule();
    }
    play.addEventListener("click", () => playing ? pause() : start());
    restart.addEventListener("click", () => { pause(); index = 0; render(); });
    seek.addEventListener("input", () => { pause(); index = Number(seek.value); render(); });
    speed.addEventListener("change", () => { if (playing) schedule(); });
    soundButton?.addEventListener("click", () => {
      sound = !sound; soundButton.textContent = sound ? "Sound on" : "Sound off";
      soundButton.setAttribute("aria-pressed", String(sound));
      if (sound) { failedAudio.clear(); playLeader(); }
      else { stopAudio(); audioStatus.textContent = ""; }
    });
    const visibility = () => { if (document.hidden) pause(); };
    document.addEventListener("visibilitychange", visibility);
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => { if (data && !disposed) render(); }) : null;
    observer?.observe(stage);
    const controller = {pause, destroy() { disposed = true; generation++; pause(); stopAudio(); request?.abort(); observer?.disconnect(); document.removeEventListener("visibilitychange", visibility); for (const animation of animations) animation.cancel(); controllers.delete(root); }};
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
