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
    focusAudio = null,
    armed = 0,
    background = null;
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
      if (audio.dataset.previewPrepared !== "true" && !armed) background?.foregroundPlayed(audio);
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
    background?.yieldToPreview();
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
    background?.yieldToPreview();
    bind(audio);
    focusAudio = audio;
    audio.dataset.previewWanted = "true";
    const id = serial,
      work = { audio, cancel: null };
    setGain(audio, 0);
    armed++;
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
      armed--;
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
    startBackground: ids => background?.startFrom(ids) || Promise.resolve(false),
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
  document.addEventListener("preview-blocked", () => {
    background?.suspend();
    stopAll();
  });
  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("background-previews");
    if (root) background = mountBackground(root);
  });
  window.addEventListener("pagehide", () => {
    closed = true;
    background?.leavePage();
    stopAll();
    clearTimeout(hideTimer);
    clearPage();
  });
  window.addEventListener("pageshow", (event) => {
    closed = false;
    if (event.persisted) {
      token = newToken();
      for (const audio of document.querySelectorAll("audio")) {
        if (audio.id === "background-audio") continue;
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
      background?.restorePage();
    }
  });

  function mountBackground(root) {
    const audio = root.querySelector("audio");
    const nowPlaying = root.querySelector("#background-now");
    const nowArt = nowPlaying.querySelector("img");
    const nowTitle = nowPlaying.querySelector("a");
    const nowArtist = nowPlaying.querySelector("[data-background-byline]");
    const nowAlbum = nowPlaying.querySelector("[data-background-album]");
    const nowRelation = nowPlaying.querySelector("[data-background-relation]");
    const progress = nowPlaying.querySelector("progress");
    const elapsed = nowPlaying.querySelector("time");
    const toggle = root.querySelector("#background-toggle");
    const skip = root.querySelector("#background-next");
    const status = root.querySelector("#background-state");
    const card = document.getElementById("background-track");
    const artwork = card.querySelector("img");
    const preference = "songRankerBackgroundPreviews";
    const handoffKey = "songRankerPreviewHandoff";
    const recent = [];
    const mixHistory = new Map();
    let preferenceValue = "auto";
    let catalogue = null, loading = null, track = null, anchor = null;
    let requested = false, starting = false, failures = 0, revision = 0;
    let wake, cardTimer, loadTimer, foregroundUntil = 0;
    let handoff = null, steps = 0, relation = "", counted = false;

    try {
      const saved = JSON.parse(localStorage.getItem(preference) || "{}");
      if (saved.preference === "paused") preferenceValue = "paused";
    } catch {}

    function remember() {
      try { localStorage.setItem(preference, JSON.stringify({preference: preferenceValue})); }
      catch {}
    }

    function leavePage() {
      try {
        if (requested) {
          sessionStorage.setItem(handoffKey, JSON.stringify({
            id: track?.id ?? handoff?.id,
            time: track ? audio.currentTime : handoff?.time,
            anchor: anchor?.id ?? handoff?.anchor,
            recent, mixHistory: [...mixHistory], steps, relation: track ? relation : handoff?.relation,
            counted: track ? counted : handoff?.counted,
          }));
        } else sessionStorage.removeItem(handoffKey);
      } catch {}
      suspend();
      track = null;
      anchor = null;
      nowPlaying.hidden = true;
      audio.removeAttribute("src");
      audio.load();
    }

    function restorePage() {
      let saved;
      try {
        saved = JSON.parse(sessionStorage.getItem(handoffKey) || "null");
        sessionStorage.removeItem(handoffKey);
      } catch {}
      try {
        const latest = JSON.parse(localStorage.getItem(preference) || "{}");
        preferenceValue = latest.preference === "paused" ? "paused" : "auto";
      } catch {}
      if (!saved || preferenceValue === "paused") {
        if (preferenceValue === "paused") showState("Paused");
        return;
      }
      handoff = saved;
      recent.splice(0, recent.length, ...(saved.recent || []).slice(-24));
      mixHistory.clear();
      for (const [type, last] of saved.mixHistory || []) mixHistory.set(type, last);
      steps = saved.steps || 0;
      requested = true;
      failures = 0;
      showState("Resuming background previews…");
      schedule();
    }

    function loadCatalogue() {
      if (catalogue) return Promise.resolve(catalogue);
      if (!loading) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), READY_TIMEOUT);
        loading = fetch("/api/background-previews", {signal: controller.signal}).then(async response => {
          if (!response.ok) throw Error("Preview list unavailable");
          const {songs} = await response.json();
          catalogue = songs;
          return songs;
        }).finally(() => {
          clearTimeout(timeout);
          loading = null;
        });
      }
      return loading;
    }

    function showState(message) {
      status.textContent = message;
      toggle.textContent = requested ? "Pause" : "Play";
      skip.disabled = !requested || !track;
      root.dataset.playing = String(!audio.paused);
    }

    function announce() {
      clearTimeout(cardTimer);
      card.href = "/song/" + encodeURIComponent(track.id);
      card.querySelector("strong").textContent = track.title;
      card.querySelector("[data-background-artist]").textContent = track.artist;
      artwork.hidden = !track.cover_url;
      if (track.cover_url) artwork.src = track.cover_url;
      else artwork.removeAttribute("src");
      card.hidden = false;
      cardTimer = setTimeout(() => { card.hidden = true; }, 6500);
    }

    function updateProgress() {
      const limit = Math.min(30, Number.isFinite(audio.duration) ? audio.duration : 30);
      const time = Math.min(audio.currentTime, limit);
      progress.max = limit || 30;
      progress.value = time;
      elapsed.textContent = "0:" + String(Math.floor(time)).padStart(2, "0");
    }

    function showTrack() {
      nowPlaying.hidden = false;
      nowArt.hidden = !track.cover_url;
      if (track.cover_url) nowArt.src = track.cover_url;
      else nowArt.removeAttribute("src");
      nowTitle.href = "/song/" + encodeURIComponent(track.id);
      nowTitle.textContent = track.title;
      nowArtist.textContent = track.artist;
      nowAlbum.textContent = track.album || "";
      nowAlbum.hidden = !track.album;
      nowRelation.textContent = relation;
      nowRelation.hidden = !relation;
      updateProgress();
    }

    function choose(songs) {
      const liked = candidates => {
        const fresh = candidates.filter(({song}) => !recent.includes(song.id));
        return fresh.length ? fresh : candidates;
      };
      const draw = candidates => {
        let roll = Math.random() * candidates.reduce((sum, candidate) => sum + candidate.weight, 0);
        return candidates.find(candidate => (roll -= candidate.weight) < 0) || candidates.at(-1);
      };
      if (!anchor) return draw(liked(songs.map(song => ({song, reason: "", weight: 1}))));

      const anchorTags = new Set(anchor.tag_ids);
      const tagCounts = new Map();
      for (const song of songs)
        for (const tag of song.tag_ids) tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);

      const groups = new Map([
        ["Same album", []], ["Shared artist", []], ["Shared tags", []], ["Similar vibe", []],
      ]);
      for (const song of songs) {
        if (song.id === anchor.id) continue;
        const add = (reason, weight) => groups.get(reason).push({song, reason, weight});
        if (anchor.album_id != null && anchor.album_id === song.album_id) add("Same album", 1);
        if (anchor.artist_ids.some(id => song.artist_ids.includes(id))) add("Shared artist", 1);

        let overlap = 0, union = 0, vibe = 0, sharedMaps = 0;
        for (const tag of new Set([...anchorTags, ...song.tag_ids])) {
          const weight = 1 / Math.log2(2 + tagCounts.get(tag));
          union += weight;
          if (anchorTags.has(tag) && song.tag_ids.includes(tag)) overlap += weight;
        }
        for (const [key, point] of Object.entries(anchor.vibe_maps || {})) {
          const other = song.vibe_maps?.[key];
          if (point.status !== "placed" || other?.status !== "placed") continue;
          sharedMaps++;
          const distance = (point.x - other.x)**2 + (point.y - other.y)**2;
          vibe += Math.exp(-distance / (2 * .65**2));
        }
        const tagScore = union ? overlap / union : 0;
        const vibeScore = sharedMaps >= 2 ? vibe / sharedMaps : 0;
        if (tagScore >= .18) add("Shared tags", tagScore);
        if (vibeScore >= .72) add("Similar vibe", vibeScore * sharedMaps / 4);
      }

      const hasFresh = [...groups.values()].some(tracks => tracks.some(({song}) => !recent.includes(song.id)));
      const choices = [];
      for (const [reason, tracks] of groups) {
        const pool = hasFresh ? tracks.filter(({song}) => !recent.includes(song.id)) : tracks;
        if (!pool.length) continue;
        // The mix type earns better odds the longer it has gone unused.
        // A type with no suitable transition stays out of the draw.
        const age = steps - (mixHistory.get(reason) ?? -4);
        choices.push({pool, weight: 1 + Math.min(20, age) / 2});
      }
      const group = draw(choices);
      return group ? draw(group.pool) : null;
    }

    function foregroundBusy() {
      return pending || armed || performance.now() < foregroundUntil ||
        [...players].some(player => player.isConnected && !player.paused &&
          player.dataset.previewPrepared !== "true");
    }

    function schedule(delay = 400) {
      clearTimeout(wake);
      if (requested && !closed) wake = setTimeout(resume, delay);
    }

    function quiet() {
      revision++;
      starting = false;
      clearTimeout(loadTimer);
      audio.pause();
      clearTimeout(cardTimer);
      card.hidden = true;
    }

    function suspend(message = "Paused") {
      requested = false;
      clearTimeout(wake);
      quiet();
      showState(message);
    }

    function yieldToPreview() {
      foregroundUntil = performance.now() + 900;
      quiet();
      if (requested) {
        showState("Waiting for your preview to finish");
        schedule();
      }
    }

    function foregroundPlayed(foreground) {
      if (preferenceValue === "paused") return;
      const id = document.body.classList.contains("gameplay-page") ? null : clipId(foreground);
      loadCatalogue().then(songs => {
        if (id && !track) {
          anchor = songs.find(song => String(song.id) === id) || null;
          if (anchor && !recent.includes(anchor.id)) recent.push(anchor.id);
          if (recent.length > 24) recent.shift();
        }
      }).catch(() => {});
      if (!requested) {
        requested = true;
        failures = 0;
        showState("Waiting for your preview to finish");
        schedule();
      }
    }

    function advance(failed = false) {
      if (!requested) return;
      quiet();
      if (track) {
        recent.push(track.id);
        if (recent.length > 24) recent.shift();
        if (!failed && counted) anchor = track;
      }
      track = null;
      nowPlaying.hidden = true;
      counted = false;
      audio.removeAttribute("src");
      if (failed && ++failures >= 5) {
        suspend("Previews unavailable. Press Play to retry.");
        return;
      }
      schedule(0);
    }

    async function resume() {
      if (!requested || closed || starting || !audio.paused) return;
      if (foregroundBusy()) {
        showState("Waiting for your preview to finish");
        schedule();
        return;
      }
      starting = true;
      const active = ++revision;
      try {
        const songs = catalogue || await loadCatalogue();
        if (active !== revision) return;
        if (foregroundBusy()) { schedule(); return; }
        let resumeTime = 0;
        if (!track) {
          const saved = handoff;
          handoff = null;
          if (saved) anchor = songs.find(song => song.id === saved.anchor) || null;
          const restored = songs.find(song => song.id === saved?.id);
          const choice = restored ? null : choose(songs);
          track = restored || choice?.song;
          if (!track) {
            suspend(anchor ? "No more closely related previews" : "No playable previews");
            anchor = null;
            return;
          }
          relation = restored ? saved.relation || "" : choice.reason;
          counted = Boolean(restored && saved.counted);
          audio.src = source(track.id, track.audio_url);
          if (saved?.id === track.id && saved.time > 0 && saved.time < 30) resumeTime = saved.time;
        }
        setGain(audio, resumeTime ? 0 : .38);
        showState("Loading preview…");
        loadTimer = setTimeout(() => {
          if (active === revision && starting) advance(true);
        }, READY_TIMEOUT);
        await audio.play();
        if (active === revision) {
          clearTimeout(loadTimer);
          if (resumeTime && resumeTime < audio.duration) audio.currentTime = resumeTime;
          setGain(audio, .38);
          failures = 0;
          if (!counted) {
            steps++;
            if (relation) mixHistory.set(relation, steps);
            counted = true;
          }
          showTrack();
          announce();
          showState("Playing");
        }
      } catch (error) {
        if (active !== revision) return;
        if (error.name === "NotAllowedError") suspend("Press Play to start background previews.");
        else if (!catalogue) suspend("Preview list unavailable. Press Play to retry.");
        else advance(true);
      } finally {
        if (active === revision) starting = false;
      }
    }

    async function startFrom(ids) {
      quiet();
      const active=revision;
      showState("Loading mix…");
      try {
        const songs=await loadCatalogue();
        if(active!==revision || closed)return false;
        const wanted=new Set(ids.map(Number));
        const pool=songs.filter(song=>wanted.has(Number(song.id)) && song.audio_url);
        if(!pool.length){showState("No playable previews for this page");if(requested)schedule();return false;}
        const seed=pool[Math.floor(Math.random()*pool.length)];
        stopAll();
        foregroundUntil=0;
        track=null;anchor=null;counted=false;
        recent.length=0;mixHistory.clear();steps=0;
        handoff={id:seed.id,anchor:seed.id,relation:"From this page"};
        preferenceValue="auto";requested=true;failures=0;
        remember();
        await resume();
        return true;
      } catch {
        showState("Preview list unavailable. Try again.");
        if(requested)schedule();
        return false;
      }
    }

    toggle.addEventListener("click", () => {
      if (requested) {
        preferenceValue = "paused";
        suspend();
      } else {
        preferenceValue = "auto";
        requested = true;
        failures = 0;
        showState("Loading preview…");
        resume();
      }
      remember();
    });
    document.addEventListener("click", event => {
      if (root.open && !root.contains(event.target)) root.open = false;
    });
    root.addEventListener("keydown", event => {
      if (event.key === "Escape" && root.open) {
        root.open = false;
        root.querySelector("summary").focus();
      }
    });
    root.addEventListener("toggle", () => {
      if (root.open) loadCatalogue().catch(() => {});
    });
    skip.addEventListener("click", () => advance());
    nowArt.addEventListener("error", () => { nowArt.hidden = true; });
    artwork.addEventListener("error", () => { artwork.hidden = true; });
    audio.addEventListener("ended", () => advance());
    audio.addEventListener("error", () => { if (audio.getAttribute("src")) advance(true); });
    audio.addEventListener("timeupdate", () => {
      if (!track) return;
      updateProgress();
      if (audio.currentTime >= 30) advance();
    });
    if (preferenceValue === "paused") showState("Paused");
    restorePage();
    return {foregroundPlayed, yieldToPreview, suspend, leavePage, restorePage, startFrom};
  }

})();
