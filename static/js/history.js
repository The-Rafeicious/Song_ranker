/* History selection uses Query's bounded lookup and the shared styled controls. */
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
      const native = document.getElementById(id);
      const label = native.closest('label');
      const wrapper = document.createElement('div');
      wrapper.innerHTML = window.GameplayUI.select(id, label.firstChild.textContent,
        [...native.options].map(o => ({value:o.value, label:o.textContent})), native.value);
      wrapper.querySelector('select').name = native.name;
      label.replaceWith(wrapper.firstElementChild);
    }
    const kind = document.getElementById('archive-kind');
    const suggestions = document.getElementById('archive-suggestions');
    const selection = document.getElementById('archive-selection');
    const error = document.getElementById('archive-error');
    let serial = 0, timer, controller;
    function close() {
      suggestions.hidden = true;
      search.setAttribute('aria-expanded', 'false');
    }
    function cancel() {
      ++serial;
      clearTimeout(timer);
      controller?.abort();
      close();
    }
    function clear() {
      cancel();
      target.value = '';
      search.value = '';
      selection.textContent = 'All records';
      error.textContent = '';
    }
    document.getElementById('archive-clear').addEventListener('click', () => { clear(); search.focus(); });
    kind.addEventListener('change', () => {
      clear();
      form.closest('.history-search-panel')?.style.setProperty('--lookup-accent', 'var(--' + ({songs:'song',albums:'album',artists:'artist',tags:'tag'})[kind.value] + ')');
    });
    search.addEventListener('input', () => {
      cancel();
      target.value = '';
      selection.textContent = search.value.trim() ? 'Choose a matching record below' : 'All records';
      error.textContent = '';
      if (!search.value.trim()) return;
      const request = serial;
      timer = setTimeout(async () => {
        controller = new AbortController();
        const active = controller;
        const timeout = setTimeout(() => active.abort(), 15000);
        try {
          const response = await fetch('/api/query?lookup=' + encodeURIComponent(kind.value) + '&q=' + encodeURIComponent(search.value), {signal: active.signal});
          if (!response.ok) throw new Error('Could not load matching records. Type again to retry.');
          const data = await response.json();
          if (request !== serial) return;
          suggestions.innerHTML = '';
          for (const row of data.items) {
            const button = document.createElement('button');
            button.type = 'button';
            button.dataset.kind = kind.value;
            const artists = (row.artists || []).map(a => a.name).join(', ');
            button.innerHTML = `${kind.value === 'tags' ? '<span class="archive-tag-art" aria-hidden="true">#</span>' : row.cover ? `<img data-cover src="${U.esc(row.cover)}" alt="" loading="lazy">` : '<span aria-hidden="true">♫</span>'}<span><strong class="${({songs:'song',albums:'album',artists:'artist',tags:'tag'})[kind.value]}">${U.esc(row.name)}</strong><small>${U.esc(artists || row.subtitle || '')}${row.album ? ' · ' + U.esc(row.album.name) : ''}</small></span>`;
            button.addEventListener('click', () => {
              target.value = row.id;
              search.value = row.name;
              selection.textContent = 'Selected: ' + row.name;
              cancel();
              search.focus();
            });
            suggestions.append(button);
          }
          if (!data.items.length) suggestions.textContent = 'No matching records.';
          suggestions.hidden = false;
          search.setAttribute('aria-expanded', 'true');
        } catch (e) {
          if (request === serial) error.textContent = e.name === 'AbortError' ? 'Search timed out. Type again to retry.' : e.message;
        } finally { clearTimeout(timeout); }
      }, 250);
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
      if (search.value.trim() && !target.value) {
        e.preventDefault();
        error.textContent = 'Choose a matching record, or clear the search to view all records.';
        search.focus();
      }
    });
    document.addEventListener('click', e => { if (!e.target.closest('.archive-lookup')) cancel(); });
    window.addEventListener('pagehide', cancel);
  });
})();
