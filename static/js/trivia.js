window.songRankerTriviaLoaded = true;
(async () => {
  const { $, esc } = window.SongRankerUI,
    root = $("#trivia-root"),
    flow = window.RoundFlow;
  const later = (fn, ms) => (flow ? flow.after(fn, ms) : setTimeout(fn, ms)),
    cancelLater = (handle) =>
      typeof handle === "function" ? handle() : clearTimeout(handle);
  const order = ["title", "artist", "album"],
    names = { title: "Song", artist: "Artist", album: "Album" },
    colours = { title: "song", artist: "artist", album: "album" },
    weights = { title: 50, artist: 20, album: 30 };
  let state,
    active = false,
    busy = false,
    paused = false,
    loading = false,
    closed = false,
    tick,
    nextTimer,
    anchor = 0,
    baseElapsed = 0,
    generation = 0;
  const pending = new Map(),
    animations = new Set();
  async function api(path, data, signal) {
    const controller = new AbortController(),
      abort = () => controller.abort(),
      timeout = setTimeout(abort, 12000);
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) abort();
    try {
      const r = await fetch(path, {
        method: data === undefined ? "GET" : "POST",
        headers: { "Content-Type": "application/json" },
        body: data === undefined ? undefined : JSON.stringify(data),
        signal: controller.signal,
      });
      let result;
      try {
        result = await r.json();
      } catch {
        throw Error(
          `Trivia request failed (HTTP ${r.status}). Check the app terminal, then retry.`,
        );
      }
      if (!r.ok) throw Error(result.message || "Could not save this round.");
      return result;
    } catch (e) {
      if (e.name === "AbortError")
        throw Error("Trivia request timed out. Retry the round.");
      throw e;
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
    }
  }
  const path = (action) => "/api/trivia/" + state.token + "/" + action;
  const audio = () => $("#trivia-audio");
  const previewPlay = (a) =>
    window.PreviewPlayback ? window.PreviewPlayback.play(a) : a.play();
  const fields = () => order.filter((f) => state.fields[f]);
  function error(e) {
    const n = $("#trivia-error");
    if (n) {
      n.textContent = e.message;
      n.hidden = false;
    }
  }
  function volume() {
    const value = Number($("#volume-range")?.value ?? 0.5);
    if (audio()) audio().volume = value;
  }
  function remaining() {
    return Math.max(
      0,
      30 - baseElapsed - (paused ? 0 : (performance.now() - anchor) / 1000),
    );
  }
  function answerLinks(f, v) {
    if (Array.isArray(v.links) && !v.links.length)
      return `<span class="${colours[f]}">${esc(v.actual)}</span>`;
    const links = v.links?.length
      ? v.links
      : [
          {
            name: v.actual,
            url:
              f === "title"
                ? "/song/" + state.song_id
                : f === "album"
                  ? "/album/" + encodeURIComponent(v.actual)
                  : "/artist/" + encodeURIComponent(v.actual),
          },
        ];
    return links
      .map(
        (link) =>
          `<a class="${colours[f]}" href="${esc(link.url)}" title="${esc(link.name)}">${esc(link.name)}</a>`,
      )
      .join('<span class="muted">, </span>');
  }
  function flip(f, input, v) {
    if (input.dataset.graded) return;
    input.dataset.graded = "true";
    input.value = v.actual || "";
    const host = input.parentElement.querySelector(".answer-flip"),
      links = input.parentElement.querySelector(".answer-links");
    links.innerHTML = answerLinks(f, v);
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const reveal = () => {
      if (!input.isConnected) return;
      host.hidden = true;
      links.hidden = false;
      input.classList.remove("flipping");
      input.classList.add("linked-answer");
      input.tabIndex = -1;
    };
    if (reduced) {
      reveal();
      return;
    }
    host.innerHTML = Array.from(v.actual || "")
      .map(
        (c, i) =>
          `<span style="--delay:${Math.min(i * (flow?.duration("triviaFlip") === 600 ? 20 : 45), flow?.duration("triviaFlip") === 600 ? 250 : 800)}ms">${esc(c === " " ? "\u00a0" : c)}</span>`,
      )
      .join("");
    host.hidden = false;
    input.classList.add("flipping");
    const timer = setTimeout(
      () => {
        animations.delete(timer);
        reveal();
      },
      flow?.duration("triviaFlip") || 1550,
    );
    animations.add(timer);
  }
  function sync(s, timing = true) {
    if (state?.completed && !s.completed) return;
    for (const [f, v] of Object.entries(state?.fields || {}))
      if (v.correct !== null && s.fields[f]?.correct === null) s.fields[f] = v;
    if (!timing)
      s = {
        ...state,
        fields: s.fields,
        round_points: Math.max(state.round_points, s.round_points),
      };
    state = s;
    if (timing) {
      baseElapsed = s.elapsed;
      anchor = performance.now();
      paused = s.paused;
    }
    $("#trivia-score").textContent = Number(s.score).toFixed(2);
    $("#trivia-streak").textContent = s.streak + " 🔥";
    $("#trivia-best").textContent = Number(s.high_score).toFixed(2);
    $("#trivia-best-streak").textContent = s.high_streak + " 🔥";
    const target =
      {
        any: "Any answer",
        title_or_album: "Song or album",
        title_and_album: "Song + album",
        title: "Song",
      }[s.streak_rule] || "Any answer";
    $("#trivia-requirement").textContent = "Streak target: " + target;
    for (const f of fields()) {
      const v = s.fields[f],
        n = $("#guess-" + f);
      if (v.correct === null) continue;
      n.readOnly = true;
      n.classList.remove("checking");
      n.classList.add(v.correct ? "correct" : "wrong");
      $("#mark-" + f).textContent = v.correct ? "✓" : "×";
      flip(f, n, v);
    }
    $("#round-points").textContent = "+" + Number(s.round_points).toFixed(2);
  }
  function guesses() {
    return Object.fromEntries(fields().map((f) => [f, $("#guess-" + f).value]));
  }
  function setEnabled() {
    if (!state || !$("#trivia-start")) return;
    for (const f of order) {
      const n = $("#guess-" + f);
      n.disabled =
        !state.fields[f] ||
        ((!active || paused) && state.fields[f].correct === null);
    }
    const b = $("#trivia-start");
    b.textContent = paused ? "Resume" : active ? "Pause" : "Start round";
    b.disabled = busy || loading || state.completed;
    $("#trivia-finish").disabled = busy || !active || paused || state.completed;
  }
  function record(label, id, kind) {
    return `<div class="stat ${kind}"><span class="stat-label">${label}</span><strong class="stat-value" id="${id}"></strong></div>`;
  }
  async function load(auto = false) {
    if (loading || closed) return;
    loading = true;
    const gen = ++generation;
    $("#trivia-next")?.setAttribute("disabled", "");
    clearInterval(tick);
    cancelLater(nextTimer);
    animations.forEach(clearTimeout);
    animations.clear();
    if (auto) window.PreviewPlayback?.hold();
    else audio()?.pause();
    pending.clear();
    active = false;
    busy = true;
    paused = false;
    try {
      const get = (signal) => api("/api/trivia/round", undefined, signal);
      const next = await (flow ? flow.take("trivia", get) : get());
      if (closed || gen !== generation) return;
      state = next;
      root.innerHTML = `<div class="page-head trivia-heading"><h1 class="recognition">Trivia</h1></div><section class="panel recognition-panel trivia-round dashboard-surface"><div class="challenge-note recognition"><strong>${state.rules_version === 1 ? "Classic round" : "Challenge"}</strong><span id="trivia-requirement" role="status"></span></div><div class="trivia-clock" role="timer"><div><span id="trivia-timer-bar"></span></div><b id="trivia-seconds">30s</b></div><div class="trivia-stage"><div class="trivia-current" aria-label="Current run">${record("Current score", "trivia-score", "recognition")}${record("Streak", "trivia-streak", "recognition")}</div><div class="trivia-centre"><button id="trivia-start" class="mystery-cover" aria-label="Start or pause trivia">Start round</button><img id="trivia-cover" class="mystery-cover" alt="Album artwork" hidden><strong class="recognition" id="round-points" aria-live="polite">+0.00</strong></div><div class="trivia-best" aria-label="Personal best">${record(state.rules_version === 1 ? "Classic best score" : "Challenge best score", "trivia-best", "recognition")}${record(state.rules_version === 1 ? "Classic best streak" : "Challenge best streak", "trivia-best-streak", "recognition")}</div></div><audio id="trivia-audio" data-song-id="${state.song_id}" src="${esc(window.PreviewPlayback?.source(state.song_id, state.audio_url) || state.audio_url)}" preload="none"></audio><form id="trivia-guesses">${order
        .map((f) => {
          const available = !!state.fields[f];
          return `<div class="field trivia-field ${available ? "" : "not-applicable"}"><label class="${colours[f]}" for="guess-${f}">${names[f]}${available ? ` <small>${state.album_available ? weights[f] : Math.round(weights[f] / 0.7)}%</small>` : ""}</label><div class="guess-wrap"><input id="guess-${f}" name="${f}" autocomplete="off" placeholder="${available ? "Guess the " + names[f].toLowerCase() + "…" : ""}" ${available ? "" : 'disabled aria-label="Album, not applicable"'}><span class="field-mark" id="mark-${f}" aria-live="polite"></span><div class="answer-flip" aria-hidden="true" hidden></div><div class="answer-links" hidden></div></div></div>`;
        })
        .join(
          "",
        )}</form><div class="trivia-controls"><button type="button" class="btn" id="trivia-finish">Reveal answers</button></div><p class="error" id="trivia-error" role="alert" hidden></p><div id="trivia-result" aria-live="polite" hidden></div></section>`;
      window.PreviewPlayback?.bind(audio());
      volume();
      sync(state);
      active = state.started && !state.completed;
      setEnabled();
      for (const f of fields()) {
        const n = $("#guess-" + f);
        n.addEventListener("blur", () => {
          if (active && !paused && n.value.trim()) mark(f);
        });
        n.addEventListener("keydown", async (e) => {
          if (e.key !== "Enter") return;
          e.preventDefault();
          await mark(f);
          if (!active) return;
          const next = fields().find((k) => state.fields[k].correct === null);
          if (next) $("#guess-" + next).focus();
          else await finish();
        });
      }
      $("#trivia-start").onclick = () => (active ? pause() : start());
      $("#trivia-finish").onclick = () => finish();
      $("#trivia-guesses").onsubmit = (e) => e.preventDefault();
      bindTriviaAudio(audio());
      tick = setInterval(updateTimer, 100);
      if (active && !paused) {
        const resumed = await api(path("pause"), { paused: true });
        if (closed || gen !== generation) return;
        sync(resumed);
      }
      loading = false;
      busy = false;
      setEnabled();
      if (auto && !document.hidden) await start();
    } catch (e) {
      if (closed || gen !== generation) return;
      clearInterval(tick);
      window.PreviewPlayback?.stopAll();
      root.innerHTML =
        '<div class="panel recognition-panel trivia-load-error"><p class="error" role="alert">' +
        esc(e.message) +
        '</p><button class="btn recognition" id="trivia-retry">Retry trivia ↻</button></div>';
      $("#trivia-retry").onclick = () => load(false);
    } finally {
      if (gen === generation) {
        loading = false;
        busy = false;
        setEnabled();
      }
    }
  }
  const triviaBound = new WeakSet();
  function bindTriviaAudio(a) {
    if (triviaBound.has(a)) return;
    triviaBound.add(a);
    a.addEventListener("ended", () => {
      if (a === audio() && active && !paused && remaining() <= 0) finish();
    });
    a.addEventListener("error", () => {
      if (a !== audio()) return;
      if (active && !paused) pause();
      error(Error("Preview unavailable. Try resuming this round."));
    });
  }
  function updateTimer() {
    if (!active || paused || busy || closed) return;
    const left = remaining();
    $("#trivia-seconds").textContent = Math.ceil(left) + "s";
    $("#trivia-timer-bar").style.width = (100 * left) / 30 + "%";
    if (left <= 0) finish();
  }
  async function start() {
    if (busy || loading || closed || state.completed) return;
    const gen = generation;
    busy = true;
    setEnabled();
    try {
      volume();
      if (window.PreviewPlayback) await window.PreviewPlayback.arm(audio());
      else {
        await previewPlay(audio());
        audio().pause();
      }
      const s = await api(
        path(paused ? "pause" : "start"),
        paused ? { paused: false } : {},
      );
      if (closed || gen !== generation) return;
      sync(s);
      active = true;
      paused = false;
      await previewPlay(audio());
      if (closed || gen !== generation) {
        audio()?.pause();
        return;
      }
      setEnabled();
      fields()
        .map((f) => $("#guess-" + f))
        .find((n) => !n.readOnly)
        ?.focus();
    } catch (e) {
      if (closed || gen !== generation) return;
      audio()?.pause();
      if (state.started) {
        try {
          const held = await api(path("pause"), { paused: true });
          if (!closed && gen === generation) {
            sync(held);
            active = true;
          }
        } catch (_) {}
      }
      if (!closed && gen === generation) error(e);
    } finally {
      if (gen === generation) {
        busy = false;
        setEnabled();
      }
    }
  }
  async function pause() {
    if (busy || !active || closed) return;
    if (paused) {
      await start();
      return;
    }
    const gen = generation;
    busy = true;
    audio()?.pause();
    try {
      const held = await api(path("pause"), { paused: true });
      if (!closed && gen === generation) sync(held);
    } catch (e) {
      if (!closed && gen === generation) error(e);
    } finally {
      if (gen === generation) {
        busy = false;
        setEnabled();
      }
    }
  }

  async function mark(f) {
    if (
      !active ||
      paused ||
      busy ||
      state.fields[f].correct !== null ||
      !$("#guess-" + f).value.trim()
    )
      return;
    if (pending.has(f)) return pending.get(f);
    const token = state.token,
      gen = generation;
    $("#guess-" + f).classList.add("checking");
    const job = (async () => {
      try {
        const s = await api("/api/trivia/" + token + "/field", {
          field: f,
          guess: $("#guess-" + f).value,
        });
        if (gen !== generation) return;
        sync(s, false);
        if (active && fields().every((k) => state.fields[k].correct !== null))
          await finish();
      } catch (e) {
        if (gen !== generation) return;
        error(e);
        $("#guess-" + f).classList.remove("checking");
      } finally {
        if (gen === generation) pending.delete(f);
      }
    })();
    pending.set(f, job);
    return job;
  }
  async function finish() {
    if (busy || !active || paused || closed) return;
    const snapshot = guesses(),
      gen = generation,
      token = state.token;
    busy = true;
    setEnabled();
    try {
      const s = await api("/api/trivia/" + token + "/finish", {
        guesses: snapshot,
      });
      if (closed || gen !== generation) return;
      sync(s);
      active = false;
      setEnabled();
      $("#trivia-start").hidden = true;
      $("#trivia-cover").src = s.cover_url || "";
      $("#trivia-cover").hidden = !s.cover_url;
      if (!s.cover_url) {
        $("#trivia-start").hidden = false;
        $("#trivia-start").textContent = "♫";
      }
      $("#trivia-result").hidden = false;
      $("#trivia-result").innerHTML =
        `<span class="${s.game_over ? "wrong" : "recognition"}">${s.game_over ? "Streak finished" : "Round complete"}</span><button class="btn" id="trivia-next">${s.game_over ? "Restart" : "Next round"} →</button>`;
      $("#trivia-next").onclick = () => load(true);
      if (window.PreviewPlayback) {
        const next = window.PreviewPlayback.replace(
          audio(),
          audio().getAttribute("src"),
        );
        bindTriviaAudio(next);
      } else audio().currentTime = 0;
      previewPlay(audio()).catch(() => {});
      if (!s.game_over)
        flow?.prepare("trivia", (signal) =>
          api("/api/trivia/round", undefined, signal),
        );
      nextTimer = later(
        () => {
          if (!s.game_over) load(true);
          else if (window.PreviewPlayback)
            window.PreviewPlayback.fadeOut(audio(), 600);
          else audio()?.pause();
        },
        flow?.duration("triviaResult") || 5500,
      );
    } catch (e) {
      if (!closed && gen === generation) error(e);
    } finally {
      if (gen === generation) {
        busy = false;
        setEnabled();
      }
    }
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && active) {
      e.preventDefault();
      pause();
    } else if (
      e.key === "Enter" &&
      !active &&
      !state?.completed &&
      !e.target.closest(
        "input,textarea,select,button,summary,form,a,[contenteditable]",
      )
    ) {
      e.preventDefault();
      start();
    }
  });
  document.addEventListener("input", (e) => {
    if (e.target.id === "volume-range") volume();
  });
  document.addEventListener("preview-blocked", () => {
    if (active && !paused) pause();
  });
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) {
      closed = false;
      loading = false;
      busy = false;
      load(false);
    }
  });
  window.addEventListener("pagehide", () => {
    closed = true;
    ++generation;
    clearInterval(tick);
    cancelLater(nextTimer);
    animations.forEach(clearTimeout);
    audio()?.pause();
    if (active && !paused)
      fetch(path("pause"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paused: true }),
        keepalive: true,
      }).catch(() => {});
  });
  await load();
})();
