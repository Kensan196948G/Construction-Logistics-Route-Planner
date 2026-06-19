/*
 * app.js — bootstrap for the Route Planner UI.
 *
 * Wires the design-derived Component (component.js) onto the page template via
 * the minimal runtime (dc-runtime.js), then exercises the backend so the UI is
 * a live client, not a static mock:
 *   - GET /api/health            connectivity check (surfaced on <html data-api>)
 *   - POST /api/knowledge/search driven from the Knowledge screen (component.js)
 */
(function () {
  'use strict';

  function boot() {
    var template = document.getElementById('app-template');
    var mount = document.getElementById('app');
    if (!template || !mount || typeof Component === 'undefined') return;

    // Props mirror the design-component defaults (accent colour + initial screen).
    var component = new Component({ accent: '#ff6a00', defaultScreen: 'dashboard' });
    component.mount(template, mount);

    // Confirm backend reachability; record it for diagnostics without altering
    // the faithful prototype visuals. Failures degrade gracefully (offline demo).
    fetch('/api/health')
      .then(function (res) { return res.ok ? res.json() : Promise.reject(res.status); })
      .then(function (health) {
        document.documentElement.setAttribute('data-api', 'online');
        if (health && health.version) {
          document.documentElement.setAttribute('data-api-version', health.version);
        }
      })
      .catch(function () {
        document.documentElement.setAttribute('data-api', 'offline');
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
