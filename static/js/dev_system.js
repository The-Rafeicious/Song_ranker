/* Developer task dashboard, local recovery and explicit Git controls. */
window.DevSystem = (() => {
  "use strict";
  const { $, $$, esc } = window.SongRankerUI,
    managed = new Set(["overview", "database", "backups", "export"]);
  let U,
    view = null,
    data = null,
    gitState = null,
    loadId = 0,
    reviewId = 0,
    loadError = "",
    loading = false;
  let gitBusy = false,
    backupBusy = false,
    restoreBusy = false,
    restoreReview = null,
    localReview = null,
    backupQuery = "",
    backupLimit = 10,
    inventoryQuery = "",
    inventoryKind = "all",
    note = "";
  const bytes = (n) =>
    n >= 1048576
      ? (n / 1048576).toFixed(1) + " MB"
      : n >= 1024
        ? (n / 1024).toFixed(1) + " KB"
        : n + " B";
  const date = (s) => {
    const d = new Date(s);
    return Number.isFinite(d.getTime())
      ? d.toLocaleString()
      : s || "Not recorded";
  };
  const button = (label, attr, kind = "") =>
    `<button class="btn ${kind}" type="button" ${attr}>${label}</button>`;
  const tile = (label, detail, attr, kind = "song") =>
    `<button class="system-task" type="button" ${attr}><strong class="${kind}">${label}</strong><span>${detail}</span></button>`;
  const header = () => "";
  function viewChanged(next) {
    if (next !== view) {
      view = managed.has(next) ? next : null;
      ++loadId;
      ++reviewId;
      restoreReview = null;
      localReview = null;
      loadError = "";
      window.DevDatabase?.close();
    }
  }
  function render(next) {
    view = next;
    draw();
    load(next === "export");
  }
  function controls() {
    $$("[data-system-git-open]").forEach((b) => {
      b.disabled = restoreBusy;
      b.textContent = gitBusy ? "Git task running…" : "Review Git";
    });
    $$("[data-system-backup]").forEach((b) => {
      b.disabled = backupBusy || restoreBusy;
      b.textContent = backupBusy
        ? "Backing up…"
        : b.hasAttribute("data-dev-header")
          ? "Local backup"
          : "Create backup";
    });
    $$("[data-system-check],[data-system-upload]").forEach(
      (b) => (b.disabled = b.disabled || gitBusy || restoreBusy),
    );
  }
  function status() {
    return `<p id="system-note" role="status" aria-live="polite">${esc(note)}</p>${loadError ? `<p class="error" role="alert">${esc(loadError)}</p>${button("Retry status", "data-system-retry")}` : ""}`;
  }
  function draw() {
    if (!view || !U.root()) return;
    const title = {
      overview: "Developer home",
      database: "Database inspector",
      backups: "Backups & restore",
      export: "Git upload & updates",
    }[view];
    U.root().innerHTML =
      U.title(title) +
      `<div class="dev-system">${status()}<div id="system-content">${data ? content() : '<section class="panel"><p role="status">Loading local status…</p></section>'}</div></div>`;
    if (view === "backups" && data) {
      drawBackups();
      drawRestore();
    }
    if (view === "database" && data) drawInventory();
    if (view === "export") drawLocalChoice();
    controls();
  }
  function content() {
    return view === "overview"
      ? overview()
      : view === "database"
        ? database()
        : view === "backups"
          ? backups()
          : sync();
  }
  function overview() {
    const t = data.totals;
    const row = (label, value, tone = "") =>
      `<div class="health-row"><span>${label}</span><strong class="${tone}">${esc(value)}</strong></div>`;
    const groups = window.DevWorkspace
      ? ["library", "modes", "tools"]
          .map(
            (area) =>
              `<section class="panel dev-home-destinations"><div class="section-head"><h2><a href="${window.DevWorkspace.href(area)}" data-dev="${area}">${{ library: "Library", modes: "Mode edits", tools: "Tools & systems" }[area]} ↗</a></h2></div>${window.DevWorkspace.cards(area)}</section>`,
          )
          .join("")
      : "";
    return `<section class="panel dev-home-library"><div class="joined-metrics" data-columns="4">${[
      [t.songs, "Songs", "songs", "song"],
      [t.artists, "Artists", "artists", "artist"],
      [t.releases, "Releases", "albums", "album"],
      [t.tags, "Tags", "tags", "tag"],
    ]
      .map(
        ([n, label, key, tone]) =>
          `<button class="dev-library-link" data-dev="${key}"><b class="${tone}">${n}</b><span>${label}</span></button>`,
      )
      .join("")}</div></section>
      <div class="dev-home-status"><section class="panel"><div class="section-head"><h2>Site health</h2></div>${row("App / schema", "V" + data.version + " / " + data.schema)}${row("Integrity", data.integrity, data.integrity === "ok" ? "song" : "error")}${row("Foreign-key errors", data.foreign_key_errors, data.foreign_key_errors ? "error" : "song")}<button class="btn" data-tool="Database integrity">Review health</button></section>
      <section class="panel"><div class="section-head"><h2>Git & backups</h2></div>${gitOverview(row)}${row("Latest backup", data.backups[0] ? date(data.backups[0].modified) : "None yet")}<div class="system-actions"><button class="btn" data-dev="export">Git sync</button><button class="btn" data-dev="backups">Backups</button></div></section>
      <section class="panel"><div class="section-head"><h2>Needs attention</h2></div>${row("Untagged songs", t.untagged, "tag")}${row("Missing previews", t.missing_previews, "artist")}${row("Missing Apple links", t.missing_sources, "album")}<div class="system-actions"><button class="btn" data-dev="tag_workbench">Tag Workshop</button><button class="btn" data-system-sources>Source links</button></div></section></div><div class="dev-home-areas">${groups}</div>`;
  }
  function gitOverview(row) {
    const g = gitState || data?.git;
    if (!g?.available)
      return `<p class="muted">${esc(g?.message || "Git unavailable")}</p>`;
    return (
      row("Branch", g.branch) +
      row("Commit", g.head?.slice(0, 10) || "Unknown") +
      row(
        "Cached code",
        labels[g.state] || g.state,
        g.state === "up_to_date" ? "song" : "",
      )
    );
  }
  function health() {
    return `<div class="health-row"><span>App / schema</span><strong>V${esc(data.version)} / ${data.schema}</strong></div><div class="health-row"><span>SQLite integrity</span><strong class="${data.integrity === "ok" ? "song" : "error"}">${esc(data.integrity)}</strong></div><div class="health-row"><span>Foreign-key errors</span><strong>${data.foreign_key_errors}</strong></div><div class="health-row"><span>Local database backups</span><strong>${data.backups.length}</strong></div>`;
  }
  function database() {
    return `<section class="panel"><div class="dev-status-strip"><span>V${esc(data.version)} / schema ${data.schema}</span><span>${bytes(data.database_bytes || 0)}</span><strong class="${data.integrity === "ok" ? "song" : "error"}">Integrity: ${esc(data.integrity)}</strong><button class="btn" data-tool="Database integrity">Health details</button><a href="/dev/tools/guides?guide=technical" data-dev-guide-link>Technical guide</a></div></section><section class="panel" id="system-inventory-panel"><div id="system-inventory"></div></section>`;
  }
  function backups() {
    return `<section class="panel"><div class="section-head"><h2>Local backups</h2><a href="/dev/tools/guides">Dev guide</a></div><div class="system-actions">${button("Create backup", "data-system-backup")}<a class="btn" href="/api/dev/database/export">Download full database</a></div><label class="system-search">Find a backup<input id="system-backup-query" type="search" value="${esc(backupQuery)}" placeholder="Date, name or purpose…"></label><div class="backup-workspace"><div id="system-backups" class="system-bounded"></div><div id="system-restore"></div></div></section>`;
  }
  const labels = {
    up_to_date: "Up to date",
    ahead: "Local commits waiting",
    behind: "Incoming updates",
    diverged: "Diverged history",
    not_checked: "Remote not checked",
    operation_in_progress: "Git operation in progress",
  };
  function gitSummary() {
    const g = gitState || data?.git;
    if (!g?.available)
      return `<p>${esc(g?.message || "Git status unavailable.")}</p><p class="muted">Local backups and full exports remain available. Git setup is explained in the technical guide.</p>`;
    return `<div class="health-row"><span>Current branch → upload target</span><strong>${esc(g.branch)} → ${esc(g.remote)}/${esc(g.target)}</strong></div><div class="health-row"><span>Destination</span><strong>${esc(g.destination)}</strong></div><div class="health-row"><span>Saved remote view</span><strong>${esc(labels[g.state] || g.state)}</strong></div><div class="health-row"><span>Local / incoming commits</span><strong>${g.ahead ?? "—"} / ${g.behind ?? "—"}</strong></div>${g.database_sync ? `<p class="${["database_conflict", "database_check_failed", "database_remote_ahead"].includes(g.database_sync.code) ? "error" : "muted"}" role="status"><b>Last database check:</b> ${esc(g.database_sync.message)}</p>` : ""}${g.code_changes ? `<p class="muted">${g.code_changes} local code edits remain on this computer. A backup upload does not publish them.</p>` : ""}`;
  }
  function sync() {
    const g = gitState || data.git,
      d = g?.database_sync,
      checked = g?.status_source === "checked";
    const canUpload =
      checked &&
      g?.available &&
      g.review_token &&
      g.tracking_head &&
      !g.in_progress &&
      !g.pending_code &&
      !g.behind &&
      g.upload_ready !== false;
    const pair = (label, value, tone = "") =>
      `<div class="health-row"><span>${label}</span><strong class="${tone}">${esc(value ?? "—")}</strong></div>`;
    const databaseLabels = {
      database_matches: "Matches Git snapshot",
      database_local_ahead: "Local data ready to upload",
      database_remote_ahead: "Remote data is newer",
      database_conflict: "Copies need review",
      no_remote_snapshot: "First snapshot ready",
      database_uploaded: "Snapshot uploaded",
      database_updated: "Remote snapshot loaded",
      database_check_failed: "Comparison failed",
    };
    return `<section class="panel dashboard-surface"><div class="section-head"><h2>Git & database sync</h2><a href="/dev/tools/guides">Dev guide</a></div><div class="system-actions">${button(gitBusy ? "Checking…" : "Refresh status", "data-system-check" + (!g?.available || gitBusy ? " disabled" : ""))}${button("Upload backup", 'data-system-upload aria-label="Upload database backup"' + (!canUpload || gitBusy ? " disabled" : ""), "primary")}${button("Keep local…", 'data-system-local-review aria-label="Keep local database"' + (!g?.available || !g.review_token || !g.tracking_head || g.in_progress || gitBusy ? " disabled" : ""))}</div><p class="muted" role="status">${checked ? "Checked " + esc(date(g.checked_at)) : "Not freshly checked · cached results below"}</p><div class="git-status-grid"><section><h3>Code commits</h3>${g?.available ? pair("Branch", g.branch) + pair("Target", g.remote + "/" + g.target) + pair("Local commit", g.head?.slice(0, 10)) + pair("Remote commit", g.tracking_head?.slice(0, 10)) + pair(checked ? "Code status" : "Cached code status", labels[g.state] || g.state, g.behind || g.pending_code ? "error" : "") + pair("Local / incoming", String(g.ahead ?? "—") + " / " + String(g.behind ?? "—")) : `<p class="error">${esc(g?.message || "Git unavailable")}</p>`}</section><section><h3>Live database</h3>${pair(checked ? "Comparison" : "Last comparison", databaseLabels[d?.code] || "Not checked", !checked || ["database_conflict", "database_remote_ahead", "database_check_failed"].includes(d?.code) ? "error" : "song")}<p class="${d && ["database_conflict", "database_remote_ahead", "database_check_failed"].includes(d.code) ? "error" : "muted"}" role="status">${esc(d?.message || "Refresh to compare the live database with the committed snapshot.")}</p>${d?.local_songs != null ? pair("Local / remote songs", d.local_songs + " / " + d.remote_songs) : ""}${g?.behind ? '<p class="error">Incoming code commits: restart to update code before uploading.</p>' : ""}${g?.pending_code ? '<p class="error">Publish or resolve local code commits first.</p>' : ""}${g?.in_progress ? '<p class="error">Finish the active Git operation first.</p>' : ""}${
      d?.local_changes || d?.remote_changes
        ? `<div class="db-scroll"><table class="data-table"><thead><tr><th>Table</th><th>Local + / − / edited</th><th>Remote + / − / edited</th></tr></thead><tbody>${[
            ...new Set([
              ...Object.keys(d.local_changes || {}),
              ...Object.keys(d.remote_changes || {}),
            ]),
          ]
            .map((name) => {
              const fmt = (v) =>
                v ? [v.added, v.removed, v.edited].join(" / ") : "0 / 0 / 0";
              return `<tr><td>${esc(name)}</td><td>${fmt(d.local_changes?.[name])}</td><td>${fmt(d.remote_changes?.[name])}</td></tr>`;
            })
            .join("")}</tbody></table></div>`
        : ""
    }</section></div><div id="system-local-choice"></div></section>
 <section class="panel dashboard-surface"><div class="section-head"><h2>Recent outcomes</h2><a href="/dev/tools/guides?guide=technical">Technical guide</a></div><div class="system-bounded">${
   g?.history?.length
     ? g.history
         .slice(0, 8)
         .map(
           (r) =>
             `<article class="system-outcome"><strong class="${r.ok ? "song" : "error"}">${esc(r.action)} · ${esc(r.code)}</strong><p>${esc(r.message)}</p><small>${esc(date(r.at))}</small></article>`,
         )
         .join("")
     : '<p class="muted">No recorded outcomes.</p>'
 }</div></section>`;
  }
  function drawBackups() {
    const root = $("#system-backups");
    if (!root) return;
    const q = backupQuery.toLocaleLowerCase(),
      rows = data.backups.filter((r) =>
        (r.name + " " + r.purpose + " " + r.modified)
          .toLocaleLowerCase()
          .includes(q),
      );
    root.innerHTML =
      `<p>${rows.length} matching backups</p>` +
      rows
        .slice(0, backupLimit)
        .map(
          (r) =>
            `<article class="system-backup"><div><strong>${esc(r.purpose)}</strong><p>${esc(r.name)}</p><small>${esc(date(r.modified))} · ${bytes(r.bytes)}</small></div><div class="system-actions">${button("Review restore", `data-system-review="${esc(r.name)}"${restoreBusy ? " disabled" : ""}`)}<a class="btn" href="/api/dev/backups/${encodeURIComponent(r.name)}/download">Download .db</a></div></article>`,
        )
        .join("") +
      (rows.length > backupLimit
        ? button("Show ten more backups", "data-system-more-backups")
        : "") +
      (rows.length ? "" : '<p class="empty">No matching local backups.</p>');
  }
  function drawInventory() {
    window.DevDatabase?.mount(data.inventory);
  }
  function drawRestore() {
    const root = $("#system-restore");
    if (!root) return;
    if (!restoreReview) {
      root.innerHTML = "";
      return;
    }
    const r = restoreReview,
      keys = [...new Set([...Object.keys(r.live), ...Object.keys(r.backup)])];
    root.innerHTML = `<section class="system-restore-review"><h3>Review whole-database restore</h3><p><strong>${esc(r.filename)}</strong> · ${esc(r.purpose)}</p><p>Backup schema ${r.source_schema} → current schema ${r.target_schema}. Restoring replaces the live catalogue and competition data; a pre-restore backup is made first. New activity since this review requires another review.</p><div class="data-scroll"><table class="data-table"><thead><tr><th>Records</th><th>Live now</th><th>Backup</th></tr></thead><tbody>${keys.map((key) => `<tr><td>${esc(key)}</td><td>${r.live[key] ?? "—"}</td><td>${r.backup[key] ?? "—"}</td></tr>`).join("")}</tbody></table></div><div class="system-actions">${button(restoreBusy ? "Restoring…" : "Back up & restore", "data-system-restore" + (restoreBusy ? " disabled" : ""), "danger")}${button("Cancel review", "data-system-cancel-restore" + (restoreBusy ? " disabled" : ""))}</div></section>`;
  }
  async function load(freshGit = false) {
    const id = ++loadId;
    loading = true;
    try {
      const r = await U.api("/api/dev/system");
      if (id !== loadId) return;
      data = r;
      gitState = r.git;
      loadError = "";
      if (view) draw();
      if (freshGit && view === "export") await gitTask("check");
    } catch (e) {
      if (id === loadId) {
        loadError = e.message;
        if (view) draw();
        else U.toast(e.message);
      }
    } finally {
      if (id === loadId) loading = false;
    }
  }
  async function makeBackup() {
    if (backupBusy || restoreBusy) return;
    backupBusy = true;
    controls();
    try {
      const r = await U.api("/api/dev/backup", {});
      note = "Created " + r.backup;
      U.toast(note);
      if (view) await load();
    } catch (e) {
      note = e.message;
      U.toast(e.message);
    } finally {
      backupBusy = false;
      if (view) draw();
      controls();
    }
  }
  async function gitTask(kind) {
    if (gitBusy || restoreBusy) return;
    const g = gitState || data?.git;
    if (!g?.available) return;
    localReview = null;
    gitBusy = true;
    note =
      kind === "check"
        ? "Checking remote…"
        : "Checking remote, saving snapshot and uploading…";
    draw();
    try {
      const r = await U.api(
        "/api/dev/git/" + kind,
        kind === "check" ? {} : { review_token: g.review_token },
      );
      ++loadId;
      gitState = r.git;
      if (data) data.git = r.git;
      note = r.message;
    } catch (e) {
      if (e.details?.git) {
        ++loadId;
        gitState = e.details.git;
        if (data) data.git = e.details.git;
      }
      note = e.message;
    } finally {
      gitBusy = false;
      if (view) draw();
      else U.toast(note);
      controls();
    }
  }

  function drawLocalChoice() {
    const node = $("#system-local-choice");
    if (!node || !localReview) return;
    const r = localReview;
    node.innerHTML = `<section class="system-restore-review"><h3>Keep this computer’s database</h3><p>The local catalogue and results stay active. A verified copy of each database is kept before recording this choice. Upload will publish the local copy using normal Git checks.</p><div class="data-scroll"><table class="data-table"><thead><tr><th>Records</th><th>Local · keep</th><th>Git snapshot</th></tr></thead><tbody>${Object.keys(
      r.local,
    )
      .map(
        (k) =>
          `<tr><td>${esc(k)}</td><td>${r.local[k]}</td><td>${r.remote[k] ?? "—"}</td></tr>`,
      )
      .join(
        "",
      )}</tbody></table></div><label>Type KEEP LOCAL<input id="system-local-confirmation" autocomplete="off" ${gitBusy ? "disabled" : ""}></label><div class="system-actions">${button(gitBusy ? "Keeping local…" : "Keep local database", "data-system-local-apply disabled", "danger")}${button("Cancel", "data-system-local-cancel" + (gitBusy ? " disabled" : ""))}</div></section>`;
  }
  async function reviewLocalChoice() {
    if (gitBusy || restoreBusy) return;
    const g = gitState || data?.git;
    if (!g?.review_token) return;
    gitBusy = true;
    localReview = null;
    note = "Comparing local and Git databases…";
    draw();
    try {
      const r = await U.api("/api/dev/git/keep-local/review", {
        review_token: g.review_token,
      });
      ++loadId;
      gitState = r.git;
      if (data) data.git = r.git;
      localReview = r;
      note = r.message;
    } catch (e) {
      if (e.details?.git) {
        gitState = e.details.git;
        if (data) data.git = e.details.git;
      }
      note = e.message;
    } finally {
      gitBusy = false;
      if (view) draw();
      controls();
    }
  }
  async function keepLocalChoice() {
    if (
      gitBusy ||
      restoreBusy ||
      !localReview ||
      $("#system-local-confirmation")?.value !== "KEEP LOCAL"
    )
      return;
    const reviewed = localReview;
    gitBusy = true;
    note = "Backing up both copies and keeping local…";
    draw();
    try {
      const r = await U.api("/api/dev/git/keep-local", {
        choice_token: reviewed.choice_token,
        confirmation: "KEEP LOCAL",
      });
      ++loadId;
      gitState = r.git;
      if (data) data.git = r.git;
      localReview = null;
      note = r.message;
      U.toast(note);
    } catch (e) {
      localReview = null;
      if (e.details?.git) {
        gitState = e.details.git;
        if (data) data.git = e.details.git;
      }
      note = e.message;
    } finally {
      gitBusy = false;
      if (view) draw();
      controls();
    }
  }
  async function inspectBackup(name) {
    if (restoreBusy) return;
    const id = ++reviewId;
    restoreReview = null;
    note = "Validating " + name + "…";
    draw();
    try {
      const r = await U.api("/api/dev/backups/review", { filename: name });
      if (id !== reviewId || view !== "backups") return;
      restoreReview = r;
      note =
        "Compare the saved backup with the live database before restoring.";
      draw();
      $("#system-restore")?.scrollIntoView?.({ block: "nearest" });
    } catch (e) {
      if (id === reviewId) {
        note = e.message;
        if (view) draw();
        else U.toast(e.message);
      }
    }
  }
  async function restore() {
    if (restoreBusy || !restoreReview) return;
    const accepted = restoreReview;
    ++loadId;
    restoreBusy = true;
    note = "Restoring the reviewed backup…";
    draw();
    try {
      const r = await U.api("/api/dev/backups/restore", {
        review_token: accepted.review_token,
      });
      restoreReview = null;
      ++reviewId;
      note = r.message + " Safety backup: " + r.safety_backup;
      try {
        await U.afterRestore();
      } catch (e) {
        note += " Reload this dashboard to refresh its catalogue.";
      }
      await load();
    } catch (e) {
      note = e.message;
      if (e.status === 409) restoreReview = null;
    } finally {
      restoreBusy = false;
      if (view) draw();
      else U.toast(note);
      controls();
    }
  }

  async function handleTool(name) {
    if (!U) return false;
    if (name === "Sync database") {
      U.navigate("export");
      return true;
    }
    if (name === "Create backup") {
      await makeBackup();
      return true;
    }
    if (name === "Restore backup" || name === "Database overview") {
      U.navigate("backups");
      return true;
    }
    return false;
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!U || !b || b.disabled) return;
    if (b.hasAttribute("data-system-git-open")) U.navigate("export");
    if (b.hasAttribute("data-system-backup")) makeBackup();
    if (b.hasAttribute("data-system-retry")) load();
    if (b.hasAttribute("data-system-check")) gitTask("check");
    if (b.hasAttribute("data-system-upload")) gitTask("upload");
    if (b.hasAttribute("data-system-local-review")) reviewLocalChoice();
    if (b.hasAttribute("data-system-local-apply")) keepLocalChoice();
    if (b.hasAttribute("data-system-local-cancel")) {
      localReview = null;
      note = "Database choice cancelled.";
      draw();
    }
    if (b.dataset.systemReview) inspectBackup(b.dataset.systemReview);
    if (b.hasAttribute("data-system-restore")) restore();
    if (b.hasAttribute("data-system-cancel-restore")) {
      ++reviewId;
      restoreReview = null;
      note = "Restore cancelled.";
      draw();
    }
    if (b.hasAttribute("data-system-more-backups")) {
      backupLimit += 10;
      drawBackups();
    }
    if (b.dataset.systemFilter)
      window.DevTags.openFilter(b.dataset.systemFilter);
    if (b.hasAttribute("data-system-sources")) U.showMissingSources();
  });
  document.addEventListener("input", (e) => {
    if (e.target.id === "system-local-confirmation") {
      $("[data-system-local-apply]").disabled =
        gitBusy || e.target.value !== "KEEP LOCAL";
    }
    if (e.target.id === "system-backup-query") {
      backupQuery = e.target.value;
      backupLimit = 10;
      drawBackups();
    }
    if (e.target.id === "system-inventory-query") {
      inventoryQuery = e.target.value;
      drawInventory();
    }
  });
  document.addEventListener("change", (e) => {
    if (e.target.id === "system-inventory-kind") {
      inventoryKind = e.target.value;
      drawInventory();
    }
  });
  return {
    busy: () => restoreBusy || gitBusy || backupBusy,
    bindUI: (ui) => (U = ui),
    header,
    viewChanged,
    render,
    handleTool,
    canNavigate: () => !restoreBusy,
  };
})();

