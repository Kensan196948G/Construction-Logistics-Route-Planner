# Security Policy

## Scope

This project is an internal-MVP route-risk review tool. It ships a FastAPI
backend and a static single-page UI with persistent storage (SQLite by default,
PostgreSQL when `DATABASE_URL` is set), Alembic migrations, a durable
`audit_logs` table, and two authentication modes: Entra ID / OIDC JWT
validation, or an `APP_API_KEY` bearer guard as fallback.

**Current deployments are PoC/sample mode and must not be used for production
decisions.** Routes and risk features are sample-generated; the UI and reports
display a persistent "本番利用禁止（PoC・サンプル）" notice. Set
`PRODUCTION_MODE=1` only after real data integration is complete.

In API-key mode, audit identity is derived from deployment configuration
(`APP_API_KEY_USER_ID` / `APP_API_KEY_USER_ROLE`), never from client-supplied
`x-user-id` / `x-user-role` headers, which are spoofable. Public exposure still
requires TLS and an access-controlled front (reverse proxy / VPN / Cloudflare
Access); the application itself does not terminate TLS.

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
