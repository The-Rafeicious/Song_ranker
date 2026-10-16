/* Small game-only controls. Scoring, selection and audio stay in each game. */
window.GameplayUI = (() => {
  'use strict';
  const {$, $$, esc} = window.SongRankerUI;
  let opened = null, letters = '', letterTimer;
  function select(id, label, options, value) {
    const selected = options.find(o => o.value === value) || options[0];
    return `<div class="game-select" data-game-select="${esc(id)}"><span id="${id}-label" class="game-control-label">${esc(label)}</span><select id="${id}" hidden tabindex="-1" aria-label="${esc(label)}">${options.map(o=>`<option value="${esc(o.value)}" ${o.value===selected.value?'selected':''}>${esc(o.label)}</option>`).join('')}</select><button type="button" class="game-select-trigger" aria-haspopup="listbox" aria-expanded="false" aria-controls="${id}-menu" aria-labelledby="${id}-label ${id}-value"><span id="${id}-value">${esc(selected.label)}</span><span aria-hidden="true">⌄</span></button><div class="game-select-menu" id="${id}-menu" role="listbox" aria-labelledby="${id}-label" hidden>${options.map(o=>`<button type="button" role="option" tabindex="-1" aria-selected="${o.value===selected.value}" data-game-option="${esc(o.value)}"><span><b>${esc(o.label)}</b>${o.detail?`<small>${esc(o.detail)}</small>`:''}</span><span class="game-select-check" aria-hidden="true">✓</span></button>`).join('')}</div></div>`;
  }
  function close(focus = false) {
    if (!opened) return;
    const root = opened; opened = null;
    $('.game-select-menu', root).hidden = true;
    $('.game-select-trigger', root).setAttribute('aria-expanded', 'false');
    root.classList.remove('opens-up');
    clearTimeout(letterTimer); letters = '';
    if (focus) $('.game-select-trigger', root).focus();
  }
  function open(root) {
    close(); opened = root;
    const menu = $('.game-select-menu', root), trigger = $('.game-select-trigger', root);
    menu.hidden = false; trigger.setAttribute('aria-expanded', 'true');
    const rect = trigger.getBoundingClientRect(), below = window.innerHeight - rect.bottom - 12;
    const up = below < Math.min(menu.scrollHeight, 260) && rect.top > below;
    root.classList.toggle('opens-up', up);
    menu.style.bottom = up ? root.getBoundingClientRect().bottom - rect.top + 8 + 'px' : 'auto';
    menu.style.maxHeight = Math.max(60, Math.min(360, up ? rect.top - 12 : below)) + 'px';
    $('[aria-selected="true"]', menu)?.focus();
  }
  function choose(option) {
    const root = option.closest('.game-select'), control = $('select', root);
    control.value = option.dataset.gameOption;
    $('.game-select-trigger > span', root).textContent = $('b', option).textContent;
    $$('[role="option"]', root).forEach(o=>o.setAttribute('aria-selected', String(o === option)));
    close(true); control.dispatchEvent(new Event('change', {bubbles: true}));
  }
  document.addEventListener('click', event => {
    const root = event.target.closest('.game-select');
    if (!root) { close(); return; }
    const option = event.target.closest('[data-game-option]');
    if (option) choose(option);
    else if (event.target.closest('.game-select-trigger')) opened === root ? close() : open(root);
  });
  document.addEventListener('keydown', event => {
    const root = event.target.closest('.game-select'); if (!root) return;
    const options = $$('[role="option"]', root), at = options.indexOf(document.activeElement);
    if (event.key === 'Escape') { event.preventDefault(); close(true); return; }
    if (event.key === 'Tab') { if (opened) close(true); return; }
    if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
      event.preventDefault(); if (opened !== root) { open(root); return; }
      const index = event.key==='Home'?0:event.key==='End'?options.length-1:(at+(event.key==='ArrowUp'?-1:1)+options.length)%options.length;
      options[index]?.focus(); return;
    }
    if (opened !== root) return;
    if ((event.key==='Enter'||event.key===' ') && at>=0) { event.preventDefault(); choose(options[at]); return; }
    if (event.key.length===1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault(); clearTimeout(letterTimer); letters += event.key.toLocaleLowerCase();
      const after = [...options.slice(at+1), ...options.slice(0,at+1)];
      let next = after.find(o=>$('b',o).textContent.toLocaleLowerCase().startsWith(letters));
      if (!next) { letters=event.key.toLocaleLowerCase(); next=after.find(o=>$('b',o).textContent.toLocaleLowerCase().startsWith(letters)); }
      next?.focus(); letterTimer=setTimeout(()=>letters='',700);
    }
  });
  document.addEventListener('focusout', event => { if (opened && !opened.contains(event.relatedTarget)) close(); });
  window.addEventListener('resize', () => close());
  window.addEventListener('pagehide', () => close());
  return Object.freeze({select, close});
})();
