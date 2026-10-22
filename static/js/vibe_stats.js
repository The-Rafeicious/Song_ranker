/* Heatmap exploration and a read-only compact song inspector. */
(() => {
  "use strict";
  if (document.body.dataset.page !== "vibe_stats") return;
  const inspector = document.querySelector("#vibe-song-inspector"),
    content = inspector?.querySelector("[data-vibe-inspector-content]");
  let sequence = 0,
    controller = null,
    selectedId = null;
  function message(text, retry = false) {
    const p = document.createElement("p");
    p.className = "empty";
    p.setAttribute("role", retry ? "alert" : "status");
    p.textContent = text;
    content.replaceChildren(p);
    if (retry) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn vibe";
      button.dataset.vibeRetry = "";
      button.textContent = "Retry song vibe";
      content.append(button);
    }
  }
  async function inspect(songId) {
    if (!inspector || !/^\d+$/.test(String(songId))) return;
    selectedId = String(songId);
    const ticket = ++sequence;
    controller?.abort();
    const request = new AbortController();
    controller = request;
    const timeout = setTimeout(() => request.abort(), 15000);
    inspector.setAttribute("aria-busy", "true");
    message("Loading song vibe…");
    for (const point of document.querySelectorAll("[data-vibe-point]"))
      point.classList.toggle(
        "is-selected",
        point.dataset.songId === selectedId,
      );
    inspector.scrollIntoView({
      block: "start",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
    document
      .querySelector("#vibe-inspector-title")
      .focus({ preventScroll: true });
    try {
      const response = await fetch("/api/vibe-map/inspect/" + songId, {
        cache: "no-store",
        signal: request.signal,
      });
      if (!response.ok)
        throw Error(
          response.status === 404
            ? "This song is no longer in the library."
            : "Song vibe could not load.",
        );
      const data = await response.json();
      if (ticket !== sequence) return;
      // The HTML fragment is rendered by our same-origin, autoescaped Jinja component.
      content.innerHTML = data.html;
      content.querySelector("[data-vibe-song-radar]").innerHTML =
        window.VibeCharts.radar(
          data.profile.radar,
          data.song.title + " · average vibe",
          true,
        );
    } catch (error) {
      if (ticket === sequence)
        message(
          error.name === "AbortError"
            ? "Song vibe timed out."
            : error.message || "Song vibe could not load.",
          true,
        );
    } finally {
      clearTimeout(timeout);
      if (ticket === sequence) {
        inspector.setAttribute("aria-busy", "false");
        controller = null;
      }
    }
  }
  content?.addEventListener("click", (event) => {
    if (event.target.closest("[data-vibe-retry]")) void inspect(selectedId);
  });
  window.addEventListener("pagehide", () => {
    sequence++;
    controller?.abort();
    controller = null;
    if (inspector?.getAttribute("aria-busy") === "true") {
      inspector.setAttribute("aria-busy", "false");
      message("Select a map point.");
    }
  });
  for (const chart of document.querySelectorAll("[data-vibe-chart]")) {
    const svg = chart.querySelector("svg"),
      points = [...chart.querySelectorAll("[data-vibe-point]")],
      caption = chart.querySelector(".vibe-chart-selection");
    const original = caption.textContent;
    let index = -1;
    function show(point) {
      if (!point) return;
      index = points.indexOf(point);
      const link = document.createElement("a");
      link.href = "/song/" + point.dataset.songId;
      link.textContent = point.dataset.songTitle;
      caption.replaceChildren(
        link,
        document.createTextNode(" · " + point.dataset.songArtist),
      );
      caption.title =
        point.dataset.songTitle + " · " + point.dataset.songArtist;
    }
    chart.addEventListener("pointerover", (event) =>
      show(event.target.closest("[data-vibe-point]")),
    );
    chart.addEventListener("focusin", (event) =>
      show(event.target.closest("[data-vibe-point]")),
    );
    chart.addEventListener("pointerleave", () => {
      if (!svg.contains(document.activeElement)) {
        caption.textContent = original;
        caption.removeAttribute("title");
      }
    });
    chart.addEventListener("click", (event) => {
      const point = event.target.closest("[data-vibe-point]");
      if (!point) return;
      event.preventDefault();
      show(point);
      void inspect(point.dataset.songId);
    });
    svg.addEventListener("keydown", (event) => {
      if (!points.length) return;
      const directions = {
        ArrowRight: 1,
        ArrowDown: 1,
        ArrowLeft: -1,
        ArrowUp: -1,
      };
      if (event.key in directions) {
        event.preventDefault();
        index =
          index < 0
            ? directions[event.key] > 0
              ? 0
              : points.length - 1
            : (index + directions[event.key] + points.length) % points.length;
        points[index].focus();
        show(points[index]);
      } else if (event.key === "Home" || event.key === "End") {
        event.preventDefault();
        index = event.key === "Home" ? 0 : points.length - 1;
        points[index].focus();
        show(points[index]);
      } else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const point =
          event.target.closest("[data-vibe-point]") ||
          points[index < 0 ? 0 : index];
        show(point);
        void inspect(point.dataset.songId);
      }
    });
  }
})();
