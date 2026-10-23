/* Dev destinations, visible navigation and the shared inline task workspace. */
window.DevWorkspace = (() => {
  "use strict";
  const { $, esc } = window.SongRankerUI;
  const context = JSON.parse(
    $("#dev-context")?.textContent || '{"areas":[],"pages":[]}',
  );
  const pages = context.pages;
  const areas = context.areas;
  const find = (key) => pages.find((row) => row[0] === key);
  const href = (key) => {
    if (key === "overview") return "/dev/dashboard";
    if (areas.some((row) => row[0] === key)) return "/dev/" + key;
    const row = find(key);
    return row ? `/dev/${row[1]}/${row[2]}` : "/dev/dashboard";
  };
  const link = (key, title, description = "") =>
    `<a href="${href(key)}" data-dev="${key}" class="${description ? "dev-destination" : ""}"><strong>${esc(title)}</strong>${description ? `<span>${esc(description)}</span><span aria-hidden="true">↗</span>` : ""}</a>`;
  let U,
    current = context.view || "overview",
    dirty = false,
    pending = null,
    replay = false,
    guideTicket = 0,
    currentAddress = location.href;
  const modeDirty = () =>
    window.DevTags?.hasUnsavedChanges?.() ||
    window.DevVibe?.hasUnsavedChanges?.();
  function guarded(action) {
    if (window.DevTags?.isBusy?.() || window.DevVibe?.isBusy?.()) {
      U.toast("Wait for the current save or review to finish.");
      return;
    }
    if (!dirty && !modeDirty()) {
      action();
      return;
    }
    pending = action;
    const node = $("#dev-unsaved");
    node.hidden = false;
    node.innerHTML =
      '<strong>You have unsaved changes.</strong><span>Save the current task, or discard its changes before continuing.</span><div><button type="button" class="btn" data-workspace-stay>Keep editing</button><button type="button" class="btn danger" data-workspace-discard>Discard & continue</button></div>';
    node.scrollIntoView?.({ block: "nearest" });
  }
  function sync(view) {
    current = view;
    currentAddress = location.href;
    const area = areas.find((row) => row[0] === view)?.[0] || find(view)?.[1];
    const primary = $("#dev-page-menu");
    if (primary)
      primary.innerHTML =
        link("overview", "Home") +
        areas.map((row) => link(row[0], row[1])).join("");
    const secondary = $("#dev-section-nav");
    if (secondary) {
      secondary.hidden = !area || area === "home" || area === view;
      secondary.innerHTML =
        link(area, areas.find((row) => row[0] === area)?.[1] || "Home") +
        pages
          .filter((row) => row[1] === area)
          .map((row) => link(row[0], row[3]))
          .join("");
    }
    document.querySelectorAll("[data-dev]").forEach((node) => {
      const selected =
        node.dataset.dev === view ||
        (node.closest("#dev-page-menu") && node.dataset.dev === area);
      node.classList.toggle("active", !!selected);
      if (selected) node.setAttribute("aria-current", "page");
      else node.removeAttribute("aria-current");
    });
    document.title =
      (find(view)?.[3] ||
        areas.find((row) => row[0] === view)?.[1] ||
        "Developer home") + " · Dev · Song Ranker";
  }
  function cards(area) {
    return `<div class="dev-destinations">${pages
      .filter((row) => row[1] === area)
      .map((row) => link(row[0], row[3], row[4]))
      .join("")}</div>`;
  }
  function landing(area, title) {
    return (
      U.title(title) +
      `<section class="panel dev-area-intro"><p>${esc(areas.find((row) => row[0] === area)?.[2] || "")}</p>${cards(area)}</section>`
    );
  }
  function closeEditor() {
    $("#editor")?.close();
  }
  function openEditor(dialog) {
    const slot = $("#dev-editor-slot");
    if (!slot) {
      dialog.showModal();
      return;
    }
    slot.append(dialog);
    $("#dev-workspace").classList.add("dev-editor-open");
    dirty = false;
    if (!dialog.open)
      dialog.show ? dialog.show() : dialog.setAttribute("open", "");
    if (window.innerWidth < 1100)
      slot.scrollIntoView?.({ block: "start", behavior: "smooth" });
    $("#editor-title")?.setAttribute("tabindex", "-1");
    $("#editor-title")?.focus({ preventScroll: true });
  }
  function bind(ui) {
    U = ui;
    $("#editor")?.addEventListener("close", () => {
      dirty = false;
      $("#dev-workspace")?.classList.remove("dev-editor-open");
      $("#dev-unsaved").hidden = true;
      pending = null;
    });
    window.addEventListener("popstate", () => {
      const key =
        pages.find((row) => href(row[0]) === location.pathname)?.[0] ||
        areas.find((row) => href(row[0]) === location.pathname)?.[0] ||
        "overview";
      if (
        dirty ||
        modeDirty() ||
        (window.DevSystem && !window.DevSystem.canNavigate()) ||
        window.DevTags?.isBusy?.() ||
        window.DevVibe?.isBusy?.()
      ) {
        history.pushState({}, "", currentAddress);
        guarded(() => U.navigate(key, true));
      } else U.navigate(key, false);
    });
    window.addEventListener("beforeunload", (event) => {
      if (dirty || modeDirty()) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
  }
  function navigate(view, action, push) {
    if (view === current) return;
    guarded(() => {
      if (window.DevSystem && !window.DevSystem.canNavigate()) {
        U.toast("Wait for the restore to finish.");
        return;
      }
      closeEditor();
      const address = new URL(href(view), location.origin);
      if (view === "explorer" && location.search.includes("q="))
        address.searchParams.set(
          "q",
          new URLSearchParams(location.search).get("q"),
        );
      if (push) history.pushState({}, "", address);
      action();
    });
  }
  async function guide(kind = "dev") {
    const address = new URL(location.href);
    address.searchParams.set("guide", kind);
    history.replaceState({}, "", address);
    const ticket = ++guideTicket;
    const root = U.root();
    root.innerHTML =
      U.title("Guides") +
      `<nav class="dev-guide-tabs" aria-label="Guide"><button class="btn ${kind === "dev" ? "active" : ""}" data-dev-guide="dev">Dev guide</button><button class="btn ${kind === "technical" ? "active" : ""}" data-dev-guide="technical">Technical guide</button><a class="btn" href="/api/dev/help/${kind}">Plain text</a></nav><div id="dev-guide-content" role="status">Loading guide…</div>`;
    try {
      const result = await U.api("/api/dev/help/" + kind + "?format=html");
      if (ticket !== guideTicket || current !== "guides") return;
      $("#dev-guide-content").innerHTML =
        `<div class="dev-guide-layout"><nav class="dev-guide-contents" aria-label="Guide contents">${result.toc}</nav><article class="panel dev-guide-article">${result.html}</article></div>`;
      if (location.hash) {
        try {
          document
            .getElementById(decodeURIComponent(location.hash.slice(1)))
            ?.scrollIntoView?.({ block: "start" });
        } catch {}
      }
    } catch (error) {
      if (ticket === guideTicket && current === "guides")
        $("#dev-guide-content").textContent = error.message;
    }
  }
  document.addEventListener("input", (event) => {
    if (event.target.closest("#editor-fields")) dirty = true;
  });
  document.addEventListener("change", (event) => {
    if (event.target.closest("#editor-fields")) dirty = true;
  });
  document.addEventListener(
    "click",
    (event) => {
      if (!U) return;
      const node = event.target.closest("a,button");
      if (!node) return;
      if (node.hasAttribute("data-workspace-stay")) {
        $("#dev-unsaved").hidden = true;
        pending = null;
        return;
      }
      if (node.hasAttribute("data-workspace-discard")) {
        const action = pending;
        pending = null;
        dirty = false;
        window.DevTags?.discardChanges?.();
        window.DevVibe?.discardChanges?.();
        $("#dev-unsaved").hidden = true;
        action?.();
        return;
      }
      if (node.dataset.devGuide) {
        guide(node.dataset.devGuide);
        return;
      }
      if (
        node.dataset.dev &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.shiftKey
      ) {
        event.preventDefault();
        event.stopImmediatePropagation();
        U.navigate(node.dataset.dev, true);
        return;
      }
      if (
        dirty &&
        !replay &&
        (node.id === "editor-close" ||
          node.matches(
            "[data-edit],[data-tool],[data-delete],[data-catalog-source],[data-catalog-single],[data-catalog-album],[data-preview-quality],[data-system-stop],[data-vibe-edit]",
          ))
      ) {
        event.preventDefault();
        event.stopImmediatePropagation();
        guarded(() => {
          dirty = false;
          replay = true;
          node.click();
          replay = false;
        });
      }
    },
    true,
  );
  return {
    sections: [
      ...pages.map((row) => [row[0], "", row[3]]),
      ...areas.map((row) => [row[0], "", row[1]]),
    ],
    initial: current,
    href,
    sync,
    cards,
    landing,
    bind,
    navigate,
    openEditor,
    guide,
  };
})();
