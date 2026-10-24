/* Vibe Map: one stable player, serial idempotent saves, continuous coordinates. */
(() => {
  "use strict";
  if (document.body.dataset.page !== "vibe_map") return;
  const { $, esc } = window.SongRankerUI,
    player = window.PreviewPlayback;
  const workspace = $("#vibe-workspace"),
    card = $("#vibe-song"),
    errorBox = $("#vibe-error");
  let round = null,
    index = 0,
    phase = "map",
    point = null,
    audio = null,
    loopWanted = false;
  let pending = null,
    inflight = false,
    advancing = false,
    dragging = false,
    closed = false,
    retry = null,
    failed = false;
  let deadline = 0,
    editTimer = null,
    advanceBody = null;
  const uid = () =>
    window.crypto?.randomUUID?.() ||
    Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  const currentMap = () => round.maps[index],
    saved = (id) => round.saved_maps.find((p) => p.map_id === id);
  const unsettled = () =>
    !!(
      pending ||
      inflight ||
      advancing ||
      dragging ||
      round?.draft ||
      editTimer ||
      failed
    );
  const allDone = () => round?.status === "complete";
  const image = (song, cls = "") =>
    song.cover_url
      ? `<img class="${cls}" src="${esc(song.cover_url)}" alt="">`
      : '<span class="vibe-art-fallback" aria-hidden="true">♫</span>';
  async function api(path, body) {
    const response = await fetch("/api/vibe-map/" + path, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok)
      throw Object.assign(
        Error(data.message || "Unable to save this map."),
        data,
      );
    return data;
  }
  function clearError() {
    errorBox.hidden = true;
    retry = null;
    failed = false;
  }
  function showError(error, action) {
    if (closed) return;
    failed = true;
    errorBox.hidden = false;
    errorBox.querySelector("span").textContent =
      error.message || "Connection lost. Retry to continue.";
    retry = action;
    $("#vibe-retry").hidden = !action;
    $("#vibe-reload").hidden = !round;
    controls();
  }
  const tagCountLabel = (song) => Array.isArray(song.tag_ids)
    ? `${song.tag_ids.length} ${song.tag_ids.length === 1 ? "tag" : "tags"}`
    : "Tags unavailable";
  function useRound(next) {
    round = next;
    const tags = $("#vibe-tag-count");
    if (tags) tags.textContent = tagCountLabel(next.song);
    deadline = next.draft ? performance.now() + next.remaining_ms : 0;
    advanceBody = null;
  }
  function controls() {
    if (!round) return;
    const locked = unsettled(),
      prev = $("#vibe-back"),
      next = $("#vibe-forward"),
      finish = $("#vibe-finish");
    if (prev) prev.disabled = locked || index === 0 || phase === "results";
    if (next)
      next.disabled =
        locked || index >= Math.min(3, round.map_index) || phase === "results";
    if (finish) {
      finish.textContent =
        phase === "results"
          ? "Next song →"
          : phase === "loading"
            ? "Loading…"
            : "Finish";
      finish.disabled = !allDone() || locked;
    }
    const status = $("#vibe-save-state");
    if (status) status.hidden = phase === "results" || phase === "loading";
    const plane = $("#vibe-plane");
    if (plane) plane.setAttribute("aria-disabled", String(advancing || failed));
  }
  function paintAudio() {
    const button = $("#vibe-play");
    if (!button || !audio) return;
    const playing = !audio.paused && !audio.ended;
    button.setAttribute("aria-pressed", String(playing));
    button.setAttribute(
      "aria-label",
      (playing ? "Pause " : "Play ") + round.song.title,
    );
    button.querySelector(".play-overlay").textContent = playing ? "Ⅱ" : "▶";
  }
  async function play() {
    const target = audio;
    try {
      await player.play(target);
      if (target !== audio || closed) {
        target.pause();
        return;
      }
      $("#vibe-audio-status").textContent = "";
      paintAudio();
    } catch (error) {
      if (target === audio) {
        loopWanted = false;
        paintAudio();
        if (error.name !== "AbortError")
          $("#vibe-audio-status").textContent =
            "Preview unavailable · tap to retry";
      }
    }
  }
  function mountSong() {
    const song = round.song;
    card.innerHTML = `<button class="vibe-cover" id="vibe-play" type="button" data-audio="vibe-audio" aria-label="Play ${esc(song.title)}" aria-pressed="false" ${song.audio_url ? "" : "disabled"}>${image(song)}<span class="play-overlay" aria-hidden="true">▶</span></button><div class="vibe-song-copy"><h2><a href="/song/${song.id}" title="${esc(song.title)}">${esc(song.title)}</a></h2><div class="vibe-identity"><div>${(song.artist_links || []).map((a) => `<a class="artist" href="/artist/${encodeURIComponent(a.name)}">${esc(a.name)}</a>`).join(", ") || `<span class="artist">${esc(song.artist || "Unknown artist")}</span>`}</div>${song.album ? `<a class="album" href="/album/${encodeURIComponent(song.album)}">${esc(song.album)}</a>` : ""}<span id="vibe-tag-count" class="tag">${esc(tagCountLabel(song))}</span></div><small id="vibe-audio-status" class="muted">${song.audio_url ? "" : "No preview available"}</small></div><div class="vibe-controls"><button class="btn" id="vibe-back" type="button" aria-label="Previous map">←</button><button class="btn vibe-primary" id="vibe-finish" type="button" disabled>Finish</button><button class="btn" id="vibe-forward" type="button" aria-label="Next map">→</button></div><div class="vibe-save-state" id="vibe-save-state"><p id="vibe-save-status" role="status" aria-live="polite"></p><div class="vibe-progress" aria-hidden="true"><span id="vibe-progress-fill"></span></div></div>`;
    // Mark bound so the generic page listener does not attach a second loop owner.
    audio = document.createElement("audio");
    audio.id = "vibe-audio";
    audio.dataset.songId = song.id;
    audio.dataset.bound = "true";
    audio.preload = "none";
    audio.loop = false;
    if (song.audio_url) audio.src = player.source(song.id, song.audio_url);
    card.append(audio);
    player.bind(audio);
    player.syncVolume();
    audio.addEventListener("play", paintAudio);
    audio.addEventListener("pause", paintAudio);
    audio.addEventListener("ended", () => {
      paintAudio();
      if (loopWanted && !document.hidden && !closed) {
        audio.currentTime = 0;
        void play();
      }
    });
    audio.addEventListener("error", () => {
      loopWanted = false;
      $("#vibe-audio-status").textContent =
        "Preview unavailable · tap to retry";
      paintAudio();
    });
    // A separate control avoids the generic delegated data-audio click handler.
    $("#vibe-play").addEventListener("click", (e) => {
      e.stopPropagation();
      if (!audio.paused && !audio.ended) {
        loopWanted = false;
        audio.pause();
      } else {
        loopWanted = true;
        void play();
      }
    });
    $("#vibe-back").addEventListener("click", () => navigate(-1));
    $("#vibe-forward").addEventListener("click", () => navigate(1));
    $("#vibe-finish").addEventListener("click", () => {
      if (allDone() && !unsettled()) {
        if (phase === "results") void nextSong();
        else showResults();
      }
    });
    if (song.audio_url) void player.preloadPair([audio]);
  }
  function coordinates() {
    const placed = point?.status === "placed",
      pin = $("#vibe-pin");
    if (pin) {
      pin.hidden = !placed;
      if (placed) {
        pin.style.left = (point.x + 5) * 10 + "%";
        pin.style.top = (5 - point.y) * 10 + "%";
      }
    }
    const plane = $("#vibe-plane");
    if (plane)
      plane.setAttribute(
        "aria-label",
        currentMap().title +
          ". " +
          (placed ? `X ${point.x.toFixed(2)}, Y ${point.y.toFixed(2)}. ` : "") +
          "Arrow keys move the pin; Shift makes larger moves.",
      );
  }
  function renderMap() {
    if (closed || !round) return;
    const map = currentMap();
    point =
      round.draft?.map_id === map.id
        ? { ...round.draft }
        : saved(map.id)
          ? { ...saved(map.id) }
          : null;
    workspace.classList.remove("vibe-results");
    workspace.innerHTML = `<div class="vibe-map-head"><h2 id="vibe-map-title">${esc(map.title)}</h2><div class="vibe-step"><span>Map ${index + 1} of ${round.maps.length}</span><span class="vibe-dots" aria-label="${round.saved_maps.length} of 4 maps saved">${round.maps.map((m, i) => `<i class="${saved(m.id) ? "saved " : ""}${i === index ? "current" : ""}"></i>`).join("")}</span></div></div><div class="vibe-plane-wrap"><div class="vibe-pole">${esc(map.y_high)}</div><div class="vibe-plane" id="vibe-plane" role="group" tabindex="0" aria-describedby="vibe-keyboard"><svg class="vibe-contours" viewBox="0 0 500 400" preserveAspectRatio="none" aria-hidden="true"><path class="axis" d="M250 0V400M0 200H500"/></svg><div class="vibe-axis-pulse" id="vibe-axis-pulse" aria-hidden="true"></div><span class="vibe-x-pole low">${esc(map.x_low)}</span><span class="vibe-x-pole high">${esc(map.x_high)}</span>${map.x_center ? `<span class="vibe-axis-center">${esc(map.x_center)}</span>` : ""}<div class="vibe-pin" id="vibe-pin" hidden>${round.song.cover_url ? image(round.song) : "<span>♫</span>"}</div></div><div class="vibe-pole">${esc(map.y_low)}</div></div><span class="sr-only" id="vibe-keyboard">Tap or drag to place. Arrow keys adjust by 0.05, Shift by 0.5.</span>`;
    const plane = $("#vibe-plane");
    const move = (e) => {
      const rect = plane.getBoundingClientRect();
      setPoint(
        Math.max(
          -5,
          Math.min(5, ((e.clientX - rect.left) / rect.width) * 10 - 5),
        ),
        Math.max(
          -5,
          Math.min(5, 5 - ((e.clientY - rect.top) / rect.height) * 10),
        ),
        false,
      );
    };
    plane.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || advancing || failed) return;
      e.preventDefault();
      plane.focus();
      dragging = true;
      plane.setPointerCapture?.(e.pointerId);
      move(e);
      controls();
    });
    plane.addEventListener("pointermove", (e) => {
      if (dragging) move(e);
    });
    const release = () => {
      if (!dragging) return;
      dragging = false;
      queueDraft();
      controls();
    };
    plane.addEventListener("pointerup", release);
    plane.addEventListener("pointercancel", release);
    plane.addEventListener("lostpointercapture", release);
    plane.addEventListener("keydown", (e) => {
      const dirs = {
        ArrowLeft: [-1, 0],
        ArrowRight: [1, 0],
        ArrowUp: [0, 1],
        ArrowDown: [0, -1],
      };
      if (!dirs[e.key] || advancing || failed) return;
      e.preventDefault();
      const [x, y] = dirs[e.key],
        step = e.shiftKey ? 0.5 : 0.05;
      setPoint(
        Math.max(-5, Math.min(5, (point?.x || 0) + x * step)),
        Math.max(-5, Math.min(5, (point?.y || 0) + y * step)),
      );
    });
    coordinates();
    controls();
    paintStatus();
  }
  function pulseAxes() {
    const pulse = $("#vibe-axis-pulse");
    if (
      !pulse ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    )
      return;
    pulse.classList.remove("pulsing");
    void pulse.offsetWidth;
    pulse.classList.add("pulsing");
  }
  function setPoint(x, y, debounce = true) {
    point = { status: "placed", x, y };
    coordinates();
    pulseAxes();
    deadline = 0;
    clearTimeout(editTimer);
    editTimer = null;
    if (debounce)
      editTimer = setTimeout(() => {
        editTimer = null;
        queueDraft();
      }, 200);
    controls();
    paintStatus();
  }
  function queueDraft() {
    clearTimeout(editTimer);
    editTimer = null;
    pending = {
      map_id: currentMap().id,
      request_id: uid(),
      point: { ...point },
    };
    deadline = 0;
    if (!inflight) void flushDraft();
    controls();
    paintStatus();
  }
  async function flushDraft(body = null) {
    if (closed || inflight || !round || (!body && !pending)) return;
    const draft = pending;
    if (!body) {
      pending = null;
      body = {
        token: round.token,
        revision: round.revision,
        map_id: draft.map_id,
        request_id: draft.request_id,
        status: draft.point.status,
        x: draft.point.x,
        y: draft.point.y,
      };
    }
    inflight = true;
    controls();
    paintStatus();
    try {
      const data = await api("draft", body);
      if (closed) return;
      useRound(data.round);
      clearError();
    } catch (error) {
      showError(error, () => flushDraft(body));
    } finally {
      inflight = false;
      controls();
      paintStatus();
    }
    if (pending && !failed && !closed) void flushDraft();
  }
  async function advance(body = null) {
    if (
      closed ||
      advancing ||
      inflight ||
      pending ||
      editTimer ||
      dragging ||
      failed ||
      !round.draft
    )
      return;
    body = body ||
      advanceBody || {
        token: round.token,
        revision: round.revision,
        map_id: round.draft.map_id,
        request_id: uid(),
      };
    advanceBody = body;
    advancing = true;
    controls();
    paintStatus();
    try {
      const data = await api("advance", body);
      if (closed) return;
      useRound(data.round);
      clearError();
      if (!allDone()) index = round.map_index;
      renderMap();
    } catch (error) {
      if (error.code === "readjusting") {
        deadline = performance.now() + error.remaining_ms;
      } else showError(error, () => advance(body));
    } finally {
      advancing = false;
      controls();
      paintStatus();
    }
  }
  function navigate(direction) {
    if (unsettled() || phase === "results") return;
    const next = index + direction;
    if (next < 0 || next > Math.min(3, round.map_index)) return;
    index = next;
    renderMap();
    $("#vibe-plane")?.focus();
  }
  function paintStatus() {
    const text = $("#vibe-save-status");
    if (!text) return;
    let status = "Place a pin to begin.";
    if (failed) status = "Save paused · retry to continue.";
    else if (advancing) status = "Saving map…";
    else if (dragging || pending || inflight || editTimer)
      status = "Adjusting pin…";
    else if (round.draft)
      status = `${round.draft.status === "not_applicable" ? "Saving N/A" : "Saving pin"} in ${Math.max(1, Math.ceil((deadline - performance.now()) / 1000))}s`;
    else if (allDone()) status = "All maps saved · finish when ready.";
    else if (saved(currentMap().id)) status = "Saved";
    if (text.textContent !== status) text.textContent = status;
    const fill = $("#vibe-progress-fill");
    if (fill)
      fill.style.width =
        round.draft && !pending && !inflight && !dragging
          ? Math.max(
              0,
              Math.min(100, 100 - (deadline - performance.now()) / 50),
            ) + "%"
          : "0%";
  }
  function showResults() {
    if (!allDone() || unsettled()) return;
    phase = "results";
    workspace.classList.add("vibe-results");
    try {
      sessionStorage.setItem("vibe-results-token", round.token);
    } catch {}
    workspace.innerHTML = `<h2>Your vibe map</h2>${window.VibeCharts.radar(round.summary.aggregate.radar, round.song.title + " · average vibe")}<h3>Similar songs</h3><div id="vibe-similar" class="vibe-similar" role="status">Finding matches…</div>`;
    controls();
    void matches(round.token);
  }
  async function matches(token) {
    try {
      const data = await api("similar/" + round.song.id);
      if (closed || round.token !== token || phase !== "results") return;
      const node = $("#vibe-similar");
      node.innerHTML =
        data.matches
          .map(
            (m) =>
              `<div class="vibe-match">${m.song.cover_url ? image(m.song) : '<span class="vibe-mini-art" aria-hidden="true"></span>'}<div><a href="/song/${m.song.id}" title="${esc(m.song.title)}">${esc(m.song.title)}</a><small title="${esc(m.song.artist)}">${esc(m.song.artist)}</small></div><strong>${m.similarity.toFixed(1)}%<small>${m.shared_maps}/4 maps</small></strong></div>`,
          )
          .join("") || '<p class="muted">Map another song to find a match.</p>';
    } catch (error) {
      if (!closed && round.token === token && phase === "results")
        $("#vibe-similar").innerHTML =
          '<p class="muted">Matches could not load.</p><button class="btn" id="vibe-retry-matches" type="button">Retry matches</button>';
      $("#vibe-retry-matches")?.addEventListener(
        "click",
        () => void matches(token),
      );
    }
  }
  async function load(body = {}) {
    try {
      const data = await api("round", body);
      if (closed) return;
      useRound(data.round);
      clearError();
      phase = "map";
      index = round.draft
        ? round.maps.findIndex((m) => m.id === round.draft.map_id)
        : Math.min(3, round.map_index);
      mountSong();
      $("#vibe-loading").hidden = true;
      $("#vibe-layout").hidden = false;
      let resultsRequested = false;
      try {
        resultsRequested =
          sessionStorage.getItem("vibe-results-token") === round.token;
      } catch {}
      if (allDone() && !round.draft && resultsRequested) showResults();
      else renderMap();
    } catch (error) {
      showError(error, () => load(body));
      $("#vibe-loading").hidden = true;
    }
  }
  async function nextSong() {
    if (unsettled() || !allDone()) return;
    const body = { previous_token: round.token };
    phase = "loading";
    advancing = true;
    controls();
    loopWanted = false;
    $("#vibe-play").disabled = true;
    try {
      await player.forgetPair([audio]);
      audio = null;
      await load(body);
    } catch (error) {
      showError(error, () => load(body));
    } finally {
      advancing = false;
      controls();
    }
  }
  $("#vibe-retry").addEventListener("click", () => {
    const action = retry;
    if (!action) return;
    clearError();
    void action();
  });
  $("#vibe-reload").addEventListener("click", () => {
    location.reload();
  });
  document.addEventListener("visibilitychange", () => {
    // Hidden tabs finish the current clip, but never initiate another loop.
    if (!document.hidden && audio?.ended && loopWanted && !closed) {
      audio.currentTime = 0;
      void play();
    }
  });
  const clock = setInterval(() => {
    const now = performance.now();
    if (closed || document.hidden || !round) return;
    if (
      round.draft &&
      deadline &&
      now >= deadline &&
      !failed &&
      !inflight &&
      !pending &&
      !dragging &&
      !editTimer
    )
      void advance();
    paintStatus();
  }, 100);
  const cardSize = () =>
    card.style.setProperty(
      "--vibe-card-height",
      card.getBoundingClientRect().height + "px",
    );
  const cardObserver = window.ResizeObserver
    ? new ResizeObserver(cardSize)
    : null;
  cardObserver?.observe(card);
  window.addEventListener("pagehide", () => {
    cardObserver?.disconnect();
    closed = true;
    clearInterval(clock);
    clearTimeout(editTimer);
    loopWanted = false;
  });
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) location.reload();
  });
  void load();
})();
