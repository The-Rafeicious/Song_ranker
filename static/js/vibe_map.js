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
      ? `<img data-cover class="${cls}" src="${esc(song.cover_url)}" alt="">`
      : '<span class="vibe-art-fallback" aria-hidden="true">♫</span>';
  async function api(path, body, signal) {
    const response = await fetch("/api/vibe-map/" + path, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal,
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
    if (!round || phase === "setup") return;
    const locked = unsettled(),
      prev = $("#vibe-back"),
      next = $("#vibe-forward"),
      finish = $("#vibe-finish");
    if (prev) prev.disabled = locked || !round.maps.some((m,i)=>i<index && !saved(m.id)?.read_only) || phase === "results";
    if (next)
      next.disabled =
        locked || !round.maps.some((m,i)=>i>index && i<=Math.min(3,round.map_index) && !saved(m.id)?.read_only) || phase === "results";
    if (finish) {
      finish.textContent =
        phase === "results"
          ? sequence.scope === "song" ? "Choose another song" : "Next song →"
          : phase === "loading"
            ? "Loading…"
            : "Finish";
      finish.disabled = !allDone() || locked;
    }
    const status = $("#vibe-save-state");
    if (status) status.hidden = phase === "results" || phase === "loading";
    $("#vibe-choose")?.toggleAttribute("disabled", locked);
    const plane = $("#vibe-plane");
    if (plane) plane.setAttribute("aria-disabled", String(advancing || failed || saved(currentMap().id)?.read_only));
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
    card.innerHTML = `<button class="vibe-cover" id="vibe-play" type="button" data-audio="vibe-audio" aria-label="Play ${esc(song.title)}" aria-pressed="false" ${song.audio_url ? "" : "disabled"}>${image(song)}<span class="play-overlay" aria-hidden="true">▶</span></button><div class="vibe-song-copy"><h2><a href="/song/${song.id}" title="${esc(song.title)}">${esc(song.title)}</a></h2><div class="vibe-identity"><div>${(song.artist_links || []).map((a) => `<a class="artist" href="/artist/${encodeURIComponent(a.name)}">${esc(a.name)}</a>`).join(", ") || `<span class="artist">${esc(song.artist || "Unknown artist")}</span>`}</div>${song.album && !song.album_hidden && song.album.trim().toLowerCase() !== "unknown album" ? `<a class="album" href="/album/${encodeURIComponent(song.album)}">${esc(song.album)}</a>` : ""}<span id="vibe-tag-count" class="tag">${esc(tagCountLabel(song))}</span></div><small id="vibe-audio-status" class="muted">${song.audio_url ? "" : "No preview available"}</small></div><div class="vibe-controls"><button class="btn" id="vibe-back" type="button" aria-label="Previous map">←</button><button class="btn vibe-primary" id="vibe-finish" type="button" disabled>Finish</button><button class="btn" id="vibe-forward" type="button" aria-label="Next map">→</button></div><div class="vibe-save-state" id="vibe-save-state"><p id="vibe-save-status" role="status" aria-live="polite"></p><div class="vibe-progress" aria-hidden="true"><span id="vibe-progress-fill"></span></div></div>`;
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
      if (e.button !== 0 || advancing || failed || saved(currentMap().id)?.read_only) return;
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
      if (!dirs[e.key] || advancing || failed || saved(currentMap().id)?.read_only) return;
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
    if(saved(currentMap().id)?.read_only)return;
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
    let next = index + direction;
    while(next>=0 && next<=Math.min(3,round.map_index) && saved(round.maps[next].id)?.read_only) next+=direction;
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
    workspace.innerHTML = `<h2>Your vibe map</h2>${window.VibeCharts.radar(round.summary.aggregate.radar, round.song.title + " · vibe map")}<h3>Similar songs</h3><div id="vibe-similar" class="vibe-similar" role="status">Finding matches…</div>`;
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
  let sequence = {scope:"all"}, choice = {scope:"all",name:"Random sequence"}, chooserRequest = 0, chooserAbort = null;
  try {
    const stored=JSON.parse(sessionStorage.getItem("vibe-mapping-selection"));
    if(["all","song","artist","album"].includes(stored?.scope)) sequence=stored;
  } catch {}
  const setup=$("#vibe-setup");
  function displayRound(next) {
    useRound(next);clearError();phase="map";
    index=round.draft?round.maps.findIndex(m=>m.id===round.draft.map_id):Math.min(3,round.map_index);
    setup.hidden=true;$("#vibe-loading").hidden=true;$("#vibe-layout").hidden=false;$("#vibe-choose").hidden=false;
    mountSong();
    let resultsRequested=false;
    try {resultsRequested=sessionStorage.getItem("vibe-results-token")===round.token;} catch {}
    if(allDone()&&!round.draft&&resultsRequested)showResults();else renderMap();
  }
  async function searchChoices(kind="song") {
    chooserAbort?.abort();chooserAbort=new AbortController();const request=++chooserRequest;
    const results=$("#vibe-choices"), query=$("#vibe-search").value;
    results.setAttribute("aria-busy","true");results.innerHTML='<p class="muted">Finding unmapped music…</p>';
    try {
      const data=await api("options?"+new URLSearchParams({kind,q:query}),undefined,chooserAbort.signal);
      if(closed||request!==chooserRequest||phase!=="setup")return;
      $("#vibe-remaining").textContent=`${data.library_remaining} songs left to map`;
      $("#vibe-start").disabled=!data.library_remaining;
      results.innerHTML=data.results.map(row=>`<button type="button" class="vibe-choice ${kind}" data-vibe-pick="${row.id}" data-name="${esc(row.name)}"><span class="vibe-choice-art ${kind}">${row.cover_url?`<img data-cover src="${esc(row.cover_url)}" alt="" loading="lazy">`:"♫"}</span><span class="vibe-choice-copy"><strong title="${esc(row.name)}">${esc(row.name)}</strong><small title="${esc([row.artist,row.album].filter(Boolean).join(" · "))}">${kind==="song"?esc([row.artist,row.album].filter(Boolean).join(" · ")):row.remaining+" songs left to map"}</small></span><span aria-hidden="true">→</span></button>`).join("")||'<p class="empty">'+(data.library_remaining?'No unmapped music matches this search.':'Your library is mapped. Add songs to map something new.')+'</p>';
      if(data.matches>data.results.length)results.insertAdjacentHTML("beforeend",'<p class="muted">Keep typing to narrow the choices.</p>');
      results.querySelectorAll("[data-vibe-pick]").forEach(button=>button.addEventListener("click",()=>{
        choice={scope:kind,scope_id:Number(button.dataset.vibePick),name:button.dataset.name};
        $("#vibe-selection").textContent=choice.name;$("#vibe-start").disabled=false;
        results.querySelectorAll("[data-vibe-pick]").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));
      }));
    } catch(error) {
      if(error.name!=="AbortError"&&request===chooserRequest){results.innerHTML='<p class="error">Could not load choices.</p><button type="button" class="btn" id="vibe-choice-retry">Retry search</button>';$("#vibe-choice-retry").onclick=()=>searchChoices(kind);}
    } finally {if(request===chooserRequest)results.removeAttribute("aria-busy");}
  }
  async function showSetup(note="") {
    phase="setup";chooserAbort?.abort();chooserRequest++;clearError();
    loopWanted=false;if(audio){await player.forgetPair([audio]);audio=null;}
    $("#vibe-layout").hidden=true;$("#vibe-choose").hidden=true;$("#vibe-loading").hidden=true;setup.hidden=false;
    choice={scope:"all",name:"Random sequence"};
    setup.innerHTML=`<div class="section-head"><h2>Choose music to map</h2></div><p id="vibe-remaining" class="muted" role="status">Finding unmapped music…</p>${note?`<p class="report-facts" role="status">${esc(note)}</p>`:""}<div id="vibe-resume"></div><div class="vibe-setup-actions"><button class="btn vibe-primary" id="vibe-random" type="button">Random sequence</button><strong id="vibe-selection"></strong><button class="btn vibe-primary" id="vibe-start" type="button" disabled>Start mapping →</button></div><div class="pill-nav" aria-label="Find music">${["song","artist","album"].map((kind,i)=>`<button class="pill ${kind} ${i===0?"active":""}" type="button" data-vibe-kind="${kind}" aria-pressed="${i===0}">${kind[0].toUpperCase()+kind.slice(1)}s</button>`).join("")}</div><label class="vibe-search-label" for="vibe-search">Find a song, artist or album</label><div class="search-form"><input id="vibe-search" class="vibe-search" type="search" placeholder="Search songs…" autocomplete="off"></div><div id="vibe-choices" class="vibe-choices" aria-live="polite"></div>`;
    let kind="song",starting=false;
    $("#vibe-search").addEventListener("input",()=>void searchChoices(kind));
    setup.querySelectorAll("[data-vibe-kind]").forEach(button=>button.addEventListener("click",()=>{
      kind=button.dataset.vibeKind;setup.querySelectorAll("[data-vibe-kind]").forEach(b=>{b.setAttribute("aria-pressed",String(b===button));b.classList.toggle("active",b===button);});
      $("#vibe-search").placeholder=`Search ${kind}s…`;void searchChoices(kind);
    }));
    $("#vibe-random").onclick=()=>{choice={scope:"all",name:"Random sequence"};$("#vibe-selection").textContent="";void searchChoices(kind);};
    $("#vibe-start").onclick=async()=>{
      if(starting)return;starting=true;
      const button=$("#vibe-start");button.disabled=true;button.textContent="Loading…";
      try {
        if(round?.status==="active"||round?.draft)round=(await api("cancel",{token:round.token,revision:round.revision})).round;
        sequence={...choice};try{sessionStorage.setItem("vibe-mapping-selection",JSON.stringify(sequence));}catch{}
        await load({...sequence,...(round?{previous_token:round.token}:{})});
      } catch(error){showError(error,()=>showSetup());}
      finally{starting=false;if(button.isConnected){button.disabled=false;button.textContent="Start mapping →";}}
    };
    try {
      const state=await api("state");if(closed||phase!=="setup")return;
      round=state.round;
      if((round?.status==="active"||round?.draft)&&round.can_resume!==false){
        $("#vibe-resume").innerHTML=`<div class="vibe-resume"><span>Continue <strong>${esc(round.song.title)}</strong> · ${round.saved_maps.length}/4 maps saved</span><button class="btn" id="vibe-resume-button" type="button">Resume mapping</button></div>`;
        $("#vibe-resume-button").onclick=()=>displayRound(round);
      }
    }catch(error){showError(error,()=>showSetup());}
    if(!closed&&phase==="setup")await searchChoices(kind);
  }
  async function load(body = {}) {
    try {
      const data=await api("round",body);
      if(!closed)displayRound(data.round);
    }catch(error){
      if(error.code==="selection_complete"){await showSetup("All songs in this selection are mapped.");return;}
      showError(error,()=>load(body));$("#vibe-loading").hidden=true;
    }
  }
  async function nextSong() {
    if (unsettled() || !allDone()) return;
    if(sequence.scope==="song"){await showSetup();return;}
    const body = { ...sequence, previous_token: round.token };
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
    if (closed || document.hidden || !round || phase!=="map") return;
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
    chooserAbort?.abort();
    clearInterval(clock);
    clearTimeout(editTimer);
    loopWanted = false;
  });
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) location.reload();
  });
  $("#vibe-choose").addEventListener("click",()=>{if(!unsettled())void showSetup();});
  void showSetup();
})();
