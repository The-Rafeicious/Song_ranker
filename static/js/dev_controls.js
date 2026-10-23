/* Shared developer controls. Native selects remain the form/state owner. */
window.DevControls = (() => {
  "use strict";
  if (document.body.dataset.page !== "dev") return {};
  const { esc } = window.SongRankerUI,
    widgets = new WeakMap();
  const navOpen = new WeakMap();
  const entityIds = new Set([
    "tag-artist",
    "tag-album",
    "tag-filter",
    "bulk-filter-artist",
    "bulk-filter-album",
  ]);
  const norm = window.SongRankerUI.searchText;
  let active = null,
    serial = 0,
    scheduled = false,
    disposed = false;
  function close(focus = false) {
    if (!active) return;
    const w = active;
    active = null;
    w.popup.remove();
    w.trigger.setAttribute("aria-expanded", "false");
    w.trigger.removeAttribute("aria-controls");
    if (focus && w.trigger.isConnected) w.trigger.focus();
  }
  function position() {
    if (!active) return;
    const w = active,
      r = w.trigger.getBoundingClientRect();
    if (!w.select.isConnected || w.select.disabled) {
      close();
      return;
    }
    const width = Math.min(Math.max(r.width, 300), window.innerWidth - 24),
      below = window.innerHeight - r.bottom - 12,
      above = r.top - 12;
    const up = below < 260 && above > below,
      height = Math.min(420, Math.max(100, up ? above : below));
    Object.assign(w.popup.style, {
      width: width + "px",
      maxHeight: height + "px",
      left:
        Math.max(12, Math.min(r.left, window.innerWidth - width - 12)) + "px",
      top:
        (up
          ? Math.max(12, r.top - Math.min(w.popup.scrollHeight, height) - 6)
          : r.bottom + 6) + "px",
    });
  }
  function mark(w, index) {
    const rows = [...w.list.querySelectorAll("[role=option]")];
    w.index = Math.max(0, Math.min(index, rows.length - 1));
    rows.forEach((b, i) =>
      b.classList.toggle("dev-option-active", i === w.index),
    );
    const row = rows[w.index];
    if (row) {
      w.input.setAttribute("aria-activedescendant", row.id);
      row.scrollIntoView?.({ block: "nearest" });
    } else w.input.removeAttribute("aria-activedescendant");
  }
  function results(w) {
    const terms = norm(w.input.value).split(/\s+/).filter(Boolean);
    w.found = [...w.select.options].filter(
      (o) =>
        !o.disabled &&
        !o.hidden &&
        terms.every((t) => norm(o.textContent).includes(t)),
    );
    w.list.innerHTML =
      w.found
        .map(
          (o, i) =>
            `<button type="button" role="option" tabindex="-1" id="dev-option-${serial}-${i}" aria-selected="${o.selected}" data-option="${i}"><span>${esc(o.textContent)}</span>${o.selected ? '<span aria-hidden="true">✓</span>' : ""}</button>`,
        )
        .join("") || '<p class="empty">No matches. Try another name.</p>';
    w.count.textContent = w.found.length + " matching options";
    mark(
      w,
      Math.max(
        0,
        w.found.findIndex((o) => o.selected),
      ),
    );
    position();
  }
  function choose(w, index) {
    const o = w.found[index];
    if (!o || w.select.disabled) return;
    const changed = w.select.value !== o.value;
    w.select.value = o.value;
    close(true);
    syncOne(w);
    if (changed) {
      w.select.dispatchEvent(new Event("input", { bubbles: true }));
      w.select.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  function open(w) {
    if (w.select.disabled) return;
    if (active === w) {
      close(true);
      return;
    }
    close();
    active = w;
    ++serial;
    const p = document.createElement("div");
    p.id = "dev-picker-popup";
    p.className = "dev-picker-popup";
    p.setAttribute("role", "dialog");
    p.setAttribute("aria-label", "Choose " + w.label);
    p.innerHTML = `<input type="search" role="combobox" autocomplete="off" aria-label="Find ${esc(w.label)}" aria-expanded="true" aria-controls="dev-picker-options" placeholder="Type to find…"><div id="dev-picker-options" class="dev-picker-options" role="listbox" aria-label="${esc(w.label)}"></div><div class="dev-picker-footer"><small role="status" aria-live="polite"></small><button type="button" data-picker-close>Close</button></div>`;
    (w.select.closest("dialog") || document.body).append(p);
    Object.assign(w, {
      popup: p,
      input: p.querySelector("input"),
      list: p.querySelector("[role=listbox]"),
      count: p.querySelector("small"),
      index: 0,
    });
    w.trigger.setAttribute("aria-expanded", "true");
    w.trigger.setAttribute("aria-controls", "dev-picker-popup");
    results(w);
    w.input.focus();
    w.input.addEventListener("input", () => results(w));
    w.input.addEventListener("keydown", (e) => {
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
        e.preventDefault();
        mark(
          w,
          e.key === "Home"
            ? 0
            : e.key === "End"
              ? w.found.length - 1
              : w.index + (e.key === "ArrowDown" ? 1 : -1),
        );
      }
      if (e.key === "Enter") {
        e.preventDefault();
        choose(w, w.index);
      }
    });
    p.addEventListener("click", (e) => {
      const b = e.target.closest("[data-option]");
      if (b) choose(w, Number(b.dataset.option));
      if (e.target.closest("[data-picker-close]")) close(true);
    });
  }
  function syncOne(w) {
    const text =
      w.select.options[w.select.selectedIndex]?.textContent || "Choose…";
    if (w.copy.textContent !== text) w.copy.textContent = text;
    w.trigger.title = text;
    w.trigger.setAttribute("aria-label", w.label + ": " + text);
    if (w.trigger.disabled !== w.select.disabled)
      w.trigger.disabled = w.select.disabled;
    if (active === w && w.select.disabled) close();
  }
  function enhance(s) {
    if (widgets.has(s)) {
      syncOne(widgets.get(s));
      return;
    }
    if (
      s.multiple ||
      s.hidden ||
      (!entityIds.has(s.id) && !s.hasAttribute("data-searchable"))
    )
      return;
    const labelNode = s.labels?.[0]?.cloneNode(true);
    labelNode
      ?.querySelectorAll("select,.dev-select")
      .forEach((n) => n.remove());
    const label = (
      labelNode?.textContent ||
      s.getAttribute("aria-label") ||
      "option"
    )
      .trim()
      .replace(/\s+/g, " ");
    const wrap = document.createElement("span");
    wrap.className = "dev-select";
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "dev-select-trigger";
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-expanded", "false");
    trigger.innerHTML = '<span></span><span aria-hidden="true">⌄</span>';
    s.after(wrap);
    wrap.append(trigger);
    s.hidden = true;
    const w = { select: s, trigger, copy: trigger.firstElementChild, label };
    widgets.set(s, w);
    syncOne(w);
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      open(w);
    });
    trigger.addEventListener("keydown", (e) => {
      if (["ArrowDown", "ArrowUp"].includes(e.key)) {
        e.preventDefault();
        open(w);
      }
    });
    s.addEventListener("change", () => {
      syncOne(w);
      if (active === w) results(w);
    });
    // The native select is hidden; its visible label must focus the replacement.
    for (const label of s.labels || [])
      label.addEventListener("click", (e) => {
        if (e.target === label) {
          e.preventDefault();
          trigger.focus();
        }
      });
  }
  function sync() {
    if (disposed) return;
    document
      .querySelectorAll("#dev-main select,#editor select")
      .forEach(enhance);
    if (active && !active.select.isConnected) close();
  }
  const observer = new MutationObserver((records) => {
    if (
      !scheduled &&
      records.some(
        (r) =>
          r.type === "childList" ||
          ["SELECT", "OPTION", "OPTGROUP"].includes(r.target.tagName),
      )
    ) {
      scheduled = true;
      queueMicrotask(() => {
        scheduled = false;
        sync();
      });
    }
  });
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["disabled", "selected", "label"],
  });
  document.addEventListener("input", (e) => {
    if (e.target.id !== "dev-tool-query") return;
    const q = norm(e.target.value);
    for (const group of document.querySelectorAll(".dev-nav-group")) {
      if (q && !navOpen.has(group)) navOpen.set(group, group.open);
      const buttons = [...group.querySelectorAll("[data-dev]")];
      for (const b of buttons)
        b.hidden = !!q && !norm(b.textContent).includes(q);
      group.hidden = buttons.every((b) => b.hidden);
      if (q && !group.hidden) group.open = true;
      else if (!q && navOpen.has(group)) {
        group.open = navOpen.get(group);
        navOpen.delete(group);
      }
    }
  });
  document.addEventListener("reset", () =>
    queueMicrotask(() => {
      sync();
      if (active) results(active);
    }),
  );
  document.addEventListener("pointerdown", (e) => {
    if (
      active &&
      !active.popup.contains(e.target) &&
      !active.trigger.contains(e.target)
    )
      close();
  });
  document.addEventListener("focusin", (e) => {
    if (
      active &&
      !active.popup.contains(e.target) &&
      !active.trigger.contains(e.target)
    )
      close();
  });
  document.addEventListener(
    "keydown",
    (e) => {
      if (active && e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        close(true);
      }
    },
    true,
  );
  document.addEventListener("close", () => close(), true);
  window.addEventListener("resize", position);
  window.addEventListener(
    "scroll",
    (e) => {
      if (active && !active.popup.contains(e.target)) position();
    },
    true,
  );
  function dispose() {
    disposed = true;
    observer.disconnect();
    close();
  }
  window.addEventListener("pagehide", (e) => {
    if (!e.persisted) dispose();
  });
  sync();
  return { sync, close, dispose };
})();
