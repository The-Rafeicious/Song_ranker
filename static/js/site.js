(async () => {
  const page = document.body.dataset.page;
  // Server-rendered reports and independently loaded modes only need the shared shell.
  const collectionPage =
    [
      "home",
      "search",
      "song",
      "artist",
      "album",
      "tag",
      "standard",
      "guesser",
      "shelves",
      "tournament_play",
      "overall_rankings",
      "global_stats",
    ].includes(page) ||
    page.startsWith("rankings_") ||
    page.startsWith("mode_rankings_");
  let COLLECTION = { songs: [], artists: [], albums: [], tags: [] };
  if (collectionPage) {
    const response = await fetch("/api/collection");
    if (!response.ok) throw new Error("Unable to load collection");
    COLLECTION = await response.json();
  }
  let devCollectionReady = page !== "dev" || !!collectionPage,
    devCollectionRequest = null;
  const { $, $$, esc } = window.SongRankerUI;
  const DB = COLLECTION,
    byId = (rows, id) => rows.find((r) => Number(r.id) === Number(id));
  const normal = window.SongRankerUI.searchText;
  const single = (a) => /\s-\s*single\s*$/i.test(a?.title || "");
  const properAlbum = (a) =>
    !!a?.title?.trim() && !single(a) && normal(a.title) !== "unknown album";
  let songs = [],
    artists = [],
    albums = [],
    tags = [];
  const performanceTotals = [
    "tournament_wins",
    "tournament_losses",
    "tournament_points",
    "championships",
    "runner_ups",
    "tournament_appearances",
    "third_places",
    "fourth_places",
    "podiums",
  ];
  const available = (s) => Number(s.available_points ?? s.attempts * 2);
  function aggregateVotes(tracks) {
    const project = (rows) => {
      const result = Object.fromEntries(
        ["standard_wins", "standard_losses", "blind_wins", "blind_losses"].map(
          (k) => [k, rows.reduce((n, v) => n + Number(v[k] || 0), 0)],
        ),
      );
      result.wins = result.standard_wins + result.blind_wins;
      result.losses = result.standard_losses + result.blind_losses;
      for (const prefix of ["", "standard_", "blind_"]) {
        result[prefix + "matches"] =
          result[prefix + "wins"] + result[prefix + "losses"];
        result[prefix + "win_rate"] = result[prefix + "matches"]
          ? (100 * result[prefix + "wins"]) / result[prefix + "matches"]
          : null;
      }
      return result;
    };
    const rows = tracks.map((s) => s.voting || {}),
      result = project(rows);
    result.ordinary = project(rows.map((v) => v.ordinary || v));
    result.tournament = project(rows.map((v) => v.tournament || {}));
    result.raw = project(rows.map((v) => v.raw || v));
    return result;
  }
  function aggregatePerformance(ss) {
    const attempts = ss.reduce((n, s) => n + Number(s.attempts || 0), 0),
      correct = ss.reduce((n, s) => n + Number(s.correct || 0), 0);
    return {
      voting: aggregateVotes(ss),
      ...window.SongRankerUI.sumFields(ss, performanceTotals),
      recognition_attempts: attempts,
      recognition_correct: correct,
      tested_tracks: ss.filter((s) => s.attempts > 0).length,
      recognition_score: ss.reduce((n, s) => n + available(s), 0)
        ? (100 * correct) / ss.reduce((n, s) => n + available(s), 0)
        : null,
    };
  }
  function rebuild() {
    songs = DB.songs.map((s) => {
      const album = byId(DB.albums, s.album_id),
        aa = s.artist_ids.map((id) => byId(DB.artists, id)).filter(Boolean),
        tt = s.tag_ids.map((id) => byId(DB.tags, id)).filter(Boolean);
      return {
        ...s,
        elo_matches_played:
          s.elo_matches_played ?? s.voting?.matches ?? s.matches_played,
        artist: aa.map((a) => a.name).join(", "),
        album: album?.title || "",
        album_is_single: single(album),
        cover_url: album?.cover_url || "",
        tag_names: tt.map((t) => t.name).join(", "),
        name: s.title,
        score: s.elo_score,
        type: "songs",
      };
    });
    songs.sort(
      (a, b) => b.elo_score - a.elo_score || a.title.localeCompare(b.title),
    );
    const related = {
      artists: DB.artists.map((a) =>
        songs.filter((s) => s.artist_ids.includes(a.id)),
      ),
      albums: DB.albums.map((a) => songs.filter((s) => s.album_id === a.id)),
      tags: DB.tags.map((t) => songs.filter((s) => s.tag_ids.includes(t.id))),
    };
    const models = Object.fromEntries(
      ["artists", "albums", "tags"].map((type) => [
        type,
        window.SongRankerUI.impactModel(
          songs,
          related[type].filter(
            (_ss, i) => type !== "albums" || properAlbum(DB.albums[i]),
          ),
        ),
      ]),
    );
    const stats = (ss, type) => ({
      ...aggregatePerformance(ss),
      song_count: ss.length,
      avg_elo: ss.length
        ? ss.reduce((sum, s) => sum + s.elo_score, 0) / ss.length
        : 0,
      ...models[type].measure(ss),
    });
    artists = DB.artists
      .map((a, index) => {
        const ss = related.artists[index],
          summary = stats(ss, "artists");
        return {
          ...a,
          ...summary,
          title: a.name,
          name: a.name,
          score: summary.impact_score,
          cover_url: a.cover_url || ss[0]?.cover_url || "",
          song_ids: ss.map((s) => s.id),
          type: "artists",
        };
      })
      .sort(
        (a, b) =>
          (b.score ?? -Infinity) - (a.score ?? -Infinity) ||
          a.name.localeCompare(b.name),
      );
    albums = DB.albums
      .map((a, index) => {
        const ss = related.albums[index],
          summary = stats(ss, "albums");
        return {
          ...a,
          ...summary,
          name: a.title,
          score: summary.impact_score,
          artist: [
            ...new Set(ss.flatMap((s) => s.artist.split(", ")).filter(Boolean)),
          ].join(", "),
          song_ids: ss.map((s) => s.id),
          type: "albums",
        };
      })
      .sort(
        (a, b) =>
          (b.score ?? -Infinity) - (a.score ?? -Infinity) ||
          a.title.localeCompare(b.title),
      );
    tags = DB.tags
      .map((t, index) => {
        const ss = related.tags[index],
          summary = stats(ss, "tags");
        return {
          ...t,
          ...summary,
          title: t.name,
          score: summary.impact_score,
          song_ids: ss.map((s) => s.id),
          type: "tags",
        };
      })
      .sort(
        (a, b) =>
          (b.score ?? -Infinity) - (a.score ?? -Infinity) ||
          a.name.localeCompare(b.name),
      );
  }
  rebuild();
  const records = (t) => ({ songs, artists, albums, tags })[t] || [],
    colour = window.SongRankerUI.entityColour;
  const label = (t) => window.SongRankerUI.entityLabels[t];
  function linkedSongs(type, item) {
    return type === "songs"
      ? [item]
      : songs.filter((s) => (item.song_ids || []).includes(s.id));
  }
  function related(query) {
    const q = normal(query);
    if (!q) return { songs, artists, albums, tags };
    const seedSongs = songs.filter((s) =>
      normal([s.title, s.artist, s.album, s.tag_names].join(" ")).includes(q),
    );
    const songIds = new Set(seedSongs.map((s) => s.id));
    return {
      songs: seedSongs,
      artists: artists.filter(
        (a) =>
          normal(a.name).includes(q) ||
          a.song_ids.some((id) => songIds.has(id)),
      ),
      albums: albums.filter(
        (a) =>
          normal(a.title).includes(q) ||
          a.song_ids.some((id) => songIds.has(id)),
      ),
      tags: tags.filter(
        (t) =>
          normal(t.name + " " + (t.description || "")).includes(q) ||
          t.song_ids.some((id) => songIds.has(id)),
      ),
    };
  }
  const urlFor = (type, r) =>
    type === "songs"
      ? `/song/${r.id}`
      : type === "tags"
        ? `/tag/${encodeURIComponent(r.name)}`
        : type === "artists"
          ? `/artist/${encodeURIComponent(r.name)}`
          : `/album/${encodeURIComponent(r.title)}`;
  function artwork(r = {}, type = "songs") {
    if (type === "tags")
      return '<div class="art-wrap tag-cover" aria-hidden="true">#</div>';
    const title = r.name || r.title || "",
      letters = (r.artist || title).slice(0, 2).toUpperCase();
    return `<div class="art-wrap ${type === "artists" ? "circle" : ""}"><div class="art-fallback"><b>${esc(letters)}</b><small>ARTWORK UNAVAILABLE</small></div>${r.cover_url ? `<img src="${esc(r.cover_url)}" alt="" loading="lazy" onerror="this.classList.add('failed')">` : ""}</div>`;
  }
  function tagLinks(s) {
    return s.tag_ids
      .map((id) => byId(tags, id))
      .filter(Boolean)
      .map(
        (t) =>
          `<a class="badge tag" href="${urlFor("tags", t)}"># ${esc(t.name)}</a>`,
      )
      .join("");
  }
  function metadata(s) {
    return (
      s.artist_ids
        .map((id) => byId(artists, id))
        .filter(Boolean)
        .map(
          (a) =>
            `<a class="artist" title="${esc(a.name)}" href="${urlFor("artists", a)}">${esc(a.name)}</a>`,
        )
        .join('<span class="separator muted">,</span>') +
      (s.album && !s.album_is_single
        ? `<span class="separator muted">·</span><a class="album" title="${esc(s.album)}" href="${urlFor("albums", byId(albums, s.album_id))}">${esc(s.album)}</a>`
        : "")
    );
  }
  function stat(labelText, value, kind = "song") {
    return `<div class="stat ${kind}"><span class="stat-label">${labelText}</span><strong class="stat-value">${value}</strong></div>`;
  }
  let toastTimer;
  function toast(message) {
    const node = $("#toast");
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (node.hidden = true), 3200);
  }
  const previewSource = (s) =>
    window.PreviewPlayback?.source(s.id, s.audio_url) || s.audio_url;
  const previewPlay = (audio) =>
    window.PreviewPlayback ? window.PreviewPlayback.play(audio) : audio.play();
  function mediaButton(s, id, anonymous = false, loop = false) {
    return `<button class="cover-button" ${s.audio_url ? "" : "disabled"} data-audio="${id}" aria-pressed="false" aria-label="Play ${anonymous ? "anonymous track" : esc(s.title)}">${anonymous ? '<span class="mystery">♫</span>' : artwork(s)}<span class="play-overlay" aria-hidden="true">▶</span></button><audio id="${id}" data-song-id="${s.id}" src="${esc(previewSource(s))}" preload="none" ${loop ? 'loop data-preview-loop="true"' : ""}></audio>`;
  }
  let volume = window.PreviewPlayback?.getVolume() ?? 0.5;
  function playState(button, playing) {
    button.dataset.playing = String(playing);
    button.setAttribute("aria-pressed", String(playing));
    const overlay = $(".play-overlay", button);
    if (overlay) overlay.textContent = playing ? "Ⅱ" : "▶";
  }
  function attachPlayers() {
    $$("audio").forEach((audio) => {
      window.PreviewPlayback?.bind(audio);
      if (audio.dataset.previewRetired) return;
      if (!window.PreviewPlayback) audio.volume = volume;
      if (audio.dataset.bound) return;
      audio.dataset.bound = "true";
      const buttons = () =>
        $$("[data-audio]").filter((b) => b.dataset.audio === audio.id);
      audio.addEventListener("play", () => {
        audio.dataset.loopRequested = "true";
        buttons().forEach((b) => playState(b, true));
      });
      audio.addEventListener("pause", () => {
        audio.dataset.loopRequested = "false";
        buttons().forEach((b) => playState(b, false));
      });
      audio.addEventListener("ended", () => {
        buttons().forEach((b) => playState(b, false));
        if (
          audio.dataset.previewLoop &&
          audio.dataset.loopRequested === "true" &&
          audio.isConnected &&
          !roundTransition.closed
        )
          restartPreview(audio);
      });
      if (audio.dataset.previewLoop)
        audio.addEventListener("timeupdate", () => {
          const end = Number.isFinite(audio.duration)
            ? Math.min(30, audio.duration)
            : 30;
          if (
            !audio.paused &&
            !audio.dataset.previewRetired &&
            audio.dataset.loopRequested === "true" &&
            audio.currentTime >= Math.max(0, end - 1.5)
          )
            restartPreview(audio);
        });
    });
    window.PreviewPlayback?.syncVolume();
  }
  async function restartPreview(audio) {
    if (
      audio.dataset.loopStarting ||
      audio.dataset.previewRetired ||
      roundTransition.closed
    )
      return;
    audio.dataset.loopStarting = "true";
    let next = audio;
    try {
      if (window.PreviewPlayback && !audio.paused) {
        next = window.PreviewPlayback.replace(audio, audio.getAttribute("src"));
        attachPlayers();
      } else audio.currentTime = 0;
      await previewPlay(next);
      if (!next.isConnected || roundTransition.closed) next.pause();
    } catch (error) {
      next.dataset.loopRequested = "false";
      if (error.name !== "AbortError")
        $$("[data-audio]")
          .filter((b) => b.dataset.audio === next.id)
          .forEach((b) => playState(b, false));
    } finally {
      delete next.dataset.loopStarting;
    }
  }
  const flow = window.RoundFlow,
    later = (fn, ms) => (flow ? flow.after(fn, ms) : setTimeout(fn, ms)),
    cancelLater = (timer) =>
      typeof timer === "function" ? timer() : clearTimeout(timer);
  const RESULT_HOLD_MS = 4500,
    roundTransition = {
      timer: null,
      fadeTimer: null,
      stageTimer: null,
      token: 0,
      closed: false,
    };
  function cancelRoundTransition() {
    cancelLater(roundTransition.timer);
    cancelLater(roundTransition.fadeTimer);
    cancelLater(roundTransition.stageTimer);
    roundTransition.timer = null;
    roundTransition.fadeTimer = null;
    roundTransition.stageTimer = null;
    roundTransition.token++;
  }
  function scheduleRoundTransition(
    audioId,
    proceed,
    hold = flow?.duration("pairResult") || RESULT_HOLD_MS,
  ) {
    cancelRoundTransition();
    if (roundTransition.closed) return;
    const token = roundTransition.token;
    roundTransition.timer = later(() => {
      if (token !== roundTransition.token || roundTransition.closed) return;
      roundTransition.timer = null;
      stopAudio();
      proceed().catch((error) => toast(error.message));
    }, hold);
    const audio = audioId && document.getElementById(audioId);
    if (!audio?.getAttribute("src")) return;
    audio.currentTime = 0;
    audio.volume = volume;
    roundTransition.fadeTimer = later(() => {
      if (token === roundTransition.token && !audio.paused)
        window.PreviewPlayback?.fadeOut(audio);
    }, hold - 1500);
    previewPlay(audio)
      .then(() => {
        if (
          token !== roundTransition.token ||
          !audio.isConnected ||
          roundTransition.closed
        )
          audio.pause();
      })
      .catch(() => {
        if (token === roundTransition.token && audio.isConnected)
          toast("Preview unavailable");
      });
  }
  function matchCover(s, id, anonymous, overlay = "") {
    return `<div class="match-cover">${mediaButton(s, id, anonymous, true)}${overlay}</div>`;
  }
  function roundProgress(
    hold = flow?.duration("pairResult") || RESULT_HOLD_MS,
  ) {
    return `<div class="round-transition"><span role="status">Next match automatically…</span><button type="button" class="btn" ${page === "tournament_play" ? "data-bracket-next" : "data-next"}>Next match →</button><div class="round-countdown" style="--result-wait:${hold}ms" aria-hidden="true"></div></div>`;
  }
  window.addEventListener("pagehide", () => {
    roundTransition.closed = true;
    bracketMapRestore = !!bracketMap;
    cancelRoundTransition();
    stopAudio();
  });
  window.addEventListener("pageshow", (e) => {
    roundTransition.closed = false;
    if (e.persisted) {
      if (page === "tournament_play" && bracketMapRestore) {
        bracketMapRestore = false;
        const id = Number(new URLSearchParams(location.search).get("tournament"));
        if (id) loadBracket(id, false).catch(error => toast(error.message));
        return;
      }
      if (page === "standard" && revealed)
        scheduleRoundTransition(null, nextMatch);
      if (page === "tournament_play" && bracketReveal)
        scheduleBracketReveal(null);
    }
  });
  async function toggleAudio(id) {
    if (podiumPlayback?.queue.some((a) => a.id === id)) {
      await selectPodiumAudio(id);
      return;
    }
    const audio = document.getElementById(id);
    if (!audio || !audio.getAttribute("src")) {
      toast("Preview unavailable");
      return;
    }
    if (!audio.paused) {
      if (window.PreviewPlayback) window.PreviewPlayback.cancel(audio);
      else audio.pause();
      return;
    }
    if (albumPlayer) {
      albumPlayer.playRequested = false;
      albumPlayer.pending = null;
      clearTimeout(albumPlayer.primeTimer);
    }
    try {
      await previewPlay(audio);
    } catch (error) {
      if (error.name !== "AbortError")
        toast(
          error.name === "PreviewBlockedError"
            ? error.message
            : "Preview unavailable",
        );
      $$("[data-audio]")
        .filter((b) => b.dataset.audio === id)
        .forEach((b) => playState(b, false));
    }
  }
  let bracketMap = null, bracketMapRestore = false;
  function stopAudio() {
    bracketMap?.cancel();
    bracketMap = null;
    cancelPodiumPlayback();
    if (window.PreviewPlayback) window.PreviewPlayback.stopAll();
    else $$("audio").forEach((a) => a.pause());
    if (albumPlayer) {
      albumPlayer.playRequested = false;
      albumPlayer.pending = null;
    }
  }
  function volumeClose() {
    if (!$("#volume-panel")) return;
    $("#volume-panel").hidden = true;
    $("#volume-btn").setAttribute("aria-expanded", "false");
  }
  function volumeApply(v) {
    volume = window.PreviewPlayback?.setVolume(v) ?? v;
    if (!window.PreviewPlayback) {
      if ($("#volume-range")) $("#volume-range").value = v;
      if ($("#volume-value"))
        $("#volume-value").textContent = Math.round(v * 100) + "%";
      $$("audio").forEach((a) => (a.volume = v));
    }
  }
  const main = $("#main");
  function pageTone(tone) {
    document.body.dataset.tone = tone;
  }
  pageTone(
    {
      home: "mixed",
      standard: "voting",
      global_stats: "voting",
      voting_stats: "voting",
      history: "voting",
      recognition_stats: "recognition",
      trivia: "recognition",
      tournament_play: "tournament",
      tournament_stats: "tournament",
      tournament_local_stats: "tournament",
      tournament_bracket: "tournament",
      guesser_stats: "guesser",
      shelves_stats: "shelves",
      dev: "mixed",
    }[page] ||
      (["song", "artist", "album", "tag"].includes(page) ? page : "song"),
  );
  const homeShelfHead = window.SongRankerUI.shelfHead;
  const HOME_BANNER_LIMIT = 10;
  function homeRateBar(kind, labelText, correct, total, emptyText, unit) {
    const count = Math.max(0, Number(total) || 0),
      right = Math.min(count, Math.max(0, Number(correct) || 0)),
      rate = count ? (100 * right) / count : null;
    const shown = rate == null ? "—" : Number(rate.toFixed(1)) + "%";
    return `<div class="home-mode-bar" data-home-bar="${kind}" data-correct="${right}" data-available="${count}"><div class="home-bar-caption"><span>${esc(labelText)}</span><strong>${shown}</strong></div><div class="home-percentage-track" ${rate == null ? 'aria-hidden="true"' : `role="progressbar" aria-label="${esc(labelText)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${rate}" aria-valuetext="${shown} · ${right} / ${count} ${esc(unit)}"`}><span style="width:${rate ?? 0}%"></span></div><small class="home-bar-details">${count ? `${right} / ${count} ${esc(unit)}` : esc(emptyText)}</small></div>`;
  }
  function homeRecognitionTotals(tracks) {
    return tracks.reduce(
      (totals, s) => {
        const rounds = Math.max(0, Number(s.new_attempts ?? s.attempts) || 0),
          album = Math.max(0, Number(s.album_attempts) || 0);
        totals.available += 2 * rounds + album;
        for (const [key, eligible] of [
          ["title_correct", rounds],
          ["artist_correct", rounds],
          ["album_correct", album],
        ])
          totals.correct += Math.min(
            eligible,
            Math.max(0, Number(s[key]) || 0),
          );
        return totals;
      },
      { correct: 0, available: 0 },
    );
  }
  function homeTournamentEntries(brackets, entries) {
    let total = 0;
    for (const t of brackets) {
      const size = Number(t.size),
        saved = (entries || []).filter(
          (e) => Number(e.tournament_id) === Number(t.id),
        ).length;
      if (Number.isInteger(size) && size > 0) total += size;
      else if (saved) total += saved;
      else return null;
    }
    return total;
  }
  function homeBracketBar(brackets) {
    const sizes = [32, 16, 8],
      counts = sizes.map(
        (size) => brackets.filter((t) => Number(t.size) === size).length,
      ),
      shown = counts.reduce((n, v) => n + v, 0),
      other = brackets.length - shown;
    const rate = (count) => (shown ? (100 * count) / shown : null),
      percentage = (count) =>
        shown ? Number(rate(count).toFixed(1)) + "%" : "—";
    const description = sizes
      .map(
        (size, i) => `${size}-track: ${counts[i]} (${percentage(counts[i])})`,
      )
      .join(", ");
    return `<div class="home-mode-bar" data-home-bar="tournament" data-brackets="${brackets.length}" data-represented="${shown}"><div class="home-bar-caption"><span>Completed bracket sizes</span></div><div class="home-stacked-bar" role="img" aria-label="${esc(description)}">${sizes.map((size, i) => `<span class="bracket-size-${size}" data-bracket-size="${size}" data-bracket-count="${counts[i]}" style="width:${rate(counts[i]) ?? 0}%" title="${size}-track: ${counts[i]} · ${percentage(counts[i])}" aria-hidden="true"></span>`).join("")}</div><div class="home-bracket-legend">${sizes.map((size, i) => `<div><span><i class="bracket-size-${size}" aria-hidden="true"></i>${size} tracks</span><strong>${counts[i]} · ${percentage(counts[i])}</strong></div>`).join("")}</div>${other ? `<small class="home-bar-details">${shown} / ${brackets.length} completed brackets shown · ${other} other or unavailable sizes</small>` : !shown ? '<small class="home-bar-details">No completed brackets yet</small>' : ""}</div>`;
  }
  function homeRecords(recognized, champions) {
    return `<section class="shelf-section recognition home-records" id="home-recognition">${homeShelfHead("Recognisability", "recognition", "/trivia_stats", "Stats")}<div class="scroller recognition-leaders" id="shelf-recognition" tabindex="0" aria-label="Songs over 90 percent recognised">${recognized.map((r, i) => `<a class="shelf-card recognition" data-home-record="recognition" href="${urlFor("songs", r)}"><span class="shelf-rank">${i + 1}</span><div class="shelf-art">${artwork(r)}</div><div class="shelf-info"><h3 class="song" title="${esc(r.title)}">${esc(r.title)}</h3><p class="artist" title="${esc(r.artist)}">${esc(r.artist)}</p><strong class="recognition">${Number(((100 * r.correct) / available(r)).toFixed(1))}% recognised</strong><small>${r.attempts} rounds · ${r.correct} / ${available(r)} fields</small></div></a>`).join("") || '<a class="empty recognition" href="/trivia">No songs above 90% yet</a>'}</div></section><section class="shelf-section tournament home-records" id="home-champions">${homeShelfHead("Champions", "champions", "/tournament_stats", "Brackets")}<div class="scroller champions-column" id="shelf-champions" tabindex="0" aria-label="Recent tournament champions">${
      champions
        .map((t) => {
          const r = byId(songs, t.champion_id);
          return `<article class="shelf-card tournament" data-home-record="champion"><a class="champion-song" href="${urlFor("songs", r)}"><span class="shelf-rank" aria-hidden="true">🏆</span><div class="shelf-art">${artwork(r)}</div><div class="shelf-info"><h3 class="song" title="${esc(r.title)}">${esc(r.title)}</h3><p class="artist" title="${esc(r.artist)}">${esc(r.artist)}</p><strong class="tournament">${t.size}-track champion</strong></div></a><a class="champion-bracket tournament" href="/tournament?tournament=${t.id}">Podium #${t.id} ↗</a></article>`;
        })
        .join("") ||
      '<a class="empty tournament" href="/tournament">No champions yet</a>'
    }</div></section>`;
  }
  function renderHome() {
    const shelf = (type, title, list, rankPage) =>
      `<section class="shelf-section ${colour(type)}">${homeShelfHead(title, type, rankPage)}<div class="scroller" id="shelf-${type}" tabindex="0" aria-label="${title}">${
        list
          .filter((r) => Number.isFinite(r.score))
          .slice(0, HOME_BANNER_LIMIT)
          .map(
            (r, i) =>
              `<a class="shelf-card ${colour(type)}" href="${urlFor(type, r)}"><span class="shelf-rank">${i + 1}</span><div class="shelf-art">${artwork(r, type)}</div><div class="shelf-info"><h3 class="${colour(type)}" title="${esc(r.name)}">${esc(r.name)}</h3><p>${esc(type === "songs" ? r.artist : type === "artists" ? r.song_count + " songs" : r.artist)}</p><strong class="${type === "songs" ? "standard" : colour(type)}">${type === "songs" ? Math.round(r.score) : window.SongRankerUI.impactText(r.score)} ${type === "songs" ? "Elo" : "impact"}</strong></div></a>`,
          )
          .join("") || '<div class="empty">No records yet</div>'
      }</div></section>`;
    const recognized = [...songs]
      .filter((s) => available(s) > 0 && (100 * s.correct) / available(s) > 90)
      .sort(
        (a, b) =>
          b.correct / available(b) - a.correct / available(a) ||
          b.attempts - a.attempts,
      )
      .slice(0, HOME_BANNER_LIMIT);
    const champions = DB.tournaments
      .filter((t) => t.status === "completed" && !["artist","album"].includes(t.scope_type) && byId(songs, t.champion_id))
      .sort(
        (a, b) =>
          String(b.completed_at || b.created_at || "").localeCompare(
            String(a.completed_at || a.created_at || ""),
          ) || b.id - a.id,
      )
      .slice(0, HOME_BANNER_LIMIT);
    const recognition = homeRecognitionTotals(songs),
      completed = DB.tournaments.filter((t) => t.status === "completed" && !["artist","album"].includes(t.scope_type)),
      entered = homeTournamentEntries(completed, DB.tournament_entries);
    const triviaSummary = `<section class="panel recognition-panel stats-glow glow-recognition" data-home-mode="recognition"><div class="section-head"><h2 class="recognition">Trivia Records</h2><a class="recognition" href="/trivia_stats">Stats ↗</a></div><div class="mini-stats joined-metrics"><div><b class="recognition">${Number(DB.challenge_records?.trivia?.best_score || 0).toFixed(2)}</b><small>Challenge best score</small></div><div><b class="recognition">${Number(DB.challenge_records?.trivia?.best_streak || 0)} 🔥</b><small>Challenge best streak</small></div><div><b class="recognition">${songs.filter((s) => s.attempts > 0).length}</b><small>Tested tracks</small></div></div>${homeRateBar("recognition", "Fields correct", recognition.correct, recognition.available, "No tested fields yet", "fields")}</section>`;
    const tournamentSummary = `<section class="panel tournament-panel stats-glow glow-tournament" data-home-mode="tournament"><div class="section-head"><h2 class="tournament">Tournament Records</h2><a class="tournament" href="/tournament_stats">Stats ↗</a></div><div class="mini-stats joined-metrics"><div><b class="tournament">${completed.length}</b><small>Completed</small></div><div><b class="tournament">${entered ?? "—"}</b><small title="Entry slots in completed brackets; repeat appearances count each time">Tracks entered</small></div><div><b class="tournament">${Number(songs.reduce((n, s) => n + Number(s.podiums || 0), 0).toFixed(2))}</b><small>Podium credit</small></div></div>${homeBracketBar(completed)}</section>`;
    main.innerHTML = `<section class="hero"><h1>Song Ranker</h1></section><section class="mode-section" id="play"><div class="section-head"><h2>Ways to Play</h2></div><div class="modes"><a class="mode-card voting" href="/game"><span class="mode-icon">🔥</span><h2>Standard Vote</h2></a><a class="mode-card recognition" href="/trivia"><span class="mode-icon">🧠</span><h2>Trivia</h2></a><a class="mode-card tournament" href="/tournament"><span class="mode-icon">🏆</span><h2>Tournament</h2></a><a class="mode-card guesser" href="/elo_guesser"><span class="mode-icon">🎯</span><h2>Elo Guesser</h2></a><a class="mode-card shelves" href="/album_shelves"><span class="mode-icon">🗂️</span><h2>Album Shelves</h2></a><a class="mode-card vibe" href="/vibe-map"><span class="mode-icon">📍</span><h2>Vibe Map</h2></a></div></section><div class="stats home-collection-totals" role="group" aria-label="Collection totals">${stat("Songs", songs.length)}${stat("Artists", artists.length, "artist")}${stat("Albums", albums.filter(properAlbum).length, "album")}</div><div class="spotlights home-record-stats" role="group" aria-label="Mode records">${triviaSummary}${tournamentSummary}${window.SpecialModes.homeSummary()}</div>${shelf("songs", "Top Tracks", songs, "/leaderboard")}${shelf("artists", "Top Artists", artists, "/artists")}${shelf("albums", "Top Albums", albums.filter(properAlbum), "/albums")}${homeRecords(recognized, champions)}${window.SpecialModes.homeBanners()}`;
    attachShelves();
  }
  const shelfState = new Map();
  const autoScrollers = new Set(),
    autoScrollStates = new WeakMap();
  function attachAutoScroll(el, vertical = false) {
    let state = autoScrollStates.get(el);
    if (!state) {
      state = { paused: false, timer: null, manualUntil: 0 };
      autoScrollStates.set(el, state);
      if (!vertical) shelfState.set(el.id, state);
      const pause = () => (state.paused = true),
        resume = () => (state.paused = false);
      el.addEventListener("mouseenter", pause);
      el.addEventListener("mouseleave", resume);
      el.addEventListener("focusin", pause);
      el.addEventListener("focusout", (e) => {
        if (!el.contains(e.relatedTarget)) resume();
      });
      el.addEventListener("touchstart", pause, { passive: true });
      el.addEventListener("touchend", resume, { passive: true });
      el.addEventListener("touchcancel", resume, { passive: true });
    }
    if (state.timer || matchMedia("(prefers-reduced-motion: reduce)").matches)
      return;
    state.timer = setInterval(() => {
      if (
        state.paused ||
        state.manualUntil > Date.now() ||
        document.hidden ||
        !el.isConnected
      )
        return;
      const max = vertical
        ? el.scrollHeight - el.clientHeight
        : el.scrollWidth - el.clientWidth;
      if (max <= 1) return;
      const key = vertical ? "scrollTop" : "scrollLeft";
      el[key] = el[key] >= max - 1 ? 0 : Math.min(max, el[key] + 0.8);
    }, 35);
    autoScrollers.add(state);
  }
  function attachShelves() {
    $$(".scroller").forEach((el) => attachAutoScroll(el));
  }
  window.addEventListener("pagehide", () => {
    autoScrollers.forEach((state) => {
      clearInterval(state.timer);
      state.timer = null;
    });
    autoScrollers.clear();
  });
  window.addEventListener("pageshow", (e) => {
    if (e.persisted && page === "home") {
      attachShelves();
    }
  });

  function matchRow(h) {
    const w = byId(songs, h.winner_id),
      l = byId(songs, h.loser_id);
    if (!w || !l) return "";
    const side = (s, position, win) => {
      const before = h[win ? "winner_before" : "loser_before"],
        after = h[win ? "winner_after" : "loser_after"],
        saved = Number.isFinite(after),
        start = Number.isFinite(before);
      const rating = saved
          ? `${start ? Math.round(before) + " → " : ""}${Math.round(after)}`
          : Math.round(s.elo_score),
        delta = saved && start ? after - before : null;
      const cover = `<span class="versus-art versus-art-${position}">${compactArt(s)}</span>`;
      const copy = `<div class="versus-copy versus-copy-${position}" data-outcome="${win ? "winner" : "loser"}"><a class="song versus-title" href="${urlFor("songs", s)}" title="${esc(s.title)}">${esc(s.title)}</a><div class="versus-artists">${(
        s.artist_ids || []
      )
        .map((id) => byId(artists, id))
        .filter(Boolean)
        .map(
          (a) =>
            `<a class="artist" href="${urlFor("artists", a)}" title="${esc(a.name)}">${esc(a.name)}</a>`,
        )
        .join(
          ", ",
        )}</div>${s.album && !s.album_is_single && properAlbum({ title: s.album }) ? `<a class="album versus-album" href="/album/${encodeURIComponent(s.album)}" title="${esc(s.album)}">${esc(s.album)}</a>` : ""}<div class="versus-rating standard"><span class="versus-rating-label">${saved ? "Public Elo" : "Current Elo"}</span><strong>${rating}</strong>${delta === null ? "" : `<span class="versus-delta ${delta < 0 ? "loss" : "song"}">${delta >= 0 ? "+" : ""}${Number(delta.toFixed(2))}</span>`}</div></div>`;
      return position === "right" ? cover + copy : copy + cover;
    };
    const tournament = h.origin === "tournament",
      source = tournament
        ? `<a class="tournament versus-origin" href="/tournament_stats?tournament=${h.tournament_id}#tournament-${h.tournament_id}">Tournament #${h.tournament_id}</a><small class="versus-date">Round 1 · ${h.rating_weight === 0.5 ? "½" : "Full"} Elo</small>`
        : '<small class="versus-date">Voting</small>';
    return `<article class="versus-row history-match dashboard-surface" data-match-mode="${esc(h.mode)}" data-match-origin="${tournament ? "tournament" : "ordinary"}" data-match-id="${h.id}">${side(w, "left", true)}<div class="versus-center"><strong class="versus-label">VS</strong><span class="versus-mode-label">${h.mode === "blind" ? "Blind" : "Non-blind"}</span>${source}<small class="versus-date">${esc(String(h.created_at || "Date unavailable").slice(0, 10))}</small>${h.history_note ? `<small class="versus-date">${esc(h.history_note)}</small>` : ""}</div>${side(l, "right", false)}</article>`;
  }
  let historyFilter = "all",
    historyOrigin = "all",
    songId;
  function songHistory(id) {
    return (DB.elo_history || DB.history).filter(
      (h) => h.winner_id === id || h.loser_id === id,
    );
  }
  function renderSong() {
    document.body.classList.add("profile-page");
    main.classList.remove("narrow");
    const params = new URLSearchParams(location.search);
    songId =
      Number(document.body.dataset.entity) ||
      Number(params.get("id")) ||
      songs[0]?.id;
    const track = byId(songs, songId) || songs[0];
    if (!track) {
      main.innerHTML = '<div class="empty">No songs available</div>';
      return;
    }
    songId = track.id;
    const rank = songs.filter((s) => s.elo_score > track.elo_score).length + 1,
      album = byId(albums, track.album_id);
    main.innerHTML = `<section class="panel song-profile profile-song dashboard-surface"><div class="profile-media">${mediaButton(track, "song-audio", false, true)}</div><div class="profile-copy"><h1 class="profile-page-title" title="${esc(track.title)}">${esc(track.title)}</h1><div class="metadata">${metadata(properAlbum(album) ? track : { ...track, album: "" })}</div><div class="tags">${tagLinks(track)}</div></div></section>${window.ProfileUI.keyStats(
      [
        ["Current Elo", Math.round(track.elo_score), "standard"],
        ["Global rank", "#" + rank, "standard"],
        [
          "Peak Elo",
          Math.round(track.highest_elo || track.elo_score),
          "standard",
        ],
        [
          "Elo matches",
          track.elo_matches_played ??
            track.voting?.matches ??
            track.matches_played,
          "standard",
        ],
      ],
    )}<div class="song-sections">${window.ProfileUI.stats([track])}${window.EloReplay?.panel(songId) || ""}<section class="panel profile-mode-panel dashboard-surface voting" id="history" style="--section-color:var(--voting)"><div class="section-head"><h2 class="voting">Recent Matches</h2><a class="voting" href="/history">History ↗</a></div><div class="profile-history-body"><div class="pill-nav" aria-label="Match filter"><button class="pill" data-history="all">All</button><button class="pill" data-history="blind">Blind</button><button class="pill" data-history="standard">Non-blind</button></div><div class="pill-nav" aria-label="Match source"><button class="pill" data-history-origin="all">All Elo matches</button><button class="pill" data-history-origin="ordinary">Voting</button><button class="pill tournament" data-history-origin="tournament">Tournament first rounds</button></div><div id="song-history"></div></div></section></div>`;
    renderSongHistory();
    window.ProfileUI.loadSongDetails(songId, main);
    window.EloReplay?.mountAll(main);
    attachPlayers();
  }
  function renderSongHistory() {
    const rows = songHistory(songId).filter(
      (h) =>
        (historyFilter === "all" || h.mode === historyFilter) &&
        (historyOrigin === "all" ||
          (h.origin === "tournament") === (historyOrigin === "tournament")),
    );
    $$("[data-history-origin]").forEach((b) => {
      b.classList.toggle("active", b.dataset.historyOrigin === historyOrigin);
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.historyOrigin === historyOrigin),
      );
    });
    $("#song-history").innerHTML =
      rows.slice(0, 10).map(matchRow).join("") ||
      '<div class="empty">No matches</div>';
    $$("[data-history]").forEach((b) => {
      b.classList.toggle("active", b.dataset.history === historyFilter);
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.history === historyFilter),
      );
    });
  }
  let blind = false,
    revealed = false,
    pair = [],
    gameNumber = 0,
    voting = false,
    gameMode = "standard",
    roundToken = null,
    roundRules = 1;
  function gameMetadata(s) {
    const aa =
      s.artist_links ||
      (s.artist_ids || []).map((id) => byId(artists, id)).filter(Boolean);
    const names = aa
      .map((a) => {
        const current = byId(artists, a.id);
        return current
          ? `<a class="artist" title="${esc(a.name)}" href="${urlFor("artists", current)}">${esc(a.name)}</a>`
          : `<span class="artist">${esc(a.name)}</span>`;
      })
      .join('<span class="muted">,</span>');
    const album = byId(albums, s.album_id),
      show = properAlbum({ title: s.album || "" });
    return (
      `<div class="game-artists">${names}</div>` +
      (show
        ? album
          ? `<a class="album" title="${esc(s.album)}" href="${urlFor("albums", album)}">${esc(s.album)}</a>`
          : `<span class="album">${esc(s.album)}</span>`
        : "")
    );
  }

  function gameCard(s, i) {
    const winner = i === gameWinner,
      overlay = revealed
        ? `<div class="score-reveal elo-reveal ${winner ? "score-win" : "score-loss"}" role="status"><small>Elo</small><div class="score-values"><span class="score-before">${Math.round(gameOld[i])}</span><span class="score-arrow" aria-hidden="true">→</span><strong class="elo-score" id="elo-${i}">${Math.round(gameOld[i])}</strong></div><b class="elo-delta ${winner ? "" : "loss"}" id="delta-${i}">${winner ? "↑ +" : "↓ "}${Math.round(gameChanges[i])}</b></div>`
        : "";
    return `<article class="game-card dashboard-surface ${revealed ? (winner ? "winner" : "loser") : ""}">${matchCover(s, "game-audio-" + i, blind && !revealed, overlay)}<h2>${blind && !revealed ? "Track " + "AB"[i] : `<a class="song" title="${esc(s.title)}" href="${urlFor("songs", s)}">${esc(s.title)}</a>`}</h2><div class="game-meta">${blind && !revealed ? "" : gameMetadata(s)}</div><button class="btn primary vote-btn" data-vote="${i}" ${revealed ? "disabled" : ""}>${revealed ? (winner ? "✓ Winner" : "Runner-up") : "Vote for " + "AB"[i]}</button></article>`;
  }
  let gameWinner = 0,
    gameChanges = [0, 0],
    gameOld = [0, 0];
  function holdGameHeight() {
    const previous = main.style.minHeight;
    main.style.minHeight = main.getBoundingClientRect().height + "px";
    return () => {
      const left = window.scrollX,
        top = window.scrollY;
      main.style.minHeight = previous;
      window.scrollTo({ left, top, behavior: "instant" });
    };
  }
  function renderGame() {
    const releaseHeight = holdGameHeight();
    try {
      pageTone("voting");
      document.body.dataset.voteMode=blind ? "blind" : "standard";
      document.body.classList.add("game-page");
      main.innerHTML = `<div class="game-head" style="--mode-color:var(--voting)"><h1>${blind ? "Blind Audition" : "Which track is better?"}</h1><div class="pill-nav" aria-label="Voting mode"><button class="pill ${!blind ? "active" : ""}" data-mode="standard" ${revealed ? "disabled" : ""}>Non-blind</button><button class="pill ${blind ? "active" : ""}" data-mode="blind" ${revealed ? "disabled" : ""}>Blind</button></div></div><div class="matchup">${gameCard(pair[0], 0)}<span class="vs-circle">VS</span>${gameCard(pair[1], 1)}</div>${revealed ? roundProgress() : ""}`;
      $$("[data-mode]").forEach((b) =>
        b.setAttribute(
          "aria-pressed",
          String(b.dataset.mode === (blind ? "blind" : "standard")),
        ),
      );
      attachPlayers();
      window.PreviewPlayback?.preloadPair([
        $("#game-audio-0"),
        $("#game-audio-1"),
      ]);
    } finally {
      releaseHeight();
    }
  }
  function animateScore(el, from, to, decimals = 0, active = () => true) {
    if (!el || !active()) return;
    const show = (value) =>
      (el.textContent = decimals
        ? Number(value).toFixed(decimals)
        : Math.round(value));
    show(from);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      show(to);
      return;
    }
    const start = performance.now(),
      duration = flow?.duration("score") || 1100;
    const tick = (now) => {
      if (!el.isConnected || !active()) return;
      const t = Math.min(1, (now - start) / duration);
      show(from + (to - from) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  async function vote(i) {
    if (revealed || voting || !roundToken) return;
    voting = true;
    $$("[data-vote]").forEach((b) => (b.disabled = true));
    cancelRoundTransition();
    let result;
    try {
      result = await api("/api/vote", {
        token: roundToken,
        rules_version: roundRules,
        winner_id: pair[i].id,
        loser_id: pair[1 - i].id,
        mode: blind ? "blind" : "standard",
      });
    } catch (error) {
      if (error.details?.saved_result?.token === roundToken) {
        result = error.details.saved_result;
        toast("Showing the result already saved for this round");
      } else {
        toast(error.message);
        $$("[data-vote]").forEach((b) => (b.disabled = false));
        return;
      }
    } finally {
      voting = false;
    }
    if (result.winner.id != null) {
      i = pair.findIndex((s) => s.id === result.winner.id);
      if (i < 0) {
        toast("Saved result does not match this round. Reload the page.");
        return;
      }
    }
    gameWinner = i;
    gameOld = pair.map((s, j) =>
      j === i ? result.winner.elo_before : result.loser.elo_before,
    );
    gameChanges = pair.map(
      (s, j) =>
        Number((j === i ? result.winner : result.loser).elo_score) - gameOld[j],
    );
    pair = pair.map((s, j) => ({
      ...s,
      elo_score: (j === i ? result.winner : result.loser).elo_score,
    }));
    revealed = true;
    window.PreviewPlayback?.hold();
    renderGame();
    pair.forEach((s, j) =>
      animateScore($("#elo-" + j), gameOld[j], s.elo_score),
    );
    scheduleRoundTransition("game-audio-" + i, nextMatch);
    const mode = blind ? "blind" : "standard";
    flow?.prepare("vote:" + mode, (signal) =>
      api("/api/matchup?mode=" + mode, undefined, undefined, { signal }),
    );
  }
  let matchLoading = false;
  async function nextMatch() {
    if (voting || matchLoading || roundTransition.closed) return;
    const releaseHeight = holdGameHeight(),
      mode = blind ? "blind" : "standard";
    matchLoading = true;
    cancelRoundTransition();
    stopAudio();
    const oldPair = $$("audio[data-preview-pair]");
    window.PreviewPlayback?.forgetPair(oldPair)?.catch(() => {});
    main.setAttribute("aria-busy", "true");
    $$("[data-vote],[data-mode],[data-next]").forEach(
      (b) => (b.disabled = true),
    );
    if (!pair.length)
      main.innerHTML = '<div class="empty" role="status">Loading match…</div>';
    else if ($("[data-next]"))
      $("[data-next]").textContent = "Loading next match…";
    $("#match-load-error")?.remove();
    try {
      const load = (signal) =>
        api("/api/matchup?mode=" + mode, undefined, undefined, { signal });
      const response = await (flow ? flow.take("vote:" + mode, load) : load());
      if (roundTransition.closed || mode !== (blind ? "blind" : "standard"))
        return;
      if (!response.token)
        throw new Error("Reload after installing the complete update");
      roundToken = response.token;
      roundRules = response.rules_version;
      pair = response.songs.map((s) => ({ ...byId(songs, s.id), ...s }));
      revealed = false;
      renderGame();
    } catch (error) {
      if (roundTransition.closed) return;
      const message =
        '<p id="match-load-error" class="error" role="alert">' +
        esc(error.message) +
        "</p>";
      if (pair.length) main.insertAdjacentHTML("beforeend", message);
      else main.innerHTML = message;
      if (!$("[data-next]"))
        main.insertAdjacentHTML(
          "beforeend",
          '<div class="next-area"><button class="btn" data-next>Retry match</button></div>',
        );
      else $("[data-next]").textContent = "Retry match";
    } finally {
      matchLoading = false;
      main.removeAttribute("aria-busy");
      $$("[data-next]").forEach((b) => (b.disabled = false));
      $$("[data-mode]").forEach((b) => (b.disabled = revealed));
      releaseHeight();
    }
  }

  let rankingView =
    new URLSearchParams(location.search).get("view") === "bottom"
      ? "bottom"
      : "top";
  function rankGlow(index, bottom, kind) {
    const step = Math.max(0, Math.min(19, index)) / 19,
      strength = bottom
        ? 0.025 + 0.095 * Math.pow(step, 1.6)
        : 0.035 + 0.385 * Math.pow(1 - step, 2.4);
    return `--glow-color:var(--${kind});--rank-glow:${(strength * 100).toFixed(2)}%;--rank-wash:${(strength * 27).toFixed(2)}%;--rank-border:${(15 + strength * 95).toFixed(2)}%;--rank-blur:${(12 + strength * 60).toFixed(1)}px`;
  }
  function rankingVotes(r, type) {
    const v = r.voting || {},
      rate = (key) => (v[key] == null ? "—" : Number(v[key]).toFixed(2) + "%"),
      matches = Number(v.matches || 0);
    return `<div class="leader-votes" aria-label="Voting statistics"><span class="standard" title="${type === "songs" ? "Saved standard and blind matches" : "Pooled track appearances; a match within this collection counts both songs"}">${matches} ${type === "songs" ? "matches" : "track matches"} · ${rate("win_rate")} wins</span><span class="standard">Non-blind <b>${Number(v.standard_matches || 0)}</b> · ${rate("standard_win_rate")}</span><span class="blind">Blind <b>${Number(v.blind_matches || 0)}</b> · ${rate("blind_win_rate")}</span></div>`;
  }
  function rankingMetadata(r, type, includeSongCount = true) {
    if (type === "songs")
      return {
        html: metadata(r),
        text: [r.artist, r.album && !r.album_is_single ? r.album : ""]
          .filter(Boolean)
          .join(" · "),
      };
    if (type === "albums") {
      const ids = [
          ...new Set(linkedSongs(type, r).flatMap((s) => s.artist_ids)),
        ],
        aa = ids.map((id) => byId(artists, id)).filter(Boolean);
      const names = aa
        .map(
          (a) =>
            `<a class="artist" title="${esc(a.name)}" href="${urlFor("artists", a)}">${esc(a.name)}</a>`,
        )
        .join('<span class="separator muted">,</span>');
      return {
        html:
          names +
          (includeSongCount
            ? (names ? '<span class="separator muted">·</span>' : "") +
              r.song_count +
              " songs"
            : ""),
        text: [
          aa.map((a) => a.name).join(", "),
          includeSongCount ? r.song_count + " songs" : "",
        ]
          .filter(Boolean)
          .join(" · "),
      };
    }
    const text =
      r.song_count + " songs · " + Math.round(r.avg_elo) + " average Elo";
    return { html: text, text };
  }
  function renderRanking(type) {
    pageTone(colour(type));
    document.body.classList.add("rankings-page", "standard-rankings-page");
    const color = colour(type),
      all = records(type).filter(
        (r) =>
          Number.isFinite(r.score) && (type !== "albums" || properAlbum(r)),
      ),
      isTag = type === "tags",
      bottom = rankingView === "bottom";
    const rows = (bottom ? [...all].reverse() : all).slice(0, 20),
      names = {
        songs: "Tracks",
        artists: "Artists",
        albums: "Albums",
        tags: "Tags",
      };
    document.body.style.setProperty("--rank-color", `var(--${color})`);
    const links = [
      ["songs", "/leaderboard", "Songs"],
      ["artists", "/artists", "Artists"],
      ["albums", "/albums", "Albums"],
      ["tags", "/tags", "Tags"],
    ];
    main.innerHTML = `<div class="page-head"><h1 style="color:var(--${color})">${bottom ? "Bottom" : "Top"} ${names[type]}</h1></div><nav class="rank-links" aria-label="Other rankings">${links.map(([key, path, name]) => `<a class="${type === key ? "active" : ""}" href="${path}${rankingView === "bottom" ? "?view=bottom" : ""}">${name}</a>`).join("")}</nav>${`<div class="ranking-switch pill-nav" aria-label="Ranking range"><button class="pill ${bottom ? "" : "active"}" data-ranking-view="top" aria-pressed="${!bottom}">Top twenty</button><button class="pill ${bottom ? "active" : ""}" data-ranking-view="bottom" aria-pressed="${bottom}">Bottom twenty</button></div>`}<div class="leaderboard">${
      rows
        .map((r, i) => {
          const info = rankingMetadata(r, type);
          return `<article class="leader-row ${!bottom && i < 3 ? "top-three" : ""}" style="${rankGlow(i, bottom, color)}"><span class="leader-rank">${bottom ? all.length - i : ["🥇", "🥈", "🥉"][i] || i + 1}</span><a href="${urlFor(type, r)}" aria-label="${esc(r.name)}">${artwork(r, type)}</a><div><a class="leader-title ${color}" title="${esc(r.name)}" href="${urlFor(type, r)}">${isTag ? "# " : ""}${esc(r.name)}</a><div class="leader-meta" title="${esc(info.text)}">${info.html}</div>${rankingVotes(r, type)}</div><div class="leader-score ${type === "songs" ? "standard" : color}">${type === "songs" ? Math.round(r.score) : window.SongRankerUI.impactText(r.score)}<small>${type === "songs" ? "Elo" : "Impact"}</small></div></article>`;
        })
        .join("") || '<div class="empty">No records</div>'
    }</div>`;
  }

  const devSections = window.DevWorkspace?.sections || [];
  let missingAppleOnly = false;
  let devView =
      window.DevWorkspace?.initial ||
      new URLSearchParams(location.search).get("view") ||
      "overview",
    devQuery = new URLSearchParams(location.search).get("q") || "",
    devTypes = new Set(["songs", "artists", "albums", "tags"]),
    devLimits = { songs: 10, artists: 10, albums: 10, tags: 10 },
    tableQuery = "",
    tableFilters = {},
    tablePage = 0,
    tableSort = "id",
    tableDir = 1;
  let tablePanel = null, tablePageSize = 30;
  const filterOps = {contains:"contains", equals:"is exactly", missing:"is blank", present:"has a value", gte:"at least", lte:"at most"};
  const numericTableFields = new Set(["id","disc_number","track_number","song_count","elo_score","elo_matches_played","matches_played","score","avg_elo"]);
  if (!devSections.some(([key]) => key === devView)) devView = "overview";
  const devStateKey = "songRanker.devTables.v415";
  let tableStateType = null,
    tableStates = {};
  try {
    const saved = JSON.parse(sessionStorage.getItem(devStateKey) || "{}");
    if (saved && typeof saved === "object" && !Array.isArray(saved))
      tableStates = saved;
  } catch {}
  function rememberTable() {
    if (!tableStateType) return;
    tableStates[tableStateType] = {
      query: tableQuery,
      filters: { ...tableFilters },
      page: tablePage,
      sort: tableSort,
      dir: tableDir,
      missing: missingAppleOnly,
      pageSize: tablePageSize,
    };
    try {
      sessionStorage.setItem(devStateKey, JSON.stringify(tableStates));
    } catch {}
  }
  function activateTable(type) {
    if (type === tableStateType) return;
    rememberTable();
    tableStateType = type;
    const saved = tableStates[type] || {},
      keys = new Set(tableColumns[type].map(([key]) => key));
    tableQuery = typeof saved.query === "string" ? saved.query : "";
    tablePanel = null;
    tablePageSize = [15,30,60,100].includes(saved.pageSize) ? saved.pageSize : 30;
    tableFilters = Object.fromEntries(Object.entries(saved.filters || {}).filter(([key,value]) => keys.has(key) && (typeof value === "string" || (value && filterOps[value.op] && typeof value.value === "string"))).map(([key,value]) => [key, typeof value === "string" ? {op:"contains",value} : value]));
    tablePage =
      Number.isInteger(saved.page) && saved.page >= 0 ? saved.page : 0;
    tableSort = keys.has(saved.sort) ? saved.sort : "id";
    tableDir = saved.dir === -1 ? -1 : 1;
    missingAppleOnly = type === "songs" && saved.missing === true;
  }

  let shownDevView = null;
  function navigateDev(next, push = true, after = null) {
    window.DevWorkspace.navigate(
      next,
      () => {
        rememberTable();
        devView = next;
        renderDevView();
        after?.();
      },
      push,
    );
  }
  function renderDev() {
    window.DevWorkspace.bind({
      api,
      title: devTitle,
      root: () => $("#dev-main"),
      navigate: navigateDev,
      toast,
    });
    const address = new URL(window.DevWorkspace.href(devView), location.origin);
    address.hash = location.hash;
    const guide = new URLSearchParams(location.search).get("guide");
    if (guide) address.searchParams.set("guide", guide);
    const q = new URLSearchParams(location.search).get("q");
    if (q) address.searchParams.set("q", q);
    history.replaceState({}, "", address);
    renderDevView();
    if (devCollectionReady) window.DevCatalog?.ensureSources().catch(() => {});
  }
  function devTitle(title, actions = "") {
    const kind =
      colour(devView) ||
      {
        trivia: "recognition",
        tournaments: "tournament",
        history: "standard",
        vibe_records: "vibe",
      }[devView] ||
      "song";
    return `<div class="page-head dev-page-head"><h1 class="${kind}">${title}</h1>${actions ? `<div class="dev-heading-actions">${actions}</div>` : ""}</div>`;
  }
  function devResult(type, r) {
    return `<div class="dev-result">${type === "tags" ? '<span class="tag-art">#</span>' : artwork(r, type)}<div class="result-info"><span class="badge ${colour(type)}">${label(type)} #${r.id}</span><h3>${esc(r.name)}</h3><p>${esc(type === "songs" ? r.artist + " · " + r.album : type === "artists" ? r.song_count + " songs · Avg " + (Number.isFinite(r.avg_elo) ? Math.round(r.avg_elo) : "—") + " Elo" : type === "albums" ? r.artist + " · " + r.song_count + " songs" : r.song_count + " linked songs")}</p></div><div class="result-score ${type === "songs" ? "standard" : colour(type)}">${type === "songs" ? Math.round(r.score) : window.SongRankerUI.impactText(r.score)}<small>${type === "songs" ? "Elo" : "Impact"}</small></div><button class="btn small" data-edit="${type}" data-id="${r.id}">Edit</button></div>`;
  }
  function renderExplorer() {
    const node = $("#dev-main");
    node.innerHTML =
      devTitle("Library Explorer") +
      `<form class="search-form dev-search" id="dev-search"><input id="dev-query" type="search" value="${esc(devQuery)}" aria-label="Search every record" placeholder="Title, artist, album, tag…"><button type="submit" aria-label="Search records">Search</button></form><div class="checkboxes">${["songs", "artists", "albums", "tags"].map((t) => `<label><input type="checkbox" data-dev-type="${t}" ${devTypes.has(t) ? "checked" : ""}>${t[0].toUpperCase() + t.slice(1)}</label>`).join("")}</div><div id="dev-results"></div>`;
    renderDevResults();
  }
  function renderDevResults() {
    const found = related(devQuery);
    $("#dev-results").innerHTML =
      ["songs", "artists", "albums", "tags"]
        .filter((t) => devTypes.has(t))
        .map(
          (t) =>
            `<section style="margin-top:28px"><div class="section-head"><h3 class="${colour(t)}">${t[0].toUpperCase() + t.slice(1)}</h3><small>${found[t].length}</small></div>${
              found[t]
                .slice(0, devLimits[t])
                .map((r) => devResult(t, r))
                .join("") || '<div class="empty">No results</div>'
            }${found[t].length > devLimits[t] ? `<button class="btn small" data-dev-more="${t}">Show more ${t}</button>` : ""}</section>`,
        )
        .join("") || '<div class="empty">Choose a record type</div>';
  }
  const tableColumns = {
    songs: [
      ["id", "ID"],
      ["cover_url", "Cover"],
      ["name", "Title"],
      ["artist", "Artists"],
      ["album", "Album"],
      ["tag_names", "Tags"],
      ["elo_score", "Elo"],
      ["elo_matches_played", "Elo matches"],
      ["matches_played", "Ordinary votes"],
      ["disc_number", "Disc"],
      ["track_number", "Track"],
      ["preview", "Preview"],
      ["release_date", "Song released"],
      ["source_status", "Apple source"],
      ["content_label", "Apple content"],
    ],
    artists: [
      ["id", "ID"],
      ["cover_url", "Cover"],
      ["name", "Artist"],
      ["song_count", "Songs"],
      ["score", "Impact"],
      ["avg_elo", "Avg Elo"],
    ],
    albums: [
      ["id", "ID"],
      ["cover_url", "Cover"],
      ["name", "Album / release"],
      ["release_date", "Released"],
      ["shelves_excluded", "Album Shelves"],
      ["song_count", "Songs"],
      ["score", "Impact"],
      ["avg_elo", "Avg Elo"],
      ["release_type", "Type"],
    ],
    tags: [
      ["id", "ID"],
      ["name", "Tag"],
      ["description", "Info"],
      ["song_count", "Songs"],
      ["score", "Impact"],
      ["avg_elo", "Avg Elo"],
    ],
  };
  const optionalSourceColumns = new Set(["apple_track_id", "apple_track_url"]);
  tableColumns.songs.push(
    ["apple_track_id", "Apple ID"],
    ["apple_track_url", "Apple link"],
  );
  const compactTableColumns = new Set([
    "id",
    "cover_url",
    "song_count",
    "track_number",
    "disc_number",
    "preview",
    "release_date",
    "release_type",
    "elo_score",
    "score",
    "avg_elo",
    "elo_matches_played",
    "matches_played",
  ]);
  const tableDefaults = {
    songs: [
      "id",
      "cover_url",
      "name",
      "artist",
      "album",
      "tag_names",
      "elo_score",
      "source_status",
    ],
    artists: ["id", "cover_url", "name", "song_count", "score", "avg_elo"],
    albums: [
      "id",
      "cover_url",
      "name",
      "release_date",
      "shelves_excluded",
      "song_count",
      "score",
      "release_type",
    ],
    tags: ["id", "name", "description", "song_count", "score"],
  };
  let visibleColumns = {};
  try {
    visibleColumns = JSON.parse(localStorage.getItem("tableColumns") || "{}");
  } catch {}
  function columns(type) {
    const chosen = visibleColumns[type];
    return tableColumns[type].filter(([key]) =>
      Array.isArray(chosen)
        ? chosen.includes(key)
        : tableDefaults[type].includes(key),
    );
  }
  function saveColumns(type, keys) {
    const focusedColumn = document.activeElement?.dataset.visible, defaultsFocused = document.activeElement?.hasAttribute("data-columns-default");
    visibleColumns[type] = [...new Set(["name",...keys])].filter(key=>tableColumns[type].some(([k])=>k===key));
    try {
      localStorage.setItem("tableColumns", JSON.stringify(visibleColumns));
    } catch {}
    renderManage(type);
    if (focusedColumn) $('[data-visible="'+focusedColumn+'"]')?.focus();
    else if (defaultsFocused) $("[data-columns-default]")?.focus();
  }
  function columnChooser(type) {
    const chosen = new Set(columns(type).map(([key]) => key));
    return `<section id="table-columns" class="column-picker table-settings-panel" ${tablePanel === "columns" ? "" : "hidden"}><div class="table-popover-head"><strong>Shown columns</strong><button type="button" class="btn small" data-columns-default>Default columns</button><button type="button" class="btn small" data-table-panel="columns">Done</button></div><div class="table-column-choices">${tableColumns[type].map(([key, name]) => `<label><input type="checkbox" data-visible="${key}" ${chosen.has(key) ? "checked" : ""} ${key === "name" ? "disabled" : ""}><span>${name}</span></label>`).join("")}</div></section>`;
  }
  function fieldMatches(value, rule) {
    if (rule.op === "missing") return value == null || String(value).trim() === "";
    if (rule.op === "present") return value != null && String(value).trim() !== "";
    if (rule.op === "gte" || rule.op === "lte") return value != null && String(value).trim() !== "" && Number.isFinite(Number(value)) && (rule.op === "gte" ? Number(value) >= Number(rule.value) : Number(value) <= Number(rule.value));
    return rule.op === "equals" ? normal(value) === normal(rule.value) : normal(value).includes(normal(rule.value));
  }
  function clipped(value) {
    const text = String(value ?? "—");
    return `<span class="ellipsis" title="${esc(text)}">${esc(text)}</span>`;
  }
  function tableValue(r, k) {
    if (k === "score") return window.SongRankerUI.impactText(r.score);
    if (k === "source_status")
      return window.DevCatalog?.sourceText(r.id) || "Unknown";
    if (k === "content_label")
      return window.DevCatalog?.contentText(r.id) || "Not explicit";
    if (optionalSourceColumns.has(k))
      return (
        window.DevCatalog?.sourceValue(
          r.id,
          k === "apple_track_id" ? "track_id" : "track_url",
        ) || ""
      );
    if (k === "preview") return r.audio_url ? "yes" : "no";
    if (k === "shelves_excluded") return r.shelves_excluded ? "Excluded" : "Included";
    if (k === "release_type") return single(r) ? "Single" : "Album";
    return r[k] ?? "";
  }
  function appleSourceLink(r) {
    const url = tableValue(r, "apple_track_url");
    return /^https:\/\/(?:www\.)?(?:music|itunes)\.apple\.com\//.test(url)
      ? `<a class="song" href="${esc(url)}" title="${esc(url)}" target="_blank" rel="noopener noreferrer">Open Apple ↗</a>`
      : "—";
  }
  function tableRows(type) {
    const terms = normal(tableQuery).split(/\s+/).filter(Boolean);
    return records(type)
      .filter(
        (r) =>
          (type !== "songs" ||
            !missingAppleOnly ||
            window.DevCatalog?.sourceText(r.id) === "Needs link") &&
          terms.every((term) =>
            normal(
              tableColumns[type].map(([k]) => tableValue(r, k)).join(" "),
            ).includes(term),
          ) &&
          Object.entries(tableFilters).every(([k, rule]) => fieldMatches(k === "score" ? r.score : k === "preview" && ["missing","present"].includes(rule.op) ? r.audio_url : tableValue(r, k), rule)),
      )
      .sort((a, b) => {
        const av = tableSort === "score" ? a.score : tableValue(a, tableSort),
          bv = tableSort === "score" ? b.score : tableValue(b, tableSort);
        if (av == null || bv == null)
          return av == null ? (bv == null ? 0 : 1) : -1;
        return (
          (typeof av === "number" && typeof bv === "number"
            ? av - bv
            : String(av).localeCompare(String(bv), undefined, {
                numeric: true,
              })) * tableDir || a.id - b.id
        );
      });
  }
  function tableFiltersMarkup(type) {
    return `<section id="table-filters" class="table-filter-panel table-settings-panel" ${tablePanel === "filters" ? "" : "hidden"}><div class="table-popover-head"><strong>Add or update a filter</strong><button class="btn small" type="button" data-table-panel="filters">Done</button></div><form id="table-filter-form" class="table-filter-form"><label>Field<select id="table-filter-field">${tableColumns[type].filter(([k])=>k !== "apple_track_url").map(([key,name])=>`<option value="${key}" ${key === "name" ? "selected" : ""}>${name}</option>`).join("")}</select></label><label>Match<select id="table-filter-op"></select></label><label>Value<input id="table-filter-value" list="table-filter-values" autocomplete="off" placeholder="Type or choose a value"><datalist id="table-filter-values"></datalist></label><button class="btn primary" type="submit">Apply filter</button><p id="table-filter-error" class="error" role="alert" hidden></p></form>${type === "songs" ? `<label class="table-filter-check"><input id="missing-apple-only" type="checkbox" ${missingAppleOnly ? "checked" : ""}>Needs Apple source link</label>` : ""}</section>`;
  }
  function configureTableFilter() {
    const field = $("#table-filter-field");
    if (!field) return;
    const key = field.value, numeric = numericTableFields.has(key);
    $("#table-filter-op").innerHTML = Object.entries(filterOps).filter(([op])=>numeric || !["gte","lte"].includes(op)).map(([op,label])=>`<option value="${op}">${label}</option>`).join("");
    $("#table-filter-values").innerHTML = [...new Set(records(devView).map(r=>String(tableValue(r,key))).filter(v=>v.trim()))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).slice(0,150).map(value=>`<option value="${esc(value)}"></option>`).join("");
    $("#table-filter-value").value = "";
    $("#table-filter-value").type = key === "release_date" ? "date" : "text";
    $("#table-filter-value").disabled = false;
    $("#table-filter-value").inputMode = numeric ? "decimal" : "text";
  }
  function applyTableFilter() {
    const key = $("#table-filter-field").value, op = $("#table-filter-op").value, value = $("#table-filter-value").value.trim(), error = $("#table-filter-error");
    if (!["missing","present"].includes(op) && (!value || (["gte","lte"].includes(op) && !Number.isFinite(Number(value))))) {
      error.textContent = ["gte","lte"].includes(op) ? "Enter a valid number." : "Enter or choose a value.";error.hidden = false;return;
    }
    tableFilters[key] = {op,value};tablePage = 0;tablePanel = null;
    renderManage(devView);$("[data-table-panel=filters]")?.focus();
  }
  function tablePager() {
    return `<div class="table-page-buttons"><button class="btn small" type="button" data-table-prev aria-label="Previous page">← Previous</button><button class="btn small" type="button" data-table-next aria-label="Next page">Next →</button></div>`;
  }
  function renderManage(type) {
    closeRecordMenu();
    activateTable(type);
    $("#dev-main").innerHTML = devTitle(type === "tags" ? "Tags" : type[0].toUpperCase()+type.slice(1)) +
      `<section class="panel dev-table-panel"><div class="dev-table-toolbar"><form class="search-form" id="manage-search"><input id="manage-query" type="search" aria-label="Search ${type}" placeholder="Search ${type}…" value="${esc(tableQuery)}"><button type="submit">Search</button></form><div class="dev-table-tools"><button class="btn" type="button" data-table-panel="filters" aria-controls="table-filters" aria-expanded="${tablePanel === "filters"}">Filters <span class="table-tool-count" id="table-filter-count"></span></button><button class="btn" type="button" data-table-panel="columns" aria-controls="table-columns" aria-expanded="${tablePanel === "columns"}">Columns <span class="table-tool-count">${columns(type).length}</span></button></div></div>${tableFiltersMarkup(type)}${columnChooser(type)}<div class="table-state-bar"><span id="table-state-label" role="status"></span><button class="btn small" type="button" data-table-clear>Clear filters</button></div><div id="table-filter-chips" class="table-filter-chips"></div><div class="table-view-bar"><label class="table-order-label">Order <select id="table-order" aria-label="Order by">${tableColumns[type].filter(([k])=>!["cover_url","apple_track_url"].includes(k)).map(([key,name])=>`<option value="${key}" ${tableSort === key ? "selected" : ""}>${name}</option>`).join("")}</select></label><button class="btn small" type="button" data-table-direction aria-label="Reverse order">${tableDir === 1 ? "↑" : "↓"}</button><button class="btn small" type="button" data-table-reset-order>Reset order</button><label>Rows <select id="table-page-size">${[15,30,60,100].map(n=>`<option ${tablePageSize === n ? "selected" : ""}>${n}</option>`).join("")}</select></label><label>Page <input id="table-page" type="number" min="1" value="${tablePage+1}" aria-label="Go to page"></label>${tablePager()}</div><div class="table-count" role="status"></div><div class="data-scroll dev-catalog-scroll" tabindex="0" role="region" aria-label="${type} table"><table class="data-table dev-catalog-table"><thead><tr>${columns(type).map(([k,name])=>`<th class="table-col-${k}" scope="col" aria-sort="${tableSort === k ? (tableDir === 1 ? "ascending" : "descending") : "none"}"><button type="button" data-sort="${k}">${name}</button></th>`).join("")}<th class="dev-actions-cell" scope="col">Actions</th></tr></thead><tbody id="manage-rows"></tbody></table></div><div class="dev-pagination"><span class="table-count"></span>${tablePager()}</div></section>`;
    configureTableFilter();renderTableBody(type);
  }
  function recordTools(type, r) {
    return (type === "songs" ? `<button class="btn small" type="button" data-preview-quality="${r.id}">Preview quality</button><button class="btn small" type="button" data-catalog-source="${r.id}">Apple source</button><button class="btn small" type="button" data-catalog-single="${r.id}">Make Single</button>` : type === "albums" ? `<button class="btn small" type="button" data-catalog-album="${r.id}">Inspect tracks</button>` : "") + `<button class="btn small danger" type="button" data-delete="${type}" data-id="${r.id}">Delete</button>`;
  }
  function recordActions(type, r) {
    return `<div class="table-actions"><button class="btn small" type="button" data-edit="${type}" data-id="${r.id}" aria-label="Edit ${esc(r.name)}">Edit</button><button class="btn small" type="button" data-record-more="${type}" data-id="${r.id}" aria-haspopup="menu" aria-expanded="false" aria-label="More actions for ${esc(r.name)}">More ▾</button></div>`;
  }
  let recordMenu = null;
  function closeRecordMenu(focus = false) {
    if (!recordMenu) return;
    const {panel, button} = recordMenu;recordMenu = null;
    panel.remove();button.setAttribute("aria-expanded","false");button.removeAttribute("aria-controls");
    if (focus && button.isConnected) button.focus({preventScroll:true});
  }
  function openRecordMenu(button) {
    if (recordMenu?.button === button) {closeRecordMenu(true);return;}
    closeRecordMenu();
    const type = button.dataset.recordMore, row = byId(records(type), Number(button.dataset.id));
    if (!row) return;
    const panel = document.createElement("div");panel.id="dev-record-menu";panel.className="dev-row-tools";panel.setAttribute("popover","auto");panel.setAttribute("role","menu");panel.setAttribute("aria-label", "Actions for "+row.name);panel.innerHTML=recordTools(type,row);
    panel.querySelectorAll("button").forEach(b=>b.setAttribute("role","menuitem"));
    const anchor = button.getBoundingClientRect(), table = button.closest(".dev-catalog-scroll");
    document.body.append(panel);recordMenu={panel,button,anchor,table,x:scrollX,y:scrollY,tableX:table?.scrollLeft,tableY:table?.scrollTop};button.setAttribute("aria-expanded","true");button.setAttribute("aria-controls",panel.id);
    panel.showPopover?.();
    const box=button.getBoundingClientRect(), width=panel.getBoundingClientRect().width || Math.min(230,innerWidth-16), height=panel.getBoundingClientRect().height || panel.querySelectorAll("button").length*48+20;
    panel.style.left=Math.max(8,Math.min(innerWidth-width-8,box.right-width))+"px";
    panel.style.top=Math.max(8,Math.min(innerHeight-height-8,box.bottom+height+8<=innerHeight ? box.bottom+6 : box.top-height-6))+"px";
    panel.addEventListener("toggle",event=>{if(event.newState==="closed" && recordMenu?.panel===panel)closeRecordMenu();});
    panel.querySelector("button")?.focus({preventScroll:true});
  }
  function renderTableBody(type = devView) {
    closeRecordMenu();
    const all = tableRows(type);
    tablePage = Math.min(
      tablePage,
      Math.max(0, Math.ceil(all.length / tablePageSize) - 1),
    );
    rememberTable();
    const offset = tablePage * tablePageSize,
      rows = all.slice(offset, offset + tablePageSize),
      activeFilters =
        Object.keys(tableFilters).length +
        (tableQuery.trim() ? 1 : 0) +
        (missingAppleOnly ? 1 : 0);
    const stateLabel = $("#table-state-label");
    if (stateLabel)
      stateLabel.textContent = activeFilters
        ? activeFilters + " active filter" + (activeFilters === 1 ? "" : "s")
        : "All records";
    const filterCount = $("#table-filter-count");
    if (filterCount)
      filterCount.textContent =
        Object.keys(tableFilters).length +
          (missingAppleOnly ? 1 : 0) || "";
    $$("[data-sort]").forEach((b) => {
      const active = b.dataset.sort === tableSort;
      b.setAttribute("aria-pressed", String(active));
      b.closest("th").setAttribute(
        "aria-sort",
        active ? (tableDir === 1 ? "ascending" : "descending") : "none",
      );
      b.textContent =
        (tableColumns[type].find(([key]) => key === b.dataset.sort)?.[1] ||
          b.dataset.sort) +
        " " +
        (active ? (tableDir === 1 ? "↑" : "↓") : "↕");
    });
    $("#manage-rows").innerHTML =
      rows
        .map(
          (r) =>
            `<tr>${columns(type)
              .map(
                ([k]) =>
                  `<td class="table-col-${k}">${k === "cover_url" ? artwork(r, type) : k === "name" ? `<a class="${colour(type)} table-record-link" href="${urlFor(type, r)}" title="${esc(r.name)}">${esc(r.name)}</a>` : k === "preview" ? (r.audio_url ? "✓" : "—") : ["elo_score", "score", "avg_elo"].includes(k) ? `<strong class="${k === "score" && type !== "songs" ? colour(type) : "standard"}">${k === "score" ? tableValue(r, k) : tableValue(r, k) === "" ? "—" : Math.round(Number(tableValue(r, k)))}</strong>` : k === "apple_track_url" ? appleSourceLink(r) : clipped(tableValue(r, k) === "" ? "—" : tableValue(r, k))}</td>`,
              )
              .join(
                "",
              )}<td class="dev-actions-cell">${recordActions(type, r)}</td></tr>`,
        )
        .join("") ||
      `<tr><td colspan="${columns(type).length + 1}" class="table-empty">No matching records. Clear filters to see all.</td></tr>`;
    $$(".table-count").forEach(node=>node.textContent =
      all.length +
      " records · " +
      (all.length ? offset + 1 : 0) +
      "–" +
      Math.min(offset + tablePageSize, all.length));
    $$("[data-table-prev]").forEach(b=>b.disabled=tablePage === 0);
    $$("[data-table-next]").forEach(b=>b.disabled=offset + tablePageSize >= all.length);
    $("#table-page").value=tablePage+1;$("#table-page").max=Math.max(1,Math.ceil(all.length/tablePageSize));
    $("#table-order").value=tableSort;
    $("#table-filter-chips").innerHTML=Object.entries(tableFilters).map(([key,rule])=>`<button class="btn small" type="button" data-remove-table-filter="${key}" title="Remove this filter">${esc(tableColumns[type].find(([k])=>k===key)?.[1]||key)} ${esc(filterOps[rule.op])} ${esc(["missing","present"].includes(rule.op)?"":rule.value)} ×</button>`).join("");
  }
  function renderImport() {
    if (!window.DevCatalog) {
      $("#dev-main").innerHTML =
        '<p class="error" role="alert">Developer catalogue script is missing. Restore static/js/dev_catalog.js from the patch.</p>';
      return;
    }
    window.DevCatalog.renderImport();
  }
  async function runAppleSearch() {
    return window.DevCatalog.search();
  }

  function tiles(items) {
    return `<div class="workshop">${items.map(([title, icon]) => `<button class="tool-tile" data-tool="${title}"><span class="tool-icon">${icon}</span>${title}</button>`).join("")}</div>`;
  }
  function renderDevView() {
    closeRecordMenu();
    rememberTable();
    if (shownDevView !== devView) {
      stopAudio();
      shownDevView = devView;
    }
    window.DevVibe?.viewChanged(devView);
    window.DevTags?.viewChanged(devView);
    window.DevSystem?.viewChanged(devView);
    window.DevSelection?.viewChanged(devView);
    window.DevMetadata?.viewChanged(devView);
    window.DevWorkspace?.sync(devView);
    const selected = devSections.find(([key]) => key === devView);
    const node = $("#dev-main");
    if (!devCollectionReady && window.DevWorkspace.needsCollection(devView)) {
      node.innerHTML =
        devTitle(selected?.[2] || "Library") +
        '<section class="panel" role="status">Loading catalogue…</section>';
      if (!devCollectionRequest) {
        devCollectionRequest = refreshData()
          .then(() => {
            devCollectionRequest = null;
            if (window.DevWorkspace.needsCollection(devView)) renderDevView();
            window.DevCatalog?.ensureSources().catch(() => {});
          })
          .catch((error) => {
            devCollectionRequest = null;
            if (window.DevWorkspace.needsCollection(devView))
              node.innerHTML =
                devTitle(
                  devSections.find((row) => row[0] === devView)?.[2] ||
                    "Library",
                ) +
                `<section class="panel"><p class="error" role="alert">${esc(error.message)}</p><button class="btn" data-retry-dev-data>Retry catalogue</button></section>`;
          });
      }
      return;
    }
    if (["overview", "database", "backups", "export"].includes(devView)) {
      if (window.DevSystem) window.DevSystem.render(devView);
      else
        node.innerHTML =
          '<p class="error" role="alert">Developer system tools could not load. Refresh this page.</p>';
      return;
    }
    if (["library", "modes", "tools"].includes(devView)) {
      node.innerHTML = window.DevWorkspace.landing(devView, selected[2]);
      return;
    }
    if (devView === "guides") {
      window.DevWorkspace.guide(
        new URLSearchParams(location.search).get("guide") === "technical"
          ? "technical"
          : "dev",
      );
      return;
    }
    if (devView === "maintenance") {
      node.innerHTML =
        devTitle("Reviewed resets") +
        '<section class="panel"><p>Choose the results to reset. Every action shows its scope and requires confirmation before changing data.</p><div class="dev-destinations">' +
        [...Object.keys(historyResets), "Reset competition"]
          .map(
            (name) =>
              `<button type="button" class="dev-destination" data-tool="${esc(name)}"><strong class="danger">${esc(name)}</strong><span>Review scope and confirm</span></button>`,
          )
          .join("") +
        "</div></section>";
      return;
    }
    if (devView === "reports") {
      node.innerHTML =
        devTitle("Exports") +
        '<section class="panel"><div class="system-actions"><a class="btn" href="/api/dev/database/export">Download full database</a><button class="btn" data-tool="Export snapshot">Generate readable report</button></div><p class="muted">The full export preserves stored values. The text report is a readable catalogue summary.</p></section>';
      return;
    }
    if (devView === "duplicates") {
      const groups = new Map();
      songs.forEach((song) => {
        const key = normal(song.title + " " + song.artist);
        groups.set(key, [...(groups.get(key) || []), song]);
      });
      const duplicates = [...groups.values()].filter((rows) => rows.length > 1);
      node.innerHTML =
        devTitle("Duplicate finder") +
        '<section class="panel"><p>Exact title and artist matches. Review each song before making changes.</p><div class="dev-duplicate-list">' +
        (duplicates.length
          ? duplicates
              .map(
                (rows) =>
                  "<section><h2>" +
                  esc(rows[0].title) +
                  "</h2>" +
                  rows.map((row) => devResult("songs", row)).join("") +
                  "</section>",
              )
              .join("")
          : '<p class="empty">No exact title / artist duplicates</p>') +
        "</div></section>";
      return;
    }
    if (devView === "metadata") {
      window.DevMetadata?.render();
      return;
    }
    if (devView === "explorer") {
      renderExplorer();
      return;
    }
    if (["songs", "artists", "albums", "tags"].includes(devView)) {
      renderManage(devView);
      return;
    }
    if (devView === "import") {
      renderImport();
      return;
    }
    if (devView === "selection_health") {
      window.DevSelection?.render();
      return;
    }
    if (devView === "overall") {
      window.Overall.renderDev();
      return;
    }
    if (devView === "tag_workbench") {
      window.DevTags.render();
      return;
    }
    if (devView === "bulk") {
      renderBulk();
      return;
    }
    if (devView === "vibe_records") {
      window.DevVibe?.render();
      return;
    }
    if (["history", "tournaments"].includes(devView)) {
      window.DevRecords?.render(devView);
      return;
    }
    if (devView === "trivia") {
      node.innerHTML =
        devTitle(
          "Trivia / Elo",
          `<button class="btn small danger" data-tool="Reset trivia history">Reset trivia</button>`,
        ) +
        tiles([
          ["Trivia maintenance", "🎯"],
          ["Manual Elo correction", "↗"],
          ["Review saved votes", "✓"],
        ]);
      return;
    }
    if (["guesser_records", "shelves_records"].includes(devView)) {
      window.SpecialModes.renderDevRecords(
        devView === "shelves_records" ? "shelves" : "guesser",
      );
      return;
    }
    node.innerHTML =
      devTitle("Tool unavailable") +
      '<section class="panel"><p class="error" role="alert">This task has no registered controller. Open Guides or choose another task.</p></section>';
  }
  let editTarget = null,
    toolTarget = null,
    editorGeneration = 0;
  const dialog = $("#editor");
  dialog.addEventListener("close", () => {
    editorGeneration++;
  });
  function openDialog(title, body, submit = "Save") {
    editorGeneration++;
    window.DevCatalog?.releaseDialog();
    stopAudio();
    $("#editor-submit").hidden = false;
    $("#editor-title").textContent = title;
    $("#editor-fields").innerHTML = body;
    if (!$("#editor-error"))
      $("#editor-fields").insertAdjacentHTML(
        "beforeend",
        '<p id="editor-error" class="dialog-error" role="alert" tabindex="-1" hidden></p>',
      );
    $("#editor-submit").textContent = submit;
    $("#editor-submit").disabled = false;
    if (page === "dev") window.DevWorkspace.openEditor(dialog);
    else if (!dialog.open) dialog.showModal();
  }
  function field(key, title, value, type = "text", attrs = "") {
    return `<div class="field"><label for="field-${key}">${title}</label><input id="field-${key}" name="${key}" type="${type}" value="${esc(value)}" ${attrs}></div>`;
  }
  function editRecord(type, id) {
    const r = byId(records(type), id);
    if (!r) return;
    editTarget = { type, id: r.id };
    toolTarget = null;
    const group = (title, body) =>
      `<section class="catalog-edit-section"><h3>${title}</h3><div class="form-grid">${body}</div></section>`;
    let body = "";
    if (type === "songs")
      body =
        group(
          "Identity",
          field("title", "Title", r.title, "text", "required") +
            field("artists", "Artists", r.artist) +
            field("album", "Album / release", r.album) +
            field("disc_number", "Disc number", r.disc_number || 1, "number", 'min="1" step="1" required') +
            field(
              "track_number",
              "Track number",
              r.track_number ?? "",
              "number",
              'min="1" step="1"',
            ) +
            field(
              "release_date",
              "Song release date",
              r.release_date || "",
              "date",
            ),
        ) +
        group(
          "Tags",
          field("tags", "Tags (up to 8)", r.tag_names) + tagPicker("edit"),
        ) +
        group(
          "Media",
          field("cover_url", "Cover URL", r.cover_url) +
            field("audio_url", "Preview URL", r.audio_url),
        );
    if (type === "artists")
      body = group(
        "Artist",
        field("name", "Name", r.name, "text", "required") +
          field("cover_url", "Artwork URL", r.cover_url),
      );
    if (type === "albums")
      body = group(
        "Album",
        field("title", "Title", r.title, "text", "required") +
          field("release_date", "Release date", r.release_date || "", "date") +
          field("cover_url", "Cover URL", r.cover_url) +
          `<label class="checkbox-label"><input type="checkbox" id="field-shelves_excluded" name="shelves_excluded" ${r.shelves_excluded ? "checked" : ""}>Exclude from Album Shelves</label><p class="muted">Keeps this as an album. Skips its name in new Trivia rounds; hides it from Shelves play, profiles and statistics. Saved Shelves rounds containing it are hidden until included again.</p>`,
      );
    if (type === "tags")
      body = group(
        "Tag",
        field("name", "Tag", r.name, "text", "required") +
          `<div class="field tag-info-field"><label for="field-description">Tag info</label><textarea id="field-description" name="description" maxlength="2000" rows="5">${esc(r.description || "")}</textarea></div>`,
      );
    openDialog(
      "Edit " + label(type),
      `<div class="catalog-edit-header"><span class="badge ${colour(type)}">${label(type)} #${r.id}</span><strong title="${esc(r.name)}">${esc(r.name)}</strong></div><div class="catalog-edit-fields">${body}</div>` +
        (type === "songs" && window.DevCatalog
          ? window.DevCatalog.summaryMarkup(id)
          : ""),
    );
    if (type === "songs") {
      renderTagPicker("edit");
      window.DevCatalog?.ensureSources(true).catch(() => {});
    }
  }
  function editorError(message) {
    const node = $("#editor-error");
    if (node) {
      node.textContent = message;
      node.hidden = false;
      node.focus();
    } else toast(message);
  }
  async function finishDevMutation(result, gen, refreshSources = false) {
    let failed = false;
    try {
      await refreshData();
      if (refreshSources) await window.DevCatalog?.ensureSources(true);
    } catch {
      failed = true;
    }
    if (gen === editorGeneration) {
      editTarget = null;
      toolTarget = null;
      dialog.close();
      if (page === "dev" && !failed) renderDevView();
    }
    toast(
      failed
        ? "Saved. Reload to refresh the catalogue."
        : result.message || "Saved",
    );
  }
  async function saveEdit(values) {
    if (
      editTarget.type === "songs" &&
      pickedTagNames(values.tags).length > SONG_TAG_LIMIT
    ) {
      editorError("A song can have at most 8 tags.");
      return;
    }
    const { type, id } = editTarget,
      gen = editorGeneration,
      payload = { ...values, artist: values.artists, genres: values.tags };
    if (type === "albums") payload.shelves_excluded = !!$("#field-shelves_excluded")?.checked;
    try {
      const result = await api(
        `/api/dev/edit_${{ songs: "song", artists: "artist", albums: "album", tags: "genre" }[type]}/${id}`,
        payload,
      );
      await finishDevMutation(result, gen, type === "songs");
    } catch (error) {
      if (gen === editorGeneration) editorError(error.message);
      else toast(error.message);
    }
  }
  async function tool(name) {
    if (window.DevSystem && (await window.DevSystem.handleTool(name))) return;
    editTarget = null;
    toolTarget = { name, requestToken: requestToken() };
    const routes = {
      Trivia: "/trivia",
      Tournament: "/tournament",
      "Global stats": "/global_stats",
      "Tournament archive": "/tournament_stats",
      "Lock database": "/dev/logout",
    };
    if (routes[name]) {
      location.href = routes[name];
      return;
    }
    if (name === "Apple Music") {
      navigateDev("import");
      return;
    }
    if (["Manual Elo correction", "Trivia maintenance"].includes(name)) {
      if (!songs.length) {
        toast("No songs");
        return;
      }
      openDialog(
        name,
        maintenancePicker() +
          (name === "Manual Elo correction"
            ? field(
                "elo",
                "New Elo",
                "",
                "number",
                'required min="0" max="5000"',
              )
            : triviaEditFields() +
              '<button class="btn small danger" type="button" data-clear-trivia disabled>Clear Stats</button>'),
      );
      $("#editor-submit").disabled = true;
      renderMaintenanceMatches();
      $("#maintenance-query").focus();
      return;
    }

    try {
      if (name === "Review saved votes") {
        await preferenceAdmin().review();
        return;
      }
      if (name === "Export snapshot") {
        const result = await api("/api/dev/export", {});
        toast(result.message);
        return;
      }
      if (historyResets[name]) {
        const [scope, phrase] = historyResets[name],
          data = await api("/api/dev/reset-preview");
        const count =
          data.clear[
            {
              vibe: "vibe_songs",
              matches: "votes_and_history",
              trivia: "trivia_rounds",
              tournaments: "tournaments",
              guesser: "elo_guesses",
              shelves: "shelf_rounds",
            }[scope]
          ];
        openDialog(
          name,
          `<div class="health-row"><span>${{ vibe: "Tracks with Vibe selections", matches: "Saved matches", trivia: "Saved trivia rounds", tournaments: "Saved tournaments", guesser: "Saved Elo guesses", shelves: "Saved shelf rounds" }[scope]}</span><strong>${count}</strong></div>` +
            field("confirmation", "Type " + phrase, ""),
          "Reset",
        );
        return;
      }
      if (name === "Reset competition") {
        const data = await api("/api/dev/reset-preview");
        openDialog(
          name,
          `<div class="health-row"><span>Votes / trivia / tournaments / Vibe tracks</span><strong>${data.clear.votes_and_history} / ${data.clear.trivia_rounds} / ${data.clear.tournaments} / ${data.clear.vibe_songs}</strong></div>` +
            field("confirmation", "Type RESET COMPETITION", ""),
          "Reset",
        );
        return;
      }
      if (name === "Database integrity") {
        const data = await api("/api/dev/integrity");
        const metric = (value, label, tone = "song") =>
          `<div><b class="${tone}">${esc(value)}</b><span>${label}</span></div>`;
        openDialog(
          name,
          `<section class="integrity-review"><div class="integrity-metrics">${metric(data.integrity.join(", "), "SQLite", data.integrity.every((v) => v === "ok") ? "song" : "error")}${metric(data.foreign_key_errors.length, "Foreign-key errors", data.foreign_key_errors.length ? "error" : "song")}${metric(data.track_number_conflicts.length, "Track conflicts", data.track_number_conflicts.length ? "error" : "song")}</div>${data.foreign_key_errors.length ? `<section><h3>Foreign-key errors</h3><div class="integrity-issues">${data.foreign_key_errors.map((row) => `<article class="health-row"><span>${esc(row[0])} · row ${esc(row[1] ?? "unknown")}</span><strong>Missing ${esc(row[2])} reference</strong></article>`).join("")}</div></section>` : ""}${data.track_number_conflicts.length ? `<section><h3>Track conflicts</h3><div class="integrity-issues">${data.track_number_conflicts.map((s) => `<article class="health-row track-conflict"><div><strong class="song">${esc(s.title)}</strong><small class="album">${esc(s.album || "No album")} · ${esc(window.SongRankerUI.trackPosition(s, true))}</small><small>${esc(s.issue)}</small></div><button class="btn" type="button" data-edit="songs" data-id="${s.id}">Edit song</button></article>`).join("")}</div></section>` : ""}</section>`,
          "Done",
        );
        $("#editor-submit").hidden = true;
        return;
      }
      if (name === "Duplicate finder") {
        const groups = new Map();
        songs.forEach((s) => {
          const key = normal(s.title + " " + s.artist);
          groups.set(key, (groups.get(key) || []).concat(s));
        });
        const duplicates = [...groups.values()].filter((g) => g.length > 1);
        openDialog(
          name,
          duplicates.length
            ? duplicates
                .map(
                  (g) =>
                    `<div class="health-row"><strong>${esc(g[0].title)}</strong><span>${g.map((s) => "#" + s.id).join(", ")}</span></div>`,
                )
                .join("")
            : '<div class="empty">No exact title / artist duplicates</div>',
          "Done",
        );
        return;
      }
    } catch (error) {
      toast(error.message);
    }
  }
  function deleteRecord(type, id) {
    const r = byId(records(type), id);
    editTarget = null;
    toolTarget = { name: "delete", type, id: Number(id) };
    openDialog(
      "Delete " + label(type),
      `<strong>${esc(r.name)}</strong><p>Remove this ${label(type).toLowerCase()} from the catalogue? Review its linked records before continuing.</p>`,
      "Delete",
    );
  }
  async function deleteLocal(type, id) {
    const gen = editorGeneration;
    try {
      const result = await api(
        `/api/dev/delete_${{ songs: "song", artists: "artist", albums: "album", tags: "genre" }[type]}/${id}`,
        null,
        "DELETE",
      );
      await finishDevMutation(result, gen);
    } catch (error) {
      if (gen === editorGeneration) editorError(error.message);
      else toast(error.message);
    }
  }
  // Dev edits refresh the catalogue; games use saved result payloads and frozen questions.
  async function api(url, data, method, options = {}) {
    const response = await fetch(url, {
      ...options,
      method: method || (data !== undefined ? "POST" : "GET"),
      headers: { "Content-Type": "application/json" },
      body: data != null ? JSON.stringify(data) : undefined,
    });
    let result;
    try {
      result = await response.json();
    } catch {
      throw new Error(
        response.redirected
          ? "Sign in to the dev dashboard"
          : "Request failed (" + response.status + ")",
      );
    }
    if (!response.ok) {
      const error = new Error(
        result.message || result.error || "Request failed",
      );
      error.status = response.status;
      error.details = result;
      throw error;
    }
    return result;
  }
  let catalogueLoad = 0;
  async function refreshData() {
    const id = ++catalogueLoad,
      fresh = await api("/api/collection");
    if (id !== catalogueLoad) return;
    Object.assign(DB, fresh);
    rebuild();
    devCollectionReady = true;
  }
  async function importSong(id) {
    return window.DevCatalog.add(id);
  }
  function requestToken() {
    return Array.from(crypto.getRandomValues(new Uint8Array(24)), (n) =>
      n.toString(16).padStart(2, "0"),
    ).join("");
  }
  let preferenceController;
  function preferenceAdmin() {
    if (!preferenceController)
      preferenceController = window.PreferenceAdmin.create({
        api,
        openDialog,
        field,
        toast,
        requestToken,
        refresh: async () => {
          await refreshData();
          renderDevView();
        },
        hasSong: (id) => !!byId(songs, id),
      });
    return preferenceController;
  }
  async function submitTool(values) {
    if (values.preference_event_id) return preferenceAdmin().save(values);
    const name = toolTarget?.name,
      gen = editorGeneration;
    let result;
    if (name === "Preview quality") {
      result = await api("/api/dev/song-quality/" + toolTarget.id, {
        preview_bad: values.preview_bad === "on",
        preview_note: values.preview_note || "",
      });
    } else if (name === "delete") {
      await deleteLocal(toolTarget.type, toolTarget.id);
      return;
    } else if (name === "Edit podium") {
      result = await api(
        "/api/dev/tournaments/" + toolTarget.id + "/placements",
        values,
      );
    } else if (name === "Delete tournament") {
      result = await api(
        "/api/dev/tournaments/" + toolTarget.id,
        null,
        "DELETE",
      );
    } else if (name === "Manual Elo correction") {
      result = await api("/api/dev/elo-correction", {
        song_id: values.song_id,
        new_elo: values.elo,
        expected_elo: toolTarget.expectedElo,
        request_token: toolTarget.requestToken,
      });
    } else if (name === "Trivia maintenance") {
      result = await api(
        "/api/dev/trivia/" + values.song_id,
        Object.fromEntries(triviaEditNames.map((key) => [key, values[key]])),
      );
    } else if (historyResets[name]) {
      result = await api("/api/dev/reset-history/" + historyResets[name][0], {
        confirmation: values.confirmation,
      });
    } else if (name === "Reset competition") {
      result = await api("/api/dev/reset-database", {
        confirmation: values.confirmation,
      });
    } else {
      dialog.close();
      return;
    }
    await finishDevMutation(result, gen);
  }
  // V3.1 collection profiles share the song page's layout and player controls.
  let profileState = null,
    albumPlayer = null;
  const trackOrder = (a, b) =>
    (a.disc_number || 1) - (b.disc_number || 1) ||
    (a.track_number || Infinity) - (b.track_number || Infinity) || a.id - b.id;
  function compactArt(s, type = "songs") {
    return `<span class="small-art ${type === "artists" ? "circle" : ""}" aria-hidden="true">♫${s.cover_url ? `<img src="${esc(s.cover_url)}" alt="" loading="lazy" onerror="this.hidden=true">` : ""}</span>`;
  }
  function renderProfile() {
    const info = JSON.parse($("#profile-data").textContent),
      type = info.kind,
      item = records(type).find((r) => normal(r.name) === normal(info.name));
    if (!item) throw new Error("Profile unavailable");
    const tracks = linkedSongs(type, item),
      isAlbum = type === "albums",
      isTag = type === "tags",
      queueLabel = isAlbum ? "album" : isTag ? "tag" : "artist",
      kind = colour(type),
      ids = new Set(tracks.map((s) => s.id));
    profileState = {
      type,
      item,
      tracks,
      sort: "rank",
      trackLimit: 30,
      albumLimit: isTag ? 6 : Infinity,
      albums: [],
    };
    const artistIds = [...new Set(tracks.flatMap((s) => s.artist_ids))],
      artistLinks = artistIds
        .map((id) => byId(artists, id))
        .filter(Boolean)
        .map(
          (a) =>
            `<a class="artist" title="${esc(a.name)}" href="${urlFor("artists", a)}">${esc(a.name)}</a>`,
        )
        .join('<span class="separator muted">,</span>');
    const properAlbums = albums.filter(
        (a) => properAlbum(a) && a.song_ids.some((id) => ids.has(id)),
      ),
      rank =
        records(type).filter(
          (r) =>
            Number.isFinite(r.score) &&
            (!isAlbum || properAlbum(r)) &&
            r.score > item.score,
        ).length + 1;
    profileState.albums = properAlbums;
    const queue = [...tracks]
      .filter((s) => s.audio_url)
      .sort(
        isAlbum
          ? trackOrder
          : (a, b) =>
              b.elo_score - a.elo_score || a.title.localeCompare(b.title),
      );
    const highlight = (track, title) =>
      track
        ? `<article class="profile-highlight dashboard-surface" data-highlight="${title === "Track to rediscover" ? "low" : "high"}"><div>${compactArt(track)}</div><div><small>${title}</small><a class="song" href="${urlFor("songs", track)}" title="${esc(track.title)}">${esc(track.title)}</a><b class="standard">${Math.round(track.elo_score)} Elo</b></div></article>`
        : "";
    document.body.classList.add("profile-page");
    main.classList.remove("narrow");
    main.innerHTML = `<section class="panel song-profile profile-${kind} dashboard-surface"><div class="profile-media"><div class="album-cover-player"><button class="cover-button" data-audio="album-audio" data-album-play aria-label="Play ${queueLabel} previews" aria-pressed="false" ${queue.length ? "" : "disabled"}>${artwork(item, type)}<span class="play-overlay" aria-hidden="true">▶</span></button>${queue.length ? `<button class="album-cover-step previous" data-album-step="-1" aria-label="Previous ${queueLabel} preview" title="Previous ${queueLabel} preview">‹</button><button class="album-cover-step next" data-album-step="1" aria-label="Next ${queueLabel} preview" title="Next ${queueLabel} preview">›</button>` : ""}<div class="album-player-info" id="album-player-info" role="status">${window.ProfileUI.queueInfo(queue)}</div></div><audio id="album-audio" preload="none"></audio></div><div class="profile-copy"><h1 class="profile-page-title" title="${esc(item.name)}">${isTag ? "# " : ""}${esc(item.name)}</h1><div class="metadata">${isAlbum ? artistLinks : `${tracks.length} tracks ${isTag ? `<span class="separator muted">·</span> ${artistIds.length} artists ` : ""} <span class="separator muted">·</span> ${properAlbums.length} albums`}</div>${isTag ? `<p class="tag-description">${esc(item.description || "")}</p>` : `<div class="tags profile-tag-list">${window.ProfileUI.tags(tracks, tags)}</div>`}<div class="profile-facts">${isAlbum && item.release_date ? `<span>Released <b>${esc(item.release_date.slice(0, 10))}</b></span>` : ""}<span>Highest track peak <b>${tracks.length ? Math.round(Math.max(...tracks.map((s) => s.highest_elo || s.elo_score))) : "—"} Elo</b></span></div></div></section>${window.ProfileUI.keyStats(
      [
        ["Impact", window.SongRankerUI.impactText(item.impact_score), kind],
        [
          "Global rank",
          !Number.isFinite(item.score) || (isAlbum && !properAlbum(item))
            ? "—"
            : "#" + rank,
          kind,
        ],
        [
          "Average Elo",
          tracks.length ? Math.round(item.avg_elo) : "—",
          "standard",
        ],
        ["Tracks", tracks.length, kind],
      ],
    )}<div class="profile-highlights">${highlight(tracks[0], "Highest-ranked track")}${tracks.length > 1 ? highlight(tracks.at(-1), "Track to rediscover") : ""}</div><div class="song-sections">${window.ProfileUI.stats(tracks, type, item)}${!isAlbum && properAlbums.length ? `<section class="panel profile-mode-panel dashboard-surface album" style="--section-color:var(--album)"><div class="section-head"><h2 class="album">Albums</h2></div><div class="profile-albums" id="profile-albums"></div><div class="profile-list-actions" id="profile-albums-more"></div></section>` : ""}<section class="panel profile-mode-panel dashboard-surface ${kind}" style="--section-color:var(--${kind})"><div class="section-head"><h2 class="${kind}">${isAlbum ? "Album Tracks" : isTag ? "Tagged Tracks" : "Ranked Discography"}</h2>${isAlbum ? '<div class="pill-nav" aria-label="Track order"><button class="pill active" data-profile-sort="rank" aria-pressed="true">Ranked</button><button class="pill" data-profile-sort="track" aria-pressed="false">Track order</button></div>' : ""}</div><div id="profile-tracks"></div><div class="profile-list-actions" id="profile-tracks-more"></div></section></div>`;
    window.ProfileUI.fitTags();
    renderProfileAlbums();
    renderProfileTracks();
    attachPlayers();
    albumPlayer = {
      label: queueLabel,
      queue,
      index: -1,
      advancing: false,
      failed: new Set(),
      finished: false,
      playRequested: false,
      primeTimer: null,
    };
    bindAlbumAudio($("#album-audio"));
  }
  function profileMore(kind, shown, total) {
    const root = $("#profile-" + kind + "-more");
    if (!root) return;
    root.innerHTML =
      shown < total
        ? `<button class="btn" type="button" data-profile-more="${kind}" aria-controls="profile-${kind}">Show more ${kind === "tracks" ? "songs" : "albums"}</button>`
        : "";
  }
  function renderProfileAlbums(append = false) {
    const root = $("#profile-albums");
    if (!root) return;
    const { albums: rows, albumLimit } = profileState,
      start = append ? root.children.length : 0;
    const html = rows
      .slice(start, albumLimit)
      .map(
        (a) =>
          `<article class="profile-album-card album">${artwork(a, "albums")}<a class="album" href="${urlFor("albums", a)}" title="${esc(a.title)}">${esc(a.title)}</a><small>${a.song_count} tracks · ${window.SongRankerUI.impactText(a.score)} impact${a.release_date ? " · " + esc(a.release_date.slice(0, 4)) : ""}</small></article>`,
      )
      .join("");
    if (append) root.insertAdjacentHTML("beforeend", html);
    else root.innerHTML = html;
    profileMore("albums", Math.min(albumLimit, rows.length), rows.length);
  }
  function renderProfileTracks(append = false) {
    const { type, tracks, sort, trackLimit } = profileState,
      rows = sort === "track" ? [...tracks].sort(trackOrder) : tracks;
    const root = $("#profile-tracks"),
      start = append ? root.querySelectorAll(".profile-track-row").length : 0;
    const html = rows
      .slice(start, trackLimit)
      .map(
        (s, i) =>
          `<div class="profile-track-row" data-profile-track="${s.id}"><span class="compact-rank" title="${esc(window.SongRankerUI.trackPosition(s, true))}">${sort === "track" ? window.SongRankerUI.trackPosition(s) : start + i + 1}</span>${compactArt(s)}<div class="compact-copy"><a class="song" title="${esc(s.title)}" href="${urlFor("songs", s)}">${esc(s.title)}</a><div class="metadata">${metadata(properAlbum(byId(albums, s.album_id)) ? s : { ...s, album: "" })}</div></div><div class="compact-score standard"><b>${Math.round(s.elo_score)}</b><small>Elo · ${s.elo_matches_played ?? s.voting?.matches ?? s.matches_played} Elo matches</small></div><button class="btn small" data-audio="track-audio-${s.id}" aria-label="Play ${esc(s.title)}" aria-pressed="false" ${s.audio_url ? "" : "disabled"}><span class="play-overlay">▶</span></button><audio id="track-audio-${s.id}" src="${esc(previewSource(s))}" preload="none"></audio></div>`,
      )
      .join("");
    if (append) root.insertAdjacentHTML("beforeend", html);
    else
      root.innerHTML = html || '<div class="empty">No linked tracks yet</div>';
    profileMore("tracks", Math.min(trackLimit, rows.length), rows.length);
    attachPlayers();
    markAlbumTrack();
  }
  function markAlbumTrack() {
    if (!albumPlayer) return;
    const selected = albumPlayer.queue[albumPlayer.index];
    $$("[data-profile-track]").forEach((row) =>
      row.classList.toggle(
        "is-playing",
        !!selected &&
          Number(row.dataset.profileTrack) === selected.id &&
          !$("#album-audio").paused,
      ),
    );
  }
  function updateAlbumInfo() {
    const { queue, index } = albumPlayer;
    $("#album-player-info").innerHTML = window.ProfileUI.queueInfo(
      queue,
      index,
    );
    markAlbumTrack();
  }
  function bindAlbumAudio(audio) {
    if (audio.dataset.albumBound) return;
    audio.dataset.albumBound = "true";
    const current = () =>
      audio === $("#album-audio") && albumPlayer?.playRequested;
    audio.addEventListener("timeupdate", () => {
      if (
        current() &&
        !audio.paused &&
        audio.currentTime >= 10 &&
        !albumPlayer.advancing
      )
        advanceAlbum(1);
    });
    audio.addEventListener("ended", () => {
      if (current() && !albumPlayer.advancing) advanceAlbum(1);
    });
    audio.addEventListener("error", async () => {
      if (!current() || albumPlayer.advancing) return;
      const state = albumPlayer,
        info = await window.PreviewPlayback?.problem(audio);
      if (state !== albumPlayer) return;
      if (info?.blocked) {
        state.playRequested = false;
        window.PreviewPlayback?.stopAll();
        return;
      }
      state.failed.add(state.index);
      startAlbumAt(state.index + 1, true);
    });
    audio.addEventListener("play", () => {
      if (audio === $("#album-audio"))
        $("[data-album-play]")?.setAttribute(
          "aria-label",
          "Pause " + albumPlayer.label + " previews",
        );
    });
    audio.addEventListener("pause", () => {
      if (audio === $("#album-audio"))
        $("[data-album-play]")?.setAttribute(
          "aria-label",
          "Play " + albumPlayer.label + " previews",
        );
    });
  }
  async function startAlbumAt(index, play = true, direction = 1) {
    if (!albumPlayer) return;
    const state = albumPlayer;
    if (state.advancing) {
      state.pending = { index, play, direction };
      window.PreviewPlayback?.abandon($("#album-audio"));
      return;
    }
    state.advancing = true;
    state.playRequested = play;
    clearTimeout(state.primeTimer);
    try {
      const count = state.queue.length;
      for (let offset = 0; offset < count; offset++) {
        const i = (((index + offset * direction) % count) + count) % count;
        if (state.failed.has(i)) continue;
        let audio = $("#album-audio");
        state.loadingIndex = i;
        const old = audio;
        audio = window.PreviewPlayback
          ? window.PreviewPlayback.replace(audio, previewSource(state.queue[i]))
          : audio;
        if (!window.PreviewPlayback) {
          audio.pause();
          audio.src = previewSource(state.queue[i]);
          audio.currentTime = 0;
        }
        audio.dataset.song = String(state.queue[i].id);
        if (audio !== old) delete audio.dataset.albumBound;
        bindAlbumAudio(audio);
        attachPlayers();
        if (!play) {
          state.index = i;
          state.finished = false;
          updateAlbumInfo();
          return;
        }
        try {
          await previewPlay(audio);
          if (
            state !== albumPlayer ||
            !state.playRequested ||
            !audio.isConnected
          ) {
            window.PreviewPlayback?.cancel(audio);
            return;
          }
          state.index = i;
          state.finished = false;
          updateAlbumInfo();
          markAlbumTrack();
          state.primeTimer = setTimeout(() => {
            if (
              state === albumPlayer &&
              state.playRequested &&
              !state.advancing
            )
              window.PreviewPlayback?.prime(
                previewSource(state.queue[(i + 1) % count]),
              );
          }, 650);
          return;
        } catch (error) {
          if (error.name === "AbortError") return;
          if (
            error.name === "PreviewBlockedError" ||
            error.name === "NotAllowedError"
          ) {
            state.playRequested = false;
            window.PreviewPlayback?.stopAll();
            if (error.name === "NotAllowedError")
              toast("Press the cover to play");
            return;
          }
          state.failed.add(i);
        }
      }
      state.index = -1;
      state.finished = true;
      state.playRequested = false;
      window.PreviewPlayback?.stopAll();
      $("#album-audio")?.removeAttribute("src");
      $("#album-player-info").textContent = "No playable previews";
      markAlbumTrack();
    } finally {
      state.advancing = false;
      state.loadingIndex = null;
      if (state.pending) {
        const pending = state.pending;
        state.pending = null;
        await startAlbumAt(pending.index, pending.play, pending.direction);
      }
    }
  }
  async function advanceAlbum(step) {
    if (!albumPlayer) return;
    const state = albumPlayer,
      current = state.pending?.index ?? state.loadingIndex ?? state.index;
    await startAlbumAt(
      current < 0 ? (step < 0 ? state.queue.length - 1 : 0) : current + step,
      state.playRequested,
      step < 0 ? -1 : 1,
    );
  }
  async function toggleAlbum() {
    if (!albumPlayer) return;
    const state = albumPlayer,
      audio = $("#album-audio");
    if (state.playRequested) {
      state.playRequested = false;
      state.pending = null;
      clearTimeout(state.primeTimer);
      if (window.PreviewPlayback) window.PreviewPlayback.cancel(audio);
      else audio.pause();
      markAlbumTrack();
      return;
    }
    if (state.index < 0) {
      state.failed.clear();
      await startAlbumAt(0);
      return;
    }
    if (
      !audio.getAttribute("src") ||
      audio.dataset.song !== String(state.queue[state.index]?.id)
    ) {
      await startAlbumAt(state.index);
      return;
    }
    state.playRequested = true;
    try {
      await previewPlay(audio);
      markAlbumTrack();
    } catch (error) {
      if (error.name === "AbortError") return;
      if (error.name === "PreviewBlockedError") {
        state.playRequested = false;
        return;
      }
      if (error.name === "NotAllowedError") {
        state.playRequested = false;
        toast("Press the cover to play");
      } else {
        state.failed.add(state.index);
        await startAlbumAt(state.index + 1);
      }
    }
  }

  // Keep maintenance selection explicit while searching title, artist, album or ID.
  let maintenanceMatches = [];
  function maintenancePicker() {
    return `<label for="maintenance-query">Find a song</label><div class="search-form maintenance-search"><input id="maintenance-query" type="search" autocomplete="off" aria-label="Find song by title, artist, album or ID" placeholder="Title, artist, album or #ID…"><button type="button" data-maintenance-first aria-label="Select first matching song">↵</button></div><div id="maintenance-results" class="maintenance-results"></div><small class="maintenance-count" id="maintenance-count" role="status"></small><input id="stats-song" name="song_id" type="hidden"><div id="maintenance-selected" class="maintenance-selected" hidden></div>`;
  }
  function renderMaintenanceMatches() {
    const query = normal($("#maintenance-query").value),
      idQuery = /^#\d+$/.test(query) ? Number(query.replace("#", "")) : null;
    maintenanceMatches = songs.filter(
      (s) =>
        !query ||
        (idQuery !== null
          ? s.id === idQuery
          : normal([s.title, s.artist, s.album, "#" + s.id].join(" ")).includes(
              query,
            )),
    );
    const selected = Number($("#stats-song").value);
    $("#maintenance-results").innerHTML =
      maintenanceMatches
        .slice(0, 12)
        .map(
          (s) =>
            `<button class="maintenance-result" type="button" data-maintenance-song="${s.id}" aria-pressed="${s.id === selected}">${compactArt(s)}<span class="compact-copy"><strong>${esc(s.title)}</strong><small>${esc(s.artist)} · ${esc(s.album)}</small></span><small>#${s.id}</small></button>`,
        )
        .join("") || '<div class="empty">No matching songs</div>';
    $("#maintenance-count").textContent =
      maintenanceMatches.length +
      " matches" +
      (maintenanceMatches.length > 12 ? " · First 12 shown" : "");
  }
  function selectMaintenanceSong(id) {
    const s = byId(songs, id);
    if (!s) return;
    if (toolTarget?.name === "Manual Elo correction")
      toolTarget.expectedElo = s.elo_score;
    $("#stats-song").value = s.id;
    const node = $("#maintenance-selected");
    node.hidden = false;
    node.innerHTML = `${compactArt(s)}<div class="compact-copy"><strong>${esc(s.title)}</strong><small>${esc(s.artist)} · ${esc(s.album)} · #${s.id}</small><small>${Math.round(s.elo_score)} Elo · ${s.attempts} trivia attempts · ${s.correct} points</small></div>`;
    if ($("#field-elo")) $("#field-elo").value = Math.round(s.elo_score);
    triviaEditNames.forEach((key) => {
      if ($("#field-" + key)) $("#field-" + key).value = s[key] || 0;
    });
    $$("[data-maintenance-song]").forEach((b) =>
      b.setAttribute(
        "aria-pressed",
        String(Number(b.dataset.maintenanceSong) === s.id),
      ),
    );
    $("#editor-submit").disabled = false;
    if ($("[data-clear-trivia]")) $("[data-clear-trivia]").disabled = false;
  }

  function filterGlobalHistory() {
    const rows = $$("#all-history [data-match-mode]");
    rows.forEach(
      (row) =>
        (row.hidden =
          historyFilter !== "all" && row.dataset.matchMode !== historyFilter),
    );
    $("#history-empty").hidden = rows.some((row) => !row.hidden);
    $$("[data-history]").forEach((b) => {
      b.classList.toggle("active", b.dataset.history === historyFilter);
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.history === historyFilter),
      );
    });
  }

  // Tournaments use the same two-card layout and audio behaviour as Standard Vote.
  let bracketState = null,
    bracketVoting = false,
    bracketLoading = false,
    bracketReveal = null;
  async function renderTournamentSetup() {
    document.body.classList.add("tournament-game");
    main.classList.remove("narrow");
    const scopeControl = window.GameplayUI.select(
      "t-scope",
      "Choose tracks from",
      [
        { value: "global", label: "Whole library" },
        { value: "artist", label: "Artist" },
        { value: "album", label: "Album" },
        { value: "tag", label: "Tag" },
      ],
      "global",
    );
    main.innerHTML = `<div class="page-head"><h1 class="tournament">Tournament</h1></div><section class="panel tournament-setup dashboard-surface"><form id="tournament-setup"><fieldset class="game-choices"><legend>Tracks in bracket</legend><div class="game-choice-row">${[8, 16, 32].map((size, i) => `<label class="game-choice"><input type="radio" name="t-size" value="${size}" ${i === 0 ? "checked" : ""}><span><b>${size} tracks</b><small>${Math.log2(size)} rounds + bronze</small></span></label>`).join("")}</div></fieldset><fieldset class="game-choices"><legend>Bracket type</legend><div class="game-choice-row two"><label class="game-choice"><input type="radio" name="t-visibility" id="t-visible" value="visible" checked><span><b>Non-blind</b><small>Names &amp; artwork</small></span></label><label class="game-choice"><input type="radio" name="t-visibility" id="t-blind" value="blind"><span><b>Blind</b><small>Listen, then reveal</small></span></label></div></fieldset>${scopeControl}<div id="t-scope-picker" hidden><div class="search-form"><input type="search" id="scope-query" aria-label="Find artist, album or tag" placeholder="Find artist, album or tag…"><button type="button" data-scope-first aria-label="Choose first result">↵</button></div><div id="scope-selected" class="podium-summary" role="status"></div><div class="scope-results" id="scope-results"></div></div><p id="tournament-ready" class="tournament-ready" role="status"></p><button class="btn primary" id="generate-btn" type="submit">Start tournament →</button><p class="tournament-error" id="setup-error" role="alert" hidden></p></form></section><section class="panel spaced-panel dashboard-surface" id="saved-tournaments" hidden><div class="section-head"><h2 class="tournament">Continue a Tournament</h2></div><div id="saved-tournament-list"></div></section>`;
    try {
      const data = await api("/api/tournaments"),
        active = (data.tournaments || []).filter(
          (t) => t.status === "in_progress",
        );
      $("#saved-tournaments").hidden = !active.length;
      $("#saved-tournament-list").innerHTML = active
        .map(
          (t) =>
            `<div class="saved-bracket"><div><strong>Tournament #${t.id}</strong><small>${t.size} tracks · ${t.is_blind ? "Blind" : "Non-blind"} · ${esc(t.scope_type)} · ${t.matches_completed || 0} saved matches</small></div><button class="btn small" type="button" data-resume-tournament="${t.id}">Resume →</button></div>`,
        )
        .join("");
    } catch (error) {
      $("#saved-tournaments").hidden = false;
      $("#saved-tournament-list").innerHTML =
        '<div class="empty error">' + esc(error.message) + "</div>";
    }
    renderScope();
    const selected = Number(
      new URLSearchParams(location.search).get("tournament"),
    );
    if (selected) await loadBracket(selected);
  }
  async function generateBracket() {
    if (bracketLoading) return;
    bracketLoading = true;
    const button = $("#generate-btn"),
      error = $("#setup-error");
    button.disabled = true;
    error.hidden = true;
    try {
      const scope = $("#t-scope").value,
        params = new URLSearchParams({
          size: tournamentSize(),
          scope,
          is_blind: String($("#t-blind").checked),
        });
      if (scope !== "global") params.set("scope_id", scopeSelection || "");
      const result = await api("/api/generate_bracket?" + params.toString());
      await loadBracket(result.tournament_id);
    } catch (err) {
      if ($("#setup-error")) {
        $("#setup-error").textContent = err.message;
        $("#setup-error").hidden = false;
        renderScope();
      } else toast(err.message);
    } finally {
      bracketLoading = false;
      if ($("#tournament-setup")) renderScope();
    }
  }
  async function loadBracket(id, autoplay = true) {
    cancelRoundTransition();
    stopAudio();
    const data = await api("/api/tournaments/" + id);
    bracketState = {
      tournament: data.tournament,
      tracks: new Map(
        data.entries.map((s) => [Number(s.id), { ...byId(songs, s.id), ...s }]),
      ),
      matches: data.matches || [],
      active: null,
    };
    bracketReveal = null;
    bracketVoting = false;
    history.replaceState(
      null,
      "",
      "/tournament?tournament=" + data.tournament.id,
    );
    if (data.tournament.status === "completed") {
      renderChampion(autoplay);
      return;
    }
    await nextBracketMatch();
  }
  async function nextBracketMatch() {
    if (!bracketState || bracketVoting) return;
    cancelRoundTransition();
    stopAudio();
    bracketReveal = null;
    const pending = bracketState.matches
      .filter((m) => m.status === "pending")
      .sort(
        (a, b) =>
          a.round_number - b.round_number || a.match_number - b.match_number,
      );
    if (!pending.length) {
      await completeBracket();
      return;
    }
    const bronze = pending.find((m) => m.match_type === "third_place");
    const current = bronze
      ? [bronze]
      : pending.filter((m) => m.round_number === pending[0].round_number);
    bracketState.active = current[Math.floor(Math.random() * current.length)];
    renderBracketMatch();
  }
  function bracketOverlay(s, i) {
    if (!bracketReveal) return "";
    const winner = bracketReveal.winner === s.id;
    if (bracketReveal.phase === "elo") {
      const side = winner ? bracketReveal.elo.winner : bracketReveal.elo.loser,
        delta = Number(side.elo_score) - Number(side.elo_before);
      return `<div class="score-reveal elo-reveal ${winner ? "score-win" : "score-loss"}" role="status"><small>Public Elo</small><div class="score-values"><span class="score-before">${Math.round(side.elo_before)}</span><span class="score-arrow" aria-hidden="true">→</span><strong class="elo-score" id="bracket-elo-${i}">${Math.round(side.elo_before)}</strong></div><b class="elo-delta ${delta < 0 ? "loss" : ""}">${delta < 0 ? "↓ " : "↑ +"}${Math.round(delta)}</b></div>`;
    }
    const loserLabel =
      bracketState.active.match_type === "third_place"
        ? "Fourth place"
        : bracketState.active.round_number ===
            Math.log2(bracketState.tournament.size)
          ? "Runner-up"
          : "Eliminated";
    return winner
      ? `<div class="score-reveal points-reveal" role="status"><small>Tournament points</small><strong>↑ +<span id="bracket-points">0.00</span></strong><b>🏆 Winner</b></div>`
      : `<div class="score-reveal runner-up-reveal"><b>${loserLabel}</b></div>`;
  }
  function bracketCard(s, i) {
    const hidden = !!bracketState.tournament.is_blind && !bracketReveal,
      winner = bracketReveal?.winner === s.id,
      loserLabel =
        bracketState.active.match_type === "third_place"
          ? "Fourth place"
          : bracketState.active.round_number ===
              Math.log2(bracketState.tournament.size)
            ? "Runner-up"
            : "Eliminated";
    return `<article class="game-card dashboard-surface ${bracketReveal ? (winner ? "winner" : "loser") : ""}">${matchCover(s, "bracket-audio-" + i, hidden, bracketOverlay(s, i))}<h2>${hidden ? "Track " + "AB"[i] : `<a class="song" title="${esc(s.title)}" href="${urlFor("songs", s)}">${esc(s.title)}</a>`}</h2><div class="game-meta">${hidden ? "" : gameMetadata(s)}</div><button class="btn primary vote-btn" data-tournament-vote="${i}" ${bracketReveal || bracketVoting ? "disabled" : ""}>${bracketReveal ? (winner ? "✓ Winner" : loserLabel) : "Vote for " + "AB"[i]}</button></article>`;
  }
  function scheduleBracketReveal(audioId) {
    const saved = bracketReveal;
    if (!saved) return;
    scheduleRoundTransition(audioId, nextBracketMatch, saved.hold);
    if (!saved.elo || saved.phase !== "points") return;
    const token = roundTransition.token;
    roundTransition.stageTimer = later(() => {
      if (
        token !== roundTransition.token ||
        bracketReveal !== saved ||
        roundTransition.closed
      )
        return;
      roundTransition.stageTimer = null;
      saved.phase = "elo";
      [bracketState.active.song1_id, bracketState.active.song2_id].forEach(
        (id, i) => {
          const cover = $$(".matchup .match-cover")[i],
            old = cover?.querySelector(".score-reveal"),
            track = bracketState.tracks.get(id);
          if (!old || !track) return;
          old.outerHTML = bracketOverlay(track, i);
          const side = id === saved.winner ? saved.elo.winner : saved.elo.loser;
          animateScore(
            $("#bracket-elo-" + i),
            side.elo_before,
            side.elo_score,
            0,
            () => bracketReveal === saved,
          );
        },
      );
    }, saved.pointsDelay);
  }
  function renderBracketMatch() {
    const { tournament, active, tracks, matches } = bracketState,
      pair = [tracks.get(active.song1_id), tracks.get(active.song2_id)];
    if (pair.some((s) => !s)) {
      main.innerHTML =
        '<div class="empty error">A track in this saved match is unavailable.</div><a class="btn" href="/tournament">Back to tournaments</a>';
      return;
    }

    const inRound = matches.filter(
        (m) => m.round_number === active.round_number,
      ),
      done = inRound.filter((m) => m.status === "completed").length,
      remaining = tournament.size / 2 ** (active.round_number - 1),
      name =
        active.match_type === "third_place"
          ? "Third-place playoff"
          : remaining === 2
            ? "Grand Final"
            : remaining === 4
              ? "Semi-finals"
              : remaining === 8
                ? "Quarter-finals"
                : "Round " + active.round_number;
    main.innerHTML = `<div class="game-head"><div><h1 class="tournament">${tournament.is_blind ? "Blind Tournament" : "Tournament"}</h1><p class="bracket-progress">${name} · Match ${Math.min(done + (bracketReveal ? 0 : 1), inRound.length)} / ${inRound.length}</p></div></div><div class="matchup">${bracketCard(pair[0], 0)}<span class="vs-circle">VS</span>${bracketCard(pair[1], 1)}</div>${bracketReveal ? roundProgress(bracketReveal.hold) : ""}<p id="bracket-error" class="tournament-error" role="alert" hidden></p>`;
    attachPlayers();
    window.PreviewPlayback?.preloadPair([
      $("#bracket-audio-0"),
      $("#bracket-audio-1"),
    ]);
  }
  async function voteBracket(index) {
    if (bracketVoting || bracketReveal || !bracketState?.active) return;
    bracketVoting = true;
    $$("[data-tournament-vote]").forEach((b) => (b.disabled = true));
    cancelRoundTransition();
    const match = bracketState.active,
      winner = index === 0 ? match.song1_id : match.song2_id,
      loser = index === 0 ? match.song2_id : match.song1_id;
    let result;
    try {
      result = await api("/api/tournament_vote", {
        tournament_id: bracketState.tournament.id,
        match_id: match.id,
        winner_id: winner,
        loser_id: loser,
      });
    } catch (error) {
      $("#bracket-error").textContent = error.message;
      $("#bracket-error").hidden = false;
      $$("[data-tournament-vote]").forEach((b) => (b.disabled = false));
      return;
    } finally {
      bracketVoting = false;
    }
    bracketState.matches = result.matches;
    const receipt = result.elo_result,
      eligible =
        match.round_number === 1 &&
        match.match_type === "bracket" &&
        receipt?.winner?.id === winner &&
        receipt?.loser?.id === loser &&
        [receipt.winner, receipt.loser].every(
          (side) =>
            Number.isFinite(side.elo_before) && Number.isFinite(side.elo_score),
        );
    bracketReveal = {
      winner,
      points: result.points_awarded,
      elo: eligible ? receipt : null,
      phase: "points",
      hold: eligible
        ? flow?.duration("tournamentFirst") || 7500
        : flow?.duration("pairResult") || RESULT_HOLD_MS,
      pointsDelay: flow?.duration("tournamentPoints") || 2800,
    };
    window.PreviewPlayback?.hold();
    renderBracketMatch();
    animateScore($("#bracket-points"), 0, Number(result.points_awarded), 2);
    scheduleBracketReveal("bracket-audio-" + index);
  }
  async function completeBracket() {
    const { tournament, matches } = bracketState,
      final = matches
        .filter((m) => m.match_type !== "third_place")
        .sort(
          (a, b) =>
            b.round_number - a.round_number || b.match_number - a.match_number,
        )[0];
    if (!final?.winner_id) {
      main.innerHTML =
        '<div class="empty error">No final result is available.</div>';
      return;
    }
    bracketVoting = true;
    try {
      await api("/api/tournament_complete", {
        tournament_id: tournament.id,
        champion_id: final.winner_id,
      });
      tournament.champion_id = final.winner_id;
      tournament.runner_up_id = final.loser_id;
      const bronze = matches.find((m) => m.match_type === "third_place");
      tournament.third_place_id = bronze?.winner_id;
      tournament.fourth_place_id = bronze?.loser_id;
      tournament.status = "completed";
      renderBracketReplay();
    } catch (error) {
      main.innerHTML = `<section class="panel"><h2 class="tournament">Finish Tournament</h2><p class="tournament-error" role="alert">${esc(error.message)}</p><button class="btn primary" data-bracket-next>Retry →</button><a class="btn" href="/tournament">Saved tournaments</a></section>`;
    } finally {
      bracketVoting = false;
    }
  }
  document.addEventListener("preview-blocked", () => {
    if (albumPlayer) {
      albumPlayer.playRequested = false;
      albumPlayer.pending = null;
      $("#album-audio")?.pause();
    }
    if (podiumPlayback) pausePodium();
  });
  const PODIUM_SNIPPET_MS = 6000;
  let podiumPlayback = null;
  function cancelPodiumPlayback() {
    if (!podiumPlayback) return;
    clearTimeout(podiumPlayback.timer);
    clearTimeout(podiumPlayback.primeTimer);
    podiumPlayback.token++;
    podiumPlayback.requested = false;
    podiumPlayback = null;
  }
  function podiumControl() {
    const b = $("[data-podium-toggle]");
    if (!b) return;
    const playing = !!podiumPlayback?.requested;
    b.textContent = playing ? "Pause previews" : "Play previews";
    b.setAttribute("aria-pressed", String(playing));
  }
  function pausePodium() {
    if (!podiumPlayback) return;
    clearTimeout(podiumPlayback.timer);
    clearTimeout(podiumPlayback.primeTimer);
    podiumPlayback.token++;
    podiumPlayback.requested = false;
    window.PreviewPlayback?.stopAll();
    podiumPlayback.queue.forEach((a) => a.pause());
    podiumControl();
  }
  async function playPodium(index) {
    const state = podiumPlayback;
    if (!state || roundTransition.closed) return;
    clearTimeout(state.timer);
    clearTimeout(state.primeTimer);
    const token = ++state.token;
    state.requested = true;
    podiumControl();
    for (let attempt = 0; attempt < state.queue.length; attempt++) {
      const next =
          (((index + attempt) % state.queue.length) + state.queue.length) %
          state.queue.length,
        audio = state.queue[next];
      if (state.failed.has(audio.id)) continue;
      audio.currentTime = 0;
      try {
        await previewPlay(audio);
        if (
          state !== podiumPlayback ||
          token !== state.token ||
          !state.requested ||
          roundTransition.closed
        ) {
          audio.pause();
          return;
        }
        state.index = next;
        state.failed.delete(audio.id);
        state.primeTimer = setTimeout(() => {
          if (
            state === podiumPlayback &&
            token === state.token &&
            state.requested
          )
            window.PreviewPlayback?.prime(
              state.queue[(next + 1) % state.queue.length],
            );
        }, 650);
        state.timer = setTimeout(() => playPodium(next + 1), PODIUM_SNIPPET_MS);
        return;
      } catch (error) {
        if (
          state !== podiumPlayback ||
          token !== state.token ||
          error.name === "AbortError"
        )
          return;
        state.failed.add(audio.id);
        if (
          error.name === "PreviewBlockedError" ||
          error.name === "NotAllowedError"
        ) {
          pausePodium();
          return;
        }
      }
    }
    pausePodium();
  }
  async function selectPodiumAudio(id) {
    const state = podiumPlayback;
    if (!state) return;
    const index = state.queue.findIndex((a) => a.id === id);
    if (index < 0) return;
    if (index === state.index && state.requested) {
      pausePodium();
      return;
    }
    await playPodium(index);
  }
  function startPodium(autoplay = true) {
    const queue = $$(".podium-entry audio").filter((a) =>
      a.getAttribute("src"),
    );
    podiumPlayback = queue.length
      ? {
          queue,
          index: 0,
          timer: null,
          primeTimer: null,
          token: 0,
          requested: false,
          failed: new Set(),
        }
      : null;
    const b = $("[data-podium-toggle]");
    if (b) b.disabled = !queue.length;
    queue.forEach((a) => {
      const card = a.closest(".podium-entry");
      a.addEventListener("play", () => card.classList.add("is-playing"));
      a.addEventListener("pause", () => card.classList.remove("is-playing"));
      a.addEventListener("ended", () => {
        card.classList.remove("is-playing");
        if (
          podiumPlayback?.requested &&
          podiumPlayback.queue[podiumPlayback.index] === a &&
          !window.PreviewPlayback?.isPending?.()
        )
          playPodium(podiumPlayback.index + 1);
      });
      a.addEventListener("error", async () => {
        const state = podiumPlayback;
        if (state?.queue[state.index] === a && state.requested) {
          const info = await window.PreviewPlayback?.problem(a);
          if (state !== podiumPlayback) return;
          if (info?.blocked) {
            pausePodium();
            return;
          }
          state.failed.add(a.id);
          if (state.failed.size >= queue.length) pausePodium();
          else {
            clearTimeout(state.timer);
            state.timer = setTimeout(() => playPodium(state.index + 1), 1000);
          }
        }
      });
    });
    if (queue.length && autoplay) playPodium(0);
    else podiumControl();
  }
  function renderBracketReplay() {
    cancelRoundTransition();stopAudio();
    main.innerHTML='<div class="bracket-page-header"><h1 class="tournament">Road to the podium</h1></div><div id="tournament-replay" class="tournament-map"></div>';
    bracketMap=window.TournamentBracket.mount($("#tournament-replay"),{
      tournament:bracketState.tournament,entries:[...bracketState.tracks.values()],matches:bracketState.matches
    },{animate:true,sound:true,onDone:state=>renderChampion(state.sound)});
  }
  function renderChampion(autoplay = true) {
    cancelRoundTransition();
    stopAudio();
    const { tournament, tracks, matches } = bracketState,
      s = tracks.get(Number(tournament.champion_id));
    if (!s) {
      main.innerHTML = '<div class="empty">Champion unavailable</div>';
      return;
    }
    const final = matches
      .filter((m) => m.match_type !== "third_place")
      .sort((a, b) => b.round_number - a.round_number)[0];
    const runner = tracks.get(
        Number(tournament.runner_up_id || final?.loser_id),
      ),
      third = tracks.get(Number(tournament.third_place_id));
    main.innerHTML = `<div class="page-head podium-heading"><h1 class="tournament">Tournament Podium</h1></div><section class="winner-podium" aria-label="Tournament podium">${podiumEntry(s, 1, matches)}${runner ? podiumEntry(runner, 2, matches) : ""}${third ? podiumEntry(third, 3, matches) : ""}</section><div class="champion-actions"><button type="button" class="btn" data-podium-toggle aria-pressed="false">Play previews</button><button class="btn tournament" type="button" data-replay-bracket>View bracket &amp; replay</button><a class="btn primary" href="/tournament">Play Again →</a></div>`;
    attachPlayers();
    startPodium(autoplay);
  }
  function podiumEntry(s, place, matches) {
    const won = matches.filter((m) => m.winner_id === s.id),
      labels = { 1: "Champion", 2: "Runner-up", 3: "Third place" },
      medals = { 1: "🥇", 2: "🥈", 3: "🥉" };
    return `<article class="game-card dashboard-surface podium-entry podium-place-${place} ${place === 1 ? "champion-card" : "podium-card"}"><div class="podium-medal" aria-label="${labels[place]}">${medals[place]}<span>${labels[place]}</span></div>${mediaButton(s, place === 1 ? "champion-audio" : "podium-audio-" + place, false, false)}<h2><a class="song" title="${esc(s.title)}" href="${urlFor("songs", s)}">${esc(s.title)}</a></h2><div class="game-meta">${gameMetadata(s)}</div><div class="tournament-award"><strong class="tournament">${won.length} wins</strong><span>${won.reduce((n, m) => n + Number(m.points_awarded || 0), 0).toFixed(2)} points</span></div><div class="podium-step" aria-hidden="true">${place}</div></article>`;
  }

  document.addEventListener("click", e=>{

    if(e.target.closest('[data-replay-bracket]')){renderBracketReplay();return;}
    const more=e.target.closest("[data-record-more]");
    if(more){openRecordMenu(more);return;}
    if(recordMenu && (!recordMenu.panel.contains(e.target) || e.target.closest("button")))closeRecordMenu();
  });
  document.addEventListener("keydown", e=>{
    if(e.key==="ArrowDown" && e.target.matches("[data-record-more]")){e.preventDefault();openRecordMenu(e.target);return;}
    if(!recordMenu)return;
    if(e.key==="Escape"){e.preventDefault();closeRecordMenu(true);return;}
    if(recordMenu.panel.contains(e.target) && ["ArrowDown","ArrowUp","Home","End"].includes(e.key)){
      e.preventDefault();const buttons=[...recordMenu.panel.querySelectorAll("button:not(:disabled)")],at=buttons.indexOf(document.activeElement);
      buttons[e.key==="Home"?0:e.key==="End"?buttons.length-1:(at+(e.key==="ArrowDown"?1:-1)+buttons.length)%buttons.length]?.focus({preventScroll:true});
    }
  });
  document.addEventListener("scroll", e=>{
    if (!recordMenu || recordMenu.panel.contains(e.target)) return;
    // Click/focus may queue a scroll event before the menu opens. Only actual
    // movement after placement invalidates its anchor geometry.
    const {button,anchor,table,x,y,tableX,tableY} = recordMenu, box = button.getBoundingClientRect();
    if (scrollX !== x || scrollY !== y || box.top !== anchor.top || box.left !== anchor.left || table?.scrollLeft !== tableX || table?.scrollTop !== tableY) closeRecordMenu();
  },true);
  window.addEventListener("resize",()=>closeRecordMenu());
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (b?.disabled) return;
    if (b?.id === "volume-btn") {
      const panel = $("#volume-panel");
      panel.hidden = !panel.hidden;
      b.setAttribute("aria-expanded", String(!panel.hidden));
      if (!panel.hidden) $("#volume-range").focus();
    } else if (!e.target.closest(".volume")) volumeClose();
    $$(".nav-left details[open]").forEach((d) => {
      if (!d.contains(e.target)) d.open = false;
    });
    if (!b) return;
    try {
      if (b.hasAttribute("data-retry-dev-data")) renderDevView();
      if (b.hasAttribute("data-podium-toggle")) {
        if (podiumPlayback?.requested) pausePodium();
        else if (podiumPlayback) await playPodium(podiumPlayback.index);
      }
      if (b.hasAttribute("data-album-play")) await toggleAlbum();
      else if (b.dataset.audio) {
        await toggleAudio(b.dataset.audio);
        markAlbumTrack();
      }
      if (b.dataset.tournamentVote !== undefined)
        await voteBracket(Number(b.dataset.tournamentVote));
      if (b.hasAttribute("data-bracket-next")) await nextBracketMatch();
      if (b.dataset.resumeTournament) {
        if (bracketLoading) return;
        bracketLoading = true;
        b.disabled = true;
        try {
          await loadBracket(Number(b.dataset.resumeTournament));
        } finally {
          bracketLoading = false;
          b.disabled = false;
        }
      }
      if (b.dataset.albumStep) await advanceAlbum(Number(b.dataset.albumStep));
      if (b.dataset.rankingView) {
        rankingView = b.dataset.rankingView;
        const params = new URLSearchParams(location.search);
        if (rankingView === "bottom") params.set("view", "bottom");
        else params.delete("view");
        history.replaceState(
          {},
          "",
          location.pathname + (params.size ? "?" + params : ""),
        );
        renderRanking(page.replace("rankings_", ""));
      }
      if (b.dataset.profileMore && profileState) {
        if (b.dataset.profileMore === "tracks") {
          profileState.trackLimit += 30;
          renderProfileTracks(true);
        } else if (b.dataset.profileMore === "albums") {
          profileState.albumLimit += 6;
          renderProfileAlbums(true);
        }
      }
      if (b.dataset.profileSort) {
        profileState.sort = b.dataset.profileSort;
        $$("[data-profile-sort]").forEach((n) => {
          n.classList.toggle(
            "active",
            n.dataset.profileSort === profileState.sort,
          );
          n.setAttribute(
            "aria-pressed",
            String(n.dataset.profileSort === profileState.sort),
          );
        });
        renderProfileTracks();
      }
      if (b.dataset.bulkAlbum) {
        bulkAlbum = Number(b.dataset.bulkAlbum);
        $("#bulk-album-selected").textContent =
          byId(albums, bulkAlbum)?.title || "";
        renderBulkAlbums();
      }
      if (b.dataset.scopeId && !b.disabled) {
        scopeSelection = b.dataset.scopeId;
        $("#scope-selected").textContent = b.dataset.scopeName;
        renderScope();
      }
      if (b.hasAttribute("data-scope-first"))
        $("#scope-results .scope-option:not(:disabled)")?.click();
      if (b.hasAttribute("data-bulk-more")) {
        bulkLimit += 50;
        renderBulkRows();
      }
      if (b.hasAttribute("data-bulk-all")) {
        bulkMatches()
          .filter((s) => !bulkSelection.has(s.id))
          .slice(0, Math.max(0, 500 - bulkSelection.size))
          .forEach((s) => bulkSelection.add(s.id));
        renderBulkRows();
      }
      if (b.hasAttribute("data-bulk-clear")) {
        bulkSelection.clear();
        renderBulkRows();
      }
      if (b.hasAttribute("data-bulk-apply")) await applyBulk();
      if (b.dataset.maintenanceSong)
        selectMaintenanceSong(b.dataset.maintenanceSong);
      if (b.hasAttribute("data-maintenance-first") && maintenanceMatches.length)
        selectMaintenanceSong(maintenanceMatches[0].id);
      if (b.dataset.scroll) {
        const el = $("#shelf-" + b.dataset.scroll);
        shelfState.get(el.id).manualUntil = Date.now() + 4000;
        el.scrollBy({ left: Number(b.dataset.dir) * 310, behavior: "smooth" });
      }
      if (b.dataset.historyOrigin) {
        historyOrigin = b.dataset.historyOrigin;
        renderSongHistory();
      }
      if (b.dataset.history) {
        historyFilter = b.dataset.history;
        if (page === "history") filterGlobalHistory();
        else renderSongHistory();
      }
      if (b.dataset.mode && !voting && !revealed && !matchLoading) {
        stopAudio();
        flow?.clear();
        window.SpecialModes?.cancelGuess();
        gameMode = b.dataset.mode;
        blind = gameMode === "blind";
        history.replaceState(
          {},
          "",
          gameMode === "standard" ? "/game" : "/game?mode=" + gameMode,
        );
        try {
          localStorage.setItem("votingMode", gameMode);
        } catch {}
        await nextMatch();
      }
      if (b.dataset.vote !== undefined) await vote(Number(b.dataset.vote));
      if (b.hasAttribute("data-next")) await nextMatch();
      if (b.dataset.devMore) {
        devLimits[b.dataset.devMore] += 20;
        renderDevResults();
      }
      if (b.dataset.tablePanel) {
        tablePanel = tablePanel === b.dataset.tablePanel ? null : b.dataset.tablePanel;
        renderManage(devView);$("[data-table-panel="+b.dataset.tablePanel+"]")?.focus();
      }
      if (b.dataset.removeTableFilter) {delete tableFilters[b.dataset.removeTableFilter];tablePage=0;renderTableBody();}
      if (b.dataset.sort) {
        tableDir = tableSort === b.dataset.sort ? -tableDir : 1;
        tableSort = b.dataset.sort;
        renderTableBody();
      }
      if (b.hasAttribute("data-columns-default")) {
        saveColumns(devView, tableDefaults[devView]);
        tablePanel="columns";$("#table-columns").hidden=false;$("[aria-controls=table-columns]").setAttribute("aria-expanded","true");
      }
      if (b.hasAttribute("data-table-reset-order")) {
        tableSort = "id";
        tableDir = 1;
        tablePage = 0;
        renderManage(devView);
      }
      if (b.hasAttribute("data-table-direction")) {
        tableDir = -tableDir;
        tablePage = 0;
        renderManage(devView);
      }
      if (b.hasAttribute("data-table-clear")) {
        tableQuery = "";
        tableFilters = {};
        tablePage = 0;
        missingAppleOnly = false;
        rememberTable();
        renderManage(devView);
        $("[data-table-clear]").focus();
      }
      if (b.hasAttribute("data-table-prev")) {
        tablePage = Math.max(0, tablePage - 1);
        renderTableBody();
        if(b.closest(".dev-pagination"))$(".dev-table-toolbar")?.scrollIntoView?.({block:"start"});
      }
      if (b.hasAttribute("data-table-next")) {
        tablePage++;
        renderTableBody();
        if(b.closest(".dev-pagination"))$(".dev-table-toolbar")?.scrollIntoView?.({block:"start"});
      }
      if (b.dataset.edit) editRecord(b.dataset.edit, Number(b.dataset.id));
      if (b.dataset.delete)
        deleteRecord(b.dataset.delete, Number(b.dataset.id));
      if (b.dataset.import) await importSong(Number(b.dataset.import));
      if (b.dataset.tool) await tool(b.dataset.tool);
      if (b.dataset.previewQuality) {
        const id = Number(b.dataset.previewQuality),
          quality = await api("/api/dev/song-quality/" + id),
          song = byId(songs, id);
        toolTarget = { name: "Preview quality", id };
        editTarget = null;
        openDialog(
          "Preview quality",
          `<div class="quality-dialog"><div class="catalog-edit-header"><span class="badge song">Song #${id}</span><strong title="${esc(song?.title || "Song")}">${esc(song?.title || "Song")}</strong></div><section class="catalog-edit-section"><h3>Preview review</h3><label class="quality-flag"><input type="checkbox" name="preview_bad" ${quality.preview_bad ? "checked" : ""}><span>Flag this preview as poor quality</span></label><div class="field"><label for="field-preview_note">Review note</label><textarea id="field-preview_note" name="preview_note" rows="4" placeholder="What needs attention?">${esc(quality.preview_note || "")}</textarea></div><p class="muted">This note is for private analysis. It does not change playback or song selection.</p></section></div>`,
        );
        return;
      }
      if (b.dataset.vibeMaintain) {
        if (window.DevSystem && !window.DevSystem.canNavigate()) return;
        navigateDev("vibe_records", true, () =>
          window.DevVibe?.edit(Number(b.dataset.vibeMaintain)),
        );
        return;
      }
      if (b.dataset.songStats) {
        await tool("Trivia maintenance");
        selectMaintenanceSong(b.dataset.songStats);
      }
      if (b.dataset.editPodium) {
        const id = Number(b.dataset.editPodium),
          ms = DB.tournament_matches.filter((m) => m.tournament_id === id),
          final = ms
            .filter((m) => m.match_type !== "third_place")
            .sort((a, b) => b.round_number - a.round_number)[0],
          bronze = ms.find((m) => m.match_type === "third_place");
        if (!final?.winner_id) {
          toast("No saved final to edit");
          return;
        }
        toolTarget = { name: "Edit podium", id };
        editTarget = null;
        const pick = (m, key, name) =>
          `<div class="field"><label>${name}<select name="${key}">${[m.song1_id, m.song2_id].map((id) => `<option value="${id}" ${id === m.winner_id ? "selected" : ""}>${esc(byId(songs, id)?.title || "Unavailable")}</option>`).join("")}</select></label></div>`;
        openDialog(
          "Edit podium",
          pick(final, "champion_id", "Final winner") +
            (bronze
              ? pick(bronze, "third_place_id", "Third-place playoff winner")
              : ""),
        );
      }
      if (b.dataset.deleteTournament) {
        toolTarget = {
          name: "Delete tournament",
          id: Number(b.dataset.deleteTournament),
        };
        editTarget = null;
        openDialog("Delete tournament #" + toolTarget.id, "", "Delete");
      }
      if (b.dataset.bracket) {
        const id = Number(b.dataset.bracket),
          t = byId(DB.tournaments, id),
          ms = DB.tournament_matches.filter((m) => m.tournament_id === id);
        toolTarget = null;
        editTarget = null;
        openDialog(
          "Tournament #" + id,
          `<div class="health-row"><span>${t.size} songs</span><strong class="tournament">${esc(byId(songs, t.champion_id)?.title || t.status)}</strong></div>` +
            ms
              .map(
                (m) =>
                  `<div class="health-row"><span>R${m.round_number} · ${esc(byId(songs, m.song1_id)?.title || "—")} / ${esc(byId(songs, m.song2_id)?.title || "—")}</span><strong class="song">${esc(byId(songs, m.winner_id)?.title || "Pending")}</strong></div>`,
              )
              .join(""),
          "Done",
        );
      }
      if (b.hasAttribute("data-clear-trivia")) {
        await api("/api/dev/trivia/" + $("#stats-song").value, null, "DELETE");
        await refreshData();
        triviaEditNames.forEach((key) => ($("#field-" + key).value = 0));
        toast("Cleared");
      }
      if (b.id === "editor-close") dialog.close();
    } catch (error) {
      toast(error.message);
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.dataset.tagQuery) {
      e.preventDefault();
      return;
    }
    if (e.key === "Enter" && e.target.id === "scope-query") {
      e.preventDefault();
      $("#scope-results .scope-option:not(:disabled)")?.click();
    }
  });
  document.addEventListener("input", (e) => {
    const n = e.target;
    if (n.dataset.tagQuery) renderTagPicker(n.dataset.tagQuery);
    if (n.id === "field-tags") renderTagPicker("edit");
    if (n.id === "scope-query") renderScope();
    if (n.id === "bulk-query") {
      bulkQuery = n.value;
      bulkLimit = 50;
      renderBulkRows();
    }
    if (n.id === "bulk-album-query") renderBulkAlbums();
    if (n.id === "maintenance-query") renderMaintenanceMatches();
    if (n.id === "volume-range") volumeApply(Number(n.value));
    if (n.id === "dev-query") {
      devQuery = n.value;
      devLimits = { songs: 10, artists: 10, albums: 10, tags: 10 };
      renderDevResults();
    }
    if (n.id === "manage-query") {
      tableQuery = n.value;
      tablePage = 0;
      renderTableBody();
    }
  });
  document.addEventListener("change", (e) => {
    const n = e.target;
    if (n.dataset.bulkSong) {
      n.checked
        ? bulkSelection.add(Number(n.dataset.bulkSong))
        : bulkSelection.delete(Number(n.dataset.bulkSong));
      renderBulkRows();
    }
    if (n.id === "bulk-action") renderBulkActions();
    if (n.id === "bulk-filter-album") {
      bulkAlbumFilter = n.value;
      renderBulkRows();
    }
    if (n.id === "bulk-filter-artist") {
      bulkArtistFilter = n.value;
      renderBulkRows();
    }
    if (n.id === "bulk-filter-source") {
      bulkSourceFilter = n.value;
      renderBulkRows();
    }
    if (n.id === "bulk-selected-only") {
      bulkSelectedOnly = n.checked;
      renderBulkRows();
    }
    if (n.dataset.pickTag) {
      const context = n.dataset.pickContext,
        id = Number(n.dataset.pickTag),
        count =
          context === "import"
            ? importTags.size
            : pickedTagNames($("#field-tags")?.value).length;
      if (n.checked && count >= SONG_TAG_LIMIT) {
        n.checked = false;
        toast("A song can have at most 8 tags.");
        return;
      }
      if (context === "import") {
        n.checked ? importTags.add(id) : importTags.delete(id);
      } else {
        let names = $("#field-tags")
          .value.split(",")
          .map((t) => t.trim())
          .filter(Boolean);
        const tag = byId(tags, id);
        names = names.filter((t) => tagIdentity(t) !== tagIdentity(tag.name));
        if (n.checked) names.push(tag.name);
        $("#field-tags").value = names.join(", ");
      }
      renderTagPicker(context);
    }
    if (n.dataset.visible) {
      const chosen = columns(devView).map(([key]) => key);
      saveColumns(
        devView,
        n.checked
          ? [...chosen, n.dataset.visible]
          : chosen.filter((k) => k !== n.dataset.visible),
      );
      tablePanel="columns";$("#table-columns").hidden=false;$("[aria-controls=table-columns]").setAttribute("aria-expanded","true");
    }
    if (n.dataset.devType) {
      n.checked
        ? devTypes.add(n.dataset.devType)
        : devTypes.delete(n.dataset.devType);
      renderDevResults();
    }
    if (n.id === "t-scope") {
      scopeSelection = null;
      $("#scope-query").value = "";
      $("#scope-selected").textContent = "";
      $("#t-scope-picker").hidden = n.value === "global";
      renderScope();
    }
    if (n.name === "t-visibility" || n.name === "t-size") renderScope();
    if(n.id === "table-filter-field")configureTableFilter();
    if(n.id === "table-filter-op")$("#table-filter-value").disabled=["missing","present"].includes(n.value);
    if(n.id === "table-page-size"){tablePageSize=Number(n.value);tablePage=0;renderTableBody();}
    if(n.id === "table-page"){tablePage=Math.max(0,(Number(n.value)||1)-1);renderTableBody();}
    if (n.id === "table-order") {
      tableSort = n.value;
      tableDir = 1;
      tablePage = 0;
      renderManage(devView);
    }
    if (n.id === "missing-apple-only") {
      missingAppleOnly = n.checked;
      tablePage = 0;
      renderTableBody("songs");
    }
    if (n.id === "stats-song") {
      const s = byId(songs, n.value);
      if ($("#field-elo")) $("#field-elo").value = Math.round(s.elo_score);
      triviaEditNames.forEach((key) => {
        if ($("#field-" + key)) $("#field-" + key).value = s[key] || 0;
      });
    }
  });
  document.addEventListener("submit", async (e) => {
    const form = e.target;
    if(form.id === "table-filter-form"){e.preventDefault();applyTableFilter();return;}
    if (
      ![
        "dev-search",
        "manage-search",
        "table-filter-form",
        "apple-search",
        "editor-form",
        "tournament-setup",
      ].includes(form.id)
    )
      return;
    e.preventDefault();
    if (form.id === "dev-search") {
      devQuery = $("#dev-query").value;
      renderDevResults();
    }
    if (form.id === "manage-search") {
      tableQuery = $("#manage-query").value;
      tablePage = 0;
      renderTableBody();
    }
    if (form.id === "tournament-setup") await generateBracket();
    if (form.id === "apple-search") await runAppleSearch();
    if (form.id === "editor-form") {
      if (
        toolTarget &&
        ["Manual Elo correction", "Trivia maintenance"].includes(
          toolTarget.name,
        ) &&
        !$("#stats-song").value
      ) {
        toast("Select a song");
        return;
      }
      const submit = $("#editor-submit"),
        gen = editorGeneration;
      if (submit.disabled) return;
      submit.disabled = true;
      form.dataset.saving = "true";
      $("#editor-error").hidden = true;
      try {
        const values = Object.fromEntries(new FormData(form));
        if (editTarget) await saveEdit(values);
        else await submitTool(values);
      } catch (error) {
        editorError(error.message);
      } finally {
        delete form.dataset.saving;
        if (gen === editorGeneration) submit.disabled = false;
      }
    }
  });
  document.addEventListener("keydown", (e) => {
    if (
      e.target.id === "maintenance-query" &&
      ["Enter", "ArrowDown"].includes(e.key)
    ) {
      e.preventDefault();
      if (e.key === "Enter" && maintenanceMatches.length)
        selectMaintenanceSong(maintenanceMatches[0].id);
      if (e.key === "ArrowDown") $("[data-maintenance-song]")?.focus();
      return;
    }
    if (e.key === "Escape") {
      volumeClose();
      $$(".nav-left details").forEach((d) => (d.open = false));
      if (page === "standard") {
        stopAudio();
        $$("[data-mode]")[0]?.focus();
      }
    }
  });
  const historyResets = {
    "Reset Vibe Map": ["vibe", "RESET VIBE"],
    "Reset Elo Guesser history": ["guesser", "RESET GUESSER"],
    "Reset Album Shelves history": ["shelves", "RESET SHELVES"],
    "Reset match history": ["matches", "RESET MATCHES"],
    "Reset trivia history": ["trivia", "RESET TRIVIA"],
    "Reset tournament history": ["tournaments", "RESET TOURNAMENTS"],
  };
  const triviaEditNames = [
    "new_attempts",
    "title_correct",
    "artist_correct",
    "album_attempts",
    "album_correct",
  ];
  function triviaEditFields() {
    const labels = [
      "Rounds",
      "Song correct",
      "Artist correct",
      "Album attempts",
      "Album correct",
    ];
    return (
      '<div class="form-grid">' +
      triviaEditNames
        .map((key, i) =>
          field(key, labels[i], 0, "number", 'required min="0" step="1"'),
        )
        .join("") +
      "</div>"
    );
  }
  let scopeSelection = null;
  function tournamentSize() {
    return $('[name="t-size"]:checked').value;
  }
  function scopeOptions() {
    const type = { artist: "artists", album: "albums", tag: "tags" }[
        $("#t-scope").value
      ],
      blind = $("#t-blind").checked;
    return records(type)
      .filter((r) => type !== "albums" || properAlbum(r))
      .map((r) => ({
        ...r,
        eligible: linkedSongs(type, r).filter((s) => !blind || s.audio_url)
          .length,
      }))
      .sort((a, b) => b.eligible - a.eligible || a.name.localeCompare(b.name));
  }
  function renderScope() {
    if (!$("#scope-results")) return;
    const size = Number(tournamentSize()),
      scope = $("#t-scope").value,
      type = { artist: "artists", album: "albums", tag: "tags" }[scope],
      q = normal($("#scope-query").value),
      options = scopeOptions(),
      selected = options.find((r) => String(r.id) === String(scopeSelection));
    if (scopeSelection && (!selected || selected.eligible < size)) {
      scopeSelection = null;
      $("#scope-selected").textContent = "";
    }
    const globalCount = songs.filter(
      (s) => !$("#t-blind").checked || s.audio_url,
    ).length;
    $("#generate-btn").disabled =
      bracketLoading ||
      (scope === "global" ? globalCount < size : !scopeSelection);
    const ready = $("#tournament-ready"),
      count = scope === "global" ? globalCount : selected?.eligible || 0;
    if (ready)
      ready.textContent =
        scope !== "global" && !scopeSelection
          ? "Choose " +
            { artist: "an artist", album: "an album", tag: "a tag" }[scope] +
            " with at least " +
            size +
            " eligible tracks"
          : count < size
            ? count + " eligible tracks · " + size + " needed"
            : count + " eligible tracks · " + size + " enter the bracket";
    if(ready) ready.textContent += scope === 'global' ? ' · Full first-round Elo' : scope === 'tag' ? ' · Half first-round Elo' : ' · Tournament points only';
    const rows = options.filter((r) =>
      normal(r.name + " " + (r.artist || "") + " #" + r.id).includes(q),
    );
    $("#scope-results").innerHTML =
      rows
        .slice(0, 30)
        .map(
          (r) =>
            `<button class="scope-option ${String(r.id) === String(scopeSelection) ? "selected" : ""}" type="button" aria-pressed="${String(r.id) === String(scopeSelection)}" data-eligible="${r.eligible}" data-scope-id="${r.id}" data-scope-name="${esc(r.name)}" ${r.eligible < size ? "disabled" : ""}>${type === "tags" ? '<span class="tag">#</span>' : compactArt(r, type)}<strong class="${colour(type)}" title="${esc(r.name)}">${esc(r.name)}</strong><small>${r.eligible} ${$("#t-blind").checked ? "preview" : "eligible"} tracks${r.eligible < size ? " · needs " + size : ""}</small></button>`,
        )
        .join("") || '<div class="empty">No matches</div>';
  }

  let bulkLimit = 50;
  let bulkSelection = new Set(),
    bulkAlbum = null,
    bulkQuery = "",
    bulkAlbumFilter = "",
    bulkArtistFilter = "",
    bulkSourceFilter = "",
    bulkSelectedOnly = false;
  let importTags = new Set();
  function bulkMatches() {
    const terms = normal(bulkQuery).split(/\s+/).filter(Boolean);
    return songs.filter(
      (s) =>
        terms.every((q) =>
          normal(
            [s.title, s.artist, s.album, s.tag_names, "#" + s.id].join(" "),
          ).includes(q),
        ) &&
        (!bulkAlbumFilter || s.album_id === Number(bulkAlbumFilter)) &&
        (!bulkArtistFilter ||
          s.artist_ids.includes(Number(bulkArtistFilter))) &&
        (!bulkSourceFilter ||
          window.DevCatalog?.sourceText(s.id) ===
            (bulkSourceFilter === "missing" ? "Needs link" : "Linked")) &&
        (!bulkSelectedOnly || bulkSelection.has(s.id)),
    );
  }
  function renderBulk() {
    $("#dev-main").innerHTML =
      devTitle("Bulk edits") +
      `<section class="panel bulk-workbench"><div class="search-form"><input id="bulk-query" type="search" value="${esc(bulkQuery)}" placeholder="Find songs by title, artist, album or tag…" aria-label="Find songs for bulk editing"></div><div class="bulk-facets">${[
        ["album", albums, bulkAlbumFilter],
        ["artist", artists, bulkArtistFilter],
      ]
        .map(
          ([key, rows, value]) =>
            `<label>${key[0].toUpperCase() + key.slice(1)}<select id="bulk-filter-${key}"><option value="">All ${key}s</option>${[
              ...rows,
            ]
              .sort((a, b) => a.name.localeCompare(b.name))
              .map(
                (r) =>
                  `<option value="${r.id}" ${String(r.id) === value ? "selected" : ""}>${esc(r.name)} (${r.song_count})</option>`,
              )
              .join("")}</select></label>`,
        )
        .join(
          "",
        )}<label>Apple source<select id="bulk-filter-source"><option value="">All sources</option><option value="missing" ${bulkSourceFilter === "missing" ? "selected" : ""}>Needs link</option><option value="linked" ${bulkSourceFilter === "linked" ? "selected" : ""}>Linked · check versions</option></select></label><label class="checkbox-label"><input type="checkbox" id="bulk-selected-only" ${bulkSelectedOnly ? "checked" : ""}>Selected only</label></div><div class="dev-selection-bar"><div><button type="button" class="btn small" data-bulk-all>Select matches (up to 500)</button> <button type="button" class="btn small" data-bulk-clear>Clear selection</button></div><strong id="bulk-count" class="song"></strong></div><div id="bulk-rows" class="bulk-selection"></div></section><section class="panel spaced-panel bulk-workbench"><div class="field"><label for="bulk-action">Action</label><select id="bulk-action"><option value="review_sources">Review Apple sources</option><option value="move_album">Move to album</option></select></div><div id="bulk-actions" class="bulk-actions"></div><button class="btn primary" type="button" data-bulk-apply>Apply to selected songs</button><p id="bulk-error" class="error" hidden role="alert"></p></section>`;
    renderBulkRows();
    renderBulkActions();
    window.DevCatalog?.ensureSources().catch(() => {});
  }
  function renderBulkRows() {
    const rows = bulkMatches();
    $("#bulk-count").textContent =
      bulkSelection.size + " selected · " + rows.length + " matching";
    $("#bulk-rows").innerHTML =
      rows
        .slice(0, bulkLimit)
        .map(
          (s) =>
            `<label class="bulk-row"><input type="checkbox" data-bulk-song="${s.id}" ${bulkSelection.has(s.id) ? "checked" : ""}>${compactArt(s)}<span class="compact-copy"><strong>${esc(s.title)}</strong><small>${esc(s.artist)} · ${esc(s.album)} · ${window.SongRankerUI.trackPosition(s, true)}</small><small>${esc(window.DevCatalog?.sourceText(s.id) || "Loading…")} · ${esc(window.DevCatalog?.contentText(s.id) || "Not explicit")}</small></span><small>#${s.id}</small></label>`,
        )
        .join("") || '<div class="empty">No matching songs</div>';
    if (rows.length > bulkLimit)
      $("#bulk-rows").insertAdjacentHTML(
        "beforeend",
        '<button class="btn" type="button" data-bulk-more>Show 50 more songs</button>',
      );
    const shown = new Set(rows.map((r) => r.id));
    $("#bulk-count").textContent =
      bulkSelection.size +
      " selected · " +
      rows.length +
      " matching · " +
      [...bulkSelection].filter((id) => !shown.has(id)).length +
      " selected outside filters";
    const apply = $("[data-bulk-apply]");
    if (apply) apply.disabled = !bulkSelection.size;
  }
  function renderBulkActions() {
    const move = $("#bulk-action").value === "move_album";
    const apply = $("[data-bulk-apply]");
    if (apply)
      apply.textContent = move ? "Apply album move" : "Review selected sources";
    $("#bulk-actions").innerHTML = move
      ? `<div class="search-form"><input id="bulk-album-query" type="search" placeholder="Find destination album…" aria-label="Destination album search"></div><strong id="bulk-album-selected" class="album">${esc(byId(albums, bulkAlbum)?.title || "")}</strong><div class="scope-results" id="bulk-albums"></div><div class="field"><label for="bulk-disc">Destination disc (blank keeps current discs)</label><input id="bulk-disc" type="number" min="1" step="1" placeholder="Keep current discs"></div><p class="catalog-note">To combine split discs, select one disc’s tracks, choose the album to keep and enter its disc number. Track numbers and destination artwork stay intact.</p><label><input type="checkbox" id="bulk-clear-tracks">Clear selected track numbers</label>`
      : `<div class="field"><label for="bulk-source-release">Apple album, EP or Single link (optional)</label><input id="bulk-source-release" type="url" maxlength="2000" placeholder="Use one release for this group…"></div><p class="catalog-note">Choose a recording for each song, skip uncertain ones, then save the reviewed group. Names, previews, tags and album placement stay as they are.</p>`;
    if (move) renderBulkAlbums();
  }
  function renderBulkAlbums() {
    const q = normal($("#bulk-album-query").value);
    const found = albums.filter((a) =>
      normal(a.title + " " + a.artist + " #" + a.id).includes(q),
    );
    $("#bulk-albums").innerHTML =
      found
        .slice(0, 30)
        .map(
          (a) =>
            `<button class="scope-option ${a.id === bulkAlbum ? "selected" : ""}" aria-pressed="${a.id === bulkAlbum}" data-bulk-album="${a.id}" type="button">${compactArt(a)}<strong class="album">${esc(a.title)}</strong><small>${a.song_count} songs · ${esc(a.artist)}<br>Tracks: ${esc(
              linkedSongs("albums", a)
                .sort(trackOrder)
                .map((t) => window.SongRankerUI.trackPosition(t, true))
                .join(", "),
            )}</small></button>`,
        )
        .join("") ||
      '<div class="empty">No matching albums. Refine the search.</div>';
    if (found.length > 30)
      $("#bulk-albums").insertAdjacentHTML(
        "beforeend",
        '<p class="muted">Showing 30 of ' +
          found.length +
          " albums. Search by name, artist or #ID to narrow the list.</p>",
      );
  }
  async function applyBulk() {
    if ($("#bulk-action").value === "review_sources") {
      await window.DevCatalog?.startSourceBatch(
        [...bulkSelection],
        $("#bulk-source-release")?.value.trim() || "",
      );
      return;
    }
    const button = $("[data-bulk-apply]"),
      err = $("#bulk-error");
    button.disabled = true;
    err.hidden = true;
    try {
      const result = await api("/api/dev/bulk_songs", {
        song_ids: [...bulkSelection],
        action: "move_album",
        album_id: bulkAlbum,
        clear_track_numbers: !!$("#bulk-clear-tracks")?.checked,
        disc_number: $("#bulk-disc")?.value || null,
      });
      await refreshData();
      renderBulkRows();
      toast(result.message);
    } catch (e) {
      err.hidden = false;
      err.textContent = e.message;
    } finally {
      button.disabled = false;
    }
  }

  const SONG_TAG_LIMIT = 8;
  const tagIdentity = window.SongRankerUI.identityText;
  const pickedTagNames = (value) => [
    ...new Set(
      String(value || "")
        .split(",")
        .map(tagIdentity)
        .filter(Boolean),
    ),
  ];
  function tagPicker(context) {
    return `<details class="tag-picker ${context === "edit" ? "tag-info-field" : ""}" ${context === "edit" ? "open" : ""}><summary>${context === "import" ? "Extra tags for new songs" : "Choose existing tags"}</summary><input type="search" data-tag-query="${context}" placeholder="Find a tag by name or info…" aria-label="Find ${context} tags"><p id="tag-limit-${context}" role="status" aria-live="polite"></p><div class="tag-picker-list" id="tag-picks-${context}"></div></details>`;
  }
  function renderTagPicker(context) {
    const root = $("#tag-picks-" + context);
    if (!root) return;
    const q = normal($(`[data-tag-query="${context}"]`).value),
      chosen =
        context === "import"
          ? tags
              .filter((t) => importTags.has(t.id))
              .map((t) => tagIdentity(t.name))
          : pickedTagNames($("#field-tags")?.value);
    const status = $("#tag-limit-" + context);
    if (status)
      status.textContent = `${chosen.length} / 8 tags${chosen.length > SONG_TAG_LIMIT ? " · Remove tags before saving" : ""}`;
    if (context === "edit")
      $("#field-tags")?.setCustomValidity(
        chosen.length > SONG_TAG_LIMIT ? "A song can have at most 8 tags." : "",
      );
    root.innerHTML =
      tags
        .filter((t) => normal(t.name + " " + (t.description || "")).includes(q))
        .sort(
          (a, b) =>
            chosen.includes(tagIdentity(b.name)) -
              chosen.includes(tagIdentity(a.name)) ||
            a.name.localeCompare(b.name),
        )
        .map(
          (t) =>
            `<label class="tag-choice"><input type="checkbox" data-pick-tag="${t.id}" data-pick-context="${context}" ${chosen.includes(tagIdentity(t.name)) ? "checked" : chosen.length >= SONG_TAG_LIMIT ? "disabled" : ""}><span><b class="tag">${esc(t.name)}</b>${t.description ? `<small>${esc(t.description)}</small>` : ""}</span><small>${t.song_count}</small></label>`,
        )
        .join("") || '<div class="empty">No matching tags</div>';
  }
  $$("time[data-timestamp]").forEach((el) => {
    const seconds = Number(el.dataset.timestamp);
    if (!seconds) return;
    const date = new Date(seconds * 1000);
    if (!Number.isFinite(date.getTime())) return;
    el.dateTime = date.toISOString();
    el.textContent = date.toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
    el.title = date.toLocaleString();
  });
  window.DevSelection?.bindUI({
    api,
    title: devTitle,
    root: () => $("#dev-main"),
    toast,
  });
  window.DevVibe?.bindUI({
    api,
    title: devTitle,
    root: () => $("#dev-main"),
    toast,
  });
  window.DevRecords?.bindUI({
    title: devTitle,
    root: () => $("#dev-main"),
    records,
    data: () => DB,
    matchRow,
    clipped,
  });
  window.DevMetadata?.bindUI({
    api,
    title: devTitle,
    root: () => $("#dev-main"),
    toast,
    refresh: refreshData,
  });
  window.AppStop?.bindUI({
    api,
    openDialog: (...args) => {
      editTarget = null;
      toolTarget = null;
      openDialog(...args);
    },
  });
  window.DevDatabase?.bindUI({ api, openDialog });
  window.DevSystem?.bindUI({
    api,
    records,
    title: devTitle,
    openDialog: (...args) => {
      editTarget = null;
      toolTarget = null;
      openDialog(...args);
    },
    root: () => $("#dev-main"),
    toast,
    navigate: navigateDev,
    showMissingSources: () => {
      activateTable("songs");
      tableQuery = "";
      tableFilters = {};
      tablePage = 0;
      missingAppleOnly = true;
      rememberTable();
      navigateDev("songs");
    },
    afterRestore: async () => {
      await refreshData();
      window.DevTags?.resetAfterRestore();
      bulkSelection.clear();
      window.DevCatalog?.resetSourceBatch();
      await window.DevCatalog?.ensureSources(true);
    },
  });
  window.DevTags?.bindUI({
    api,
    records,
    artwork,
    title: devTitle,
    root: () => $("#dev-main"),
    toast,
    refresh: refreshData,
    navigate: () => {
      if (devView === "tag_workbench") renderDevView();
      else navigateDev("tag_workbench");
    },
  });
  window.DevCatalog?.bindUI({
    moveAlbum: (id) => navigateDev("bulk", true, () => {
      bulkAlbumFilter = String(id);
      bulkArtistFilter = "";
      bulkSourceFilter = "";
      bulkQuery = "";
      bulkSelectedOnly = false;
      bulkSelection = new Set(songs.filter((s) => s.album_id === id).slice(0, 500).map((s) => s.id));
      bulkAlbum = null;
      renderBulk();
      $("#bulk-action").value = "move_album";
      renderBulkActions();
    }),
    api,
    records,
    artwork,
    title: devTitle,
    root: () => $("#dev-main"),
    toast,
    refresh: async () => {
      await refreshData();
      renderDevView();
    },
    openDialog: (...args) => {
      editTarget = null;
      toolTarget = null;
      openDialog(...args);
    },
    tagPicker: () => tagPicker("import"),
    renderTagPicker: () => renderTagPicker("import"),
    selectedTags: () =>
      tags.filter((t) => importTags.has(t.id)).map((t) => t.name),
    sourcesChanged: () => {
      if ($("#manage-rows") && devView === "songs") renderTableBody("songs");
      if ($("#apple-results")) window.DevCatalog.renderResults();
      if ($("#bulk-rows")) renderBulkRows();
    },
  });
  window.SpecialModes?.bindUI({
    rankingMetadata,
    main,
    api,
    stat,
    artwork,
    compactArt,
    records,
    properAlbum,
    colour,
    urlFor,
    rankGlow,
    animateScore,
    attachPlayers,
    mediaButton,
    toast,
    stopAudio,
    refreshData,
    pageTone,
    holdHeight: holdGameHeight,
    cancelTransition: cancelRoundTransition,
    data: () => DB,
    homeBannerLimit: HOME_BANNER_LIMIT,
    homeRateBar,
  });
  window.VibeLibrary?.bindUI({
    main,
    records,
    artwork,
    rankingMetadata,
    properAlbum,
    urlFor,
    rankGlow,
    colour,
    pageTone,
    attachAutoScroll,
  });
  window.Overall?.bindUI({
    rankingMetadata,
    properAlbum,
    main,
    api,
    records,
    colour,
    urlFor,
    artwork,
    rankGlow,
    pageTone,
    toast,
    data: () => DB,
    profile: () => profileState,
  });
  window.ProfileUI?.bindUI({
    stat,
    available,
    aggregateVotes,
    urlFor,
    historyRow: matchRow,
    data: () => DB,
  });
  volumeApply(volume);
  attachPlayers();
  if (page === "guesser") await window.SpecialModes.loadGuess();
  if (page === "shelves") await window.SpecialModes.loadShelf();
  if (page === "mode_rankings_vibe") window.VibeLibrary?.mountRankings();
  else if (page.startsWith("mode_rankings_"))
    window.SpecialModes.renderModeRanking(
      page.replace("mode_rankings_", ""),
      true,
    );
  if (page === "overall_rankings") await window.Overall.renderRankings(true);
  if (page === "home") renderHome();
  if (page === "song") renderSong();
  if (page === "standard") {
    try {
      gameMode =
        new URLSearchParams(location.search).get("mode") ||
        localStorage.getItem("votingMode") ||
        "standard";
    } catch {}
    if (!["standard", "blind"].includes(gameMode)) gameMode = "standard";
    blind = gameMode === "blind";
    await nextMatch();
  }
  if (page.startsWith("rankings_"))
    renderRanking(page.replace("rankings_", ""));
  if (page === "search")
    window.SearchPage.init({
      main,
      records,
      related,
      linkedSongs,
      rankingMetadata,
      properAlbum,
      colour,
      urlFor,
      artwork,
      pageTone,
    });
  if (page === "dev") renderDev();
  if (["album", "artist", "tag"].includes(page)) renderProfile();
  if (page === "tournament_play") await renderTournamentSetup();

  if (["song", "artist", "album", "tag"].includes(page))
    window.VibeProfiles?.mount({
      kind: page,
      id: page === "song" ? songId : profileState.item.id,
    });
  if (["home", "song", "artist", "album", "tag", "global_stats"].includes(page))
    await window.Overall.mount(page);
  if (page === "home" || page === "global_stats")
    window.VibeLibrary?.mount(page);
})().catch((error) => {
  const node = document.getElementById("loading");
  if (node) {
    node.textContent = error.message;
    node.classList.add("error");
  } else console.error(error);
});
