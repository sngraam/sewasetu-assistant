# Sewa Setu — Old Age Pension Portal

Department of Social Welfare, Government of Purvanchal.

---

## Quick start

```bash
ADMIN_PASSWORD=admin123 docker compose up --build
```

| Service | URL | Notes |
|---|---|---|
| Portal | http://localhost:8000 | Also via Caddy at http://localhost |
| Status portal | http://localhost:8000/status | Password = DOB as DDMMYYYY |
| Admin | http://localhost:8000/admin | user `admin`, password from `ADMIN_PASSWORD` |
| SMS inbox | http://localhost:8000/__gateway/ | OTPs appear here after 1–4 s delivery delay |
| OTP JSON API | http://localhost:8000/__gateway/api/messages?to=<mobile> | Read OTP for a specific mobile |
| Eval dashboard | http://localhost:8000/eval-dashboard | Personas, pass criteria, results |
| **Citizen MCP** | **http://localhost/mcp/citizen/mcp** | Via Caddy (strips prefix) |
| **Officer MCP** | **http://localhost/mcp/officer/mcp** | Via Caddy (strips prefix) |
| Citizen MCP (direct) | http://localhost:8001/mcp | Direct port — no Caddy |
| Officer MCP (direct) | http://localhost:8002/mcp | Direct port — no Caddy |

---

## MCP servers

Sewa Setu exposes two MCP endpoints for AI assistants (Claude Code, Claude Desktop, Kiro, etc.).

### Citizen MCP — `http://localhost/mcp/citizen/mcp`

Helps elderly citizens apply for and manage the Old Age Pension.

| Tool | When to call |
|---|---|
| `who_am_i()` | Start of every conversation — confirms sign-in, checks active application |
| `get_scheme_info()` | Citizen asks about scheme eligibility or documents |
| `check_eligibility(dob, block)` | Before collecting full details — fails fast if ineligible |
| `submit_application(...)` | After collecting all fields and explicit confirmation |
| `my_applications()` | Citizen wants to check application status |
| `get_application(application_no)` | Full details of one application |
| `withdraw_application(application_no)` | Withdraw a PENDING application |

### Officer MCP — `http://localhost/mcp/officer/mcp`

Helps block officers review the pending queue and approve or reject applications.

| Tool | When to call |
|---|---|
| `queue_summary()` | Start of officer session — overview of pending, overdue counts |
| `list_pending(page, block)` | See the PENDING queue, oldest first |
| `get_dossier(application_no)` | Full record + flags before deciding |
| `decide_application(application_no, decision, reason, confirmed_original_seen)` | Approve or reject |

### Auth

**Production:** Citizen and officer sign in via the portal's OAuth 2.1 flow.
The AI assistant receives a short-lived RS256 JWT and sends it as `Authorization: Bearer <token>`.

```
OAuth discovery:  http://localhost:8000/.well-known/oauth-authorization-server
JWKS:             http://localhost:8000/.well-known/jwks.json
Authorize:        http://localhost:8000/oauth/authorize
Token:            http://localhost:8000/oauth/token
```

**Local dev bypass (no OAuth needed):**
```bash
DEV_INSECURE_MOBILE=9876543210   # citizen MCP acts as this mobile
DEV_INSECURE_OFFICER=admin       # officer MCP acts as this officer
ADMIN_PASSWORD=admin123 docker compose up --build
```

---

## Project structure

```
app/              Flask portal + OAuth 2.1 server
  app.py          Main routes, application flow, admin panel
  oauth.py        Authorization server (RFC 8414, 7591, PKCE, RFC 8707)
  eval_personas.py Invented test personas for the eval dashboard
  templates/      HTML templates (Jinja2)
  scripts/        Nightly deemed-approval cron job
  schema.sql      PostgreSQL schema

mcp/              MCP servers (two separate processes)
  config.py       All env vars — single source of truth
  auth.py         JWT verification via portal JWKS (RS256)
  shared.py       Backward-compat re-export shim
  db/             Database layer (connection pool + queries)
    pool.py       ThreadedConnectionPool
    citizen.py    Citizen SQL queries
    officer.py    Officer SQL queries
  domain/         Business logic (no DB imports)
    validation.py validate_application() — mirrors portal rules exactly
    application.py create, withdraw, build_dossier
    audit.py      write_audit()
    time.py       IST clock
  middleware/     Cross-cutting concerns
    masking.py    mask_account(), mask_mobile()
    otp.py        OTP send + verify with rate limiting
  prompts/        System instructions + next_step constants
    citizen_instructions.py  <300 token compressed system prompt
    officer_instructions.py  <200 token compressed system prompt
    next_steps.py            Structured next_step objects (not prose)
  tools/          One file per MCP tool
    citizen/      who_am_i, scheme_info, eligibility, apply, status, withdraw
    officer/      queue, dossier, decide
  citizen_mcp.py  Entry point — wires tools, starts server on :8001
  officer_mcp.py  Entry point — wires tools, starts server on :8002

seed/             seed.sql — 100k-row production data snapshot
smsgw/            Simulated SMS gateway (OTP delivery)
tests/            e2e test suite (26 checks)
```

---

## Deploying on a server

```bash
PUBLIC_BASE_URL=https://sewasetu.example.in \
ADMIN_PASSWORD=strong-password-here \
PUBLIC_DOMAIN=sewasetu.example.in \
docker compose up --build -d
```

- Set `PUBLIC_DOMAIN` so Caddy provisions a TLS certificate automatically.
- Set `PUBLIC_BASE_URL` so OAuth tokens have the correct `iss` and MCP audience.
- Remove `DEV_INSECURE_MOBILE` and `DEV_INSECURE_OFFICER` — these must never be set in production.
- The MCP endpoints will be at `https://sewasetu.example.in/mcp/citizen/mcp` and `/mcp/officer/mcp`.

---

## How the portal works

**Citizen flow:** mobile → OTP → personal details → address → bank details →
age-proof upload → preview and declaration → application number.

**Rules enforced at submission** (in `validate_application()` — identical in portal and MCP):
- Applicant is 60 years of age or above
- Required fields and age-proof document are present
- Scheme window is open (closes 31 October 2026)
- Mobile holds no other active (PENDING / APPROVED / DEEMED_APPROVED) application

**Deemed approval:** A nightly cron job (`scripts/deemed_approval.py`) automatically
approves any application still PENDING after the 15-day SLA, per the Purvanchal
Right to Public Services Act.

---

## Agent pilot blocks

The AI channel covers three pilot blocks: **Sonari, Rajapara, Dhemaji Pathar**.
Citizens in the other three blocks (Borgaon, Namti, Khelua) must apply at the
block office counter or directly on the portal.

Configure with `AGENT_BLOCKS=Sonari,Rajapara,Dhemaji Pathar` env var.
