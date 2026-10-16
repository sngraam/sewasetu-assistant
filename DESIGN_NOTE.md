# Sewa Setu MCP — Design Note

## Three Decisions That Mattered Most

### 1. JWT over OTP-in-MCP

The original prototype had `send_otp` and `verify_otp` as MCP tools, meaning
the AI model handled the citizen's authentication credential directly in the chat.
We replaced this with the portal's full OAuth 2.1 flow:

- The citizen opens the portal's sign-in page (mobile + OTP + consent).
- The AI assistant receives a short-lived RS256 JWT.
- Every tool call arrives with `Authorization: Bearer <token>`.
- `auth.py` verifies the RS256 signature against the portal's JWKS, checks `iss`,
  `aud`, `exp`, and the scope (`citizen` or `officer`).
- The citizen's mobile is read from `sub` (`citizen:<mobile>`). The model never
  sees it in plaintext; the tools show a masked version (`98****3210`).

**Why it matters:** The old design had the AI ask "Please tell me your OTP" — which
trains elderly citizens to share OTPs with anything that asks. The new design makes
the MCP indistinguishable from any other portal service in terms of security model.

### 2. Pilot block scope enforced at eligibility check, not at submit

`AGENT_BLOCKS` (default: Sonari, Rajapara, Dhemaji Pathar) is enforced in both
`check_eligibility` and `submit_application`. The key decision was to check it at
eligibility time — before collecting name, bank account, IFSC, etc.

Without this, a citizen from Namti would give all their details, reach the submit
step, and then be told the AI cannot help them. That is a worse experience than
being told at the start: "This AI channel covers Sonari, Rajapara, and Dhemaji
Pathar. For Namti, please go to the block office counter."

### 3. Declared-only age proof with mandatory officer confirmation

The agent channel cannot upload files. We store `declared://<type>` in `doc_path`
(e.g. `declared://voter_id`) as a marker. The officer's `get_dossier` tool surfaces
this prominently in `flags.declared_only` and `flags.age_proof_note`.

Critically, `decide_application` checks this flag before approving: if
`declared_only=True` and the officer has not passed `confirmed_original_seen=True`,
the tool returns an error asking them to physically verify the document first. This
makes it structurally impossible for the AI to approve an application on a document
it has never seen — the human officer must explicitly attest.

---

## One Decision We Would Make Differently

**Redis-backed session state instead of in-process dict.**

The citizen MCP currently has no shared state between tool calls in production
(JWT is the only state carrier), which is correct. But the `shared.py` OTP
functions write to PostgreSQL, and if we ever needed to cache verification state
(e.g. a rate-limit counter per mobile), we would store it in the same PostgreSQL
instance — adding latency on every tool call.

With more time we would use Redis for ephemeral per-session state (OTP attempt
counters, short-lived verification tokens) and reserve PostgreSQL for durable
application records only. This also enables stateless horizontal scaling of the
MCP containers without any session-stickiness requirement.
