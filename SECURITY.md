# Security Policy

## Scope

This project is an internal-MVP route-risk review tool. It ships a FastAPI
backend and a static single-page UI. It has no persistence, no enterprise
authentication, and an optional `APP_API_KEY` bearer guard only (see
`RELEASE_READINESS.md`). Treat deployments as internal/evaluation, behind a
trusted network, until the production-hardening roadmap items land.

## Reporting a Vulnerability

Please report security issues **privately**, not in public issues or PRs:

- Use GitHub's private vulnerability reporting: the repository's **Security** tab
  → **Report a vulnerability**.

Include affected version/commit, reproduction steps, and impact. We aim to
acknowledge within a few working days. Please give us a reasonable window to
remediate before any public disclosure.

## Dependency Security

Runtime dependencies are intentionally minimal (`fastapi`, `uvicorn`,
`pydantic`); most CVE exposure comes from transitive packages.

### Continuous checks

- **`pip-audit .` (CI `dependency-audit` job)** — audits *this project's* declared
  dependency tree in isolation (not the whole runner environment) and uploads a
  JSON report artifact. It is **advisory (non-blocking)** on purpose: new
  transitive CVEs are published daily, and gating every unrelated PR on that
  churn would stall delivery without improving the change under review.
- **`bandit` (CI `quality` job, blocking)** — first-party code security scan.
- **Dependabot (`.github/dependabot.yml`)** — weekly update PRs for the `pip`
  (pyproject.toml) and `github-actions` ecosystems, including the SHA-pinned
  action versions.

### Triage policy for dependency CVEs

| Situation | Action |
|---|---|
| CVE in a **direct** dependency (`fastapi`/`uvicorn`/`pydantic`) with a fix | Bump the floor in `pyproject.toml` in a dedicated PR; verify the full gate. |
| CVE in a **transitive** dependency, fix available, reachable in our usage | Raise the relevant direct dependency's floor (or add a constraint) to pull the fixed transitive; verify. |
| CVE in a transitive dependency, **not reachable** in our code paths | Record the rationale; let the scheduled Dependabot/upgrade cycle carry it. Do not block unrelated PRs. |
| Critical/High with active exploitation | Patch out-of-band immediately, even mid-cycle. |

### Principles

- Prefer **raising dependency floors** over pinning exact versions, so security
  patches flow in without manual intervention while keeping builds reproducible
  enough for an MVP.
- Keep GitHub Actions **SHA-pinned** with a readable version comment; let
  Dependabot move the pin forward.
- Never silence `pip-audit` findings without a recorded reason.