/* Read-only SQLite browser. Object names are selected server-side; no SQL editor. */
window.DevDatabase = (() => {
  "use strict";
  const { $, esc } = window.SongRankerUI;
  let U,
    items = [],
    chosen = "",
    offset = 0,
    tab = "rows",
    data = null,
    error = "",
    busy = false,
    objectQuery = "",
    ticket = 0,
    cellTicket = 0;
  const btn = (label, attrs) =>
    `<button type="button" class="btn" ${attrs}>${label}</button>`;
  function close() {
    ++ticket;
    ++cellTicket;
    data = null;
    busy = false;
  }
  function mount(rows) {
    items = rows;
    if (!items.some((r) => r.name === chosen))
      chosen = items.find((r) => r.kind === "table")?.name || "";
    draw();
    if (chosen) load();
  }
  function draw() {
    const node = $("#system-inventory");
    if (!node) return;
    const scroll = node.querySelector(".db-objects")?.scrollTop || 0;
    node.innerHTML = `<div class="db-browser"><aside><label>Find an object<input id="db-object-query" type="search" value="${esc(objectQuery)}" placeholder="Table or view…"></label><div class="db-objects">${items.map((r) => `<button type="button" class="db-object ${chosen === r.name ? "active" : ""}" data-db-object="${esc(r.name)}" ${r.name.toLowerCase().includes(objectQuery.toLowerCase()) ? "" : "hidden"} aria-pressed="${chosen === r.name}"><code>${esc(r.name)}</code><small>${esc(r.kind)} · ${r.rows ?? "—"} rows</small></button>`).join("")}</div></aside><div class="db-inspection"><div class="section-head"><h3>${esc(chosen || "Choose a table")}</h3><span class="muted">Read only</span></div><div class="system-actions db-tabs">${["rows", "columns", "definition"].map((t) => btn(t[0].toUpperCase() + t.slice(1), `data-db-tab="${t}" aria-pressed="${tab === t}"`)).join("")}${btn("Refresh", `data-db-refresh ${busy ? "disabled" : ""}`)}</div><p role="status" class="${error ? "error" : "muted"}">${esc(error || (busy ? "Loading…" : data ? data.total + " rows · " + data.columns.length + " columns" : ""))}</p><div id="db-content">${content()}</div></div></div>`;
    node.querySelector(".db-objects").scrollTop = scroll;
  }
  function content() {
    if (!data) return "";
    if (tab === "definition")
      return `<pre class="db-definition">${esc(data.object.sql || "SQLite internal object")}</pre><h4>Foreign keys</h4><pre>${esc(JSON.stringify(data.foreign_keys, null, 2))}</pre><h4>Indexes</h4><pre>${esc(JSON.stringify(data.indexes, null, 2))}</pre>`;
    if (tab === "columns")
      return `<div class="db-scroll"><table class="data-table"><thead><tr>${["Column", "Type", "Not null", "Default", "Primary key", "Hidden / generated"].map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${data.columns.map((c) => `<tr><td><code>${esc(c.name)}</code></td><td>${esc(c.type || "Unspecified")}</td><td>${c.notnull ? "Yes" : "No"}</td><td>${c.dflt_value == null ? "—" : esc(c.dflt_value)}</td><td>${c.pk || "—"}</td><td>${{ 1: "Hidden", 2: "Generated (virtual)", 3: "Generated (stored)" }[c.hidden] || "—"}</td></tr>`).join("")}</tbody></table></div>`;
    return `<div class="db-scroll"><table class="data-table db-rows"><thead><tr><th>Row</th>${data.columns.map((c) => `<th>${esc(c.name)}</th>`).join("")}</tr></thead><tbody>${data.rows.map((r, i) => `<tr><th>${data.offset + i + 1}</th>${r.cells.map((c, j) => `<td><button type="button" data-db-cell="${i}" data-db-column="${j}" title="Inspect ${esc(data.columns[j].name)}"><small>${esc(c.type)}${c.encoding ? " · " + esc(c.encoding) : ""}</small><span>${c.type === "null" ? "NULL" : esc(c.value)}${c.truncated ? "…" : ""}</span></button></td>`).join("")}</tr>`).join("")}</tbody></table>${!data.rows.length ? '<p class="empty">No rows.</p>' : ""}</div><div class="db-pager">${btn("Previous", `data-db-page="-1" ${!offset || busy ? "disabled" : ""}`)}<span>${data.total ? data.offset + 1 : 0}–${Math.min(data.offset + data.rows.length, data.total)} of ${data.total}</span>${btn("Next", `data-db-page="1" ${offset + data.limit >= data.total || busy ? "disabled" : ""}`)}</div>`;
  }
  async function load() {
    const own = ++ticket;
    busy = true;
    error = "";
    data = null;
    draw();
    try {
      const r = await U.api(
        "/api/dev/database/inspect?name=" +
          encodeURIComponent(chosen) +
          "&offset=" +
          offset,
      );
      if (own !== ticket || !$("#system-inventory")) return;
      data = r;
      const item = items.find((v) => v.name === chosen);
      if (item) item.rows = r.total;
    } catch (e) {
      if (own === ticket) error = e.message;
    } finally {
      if (own === ticket) {
        busy = false;
        draw();
      }
    }
  }
  async function inspectCell(row, column, start = 0) {
    const own = ++cellTicket;
    U.openDialog(
      "Stored value",
      `<p data-db-cell-owner="${own}" role="status">Loading value…</p>`,
    );
    $("#editor-submit").hidden = true;
    try {
      const r = await U.api(
        "/api/dev/database/cell?review_token=" +
          encodeURIComponent(row.review_token) +
          "&column=" +
          column +
          "&start=" +
          start,
      );
      if (
        own !== cellTicket ||
        !$("#editor").open ||
        !$('[data-db-cell-owner="' + own + '"]')
      )
        return;
      $("#editor-fields").innerHTML =
        `<div class="db-cell-detail" data-db-cell-owner="${own}"><strong>${esc(r.column)}</strong><p>${esc(r.type)}${r.encoding ? " · " + esc(r.encoding) : ""} · ${r.total} ${esc(r.unit || "values")}</p><pre>${r.value === null ? "NULL" : esc(r.value)}</pre><div class="db-pager">${btn("Previous", `data-db-chunk="${Math.max(0, start - r.limit)}" ${!start ? "disabled" : ""}`)}<span>${start}–${Math.min(start + r.limit, r.total)}</span>${btn("Next", `data-db-chunk="${start + r.limit}" ${!r.truncated ? "disabled" : ""}`)}</div></div>`;
      $("#editor-fields")
        .querySelectorAll("[data-db-chunk]")
        .forEach(
          (b) =>
            (b.onclick = () =>
              inspectCell(row, column, Number(b.dataset.dbChunk))),
        );
    } catch (e) {
      if (own === cellTicket && $('[data-db-cell-owner="' + own + '"]'))
        $("#editor-fields").innerHTML =
          `<p class="error" role="alert">${esc(e.message)}</p>`;
    }
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!U || !b || b.disabled) return;
    if (b.dataset.dbObject) {
      chosen = b.dataset.dbObject;
      offset = 0;
      load();
    }
    if (b.dataset.dbTab) {
      tab = b.dataset.dbTab;
      draw();
    }
    if (b.hasAttribute("data-db-refresh")) load();
    if (b.dataset.dbPage) {
      offset = Math.max(0, offset + Number(b.dataset.dbPage) * data.limit);
      load();
    }
    if (b.hasAttribute("data-db-cell"))
      inspectCell(
        data.rows[Number(b.dataset.dbCell)],
        Number(b.dataset.dbColumn),
      );
  });
  document.addEventListener("input", (e) => {
    if (e.target.id === "db-object-query") {
      objectQuery = e.target.value;
      const q = objectQuery.toLowerCase();
      document
        .querySelectorAll("[data-db-object]")
        .forEach(
          (b) => (b.hidden = !b.dataset.dbObject.toLowerCase().includes(q)),
        );
    }
  });
  document.addEventListener(
    "close",
    (e) => {
      if (e.target.id === "editor") ++cellTicket;
    },
    true,
  );
  window.addEventListener("pagehide", (e) => {
    if (!e.persisted) close();
  });
  return { bindUI: (ui) => (U = ui), mount, close };
})();

