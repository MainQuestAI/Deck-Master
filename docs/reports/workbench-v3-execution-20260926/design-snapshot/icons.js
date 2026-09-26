/* Shared 24-unit line icons: 1.75 stroke, rounded ends, inherited semantic ink. */
(function () {
  const paths = {
    overview:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 10h16M10 10v10"/>',
    content:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 12h6M9 16h6"/>',
    gallery:'<rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/>',
    style:'<path d="M4 7h7m6 0h3M4 17h3m6 0h7"/><circle cx="14" cy="7" r="3"/><circle cx="10" cy="17" r="3"/>',
    runs:'<path d="M6 4h8a3 3 0 0 1 3 3v10M13 13l4 4 4-4"/><circle cx="6" cy="4" r="2"/><path d="M4 11v7a2 2 0 0 0 2 2h5"/>',
    left:'<path d="M19 12H5m6-6-6 6 6 6"/>',
    right:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
    up:'<path d="M12 19V5m-6 6 6-6 6 6"/>',
    down:'<path d="M12 5v14m-6-6 6 6 6-6"/>',
    external:'<path d="M9 5H5v14h14v-4M13 5h6v6M19 5l-9 9"/>',
    check:'<path d="m5 12 4.5 4.5L19 7"/>',
    attention:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5M12 16h.01"/>',
    minus:'<path d="M5 12h14"/>',
    plus:'<path d="M5 12h14M12 5v14"/>',
    clock:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
    dot:'<circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/>'
  };
  window.uiIcon = function(name) {
    if (!paths[name]) throw new Error('Unknown icon: '+name);
    return '<svg class="ui-icon" data-icon="'+name+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'+paths[name]+'</svg>';
  };
  const glyphs={'←':'left','→':'right','↑':'up','↓':'down','↗':'external','✓':'check','●':'attention','—':'minus','＋':'plus','−':'minus'};
  window.uiIconLabel = text => String(text).replace(/[←→↑↓↗✓●—＋−]/g, value=>window.uiIcon(glyphs[value]));
})();
