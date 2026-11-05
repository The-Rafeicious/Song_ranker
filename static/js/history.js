/* Shared selectors and a bounded live lookup: one request, newest query next. */
(() => {
  'use strict';
  document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('archive-filters');
    if (!form || form.dataset.mounted) return;
    form.dataset.mounted = 'true';
    const U = window.SongRankerUI;
    const search = document.getElementById('archive-search');
    const target = document.getElementById('archive-target');
    for (const id of ['archive-mode', 'archive-kind']) {
      const native = document.getElementById(id), label = native.closest('label'), wrapper = document.createElement('div');
      wrapper.innerHTML = window.GameplayUI.select(id, label.firstChild.textContent,
        [...native.options].map(o => ({value:o.value, label:o.textContent})), native.value);
      wrapper.querySelector('select').name = native.name;
      label.replaceWith(wrapper.firstElementChild);
    }
    const kind = document.getElementById('archive-kind'), mode = document.getElementById('archive-mode');
    const panel = form.closest('.history-search-panel');
    const suggestions = document.getElementById('archive-suggestions');
    const selection = document.getElementById('archive-selection'), error = document.getElementById('archive-error');
    const modeColours = {voting:'voting', standard:'standard', blind:'blind', tournament:'tournament', recognition:'recognition', shelves:'shelves', vibe:'vibe'};
    function modeColour() {
      if (!panel) return;
      panel.dataset.mode = mode.value;
      panel.style.setProperty('--history-mode-accent', 'var(--' + (modeColours[mode.value] || 'overall') + ')');
    }
    mode.addEventListener('change', modeColour);
    modeColour();
    let serial = 0, controller, active = false, rows = [];
    function close() { suggestions.hidden = true; search.setAttribute('aria-expanded', 'false'); }
    function cancel() { ++serial; controller?.abort(); active = false; rows = []; close(); }
    function clear() { cancel(); target.value = ''; search.value = ''; selection.textContent = 'All records'; error.textContent = ''; }
    function render(exact = false) {
      const terms = U.searchText(search.value).split(/\s+/).filter(Boolean);
      const matches = rows.filter(row => {
        const text = U.searchText([row.name, row.subtitle, ...(row.artists || []).map(a=>a.name), row.album?.name, ...(row.related || []).map(r=>r.name)].join(' '));
        return terms.every(term=>text.includes(term));
      }).slice(0,3);
      const focused = suggestions.contains(document.activeElement) ? document.activeElement.dataset.recordId : null;
      suggestions.innerHTML = '';
      for (const row of matches) {
        const button = document.createElement('button');
        button.type = 'button'; button.dataset.kind = kind.value; button.dataset.recordId = row.id;
        const artists = (row.artists || []).map(a => a.name).join(', ');
        button.innerHTML = `${kind.value === 'tags' ? '<span class="archive-tag-art" aria-hidden="true">#</span>' : row.cover ? `<img data-cover src="${U.esc(row.cover)}" alt="" loading="lazy">` : '<span aria-hidden="true">♫</span>'}<span><strong class="${({songs:'song',albums:'album',artists:'artist',tags:'tag'})[kind.value]}">${U.esc(row.name)}</strong><small>${U.esc(artists || row.subtitle || '')}${row.album ? ' · ' + U.esc(row.album.name) : ''}</small></span>`;
        button.addEventListener('click', () => {
          target.value = row.id; search.value = row.name; selection.textContent = 'Selected: ' + row.name;
          cancel(); search.focus();
        });
        suggestions.append(button);
      }
      if (!matches.length) suggestions.textContent = exact ? 'No matching records.' : 'Searching…';
      suggestions.hidden = false; search.setAttribute('aria-expanded', 'true');
      if (focused) ([...suggestions.querySelectorAll('button')].find(b=>b.dataset.recordId===focused) || search).focus();
    }
    async function lookup() {
      if (active || !search.value.trim()) return;
      active = true;
      const request = serial, query = search.value.trim(), type = kind.value;
      controller = new AbortController();
      const current = controller, timeout = setTimeout(()=>current.abort(),15000);
      try {
        const response = await fetch('/api/query?lookup=' + encodeURIComponent(type) + '&q=' + encodeURIComponent(query), {signal:current.signal});
        if (!response.ok) throw new Error('Could not load matching records. Type again to retry.');
        const data = await response.json();
        if (request !== serial) return;
        rows = data.items;
        render(query === search.value.trim());
      } catch (e) {
        if (request === serial && query === search.value.trim()) { error.textContent = e.name === 'AbortError' ? 'Search timed out. Type again to retry.' : e.message; close(); }
      } finally {
        clearTimeout(timeout);
        if (request === serial) {
          active = false;
          if (search.value.trim() && query !== search.value.trim()) lookup();
        }
      }
    }
    document.getElementById('archive-clear').addEventListener('click', () => { clear(); search.focus(); });
    kind.addEventListener('change', () => {
      clear();
      panel?.style.setProperty('--lookup-accent', 'var(--' + ({songs:'song',albums:'album',artists:'artist',tags:'tag'})[kind.value] + ')');
    });
    search.addEventListener('input', () => {
      target.value = ''; error.textContent = '';
      selection.textContent = search.value.trim() ? 'Choose a matching record below' : 'All records';
      if (!search.value.trim()) { cancel(); return; }
      render(); lookup();
    });
    form.addEventListener('keydown', e => {
      if (!e.target.closest('.archive-lookup')) return;
      const buttons = [...suggestions.querySelectorAll('button')];
      if (e.key === 'Escape') { cancel(); search.focus(); }
      if (!suggestions.hidden && ['ArrowDown', 'ArrowUp'].includes(e.key) && buttons.length) {
        e.preventDefault();
        const index = buttons.indexOf(document.activeElement);
        buttons[index < 0 ? (e.key === 'ArrowDown' ? 0 : buttons.length-1) : (index + (e.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length].focus();
      }
    });
    form.addEventListener('submit', e => {
      if (search.value.trim() && !target.value) { e.preventDefault(); error.textContent = 'Choose a matching record, or clear the search to view all records.'; search.focus(); }
    });
    document.addEventListener('click', e => { if (!e.target.closest('.archive-lookup')) cancel(); });
    window.addEventListener('pagehide', cancel);
  });
})();
