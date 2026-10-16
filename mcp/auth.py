"""
Token auth for the Sewa Setu MCP servers.

The portal is an OAuth 2.1 authorization server. A citizen signs in there with
mobile + OTP (an officer with the departmental login) and approves the
assistant. The MCP client then sends `Authorization: Bearer <JWT>` on every
call. We never see an OTP or a password; we only:

  1. verify the RS256 signature with the portal's JWKS,
  2. check `iss` is the portal, `aud` is THIS server's URL, `exp` is in the future,
  3. check the scope/role (citizen token on the citizen server, officer on officer),
  4. take identity from `sub` ("citizen:<mobile>" / "officer:<username>"),
     never from a tool argument the model could guess or invent.

Env (all URLs without trailing slash):
  PORTAL_ISSUER      public portal URL = PUBLIC_BASE_URL, e.g. https://sewasetu.example.in
  PORTAL_JWKS_URL    where THIS container can fetch keys (default PORTAL_ISSUER + /.well-known/jwks.json;
                     inside docker use the internal URL, e.g. http://web:8000/.well-known/jwks.json)
  CITIZEN_MCP_URL    canonical public URL of the citizen endpoint, e.g. https://.../mcp/citizen/mcp
  OFFICER_MCP_URL    canonical public URL of the officer endpoint

Local-only escape hatch (NEVER set on the public deployment):
  DEV_INSECURE_MOBILE=9876543210   -> citizen server skips auth and acts as that mobile
  DEV_INSECURE_OFFICER=testofficer -> officer server skips auth and acts as that officer
"""
import asyncio
import logging
import os

import jwt
from jwt import PyJWKClient
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings

log = logging.getLogger("sewasetu.auth")

ISSUER = os.environ.get("PORTAL_ISSUER", "").rstrip("/")
JWKS_URL = os.environ.get("PORTAL_JWKS_URL") or (ISSUER + "/.well-known/jwks.json")
RESOURCE_URLS = {
    "citizen": os.environ.get("CITIZEN_MCP_URL", "http://localhost:8001/mcp").rstrip("/"),
    "officer": os.environ.get("OFFICER_MCP_URL", "http://localhost:8002/mcp").rstrip("/"),
}
DEV_MOBILE = os.environ.get("DEV_INSECURE_MOBILE", "").strip()
DEV_OFFICER = os.environ.get("DEV_INSECURE_OFFICER", "").strip()

_jwks = None


def _jwk_client() -> PyJWKClient:
    global _jwks
    if _jwks is None:
        # PyJWKClient caches keys; a rotated key triggers one refetch on unknown `kid`.
        _jwks = PyJWKClient(JWKS_URL, cache_keys=True, lifespan=300, timeout=5)
    return _jwks


class PortalTokenVerifier:
    """Implements mcp's TokenVerifier protocol for one audience + one role."""

    def __init__(self, role: str):
        assert role in ("citizen", "officer")
        self.role = role
        self.audience = RESOURCE_URLS[role]

    def _decode(self, token: str) -> dict:
        key = _jwk_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],  # never accept HS256 / none
            audience=[self.audience, self.audience + "/"],
            options={"require": ["exp", "iss", "sub", "aud"]},
            leeway=10,
        )
        if str(claims["iss"]).rstrip("/") != ISSUER:
            raise jwt.InvalidIssuerError("wrong issuer")
        return claims

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = await asyncio.to_thread(self._decode, token)
        except Exception as e:  # bad signature, expired, wrong aud, JWKS down ...
            log.info("token rejected (%s): %s", self.role, e)
            return None

        scopes = str(claims.get("scope", "")).split()
        sub = str(claims["sub"])
        if self.role == "citizen":
            ok = "citizen" in scopes and sub.startswith("citizen:")
        else:
            # interactive officer sign-in OR an admin-issued program token (role=officer)
            ok = ("officer" in scopes or claims.get("role") == "officer")
            if ok and "officer" not in scopes:
                scopes.append("officer")
        if not ok:
            log.info("token rejected: scope/role mismatch for %s server (scope=%s role=%s sub=%s)",
                     self.role, scopes, claims.get("role"), sub)
            return None

        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id") or claims.get("azp") or "unknown"),
            scopes=scopes,
            expires_at=int(claims["exp"]),
            resource=self.audience,
            subject=sub,
            claims=claims,
        )


def server_kwargs(role: str) -> dict:
    """kwargs for MCPServer(...): turns on 401 + RFC 9728 discovery + JWT verification."""
    if (role == "citizen" and DEV_MOBILE) or (role == "officer" and DEV_OFFICER):
        log.warning("!!! %s server running with AUTH DISABLED (dev bypass) !!!", role)
        return {}
    if not ISSUER:
        raise RuntimeError("PORTAL_ISSUER is not set (public portal URL, = PUBLIC_BASE_URL)")
    return {
        "auth": AuthSettings(
            issuer_url=ISSUER,
            resource_server_url=RESOURCE_URLS[role],
            required_scopes=None,           # role check is done in the verifier
            validate_token_resource=False,  # the verifier already checks `aud`
        ),
        "token_verifier": PortalTokenVerifier(role),
    }


# ── identity helpers used inside tools ─────────────────────────────────────── #

def _subject(kind: str) -> str | None:
    tok = get_access_token()
    if not tok or not tok.subject:
        return None
    k, sep, val = tok.subject.partition(":")
    if sep and k == kind and val:
        return val
    # admin-issued program tokens (role=officer) may carry a bare subject
    if kind == "officer" and not sep:
        return tok.subject
    return None


def citizen_mobile() -> str | None:
    """10-digit mobile of the signed-in citizen, from the token. Never from the model."""
    if DEV_MOBILE:
        return DEV_MOBILE
    val = _subject("citizen")
    return val if val and val.isdigit() and len(val) == 10 else None


def officer_name() -> str | None:
    """Username of the signed-in officer, from the token. Used for decided_by."""
    if DEV_OFFICER:
        return DEV_OFFICER
    return _subject("officer")


def session_expires_at() -> int | None:
    tok = get_access_token()
    return tok.expires_at if tok else None


SIGN_IN_REQUIRED = {
    "error": "Not signed in.",
    "next_step": (
        "Tell the person, in simple words, that they must sign in on the Sewa Setu "
        "portal page that the app opens, then try again. Do not ask for an OTP or "
        "password in the chat."
    ),
}