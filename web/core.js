(function (root) {
  'use strict';
  const common = [
    { time: 0, type: 'request', label: 'initialize', slot: 0 },
    { time: 100, type: 'response', label: 'serverInfo', slot: 0 },
    { time: 200, type: 'request', label: 'ping', slot: 1 },
    { time: 300, type: 'response', label: '{}', slot: 1 },
    { time: 400, type: 'request', label: 'add_numbers(1 + 2)', slot: 2 },
    { time: 450, type: 'request', label: 'add_numbers(40 + 2)', slot: 3 },
    { time: 550, type: 'response', label: '3', slot: 2 },
    { time: 600, type: 'response', label: '42', slot: 3 },
    { time: 700, type: 'request', label: 'sleep_ms(300)', slot: 4 },
    { time: 750, type: 'timeout', label: 'timeoutLabel', slot: 4 },
    { time: 1000, type: 'orphan', label: 'orphanLabel', slot: 4 }
  ];
  const ids = ['a3f8c9…', '7b2d4f…', 'cdb4fb…', '02d0c6…', 'b484ad…'];
  function events(mode) {
    if (!['vulnerable', 'secure'].includes(mode)) throw new RangeError('Unknown policy');
    return common.map(event => ({
      ...event,
      id: mode === 'secure' ? ids[event.slot] : String(event.slot + 1),
      type: event.type === 'orphan' && mode === 'secure' ? 'discarded' : event.type
    }));
  }
  function summarize(items) {
    const stats = { requests: 0, responses: 0, timeouts: 0, orphans: 0 };
    items.forEach(event => {
      if (event.type === 'request') stats.requests++;
      if (event.type === 'response') stats.responses++;
      if (event.type === 'timeout') stats.timeouts++;
      if (event.type === 'orphan' || event.type === 'discarded') stats.orphans++;
    });
    return stats;
  }
  const api = { events, summarize };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RpcDemo = api;
})(typeof globalThis === 'object' ? globalThis : this);
