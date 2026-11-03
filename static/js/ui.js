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
  const countFormatter = new Intl.NumberFormat("en-GB", {
    notation: "compact", maximumFractionDigits: 1,
  });
  const countText = (value) => Number.isFinite(value)
    ? Math.abs(value) >= 1000 ? countFormatter.format(value).replace("K", "k") : String(value)
    : "—";
  // Only summary counts are shortened. Ratings, positions, rates and raw tables
  // retain their precision; refreshed summaries are handled by the same observer.
  function refreshCounts() {
    if (typeof document === "undefined" || !document) return;
    document.querySelectorAll(".stat-value, .mode-stats-metrics dd, .mode-stats-small-metrics dd, .global-metric > strong, .pulse-metrics b, .mini-stats b, [data-count]").forEach((node) => {
      const label = node.parentElement.querySelector("dt, .stat-label, small, span")?.textContent || "";
      if (/elo(?! matches)|rating|score|points|mean|average|accuracy|rate|gap|gain|credit|active days/i.test(label)) return;
      const raw = node.textContent.trim();
      if (node.classList.contains("compact-count") && /^[+-]?\d+(?:\.\d+)?$/.test(raw)) {
        node.removeAttribute("title");
        node.removeAttribute("aria-label");
        node.removeAttribute("tabindex");
        node.classList.remove("compact-count");
      }
      if (!/^[+-]?\d+(?:\.\d+)?$/.test(raw) || Math.abs(Number(raw)) < 1000) return;
      const exact = new Intl.NumberFormat("en-GB", {maximumFractionDigits: 20}).format(Number(raw));
      node.textContent = countText(Number(raw));
      node.title = exact;
      node.setAttribute("aria-label", exact);
      node.setAttribute("tabindex", "0");
      node.classList.add("compact-count");
    });
  }
  if (typeof document !== "undefined" && typeof MutationObserver !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => {
      refreshCounts();
      const main = document.querySelector("#main");
      if (main) {
        const observer = new MutationObserver(refreshCounts);
        observer.observe(main, {subtree: true, childList: true, characterData: true});
        window.addEventListener("pagehide", () => observer.disconnect(), {once: true});
      }
    });
  }
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
  // Shared ranking headers and navigation; feature owners retain data and actions.
  function rankingHeading(title,tone){
    return `<header class="ranking-heading"><h1 class="ranking-title ${tone==='query'?'ranking-title-query':esc(tone)}"><span>${esc(title)}</span></h1></header>`;
  }
  function rankingCategories(type,items,action=''){
    return `<nav class="rank-links" aria-label="Ranking category">${items.map(item=>{
      const colour=entityColour(item.entity),active=item.entity===type,body=esc(item.entity[0].toUpperCase()+item.entity.slice(1));
      return action?`<button type="button" style="--category-color:var(--${colour})" class="${active?'active':''}" data-${esc(action)}="${esc(item.entity)}" aria-pressed="${active}">${body}</button>`:`<a style="--category-color:var(--${colour})" class="${active?'active':''}" ${active?'aria-current="page"':''} href="${esc(item.href)}">${body}</a>`;
    }).join('')}</nav>`;
  }
  function rankingRange(bottom,action){
    return `<div class="ranking-switch pill-nav" aria-label="Ranking range"><button class="pill ${bottom?'':'active'}" data-${action}-view="top" aria-pressed="${!bottom}">Top twenty</button><button class="pill ${bottom?'active':''}" data-${action}-view="bottom" aria-pressed="${bottom}">Bottom twenty</button></div>`;
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
    return rankingCategories(type,categories.map(entity=>({entity,href:query(entity)})))+rankingRange(bottom,action);
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
  // Retry only covers that actually failed. Keep URL identity and layout intact.
  function manageCoverImages(root=document,{delays=[800,2400],setTimer=setTimeout,clearTimer=clearTimeout}={}){
    const doc=root.ownerDocument||root,view=doc.defaultView||window;
    const states=new WeakMap(),pending=new Map();let suspended=false,disposed=false;
    const source=image=>image.getAttribute('src')||'';
    const eligible=image=>image?.tagName==='IMG'&&image.hasAttribute('data-cover');
    function allowed(){return !disposed&&!suspended&&!doc.hidden&&view.navigator.onLine!==false;}
    function forget(image){
      for(const [url,batch] of pending){batch.images.delete(image);if(!batch.images.size){if(batch.timer!=null)clearTimer(batch.timer);pending.delete(url);}}
    }
    function arm(url,batch){
      if(batch.timer!=null||!allowed())return;
      const attempts=Math.max(0,...[...batch.images].map(image=>states.get(image)?.attempts||0));
      batch.timer=setTimer(()=>{
        if(pending.get(url)!==batch)return;
        batch.timer=null;
        if(!allowed())return;
        pending.delete(url);
        for(const image of batch.images){
          const state=states.get(image);
          if(!image.isConnected||!state||source(image)!==state.source||state.url!==url||state.attempts>=delays.length)continue;
          state.attempts++;
          // A failed lazy image must request again even while its placeholder shows.
          image.loading='eager';
          image.removeAttribute('src');image.setAttribute('src',state.source);
        }
      },delays[Math.min(attempts,delays.length-1)]);
    }
    function failed(event){
      const image=event.target;if(disposed||!eligible(image)||!source(image))return;
      image.classList.add('failed');
      const raw=source(image);let url;
      try{url=new URL(raw,doc.baseURI);if(!['http:','https:'].includes(url.protocol))return;}catch{return;}
      let state=states.get(image);
      if(!state||state.source!==raw){forget(image);state={source:raw,url:url.href,attempts:0,loading:image.getAttribute('loading')};states.set(image,state);}
      if(state.attempts>=delays.length||!delays.length)return;
      let batch=pending.get(state.url);
      if(!batch){batch={images:new Set(),timer:null};pending.set(state.url,batch);}
      batch.images.add(image);arm(state.url,batch);
    }
    function loaded(event){
      const image=event.target;if(!eligible(image)||!image.naturalWidth)return;
      image.classList.remove('failed');forget(image);
      const state=states.get(image);
      if(state&&source(image)===state.source){if(state.loading==null)image.removeAttribute('loading');else image.setAttribute('loading',state.loading);}
      states.delete(image);
      // Never change `hidden`: game owners decide when blind identities reveal.
    }
    function scan(){root.querySelectorAll('img[data-cover][src]').forEach(image=>{if(image.complete){if(image.naturalWidth)loaded({target:image});else failed({target:image});}});}
    function resume(){if(disposed)return;for(const [url,batch] of pending)arm(url,batch);}
    function hide(){suspended=true;for(const batch of pending.values()){if(batch.timer!=null)clearTimer(batch.timer);batch.timer=null;}}
    function show(){suspended=false;scan();resume();}
    function dispose(){disposed=true;for(const batch of pending.values())if(batch.timer!=null)clearTimer(batch.timer);pending.clear();root.removeEventListener('error',failed,true);root.removeEventListener('load',loaded,true);doc.removeEventListener('DOMContentLoaded',scan);doc.removeEventListener('visibilitychange',resume);view.removeEventListener('online',resume);view.removeEventListener('pagehide',hide);view.removeEventListener('pageshow',show);}
    root.addEventListener('error',failed,true);root.addEventListener('load',loaded,true);
    doc.addEventListener('DOMContentLoaded',scan);doc.addEventListener('visibilitychange',resume);
    view.addEventListener('online',resume);view.addEventListener('pagehide',hide);view.addEventListener('pageshow',show);
    if(doc.readyState!=='loading')scan();
    return Object.freeze({scan,dispose});
  }
  const coverRecovery=typeof document==='undefined'?null:manageCoverImages();
  return Object.freeze({
    $,
    $$,
    esc,
    searchText,
    identityText,
    ratio,
    impactModel,
    impactText,
    countText,
    sumFields,
    trackPosition,
    manageCoverImages,
    coverRecovery,
    entityTypes,
    entityLabels,
    entityColour,
    shelfHead,
    rankingHeading,
    rankingCategories,
    rankingRange,
    modeRankingControls,
    modeRankingRow,
  });
})();
