# Release Readiness

Date: 2026-06-19

## Decision

Release Ready for an internal MVP evaluation.

Production Ready is not approved because external GIS/API integration, persistent storage, enterprise authentication, and durable audit logging are intentionally stubbed or deferred.

## Implemented Scope

- FastAPI application with health, project, route generation, route evaluation, route risk, report, data source, and knowledge search endpoints.
- Nine-screen single-page UI implementing the Claude Design handoff (`Route Planner.dc.html`): dashboard, project/conditions, route review & map, risk memo, report output, knowledge search, facilities dictionary, admin, and system settings.
- Self-contained client runtime (`app/static/dc-runtime.js`) that interprets the design-component template dialect (`sc-if` / `sc-for` / `{{ }}` bindings, event handlers, SVG namespacing) with text-input focus preservation across re-renders.
- Deterministic, safety-first knowledge responder (`app/knowledge.py`) that returns conservative guidance plus confirmation targets and never asserts passability; surfaced as reliability tier "E" in the UI.
- Deterministic sample overlay engine for bridge, tunnel, school, hospital, residential, traffic, disaster, and OSM attribute-quality risks.
- Safety-first route scoring that never treats missing height, weight, or road restriction data as clear passage.
- Markdown and CSV report generation with mandatory disclaimer and confirmation actions.
- Optional `APP_API_KEY` bearer-token protection for API endpoints.
- Unit, API flow, and knowledge tests, plus a jsdom render harness for the UI runtime.

## Validation Results

- `pytest -q`: passed, 11 tests.
- `ruff check .`: passed.
- `python3 -m compileall app tests`: passed.
- `bandit -q -r app`: passed.
- `pip-audit .`: passed, no known vulnerabilities found.
- `node --check` on `dc-runtime.js`, `component.js`, `app.js`: passed.
- jsdom render harness: all 9 screens render with no exceptions, no unresolved `{{ }}` bindings, and no leftover `sc-*` tags; SVG elements land in the SVG namespace; nav transitions, layer toggles, route/hazard selection, the knowledge search round-trip, and text-input focus preservation all pass.
- HTTP smoke test on `127.0.0.1:8019`: passed for `/api/health`, `/`, static assets (`dc-runtime.js`, `component.js`), and `POST /api/knowledge/search`.

## Known Limitations

- No real OpenStreetMap, xROAD, PLATEAU, or National Land Numerical Information API connection yet.
- No PostgreSQL/PostGIS persistence; current storage is process memory.
- No Entra ID/OIDC integration; API key protection is only a basic MVP guard.
- No durable audit log table or external log sink.
- The knowledge search is a deterministic, rule-based responder, not a live LLM; the UI labels it reliability tier "E · 要レビュー".
- Eight of the nine UI screens render from sample/demo data; only the knowledge search and the startup health check call the live backend. Live data-source, persistence, and report wiring remain deferred.
- Playwright screenshot validation could not be completed because Chromium exited immediately in this environment (SIGTRAP). The UI runtime was instead verified with a jsdom render harness; pixel-level visual regression against the design screenshots is still outstanding.

## Release Guard

- Critical security issue: none found in local checks.
- Failed tests: none.
- Failed build/compile: none.
- Open blocker for internal MVP release: none.
- Open blocker for production release: external data, persistence, auth, and audit logging remain required.
