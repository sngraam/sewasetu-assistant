# Sewa Setu — AWS Production Deployment Guide
## Domain: https://sewasetu.sercho.in

---

## What you get after deployment

| URL | What it does |
|---|---|
| `https://sewasetu.sercho.in` | Citizen portal (apply, status check) |
| `https://sewasetu.sercho.in/admin` | Officer admin panel |
| `https://sewasetu.sercho.in/eval-dashboard` | Eval dashboard for the jury |
| `https://sewasetu.sercho.in/mcp/citizen` | Citizen MCP endpoint (Claude/ChatGPT connect here) |
| `https://sewasetu.sercho.in/mcp/officer` | Officer MCP endpoint |
| `https://sewasetu.sercho.in/.well-known/oauth-authorization-server` | OAuth discovery (auto-used by AI clients) |
| `https://sewasetu.sercho.in/oauth/authorize` | Login page AI client opens in browser |
| `https://sewasetu.sercho.in/__gateway/` | SMS OTP inbox (for testing) |

---

## Before you start: Cloudflare SSL setting (REQUIRED)

Your domain is proxied by Cloudflare. You **must** set Cloudflare's SSL/TLS mode to
**Full** or **Full (Strict)** — not "Flexible".

- Go to Cloudflare dashboard → Your domain → SSL/TLS → Overview
- Select **Full** (or Full Strict if you add a Cloudflare Origin Certificate)

Why: With "Flexible", Cloudflare sends plain HTTP to your AWS server. The portal
stamps `https://sewasetu.sercho.in` in JWT `iss` fields and OAuth discovery URLs.
When AI clients verify tokens they cross-check the issuer URL — if the actual
HTTP response headers say HTTP, the flow breaks.

---

## One-time AWS server setup

```bash
# 1. Install Docker + Compose
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and back in after this

# 2. Open ports in AWS Security Group (inbound rules)
#    Port 80  (HTTP) — only Caddy needs this; Cloudflare hits port 80
#    Port 22  (SSH)  — your management access only
#    Do NOT open 8000, 8001, 8002 — those are internal only

# 3. Point your domain DNS A-record to the server's public IP
#    sewasetu.sercho.in  →  <your EC2 public IP>
#    In Cloudflare: make sure the record is PROXIED (orange cloud, not grey)
#    Test: nslookup sewasetu.sercho.in  (should return Cloudflare IPs, not your EC2 IP)

# 4. Clone the repo onto the server
git clone https://github.com/YOUR_USERNAME/sewasetu-assistant.git
cd sewasetu-assistant
```

---

## Deploy

```bash
# 1. Generate secrets
python3 -c "import secrets; print(secrets.token_hex(32))"
# → copy this as SECRET_KEY

python3 -c "import secrets; print(secrets.token_urlsafe(24))"
# → copy this as DB_PASSWORD

# 2. Create the production .env file
cp .env.production .env

# 3. Edit .env — fill in FOUR values:
#    SECRET_KEY=<output from step 1>
#    DB_PASSWORD=<output from step 1, second run>
#    ADMIN_PASSWORD=<strong password, min 16 chars>
#    (PUBLIC_DOMAIN, PUBLIC_BASE_URL, CITIZEN_MCP_URL etc. are already set)
nano .env

# 4. Start everything
docker compose up --build -d

# 5. Check all containers are running
docker compose ps
# Expected: all 7 services (db, smsgw, app, scheduler, citizen_mcp, officer_mcp, caddy) = Up

# 6. Watch the portal start
docker compose logs app -f
# Should see: Running on http://0.0.0.0:8000

# 7. Verify the full stack
curl https://sewasetu.sercho.in/                                      # portal loads
curl https://sewasetu.sercho.in/.well-known/jwks.json                 # JWKS returns JSON
curl https://sewasetu.sercho.in/.well-known/oauth-authorization-server # discovery doc
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://sewasetu.sercho.in/mcp/citizen \
  -H "Content-Type: application/json" \
  -d '{}'
# → 401  (auth required — this is correct, means the MCP server is live)
```

---

## How Claude connects (the OAuth flow step by step)