/* Read-only selector inspection. The server owns pools, rules and probabilities. */
window.DevSelection = (() => {
  "use strict";
  const { $, esc } = window.SongRankerUI;
  let U,
    active = false,
    request = 0,
    data = null,
    poolKey = "standard",
    query = "",
    limit = 25;
  const number = (v) =>
    v == null
      ? "—"
      : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
  const percent = (v) => (v == null ? "—" : number(100 * v) + "%");
  const figure = (value, label) =>
    `<div><b>${value}</b><span>${label}</span></div>`;
  const bar = (label, value) =>
    `<div class="selection-bar" role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" ${value == null ? 'aria-valuetext="No eligible data"' : `aria-valuenow="${value}"`}><span style="width:${value ?? 0}%"></span></div>`;
  function mix(title, left, right, leftLabel, rightLabel) {
    return `<div class="selection-inset"><h3>${title}</h3><div class="selection-mix" role="img" aria-label="${leftLabel} ${percent(left)}, ${rightLabel} ${percent(right)}"><span style="width:${left * 100}%"></span><span style="width:${right * 100}%"></span></div><div class="selection-legend"><span>${leftLabel} <b>${percent(left)}</b></span><span>${rightLabel} <b>${percent(right)}</b></span></div></div>`;
  }
  function draw() {
    if (!active || !data) return;
    const w = data.weights,
      c = data.challenge,
      s = data.shelves;
    U.root().innerHTML =
      U.title(
        "Selection health",
        '<button class="btn" type="button" data-selection-refresh>Refresh snapshot</button>',
      ) +
      `<div id="selection-health" class="selection-health">
   <section class="panel dashboard-surface"><div class="section-head"><h2>Data coverage</h2></div><p class="selection-analysis">${data.preview_flags || 0} privately flagged previews · <a class="song" href="/api/dev/analysis" download="song-ranker-analysis.json">Download analysis ↗</a></p><div class="selection-quality">${data.quality.map((row) => `<div class="selection-inset"><h3>${esc(row.label)}</h3><strong class="health-state" data-level="${row.health?.level || "new"}">${esc(row.health?.label || "Unavailable")}</strong>${bar(row.label, row.percent)}<small>${row.count} / ${row.total} tracks</small></div>`).join("")}</div></section>
   <section class="panel dashboard-surface"><div class="section-head"><h2>Live eligible pools</h2></div><div class="selection-pools">${data.pools.map((p) => `<div class="selection-inset"><h3>${esc(p.label)}</h3><div class="joined-metrics" data-columns="3">${figure(p.eligible, "Eligible " + p.unit)}${figure(p.tested, "Tested")}${figure(p.untested, "Untested")}</div><p><span class="health-state" data-level="${p.health?.balance.level || "new"}">${esc(p.health?.balance.label || "Unavailable")}</span> · ${esc(p.health?.stage || "Starting")}</p><div class="selection-facts"><span>Exposure dispersion <b>${number(p.health?.dispersion)}</b></span><span>Mean exposure <b>${number(p.mean)}</b></span>${p.first_round_exposures == null ? "" : `<span>Round 1 Elo weight <b>${number(p.first_round_exposures)}</b></span>`}<span>Below mean <b>${p.below}</b></span>${p.spread == null ? "" : `<span>Elo spread <b>${number(p.spread)}</b></span><span>${esc(p.health?.elo.label || "Settling")} <b>${number(p.health?.reference_low)}–${number(p.health?.reference_high)} reference</b></span>`}${p.policy ? `<span>Support strength <b>×${number(p.policy.strength)}</b></span>${["standard", "blind"].includes(p.key) ? `<span>Opponent floor <b>${number(p.policy.match_floor * 100)}%</b></span><span>Closeness bandwidth <b>×${number(p.policy.bandwidth)}</b></span>` : ""}` : ""}<span>Draw <b class="${p.ready ? "song" : "error"}">${p.ready ? "Ready" : "Needs more eligible data"}</b></span></div></div>`).join("")}</div></section>
   <section class="panel dashboard-surface"><div class="section-head"><h2>Weights in use</h2></div><div class="selection-rule-grid">${mix("Exposure balancing", w.shortfall, w.exploration, "Adaptive support", "Uniform")}${mix("Voting kernel · starting baseline", w.match_floor, w.match_close, "Floor", "Elo closeness")}${mix("Guesser gap kernel", w.guess_floor, w.guess_target, "Floor", "Target match")}</div><div class="selection-facts"><span>Guesser width <b>${percent(w.guess_width)}</b></span><span>Previous Guesser pair multiplier <b>×${number(w.previous)}</b></span><span>Restricted first-round Elo <b>½ influence</b></span></div></section>
   <section class="panel dashboard-surface"><div class="section-head"><h2>Challenge &amp; Shelves balance</h2></div><div class="selection-rule-grid"><div class="selection-inset"><h3>Guesser target gap rank</h3><strong>${percent(c.target)}</strong><p>${c.current_run ? "Current browser run" : "New-run baseline"} · ${c.streak} streak</p><div class="selection-facts">${c.samples.map((r) => `<span>${r.streak} streak <b>${percent(r.target)}</b></span>`).join("")}</div></div><div class="selection-inset"><h3>Shelves formats</h3><strong>${s.formats.length ? s.formats.map((n) => n + " albums").join(" / ") : "Unavailable"}</strong><p>${s.albums} eligible albums · ${s.tracks} tracks</p><div class="selection-facts">${s.cycles.map((r) => `<span>${r.size}-album draw <b>${number(s.formats_share)}% format chance</b><small>${number(r.cycle)} rounds per expected album cycle</small></span>`).join("")}</div></div></div></section>
   <section class="panel dashboard-surface"><div class="section-head"><h2>Inspect draw weights</h2></div><div class="selection-controls"><label>Pool<select id="selection-pool">${data.pools.map((p) => `<option value="${p.key}">${esc(p.label)}</option>`).join("")}</select></label><label>Find a track or album<input id="selection-query" type="search" placeholder="Name, album or #ID…" value="${esc(query)}"></label></div><div id="selection-detail"></div></section>
  </div>`;
    $("#selection-pool").value = poolKey;
    drawRows();
  }
  function drawRows() {
    if (!active || !data || !$("#selection-detail")) return;
    const pool = data.pools.find((p) => p.key === poolKey) || data.pools[0];
    poolKey = pool.key;
    const q = query.trim().toLocaleLowerCase(),
      rows = pool.rows.filter((r) =>
        (r.name + " " + r.album + " #" + r.id).toLocaleLowerCase().includes(q),
      );
    const label =
      pool.key === "shelves"
        ? "Album base share"
        : pool.key.startsWith("tournament")
          ? "Initial entry share"
          : pool.key === "trivia"
            ? "Track draw share"
            : "Anchor draw share";
    $("#selection-detail").innerHTML =
      `<div class="joined-metrics" data-columns="4">${figure(number(pool.total), "Total exposures")}${figure(number(pool.effective), "Effective pool size")}${figure(percent(pool.min_share), "Smallest active share")}${figure(percent(pool.max_share), "Largest share")}</div><p class="selection-note">${pool.key === "shelves" ? "Base album weights; recency and ten-track capacity apply during selection." : pool.key.startsWith("tournament") ? "Whole-library first entry; later entries are drawn without replacement." : pool.key === "trivia" ? "New-draw weights, after the previous-track exclusion." : pool.key === "guesser" ? "Anchor weights include the previous-pair multiplier; the second song uses the gap kernel." : "Anchor weights favour low evidence and recent additions; opponent closeness tightens gradually with this pool’s mean."} Saved questions stay frozen.</p><p class="selection-count" role="status">${rows.length} matching ${pool.unit} · ${pool.available} active weights${pool.ready ? "" : " · draw unavailable"} · bars relative to largest share</p><div class="data-scroll"><table class="data-table selection-table"><thead><tr><th>${pool.kind === "album" ? "Album" : "Track"}</th><th>Exposures</th><th>Base share</th><th>${label}</th></tr></thead><tbody>${
        rows
          .slice(0, limit)
          .map(
            (r) =>
              `<tr><td><a class="${pool.kind}" href="${pool.kind === "album" ? "/album/" + encodeURIComponent(r.name) : "/song/" + r.id}" title="${esc(r.name)}">${esc(r.name)}</a><small>${esc(r.album)} · #${r.id}${r.cooling ? " · previous round" : ""}</small></td><td>${number(r.exposure)}</td><td>${percent(r.base_probability)}</td><td><strong>${percent(r.probability)}</strong>${bar(r.name + " weight relative to largest share", pool.max_share ? (100 * r.probability) / pool.max_share : 0)}</td></tr>`,
          )
          .join("") ||
        '<tr><td colspan="4">No matching eligible records.</td></tr>'
      }</tbody></table></div>${rows.length > limit ? '<div class="system-actions"><button class="btn" type="button" data-selection-more>Show 25 more</button></div>' : ""}`;
  }
  async function render() {
    active = true;
    const id = ++request;
    U.root().innerHTML =
      U.title("Selection health") +
      '<p role="status">Reading selection snapshot…</p>';
    try {
      const next = await U.api("/api/dev/selection-health");
      if (!active || id !== request) return;
      data = next;
      draw();
    } catch (error) {
      if (active && id === request)
        U.root().innerHTML =
          U.title("Selection health") +
          `<p class="error" role="alert">${esc(error.message)}</p><button class="btn" type="button" data-selection-refresh>Retry snapshot</button>`;
    }
  }
  document.addEventListener("click", (e) => {
    if (!active) return;
    const b = e.target.closest("button");
    if (b?.hasAttribute("data-selection-refresh")) render();
    if (b?.hasAttribute("data-selection-more")) {
      limit += 25;
      drawRows();
    }
  });
  document.addEventListener("input", (e) => {
    if (active && e.target.id === "selection-query") {
      query = e.target.value;
      limit = 25;
      drawRows();
    }
  });
  document.addEventListener("change", (e) => {
    if (active && e.target.id === "selection-pool") {
      poolKey = e.target.value;
      limit = 25;
      drawRows();
    }
  });
  return {
    bindUI: (ui) => (U = ui),
    render,
    viewChanged: (next) => {
      if (next !== "selection_health") {
        active = false;
        ++request;
      }
    },
  };
})();
