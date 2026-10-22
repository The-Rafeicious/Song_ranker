/* Vibe averages are edited explicitly; never modify preference scores here. */
window.DevVibe = (() => {
  "use strict";
  const { esc } = window.SongRankerUI;
  let U,
    active = false,
    ticket = 0,
    editTicket = 0,
    current = null,
    offset = 0,
    query = "",
    busy = false;
  const root = () => U.root(),
    error = (e) => {
      const node = root()?.querySelector("[data-vibe-dev-error]");
      if (node) {
        node.hidden = false;
        node.textContent = e.message || String(e);
      }
    };
  function viewChanged(view) {
    if (view !== "vibe_records") {
      active = false;
      ++ticket;
      ++editTicket;
      current = null;
    }
  }
  function render() {
    ++editTicket;
    active = true;
    offset = 0;
    query = "";
    current = null;
    root().innerHTML =
      U.title("Vibe Map") +
      `<p class="error" role="alert" data-vibe-dev-error hidden></p><section class="panel dev-vibe"><form id="dev-vibe-search" class="search-form"><label>Find a song<input name="q" type="search" placeholder="Song, artist, album or ID…"></label><button class="btn" type="submit">Search</button></form><div id="dev-vibe-list" aria-live="polite"></div><div class="dev-pagination"><button class="btn" data-vibe-page="-1">Previous</button><span id="dev-vibe-count"></span><button class="btn" data-vibe-page="1">Next</button></div></section><section id="dev-vibe-editor" class="panel dev-vibe" hidden></section><section class="panel dev-vibe"><h3 class="vibe">Reset Vibe Map</h3><form id="dev-vibe-reset"><label>Type RESET VIBE<input name="confirmation" required autocomplete="off"></label><button class="btn danger" type="submit">Clear all Vibe data</button></form></section>`;
    void list();
  }
  async function list() {
    const own = ++ticket;
    try {
      const data = await U.api(
        "/api/dev/vibe?q=" + encodeURIComponent(query) + "&offset=" + offset,
      );
      if (!active || own !== ticket || !root()) return;
      root().querySelector("#dev-vibe-list").innerHTML =
        data.items
          .map(
            (s) =>
              `<div class="health-row"><div class="dev-vibe-identity"><a class="song" href="/song/${s.id}" title="${esc(s.title)}">${esc(s.title)}</a><small class="album">${esc(s.album || "No album")}</small><small>${s.placed} / 4 maps · ${s.completed_passes} passes</small></div><button class="btn" data-vibe-edit="${s.id}">Edit</button></div>`,
          )
          .join("") || '<p class="empty">No matching songs.</p>';
      root().querySelector("#dev-vibe-count").textContent =
        data.total +
        " songs · " +
        (data.total ? offset + 1 : 0) +
        "–" +
        Math.min(data.total, offset + 30);
      root().querySelector('[data-vibe-page="-1"]').disabled = offset === 0;
      root().querySelector('[data-vibe-page="1"]').disabled =
        offset + 30 >= data.total;
    } catch (e) {
      if (active && own === ticket) error(e);
    }
  }
  const input = (name, label, value, min, max, step = "1") =>
    `<label>${esc(label)}<input name="${name}" type="number" min="${min}" max="${max}" step="${step}" value="${value}" required></label>`;
  function editor(data) {
    current = data;
    const node = root().querySelector("#dev-vibe-editor");
    node.hidden = false;
    node.innerHTML = `<h3 class="song">${esc(data.song.title)}</h3><p>${data.active_rounds} active rounds will be cleared when saved.</p><form id="dev-vibe-save"><div class="dev-vibe-maps">${data.maps
      .map(
        (m) =>
          `<fieldset data-vibe-map="${m.id}"><legend class="vibe">${esc(m.title)}</legend><label>Selection<select name="${m.id}:status">${[
            ["placed", "Placed"],
            ["unmapped", "Unplaced"],
            ["not_applicable", "Skipped"],
          ]
            .map(
              ([key, label]) =>
                `<option value="${key}" ${m.status === key ? "selected" : ""}>${label}</option>`,
            )
            .join(
              "",
            )}</select></label>${input(m.id + ":x", m.x_low + " ↔ " + m.x_high, m.x == null ? 0 : Number((m.x * 5).toFixed(2)), -5, 5, ".01")}${input(m.id + ":y", m.y_low + " ↔ " + m.y_high, m.y == null ? 0 : Number((m.y * 5).toFixed(2)), -5, 5, ".01")}${input(m.id + ":sample_count", "Placed samples", m.sample_count, 0, 1000000)}${input(m.id + ":not_applicable_count", "Skipped samples", m.not_applicable_count, 0, 1000000)}<button class="btn danger" type="button" data-vibe-clear-map="${m.id}">Clear map</button></fieldset>`,
      )
      .join(
        "",
      )}</div>${input("completed_passes", "Completed passes", data.completed_passes, 0, 1000000)}<button class="btn vibe" type="submit">Save Vibe data</button></form><form id="dev-vibe-delete"><label>Type DELETE VIBE<input name="confirmation" required autocomplete="off"></label><button class="btn danger" type="submit">Delete this song’s Vibe data</button></form>`;
  }
  async function edit(id) {
    const own = ++editTicket;
    try {
      const data = await U.api("/api/dev/vibe/" + id);
      if (active && own === editTicket && root()) editor(data);
    } catch (e) {
      if (active && own === editTicket) error(e);
    }
  }
  async function mutate(form) {
    if (busy || !active) return;
    busy = true;
    root().querySelector("[data-vibe-dev-error]").hidden = true;
    const data = new FormData(form),
      own = editTicket;
    let url,
      body,
      method = "POST";
    if (form.id === "dev-vibe-reset") {
      url = "/api/dev/reset-history/vibe";
      body = { confirmation: data.get("confirmation") };
    } else if (!current) {
      busy = false;
      return;
    } else {
      url = "/api/dev/vibe/" + current.song.id;
      body = { version: current.version };
      if (form.id === "dev-vibe-delete") {
        method = "DELETE";
        body.confirmation = data.get("confirmation");
      } else {
        body.completed_passes = Number(data.get("completed_passes"));
        body.maps = Object.fromEntries(
          current.maps.map((m) => [
            m.id,
            {
              status: data.get(m.id + ":status"),
              x: Number(data.get(m.id + ":x")),
              y: Number(data.get(m.id + ":y")),
              sample_count: Number(data.get(m.id + ":sample_count")),
              not_applicable_count: Number(
                data.get(m.id + ":not_applicable_count"),
              ),
            },
          ]),
        );
      }
    }
    const controls = [...root().querySelectorAll("button,input,select")];
    const disabled = controls.map((c) => c.disabled);
    controls.forEach((c) => (c.disabled = true));
    try {
      const result = await U.api(url, body, method);
      if (!active || own !== editTicket) return;
      U.toast(result.message);
      if (form.id === "dev-vibe-reset") {
        current = null;
        root().querySelector("#dev-vibe-editor").hidden = true;
        form.reset();
      } else editor(result);
      await list();
    } catch (e) {
      if (active && own === editTicket) error(e);
    } finally {
      controls.forEach((c, i) => {
        if (c.isConnected) c.disabled = disabled[i];
      });
      busy = false;
    }
  }
  document.addEventListener("submit", (e) => {
    if (!e.target.id.startsWith("dev-vibe-")) return;
    e.preventDefault();
    if (e.target.id === "dev-vibe-search") {
      query = new FormData(e.target).get("q").trim();
      offset = 0;
      void list();
    } else void mutate(e.target);
  });
  document.addEventListener("change", (e) => {
    if (!active || !e.target.name?.endsWith(":status")) return;
    const form = e.target.closest("#dev-vibe-save");
    if (!form) return;
    const key = e.target.name.split(":")[0],
      state = e.target.value;
    form.elements.namedItem(key + ":sample_count").value =
      state === "placed"
        ? Math.max(
            1,
            Number(form.elements.namedItem(key + ":sample_count").value),
          )
        : 0;
    form.elements.namedItem(key + ":not_applicable_count").value =
      state === "not_applicable"
        ? Math.max(
            1,
            Number(
              form.elements.namedItem(key + ":not_applicable_count").value,
            ),
          )
        : 0;
    if (state === "unmapped")
      form.elements.namedItem("completed_passes").value = 0;
  });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b || !active || busy) return;
    if (b.dataset.vibeEdit) void edit(Number(b.dataset.vibeEdit));
    if (b.dataset.vibePage) {
      offset = Math.max(0, offset + 30 * Number(b.dataset.vibePage));
      void list();
    }
    if (b.dataset.vibeClearMap) {
      const form = root().querySelector("#dev-vibe-save"),
        key = b.dataset.vibeClearMap;
      for (const [field, value] of Object.entries({
        status: "unmapped",
        x: 0,
        y: 0,
        sample_count: 0,
        not_applicable_count: 0,
      }))
        form.elements.namedItem(key + ":" + field).value = value;
      form.elements.namedItem("completed_passes").value = 0;
    }
  });
  window.addEventListener("pagehide", () => viewChanged(""));
  return { bindUI: (ui) => (U = ui), render, edit, viewChanged };
})();
