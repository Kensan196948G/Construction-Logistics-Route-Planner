# Release Readiness

Date: 2026-06-19

## Decision

Release Ready for an internal MVP evaluation.

Production Ready is not approved because external GIS/API integration, persistent storage, enterprise authentication, and durable audit logging are intentionally stubbed or deferred.

## Implemented Scope

- FastAPI application with health, project, route generation, route evaluation, route risk, report, and data source endpoints.
- Static local UI for creating an evaluation and viewing route risk results.
- Deterministic sample overlay engine for bridge, tunnel, school, hospital, residential, traffic, disaster, and OSM attribute-quality risks.
- Safety-first route scoring that never treats missing height, weight, or road restriction data as clear passage.
- Markdown and CSV report generation with mandatory disclaimer and confirmation actions.
- Optional `APP_API_KEY` bearer-token protection for API endpoints.
- Unit and API flow tests.

## Validation Results

- `pytest -q`: passed, 6 tests.
- `ruff check .`: passed.
- `python3 -m compileall app tests`: passed.
- `bandit -q -r app`: passed.
- `pip-audit .`: passed, no known vulnerabilities found.
- HTTP smoke test on `127.0.0.1:8017`: passed for `/api/health`, `/`, project creation, route generation, route evaluation, and Markdown report.

## Known Limitations

- No real OpenStreetMap, xROAD, PLATEAU, or National Land Numerical Information API connection yet.
- No PostgreSQL/PostGIS persistence; current storage is process memory.
- No Entra ID/OIDC integration; API key protection is only a basic MVP guard.
- No durable audit log table or external log sink.
- Playwright screenshot validation could not be completed because Chromium exited immediately in this environment.

## Release Guard

- Critical security issue: none found in local checks.
- Failed tests: none.
- Failed build/compile: none.
- Open blocker for internal MVP release: none.
- Open blocker for production release: external data, persistence, auth, and audit logging remain required.
