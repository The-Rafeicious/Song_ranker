/* Independent V3.3 games and their shared stats/profile projections. */
window.SpecialModes = (() => {
  "use strict";
  let U,
    guess = null,
    guessBusy = false,
    guessLoading = false,
    guessRequest = 0,
    shelf = null,
    shelfBusy = false,
    dragged = null,
    loopRequested = false,
    playingSlot = null,
    selectedSlot = null,
    previewTimer = null,
    previewGeneration = 0;
  const { $, $$, esc } = window.SongRankerUI,
    flow = window.RoundFlow;
  const wait = (name, fallback) => flow?.duration(name) || fallback;
  const pct = window.SongRankerUI.ratio,
    num = (n) => Number(n || 0).toFixed(2);
  const metricKeys = [
    "guess_attempts",
    "guess_correct",
    "shelf_attempts",
    "shelf_album_correct",
    "shelf_order_right",
    "shelf_order_pairs",
    "shelf_points",
    "shelf_available",
  ];
  function totals(tracks) {
    return window.SongRankerUI.sumFields(tracks, metricKeys);
  }

  const reveal = {
    generation: 0,
    timers: new Map(),
    audio: null,
    clip: 0,
    closed: false,
  };
  function cancelReveal() {
    reveal.generation++;
    for (const [timer, resolve] of reveal.timers) {
      typeof timer === "function" ? timer() : clearTimeout(timer);
      resolve(false);
    }
    reveal.timers.clear();
    reveal.audio?.pause();
    reveal.audio?.remove();
    reveal.audio = null;
    cancelShelfClips();
  }
  function revealDelay(ms, generation) {
    return new Promise((resolve) => {
      if (generation !== reveal.generation || reveal.closed) {
        resolve(false);
        return;
      }
      const done = () => {
        reveal.timers.delete(timer);
        resolve(generation === reveal.generation && !reveal.closed);
      };
      const timer = flow ? flow.after(done, ms) : setTimeout(done, ms);
      reveal.timers.set(timer, resolve);
    });
  }
  function snippet(song, ms, generation) {
    reveal.audio?.pause();
    reveal.audio?.remove();
    reveal.audio = null;
    if (
      !song?.audio_url ||
      generation !== reveal.generation ||
      reveal.closed ||
      window.PreviewPlayback?.blocked()
    )
      return;
    const audio = document.createElement("audio");
    audio.id = "answer-snippet";
    audio.preload = "none";
    audio.dataset.song = String(song.id);
    audio.volume = Number($("#volume-range")?.value ?? 0.5);
    audio.src =
      window.PreviewPlayback?.source(song.id, song.audio_url) || song.audio_url;
    U.main.append(audio);
    reveal.audio = audio;
    let timer = null;
    const pause = () => {
      clearTimeout(timer);
      audio.pause();
    };
    audio.addEventListener("playing", () => {
      clearTimeout(timer);
      timer = setTimeout(
        () =>
          window.PreviewPlayback
            ? window.PreviewPlayback.fadeOut(audio, 600)
            : pause(),
        Math.max(0, ms - 600),
      );
    });
    audio.addEventListener("timeupdate", () => {
      if (audio.currentTime >= ms / 1000) pause();
    });
    audio.addEventListener("pause", () => clearTimeout(timer));
    const playing = window.PreviewPlayback
      ? window.PreviewPlayback.play(audio)
      : audio.play();
    playing
      .then(() => {
        if (
          generation !== reveal.generation ||
          reveal.closed ||
          !audio.isConnected
        )
          pause();
      })
      .catch((error) => {
        pause();
        if (generation !== reveal.generation || !audio.isConnected) return;
        const note = $("#reveal-audio-note");
        if (note)
          note.textContent =
            error.name === "PreviewBlockedError"
              ? "Audio paused by preview limits"
              : "Preview unavailable";
      });
  }
  // Answer media starts only when its card is revealed; never load ahead.
  const shelfClips = { current: null, outgoing: new Set() };
  function discardClip(audio) {
    if (!audio) return;
    if (window.PreviewPlayback) window.PreviewPlayback.release(audio);
    else {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      audio.remove();
    }
  }
  function cancelShelfClips() {
    discardClip(shelfClips.current);
    shelfClips.outgoing.forEach(discardClip);
    shelfClips.current = null;
    shelfClips.outgoing.clear();
  }
  function answerAudio(song) {
    const audio = document.createElement("audio");
    audio.id = "answer-snippet";
    audio.preload = "none";
    audio.dataset.song = String(song.id);
    audio.volume = 0;
    audio.src =
      window.PreviewPlayback?.source(song.id, song.audio_url) || song.audio_url;
    U.main.append(audio);
    window.PreviewPlayback?.bind(audio);
    return audio;
  }
  function retireShelfClip(generation) {
    const previous = shelfClips.current;
    shelfClips.current = null;
    if (previous) {
      shelfClips.outgoing.add(previous);
      window.PreviewPlayback?.retire(previous);
      if (window.PreviewPlayback) window.PreviewPlayback.fadeOut(previous);
      else discardClip(previous);
    }
  }
  async function shelfAnswerAudio(song, generation) {
    if (generation !== reveal.generation || reveal.closed) return;
    if (!song?.audio_url || window.PreviewPlayback?.blocked()) return;
    const previous = shelfClips.current;
    const audio = answerAudio(song);
    if (previous) {
      previous.id = "outgoing-snippet";
      shelfClips.outgoing.add(previous);
    }
    audio.id = "answer-snippet";
    audio.volume = 0;
    try {
      const playing = Promise.resolve(
        window.PreviewPlayback
          ? window.PreviewPlayback.play(audio)
          : audio.play(),
      );
      playing.catch(() => {});
      const ready = await Promise.race([
        playing.then(() => true),
        revealDelay(3000, generation).then(() => false),
      ]);
      if (
        !ready ||
        generation !== reveal.generation ||
        reveal.closed ||
        !audio.isConnected
      ) {
        window.PreviewPlayback?.abandon(audio);
        discardClip(audio);
        const note = $("#reveal-audio-note");
        if (note && generation === reveal.generation)
          note.textContent = "Preview unavailable";
        return;
      }
      shelfClips.current = audio;
      audio.loop = true;
      if (previous) {
        window.PreviewPlayback?.retire(previous);
        previous.addEventListener(
          "pause",
          () => shelfClips.outgoing.delete(previous),
          { once: true },
        );
      }
    } catch (error) {
      window.PreviewPlayback?.abandon(audio);
      discardClip(audio);
      if (generation === reveal.generation && !reveal.closed) {
        const note = $("#reveal-audio-note");
        if (note)
          note.textContent =
            error.name === "PreviewBlockedError"
              ? "Audio paused by preview limits"
              : "Preview unavailable";
      }
    }
  }

  const guessLink = "/mode_rankings/guesser",
    shelfLink = "/mode_rankings/shelves";
  function panels(tracks, type = "songs") {
    const t = totals(tracks);
    return `<div class="special-profile-panels"><section class="panel special-panel guesser"><div class="section-head"><h2 class="guesser">Elo Guesser</h2><a class="guesser" href="${guessLink}?entity=${["songs", "artists", "albums"].includes(type) ? type : "songs"}">Rankings ↗</a></div><div class="mini-stats"><div><b class="guesser">${pct(t.guess_correct, t.guess_attempts)}</b><small>Correct picks</small></div><div><b class="guesser">${t.guess_correct} / ${t.guess_attempts}</b><small>Track appearances</small></div></div></section><section class="panel special-panel shelves"><div class="section-head"><h2 class="shelves">Album Shelves</h2><a class="shelves" href="${shelfLink}?entity=${["songs", "artists", "albums"].includes(type) ? type : "songs"}">Rankings ↗</a></div><div class="mini-stats"><div><b class="shelves">${pct(t.shelf_points, t.shelf_available)}</b><small>Points earned</small></div><div><b class="shelves">${pct(t.shelf_order_right, t.shelf_order_pairs)}</b><small>Track order</small></div></div></section></div>`;
  }
  function homeSummary() {
    const s = U.data().special_modes || {},
      g = s.guesser || {},
      a = s.shelves || {};
    return `<section class="panel special-panel guesser" data-home-mode="guesser"><div class="section-head"><h2 class="guesser">Elo Guesser</h2><a class="guesser" href="/elo_guesser_stats">Stats ↗</a></div><div class="mini-stats joined-metrics"><div><b class="guesser">${g.correct || 0}</b><small>Correct picks</small></div><div><b class="guesser">${g.challenge?.best_streak || 0} 🔥</b><small>Challenge best streak</small></div><div><b class="guesser">${Math.max(0, Number(g.rounds || 0) - Number(g.correct || 0))}</b><small>Wrong guesses</small></div></div>${U.homeRateBar("guesser", "Correct guesses", g.correct, g.rounds, "No completed guesses yet", "guesses")}</section><section class="panel special-panel shelves" data-home-mode="shelves"><div class="section-head"><h2 class="shelves">Album Shelves</h2><a class="shelves" href="/album_shelves_stats">Stats ↗</a></div><div class="mini-stats joined-metrics"><div><b class="shelves">${a.rounds || 0}</b><small>Rounds</small></div><div><b class="shelves">${Number(a.albums_played || 0)}</b><small title="Distinct albums in completed Shelves rounds">Albums played</small></div><div><b class="shelves">${a.perfect || 0}</b><small>Perfect shelves</small></div></div>${U.homeRateBar("shelves", "Relative track order", a.order_right, a.order_pairs, "No eligible track comparisons yet", "order comparisons")}</section>`;
  }
  function homeBanners() {
    const limit = U.homeBannerLimit ?? 10;
    const songs = U.records("songs"),
      guesses = songs
        .filter((s) => s.guess_attempts > 0)
        .sort(
          (a, b) =>
            b.guess_correct / b.guess_attempts -
              a.guess_correct / a.guess_attempts ||
            b.guess_attempts - a.guess_attempts ||
            a.title.localeCompare(b.title),
        )
        .slice(0, limit);
    const albums = U.records("albums")
      .filter(U.properAlbum)
      .map((a) => ({
        ...a,
        ...totals(songs.filter((s) => s.album_id === a.id)),
      }))
      .filter((a) => a.shelf_order_pairs > 0)
      .sort(
        (a, b) =>
          b.shelf_order_right / b.shelf_order_pairs -
            a.shelf_order_right / a.shelf_order_pairs ||
          b.shelf_order_pairs - a.shelf_order_pairs ||
          a.title.localeCompare(b.title),
      )
      .slice(0, limit);
    const head = (title, key, path) =>
      window.SongRankerUI.shelfHead(title, key, path, "Stats");
    const banner = (rows, key, title, type) =>
      `<section class="shelf-section ${key} home-records" id="home-${key}">${head(title, key, key === "guesser" ? "/elo_guesser_stats" : "/album_shelves_stats")}<div class="scroller" id="shelf-${key}" tabindex="0" aria-label="${title}">${rows.map((r, i) => `<a class="shelf-card ${key}" data-home-record="${key}" href="${U.urlFor(type, r)}"><span class="shelf-rank">${i + 1}</span><div class="shelf-art">${U.artwork(r, type)}</div><div class="shelf-info"><h3 class="${type === "songs" ? "song" : "album"}" title="${esc(r.name)}">${esc(r.name)}</h3><p class="artist" title="${esc(r.artist)}">${esc(r.artist)}</p><strong class="${key}">${key === "guesser" ? pct(r.guess_correct, r.guess_attempts) + " correct" : pct(r.shelf_order_right, r.shelf_order_pairs) + " track order"}</strong><small>${key === "guesser" ? r.guess_correct + " / " + r.guess_attempts + " guesses" : r.shelf_attempts + " track appearances"}</small></div></a>`).join("") || `<div class="empty">${key === "guesser" ? "No Elo guesses yet" : "No shelf placements yet"}</div>`}</div></section>`;
    return (
      banner(guesses, "guesser", "Elo Guesser", "songs") +
      banner(albums, "shelves", "Album Shelves", "albums")
    );
  }
  function gameTabs() {
    return '<div class="game-head"><h1 class="guesser">Elo Guesser</h1></div>';
  }
  function guessCounters(records) {
    return `<div class="stats guess-records">${U.stat("Correct picks", records.correct || 0, "guesser")}${U.stat("Accuracy", pct(records.correct, records.rounds), "guesser")}${U.stat(records.rules_version === 1 ? "Classic streak" : "Challenge streak", (records.streak || 0) + " 🔥", "guesser")}${U.stat(records.rules_version === 1 ? "Classic best" : "Challenge best", (records.best_streak || 0) + " 🔥", "guesser")}</div>`;
  }
  function artistLinks(s) {
    return (s.artists || [])
      .map(
        (a) =>
          `<a class="artist" href="/artist/${encodeURIComponent(a.name)}" title="${esc(a.name)}">${esc(a.name)}</a>`,
      )
      .join('<span class="muted">, </span>');
  }
  async function loadGuess() {
    if (guessLoading || reveal.closed) return;
    guessLoading = true;
    cancelReveal();
    const requestId = ++guessRequest;
    guessBusy = true;
    U.cancelTransition();
    U.stopAudio();
    U.pageTone("guesser");
    document.body.classList.add("game-page");
    const release = U.holdHeight(),
      oldPair = $$("audio[data-preview-pair]");
    window.PreviewPlayback?.forgetPair(oldPair)?.catch(() => {});
    U.main.setAttribute("aria-busy", "true");
    if (!guess)
      U.main.innerHTML =
        gameTabs() + '<div class="empty" role="status">Loading pair…</div>';
    $$("[data-guess-pick],[data-guess-next]").forEach(
      (b) => (b.disabled = true),
    );
    if ($("[data-guess-next]"))
      $("[data-guess-next]").textContent = "Loading next pair…";
    $("#guess-load-error")?.remove();
    try {
      const load = (signal) =>
        U.api("/api/elo-guesser/round", {}, undefined, { signal });
      const result = await (flow ? flow.take("guesser", load) : load());
      if (
        requestId !== guessRequest ||
        reveal.closed ||
        document.body.dataset.tone !== "guesser"
      )
        return;
      guess = { ...result, answered: false };
      renderGuess();
    } catch (error) {
      if (
        requestId === guessRequest &&
        !reveal.closed &&
        document.body.dataset.tone === "guesser"
      ) {
        U.main.insertAdjacentHTML(
          "beforeend",
          `<p id="guess-load-error" class="error" role="alert">${esc(error.message)}</p>`,
        );
        if (!$("[data-guess-next]"))
          U.main.insertAdjacentHTML(
            "beforeend",
            '<div class="next-area"><button class="btn" data-guess-next>Retry pair</button></div>',
          );
        else $("[data-guess-next]").textContent = "Retry pair";
      }
    } finally {
      if (requestId === guessRequest) {
        guessBusy = false;
        guessLoading = false;
        U.main.removeAttribute("aria-busy");
        $$("[data-guess-next]").forEach((b) => (b.disabled = false));
      }
      release();
    }
  }

  function renderGuess() {
    const release = U.holdHeight();
    U.main.innerHTML =
      gameTabs() +
      guessCounters(guess.records) +
      `${guess.rules_version === 1 ? '<div class="challenge-note guesser"><strong>Classic question</strong></div>' : ""}<div class="matchup">${guess.songs
        .map((song, i) => {
          const high =
              guess.answered &&
              guess.result.ratings[i] > guess.result.ratings[1 - i],
            chosen = guess.chosen === song.id;
          const overlay = guess.answered
            ? `<div class="score-reveal guess-elo ${high ? "score-win" : "score-loss"}"><small>${high ? "Higher Elo" : "Lower Elo"}</small><strong>${Math.round(guess.result.ratings[i])}</strong><b>${high ? "✓ Correct answer" : chosen ? "✕ Your pick" : ""}</b></div>`
            : "";
          const cover = U.mediaButton(
            {
              ...song,
              name: song.title,
              artist: song.artists.map((a) => a.name).join(", "),
            },
            "guess-audio-" + i,
            false,
            !guess.answered,
          );
          return `${i ? '<span class="vs-circle">VS</span>' : ""}<article class="game-card dashboard-surface ${guess.answered ? (high ? "guess-right-card" : "guess-wrong-card") : ""}"><div class="match-cover">${cover}${overlay}</div><h2><a class="song" title="${esc(song.title)}" href="/song/${song.id}">${esc(song.title)}</a></h2><div class="game-meta"><div class="game-artists">${artistLinks(song)}</div>${song.album && song.album.trim().toLowerCase() !== "unknown album" && !/\s-\s*single\s*$/i.test(song.album) ? `<a class="album" title="${esc(song.album)}" href="/album/${encodeURIComponent(song.album)}">${esc(song.album)}</a>` : ""}</div><button class="btn primary vote-btn" data-guess-pick="${song.id}" ${guess.answered ? "disabled" : ""}>${guess.answered ? (chosen ? (guess.result.correct ? "✓ Correct · +1" : "✕ Wrong pick") : high ? "✓ Correct answer" : "Lower Elo") : "Higher Elo"}</button></article>`;
        })
        .join(
          "",
        )}</div>${guess.answered ? `<section class="panel guess-feedback dashboard-surface ${guess.result.correct ? "guess-success" : "guess-failure"}"><strong role="status">${guess.result.correct ? "✓ Correct · +1 point" : "✕ Incorrect · +0 points · streak reset"}</strong><span>Next pair automatically…</span><button class="btn" data-guess-next>Next pair →</button><small id="reveal-audio-note"></small></section>` : ""}`;
    U.attachPlayers();
    window.PreviewPlayback?.preloadPair([
      $("#guess-audio-0"),
      $("#guess-audio-1"),
    ]);
    if (guess.answered)
      $$(".match-cover .cover-button").forEach((b) => (b.disabled = true));
    release();
  }

  async function answerGuess(id) {
    if (guessBusy || !guess || guess.answered) return;
    guessBusy = true;
    $$("[data-guess-pick]").forEach((b) => (b.disabled = true));
    let saved = false;
    const current = guess,
      requestGeneration = reveal.generation;
    try {
      const result = await U.api("/api/elo-guesser/answer", {
        token: current.token,
        song_id: id,
      });
      saved = true;
      if (
        guess !== current ||
        reveal.closed ||
        requestGeneration !== reveal.generation
      )
        return;
      window.PreviewPlayback?.hold();
      cancelReveal();
      guess.answered = true;
      guess.chosen = id;
      guess.result = result;
      guess.records = result.records;
      renderGuess();
      const generation = reveal.generation,
        correct = guess.songs[result.ratings[0] > result.ratings[1] ? 0 : 1];
      snippet(correct, wait("guessClip", 2800), generation);
      flow?.prepare("guesser", (signal) =>
        U.api("/api/elo-guesser/round", {}, undefined, { signal }),
      );
      if (await revealDelay(wait("pairResult", 4500), generation)) loadGuess();
    } catch (error) {
      U.toast(error.message);
      if (!saved) $$("[data-guess-pick]").forEach((b) => (b.disabled = false));
    } finally {
      guessBusy = false;
    }
  }

  let shelfPlayback = null;
  function stopShelf(keepAudio = false) {
    previewGeneration++;
    loopRequested = false;
    playingSlot = null;
    clearTimeout(previewTimer);
    shelfPlayback = null;
    const a = $("#shelf-preview-audio");
    if (a && !keepAudio) {
      if (window.PreviewPlayback) window.PreviewPlayback.cancel(a);
      else a.pause();
    }
    markPlayback();
  }
  function markPlayback() {
    $$("[data-shelf-slot]").forEach((row) => {
      row.classList.toggle(
        "selected",
        Number(row.dataset.shelfSlot) === selectedSlot,
      );
      row.classList.toggle(
        "is-playing",
        Number(row.dataset.shelfSlot) === playingSlot && loopRequested,
      );
    });
    const button = $("[data-shelf-play]");
    if (button) {
      button.textContent = loopRequested
        ? "Ⅱ Pause previews"
        : "▶ Play previews";
      button.setAttribute("aria-pressed", String(loopRequested));
    }
  }
  function currentShelfPlayback(state) {
    return !!state && shelfPlayback === state && state.generation === previewGeneration &&
      state.audio === $("#shelf-preview-audio") && loopRequested && !state.advanced;
  }
  function scheduleShelf(state) {
    clearTimeout(previewTimer);
    if (!currentShelfPlayback(state) || !state.ready || state.audio.paused || state.audio.seeking) return;
    const remaining = 10 - state.audio.currentTime;
    if (remaining <= 0) { advanceShelf(state); return; }
    previewTimer = setTimeout(() => {
      if (!currentShelfPlayback(state)) return;
      // A stalled or sought clip must earn its remaining media time, not wall time.
      if (state.audio.currentTime >= 10) advanceShelf(state);
      else scheduleShelf(state);
    }, Math.max(100, remaining * 1000));
  }
  async function playShelf(slot) {
    if (!shelf) return;
    const available = shelf.songs.filter((s) => s.audio_url);
    if (!available.length) return;
    const song = available.find((s) => s.slot === slot) || available[0];
    // Shelves owns one player. A manual jump also stops pending/fading old clips.
    stopShelf();
    let audio = $("#shelf-preview-audio");
    if (!audio) return;
    selectedSlot = song.slot;
    playingSlot = song.slot;
    loopRequested = true;
    const url = window.PreviewPlayback?.source(song.id, song.audio_url) || song.audio_url;
    const previousAudio = audio;
    if (window.PreviewPlayback) audio = window.PreviewPlayback.replace(audio, url);
    else {audio.src = url; audio.currentTime = 0;}
    audio.preload = "none";
    audio.loop = false;
    audio.dataset.songId = song.id;
    // cloneNode copies data attributes but does not copy event listeners.
    if (audio !== previousAudio) delete audio.dataset.shelfBound;
    const state = {audio, slot: song.slot, generation: previewGeneration, ready: false, advanced: false};
    shelfPlayback = state;
    bindShelfAudio();
    markPlayback();
    try {
      await (window.PreviewPlayback ? window.PreviewPlayback.play(audio) : audio.play());
      if (!currentShelfPlayback(state)) return;
      state.ready = true;
      $("#shelf-preview-info").textContent = song.title;
      markPlayback();
      scheduleShelf(state);
    } catch (error) {
      if (!currentShelfPlayback(state) || error.name === "AbortError") return;
      stopShelf();
      U.toast(error.name === "PreviewBlockedError" ? error.message : "Preview unavailable. Choose another track.");
    }
  }
  function advanceShelf(state = shelfPlayback) {
    if (!currentShelfPlayback(state) || !state.ready || !shelf || state.audio.seeking) return;
    state.advanced = true;
    clearTimeout(previewTimer);
    const available = shelf.songs.filter((s) => s.audio_url),
      at = available.findIndex((s) => s.slot === state.slot);
    if (available.length) void playShelf(available[(at + 1) % available.length].slot);
  }
  function bindShelfAudio() {
    const audio = $("#shelf-preview-audio");
    if (audio.dataset.shelfBound) return;
    audio.dataset.shelfBound = "true";
    const current = () => shelfPlayback?.audio === audio && currentShelfPlayback(shelfPlayback);
    for (const event of ["playing", "seeked"]) audio.addEventListener(event, () => {
      if (current()) scheduleShelf(shelfPlayback);
      markPlayback();
    });
    audio.addEventListener("timeupdate", () => {
      if (current() && audio.currentTime >= 10) advanceShelf(shelfPlayback);
    });
    audio.addEventListener("ended", () => {
      if (current() && audio.ended) advanceShelf(shelfPlayback);
    });
    for (const event of ["waiting", "seeking", "pause"]) audio.addEventListener(event, () => {
      if (!current()) return;
      clearTimeout(previewTimer);
      if (event === "pause") $$("[data-shelf-slot]").forEach(row => row.classList.remove("is-playing"));
    });
    audio.addEventListener("error", () => {
      if (current() && !window.PreviewPlayback?.isPending()) {
        stopShelf();
        U.toast("Preview unavailable. Try another track.");
      }
    });
  }

  async function loadShelf(fresh = false) {
    if (shelfBusy || reveal.closed) return;
    const previous = shelf;
    shelfBusy = true;
    cancelReveal();
    stopShelf();
    U.stopAudio();
    shelf = null;
    selectedSlot = null;
    U.pageTone("shelves");
    document.body.classList.remove("game-page");
    const generation = reveal.generation,
      release = U.holdHeight();
    if (!previous)
      U.main.innerHTML =
        '<div class="page-head"><h1 class="shelves">Album Shelves</h1></div><div id="shelf-content"><div class="empty" role="status">Loading shelves…</div></div>';
    $$("[data-shelf-next],[data-shelf-play],[data-shelf-retry]").forEach(
      (b) => (b.disabled = true),
    );
    U.main.setAttribute("aria-busy", "true");
    $("#shelf-load-error")?.remove();
    try {
      const load = (signal) =>
        U.api(
          "/api/album-shelves/round",
          { album_count: 0, fresh: false },
          undefined,
          { signal },
        );
      const result = await (flow ? flow.take("shelves", load) : load());
      if (generation !== reveal.generation || reveal.closed) return;
      shelf = {
        ...result,
        placements: Object.fromEntries(
          result.albums.map((a) => [String(a.slot), []]),
        ),
        pool: result.songs.map((s) => s.slot),
        answered: false,
        revealed: new Set(),
      };

      $("#shelf-content").innerHTML =
        `<div class="shelf-actions"><button class="btn primary" data-shelf-check>Check shelves</button><button class="btn primary shelf-next" data-shelf-next hidden>Next round →</button><div id="shelf-order-score" class="shelf-order-score" hidden role="status"></div><span id="shelf-reveal-progress" class="shelf-reveal-progress" role="status"></span><div id="shelf-perfect" class="shelf-perfect" role="status" hidden><span aria-hidden="true">✦</span><div><strong>Perfect shelves</strong><small>All albums and track orders correct</small></div></div><small id="reveal-audio-note"></small></div><div class="shelf-audio-bar panel dashboard-surface"><span class="shelf-preview-duration">10-second samples</span><button class="btn primary" data-shelf-play aria-pressed="false" ${shelf.songs.some((s) => s.audio_url) ? "" : "disabled"}>▶ Play previews</button><span id="shelf-preview-info" role="status">${shelf.songs.filter((s) => s.audio_url).length} / 10 previews</span><audio id="shelf-preview-audio" preload="none"></audio></div><div id="shelf-board"></div>`;
      renderShelfBoard();
      bindShelfAudio();
    } catch (error) {
      if (generation === reveal.generation && !reveal.closed) {
        $("#shelf-content").insertAdjacentHTML(
          "beforeend",
          `<div id="shelf-load-error"><p class="error" role="alert">${esc(error.message)}</p><button class="btn" data-shelf-retry>Retry loading</button></div>`,
        );
      }
    } finally {
      if (generation === reveal.generation) {
        shelfBusy = false;
        U.main.removeAttribute("aria-busy");
      }
      release();
    }
  }

  function positionShelfPicker(picker) {
    const menu = picker.querySelector(".shelf-picker-options"),
      rect = picker.querySelector("summary").getBoundingClientRect(),
      below = window.innerHeight - rect.bottom - 12;
    const up = below < Math.min(menu.scrollHeight, 220) && rect.top > below;
    menu.style.top = up ? "auto" : "calc(100% + 6px)";
    menu.style.bottom = up ? "calc(100% + 6px)" : "auto";
    menu.style.maxHeight =
      Math.max(60, Math.min(300, up ? rect.top - 12 : below)) + "px";
  }
  function shelfPicker(song, where) {
    const chosen = shelf.albums.find((a) => String(a.slot) === where),
      title = chosen?.title || "Unsorted";
    const option = (target, title, art) =>
      `<button type="button" role="menuitemradio" aria-checked="${where === target}" data-shelf-pick="${song.slot}" data-shelf-target="${target}"><span class="shelf-option-art">${art || "⠿"}</span><span>${esc(title)}</span><b aria-hidden="true">${where === target ? "✓" : ""}</b></button>`;
    return `<details class="shelf-picker"><summary aria-label="Album for ${esc(song.title)}" aria-haspopup="menu" title="${esc(title)}"><span>${esc(title)}</span><b aria-hidden="true">⌄</b></summary><div class="shelf-picker-options" role="menu" aria-label="Choose album for ${esc(song.title)}">${option("pool", "Unsorted", "")}${shelf.albums.map((a) => option(String(a.slot), a.title, U.artwork({ name: a.title, cover_url: a.cover_url }, "albums"))).join("")}</div></details>`;
  }
  function shelfTrack(slot, where, index, length) {
    const song = shelf.songs.find((s) => s.slot === slot),
      answer = shelf.result?.items.find((i) => i.item_slot === slot),
      revealed = shelf.revealed.has(slot);
    const full =
        answer &&
        answer.album_correct &&
        (!answer.order_pairs || answer.order_right === answer.order_pairs),
      truth = shelf.result?.answers.find((a) => a.slot === slot);
    const errorDepth = revealed && !full
      ? (!answer.album_correct || !answer.order_pairs ? 1 : Math.max(0, Math.min(1, 1 - answer.order_right / answer.order_pairs)))
      : 0;
    const truthPosition = truth ? window.SongRankerUI.trackPosition(truth, true) : "";
    const status = full
      ? "✓ Correct"
      : !answer?.album_correct
        ? "✕ Wrong album"
        : "✕ Order error";
    const submittedAlbum =
        answer && shelf.albums.find((a) => a.slot === answer.answer_slot),
      corrected = revealed && !full;
    const positionLabel = corrected
      ? `Your shelf position ${answer.answer_position} on ${submittedAlbum?.title || "another album"}; correct ${truthPosition}`
      : revealed
        ? truthPosition
        : "Shelf position";
    const actualPosition = revealed
      ? `<span class="shelf-position-actual" title="${esc(truthPosition)}">${esc(window.SongRankerUI.trackPosition(truth))}</span>`
      : "";
    const position = corrected
      ? `<del title="Your submitted shelf position">${answer.answer_position}</del>${actualPosition}`
      : revealed
        ? actualPosition
        : where === "pool"
          ? "⠿"
          : index + 1;
    const feedback = revealed
      ? `<div class="shelf-revealed-answer"><strong class="${full ? "answer-correct" : "answer-wrong"}">${status}</strong><span>${answer.order_pairs ? `${answer.order_right} / ${answer.order_pairs} order comparisons` : "No order comparisons"}</span><b class="shelves">${num(answer.points)} / ${answer.available} points</b></div>`
      : "";
    return `<div class="shelf-track ${shelf.answered ? "reveal-track" : ""} ${revealed ? (full ? "answer-correct" : "answer-wrong") : "reveal-pending"}" data-shelf-slot="${slot}" ${revealed && !full ? `style="--shelf-error-depth:${errorDepth.toFixed(4)}"` : ""} ${revealed ? `data-correct-track="${truth.track_number}"` : ""} tabindex="0" draggable="${!shelf.answered}"><div class="shelf-track-title"><span class="shelf-position ${corrected ? "shelf-position-corrected" : ""}" aria-label="${esc(positionLabel)}">${position}</span>${revealed ? `<a class="song" title="${esc(song.title)}" href="/song/${song.id}">${esc(song.title)}</a>` : `<b class="song" title="${esc(song.title)}">${esc(song.title)}</b>`}<button class="preview-track" data-shelf-preview="${slot}" aria-label="Play ${esc(song.title)}" ${song.audio_url && (!shelf.answered || shelf.revealComplete) ? "" : "disabled"}>▶</button></div>${feedback}${shelf.answered ? "" : `<div class="shelf-track-controls">${shelfPicker(song, where)}${where === "pool" ? "" : `<button class="shelf-arrow" data-shelf-shift="${slot}" data-direction="-1" aria-label="Move ${esc(song.title)} up" ${index === 0 ? "disabled" : ""}>↑</button><button class="shelf-arrow" data-shelf-shift="${slot}" data-direction="1" aria-label="Move ${esc(song.title)} down" ${index === length - 1 ? "disabled" : ""}>↓</button>`}</div>`}</div>`;
  }
  function shelfAlbumScore(album) {
    const answers = shelf.result.answers.filter(
        (a) => a.album_slot === album.slot,
      ),
      items = answers.map((a) =>
        shelf.result.items.find((i) => i.item_slot === a.slot),
      );
    const available = items.reduce((total, item) => total + item.available, 0),
      points = items.reduce(
        (total, item) =>
          total + (shelf.revealed.has(item.item_slot) ? item.points : 0),
        0,
      );
    return `<div class="shelf-cover-score"><small id="shelf-album-label-${album.slot}">${shelf.scoredAlbums?.has(album.slot) ? "Added to total" : "Album points"}</small><strong id="shelf-album-score-${album.slot}">${num(points)}</strong><span>/ ${available}</span><b class="shelf-point-gain" id="shelf-album-gain-${album.slot}" aria-label="Latest revealed points"></b></div>`;
  }
  function renderShelfBoard() {
    if (!shelf) return;
    $("#shelf-board").innerHTML =
      `<div class="shelf-columns ${shelf.albums.length === 2 ? "two" : ""}">${shelf.albums.map((a) => `<section class="panel shelf-column dashboard-surface" data-shelf-album="${a.slot}" data-score-added="${!!shelf.scoredAlbums?.has(a.slot)}"><div class="shelf-column-head"><div class="shelf-album-art">${U.artwork({ name: a.title, cover_url: a.cover_url }, "albums")}${shelf.answered ? shelfAlbumScore(a) : ""}</div><h2 class="album" title="${esc(a.title)}">${esc(a.title)}</h2>${a.disc_count > 1 ? `<small class="metadata">${a.disc_count} discs · one album shelf</small>` : ""}</div><div class="shelf-drop" data-shelf-drop="${a.slot}">${shelf.placements[a.slot].length ? shelf.placements[a.slot].map((slot, i, list) => shelfTrack(slot, String(a.slot), i, list.length)).join("") : '<div class="shelf-empty">Drop tracks here</div>'}</div></section>`).join("")}</div>${shelf.answered ? "" : `<section class="panel shelf-pool dashboard-surface"><div class="section-head"><h2>Unsorted</h2><b class="shelves">${shelf.pool.length} / 10</b></div><div class="shelf-pool-grid" data-shelf-drop="pool">${shelf.pool.map((slot, i, list) => shelfTrack(slot, "pool", i, list.length)).join("") || "<p>All ten tracks placed</p>"}</div></section>`}`;
    $("[data-shelf-check]").disabled = !!shelf.pool.length || shelf.answered;
    markPlayback();
  }

  function moveShelf(slot, where, before = null) {
    if (
      !shelf ||
      shelf.answered ||
      !shelf.songs.some((s) => s.slot === slot) ||
      (where !== "pool" && !Object.hasOwn(shelf.placements, where))
    )
      return;
    shelf.pool = shelf.pool.filter((s) => s !== slot);
    Object.keys(shelf.placements).forEach(
      (k) =>
        (shelf.placements[k] = shelf.placements[k].filter((s) => s !== slot)),
    );
    const list = where === "pool" ? shelf.pool : shelf.placements[where],
      at = list.indexOf(before);
    list.splice(at < 0 ? list.length : at, 0, slot);
    selectedSlot = slot;
    renderShelfBoard();
  }
  function shiftShelf(slot, direction) {
    if (!shelf || shelf.answered) return;
    const list = Object.values(shelf.placements).find((ids) =>
      ids.includes(slot),
    );
    if (!list) return;
    const at = list.indexOf(slot),
      to = at + direction;
    if (to < 0 || to >= list.length) return;
    [list[at], list[to]] = [list[to], list[at]];
    selectedSlot = slot;
    renderShelfBoard();
    $(`[data-shelf-slot="${slot}"]`)?.focus();
  }
  async function revealShelfRound() {
    const current = shelf,
      generation = reveal.generation;
    // Follow the visible album order. Keep unrounded saved points until display.
    const groups = current.albums.map((album) => ({
      album,
      answers: current.result.answers
        .filter((a) => a.album_slot === album.slot)
        .sort((a, b) => (a.disc_number || 1) - (b.disc_number || 1) || a.track_number - b.track_number),
    }));
    const answers = groups.flatMap((group) => group.answers);
    let points = 0,
      index = 0;
    current.scoredAlbums = new Set();
    const albumPoints = Object.fromEntries(
        current.albums.map((a) => [a.slot, 0]),
      ),
      button = $("[data-shelf-check]");
    button.classList.add("shelf-score-counter");
    button.innerHTML = `<span>Total points</span><strong id="shelf-running-score">0.00</strong><small>/ ${current.result.available}</small>`;
    for (let albumIndex = 0; albumIndex < groups.length; albumIndex++) {
      const group = groups[albumIndex],
        albumNode = $(`[data-shelf-album="${group.album.slot}"]`);
      albumNode.dataset.revealActive = "true";
      for (
        let trackIndex = 0;
        trackIndex < group.answers.length;
        trackIndex++, index++
      ) {
        if (generation !== reveal.generation || reveal.closed) return;
        const truth = answers[index],
          slot = truth.slot,
          item = current.result.items.find((i) => i.item_slot === slot),
          old = $(`[data-shelf-slot="${slot}"]`);
        old.classList.add("reveal-closing");
        if (!(await revealDelay(wait("shelfClose", 420), generation))) return;
        current.revealed.add(slot);
        const destination = $(`[data-shelf-drop="${truth.album_slot}"]`);
        destination.querySelector(".shelf-empty")?.remove();
        const holder = document.createElement("div");
        holder.innerHTML = shelfTrack(
          slot,
          String(truth.album_slot),
          index,
          answers.length,
        );
        const row = holder.firstElementChild;
        old.remove();
        destination.insertBefore(
          row,
          destination.querySelector(".shelf-track:not([data-correct-track])"),
        );
        row.classList.add("reveal-opening");
        const previousAlbum = albumPoints[truth.album_slot];
        albumPoints[truth.album_slot] += item.points;
        $("#shelf-album-gain-" + truth.album_slot).textContent =
          "+" + num(item.points) + " points";
        U.animateScore(
          $("#shelf-album-score-" + truth.album_slot),
          previousAlbum,
          albumPoints[truth.album_slot],
          2,
          () => generation === reveal.generation && !reveal.closed,
        );
        $("#shelf-reveal-progress").textContent =
          `Album ${albumIndex + 1} / ${groups.length} · Track ${trackIndex + 1} / ${group.answers.length}`;
        await shelfAnswerAudio(
          current.songs.find((s) => s.slot === slot),
          generation,
        );
        if (!(await revealDelay(wait("shelfTrack", 2600), generation))) return;
        row.classList.remove("reveal-opening");
      }
      if (generation !== reveal.generation || reveal.closed) return;
      const previous = points;
      points += albumPoints[group.album.slot];
      albumNode.dataset.revealActive = "false";
      albumNode.classList.add("shelf-score-transfer");
      button.classList.add("shelf-score-transfer");
      $("#shelf-album-label-" + group.album.slot).textContent =
        "Adding to total";
      $("#shelf-reveal-progress").textContent =
        `Album ${albumIndex + 1} / ${groups.length} · +${num(albumPoints[group.album.slot])} points`;
      U.animateScore(
        $("#shelf-running-score"),
        previous,
        points,
        2,
        () => generation === reveal.generation && !reveal.closed,
      );
      if (
        !(await revealDelay(
          matchMedia("(prefers-reduced-motion: reduce)").matches
            ? 350
            : wait("shelfTransfer", 1250),
          generation,
        ))
      )
        return;
      current.scoredAlbums.add(group.album.slot);
      albumNode.dataset.scoreAdded = "true";
      $("#shelf-album-label-" + group.album.slot).textContent =
        "Added to total";
      albumNode.classList.remove("shelf-score-transfer");
      button.classList.remove("shelf-score-transfer");
    }
    current.placements = Object.fromEntries(
      current.albums.map((a) => [
        String(a.slot),
        answers.filter((t) => t.album_slot === a.slot).map((t) => t.slot),
      ]),
    );
    current.revealComplete = true;
    renderShelfBoard();
    $("#shelf-running-score").textContent = num(current.result.points);
    retireShelfClip(generation);
    const order = $("#shelf-order-score");
    order.innerHTML = `<small>Track order</small><strong>${pct(current.result.order_right, current.result.order_pairs)}</strong>`;
    order.hidden = false;
    $(".shelf-actions").classList.add("shelf-results-ready");
    const perfect = $("#shelf-perfect");
    perfect.hidden = !(current.result.available > 0 && Math.abs(current.result.points - current.result.available) < 1e-8);
    $("#shelf-reveal-progress").textContent =
      `${answers.length} / ${answers.length} tracks revealed`;
    $("[data-shelf-next]").hidden = false;
    $("[data-shelf-play]").disabled = !current.songs.some((s) => s.audio_url);
    shelfBusy = false;
  }

  async function checkShelf() {
    if (shelfBusy || !shelf || shelf.answered || shelf.pool.length) return;
    const current = shelf,
      generation = reveal.generation;
    shelfBusy = true;
    $("[data-shelf-check]").disabled = true;
    let saved = false;
    try {
      const result = await U.api("/api/album-shelves/answer", {
        token: current.token,
        placements: current.placements,
      });
      saved = true;
      current.answered = true;
      current.result = result;
      if (
        shelf !== current ||
        generation !== reveal.generation ||
        reveal.closed
      )
        return;
      stopShelf(true);
      window.PreviewPlayback?.hold();
      cancelReveal();
      renderShelfBoard();
      $("[data-shelf-play]").disabled = true;
      flow?.prepare("shelves", (signal) =>
        U.api(
          "/api/album-shelves/round",
          { album_count: 0, fresh: false },
          undefined,
          { signal },
        ),
      );
      await revealShelfRound();
    } catch (error) {
      U.toast(error.message);
      if (!saved && $("[data-shelf-check]"))
        $("[data-shelf-check]").disabled = false;
    } finally {
      if (!saved) shelfBusy = false;
    }
  }

  // Keep a single meaningful ordering per mode; detailed breakdowns live in Stats.
  function metrics(mode) {
    return [
      mode === "guesser"
        ? [
            "accuracy",
            "Accuracy",
            "guess_correct",
            "guess_attempts",
            "percentage",
          ]
        : mode === "shelves"
          ? [
              "order",
              "Track order",
              "shelf_order_right",
              "shelf_order_pairs",
              "percentage",
            ]
          : mode === "trivia"
            ? [
                "recognition",
                "Recognisability",
                "recognition_correct",
                "recognition_score",
                "trivia",
              ]
            : ["points", "Points", "tournament_points", null, "decimal"],
    ];
  }

  function entityRows(mode, type) {
    const songs = U.records("songs");
    return U.records(type)
      .filter((r) => type !== "albums" || U.properAlbum(r))
      .map((r) => {
        const tracks =
          type === "songs"
            ? [r]
            : songs.filter((s) =>
                type === "artists"
                  ? s.artist_ids.includes(r.id)
                  : type === "tags"
                    ? (s.tag_ids || []).includes(r.id)
                    : s.album_id === r.id,
              );
        const t = totals(tracks),
          recognitionAvailable = tracks.reduce(
            (n, s) => n + Number(s.available_points || 0),
            0,
          );
        return {
          ...r,
          ...t,
          recognition_correct: tracks.reduce(
            (n, s) => n + Number(s.correct || 0),
            0,
          ),
          recognition_score: recognitionAvailable,
          tournament_appearances: tracks.reduce(
            (n, s) => n + Number(s.tournament_appearances || 0),
            0,
          ),
          ...Object.fromEntries(
            [
              "championships",
              "runner_ups",
              "third_places",
              "podiums",
              "tournament_wins",
              "tournament_points",
            ].map((key) => [
              key,
              tracks.reduce((n, s) => n + Number(s[key] || 0), 0),
            ]),
          ),
        };
      });
  }
  function rankingValue(row, m) {
    return m[4] === "percentage" || m[4] === "trivia"
      ? row[m[3]]
        ? (100 * row[m[2]]) / row[m[3]]
        : null
      : Number(row[m[2]] || 0);
  }
  let rankingState = null,
    devRecordMode = "guesser";
  function renderModeRanking(mode, init = false) {
    if (init) {
      const p = new URLSearchParams(location.search),
        context = $("#mode-ranking-context")
          ? JSON.parse($("#mode-ranking-context").textContent)
          : {};
      rankingState = {
        mode,
        type:
          context.entity ||
          (["songs", "artists", "albums", "tags"].includes(p.get("entity"))
            ? p.get("entity")
            : "songs"),
        metric: p.get("metric") || metrics(mode)[0][0],
        bottom: p.get("view") === "bottom",
      };
    }
    const r = rankingState,
      list = metrics(mode),
      m = list.find((m) => m[0] === r.metric) || list[0];
    r.metric = m[0];
    const tone = mode === "trivia" ? "recognition" : mode;
    U.pageTone(tone);
    document.body.classList.add(
      "rankings-page",
      "standard-rankings-page",
      "mode-rankings-page",
    );
    document.body.style.setProperty("--rank-color", `var(--${tone})`);
    const eligible = entityRows(mode, r.type)
      .filter((row) =>
        mode === "guesser"
          ? row.guess_attempts
          : mode === "shelves"
            ? row.shelf_attempts
            : mode === "trivia"
              ? row.recognition_score
              : row.tournament_appearances,
      )
      .filter((row) => rankingValue(row, m) !== null);
    eligible.sort(
      (a, b) =>
        rankingValue(b, m) - rankingValue(a, m) ||
        (mode === "tournament"
          ? b.podiums - a.podiums || b.tournament_wins - a.tournament_wins
          : 0) ||
        (m[3]
          ? b[m[3]] - a[m[3]]
          : b.tournament_appearances - a.tournament_appearances) ||
        a.name.localeCompare(b.name),
    );
    const rows = (r.bottom ? [...eligible].reverse() : eligible).slice(0, 20),
      titles = {
        guesser: "Elo Guesser",
        shelves: "Album Shelves",
        trivia: "Recognisability",
        tournament: "Tournament",
      };
    const facts = (row) =>
      mode === "guesser"
        ? [
            `${row.guess_correct} correct · ${row.guess_attempts - row.guess_correct} wrong`,
            `${row.guess_attempts} appearances`,
          ]
        : mode === "shelves"
          ? [
              `${row.shelf_order_right} / ${row.shelf_order_pairs} order comparisons`,
              `${row.shelf_attempts} track appearances`,
            ]
          : mode === "trivia"
            ? [
                `${row.recognition_correct} / ${row.recognition_score} fields correct`,
              ]
            : [
                `${num(row.podiums)} podium credit`,
                `${num(row.tournament_wins)} win credit · ${num(row.tournament_appearances)} entry credit`,
              ];
    U.main.innerHTML = `<div class="page-head"><h1 class="${tone}">${titles[mode]} Rankings</h1></div>${window.SongRankerUI.modeRankingControls("/mode_rankings/" + mode, r.type, r.bottom, "special")}${mode === "tournament" ? '<p class="muted">Scope-weighted credit: library 100%, tags 50%; artist/album results share caps of 2%/0.5% of broader entry credit.</p>' : ""}<div class="leaderboard">${rows.map((row, i) => window.SongRankerUI.modeRankingRow(U, row, r.type, i, eligible.length, r.bottom, tone, m[4] === "number" ? rankingValue(row, m) : m[4] === "decimal" ? num(rankingValue(row, m)) : rankingValue(row, m).toFixed(2) + "%", m[1], facts(row))).join("") || '<div class="empty">No results for this category yet</div>'}</div>`;
    history.replaceState(
      {},
      "",
      `/mode_rankings/${mode}?entity=${r.type}&view=${r.bottom ? "bottom" : "top"}`,
    );
  }
  async function renderDevRecords(mode = "guesser") {
    devRecordMode = mode;
    const node = $("#dev-main");
    if (!node) return;
    node.innerHTML =
      '<div class="empty" data-mode-record-loader="' +
      mode +
      '">Loading records…</div>';
    try {
      const d = await U.api("/api/special-modes/stats");
      if (
        !node.isConnected ||
        node.querySelector("[data-mode-record-loader]")?.dataset
          .modeRecordLoader !== mode
      )
        return;
      const section = (mode, rows) =>
        `<section class="panel special-panel ${mode} mode-records"><div class="section-head"><h2 class="${mode}">${mode === "guesser" ? "Elo Guesser" : "Album Shelves"}</h2><button class="btn small danger" data-tool="Reset ${mode === "guesser" ? "Elo Guesser" : "Album Shelves"} history">Reset history</button></div><div class="mode-record-search"><input type="search" data-mode-history-search="${mode}" placeholder="Find round ID or song…" aria-label="Find ${mode} round"></div><div class="data-scroll"><table class="mode-record-table"><thead><tr><th>Round</th><th>Completed</th><th>Result / tracks</th><th>Actions</th></tr></thead><tbody>${
          rows
            .map((r) => {
              const labels =
                mode === "guesser"
                  ? [r.song1_id, r.song2_id]
                      .map(
                        (id) =>
                          U.records("songs").find((s) => s.id === id)?.title ||
                          "Deleted track",
                      )
                      .join(" vs ")
                  : (r.song_ids || [])
                      .map(
                        (id) =>
                          U.records("songs").find((s) => s.id === id)?.title ||
                          "Deleted track",
                      )
                      .join(", ");
              return `<tr data-special-history="${mode}" data-history-query="${esc((r.id + " " + labels).toLowerCase())}"><td>#${r.id}</td><td><small>${new Date(r.completed_at * 1000).toLocaleString()}</small></td><td><b class="${mode}">${mode === "guesser" ? (r.correct ? "Correct +1" : "Incorrect +0") : num(r.points) + " / " + r.available}</b><small class="record-track-names" title="${esc(labels)}">${esc(labels)}</small></td><td><button class="btn small danger" data-remove-special="${mode}" data-round="${r.id}">Delete round</button></td></tr>`;
            })
            .join("") || '<tr><td colspan="4">No completed rounds</td></tr>'
        }</tbody></table></div></section>`;
      node.innerHTML =
        `<div class="page-head"><h2 class="${mode}">${mode === "guesser" ? "Elo Guesser" : "Album Shelves"} Records</h2><small>Latest 30</small></div>` +
        section(mode, mode === "guesser" ? d.guess_history : d.shelf_history);
    } catch (error) {
      node.innerHTML = `<div class="empty error">${esc(error.message)}</div>`;
    }
  }
  document.addEventListener("click", async (e) => {
    $$(".shelf-picker[open]").forEach((picker) => {
      if (!picker.contains(e.target)) picker.open = false;
    });
    if (!U) return;
    const b = e.target.closest("button");
    if (!b || b.disabled) return;
    if (b.dataset.guessPick) await answerGuess(Number(b.dataset.guessPick));
    if (b.hasAttribute("data-guess-next")) await loadGuess();
    if (b.hasAttribute("data-shelf-play")) {
      if (loopRequested) stopShelf();
      else playShelf(selectedSlot);
    }
    if (b.dataset.shelfPreview) {
      const slot = Number(b.dataset.shelfPreview);
      if (loopRequested && playingSlot === slot) stopShelf();
      else playShelf(slot);
    }
    if (b.dataset.shelfPick) {
      const slot = Number(b.dataset.shelfPick);
      moveShelf(slot, b.dataset.shelfTarget);
      $(`[data-shelf-slot="${slot}"] .shelf-picker summary`)?.focus();
    }
    if (b.dataset.shelfShift)
      shiftShelf(Number(b.dataset.shelfShift), Number(b.dataset.direction));
    if (b.hasAttribute("data-shelf-check")) await checkShelf();
    if (b.hasAttribute("data-shelf-retry")) await loadShelf();
    if (b.hasAttribute("data-shelf-next") && shelf?.revealComplete)
      await loadShelf(true);
    if (b.dataset.specialEntity) {
      rankingState.type = b.dataset.specialEntity;
      renderModeRanking(rankingState.mode);
    }
    if (b.dataset.specialView) {
      rankingState.bottom = b.dataset.specialView === "bottom";
      renderModeRanking(rankingState.mode);
    }
    if (b.dataset.removeSpecial) {
      if (
        !confirm(
          "Delete this saved round? Create a backup first if you need a restore point.",
        )
      )
        return;
      try {
        await U.api(
          "/api/dev/special-round/" +
            b.dataset.removeSpecial +
            "/" +
            b.dataset.round,
          {},
        );
        await U.refreshData();
        await renderDevRecords(devRecordMode);
        U.toast("Round deleted");
      } catch (error) {
        U.toast(error.message);
      }
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.dataset.modeHistorySearch) {
      const mode = e.target.dataset.modeHistorySearch,
        q = e.target.value.toLowerCase().trim();
      $$(`[data-special-history="${mode}"]`).forEach(
        (r) => (r.hidden = !r.dataset.historyQuery.includes(q)),
      );
    }
  });
  document.addEventListener("focusout", (e) => {
    const picker = e.target.closest(".shelf-picker");
    if (picker && !picker.contains(e.relatedTarget)) picker.open = false;
  });
  document.addEventListener(
    "toggle",
    (e) => {
      if (e.target.matches(".shelf-picker") && e.target.open)
        positionShelfPicker(e.target);
    },
    true,
  );
  window.addEventListener("resize", () =>
    $$(".shelf-picker[open]").forEach((picker) => (picker.open = false)),
  );
  document.addEventListener("dragstart", (e) => {
    const row = e.target.closest("[data-shelf-slot]");
    if (row && shelf && !shelf.answered) {
      dragged = Number(row.dataset.shelfSlot);
      e.dataTransfer?.setData("text/plain", String(dragged));
      row.classList.add("dragging");
    }
  });
  document.addEventListener("dragover", (e) => {
    const zone = e.target.closest("[data-shelf-drop]");
    if (zone && shelf && !shelf.answered) {
      e.preventDefault();
      zone.classList.add("dragover");
    }
  });
  document.addEventListener("dragleave", (e) => {
    const zone = e.target.closest("[data-shelf-drop]");
    if (zone && !zone.contains(e.relatedTarget))
      zone.classList.remove("dragover");
  });
  document.addEventListener("drop", (e) => {
    const zone = e.target.closest("[data-shelf-drop]");
    if (!zone || dragged === null || !shelf || shelf.answered) return;
    e.preventDefault();
    const row = e.target.closest("[data-shelf-slot]"),
      before = row ? Number(row.dataset.shelfSlot) : null;
    if (before !== dragged) moveShelf(dragged, zone.dataset.shelfDrop, before);
    dragged = null;
  });
  document.addEventListener("dragend", () => {
    dragged = null;
    $$(".dragover,.dragging").forEach((e) =>
      e.classList.remove("dragover", "dragging"),
    );
  });
  document.addEventListener("keydown", (e) => {
    const picker = e.target.closest(".shelf-picker");
    if (picker) {
      const options = [...picker.querySelectorAll("[data-shelf-pick]")];
      if (e.key === "Escape") {
        e.preventDefault();
        picker.open = false;
        picker.querySelector("summary").focus();
        return;
      }
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
        e.preventDefault();
        picker.open = true;
        positionShelfPicker(picker);
        const at = options.indexOf(e.target),
          direction = e.key === "ArrowUp" ? -1 : 1;
        const target =
          e.key === "Home"
            ? 0
            : e.key === "End"
              ? options.length - 1
              : at < 0
                ? Math.max(
                    0,
                    options.findIndex(
                      (b) => b.getAttribute("aria-checked") === "true",
                    ),
                  )
                : (at + direction + options.length) % options.length;
        options[target]?.focus();
        return;
      }
    }
    const row = e.target.closest("[data-shelf-slot]");
    if (row && e.target === row && ["ArrowUp", "ArrowDown"].includes(e.key)) {
      e.preventDefault();
      shiftShelf(Number(row.dataset.shelfSlot), e.key === "ArrowUp" ? -1 : 1);
    }
  });
  document.addEventListener("preview-blocked", () => {
    stopShelf();
    cancelShelfClips();
    reveal.audio?.pause();
  });
  document.addEventListener("visibilitychange", () => {
    if (
      document.hidden &&
      U &&
      ["guesser", "shelves"].includes(document.body.dataset.page)
    ) {
      U.stopAudio();
      stopShelf();
    }
  });
  window.addEventListener("pagehide", () => {
    reveal.closed = true;
    cancelReveal();
    stopShelf();
  });
  window.addEventListener("pageshow", (e) => {
    if (e.persisted && U) {
      reveal.closed = false;
      guessBusy = false;
      guessLoading = false;
      shelfBusy = false;
      if (document.body.dataset.page === "guesser") loadGuess();
      if (document.body.dataset.page === "shelves") {
        if (shelf?.answered) {
          if (!shelf.revealComplete) {
            shelf.revealed.clear();
            renderShelfBoard();
            shelfBusy = true;
            revealShelfRound().catch((error) => U.toast(error.message));
          }
        } else loadShelf();
      }
    }
  });
  return {
    bindUI: (ui) => (U = ui),
    panels,
    homeSummary,
    homeBanners,
    loadGuess,
    loadShelf,
    renderModeRanking,
    renderDevRecords,
    cancelGuess: () => {
      guessRequest++;
      guessBusy = false;
    },
    totals,
  };
})();
