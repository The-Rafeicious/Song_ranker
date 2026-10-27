/* Shared presentation helpers. Game state, requests, grading and audio stay
   with their modules; include this before those deferred scripts. */
window.SongRankerUI = (() => {
  "use strict";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
  ];
  const escapes = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => escapes[character]);
  function trackPosition(song, labelled = false) {
    const disc = song.disc_number || 1, track = song.track_number || "—";
    return labelled ? `Disc ${disc} · Track ${track}` : disc > 1 ? `${disc}·${track}` : String(track);
  }
  // Search ignores accents; tag identity preserves them and normalises whitespace.
  const searchText = (value) =>
    String(value ?? "")
      .normalize("NFKD")
      .replace(/\p{M}/gu, "")
      .replace(/[’‘]/g, "'")
      .toLocaleLowerCase()
      .trim();
  const identityText = (value) =>
    String(value ?? "")
      .normalize("NFKC")
      .toLocaleLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  const impactText = (value) =>
    Number.isFinite(value) ? value.toFixed(1) : "—";
  const ratio = (right, total) =>
    total ? Number(((100 * right) / total).toFixed(1)) + "%" : "—";
  const sumFields = (rows, keys) =>
    Object.fromEntries(
      keys.map((key) => [
        key,
        rows.reduce((sum, row) => sum + Number(row[key] || 0), 0),
      ]),
    );
  const entityTypes = Object.freeze(["songs", "artists", "albums", "tags"]);
  const entityLabels = Object.freeze({
    songs: "Song",
    artists: "Artist",
    albums: "Album",
    tags: "Tag",
  });
  const entityColour = (type) =>
    ({ songs: "song", artists: "artist", albums: "album", tags: "tag" })[type];
  function shelfHead(title, key, href, label = "View all") {
    return `<div class="section-head"><h2>${esc(title)}</h2><div class="shelf-controls"><a href="${esc(href)}">${esc(label)} ↗</a><button class="icon-btn" data-scroll="${esc(key)}" data-dir="-1" aria-label="Scroll ${esc(title)} left">‹</button><button class="icon-btn" data-scroll="${esc(key)}" data-dir="1" aria-label="Scroll ${esc(title)} right">›</button></div></div>`;
  }
  // Keep this read-only policy in parity with impact.py; no stored rating changes.
  function impactModel(songs, peers) {
    const rated = (rows) =>
      new Map(
        rows
          .filter((s) => s.id != null && s.matches_played > 0 && Number.isFinite(s.elo_score))
          .map((s) => [s.id, s.elo_score]),
      );
    const library = rated(songs),
      ids = (rows) => [...rated(rows).keys()].filter((id) => library.has(id));
    const sizes = peers
      .map((group) => ids(group).length)
      .filter(Boolean)
      .sort((a, b) => a - b);
    const baseline = library.size
      ? [...library.values()].reduce((n, v) => n + v, 0) / library.size
      : 1200;
    const mid = Math.floor(sizes.length / 2),
      prior = Math.sqrt(sizes.length
        ? sizes.length % 2
          ? sizes[mid]
          : (sizes[mid - 1] + sizes[mid]) / 2
        : 1);
    return {
      baseline,
      prior_tracks: prior,
      measure(rows) {
        const linked = ids(rows),
          n = linked.length,
          average = n
            ? linked.reduce((total, id) => total + library.get(id), 0) / n
            : null,
          support = n / (n + prior);
        return {
          impact_score: n ? baseline + support * (average - baseline) : null,
          impact_average: average,
          impact_tracks: n,
          impact_support: support,
          impact_baseline: baseline,
          impact_prior_tracks: prior,
        };
      },
    };
  }
  // One navigation and row renderer for the five mode boards.
  function modeRankingControls(
    path,
    type,
    bottom,
    action,
    categories = ["songs", "artists", "albums", "tags"],
  ) {
    const query = (entity) =>
      `${path}?entity=${entity}&view=${bottom ? "bottom" : "top"}`;
    return `<nav class="rank-links" aria-label="Ranking category">${categories.map((entity) => `<a style="--category-color:var(--${entityColour(entity)})" class="${entity === type ? "active" : ""}" ${entity === type ? 'aria-current="page"' : ""} href="${query(entity)}">${entity[0].toUpperCase() + entity.slice(1)}</a>`).join("")}</nav><div class="ranking-switch pill-nav" aria-label="Ranking range"><button class="pill ${bottom ? "" : "active"}" data-${action}-view="top" aria-pressed="${!bottom}">Top twenty</button><button class="pill ${bottom ? "active" : ""}" data-${action}-view="bottom" aria-pressed="${bottom}">Bottom twenty</button></div>`;
  }
  function modeRankingRow(
    U,
    row,
    type,
    index,
    total,
    bottom,
    tone,
    score,
    label,
    facts,
    rank = null,
  ) {
    const record =
      U.records(type).find((item) => Number(item.id) === Number(row.id)) || row;
    const info =
      type === "artists" || type === "tags"
        ? {
            html: esc((record.song_count || 0) + " songs"),
            text: (record.song_count || 0) + " songs",
          }
        : U.rankingMetadata(
            type === "songs" &&
              !U.properAlbum(
                U.records("albums").find(
                  (album) => Number(album.id) === Number(record.album_id),
                ),
              )
              ? { ...record, album: "" }
              : record,
            type,
          );
    const standing =
      Number.isInteger(rank) && rank > 0
        ? rank
        : bottom
          ? total - index
          : index + 1;
    return `<article class="leader-row ${!bottom && standing <= 3 ? "top-three" : ""}" style="${U.rankGlow(rank == null || bottom ? index : standing - 1, bottom, tone)}"><span class="leader-rank" aria-label="Rank ${standing}">${bottom ? standing : ["🥇", "🥈", "🥉"][standing - 1] || standing}</span><a href="${U.urlFor(type, row)}" aria-label="${esc(row.name)}">${U.artwork(record, type)}</a><div class="special-rank-copy"><a class="leader-title ${U.colour(type)}" title="${esc(row.name)}" href="${U.urlFor(type, row)}">${esc(row.name)}</a><div class="leader-meta" title="${esc(info.text)}">${info.html}</div><div class="leader-votes ${tone}" aria-label="Ranking context">${facts.map((f) => `<span>${esc(f)}</span>`).join("")}</div></div><div class="leader-score ${tone}">${esc(score)}<small>${esc(label)}</small></div></article>`;
  }
  return Object.freeze({
    $,
    $$,
    esc,
    searchText,
    identityText,
    ratio,
    impactModel,
    impactText,
    sumFields,
    trackPosition,
    entityTypes,
    entityLabels,
    entityColour,
    shelfHead,
    modeRankingControls,
    modeRankingRow,
  });
})();
