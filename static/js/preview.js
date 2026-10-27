/* Shared ready-only preview handoffs. Audio caching lives in bounded app memory. */
(() => {
  "use strict";
  const bound = new WeakSet(),
    problems = new WeakMap(),
    players = new Set(),
    gains = new WeakMap(),
    fades = new WeakMap(),
    mixes = new WeakMap(),
    prepared = new Map();
  const FADE_MS = 1500,
    READY_TIMEOUT = 12000;
  let cooldown = 0,
    blockedMessage = "",
    hideTimer,
    serial = 0,
    pending = null,
    closed = false,
    tailId = 0,
    focusAudio = null;
  // A visible-time fade clock excludes even background time with no timer callbacks.
  let fadeHidden = 0,
    fadeHiddenAt = document.hidden ? performance.now() : null;
  function fadeClock() {
    const now = performance.now();
    return now - fadeHidden - (fadeHiddenAt === null ? 0 : now - fadeHiddenAt);
  }
  document.addEventListener("visibilitychange", () => {
    const now = performance.now();
    if (document.hidden) {
      if (fadeHiddenAt === null) fadeHiddenAt = now;
    } else if (fadeHiddenAt !== null) {
      fadeHidden += now - fadeHiddenAt;
      fadeHiddenAt = null;
    }
  });
  const newToken = () =>
    Date.now().toString(36) + "_" + Math.random().toString(36).slice(2);
  let token = newToken(),
    warmQueue = Promise.resolve(),
    warmLast = 0;
  const warmJobs = new Map();
  const notice = () => document.getElementById("preview-status");
  let volume = 0.5;
  try {
    const saved = Number(localStorage.getItem("siteVolume") ?? 0.5);
    if (Number.isFinite(saved)) volume = Math.max(0, Math.min(1, saved));
  } catch {}
  const level = () => volume;
  function setVolume(value) {
    const next = Number(value);
    if (!Number.isFinite(next)) return volume;
    volume = Math.max(0, Math.min(1, next));
    const input = document.getElementById("volume-range"),
      label = document.getElementById("volume-value");
    if (input) input.value = volume;
    if (label) label.textContent = Math.round(volume * 100) + "%";
    try {
      localStorage.setItem("siteVolume", String(volume));
    } catch {}
    syncVolume();
    return volume;
  }
  function show(message, state = "loading", seconds = 0) {
    const node = notice();
    if (!node) return;
    clearTimeout(hideTimer);
    node.textContent = message;
    node.dataset.state = state;
    node.hidden = false;
    if (seconds)
      hideTimer = setTimeout(() => (node.hidden = true), seconds * 1000);
  }
  function report(audio, ...args) {
    if (!focusAudio || focusAudio === audio) show(...args);
  }
  function paint(audio, state) {
    audio.dataset.previewState = state;
    document.querySelectorAll("[data-audio]").forEach((button) => {
      if (button.dataset.audio !== audio.id) return;
      button.dataset.previewState = state;
      button.setAttribute(
        "aria-busy",
        String(state === "loading" || state === "buffering"),
      );
    });
  }
  function urlRevision(url) {
    let value = 2166136261;
    for (const c of url) value = Math.imul(value ^ c.charCodeAt(0), 16777619);
    return (value >>> 0).toString(36);
  }
  function source(id, url) {
    try {
      const parsed = new URL(url, location.href),
        host = parsed.hostname.toLowerCase();
      if (
        id &&
        ["https:", "http:"].includes(parsed.protocol) &&
        !parsed.username &&
        !parsed.password &&
        ["", "80", "443"].includes(parsed.port) &&
        (host.endsWith(".itunes.apple.com") || host.endsWith(".mzstatic.com"))
      )
        return (
          "/api/previews/" +
          encodeURIComponent(id) +
          "?play=" +
          token +
          "&page=" +
          token +
          "&rev=" +
          urlRevision(parsed.href)
        );
    } catch {}
    return url || "";
  }
  function clipId(audio) {
    return /^\/api\/previews\/(\d+)$/.exec(
      new URL(audio.getAttribute("src") || "", location.href).pathname,
    )?.[1];
  }
  const aborted = () =>
    Object.assign(Error("Preview playback cancelled"), { name: "AbortError" });
  function setGain(audio, gain) {
    gains.set(audio, Math.max(0, Math.min(1, gain)));
    audio.volume = level() * gains.get(audio);
  }
  function syncVolume() {
    for (const audio of document.querySelectorAll("audio"))
      audio.volume = level() * (gains.get(audio) ?? 1);
  }
  function bank() {
    let root = document.getElementById("preview-audio-bank");
    if (!root) {
      root = document.createElement("div");
      root.id = "preview-audio-bank";
      root.hidden = true;
      document.body.append(root);
    }
    return root;
  }
  function dispose(audio) {
    if (!audio) return;
    fades.delete(audio);
    players.delete(audio);
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    audio.remove();
  }
  function retire(audio) {
    if (!audio) return;
    if (audio.paused || !audio.isConnected || !audio.getAttribute("src")) {
      dispose(audio);
      return;
    }
    audio.id = "preview-tail-" + ++tailId;
    audio.dataset.previewRetired = "true";
    audio.dataset.previewLoop = "";
    audio.loop = true;
    bank().append(audio);
  }
  function hold() {
    for (const audio of [...players])
      if (
        audio.isConnected &&
        !audio.paused &&
        audio.dataset.previewPrepared !== "true" &&
        !audio.dataset.previewRetired
      )
        retire(audio);
  }
  function prime(item) {
    if (!item || closed || Date.now() < cooldown) return null;
    if (typeof item !== "string") {
      bind(item);
      if (
        item.getAttribute("src") &&
        item.readyState < 3 &&
        item.dataset.previewPrimed !== item.getAttribute("src")
      ) {
        item.dataset.previewPrimed = item.getAttribute("src");
        item.preload = "auto";
        item.load();
      }
      return item;
    }
    if (prepared.has(item)) return prepared.get(item);
    const audio = document.createElement("audio");
    audio.src = item;
    audio.preload = "auto";
    audio.dataset.previewPrepared = "true";
    bank().append(audio);
    bind(audio);
    prepared.set(item, audio);
    audio.load();
    while (prepared.size > 2) {
      const key = prepared.keys().next().value;
      dispose(prepared.get(key));
      prepared.delete(key);
    }
    return audio;
  }
  function cacheControl(action, song_ids = [], page = token, leaving = false) {
    const body = JSON.stringify({ action, page, song_ids });
    if (leaving)
      try {
        if (
          navigator.sendBeacon?.(
            "/api/previews/cache",
            new Blob([body], { type: "application/json" }),
          )
        )
          return Promise.resolve();
      } catch {}
    const controller = new AbortController(),
      timer = setTimeout(() => controller.abort(), 2000);
    return fetch("/api/previews/cache", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      keepalive: true,
      signal: controller.signal,
    })
      .catch(() => {})
      .finally(() => clearTimeout(timer));
  }
  function warmDelay(ms, signal) {
    return new Promise((resolve, reject) => {
      const finish = () => {
        signal.removeEventListener("abort", cancel);
        resolve();
      };
      const timer = setTimeout(finish, ms),
        cancel = () => {
          clearTimeout(timer);
          signal.removeEventListener("abort", cancel);
          reject(aborted());
        };
      signal.addEventListener("abort", cancel, { once: true });
      if (signal.aborted) cancel();
    });
  }
  function warm(url) {
    if (warmJobs.has(url)) return warmJobs.get(url).promise;
    const controller = new AbortController(),
      job = { controller, promise: null };
    job.promise = warmQueue
      .catch(() => {})
      .then(async () => {
        if (closed || controller.signal.aborted) return false;
        // Space quiet pair downloads so two new clips respect the local CDN gate.
        const delay = Math.max(0, 650 - (Date.now() - warmLast));
        if (delay) await warmDelay(delay, controller.signal);
        if (closed || controller.signal.aborted) return false;
        warmLast = Date.now();
        const timer = setTimeout(() => controller.abort(), READY_TIMEOUT);
        try {
          const response = await fetch(url, {
            signal: controller.signal,
            cache: "no-store",
          });
          if (!response.ok) {
            await response.body?.cancel();
            return false;
          }
          // Consume a whole preview to fill the RAM cache; retain no second JS copy.
          if (response.body?.getReader) {
            const reader = response.body.getReader();
            let bytes = 0;
            try {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                bytes += value.byteLength;
                if (bytes > 4 * 1024 * 1024) {
                  await reader.cancel();
                  return false;
                }
              }
            } finally {
              reader.releaseLock();
            }
          } else await response.arrayBuffer();
          return !closed && !controller.signal.aborted;
        } finally {
          clearTimeout(timer);
        }
      })
      .catch(() => false);
    warmJobs.set(url, job);
    warmQueue = job.promise;
    while (warmJobs.size > 10) {
      const key = warmJobs.keys().next().value;
      warmJobs.get(key).controller.abort();
      warmJobs.delete(key);
    }
    return job.promise;
  }
  function preloadPair(audios) {
    for (const audio of [...players]) if (!audio.isConnected) dispose(audio);
    return Promise.all(
      [...audios].filter(Boolean).map(async (audio) => {
        const url = audio.getAttribute("src");
        if (!url || closed) return;
        audio.dataset.previewPair = "true";
        bind(audio);
        if (clipId(audio)) await warm(url);
        if (
          !closed &&
          audio.isConnected &&
          audio.getAttribute("src") === url &&
          audio.paused &&
          audio.dataset.previewWanted !== "true"
        )
          prime(audio);
      }),
    );
  }
  function forgetPair(audios) {
    const ids = new Set();
    for (const audio of [...audios].filter(Boolean)) {
      const url = audio.getAttribute("src"),
        id = clipId(audio);
      if (id) ids.add(Number(id));
      warmJobs.get(url)?.controller.abort();
      warmJobs.delete(url);
      if (prepared.has(url)) {
        dispose(prepared.get(url));
        prepared.delete(url);
      }
      dispose(audio);
    }
    return ids.size ? cacheControl("forget", [...ids]) : Promise.resolve();
  }
  function clearPage() {
    for (const job of warmJobs.values()) job.controller.abort();
    warmJobs.clear();
    warmQueue = Promise.resolve();
    warmLast = 0;
    for (const audio of [...players]) {
      if (audio.dataset.previewRetired || audio.dataset.previewPrepared)
        dispose(audio);
      else {
        audio.dataset.previewPageSource = audio.getAttribute("src") || "";
        audio.removeAttribute("src");
        audio.load();
        players.delete(audio);
      }
    }
    return cacheControl("clear", [], token, true);
  }
  function replace(audio, url) {
    let next = prepared.get(url);
    if (next) {
      prepared.delete(url);
      delete next.dataset.previewPrepared;
    } else if (!audio.paused || pending?.audio === audio) {
      next = audio.cloneNode(false);
      delete next.dataset.bound;
      delete next.dataset.previewRetired;
      delete next.dataset.previewPrimed;
    } else next = audio;
    if (next !== audio) {
      next.id = audio.id;
      next.loop = audio.loop;
      next.dataset.previewLoop = audio.dataset.previewLoop || "";
      audio.before(next);
      if (!audio.paused) retire(audio);
      else dispose(audio);
    }
    if (next.getAttribute("src") !== url) {
      next.src = url;
      delete next.dataset.previewPrimed;
    }
    next.currentTime = 0;
    bind(next);
    return next;
  }
  async function problem(audio) {
    if (problems.has(audio)) return problems.get(audio);
    const work = (async () => {
      let info = {
        state: "unavailable",
        message:
          "Preview could not load. Check the connection or refresh its URL in Dev.",
        retry_after: 0,
      };
      const id = clipId(audio);
      if (id) {
        const controller = new AbortController(),
          timer = setTimeout(() => controller.abort(), 4000);
        try {
          const response = await fetch("/api/previews/" + id + "/status", {
            signal: controller.signal,
            cache: "no-store",
          });
          if (response.ok) {
            const status = await response.json();
            if (
              status.state !== "unknown" &&
              status.state !== "streaming" &&
              status.state !== "cached"
            )
              info = status;
            else
              info.message =
                "Preview stream started but could not play. Check the connection or audio format.";
          }
        } catch {
        } finally {
          clearTimeout(timer);
        }
      }
      const seconds = Number(info.retry_after) || 0,
        blocked =
          ["rate_limited", "refused", "throttled"].includes(info.state) ||
          seconds > 0;
      if (blocked) {
        cooldown = Math.max(cooldown, Date.now() + seconds * 1000);
        blockedMessage =
          info.message || "Preview access paused. Try again shortly.";
        document.dispatchEvent(
          new CustomEvent("preview-blocked", { detail: info }),
        );
      }
      paint(audio, blocked ? "blocked" : "error");
      show(info.message || blockedMessage, blocked ? "blocked" : "error");
      return { ...info, blocked };
    })();
    problems.set(audio, work);
    try {
      return await work;
    } finally {
      problems.delete(audio);
    }
  }
  function recover(audio) {
    const tails = mixes.get(audio);
    if (!tails) return;
    mixes.delete(audio);
    fades.delete(audio);
    const keeper = [...tails].filter((a) => !a.paused && !a.error).at(-1);
    for (const previous of tails) {
      fades.delete(previous);
      if (previous === keeper) setGain(previous, 1);
      else {
        previous.pause();
        if (previous.dataset.previewRetired) dispose(previous);
      }
    }
    audio.pause();
    setGain(audio, 1);
    focusAudio = keeper || audio;
  }
  function bind(audio) {
    players.add(audio);
    if (bound.has(audio)) return;
    bound.add(audio);
    audio.addEventListener("loadstart", () => {
      if (audio.dataset.previewWanted === "true") {
        paint(audio, "loading");
        report(audio, "Loading preview…");
      }
    });
    audio.addEventListener("waiting", () => {
      audio.dataset.previewStalled = "true";
      if (audio.dataset.previewWanted === "true") {
        paint(audio, "buffering");
        report(audio, "Buffering preview…");
      }
    });
    audio.addEventListener("canplay", () => {
      delete audio.dataset.previewStalled;
      if (audio.dataset.previewWanted === "true") {
        paint(audio, audio.paused ? "ready" : "playing");
        report(
          audio,
          audio.paused ? "Preview ready" : "Preview playing",
          "ready",
          2,
        );
      }
    });
    audio.addEventListener("playing", () => {
      delete audio.dataset.previewStalled;
      paint(audio, "playing");
      report(audio, "Preview playing", "ready", 2);
    });
    audio.addEventListener("pause", () => {
      const tails = mixes.get(audio);
      if (tails) {
        mixes.delete(audio);
        fades.delete(audio);
        for (const previous of tails) {
          fades.delete(previous);
          previous.pause();
          if (previous.dataset.previewRetired) dispose(previous);
          else setGain(previous, 1);
        }
      }
      audio.dataset.previewWanted = "false";
      if (pending?.audio === audio) pending.cancel();
      if (!["blocked", "error"].includes(audio.dataset.previewState))
        paint(audio, "idle");
    });
    audio.addEventListener("ended", () => {
      if (audio.dataset.previewRetired) dispose(audio);
    });
    audio.addEventListener("error", () => {
      if (audio.getAttribute("src")) {
        recover(audio);
        problem(audio);
      }
    });
  }
  function fadeOut(audio, ms = FADE_MS) {
    if (!audio || audio.paused) return;
    const tails = mixes.get(audio);
    if (tails) {
      mixes.delete(audio);
      for (const previous of tails) fadeOut(previous, ms);
    }
    const tag = {},
      initial = gains.get(audio) ?? 1,
      started = fadeClock();
    fades.set(audio, tag);
    function step(now) {
      if (fades.get(audio) !== tag) return;
      const t = Math.min(1, (fadeClock() - started) / ms);
      setGain(audio, initial * (1 - t));
      if (t < 1) setTimeout(() => step(performance.now()), 25);
      else {
        fades.delete(audio);
        audio.pause();
        if (audio.dataset.previewRetired) dispose(audio);
        else setGain(audio, 1);
      }
    }
    setTimeout(() => step(performance.now()), 25);
  }
  function overlap(audio, outgoing) {
    const incomingTag = {},
      initial = new Map(),
      incomingGain = gains.get(audio) ?? 0;
    fades.set(audio, incomingTag);
    mixes.set(audio, new Set(outgoing));
    for (const previous of outgoing) {
      const tag = {};
      fades.set(previous, tag);
      initial.set(previous, { tag, gain: gains.get(previous) ?? 1 });
    }
    let elapsed = 0,
      last = performance.now();
    function step(now) {
      if (closed || fades.get(audio) !== incomingTag) return;
      if (audio.paused) {
        for (const [previous, { tag }] of initial)
          if (fades.get(previous) === tag) {
            fades.delete(previous);
            setGain(previous, 1);
          }
        return;
      }
      // Keep the outgoing sound available if the incoming stream stalls mid-fade.
      if (audio.dataset.previewStalled !== "true")
        elapsed += Math.max(0, now - last);
      last = now;
      const t = Math.min(1, elapsed / FADE_MS);
      setGain(audio, incomingGain + (1 - incomingGain) * t);
      for (const [previous, { tag, gain }] of initial) {
        if (fades.get(previous) !== tag) continue;
        setGain(previous, gain * (1 - t));
        if (t === 1) {
          fades.delete(previous);
          previous.pause();
          if (previous.dataset.previewRetired) dispose(previous);
          else setGain(previous, 1);
        }
      }
      if (t < 1) setTimeout(() => step(performance.now()), 25);
      else {
        fades.delete(audio);
        mixes.delete(audio);
      }
    }
    setTimeout(() => step(performance.now()), 25);
  }
  function waitReady(audio, work) {
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        clearTimeout(timer);
        for (const event of ["canplay", "playing", "progress", "error"])
          audio.removeEventListener(event, check);
      };
      const finish = (error) => {
        cleanup();
        error ? reject(error) : resolve();
      };
      const check = () => {
        if (audio.error) finish(Error("Preview unavailable"));
        else if (audio.readyState >= 3) finish();
      };
      const timer = setTimeout(
        () =>
          finish(
            Object.assign(Error("Preview buffering timed out"), {
              name: "PreviewTimeoutError",
            }),
          ),
        READY_TIMEOUT,
      );
      work.cancel = () => finish(aborted());
      for (const event of ["canplay", "playing", "progress", "error"])
        audio.addEventListener(event, check);
      check();
    });
  }
  async function play(audio) {
    bind(audio);
    if (closed) throw aborted();
    if (Date.now() < cooldown && audio.readyState < 3) {
      paint(audio, "blocked");
      show(blockedMessage, "blocked");
      throw Object.assign(Error(blockedMessage), {
        name: "PreviewBlockedError",
      });
    }
    if (pending) {
      const previous = pending;
      pending = null;
      previous.cancel?.();
      if (previous.audio !== audio) {
        previous.audio.pause();
        if (previous.audio.dataset.previewRetired) dispose(previous.audio);
      }
    }
    const id = ++serial,
      previousFocus = focusAudio;
    focusAudio = audio;
    for (const a of [...players]) if (!a.isConnected) dispose(a);
    const outgoing = [...players].filter(
      (a) => a !== audio && !a.paused && a.dataset.previewPrepared !== "true",
    );
    const loops = new Map(outgoing.map((a) => [a, a.dataset.loopRequested]));
    for (const a of outgoing) a.dataset.loopRequested = "false";
    const incomingGain = !audio.paused ? (gains.get(audio) ?? 1) : 0;
    for (const a of players) {
      fades.delete(a);
      mixes.delete(a);
    }
    setGain(audio, outgoing.length ? incomingGain : 1);
    if (audio.error) audio.load();
    const work = { audio, cancel: null };
    pending = work;
    audio.dataset.previewWanted = "true";
    paint(audio, audio.readyState >= 3 ? "ready" : "loading");
    if (audio.readyState < 3) show("Loading preview…");
    try {
      // Start inside the user gesture; fade only after native playback and readiness.
      const ready = waitReady(audio, work);
      ready.catch(() => {});
      const started = Promise.resolve(audio.play()).then(() => {
        // A readiness wait may already have rejected while native play() was
        // still pending. Its late success must not restart an obsolete element.
        if ((id !== serial && focusAudio !== audio) || closed || !audio.isConnected) {
          audio.pause();
          if (audio.dataset.previewRetired || !audio.isConnected) dispose(audio);
          throw aborted();
        }
      });
      await Promise.all([started, ready]);
      if (id !== serial || closed || !audio.isConnected) throw aborted();
      pending = null;
      paint(audio, "playing");
      if (outgoing.length) overlap(audio, outgoing);
      else setGain(audio, 1);
      show("Preview playing", "ready", 2);
    } catch (error) {
      work.cancel?.();
      if (pending === work) pending = null;
      // Native play() can resolve after cancellation. Silence only superseded
      // elements; the same element may already belong to a newer play request.
      if (id !== serial) {
        if (focusAudio !== audio) {
          audio.pause();
          if (audio.dataset.previewRetired || !audio.isConnected) dispose(audio);
        }
        throw aborted();
      }
      if (id === serial) {
        audio.pause();
        setGain(audio, 1);
        const keeper =
          outgoing.includes(previousFocus) && !previousFocus.paused
            ? previousFocus
            : outgoing.filter((a) => !a.paused && !a.error).at(-1);
        for (const a of outgoing) {
          if (a === keeper) {
            setGain(a, 1);
            if (loops.get(a)) a.dataset.loopRequested = loops.get(a);
          } else {
            a.pause();
            if (a.dataset.previewRetired) dispose(a);
          }
        }
        focusAudio = keeper || audio;
      }
      if (error.name === "NotAllowedError") {
        paint(audio, "idle");
        show("Press a cover or Play previews to start audio.", "error");
        throw error;
      }
      if (error.name === "AbortError") {
        paint(audio, "idle");
        throw error;
      }
      const info = await problem(audio);
      if (info.blocked)
        throw Object.assign(Error(info.message), {
          name: "PreviewBlockedError",
        });
      throw error;
    }
  }
  async function arm(audio) {
    bind(audio);
    focusAudio = audio;
    audio.dataset.previewWanted = "true";
    const id = serial,
      work = { audio, cancel: null };
    setGain(audio, 0);
    if (audio.readyState < 3) show("Loading preview…");
    try {
      const ready = waitReady(audio, work);
      ready.catch(() => {});
      await Promise.all([audio.play(), ready]);
      if (closed || id !== serial || !audio.isConnected) throw aborted();
    } finally {
      work.cancel?.();
      audio.pause();
      setGain(audio, 1);
    }
  }
  function abandon(audio) {
    if (pending?.audio === audio) {
      const work = pending;
      pending = null;
      serial++;
      work.cancel?.();
    }
    fades.delete(audio);
    audio?.pause();
    if (audio) setGain(audio, 1);
  }
  function cancel(audio) {
    stopAll();
  }
  function stopAll() {
    serial++;
    focusAudio = null;
    if (pending) {
      const work = pending;
      pending = null;
      work.cancel?.();
    }
    for (const a of [...players]) {
      fades.delete(a);
      a.pause();
      if (a.dataset.previewRetired || a.dataset.previewPrepared) dispose(a);
      else setGain(a, 1);
    }
    prepared.clear();
  }
  window.PreviewPlayback = {
    source,
    bind,
    play,
    arm,
    problem,
    prime,
    preloadPair,
    forgetPair,
    replace,
    hold,
    retire,
    release: dispose,
    fadeOut,
    abandon,
    cancel,
    stopAll,
    syncVolume,
    setVolume,
    getVolume: level,
    blocked: () => Date.now() < cooldown,
    isPending: () => !!pending,
    fadeMilliseconds: FADE_MS,
  };
  document.addEventListener("preview-blocked", stopAll);
  window.addEventListener("pagehide", () => {
    closed = true;
    stopAll();
    clearTimeout(hideTimer);
    clearPage();
  });
  window.addEventListener("pageshow", (event) => {
    closed = false;
    if (event.persisted) {
      token = newToken();
      for (const audio of document.querySelectorAll("audio")) {
        const url = audio.dataset.previewPageSource;
        delete audio.dataset.previewPageSource;
        if (!url) {
          bind(audio);
          continue;
        }
        const parsed = new URL(url, location.href);
        if (
          parsed.origin === location.origin &&
          /^\/api\/previews\/\d+$/.test(parsed.pathname)
        ) {
          parsed.searchParams.set("play", token);
          parsed.searchParams.set("page", token);
          audio.src = parsed.pathname + parsed.search;
        } else audio.src = url;
        bind(audio);
      }
      preloadPair(document.querySelectorAll("audio[data-preview-pair]"));
    }
  });
})();
