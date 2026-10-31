/* Shared entity-profile presentation; audio queues and game state stay in site.js. */
window.ProfileUI = (() => {
  "use strict";
  const { $, $$, esc, ratio, sumFields } = window.SongRankerUI;
  let U, tagObserver;
  const count = (value, label) =>
    `<div><b>${esc(value)}</b><small>${esc(label)}</small></div>`;
  const joined = (fields) =>
    `<div class="mini-stats joined-metrics" data-columns="${fields.length}">${fields.map(([value, label]) => count(value, label)).join("")}</div>`;
  function rate(label, right, total) {
    const shown = (value) => Number(Number(value).toFixed(2));
    const pct = total ? Math.max(0, Math.min(100, (100 * right) / total)) : 0;
    return `<div class="profile-rate"><div class="profile-rate-caption"><span>${esc(label)}</span><strong>${ratio(right, total)}</strong></div><div class="overall-progress" ${total ? `role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"` : 'aria-hidden="true"'}><span style="width:${pct}%"></span></div><small>${total ? `${shown(right)} / ${shown(total)}` : "No results yet"}</small></div>`;
  }
  function panel(tone, title, body, links = "") {
    return `<section id="${tone === "standard" ? "voting-record" : tone === "recognition" || tone === "tournament" ? tone : "profile-" + tone}" class="panel profile-mode-panel dashboard-surface ${tone=== "standard" ? "voting" : tone}" data-profile-panel="${tone}" style="--section-color:var(--${tone=== "standard" ? "voting" : tone});--surface-accent:var(--${tone=== "standard" ? "voting" : tone})"><div class="section-head"><h2 class="${tone=== "standard" ? "voting" : tone}">${title}</h2><div class="profile-stat-links">${links}</div></div>${body}</section>`;
  }
  const link = (tone, path, text) =>
    `<a class="${tone}" href="${path}">${text} ↗</a>`;
  function keyStats(fields) {
    return `<div class="stats profile-key-stats" aria-label="Key statistics">${fields.map(([label, value, tone]) => U.stat(label, value, tone).replace('class="stat ', 'class="stat dashboard-surface ')).join("")}</div>`;
  }
  function queueInfo(queue, index = -1) {
    const song = queue[index];
    return song
      ? `<a class="song" title="${esc(song.title)}" href="${U.urlFor("songs", song)}">${esc(song.title)}</a><small class="profile-preview-position">${index + 1} / ${queue.length}</small>`
      : "";
  }
  function tags(tracks, allTags) {
    const counts = new Map();
    for (const song of new Map(tracks.map((song) => [song.id, song])).values())
      for (const id of new Set(song.tag_ids || []))
        counts.set(id, (counts.get(id) || 0) + 1);
    return allTags
      .filter((tag) => counts.has(tag.id))
      .sort(
        (a, b) =>
          counts.get(b.id) - counts.get(a.id) ||
          a.name.localeCompare(b.name) ||
          a.id - b.id,
      )
      .map(
        (tag) =>
          `<a class="badge tag" href="${U.urlFor("tags", tag)}" title="${esc(tag.name)} · ${counts.get(tag.id)} matching songs"><span class="profile-tag-name"># ${esc(tag.name)}</span><small>${counts.get(tag.id)}</small></a>`,
      )
      .join("");
  }
  function fitTagRows(container) {
    const items = [...container.children];
    items.forEach((item) => (item.hidden = false));
    if (!container.clientWidth) return;
    const positions = items.map((item) => item.offsetTop),
      rows = [...new Set(positions)].sort((a, b) => a - b);
    items.forEach(
      (item, index) => (item.hidden = rows.indexOf(positions[index]) >= 2),
    );
  }
  function fitTags() {
    tagObserver?.disconnect();
    const containers = $$(".profile-tag-list");
    if (typeof ResizeObserver !== "undefined") {
      tagObserver ??= new ResizeObserver((entries) =>
        entries.forEach((entry) => fitTagRows(entry.target)),
      );
      containers.forEach((container) => tagObserver.observe(container));
    }
    containers.forEach(fitTagRows);
  }
  window.addEventListener("resize", () => {
    if (U) fitTags();
  });
  function stats(tracks, type = "songs", identity = null) {
    tracks = [...new Map(tracks.map((s) => [s.id, s])).values()];
    const record = (tone, title, body, links) => panel(tone, title, body +
      ((type === "songs" && tracks.length === 1 || ["artists","albums"].includes(type) && identity) ? `<div class="profile-song-details" data-song-details="${({standard:"voting",recognition:"trivia",tournament:"tournament",guesser:"guesser",shelves:"shelves"})[tone]}" aria-busy="true"><p class="muted">Loading mode details…</p></div>` : ""), links);
    const sums = sumFields(tracks, [
      "attempts",
      "correct",
      "championships",
      "runner_ups",
      "third_places",
      "podiums",
      "tournament_wins",
      "tournament_losses",
      "tournament_points",
      "guess_attempts",
      "guess_correct",
      "shelf_attempts",
      "shelf_album_correct",
      "shelf_order_right",
      "shelf_order_pairs",
      "shelf_points",
      "shelf_available",
    ]);
    const fields = tracks.reduce((n, s) => n + U.available(s), 0),
      votes = U.aggregateVotes(tracks),
      tested = tracks.filter((s) => U.available(s) > 0).length;
    const ranking = (mode, tone) =>
      link(tone, `/mode_rankings/${mode}?entity=${type}`, "Rankings");
    const number = (n) => Number(Number(n || 0).toFixed(2));
    const paired = tracks.filter(
        (s) =>
          s.mode_ratings?.standard.matches > 0 &&
          s.mode_ratings?.blind.matches > 0,
      ),
      cohort = type === "songs" ? tracks : paired;
    const modeCards = ["standard", "blind"]
      .map((mode) => {
        const prefix = mode + "_",
          rated = cohort.some((s) => s.mode_ratings?.[mode].matches > 0);
        const elo = rated
          ? cohort.reduce(
              (n, s) => n + Number(s.mode_ratings?.[mode].elo ?? 1200),
              0,
            ) / cohort.length
          : null;
        const peers = (U.data().songs || []).filter(s => s.mode_ratings?.[mode]?.matches > 0 && Number.isFinite(s.mode_ratings[mode].elo));
        const standing = type === "songs" && tracks.length === 1 && rated && elo !== null
          ? `<p class="profile-detail-note">Rank <b>#${1 + peers.filter(s=>s.mode_ratings[mode].elo > elo).length}</b> of ${peers.length} rated tracks</p>` : "";
        return `<div class="profile-vote-mode profile-inset ${mode}" style="--section-color:var(--${mode})"><h3>${mode === "standard" ? "Non-blind" : "Blind"}</h3>${joined(
          [
            [
              elo === null ? "—" : elo.toFixed(1),
              type === "songs" ? "Mode Elo" : "Shared-track Elo",
            ],
            [
              votes.raw?.[prefix + "matches"] ?? votes[prefix + "matches"],
              "Appearances",
            ],
          ],
        )}${rate("Win rate", votes[prefix + "wins"], votes[prefix + "matches"])}${standing}</div>`;
      })
      .join("");
    const outcomes = `<div class="mini-stats joined-metrics profile-vote-totals" data-columns="3">${count(number(votes.wins), "Win weight").replace("<div>", '<div class="vote-win">')}${count(number(votes.losses), "Loss weight").replace("<div>", '<div class="vote-loss">')}${count(votes.raw?.matches ?? votes.matches, type === "songs" ? "Matches" : "Track appearances")}</div>`;
    const voting = record(
      "standard",
      "Voting Record",
      outcomes +
        rate("Weighted win rate", votes.wins, votes.matches) +
        `<div class="profile-detail-grid profile-vote-grid">${modeCards}</div>`,
      link("voting", "/voting_stats", "Stats") +
        link("voting", "/history", "History"),
    );
    const fieldRows = [
      ["title", "Song"],
      ["artist", "Artist"],
      ["album", "Album"],
    ]
      .map(([key, label]) => {
        const offered = tracks.reduce(
          (n, s) =>
            n +
            Number(
              key === "album"
                ? s.album_attempts || 0
                : (s.new_attempts ?? s.attempts ?? 0),
            ),
          0,
        );
        const correct = tracks.reduce(
          (n, s) => n + Number(s[key + "_correct"] || 0),
          0,
        );
        return `<div class="profile-inset">${rate(label + " fields", correct, offered)}</div>`;
      })
      .join("");
    const recognition = record(
      "recognition",
      "Recognisability",
      joined([
        [sums.attempts, "Rounds"],
        [tested, "Tested tracks"],
        [sums.correct, "Fields correct"],
      ]) +
        rate("Fields correct", sums.correct, fields) +
        `<div class="profile-detail-grid profile-field-grid">${fieldRows}</div>`,
      ranking("trivia", "recognition") +
        link("recognition", "/trivia_stats", "Stats"),
    );
    const db = U.data();
    const localKind=type==='artists'?'artist':type==='albums'?'album':null;
    const localBrackets=identity&&localKind?(db.tournaments||[]).filter(t=>t.scope_type===localKind&&Number(t.scope_id)===Number(identity.id)):[];
    const localMatches=(db.tournament_matches||[]).filter(m=>localBrackets.some(t=>t.id===m.tournament_id&&t.status==='completed')&&m.status==='completed'&&m.winner_id&&m.loser_id);
    const completedLocal=localBrackets.filter(t=>t.status==='completed'),localTitles=new Map();
    for(const t of completedLocal)if(t.champion_id)localTitles.set(t.champion_id,(localTitles.get(t.champion_id)||0)+1);
    const localScores=new Map();
    for(const m of localMatches)for(const sid of [m.winner_id,m.loser_id]){
      const score=localScores.get(sid)||{wins:0,played:0};score.played++;if(sid===m.winner_id)score.wins++;localScores.set(sid,score);
    }
    const localCandidates=(db.songs||[]).filter(s=>localScores.has(s.id)).sort((a,b)=>{
      const x=localScores.get(a.id),y=localScores.get(b.id);
      return (localTitles.get(b.id)||0)-(localTitles.get(a.id)||0)||y.wins/y.played-x.wins/x.played||y.played-x.played||a.title.localeCompare(b.title);
    });
    const localLeader=localCandidates[0],leadingLocal=localLeader?[localLeader.id,localTitles.get(localLeader.id)||0]:null;
    const localHistory=localBrackets.length?`<section id="local-tournaments" class="panel profile-mode-panel dashboard-surface tournament" style="--section-color:var(--tournament);--surface-accent:var(--tournament)"><div class="section-head"><h2 class="tournament">${localKind==='artist'?'Artist':'Album'}-only tournaments</h2><a class="tournament" href="/tournament_local_stats?scope=${localKind}&scope_id=${identity.id}">Stats & comparisons ↗</a></div>${joined([[completedLocal.length,'Completed brackets'],[localMatches.length,'Matches']])}${localLeader?`<div class="profile-inset local-leader"><h3>Leading track</h3><a class="compact-track" href="/song/${localLeader.id}"><span class="compact-copy"><strong class="song" title="${esc(localLeader.title)}">${esc(localLeader.title)}</strong></span><span class="compact-score"><b>${leadingLocal[1]}</b><small>Titles</small></span></a></div>`:''}<a class="tournament" href="/tournament/${localBrackets[0].id}/bracket">Latest bracket ↗</a></section>`:'';
    const tournament = record(
      "tournament",
      "Tournament Record",
      joined([
        [sums.tournament_points.toFixed(2), "Points"],
        [Number(sumFields(tracks,["tournament_appearances"]).tournament_appearances.toFixed(2)), "Entry credit"],
        [Number(sums.podiums.toFixed(2)), "Podium credit"],
      ]) +
        rate(
          "Match wins",
          sums.tournament_wins,
          sums.tournament_wins + sums.tournament_losses,
        ) +
        `<div class="profile-secondary-metrics">${joined([
          [Number(sums.championships.toFixed(2)), "First credit"],
          [Number(sums.runner_ups.toFixed(2)), "Second credit"],
          [Number(sums.third_places.toFixed(2)), "Third credit"],
        ])}</div>`,
      ranking("tournament", "tournament") +
        link("tournament", "/tournament_stats", "Stats"),
    );
    const guesser = record(
      "guesser",
      "Elo Guesser",
      joined([
        [sums.guess_correct, "Correct"],
        [sums.guess_attempts - sums.guess_correct, "Wrong"],
        [sums.guess_attempts, "Track appearances"],
      ]) + rate("Correct picks", sums.guess_correct, sums.guess_attempts),
      ranking("guesser", "guesser") +
        link("guesser", "/elo_guesser_stats", "Stats"),
    );
    const shelves = tracks.some(s => s.shelves_eligible) ? record(
      "shelves",
      "Album Shelves",
      joined([
        [sums.shelf_attempts, "Track appearances"],
        [sums.shelf_album_correct, "Correct placements"],
        [sums.shelf_points.toFixed(2), "Points"],
      ]) +
        rate(
          "Relative track order",
          sums.shelf_order_right,
          sums.shelf_order_pairs,
        ) +
        `<div class="profile-detail-grid profile-field-grid"><div class="profile-inset">${rate("Album placement", sums.shelf_album_correct, sums.shelf_attempts)}</div><div class="profile-inset">${rate("Points earned", sums.shelf_points, sums.shelf_available)}</div></div>`,
      ranking("shelves", "shelves") +
        link("shelves", "/album_shelves_stats", "Stats"),
    ) : "";
    return voting + recognition + tournament + localHistory + guesser + shelves;
  }
  let songRequest = null;
  const detailNumber = value => value == null ? "—" : Number(value).toLocaleString(undefined, {maximumFractionDigits:2});
  function detailDate(value) {
    const date = value?.iso && new Date(value.iso);
    return date && Number.isFinite(date.getTime()) ? `<time datetime="${esc(value.iso)}" title="${esc(date.toLocaleString())}">${esc(date.toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"}))}</time>` : "Date unavailable";
  }
  function detailList(title, rows) {
    return `<details class="profile-song-disclosure"><summary>${esc(title)}</summary><ul class="profile-result-list">${rows.join("") || '<li class="muted">No saved results yet.</li>'}</ul></details>`;
  }
  function detailTrack(track, label = "") {
    if (!track) return `<span class="muted">Track unavailable</span>${label ? `<span>${esc(label)}</span>` : ""}`;
    return `<div class="profile-opponent"><a href="/song/${track.id}" aria-label="${esc(track.title)}">${track.cover_url ? `<img src="${esc(track.cover_url)}" alt="" loading="lazy">` : '<span class="profile-detail-art" aria-hidden="true">♫</span>'}</a><div class="profile-opponent-copy"><a class="song" href="/song/${track.id}" title="${esc(track.title)}">${esc(track.title)}</a><div class="metadata">${(track.artists || []).map(a=>`<a class="artist" href="${U.urlFor("artists",a)}">${esc(a.name)}</a>`).join(", ")}${track.album && track.album.toLowerCase() !== "unknown album" && !/ - single$/i.test(track.album) ? ` · <a class="album" href="${U.urlFor("albums",{id:track.album_id,name:track.album,title:track.album})}">${esc(track.album)}</a>` : ""}</div></div></div>${label ? `<strong>${esc(label)}</strong>` : ""}`;
  }
  function songDetailBodies(data) {
    const {voting:v, trivia:t, tournament:b, guesser:g, shelves:s} = data;
    const collection = data.context && data.context.kind !== "songs";
    const source = row => collection ? `<div class="profile-result-context"><p>Collection track</p>${detailTrack(data.songs[row.song_id])}</div>` : "";
    const metrics = fields => joined(fields.map(([value,label])=>[value == null ? "—" : value,label]));
    const windowRate = (name, window) => `<div class="profile-inset">${rate(`${name} · ${window.rounds} rounds`,window.correct,window.available)}</div>`;
    return {
      voting: metrics(collection ? [[v.events,"Different matches"],[v.internal,"Within-collection matches"],[v.opponents,"External opponents"]] : [[v.opponents,"Different opponents"],[v.best_run,"Best win run"],[v.current_run,"Current win run"]]) +
        rate(collection ? `Last ${v.recent_events} matches · track wins` : "Last 10 matches · raw wins",v.recent_wins,v.recent_matches) +
        `<p class="profile-detail-note">Recorded Elo change <b>${v.net == null ? "—" : (v.net > 0 ? "+" : "") + detailNumber(v.net)}</b> · usable snapshots in ${v.snapshots} / ${v.matches} ${collection ? "track appearances. Internal matches contribute one win and one loss." : "matches."}</p>` +
        `<div class="profile-detail-grid">${v.sources.map(r=>`<div class="profile-inset" style="--section-color:var(--${r.key === "tournament" ? "tournament" : "voting"})">${rate(r.key === "tournament" ? "Tournament first-round · raw wins" : "Ordinary voting · raw wins",r.wins,r.matches)}</div>`).join("")}</div>` +
        detailList(collection ? "Most frequent external opponents" : "Most frequent opponents",v.opponents_list.map(r=>`<li>${detailTrack(data.songs[r.id],`${r.wins}W · ${r.losses}L`)}</li>`)),
      trivia: metrics([[t.rounds,"Saved rounds"],[t.perfect,"Perfect recall rounds"],[t.missed,"Missed all fields"]]) +
        `<div class="profile-detail-grid">${windowRate("Latest",t.latest)}${windowRate("Previous",t.previous)}</div>` +
        `<p class="profile-detail-note">Field accuracy from completed saved rounds; edited lifetime totals above may differ.${t.rounds > t.graded ? ` ${t.rounds-t.graded} saved rounds lack complete grading.` : ""}</p>` +
        detailList("Recall timing & recent rounds",[
          ...t.timing.map(r=>`<li><span>${esc(({title:"Song",artist:"Artist",album:"Album"})[r.key])} · correct-answer time<small>${r.samples} timed answers</small></span><strong>${r.mean == null ? "—" : detailNumber(r.mean)+"s average"}<small>${r.fastest == null ? "No timing saved" : detailNumber(r.fastest)+"s fastest"}</small></strong></li>`),
          ...t.recent.map(r=>`<li><span>${detailDate(r.date)}<small>${Object.entries(r.fields).map(([key,value])=>esc(({title:"Song",artist:"Artist",album:"Album"})[key])+": "+(value==null?"Unavailable":value?"Correct":"Missed")).join(" · ")}</small></span><strong>${r.correct == null ? "Unavailable" : `${r.correct} / ${r.available} fields`}</strong>${source(r)}</li>`)
        ]),
      tournament: metrics(collection ? [[b.completed,"Track entries"],[b.brackets,"Different brackets"],[b.first_exits,"First-round exits"]] : [[b.completed,"Completed appearances"],[b.first_exits,"First-round exits"]]) +
        `<div class="profile-detail-grid">${b.groups.map(r=>`<div class="profile-inset">${rate(r.key === "local" ? "Artist / album match wins" : "Library / tag match wins",r.wins,r.wins+r.losses)}<p class="profile-detail-note">${r.entries} completed ${collection ? "track" : "bracket"} entries</p></div>`).join("")}</div>` +
        `<p class="profile-detail-note">Actual completed results here; competition credit remains in the summary above.</p>` +
        detailList("Recent tournament finishes",b.recent.map(r=>`<li><span><a class="tournament" href="/tournament/${r.id}/bracket">${esc(r.finish)} · ${r.size}-track bracket ↗</a><small><span class="${r.mode}">${r.mode === "blind" ? "Blind" : "Non-blind"}</span> · ${esc(({global:"Library",tag:"Tag",artist:"Artist",album:"Album"})[r.scope] || "Other scope")} · ${detailDate(r.date)}</small></span><strong>${r.wins}W · ${r.losses}L</strong>${source(r)}${r.exit ? `<div class="profile-result-context"><p>${r.finish.startsWith("Out in ") ? "Lost to" : `Lost in ${esc(r.exit.round)} to`}</p>${detailTrack(data.songs[r.exit.opponent_id])}</div>` : ""}</li>`)),
      guesser: metrics(collection ? [[g.selected,"Picked collection track"],[g.external_graded-g.selected,"Picked external track"],[g.internal,"Within-collection pairs"]] : [[g.selected,"Picked this song"],[g.graded-g.selected,"Picked its opponent"],[g.rounds,"Saved comparisons"]]) +
        `<div class="profile-detail-grid">${g.bands.map(r=>`<div class="profile-inset">${rate(r.label,r.correct,r.graded)}</div>`).join("")}</div>` +
        `<p class="profile-detail-note">${collection ? `${g.rounds} unique comparisons. Picked-side counts exclude internal pairs. ` : ""}Difficulty uses the Elo gap saved when the pair was offered.${g.unknown ? ` ${g.unknown} comparisons lack usable grading.` : ""}</p>` +
        detailList("Recent comparisons",g.recent.map(r=>`<li>${detailTrack(data.songs[r.opponent_id],r.correct == null ? "Unavailable" : r.correct ? "Correct" : "Wrong")}<p class="profile-result-context">${detailDate(r.date)} · ${r.internal && collection ? "Within collection · " : ""}${r.selected ? (collection ? "Picked collection track below" : "Picked this song") : "Picked opponent above"} · ${detailNumber(r.gap)} Elo apart</p>${source(r)}</li>`)),
      shelves: metrics([[s.perfect,"Perfect track results"],[s.wrong_album,"Wrong-album placements"],[s.graded,"Graded track results"]]) +
        `<p class="profile-detail-note">${collection ? `${s.sessions} distinct completed rounds. ` : ""}Perfect means all available points for this track; other tracks in the round may still be wrong.${s.unknown ? ` ${s.unknown} saved rounds cannot be graded.` : ""}</p>` +
        detailList("Recent track placements",s.recent.map(r=>`<li><span>${detailDate(r.date)}<small>${r.grade ? (r.grade.album_correct ? "Correct album" : "Wrong album") + ` · ${r.grade.order_right} / ${r.grade.order_pairs} order comparisons` : "Saved round cannot be graded"}</small></span><strong>${r.grade ? `${detailNumber(r.grade.points)} / ${detailNumber(r.grade.available)} pts` : "Unavailable"}</strong>${source(r)}</li>`))
    };
  }
  async function loadProfileDetails(kind, entityId, container = document) {
    songRequest?.abort();
    const request = new AbortController(); songRequest = request;
    const slots = [...container.querySelectorAll("[data-song-details]")];
    if (!slots.length) return;
    slots.forEach(node => { node.setAttribute("aria-busy","true"); node.innerHTML = '<p class="muted">Loading mode details…</p>'; });
    const timeout = setTimeout(()=>request.abort(),15000);
    try {
      const response = await fetch(kind === "songs" ? `/api/song/${entityId}/stats` : `/api/profile/${kind}/${entityId}/stats`,{signal:request.signal,cache:"no-store"});
      if (!response.ok) throw Error("Song details could not load.");
      const data = await response.json();
      if (songRequest !== request || !slots[0].isConnected) return;
      if (request.signal.aborted) throw Error("Song details timed out.");
      if (data.context ? data.context.kind !== kind || data.context.id !== entityId : kind !== "songs" || data.song_id !== entityId) throw Error("Unexpected profile details.");
      const bodies = songDetailBodies(data);
      slots.forEach(node => { node.innerHTML=bodies[node.dataset.songDetails] || ""; });
    } catch (error) {
      if (songRequest !== request || !slots[0].isConnected) return;
      slots.forEach((node,i) => { node.innerHTML=i ? "" : '<p class="muted" role="alert">Additional mode details could not load. Your summary and player are still available.</p><button class="btn" data-song-details-retry>Retry details</button>'; });
      slots[0].querySelector("button").addEventListener("click",()=>loadProfileDetails(kind,entityId,container));
    } finally {
      clearTimeout(timeout);
      if (songRequest === request) slots.forEach(node=>node.removeAttribute("aria-busy"));
    }
  }
  window.addEventListener("pagehide",()=>{songRequest?.abort();songRequest=null;});
  return {
    loadSongDetails: (id,container) => loadProfileDetails("songs",id,container),
    loadProfileDetails,
    bindUI: (ui) => (U = ui),
    keyStats,
    queueInfo,
    tags,
    fitTags,
    fitTagRows,
    stats,
  };
})();
