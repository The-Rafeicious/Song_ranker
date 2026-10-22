/* Missing-information tasks: one page owner for polling, review and apply. */
window.DevMetadata = (() => {
  "use strict";
  const { $, $$, esc } = window.SongRankerUI;
  let U,
    active = false,
    state = { state: "idle" },
    country = "gb",
    timer = null,
    sequence = 0,
    busy = false;
  const running = () => ["scanning", "applying"].includes(state.state);
  const hasChanges = () =>
    !!(state.tracks || state.dates || state.song_dates || state.sources);
  function controls() {
    const scan = $('[data-metadata="scan"]'),
      store = $("#metadata-country");
    if (scan) {
      scan.disabled = busy || running();
      scan.textContent = busy ? "Working…" : "Scan missing values";
    }
    if (store) store.disabled = busy || running();
  }
  function message(text) {
    const root = $("#metadata-error");
    if (root) {
      root.hidden = !text;
      root.textContent = text;
    }
  }
  function review(title, rows, value) {
    return rows?.length
      ? `<details class="metadata-review"><summary>${title} · ${rows.length}</summary>${rows.map((r) => `<div class="health-row"><span>${esc(r.title)}</span><strong>${esc(r[value])}</strong></div>`).join("")}</details>`
      : "";
  }
  function draw() {
    if (!active || !$("#metadata-status")) return;
    controls();
    const m = state;
    $("#metadata-status").innerHTML = running()
      ? `<div class="health-row"><strong>${m.state === "scanning" ? "Scanning" : "Saving"} ${m.done || 0} / ${m.total || "…"}</strong><button class="btn" type="button" data-metadata="cancel" ${busy || m.state === "applying" ? "disabled" : ""}>Stop scan</button></div><p>${esc(m.album || "")}</p>`
      : m.state === "idle"
        ? '<p class="muted">Start a scan to review missing values before saving.</p>'
        : `<div class="joined-metrics" data-columns="4">${[
            ["Track numbers", m.tracks],
            ["Album dates", m.date_changes?.length],
            ["Song dates", m.song_dates],
            ["Apple sources", m.sources],
          ]
            .map(
              ([label, value]) =>
                `<div><b>${value || 0}</b><span>${label}</span></div>`,
            )
            .join(
              "",
            )}</div><p class="muted">${(m.track_failures || 0) + (m.date_failures || 0) + (m.metadata_failures || 0)} unresolved fields · details in text report</p>${m.error || m.stopped ? `<p class="error">${esc(m.error || m.stopped)}</p>` : ""}<div class="metadata-actions">${m.state === "ready" ? `<button class="btn primary" type="button" data-metadata="apply" ${busy || !hasChanges() ? "disabled" : ""}>Fill matched blanks</button>` : ""}${m.state === "applied" ? '<strong class="song">✓ Matched blanks filled</strong>' : ""}${m.token ? `<a class="btn" href="/api/dev/metadata/${encodeURIComponent(m.token)}/report">Download text report</a>` : ""}</div>${review("Song release dates", m.song_date_changes, "value")}${review("Apple source updates", m.source_changes, "content_label")}${review("Album release dates", m.date_changes, "value")}`;
  }
  function poll(delay = 1500) {
    clearTimeout(timer);
    if (active && running()) timer = setTimeout(refresh, delay);
  }
  async function refresh() {
    const id = ++sequence;
    try {
      const result = await U.api("/api/dev/metadata");
      if (!active || id !== sequence) return;
      state = result;
      draw();
      message("");
      poll();
    } catch (e) {
      if (active && id === sequence) {
        message(e.message);
        $("#metadata-retry").hidden = false;
      }
    }
  }
  function render() {
    active = true;
    U.root().innerHTML =
      U.title("Fill missing metadata") +
      `<section class="panel metadata-panel"><div class="section-head"><h3>Missing catalogue information</h3></div><div class="metadata-actions"><label>Apple store<input id="metadata-country" value="${esc(country)}" maxlength="2" pattern="[A-Za-z]{2}" aria-label="Two-letter Apple store" list="metadata-stores"><datalist id="metadata-stores"><option value="gb">United Kingdom</option><option value="us">United States</option></datalist></label><button class="btn primary" type="button" data-metadata="scan">Scan missing values</button></div><p class="muted">Review missing track numbers, album/song dates and Apple source details. Existing artwork, album placement, tags and previews are kept.</p><div id="metadata-status" role="status" aria-live="polite">Loading task…</div><p id="metadata-error" class="error" role="alert" hidden></p><button id="metadata-retry" class="btn" type="button" data-metadata="retry" hidden>Refresh task</button></section>`;
    draw();
    refresh();
  }
  async function action(kind) {
    if (kind === "retry") {
      refresh();
      return;
    }
    if (busy || !active) return;
    if (kind === "scan") {
      country = $("#metadata-country").value.trim().toLowerCase();
      if (!/^[a-z]{2}$/.test(country)) {
        message("Choose a two-letter Apple store, such as gb or us.");
        return;
      }
    }
    if (kind === "apply" && (state.state !== "ready" || !hasChanges())) return;
    if (kind === "cancel" && state.state !== "scanning") return;
    busy = true;
    ++sequence;
    clearTimeout(timer);
    message("");
    draw();
    let saved = false;
    try {
      state = await U.api(
        kind === "scan"
          ? "/api/dev/metadata"
          : `/api/dev/metadata/${encodeURIComponent(state.token)}/${kind}`,
        kind === "scan" ? { country } : {},
      );
      saved = kind === "apply";
      if (saved) {
        let failed = false;
        try {
          await U.refresh();
          await window.DevCatalog?.ensureSources(true);
        } catch {
          failed = true;
        }
        U.toast(
          failed
            ? "Metadata filled. Reload to refresh the catalogue."
            : "Metadata filled",
        );
      }
    } catch (e) {
      if (active) message(e.message);
      else U.toast(e.message);
    } finally {
      busy = false;
      draw();
      poll(500);
    }
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-metadata]");
    if (U && b && !b.disabled) action(b.dataset.metadata);
  });
  return {
    bindUI: (ui) => (U = ui),
    render,
    viewChanged: (next) => {
      active = next === "metadata";
      if (!active) {
        clearTimeout(timer);
        ++sequence;
      }
    },
  };
})();
