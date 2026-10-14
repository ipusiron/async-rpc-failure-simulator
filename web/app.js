(() => {
  'use strict';
  let lang = 'ja';
  try { if (localStorage.getItem('rpc-demo-language') === 'en') lang = 'en'; } catch (_) {}
  const state = { vulnerable: [], secure: [] };
  const timers = new Set();
  let generation = 0;
  let active = null;
  let statusKey = 'ready';
  let statusMode = null;
  const t = key => RpcMessages[lang][key];
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function renderPanel(mode) {
    const container = document.getElementById(mode + '-events');
    const fragment = document.createDocumentFragment();
    if (!state[mode].length) fragment.append(node('p', t('empty'), 'empty'));
    state[mode].forEach(event => {
      const row = node('li', undefined, 'event ' + event.type);
      row.append(node('span', event.time + ' ms', 'event-time'),
        node('span', t(event.type), 'event-kind'),
        node('span', t(event.label) || event.label, 'event-label'),
        node('code', 'id=' + event.id, 'event-id'));
      fragment.append(row);
    });
    container.replaceChildren(fragment);
    const stats = RpcDemo.summarize(state[mode]);
    const prefix = mode === 'vulnerable' ? 'v' : 's';
    Object.entries(stats).forEach(([key, value]) => {
      document.getElementById(prefix + '-' + key).textContent = value;
    });
  }
  function renderStatus() {
    document.getElementById('status').textContent = t(statusKey) + (statusMode ? t(statusMode) : '');
    document.querySelectorAll('[data-run]').forEach(button => { button.disabled = active !== null; });
  }
  function render() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach(element => {
      element.textContent = t(element.dataset.i18n);
    });
    document.getElementById('language').setAttribute('aria-label', t('languageLabel'));
    document.getElementById('readme').href = 'https://github.com/ipusiron/async-rpc-failure-simulator/blob/main/' +
      (lang === 'en' ? 'README.en.md' : 'README.md');
    ['vulnerable', 'secure'].forEach(renderPanel);
    renderStatus();
  }
  function clear() {
    generation++;
    timers.forEach(clearTimeout);
    timers.clear();
    active = null;
    state.vulnerable = [];
    state.secure = [];
    statusKey = 'cleared';
    statusMode = null;
    render();
  }
  function run(mode) {
    if (active) return;
    active = mode;
    statusKey = 'running';
    statusMode = mode;
    state[mode] = [];
    render();
    const current = ++generation;
    const events = RpcDemo.events(mode);
    const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    events.forEach((event, index) => {
      const timer = setTimeout(() => {
        timers.delete(timer);
        if (current !== generation) return;
        state[mode].push(event);
        renderPanel(mode);
        if (index === events.length - 1) {
          active = null;
          statusKey = 'finished';
          renderStatus();
        }
      }, reduceMotion ? 0 : event.time * 2);
      timers.add(timer);
    });
  }
  document.querySelectorAll('[data-run]').forEach(button =>
    button.addEventListener('click', () => run(button.dataset.run)));
  document.getElementById('clear').addEventListener('click', clear);
  document.getElementById('language').addEventListener('click', () => {
    lang = lang === 'ja' ? 'en' : 'ja';
    try { localStorage.setItem('rpc-demo-language', lang); } catch (_) {}
    render();
  });
  render();
})();
