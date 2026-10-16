# Sewa Setu MCP Servers

Two MCP servers over streamable-HTTP for the Old Age Pension portal.

## Endpoints

| Server | Port | Path via Caddy |
|---|---|---|
| Citizen MCP | 8001 | `/mcp/citizen/mcp` |
| Officer MCP | 8002 | `/mcp/officer/mcp` |

## Quick test (no OAuth needed)

```bash
# Start with dev bypass
DEV_INSECURE_MOBILE=9876543210 DEV_INSECURE_OFFICER=admin \
ADMIN_PASSWORD=admin123 docker compose up --build

# Call a tool
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}'
```

## Folder structure

```
mcp/
├── config.py              All env vars — single source of truth
├── auth.py                JWT verification (RS256, JWKS, audience check)
├── shared.py              Backward-compat shim — imports from new layers
│
├── db/
│   ├── pool.py            ThreadedConnectionPool (2–10 connections)
│   ├── citizen.py         Citizen SQL queries
│   └── officer.py         Officer SQL queries
│
├── domain/
│   ├── time.py            IST clock
│   ├── validation.py      validate_application() — mirrors portal rules exactly
│   ├── application.py     create, withdraw, build_dossier
│   └── audit.py           write_audit()
│
├── middleware/
│   ├── masking.py         mask_account(), mask_mobile()
│   ├── otp.py             send_otp(), verify_otp() with rate limiting
│   └── logging_setup.py   JSON structured logging
│
├── prompts/
│   ├── citizen_instructions.py  <300 token system prompt
│   ├── officer_instructions.py  <200 token system prompt
│   └── next_steps.py            Structured next_step objects
│
├── tools/
│   ├── citizen/
│   │   ├── who_am_i.py    who_am_i()
│   │   ├── scheme_info.py get_scheme_info()
│   │   ├── eligibility.py check_eligibility(dob, block)
│   │   ├── apply.py       submit_application(...)
│   │   ├── status.py      my_applications(), get_application(no)
│   │   └── withdraw.py    withdraw_application(no)
│   └── officer/
│       ├── queue.py       queue_summary(), list_pending(page, block)
│       ├── dossier.py     get_dossier(no)
│       └── decide.py      decide_application(no, decision, reason, confirmed)
│
├── citizen_mcp.py         Entry point — wires tools, starts on :8001
└── officer_mcp.py         Entry point — wires tools, starts on :8002
```

## Key design decisions

### next_step is a structured object, not prose

Every tool returns `next_step` as a dict with `action`, `prompt`, and optionally
`field`, `options`, `remaining`, `progress`. Small models parse objects reliably
and miss things in paragraphs.

```json
"next_step": {
  "action": "ask_question",
  "field": "applicant_name",
  "prompt": "Poora naam batayein — jaisa age proof document mein likha hai.",
  "progress": "0 of 7 fields collected"
}
```

### errors have a code + recovery

```json
"error": {
  "code": "INVALID_FIELD",
  "field": "ifsc",
  "message": "IFSC must be 11 characters, e.g. SBIN0003077.",
  "recovery": "ask_again"
}
```

`recovery` values: `ask_again` | `resend` | `stop` | `redirect` | `call_tool`

### check_eligibility returns `collected`

The DOB and block gathered for eligibility are returned in a `collected` dict.
The model must carry these forward and NOT ask for them again.

### OTP rate limiting

Max 3 OTPs per mobile per 10 minutes (configurable via `OTP_MAX_PER_WINDOW`
and `OTP_WINDOW_SECONDS`).

### Connection pool

`db/pool.py` uses `psycopg2.pool.ThreadedConnectionPool` (min=2, max=10).
No new connection is opened per tool call.

## Adding a new tool

1. Create `tools/citizen/my_tool.py` with a `register(mcp)` function.
2. Add `from tools.citizen import my_tool` to `citizen_mcp.py`.
3. Add `my_tool.register(mcp)` after the other register calls.
4. Add the tool to `prompts/citizen_instructions.py` tool list.
5. Add next_step constants to `prompts/next_steps.py`.

## Environment variables

See `.env.example` for the full list. Key ones:

| Var | Default | Description |
|---|---|---|
| `PORTAL_ISSUER` | — | Public portal URL (= `PUBLIC_BASE_URL`) |
| `PORTAL_JWKS_URL` | `PORTAL_ISSUER/.well-known/jwks.json` | Where to fetch signing keys |
| `CITIZEN_MCP_URL` | — | Public URL of citizen MCP (= JWT audience) |
| `OFFICER_MCP_URL` | — | Public URL of officer MCP (= JWT audience) |
| `AGENT_BLOCKS` | `Sonari,Rajapara,Dhemaji Pathar` | Pilot blocks for AI channel |
| `DEV_INSECURE_MOBILE` | — | Bypass JWT (dev only) |
| `DEV_INSECURE_OFFICER` | — | Bypass JWT (dev only) |
| `LOG_FORMAT` | `json` | `json` or `text` |
