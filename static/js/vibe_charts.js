/* Reusable SVG radar: semantic spoke order comes from Python, absent values stay gaps. */
(() => {
  "use strict";
  const esc = (value) => window.SongRankerUI.esc(value);
  function radar(data, label = "Song vibe", compact = false) {
    const spokes = data.spokes,
      n = spokes.length,
      cx = 220,
      cy = compact ? 150 : 205,
      r = compact ? 100 : 128;
    const at = (i, radius) => {
      const a = (i * 2 * Math.PI) / n - Math.PI / 2;
      return [cx + Math.cos(a) * r * radius, cy + Math.sin(a) * r * radius];
    };
    const pair = (p) => p.map((v) => v.toFixed(2)).join(",");
    const rings = [0.25, 0.5, 0.75, 1]
      .map(
        (radius) =>
          `<polygon class="radar-ring ${radius === 0.5 ? "radar-neutral" : ""}" points="${spokes.map((_, i) => pair(at(i, radius))).join(" ")}"/>`,
      )
      .join("");
    const axes = spokes
      .map((s, i) => {
        const [x, y] = at(i, 1),
          [tx, ty] = at(i, 1.16);
        return `<line class="radar-axis" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/><text x="${tx}" y="${ty}" text-anchor="${Math.abs(tx - cx) < 1 ? "middle" : tx < cx ? "end" : "start"}" dominant-baseline="middle">${esc(s.label || s.high)}</text>`;
      })
      .join("");
    const valid = (s) => Number.isFinite(s.radius);
    let shape = "";
    if (spokes.every(valid))
      shape = `<polygon class="radar-shape" points="${spokes.map((s, i) => pair(at(i, s.radius))).join(" ")}"/>`;
    else
      shape = spokes
        .map((s, i) => {
          const next = (i + 1) % n;
          if (!valid(s) || !valid(spokes[next])) return "";
          return `<polyline class="radar-shape" fill="none" points="${pair(at(i, s.radius))} ${pair(at(next, spokes[next].radius))}"/>`;
        })
        .join("");
    const points = spokes
      .map((s, i) => {
        if (!valid(s)) return "";
        const [x, y] = at(i, s.radius);
        return `<circle class="radar-point" cx="${x}" cy="${y}" r="4"><title>${esc(s.low)} → ${esc(s.high)}</title></circle>`;
      })
      .join("");
    return `<svg class="vibe-radar" viewBox="0 0 440 ${compact ? 300 : 410}" role="img" aria-label="${esc(label)}"><desc>Eight bipolar axes. The dashed ring is neutral. Missing maps leave gaps.</desc>${rings}${axes}${shape}${points}</svg>`;
  }
  window.VibeCharts = Object.freeze({ radar });
})();

/* Independent descriptive cards; Overall and hero playback keep their own owners. */
window.VibeProfiles = (() => {
  "use strict";
  let active = null,
    reload = null;
  function mount(info) {
    if (
      !["song", "album", "artist", "tag"].includes(info.kind) ||
      !Number.isSafeInteger(info.id) ||
      info.id <= 0
    )
      return;
    const anchor = document.querySelector(".profile-key-stats");
    if (!anchor) return;
    active?.abort();
    document.querySelector("#profile-vibe")?.remove();
    const panel = document.createElement("section");
    panel.id = "profile-vibe";
    panel.hidden = true;
    panel.className =
      "panel profile-mode-panel mode-stats-panel vibe-profile-panel dashboard-surface vibe";
    panel.setAttribute("aria-labelledby", "profile-vibe-title");
    const ranks =
      info.kind === "song"
        ? ""
        : '<a class="vibe" href="/mode_rankings/vibe?entity=' +
          { album: "albums", artist: "artists", tag: "tags" }[info.kind] +
          '">Rankings ↗</a>';
    panel.innerHTML =
      '<div class="section-head"><h2 class="vibe" id="profile-vibe-title">Vibe Map</h2><div class="profile-stat-links"><a class="vibe" href="/vibe_map_stats">Stats ↗</a>' +
      ranks +
      '</div></div><div class="vibe-profile-content mode-stats-page"></div>';
    anchor.after(panel);
    const body = panel.querySelector(".vibe-profile-content");
    async function load() {
      active?.abort();
      const request = new AbortController();
      active = request;
      const timeout = setTimeout(() => request.abort(), 15000);
      panel.setAttribute("aria-busy", "true");
      body.innerHTML = '<p class="empty" role="status">Loading Vibe Map…</p>';
      try {
        const path =
          info.kind === "song"
            ? "inspect/" + info.id + "?context=profile"
            : "entity/" + info.kind + "/" + info.id;
        const response = await fetch("/api/vibe-map/" + path, {
          cache: "no-store",
          signal: request.signal,
        });
        if (!response.ok)
          throw Error(
            response.status === 404
              ? "Vibe Map data is no longer available."
              : "Vibe Map could not load.",
          );
        const data = await response.json();
        if (request.signal.aborted || !panel.isConnected || active !== request)
          return;
        panel.hidden = !data.profile_ready;
        if (!data.profile_ready) {
          body.replaceChildren();
          return;
        }
        body.innerHTML = data.html; // Same-origin, autoescaped reusable server component.
        if (info.kind === "song")
          body.querySelector("[data-vibe-song-radar]").innerHTML =
            window.VibeCharts.radar(
              data.profile.radar,
              data.song.title + " · average vibe",
              true,
            );
      } catch (error) {
        if (!panel.isConnected || active !== request) return;
        panel.hidden = false;
        const text = document.createElement("p");
        text.className = "empty";
        text.setAttribute("role", "alert");
        text.textContent =
          error.name === "AbortError" ? "Vibe Map timed out." : error.message;
        const retry = document.createElement("button");
        retry.className = "btn vibe";
        retry.type = "button";
        retry.dataset.vibeProfileRetry = "";
        retry.textContent = "Retry Vibe Map";
        body.replaceChildren(text, retry);
      } finally {
        clearTimeout(timeout);
        if (active === request) {
          active = null;
          panel.setAttribute("aria-busy", "false");
        }
      }
    }
    panel.addEventListener("click", (event) => {
      if (event.target.closest("[data-vibe-profile-retry]")) void load();
    });
    reload = () => {
      if (panel.isConnected) void load();
    };
    void load();
  }
  window.addEventListener("pagehide", () => {
    const request = active;
    active = null;
    request?.abort();
    document.querySelector("#profile-vibe")?.setAttribute("aria-busy", "false");
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) reload?.();
  });
  return Object.freeze({ mount });
})();
