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
  // Fit the exact value at its designed size first. Abbreviate counts only if
  // they overflow; scores/ratings/rates retain every displayed digit. Refit on
  // resize, disclosure opening, font readiness and asynchronously replaced data.
  const numericSelector = ".stat-value, .joined-metrics > * > b, .joined-metrics dd, .mode-stats-metrics dd, .mode-stats-small-metrics dd, .global-metric > strong, .mode-stats-primary, .mode-stats-result > strong, .overall-value, .profile-rate-caption > strong, .versus-count > b, [data-count]";
  const fittedNumbers = new WeakMap(), numberParents = new Set();
  let numberObserver, numberTimer, measureCanvas;
  function refreshCounts() {
    if (typeof document === "undefined" || !document) return;
    const nodes = [...document.querySelectorAll(numericSelector)];
    const plans = [];
    for (const node of nodes) {
      if (node.children.length) continue;
      const prior = fittedNumbers.get(node), displayed = node.textContent.trim();
      const raw = prior && displayed === prior.rendered ? prior.raw : displayed;
      if (!/^[+#−+\-]?\d[\d,.]*(?:\s*[/–→]\s*[#−+\-]?\d[\d,.]*)*%?$/.test(raw)) continue;
      if (prior && displayed !== prior.rendered) {
        node.removeAttribute("title"); node.removeAttribute("aria-label"); node.removeAttribute("tabindex");
      }
      node.style.removeProperty("font-size");
      node.classList.remove("compact-count");
      plans.push({node, raw});
    }
    for (const {node, raw} of plans) {
      const style = getComputedStyle(node), parent = node.parentElement;
      const parentStyle = getComputedStyle(parent);
      const available = parent.clientWidth - parseFloat(parentStyle.paddingLeft || 0) - parseFloat(parentStyle.paddingRight || 0) - parseFloat(style.paddingLeft || 0) - parseFloat(style.paddingRight || 0);
      if (available <= 0) continue; // Hidden/unlaid-out slots keep exact text.
      measureCanvas ||= document.createElement("canvas");
      const context = measureCanvas.getContext("2d");
      if (!context) continue;
      const baseSize = parseFloat(style.fontSize) || 36;
      context.font = `${style.fontWeight} ${baseSize}px ${style.fontFamily}`;
      const width = text => context.measureText(text).width + (parseFloat(style.letterSpacing) || 0) * text.length;
      const label = parent.querySelector("dt, .stat-label, small, .report-meta, span")?.textContent || "";
      const count = /^[+\-]?\d+(?:\.\d+)?$/.test(raw) && Math.abs(Number(raw)) >= 1000 &&
        !/elo(?! matches)|rating|score|points|mean|average|accuracy|rate|gap|gain|credit|weight|evidence|confidence/i.test(label) &&
        !node.matches(".overall-value, .mode-stats-primary, .mode-stats-result > strong, .profile-rate-caption > strong");
      const compact = count && width(raw) > available + 1;
      const rendered = compact ? countText(Number(raw)) : raw;
      // Keep a readable 18px floor. Exceptional exact values may wrap at separators.
      const size = Math.min(baseSize, Math.max(18, baseSize * available / Math.max(1, width(rendered))));
      if (size < baseSize - .5) node.style.fontSize = `${size}px`;
      if (node.textContent !== rendered) node.textContent = rendered;
      node.classList.toggle("compact-count", compact);
      if (compact) {
        const exact = new Intl.NumberFormat("en-GB", {maximumFractionDigits: 20}).format(Number(raw));
        node.title = exact; node.setAttribute("aria-label", exact); node.setAttribute("tabindex", "0");
      } else if (fittedNumbers.has(node)) {
        node.removeAttribute("title"); node.removeAttribute("aria-label"); node.removeAttribute("tabindex");
      }
      fittedNumbers.set(node, {raw, rendered});
      numberParents.add(parent);
    }
    if (numberObserver) {
      for (const parent of numberParents) {
        if (!parent.isConnected) { numberObserver.unobserve(parent); numberParents.delete(parent); }
        else numberObserver.observe(parent);
      }
    }
  }
  function scheduleNumbers() {
    if (numberTimer) return;
    const run = () => { numberTimer = null; refreshCounts(); };
    numberTimer = true;
    if (window.requestAnimationFrame) numberTimer = window.requestAnimationFrame(run);
    else Promise.resolve().then(run);
  }
  if (typeof document !== "undefined" && typeof MutationObserver !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => {
      if (typeof ResizeObserver !== "undefined") numberObserver = new ResizeObserver(scheduleNumbers);
      refreshCounts();
      const main = document.querySelector("#main");
      if (main) {
        const observer = new MutationObserver(scheduleNumbers);
        observer.observe(main, {subtree: true, childList: true, characterData: true});
        window.addEventListener("resize", scheduleNumbers);
        main.addEventListener("toggle", scheduleNumbers, true);
        document.fonts?.ready.then(scheduleNumbers);
        window.addEventListener("pagehide", () => { observer.disconnect(); numberObserver?.disconnect(); if (window.cancelAnimationFrame) window.cancelAnimationFrame(numberTimer); numberParents.clear(); }, {once: true});
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
  function manageDateInputs(root = document) {
    const doc = root.ownerDocument || root, view = doc.defaultView;
    if (!view.HTMLDialogElement?.prototype.showModal) return null;
    const controls = new Map();
    let source = null, returnTo = null, cursor = null;
    const popup = doc.createElement('dialog');
    popup.className = 'date-picker'; popup.id = 'shared-date-picker';
    popup.setAttribute('aria-label', 'Choose date'); popup.setAttribute('aria-modal', 'true');
    const date = (year, month, day) => { const d = new Date(0); d.setUTCFullYear(year,month,day); d.setUTCHours(0,0,0,0); return d; };
    const iso = d => d.toISOString().slice(0,10);
    function parse(value) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null;
      const [y,m,d] = value.split('-').map(Number), result = date(y,m-1,d);
      return y>0 && iso(result)===value ? result : null;
    }
    function today() {
      const now = new Date();
      return source?.dataset.dateZone==='utc' ? date(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()) : date(now.getFullYear(),now.getMonth(),now.getDate());
    }
    function allowed(d) { return d.getUTCFullYear()>=1 && d.getUTCFullYear()<=9999 && (!parse(source.min) || d>=parse(source.min)) && (!parse(source.max) || d<=parse(source.max)); }
    function clamp(d) { const min=parse(source.min),max=parse(source.max); return min && d<min ? min : max && d>max ? max : d; }
    function close(focus = true) {
      if (popup.open) popup.close();
      const button = returnTo; source = null; returnTo = null;
      for (const control of controls.values()) control.setAttribute('aria-expanded','false');
      if (focus && button?.isConnected) button.focus();
    }
    function position() {
      if (!source) return;
      const rect = source.getBoundingClientRect(), width = Math.max(240,Math.min(360,view.innerWidth-24));
      popup.style.width = width+'px';
      popup.style.left = Math.max(12,Math.min(rect.left,view.innerWidth-width-12))+'px';
      const height = popup.getBoundingClientRect().height;
      const top = rect.bottom+8+height<=view.innerHeight-12 ? rect.bottom+8 : rect.top-height-8;
      popup.style.top = Math.max(12,Math.min(top,view.innerHeight-height-12))+'px';
    }
    function draw(focusDay = false) {
      const year=cursor.getUTCFullYear(),month=cursor.getUTCMonth(),start=date(year,month,1),end=date(year,month+1,0);
      const heading=new Intl.DateTimeFormat(undefined,{month:'long',year:'numeric',timeZone:'UTC'}).format(start);
      const months=Array.from({length:12},(_,m)=>new Intl.DateTimeFormat(undefined,{month:'long',timeZone:'UTC'}).format(date(2000,m,1)));
      const offset=(start.getUTCDay()+6)%7, count=Math.ceil((offset+end.getUTCDate())/7)*7;
      const previous=date(year,month,0),next=date(year,month+1,1);
      let cells='';
      for(let i=0;i<count;i++) {
        if(i%7===0) cells+='<tr>';
        const day=i-offset+1;
        if(day<1 || day>end.getUTCDate()) cells+='<td aria-hidden="true"></td>';
        else {
          const d=date(year,month,day),value=iso(d),label=new Intl.DateTimeFormat(undefined,{dateStyle:'full',timeZone:'UTC'}).format(d);
          cells+=`<td role="gridcell" aria-selected="${source.value===value}"><button type="button" data-date-day="${value}" aria-label="${esc(label)}" ${value===iso(today())?'aria-current="date"':''} tabindex="${value===iso(cursor)?0:-1}" ${allowed(d)?'':'disabled'}>${day}</button></td>`;
        }
        if(i%7===6) cells+='</tr>';
      }
      popup.innerHTML=`<div class="date-picker-head"><h2>Choose date</h2><button type="button" data-date-close aria-label="Close calendar">×</button></div><div class="date-picker-month"><button type="button" data-date-step="-1" aria-label="Previous month" ${previous.getUTCFullYear()<1 || (parse(source.min) && previous<parse(source.min))?'disabled':''}>‹</button><select aria-label="Calendar month" data-date-month>${months.map((name,m)=>`<option value="${m}" ${m===month?'selected':''}>${esc(name)}</option>`).join('')}</select><input type="number" aria-label="Calendar year" data-date-year min="1" max="9999" value="${year}"><button type="button" data-date-step="1" aria-label="Next month" ${next.getUTCFullYear()>9999 || (parse(source.max) && next>parse(source.max))?'disabled':''}>›</button></div><table role="grid" aria-label="${esc(heading)}"><thead><tr>${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day=>`<th scope="col">${day}</th>`).join('')}</tr></thead><tbody>${cells}</tbody></table><div class="date-picker-actions"><button type="button" data-date-today ${allowed(today())?'':'disabled'}>Today</button><button type="button" data-date-clear>Clear</button></div>`;
      position();
      if(focusDay) popup.querySelector(`[data-date-day="${iso(cursor)}"]:not(:disabled)`)?.focus();
    }
    function open(input) {
      if (input.matches(':disabled') || input.readOnly || !input.isConnected) return;
      source=input; returnTo=controls.get(input); cursor=clamp(parse(input.value)||today());
      popup.style.setProperty('--date-accent',view.getComputedStyle(input).getPropertyValue('--date-accent').trim() || 'var(--artist)');
      if(!popup.isConnected) doc.body.append(popup);
      draw();
      if(!popup.open) popup.showModal();
      returnTo.setAttribute('aria-expanded','true');
      draw(true);
    }
    function write(value) {
      const input=source;
      if(value && !allowed(parse(value))) {cursor=clamp(parse(value));draw(true);return;}
      input.value=value;
      input.dispatchEvent(new view.Event('input',{bubbles:true}));
      input.dispatchEvent(new view.Event('change',{bubbles:true}));
      close();
    }
    function moveMonth(delta) {
      const day=cursor.getUTCDate(),first=date(cursor.getUTCFullYear(),cursor.getUTCMonth()+delta,1);
      if(first.getUTCFullYear()<1 || first.getUTCFullYear()>9999) return;
      cursor=clamp(date(first.getUTCFullYear(),first.getUTCMonth(),Math.min(day,date(first.getUTCFullYear(),first.getUTCMonth()+1,0).getUTCDate())));
      draw(true);
    }
    popup.addEventListener('click',event=>{
      const button=event.target.closest('button');
      if(button?.dataset.dateDay) write(button.dataset.dateDay);
      else if(button?.hasAttribute('data-date-clear')) write('');
      else if(button?.hasAttribute('data-date-today')) write(iso(today()));
      else if(button?.hasAttribute('data-date-step')) moveMonth(Number(button.dataset.dateStep));
      else if(button?.hasAttribute('data-date-close')) close();
      else if(event.target===popup) { const r=popup.getBoundingClientRect(); if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) close(); }
    });
    popup.addEventListener('change',event=>{
      if(event.target.matches('[data-date-month],[data-date-year]')) {
        const year=Number(popup.querySelector('[data-date-year]').value),month=Number(popup.querySelector('[data-date-month]').value);
        if(Number.isInteger(year) && year>=1 && year<=9999) cursor=clamp(date(year,month,Math.min(cursor.getUTCDate(),date(year,month+1,0).getUTCDate())));
        draw(true);
      }
    });
    popup.addEventListener('keydown',event=>{
      if(!event.target.matches('[data-date-day]')) return;
      const day=parse(event.target.dataset.dateDay),weekday=(day.getUTCDay()+6)%7;
      const offsets={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7,Home:-weekday,End:6-weekday};
      if(event.key in offsets) {
        event.preventDefault();
        const moved=date(day.getUTCFullYear(),day.getUTCMonth(),day.getUTCDate()+offsets[event.key]);
        if(moved.getUTCFullYear()>=1 && moved.getUTCFullYear()<=9999) {cursor=clamp(moved);draw(true);}
      } else if(event.key==='PageUp' || event.key==='PageDown') {event.preventDefault();moveMonth((event.key==='PageUp'?-1:1)*(event.shiftKey?12:1));}
    });
    popup.addEventListener('cancel',event=>{event.preventDefault();close();});
    function scan(node = root) {
      const inputs=[...(node.matches?.('input[type="date"]')?[node]:[]),...node.querySelectorAll('input[type="date"]')];
      for(const input of inputs) {
        if(controls.has(input)) {controls.get(input).disabled=input.matches(':disabled')||input.readOnly;continue;}
        const wrapper=doc.createElement('span'),button=doc.createElement('button');
        wrapper.className='date-control';button.type='button';button.className='date-open';
        const label=input.getAttribute('aria-label') || input.labels?.[0]?.textContent.trim() || input.name || 'date';
        button.setAttribute('aria-label','Open calendar · '+label);button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls',popup.id);
        button.disabled=input.matches(':disabled')||input.readOnly;
        button.innerHTML='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v5M17 3v5M3 11h18M8 15h2M14 15h2"/></svg>';
        controls.set(input,button);input.classList.add('date-enhanced');input.before(wrapper);wrapper.append(input,button);
      }
    }
    function click(event) {
      const button=event.target.closest('.date-open'),input=button?.parentElement.querySelector('input[type="date"]') || (event.target.matches?.('input.date-enhanced')?event.target:null);
      if(input && controls.has(input)) {event.preventDefault();open(input);}
    }
    function key(event) {
      if(event.target.matches?.('input.date-enhanced') && (event.key===' ' || event.altKey && event.key==='ArrowDown')) {event.preventDefault();open(event.target);}
    }
    const observer=new view.MutationObserver(records=>{
      for(const record of records) {
        if(record.type==='attributes') scan(record.target);
        else for(const node of record.addedNodes) if(node.nodeType===1 && !popup.contains(node)) scan(node);
      }
      for(const [input,button] of controls) if(!input.isConnected) {controls.delete(input);button.parentElement?.remove();if(source===input)close(false);}
      if(source && (source.matches(':disabled') || source.readOnly)) close(false);
    });
    const dismiss=()=>close(false), resize=()=>{if(popup.open)position();}, ready=()=>scan();
    root.addEventListener('click',click);root.addEventListener('keydown',key);
    doc.addEventListener('DOMContentLoaded',ready);
    view.addEventListener('resize',resize);view.addEventListener('pagehide',dismiss);
    observer.observe(root.documentElement || root,{subtree:true,childList:true,attributes:true,attributeFilter:['disabled','readonly']});
    scan();
    return Object.freeze({scan,close,dispose(){close(false);observer.disconnect();root.removeEventListener('click',click);root.removeEventListener('keydown',key);doc.removeEventListener('DOMContentLoaded',ready);view.removeEventListener('resize',resize);view.removeEventListener('pagehide',dismiss);popup.remove();for(const [input,button] of controls){input.classList.remove('date-enhanced');const wrapper=button.parentElement;wrapper.replaceWith(input);}controls.clear();}});
  }
  const dateInputs=typeof document==='undefined'?null:manageDateInputs();
  let fullscreenPending = false;
  function fullscreenShortcut(event) {
    if (event.defaultPrevented || event.repeat || event.isComposing ||
        event.ctrlKey || event.altKey || event.metaKey || event.key?.toLowerCase() !== 'f') return;
    const target = event.target;
    if (target?.isContentEditable || target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"], [role="listbox"], [role="option"], .game-select') ||
        document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return;
    if (fullscreenPending) return;
    const action = document.fullscreenElement
      ? document.exitFullscreen?.bind(document)
      : document.fullscreenEnabled === false ? null : document.documentElement.requestFullscreen?.bind(document.documentElement);
    if (!action) return;
    event.preventDefault();
    fullscreenPending = true;
    try {
      Promise.resolve(action()).catch(() => {}).finally(() => { fullscreenPending = false; });
    } catch {
      fullscreenPending = false;
    }
  }
  if (typeof document !== 'undefined') document.addEventListener('keydown', fullscreenShortcut);
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
    manageDateInputs,
    dateInputs,
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