```
1. User adds MCP server in Claude.ai or Claude Desktop:
      URL: https://sewasetu.sercho.in/mcp/citizen

2. Claude sends an unauthenticated request
   → Gets 401 with header:
      WWW-Authenticate: Bearer resource_metadata="https://sewasetu.sercho.in/.well-known/oauth-protected-resource/mcp/citizen"

3. Claude fetches the protected resource metadata:
   GET https://sewasetu.sercho.in/.well-known/oauth-protected-resource/mcp/citizen
   → {
       "resource": "https://sewasetu.sercho.in/mcp/citizen",
       "authorization_servers": ["https://sewasetu.sercho.in"]
     }

4. Claude fetches the authorization server discovery:
   GET https://sewasetu.sercho.in/.well-known/oauth-authorization-server
   → {
       "authorization_endpoint": "https://sewasetu.sercho.in/oauth/authorize",
       "token_endpoint":         "https://sewasetu.sercho.in/oauth/token",
       "registration_endpoint":  "https://sewasetu.sercho.in/oauth/register",
       ...
       "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
       "client_id_metadata_document_supported": true
     }

5. Claude registers itself (DCR) or uses its CIMD URL as client_id.
   Claude.ai web: uses CIMD — its client_id is a URL like https://claude.ai/...
   Claude Code:   uses CIMD — redirects to http://localhost:<port>/callback

6. Claude opens in browser:
   https://sewasetu.sercho.in/oauth/authorize
     ?client_id=https://claude.ai/...
     &redirect_uri=https://claude.ai/api/mcp/auth_callback
     &scope=citizen offline_access
     &code_challenge=<S256 PKCE challenge>
     &response_type=code

7. Citizen logs in on the portal:
   a. Enter 10-digit mobile number → OTP sent by SMS
   b. Enter OTP
   c. Click "Allow" on the consent page

8. Browser redirects back to Claude with an auth code:
   https://claude.ai/api/mcp/auth_callback?code=...&iss=https://sewasetu.sercho.in

9. Claude exchanges the code for tokens:
   POST https://sewasetu.sercho.in/oauth/token
   → { "access_token": "<JWT>", "refresh_token": "...", "expires_in": 1200 }

10. All MCP tool calls carry:
    Authorization: Bearer <JWT>
    Claude refreshes automatically using the refresh_token before expiry.
```

---

## How to add in Claude Desktop

1. Open Claude Desktop → Settings → Developer → Edit Config
2. Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sewasetu-citizen": {
      "type": "http",
      "url": "https://sewasetu.sercho.in/mcp/citizen"
    },
    "sewasetu-officer": {
      "type": "http",
      "url": "https://sewasetu.sercho.in/mcp/officer"
    }
  }
}
```

3. Restart Claude Desktop
4. The MCP icon appears → click "sewasetu-citizen" → Claude opens the login page

---

## How to add in Claude.ai (web custom connector)

1. Go to claude.ai → Settings → Connectors → Add connector
2. Enter URL: `https://sewasetu.sercho.in/mcp/citizen`
3. Claude auto-discovers OAuth and prompts the user to sign in via the portal

---

## How to add in ChatGPT (Custom Connector / Developer Mode)

ChatGPT follows the same MCP OAuth spec as Claude:

1. Enable Developer Mode in ChatGPT settings (Settings → Developer mode)
2. Go to a new chat → click the tools icon → "Add MCP server"
3. Enter: `https://sewasetu.sercho.in/mcp/citizen`
4. ChatGPT fetches the discovery doc and redirects to the portal login page
5. Citizen logs in with mobile + OTP → approves → ChatGPT stores the token

> Note: ChatGPT does not support `client_credentials` (machine-to-machine) grants.
> The citizen must sign in interactively. This is already how the portal works.

---

## How to add in Claude Code

Claude Code runs on your local machine and uses a loopback redirect:

```bash
# Add the server
claude mcp add sewasetu-citizen \
  --transport http \
  https://sewasetu.sercho.in/mcp/citizen

# Or edit ~/.claude/claude_code_config.json directly (same format as Desktop)
```

Claude Code opens a browser to the portal login page and listens on a local port
for the OAuth redirect. The portal's `redirect_allowed()` matches any port on
`localhost` / `127.0.0.1`, which is required by RFC 8252 for native clients.

---

## Environment variable reference

