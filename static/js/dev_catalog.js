/* Developer import/source/Single workflows. Never loaded on public game pages. */
window.DevCatalog = (() => {
  "use strict";
  const { $, $$, esc } = window.SongRankerUI;
  let U,
    rows = [],
    query = "",
    country = "gb",
    keep = true,
    showMatches = false,
    asSingle = false,
    limit = 20;
  let searching = false,
    mutating = false,
    request = 0,
    summaries = {},
    loaded = false,
    sourceError = "",
    loading = null;
  let dialogState = null,
    dialogGeneration = 0,
    sourceBatch = null;
  const norm = window.SongRankerUI.identityText;
  const song = (id) => U.records("songs").find((s) => s.id === Number(id));
  const duration = (ms) =>
    Number.isFinite(Number(ms)) && ms > 0
      ? `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}`
      : "Duration unknown";
  const sourceText = (id) =>
    summaries[id]?.status === "linked"
      ? "Linked"
      : sourceError
        ? "Unavailable"
        : !loaded
          ? "Loading…"
          : "Needs link";
  const contentText = (id) => summaries[id]?.content_label || "Not explicit";
  const sourceValue = (id, key) => summaries[id]?.source?.[key] ?? "";
  function releaseDialog() {
    dialogGeneration++;
    dialogState = null;
    const a = $("#catalog-audio");
    if (a) {
      window.PreviewPlayback?.cancel(a);
      a.pause();
    }
  }
  function open(title, body, state) {
    U.openDialog(title, `<div class="catalog-dialog">${body}</div>`);
    dialogState = state;
    $("#editor-submit").hidden = true;
    return dialogGeneration;
  }
  function error(message) {
    const n = $("#editor-error");
    if (dialogState && n) {
      n.hidden = false;
      n.textContent = message;
      n.focus();
    } else U.toast(message);
  }
  function sourceMarkup(source) {
    if (!source)
      return '<p class="catalog-note">Apple source unknown. Use an exact song link to check the recording.</p>';
    return `<div class="catalog-source-facts"><strong class="catalog-flag" data-explicitness="${esc(source.explicitness)}">${source.content_assumed ? "Default" : "Apple"}: ${esc(source.content_label)}</strong><span>${esc(duration(source.duration_ms))}</span><span>Store ${esc(source.storefront.toUpperCase())}</span><span>Track ID ${esc(source.track_id)}</span>${source.radio_hint ? "<span>Radio edit/version in title</span>" : ""}${source.track_url ? `<a class="song" href="${esc(source.track_url)}" target="_blank" rel="noopener noreferrer">Open Apple song ↗</a>` : ""}</div>`;
  }
  function summaryMarkup(id) {
    const s = summaries[id];
    return `<div class="catalog-source-summary" data-catalog-summary="${Number(id)}"><strong>${esc(sourceText(id))}</strong>${s?.source ? sourceMarkup(s.source) : '<span class="catalog-note">Not explicit by default; a saved explicit/cleaned flag takes priority.</span>'}${s?.source && s.preview_matches === false ? '<span class="catalog-note">Local preview differs from the saved Apple source.</span>' : ""}</div>`;
  }
  function publishSources() {
    U.sourcesChanged?.();
    $$("[data-catalog-summary]").forEach((n) => {
      n.outerHTML = summaryMarkup(Number(n.dataset.catalogSummary));
    });
  }
  function rememberSource(result) {
    if (!result.source?.track_id) return;
    summaries[result.song_id] = {
      status: "linked",
      source_id: result.source_id,
      source: result.source,
      content_label: result.source.content_label,
      preview_matches: null,
    };
    publishSources();
  }
  async function refreshSavedSource(result) {
    rememberSource(result);
    let failed = false;
    try {
      await U.refresh();
    } catch {
      failed = true;
    }
    try {
      await ensureSources(true);
    } catch {
      failed = true;
    }
    return failed
      ? "Source saved. Some page data could not refresh; reload to update it."
      : result.message || "Source saved";
  }
  async function ensureSources(force = false) {
    if (loading && !force) return loading;
    if (loaded && !force) return summaries;
    const seq = ++request;
    loading = (async () => {
      try {
        const result = await U.api("/api/dev/song-sources");
        if (seq !== request) return summaries;
        summaries = result.songs || {};
        loaded = true;
        sourceError = "";
        publishSources();
        return summaries;
      } catch (e) {
        if (seq === request) {
          sourceError = e.message;
          U.toast(e.message);
        }
        throw e;
      } finally {
        if (seq === request) loading = null;
      }
    })();
    return loading;
  }
  function matches(row) {
    const known = new Map(
      (row.library_matches || [])
        .filter(
          (m) =>
            song(m.song_id) &&
            (m.kind !== "source_id" ||
              !loaded ||
              summaries[m.song_id]?.source?.track_id === row.source.track_id),
        )
        .map((m) => [m.song_id, m]),
    );
    for (const local of U.records("songs")) {
      const source = summaries[local.id]?.source;
      const names = (local.artist_ids || []).map(
        (id) => U.records("artists").find((a) => a.id === id)?.name || "",
      );
      if (source?.track_id === row.source.track_id)
        known.set(local.id, {
          song_id: local.id,
          title: local.title,
          album: local.album,
          kind: "source_id",
        });
      else if (
        norm(local.title) === norm(row.title) &&
        [...names, names.join(", ")].some(
          (n) => norm(n) === norm(row.artist),
        ) &&
        !known.has(local.id)
      )
        known.set(local.id, {
          song_id: local.id,
          title: local.title,
          album: local.album,
          kind: "title_artist",
        });
    }
    return [...known.values()];
  }
  function candidate(row) {
    const found = matches(row),
      confirmed = found.some((m) => m.kind === "source_id"),
      added = row.added;
    return `<article class="catalog-card dashboard-surface" data-catalog-track="${esc(row.source.track_id)}"><div class="catalog-art">${U.artwork({ ...row, name: row.title }, "songs")}</div><div class="catalog-copy"><h3 class="song catalog-name" title="${esc(row.title)}">${esc(row.title)}</h3><p class="artist catalog-name" title="${esc(row.artist)}">${esc(row.artist)}</p><p class="album catalog-name" title="${esc(row.album)}">${esc(row.album || "No album")}</p><p class="catalog-note">${esc(row.release_date || "Release date unknown")} · ${Number(row.disc_count) > 1 ? `Disc ${esc(row.disc_number)} · source track ${esc(row.source_track_number)} · local position left blank` : row.track_number ? `Track ${row.track_number}` : "Track position unknown"}</p>${sourceMarkup(row.source)}${found.length ? `<p class="catalog-note">${confirmed ? "Saved Apple identity already linked" : `${found.length} matching ${found.length === 1 ? "title" : "titles"} · version unverified`}</p>` : ""}</div><div class="catalog-actions">${confirmed || added ? '<strong class="song">✓ In library</strong>' : `<button class="btn primary" type="button" data-import="${row.id}" ${mutating ? "disabled" : ""}>${found.length ? "Add separately" : "Add"}</button>`}<button class="btn" type="button" data-catalog-review="${row.id}">${found.length ? "Review matches" : "Release details"}</button></div></article>`;
  }
  function renderResults() {
    const root = $("#apple-results");
    if (!root) return;
    const hidden = rows.filter((r) => r.added || matches(r).length).length;
    const visible = rows.filter(
      (r) => showMatches || (!r.added && !matches(r).length),
    );
    $("#apple-result-count").textContent = rows.length
      ? `${visible.length} ${showMatches ? "results" : "new tracks"} · ${hidden} library matches${showMatches ? "" : " hidden"}`
      : "No search yet";
    root.innerHTML =
      visible.slice(0, limit).map(candidate).join("") ||
      (rows.length
        ? '<div class="empty">No new tracks in these results. Show library matches to review versions or saved sources.</div>'
        : '<div class="empty">Search by song and artist, or paste an Apple song/album link.</div>');
    const more = $("#apple-more");
    more.hidden = limit >= visible.length;
    more.disabled = mutating;
  }
  function renderImport() {
    U.root().innerHTML =
      U.title("Apple Music") +
      `<section class="panel dashboard-surface catalog-workbench"><form class="search-form catalog-search" id="apple-search"><input id="apple-query" type="search" value="${esc(query)}" placeholder="Song and artist, or Apple song/album link…" aria-label="Search Apple Music"><label class="catalog-store">Store<input id="apple-country" value="${esc(country)}" maxlength="2" pattern="[A-Za-z]{2}" aria-label="Two-letter Apple store" required></label><button type="submit" aria-label="Search Apple Music" ${searching ? "disabled" : ""}>Search</button></form><div class="catalog-options"><label><input type="checkbox" id="keep-import" ${keep ? "checked" : ""}>Keep search after adding</label><label><input type="checkbox" id="show-apple-matches" ${showMatches ? "checked" : ""}>Show library matches</label><label><input type="checkbox" id="apple-as-single" ${asSingle ? "checked" : ""}>Add as hidden Single</label></div><p class="catalog-note">Matching titles need version review. “Not explicit” does not identify a radio edit.</p><p id="apple-status" role="status" aria-live="polite" ${searching ? "" : "hidden"}>${searching ? "Searching Apple…" : ""}</p><p id="apple-result-count" role="status" aria-live="polite"></p>${U.tagPicker()}<div id="apple-results"></div><button class="btn" id="apple-more" type="button" data-catalog-more hidden>Show 20 more</button></section>`;
    U.renderTagPicker();
    renderResults();
    ensureSources().catch(() => {});
  }
  async function search() {
    if (searching || mutating) return;
    query = $("#apple-query").value.trim();
    country = $("#apple-country").value.trim().toLowerCase();
    const n = $("#apple-status"),
      button = $("#apple-search button"),
      root = $("#apple-results");
    searching = true;
    button.disabled = true;
    n.hidden = false;
    n.classList.remove("error");
    n.textContent = "Searching Apple…";
    try {
      const result = await U.api(
        "/api/dev/search_apple?q=" +
          encodeURIComponent(query) +
          "&country=" +
          encodeURIComponent(country),
      );
      rows = result.map((r, i) => ({ ...r, id: i + 1 }));
      limit = 20;
      try {
        const link = new URL(query);
        if (link.searchParams.has("i") || link.pathname.includes("/song/"))
          showMatches = true;
      } catch {}
      if ($("#apple-results")) {
        $("#show-apple-matches").checked = showMatches;
        renderResults();
        $("#apple-status").hidden = true;
        try {
          const link = new URL(query);
          if (
            ["music.apple.com", "www.music.apple.com"].includes(
              link.hostname,
            ) &&
            link.pathname.includes("/album/") &&
            !link.searchParams.has("i") &&
            rows.length
          )
            reviewAlbumImport();
        } catch {}
      }
    } catch (e) {
      const current = $("#apple-status");
      if (current) {
        current.hidden = false;
        current.classList.add("error");
        current.textContent = e.message;
      }
    } finally {
      searching = false;
      const current = $("#apple-search button");
      if (current) current.disabled = false;
    }
  }

  function reviewAlbumImport() {
    const tracks = rows.filter((r) => !r.added),
      tags = U.selectedTags().join(", ");
    open(
      "Add album",
      `<h3 class="album">${esc(tracks[0]?.album || "Album")}</h3><p>Untick any songs you do not want to add. Library matches are unticked by default.</p><div class="catalog-actions"><button class="btn" type="button" data-album-import-all>Select new songs</button><button class="btn" type="button" data-album-import-none>Clear selection</button><strong id="album-import-count" role="status"></strong></div><div class="catalog-album-tracks">${tracks.map((r) => `<label class="catalog-check"><input type="checkbox" data-album-import-id="${r.id}" ${matches(r).length ? "" : "checked"}><span><strong class="song">${esc(r.title)}</strong><span class="artist"> · ${esc(r.artist)}</span>${matches(r).length ? " · Library match" : ""}</span></label>`).join("")}</div><p class="catalog-note">Tracks keep their album and source positions. Selected tags apply to every added track.</p><button class="btn primary" type="button" data-album-import-save>Add selected songs</button><p id="album-import-status" role="status"></p><p id="editor-error" class="dialog-error" role="alert" tabindex="-1" hidden></p>`,
      { type: "album-import", tracks, tags },
    );
    updateAlbumSelection();
  }
  function updateAlbumSelection() {
    if (dialogState?.type !== "album-import") return;
    const count = $$("[data-album-import-id]:checked").filter(
      (n) => !n.disabled,
    ).length;
    const label = $("#album-import-count");
    if (label) label.textContent = count + " selected";
  }
  async function saveAlbumImport() {
    const state = dialogState;
    if (state?.type !== "album-import" || mutating) return;
    const selected = $$("[data-album-import-id]:checked")
      .map((n) =>
        state.tracks.find((r) => r.id === Number(n.dataset.albumImportId)),
      )
      .filter((r) => r && !r.added);
    if (!selected.length) {
      error("Select at least one new track.");
      return;
    }
    const gen = dialogGeneration;
    mutating = true;
    state.busy = true;
    const errorNode = $("#editor-error");
    if (errorNode) errorNode.hidden = true;
    $("#album-import-status").textContent =
      "Adding " + selected.length + " songs…";
    $$("#editor-fields button, #editor-fields input").forEach(
      (n) => (n.disabled = true),
    );
    let saved = 0,
      failure = "";
    try {
      for (const row of selected) {
        const result = await U.api("/api/dev/add_song", {
          source_token: row.source_token,
          import_source: "apple",
          genres: state.tags,
          allow_duplicate: matches(row).length > 0,
          placement: "keep",
        });
        if (
          !result.source_id ||
          result.source?.track_id !== row.source.track_id
        )
          throw new Error(
            "Save could not be confirmed. Reload before retrying.",
          );
        row.added = true;
        saved++;
        rememberSource(result);
        if (gen === dialogGeneration) {
          const n = $("#album-import-status");
          if (n) n.textContent = `${saved} of ${selected.length} saved`;
        }
      }
    } catch (e) {
      failure = e.message;
    } finally {
      let refreshFailed = false;
      try {
        await U.refresh();
        await ensureSources(true);
      } catch {
        refreshFailed = true;
      }
      mutating = false;
      state.busy = false;
      renderResults();
      const message = `${saved} of ${selected.length} songs saved.${failure ? " " + failure : ""}${refreshFailed ? " Reload to refresh the catalogue." : ""}`;
      if (gen === dialogGeneration) {
        if (!failure) $("#editor").close();
        else {
          $$("#editor-fields button, #editor-fields input").forEach(
            (n) => (n.disabled = false),
          );
          $$("[data-album-import-id]").forEach((n) => {
            if (
              state.tracks.find((r) => r.id === Number(n.dataset.albumImportId))
                ?.added
            ) {
              n.checked = false;
              n.disabled = true;
            }
          });
          updateAlbumSelection();
          error(message);
        }
      }
      U.toast(message);
    }
  }

  async function add(id) {
    const row = rows.find((r) => r.id === id);
    if (!row || mutating) return;
    if (typeof row.source_token !== "string" || !row.source_token) {
      error(
        "Apple source details are missing. Search again before adding this song.",
      );
      return;
    }
    const gen = dialogGeneration;
    mutating = true;
    renderResults();
    try {
      const result = await U.api("/api/dev/add_song", {
        source_token: row.source_token,
        import_source: "apple",
        genres: U.selectedTags().join(", "),
        allow_duplicate: matches(row).length > 0,
        placement: asSingle ? "single" : "keep",
      });
      if (!result.source_id || result.source?.track_id !== row.source.track_id)
        throw new Error(
          "The Apple source save could not be confirmed. Reload and review this song’s Source before adding again.",
        );
      row.added = true;
      const message = await refreshSavedSource(result);
      if (!keep && rows.includes(row)) {
        rows = [];
        query = "";
        if ($("#apple-query")) $("#apple-query").value = "";
      }
      if (gen === dialogGeneration && dialogState?.type === "review")
        $("#editor").close();
      U.toast(message);
    } catch (e) {
      error(e.message);
    } finally {
      mutating = false;
      renderResults();
    }
  }
  function review(id) {
    const row = rows.find((r) => r.id === id);
    if (!row) return;
    const found = matches(row);
    open(
      "Apple release details",
      `<h3 class="song">${esc(row.title)}</h3><p class="artist">${esc(row.artist)}</p><p class="album">${esc(row.album)}</p><p>${esc(row.release_date || "Release date unknown")}</p>${sourceMarkup(row.source)}<p class="catalog-note">Censored title text and missing labels do not confirm a cleaned recording.</p>${found.length ? `<h3>Library matches</h3>${found.map((m) => `<div class="catalog-match"><div><strong class="song">${esc(m.title)}</strong><p>#${m.song_id} · ${esc(m.album || "No album")} · ${m.kind === "source_id" ? "Same Apple ID" : "Title/artist match only"}</p></div><button class="btn" type="button" data-catalog-link="${m.song_id}" data-catalog-offer="${row.id}">Review source link</button></div>`).join("")}` : `<p class="catalog-note">${Number(row.disc_count) > 1 ? "This is a multi-disc release; no album-wide position was inferred." : "The source position is shown in the search result."}</p><button class="btn primary" type="button" data-import="${row.id}" ${mutating ? "disabled" : ""}>Add track</button>`}`,
      { type: "review", row },
    );
  }
  async function openSource(id, preselected = null, batch = null) {
    const gen = open(
      "Apple source",
      '<p role="status">Loading saved source…</p>',
      { type: "source", songId: id, batch },
    );
    try {
      const result = await U.api("/api/dev/song-source/" + id);
      if (gen !== dialogGeneration) return;
      if (result.current)
        rememberSource({
          song_id: id,
          source_id: result.source_id,
          source: result.current,
        });
      dialogState = {
        type: "source",
        songId: id,
        local: result,
        offer: preselected || batch?.choices.get(id)?.offer || null,
        offers: [],
        busy: false,
        batch,
      };
      drawSource();
      if (batch) await findSource(true);
    } catch (e) {
      if (gen === dialogGeneration) error(e.message);
    }
  }
  function sourceOffers(state) {
    const item = (r, i) =>
      `<div class="catalog-match"><div><strong class="song">${esc(r.title)}</strong><p class="artist">${esc(r.artist)}</p><p class="album">${esc(r.album)} · ${esc(r.release_date || "Date unknown")}</p>${sourceMarkup(r.source)}</div><button class="btn" type="button" data-catalog-source-select="${i}" aria-pressed="${state.offer?.source.track_id === r.source.track_id}">${state.offer?.source.track_id === r.source.track_id ? "✓ Selected" : "Choose this version"}</button></div>`;
    return (
      state.offers.slice(0, 5).map(item).join("") +
      (state.offers.length > 5
        ? `<details class="catalog-more-sources"><summary>Show ${Math.min(10, state.offers.length - 5)} more versions</summary><div class="catalog-extra-sources">${state.offers
            .slice(5, 15)
            .map((r, i) => item(r, i + 5))
            .join("")}</div></details>`
        : "") +
      (state.offers.length > 15
        ? '<p class="catalog-note">More versions exist. Refine the search or paste an exact Apple song link.</p>'
        : "")
    );
  }
  function batchToolbar(batch) {
    return `<div class="catalog-batch-bar"><strong role="status">Song ${batch.index + 1} of ${batch.ids.length} · ${batch.choices.size} chosen</strong><div class="catalog-actions"><button class="btn" type="button" data-source-batch-prev ${batch.index === 0 ? "disabled" : ""}>Previous</button><button class="btn" type="button" data-source-batch-skip>Skip · leave unchanged</button><button class="btn" type="button" data-source-batch-review>Review group</button></div></div>`;
  }
  function drawSource() {
    const state = dialogState,
      local = state.local,
      s = local.song;
    $("#editor-fields").innerHTML =
      `<div class="catalog-dialog">${state.batch ? batchToolbar(state.batch) : ""}<h3 class="song">${esc(s.title)}</h3><p class="artist">${esc(s.artist)}</p><p class="album">${esc(s.album || "No album")}</p><h3>Saved source</h3>${sourceMarkup(local.current)}${local.current ? `<p class="catalog-note">Source title: ${esc(local.current.title)} · ${esc(local.current.artist)}</p>` : ""}<div class="catalog-source-search"><label for="catalog-source-query">Exact Apple song link, or search to choose a version</label><div class="search-form"><input id="catalog-source-query" type="search" value="${esc(state.query ?? s.title + " " + s.artist)}" aria-label="Find the source recording"><button class="btn" type="button" data-catalog-source-search ${state.busy ? "disabled" : ""}>Find source</button></div></div><details class="catalog-source-choices" id="catalog-source-choices" ${state.offer ? "" : "open"}><summary>${state.offer ? "Change selected recording" : "Choose a recording"}</summary><div id="catalog-source-offers">${sourceOffers(state)}</div></details>${state.offer ? `<section class="catalog-selected" aria-label="Confirm selected recording"><h3 role="status">✓ Selected recording</h3><strong class="song">${esc(state.offer.title)}</strong><p class="artist">${esc(state.offer.artist)}</p><p class="album">${esc(state.offer.album)} · ${esc(state.offer.release_date || "Date unknown")}</p>${sourceMarkup(state.offer.source)}${state.batch ? `<p class="catalog-note">Only the source link and its content flag change.</p><button class="btn primary" type="button" data-source-batch-choose>Keep choice & next</button>` : `<div class="catalog-options catalog-options-stack"><label><input type="checkbox" id="catalog-refresh-source">Use Apple’s names, preview and song release date</label><label><input type="checkbox" id="catalog-use-album" disabled>Also use Apple’s album and track position</label></div><p class="catalog-note">With both options off, only the source link is saved. Current placement and custom tags are kept.</p><button class="btn primary" type="button" data-catalog-save-source ${state.busy ? "disabled" : ""}>Save selected source</button>`}</section>` : ""}</div><p id="editor-error" class="dialog-error" role="alert" tabindex="-1" hidden></p>`;
  }
  async function findSource(initial = false) {
    const state = dialogState;
    if (state?.type !== "source" || state.busy) return;
    state.busy = true;
    const gen = dialogGeneration,
      query =
        initial && state.batch?.releaseQuery
          ? state.batch.releaseQuery
          : $("#catalog-source-query").value;
    state.query = query;
    const b = $("[data-catalog-source-search]");
    b.disabled = true;
    b.textContent = "Searching…";
    try {
      const shared = initial && state.batch?.releaseQuery;
      const result =
        shared && state.batch.pool
          ? state.batch.pool
          : await U.api(
              "/api/dev/search_apple?q=" +
                encodeURIComponent(query) +
                "&country=" +
                encodeURIComponent(country),
            );
      if (gen !== dialogGeneration) return;
      if (shared) state.batch.pool = result;
      const local = state.local.song,
        priority = (r) =>
          (norm(r.title) === norm(local.title) ? 2 : 0) +
          (norm(r.album) === norm(local.album) ? 1 : 0);
      state.offers = shared
        ? [...result].sort((a, b) => priority(b) - priority(a))
        : result;
      if (!state.batch) state.offer = null;
      drawSource();
      if (!result.length)
        error("No matching Apple songs returned. Try an exact song link.");
    } catch (e) {
      if (gen === dialogGeneration) error(e.message);
    } finally {
      state.busy = false;
      if (gen === dialogGeneration) {
        const n = $("[data-catalog-source-search]");
        if (n) {
          n.disabled = false;
          n.textContent = "Find source";
        }
      }
    }
  }
  async function saveSource() {
    const state = dialogState;
    if (state?.type !== "source" || !state.offer || state.busy || mutating)
      return;
    state.busy = true;
    mutating = true;
    const gen = dialogGeneration,
      b = $("[data-catalog-save-source]");
    b.disabled = true;
    const refresh = $("#catalog-refresh-source").checked,
      useAlbum = $("#catalog-use-album").checked;
    try {
      const result = await U.api("/api/dev/song-source/" + state.songId, {
        source_token: state.offer.source_token,
        fingerprint: state.local.fingerprint,
        refresh_metadata: refresh,
        use_source_album: useAlbum,
      });
      if (
        !result.source_id ||
        result.source?.track_id !== state.offer.source.track_id
      )
        throw new Error(
          "The Apple source save could not be confirmed. Reload and review this song’s Source.",
        );
      const message = await refreshSavedSource(result);
      if (gen === dialogGeneration) $("#editor").close();
      renderResults();
      U.toast(message);
    } catch (e) {
      if (gen === dialogGeneration) error(e.message);
      else U.toast(e.message);
    } finally {
      state.busy = false;
      mutating = false;
      if (b.isConnected) b.disabled = false;
    }
  }

  async function startSourceBatch(ids, releaseQuery = "") {
    ids = [...new Set(ids)].filter((id) => song(id));
    if (!ids.length) {
      U.toast("Select songs to review first.");
      return;
    }
    if (ids.length > 500) {
      U.toast("Review up to 500 songs at a time.");
      return;
    }
    if (sourceBatch && ids.join() !== sourceBatch.ids.join())
      U.toast(
        "Resuming your pending source group. Discard its draft to start a different selection.",
      );
    if (!sourceBatch)
      sourceBatch = {
        ids,
        index: 0,
        choices: new Map(),
        busy: false,
        releaseQuery,
        pool: null,
      };
    // Resume a pending draft rather than silently dropping reviewed choices.
    const batch = sourceBatch;
    if (batch.finished) {
      reviewSourceBatch();
      return;
    }
    await openSource(batch.ids[batch.index], null, batch);
  }
  async function moveSourceBatch(step, choose = false) {
    const state = dialogState,
      batch = state?.batch;
    if (!batch || state.busy || batch.busy) return;
    if (choose) {
      if (!state.offer) return;
      const other = [...batch.choices].find(
        ([id, c]) =>
          id !== state.songId &&
          c.offer.source.track_id === state.offer.source.track_id,
      );
      if (other) {
        error(
          `This recording is already chosen for song #${other[0]}. Choose another version.`,
        );
        return;
      }
      batch.choices.set(state.songId, {
        offer: state.offer,
        fingerprint: state.local.fingerprint,
        local: state.local,
      });
    }
    if (!choose && step === 1) batch.choices.delete(state.songId);
    if (batch.index + step >= batch.ids.length) {
      batch.finished = true;
      reviewSourceBatch();
      return;
    }
    batch.index = Math.max(0, batch.index + step);
    await openSource(batch.ids[batch.index], null, batch);
  }
  function reviewSourceBatch() {
    const batch = sourceBatch;
    if (!batch || batch.busy || dialogState?.busy) return;
    open(
      "Review source group",
      `<p role="status">${batch.choices.size} chosen · ${batch.ids.length - batch.choices.size} unchanged</p><p class="catalog-note">Closing keeps this draft until you resume, discard it or reload the page.</p><div class="catalog-batch-review">${[...batch.choices].map(([id, c]) => `<article class="catalog-match"><div><strong class="song">${esc(c.local.song.title)}</strong><p class="album">${esc(c.local.current?.original_album || "No saved source")} → ${esc(c.offer.album)}</p><p>${esc(c.local.current?.content_label || "Not explicit")} → ${esc(c.offer.source.content_label)} · Apple ID ${esc(c.offer.source.track_id)}</p></div><button class="btn" type="button" data-source-batch-edit="${id}">Review again</button></article>`).join("") || '<p class="empty">No source changes chosen yet.</p>'}</div><div class="catalog-actions"><button class="btn" type="button" data-source-batch-resume>Continue reviewing</button><button class="btn primary" type="button" data-source-batch-save ${batch.choices.size ? "" : "disabled"}>Save ${batch.choices.size} sources</button><button class="btn danger" type="button" data-source-batch-discard>Discard draft</button></div><p id="editor-error" class="dialog-error" role="alert" tabindex="-1" hidden></p>`,
      { type: "source-batch", batch },
    );
  }
  async function saveSourceBatch() {
    const batch = sourceBatch;
    if (!batch || batch.busy || mutating || !batch.choices.size) return;
    batch.busy = true;
    mutating = true;
    const gen = dialogGeneration;
    $$("#editor-fields button").forEach((n) => (n.disabled = true));
    try {
      const result = await U.api("/api/dev/song-sources/bulk", {
        changes: [...batch.choices].map(([id, c]) => ({
          song_id: id,
          source_token: c.offer.source_token,
          fingerprint: c.fingerprint,
        })),
      });
      sourceBatch = null;
      for (const item of result.songs || []) rememberSource(item);
      if (gen === dialogGeneration) $("#editor").close();
      let failed = false;
      try {
        await U.refresh();
        await ensureSources(true);
      } catch {
        failed = true;
      }
      U.toast(
        failed ? "Sources saved. Reload to refresh the page." : result.message,
      );
    } catch (e) {
      if (gen === dialogGeneration) {
        error(e.message);
        $$("#editor-fields button").forEach((n) => (n.disabled = false));
      } else U.toast(e.message);
    } finally {
      batch.busy = false;
      mutating = false;
    }
  }
  async function openSingle(id) {
    const gen = open(
      "Move to Single",
      '<p role="status">Checking album and release date…</p>',
      { type: "single", songId: id },
    );
    try {
      const plan = await U.api("/api/dev/single/" + id);
      if (gen !== dialogGeneration) return;
      dialogState = { type: "single", songId: id, plan, busy: false };
      $("#editor-fields").innerHTML =
        `<div class="catalog-dialog"><h3 class="song">${esc(plan.title)}</h3><p class="artist">${esc(plan.artist)}</p><p>From <strong class="album">${esc(plan.source_album?.title || "No album")}</strong></p><p>To <strong class="album">${esc(plan.destination_title)}</strong></p><p>Song release date: <strong>${esc(plan.release_date || "Unknown")}</strong>${plan.release_date ? ` · ${esc({ apple: "Apple source", album: "carried from album", manual: "saved song date" }[plan.release_date_origin] || "saved song date")}` : ""}</p><p class="catalog-note">The Single is hidden from proper-album pages. Song ID, previews, ratings and game records stay with the track. Its source position is kept in any saved Apple observation; the local position is cleared.</p>${plan.already_single ? '<strong class="song">Already in a Single</strong>' : `<label class="catalog-check"><input type="checkbox" id="catalog-remove-empty" checked>Remove the previous album if it becomes empty and has no saved references</label>${!plan.cleanup_possible ? '<p class="catalog-note">The previous album will be kept while other tracks or saved records use it.</p>' : ""}<button class="btn primary" type="button" data-catalog-save-single>Move to Single</button>`}</div><p id="editor-error" class="dialog-error" role="alert" tabindex="-1" hidden></p>`;
    } catch (e) {
      if (gen === dialogGeneration) error(e.message);
    }
  }
  async function saveSingle() {
    const state = dialogState;
    if (state?.type !== "single" || state.busy || mutating) return;
    state.busy = true;
    mutating = true;
    const gen = dialogGeneration,
      b = $("[data-catalog-save-single]");
    b.disabled = true;
    try {
      const result = await U.api("/api/dev/single/" + state.songId, {
        fingerprint: state.plan.fingerprint,
        remove_empty_album: $("#catalog-remove-empty").checked,
      });
      await U.refresh();
      await ensureSources(true);
      if (gen === dialogGeneration) $("#editor").close();
      U.toast(result.album_cleanup?.reason || result.message);
    } catch (e) {
      if (gen === dialogGeneration) error(e.message);
      else U.toast(e.message);
    } finally {
      state.busy = false;
      mutating = false;
      if (b.isConnected) b.disabled = false;
    }
  }
  async function openAlbum(id) {
    const gen = open(
      "Album tracks",
      '<p role="status">Loading album tracks…</p>',
      { type: "album", albumId: id },
    );
    try {
      const result = await U.api("/api/dev/album-tracks/" + id);
      if (gen !== dialogGeneration) return;
      $("#editor-fields").innerHTML =
        `<div class="catalog-dialog"><h3 class="album">${esc(result.album.title)}</h3><p>${result.songs.length} tracks · ${esc(result.album.release_date || "Album release date unknown")}</p><audio id="catalog-audio" preload="none"></audio>${result.songs.map((s) => `<article class="catalog-match"><div><strong class="song">${s.track_number ? esc(s.track_number) + ". " : ""}${esc(s.title)}</strong><p>${esc(s.release_date || "Song date unknown")} · ${esc(s.source_summary.content_label)} · ${s.source_summary.status === "linked" ? "Source linked" : "Needs source link"}</p></div><div class="catalog-actions"><button class="btn" type="button" data-catalog-preview="${s.id}" ${s.audio_url ? "" : "disabled"}>Preview</button><button class="btn" type="button" data-catalog-source="${s.id}">Source</button><button class="btn" type="button" data-catalog-single="${s.id}">Make Single</button></div></article>`).join("") || '<p class="empty">No tracks in this album.</p>'}</div><p id="editor-error" class="dialog-error" role="alert" tabindex="-1" hidden></p>`;
      dialogState = { type: "album", albumId: id, songs: result.songs };
    } catch (e) {
      if (gen === dialogGeneration) error(e.message);
    }
  }
  async function preview(id) {
    const item = dialogState?.songs?.find((s) => s.id === id);
    let a = $("#catalog-audio");
    if (!item?.audio_url || !a) return;
    const url =
      window.PreviewPlayback?.source(id, item.audio_url) || item.audio_url;
    if (window.PreviewPlayback) a = window.PreviewPlayback.replace(a, url);
    else {
      a.pause();
      a.src = url;
    }
    a.volume = Number($("#volume-range")?.value ?? 0.5);
    try {
      await (window.PreviewPlayback
        ? window.PreviewPlayback.play(a)
        : a.play());
    } catch (e) {
      error(e.message);
    }
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!U || !b || b.disabled) return;
    if (b.hasAttribute("data-album-import-save")) saveAlbumImport();
    if (
      (b.hasAttribute("data-album-import-all") ||
        b.hasAttribute("data-album-import-none")) &&
      !mutating &&
      dialogState?.type === "album-import"
    ) {
      for (const n of $$("[data-album-import-id]"))
        if (!n.disabled)
          n.checked =
            b.hasAttribute("data-album-import-all") &&
            !matches(
              dialogState.tracks.find(
                (r) => r.id === Number(n.dataset.albumImportId),
              ),
            ).length;
      updateAlbumSelection();
    }
    if (b.dataset.catalogReview) review(Number(b.dataset.catalogReview));
    if (b.dataset.catalogSource) openSource(Number(b.dataset.catalogSource));
    if (b.dataset.catalogSingle) openSingle(Number(b.dataset.catalogSingle));
    if (b.dataset.catalogAlbum) openAlbum(Number(b.dataset.catalogAlbum));
    if (b.dataset.catalogLink)
      openSource(
        Number(b.dataset.catalogLink),
        rows.find((r) => r.id === Number(b.dataset.catalogOffer)),
      );
    if (b.hasAttribute("data-catalog-more")) {
      limit += 20;
      renderResults();
    }
    if (b.hasAttribute("data-catalog-source-search")) findSource();
    if (b.hasAttribute("data-source-batch-choose")) moveSourceBatch(1, true);
    if (b.hasAttribute("data-source-batch-skip")) moveSourceBatch(1);
    if (b.hasAttribute("data-source-batch-prev")) moveSourceBatch(-1);
    if (b.hasAttribute("data-source-batch-review")) reviewSourceBatch();
    if (b.hasAttribute("data-source-batch-save")) saveSourceBatch();
    if (b.hasAttribute("data-source-batch-resume") && sourceBatch) {
      sourceBatch.finished = false;
      openSource(sourceBatch.ids[sourceBatch.index], null, sourceBatch);
    }
    if (b.dataset.sourceBatchEdit && sourceBatch) {
      sourceBatch.finished = false;
      sourceBatch.index = sourceBatch.ids.indexOf(
        Number(b.dataset.sourceBatchEdit),
      );
      openSource(Number(b.dataset.sourceBatchEdit), null, sourceBatch);
    }
    if (
      b.hasAttribute("data-source-batch-discard") &&
      sourceBatch &&
      !sourceBatch.busy
    ) {
      sourceBatch = null;
      $("#editor").close();
    }

    if (
      b.hasAttribute("data-catalog-source-select") &&
      dialogState?.type === "source"
    ) {
      dialogState.offer =
        dialogState.offers[Number(b.dataset.catalogSourceSelect)];
      drawSource();
      const selected = $(".catalog-selected");
      selected?.querySelector("button")?.focus({ preventScroll: true });
      selected?.scrollIntoView?.({
        block: "start",
        behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)")
          .matches
          ? "auto"
          : "smooth",
      });
    }
    if (b.hasAttribute("data-catalog-save-source")) saveSource();
    if (b.hasAttribute("data-catalog-save-single")) saveSingle();
    if (b.dataset.catalogPreview) preview(Number(b.dataset.catalogPreview));
  });
  document.addEventListener("change", (e) => {
    if (!U) return;
    const n = e.target;
    if (n.hasAttribute("data-album-import-id")) updateAlbumSelection();
    if (n.id === "keep-import") keep = n.checked;
    if (n.id === "show-apple-matches") {
      showMatches = n.checked;
      limit = 20;
      renderResults();
    }
    if (n.id === "apple-as-single") asSingle = n.checked;
    if (n.id === "catalog-refresh-source") {
      const album = $("#catalog-use-album");
      album.disabled = !n.checked;
      if (!n.checked) album.checked = false;
    }
  });
  document.addEventListener("submit", (e) => {
    if (!dialogState || e.target.id !== "editor-form") return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (dialogState.type === "source") {
      if (e.submitter?.hasAttribute("data-catalog-save-source")) saveSource();
      else if (document.activeElement?.id === "catalog-source-query")
        findSource();
    }
  });
  document.addEventListener(
    "close",
    (e) => {
      if (e.target.id === "editor") releaseDialog();
    },
    true,
  );
  return {
    isBusy: () => mutating || !!dialogState?.busy || !!sourceBatch?.busy,
    bindUI: (ui) => (U = ui),
    renderImport,
    search,
    add,
    ensureSources,
    sourceText,
    contentText,
    sourceValue,
    summaryMarkup,
    releaseDialog,
    openSource,
    openSingle,
    openAlbum,
    renderResults,
    startSourceBatch,
    resetSourceBatch: () => {
      sourceBatch = null;
    },
  };
})();