| Variable | Example value | What it controls |
|---|---|---|
| `PUBLIC_DOMAIN` | `sewasetu.sercho.in` | Caddy virtual host (no https://) |
| `PUBLIC_BASE_URL` | `https://sewasetu.sercho.in` | JWT `iss`, OAuth discovery issuer |
| `CITIZEN_MCP_URL` | `https://sewasetu.sercho.in/mcp/citizen` | JWT `aud` for citizen tokens |
| `OFFICER_MCP_URL` | `https://sewasetu.sercho.in/mcp/officer` | JWT `aud` for officer tokens |
| `SECRET_KEY` | 64-char hex string | Flask session signing key |
| `DB_PASSWORD` | random string | PostgreSQL password |
| `ADMIN_USERNAME` | `admin` | Officer login username |
| `ADMIN_PASSWORD` | strong password | Officer login password |
| `AGENT_BLOCKS` | `Sonari,Rajapara,Dhemaji Pathar` | Blocks covered by AI channel |
| `BEHIND_PROXY` | `1` | Enables ProxyFix for Cloudflare → Caddy → Flask |
| `LOG_FORMAT` | `json` | Structured JSON logs for log aggregation |
| `DEV_INSECURE_MOBILE` | *(blank)* | **Must be empty in production** |
| `DEV_INSECURE_OFFICER` | *(blank)* | **Must be empty in production** |

---

## Update the running server

```bash
git pull origin main
docker compose up --build -d
docker compose ps
```

---

## Troubleshooting

### "Claude shows 'Could not connect to MCP server'"
```bash
# Check all containers are up
docker compose ps

# Check Caddy is routing correctly (should return 401)
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://sewasetu.sercho.in/mcp/citizen \
  -H "Content-Type: application/json" -d '{}'
# Expected: 401

# Check the protected resource metadata is served
curl https://sewasetu.sercho.in/.well-known/oauth-protected-resource/mcp/citizen
# Expected: JSON with "resource" and "authorization_servers"
```

### "Claude doesn't redirect to login page"
This means Claude isn't finding the 401 or can't fetch the discovery doc.

```bash
# 1. Verify the 401 response includes WWW-Authenticate
curl -v -X POST https://sewasetu.sercho.in/mcp/citizen \
  -H "Content-Type: application/json" -d '{}' 2>&1 | grep -i "www-authenticate\|401"
# Must see: WWW-Authenticate: Bearer ... resource_metadata="..."

# 2. Verify the protected resource doc returns authorization_servers
curl https://sewasetu.sercho.in/.well-known/oauth-protected-resource/mcp/citizen | python3 -m json.tool
# Must include: "authorization_servers": ["https://sewasetu.sercho.in"]

# 3. Verify the AS discovery doc
curl https://sewasetu.sercho.in/.well-known/oauth-authorization-server | python3 -m json.tool
# Must include: authorization_endpoint, token_endpoint, registration_endpoint

# 4. Check PUBLIC_BASE_URL starts with https://
grep PUBLIC_BASE_URL .env
```

### "Authorization with the MCP server failed" (after Claude shows login page)
```bash
# Check CITIZEN_MCP_URL exactly matches what Claude connects to (no trailing slash)
grep CITIZEN_MCP_URL .env
# Should be: CITIZEN_MCP_URL=https://sewasetu.sercho.in/mcp/citizen

# Check the JWT is being verified correctly
docker compose logs citizen_mcp --tail=50 | grep -i "token\|error\|rejected"
```

### "OTP not received"
```bash
# Read OTPs directly from the gateway console
open https://sewasetu.sercho.in/__gateway/

# Or as JSON API
curl "https://sewasetu.sercho.in/__gateway/api/messages?to=<mobile>"
```

### "JWT rejected (401 on every tool call after sign-in)"
```bash
# Check env vars are correct
grep -E "DEV_INSECURE|PORTAL_ISSUER|CITIZEN_MCP_URL" .env
# DEV_INSECURE_MOBILE and DEV_INSECURE_OFFICER must be blank
# PORTAL_ISSUER inside containers = PUBLIC_BASE_URL

# Compare what the MCP container sees vs what the portal stamps in tokens
docker compose exec citizen_mcp env | grep PORTAL_ISSUER
docker compose exec app env | grep PUBLIC_BASE_URL
# Both must be identical: https://sewasetu.sercho.in
```

### "Users have to sign in again every 20 minutes"
This means refresh tokens aren't being issued. Check that:
```bash
# scopes_supported in the AS discovery doc includes offline_access
curl https://sewasetu.sercho.in/.well-known/oauth-authorization-server | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(d.get('scopes_supported'))"
# Must include 'offline_access'
```

---

## Quick reference — MCP endpoints for submission

```
Citizen MCP:      https://sewasetu.sercho.in/mcp/citizen
Officer MCP:      https://sewasetu.sercho.in/mcp/officer
Portal:           https://sewasetu.sercho.in
Eval dashboard:   https://sewasetu.sercho.in/eval-dashboard
Officer login:    https://sewasetu.sercho.in/admin
OTP console:      https://sewasetu.sercho.in/__gateway/
```
