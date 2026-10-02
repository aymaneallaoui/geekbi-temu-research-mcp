"""Single-account OAuth login for Claude.ai, using the MCP SDK protocol handlers."""

from __future__ import annotations

import getpass
import re
from contextlib import contextmanager
import hashlib
import hmac
import html
import json
import os
import secrets
import sqlite3
import sys
import time
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

import anyio
from mcp.server.auth.provider import (
    AccessToken, AuthorizationCode, AuthorizationParams, AuthorizeError,
    RefreshToken, RegistrationError, TokenError, construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import RequestBodyLimitMiddleware, TransportSecuritySettings
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

SCOPE = "temu:read"
DEFAULT_REDIRECTS = "https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback"
OWNER_PASSWORD_FILE = "owner-password.json"


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Choose a password of at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    if len(password) > 1024:
        return False
    try:
        scheme, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def password_main() -> None:
    """Print a salted hash without putting the password in shell history."""
    first = getpass.getpass("Password (at least 12 characters): ")
    if first != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    print(hash_password(first))


def load_owner_password_hash(state_dir: Path) -> str | None:
    path = state_dir / OWNER_PASSWORD_FILE
    try:
        encoded = json.loads(path.read_text())["password_hash"]
    except FileNotFoundError:
        return None
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"{path} is unreadable; delete it to generate a new owner password") from error
    if not isinstance(encoded, str):
        raise ValueError(f"{path} is unreadable; delete it to generate a new owner password")
    return encoded


def store_owner_password_hash(state_dir: Path, encoded: str) -> bool:
    """Persist only the hash, readable by the owner alone. Returns False if a hash is already stored."""
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = state_dir / OWNER_PASSWORD_FILE
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump({"password_hash": encoded}, handle)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


@dataclass(frozen=True)
class RemoteConfig:
    public_url: str
    email: str
    password_hash: str
    state_dir: Path
    redirect_uris: tuple[str, ...]

    def __post_init__(self):
        parsed = urlsplit(self.public_url)
        local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or not parsed.hostname:
            raise ValueError("MCP_PUBLIC_URL must be HTTPS (HTTP is allowed only on loopback for development)")
        if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("MCP_PUBLIC_URL must be an origin, without a path, query, or credentials")
        if "@" not in self.email or len(self.email) > 254:
            raise ValueError("MCP_LOGIN_EMAIL must be a valid email address")
        try:
            scheme, salt, digest = self.password_hash.split("$")
            valid_hash = scheme == "scrypt" and len(bytes.fromhex(salt)) == 16 and len(bytes.fromhex(digest)) == 64
        except ValueError:
            valid_hash = False
        if not valid_hash:
            raise ValueError("MCP_PASSWORD_HASH must be a geekbi-password-hash scrypt hash; leave it unset to generate one")
        if not self.redirect_uris:
            raise ValueError("At least one exact MCP_OAUTH_REDIRECT_URIS callback is required")
        for uri in self.redirect_uris:
            target = urlsplit(uri)
            if not target.hostname or target.fragment or target.username or target.password or not (
                target.scheme == "https" or (target.scheme == "http" and target.hostname in ("127.0.0.1", "localhost", "::1"))
            ):
                raise ValueError("OAuth callbacks must be HTTPS or loopback HTTP URLs")

    @classmethod
    def from_env(cls):
        state_dir = Path(os.environ.get("MCP_STATE_DIR", "/data"))
        password_hash = os.environ.get("MCP_PASSWORD_HASH", "").strip()
        generated = None
        if not password_hash:
            password_hash = load_owner_password_hash(state_dir)
            if password_hash is None:
                generated = secrets.token_urlsafe(24)
                password_hash = hash_password(generated)
        config = cls(
            public_url=os.environ.get("MCP_PUBLIC_URL", "").strip().rstrip("/"),
            email=os.environ.get("MCP_LOGIN_EMAIL", "").strip().casefold(),
            password_hash=password_hash,
            state_dir=state_dir,
            redirect_uris=tuple(x.strip() for x in os.environ.get("MCP_OAUTH_REDIRECT_URIS", DEFAULT_REDIRECTS).split(",") if x.strip()),
        )
        if generated:
            if not store_owner_password_hash(state_dir, password_hash):
                return replace(config, password_hash=load_owner_password_hash(state_dir))
            print(f"GENERATED OWNER PASSWORD (shown only once, save it now; sign in as {config.email}): {generated}", file=sys.stderr, flush=True)
        return config

    @property
    def resource(self):
        return self.public_url + "/mcp"


class OAuthProvider:
    """Small persistent store. Bearer tokens/codes are indexed by SHA-256, never stored raw."""

    def __init__(self, config: RemoteConfig):
        self.config = config
        config.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db_path = config.state_dir / "oauth.sqlite3"
        self.login_attempts: deque[float] = deque()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, key TEXT, payload TEXT, expires REAL, family TEXT, PRIMARY KEY(kind,key))")
            db.execute("CREATE INDEX IF NOT EXISTS record_family ON records(family)")
            db.execute("CREATE INDEX IF NOT EXISTS record_expiry ON records(expires)")
            fingerprint = hashlib.sha256((config.email + config.password_hash + config.public_url).encode()).hexdigest()
            previous = db.execute("SELECT payload FROM records WHERE kind='config'").fetchone()
            if previous and previous[0] != fingerprint:
                db.execute("DELETE FROM records WHERE kind != 'client'")
            db.execute("INSERT OR REPLACE INTO records VALUES ('config','fingerprint',?,NULL,NULL)", (fingerprint,))
        self.db_path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def key(value: str):
        return hashlib.sha256(value.encode()).hexdigest()

    def put(self, kind, key, value, expires=None, family=None):
        import json
        with self.connect() as db:
            db.execute("DELETE FROM records WHERE expires IS NOT NULL AND expires <= ?", (time.time(),))
            if db.execute("SELECT count(*) FROM records").fetchone()[0] >= 10000:
                raise ValueError("Authentication store is full; try again later")
            db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)", (kind, self.key(key), json.dumps(value), expires, family))

    def get(self, kind, key, *, consume=False):
        import json
        with self.connect() as db:
            if consume:
                db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload,expires FROM records WHERE kind=? AND key=?", (kind, self.key(key))).fetchone()
            if consume:
                db.execute("DELETE FROM records WHERE kind=? AND key=?", (kind, self.key(key)))
            if not row or (row[1] is not None and row[1] <= time.time()):
                return None
            return json.loads(row[0])

    async def get_client(self, client_id):
        data = self.get("client", client_id)
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def register_client(self, client_info):
        if not client_info.redirect_uris or any(str(uri) not in self.config.redirect_uris for uri in client_info.redirect_uris):
            raise RegistrationError("invalid_redirect_uri", "Callback must exactly match a configured Claude callback")
        if not set(client_info.grant_types).issubset({"authorization_code", "refresh_token"}):
            raise RegistrationError("invalid_client_metadata", "Only authorization code and refresh grants are supported")
        with self.connect() as db:
            if db.execute("SELECT count(*) FROM records WHERE kind='client'").fetchone()[0] >= 1000:
                raise RegistrationError("invalid_client_metadata", "Client limit reached")
        self.put("client", client_info.client_id, client_info.model_dump(mode="json"))

    async def authorize(self, client, params: AuthorizationParams):
        if params.resource not in (None, self.config.resource):
            raise AuthorizeError("invalid_target", "Unknown MCP resource")
        if str(params.redirect_uri) not in self.config.redirect_uris:
            raise AuthorizeError("invalid_request", "Callback is not allowed")
        if not (params.scopes or [SCOPE]) == [SCOPE]:
            raise AuthorizeError("invalid_scope", "Only temu:read is supported")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", params.code_challenge):
            raise AuthorizeError("invalid_request", "A valid S256 PKCE challenge is required")
        ticket = secrets.token_urlsafe(32)
        self.put("pending", ticket, {"client_id": client.client_id, "params": params.model_dump(mode="json"), "csrf": secrets.token_urlsafe(32)}, time.time() + 600)
        return self.config.public_url + "/login?ticket=" + ticket

    async def load_authorization_code(self, client, authorization_code):
        data = self.get("code", authorization_code)
        return AuthorizationCode(code=authorization_code, **data) if data and data["client_id"] == client.client_id else None

    async def exchange_authorization_code(self, client, authorization_code):
        if not self.get("code", authorization_code.code, consume=True):
            raise TokenError("invalid_grant", "Authorization code already used or expired")
        return self.issue(client.client_id, authorization_code.scopes)

    def issue(self, client_id, scopes, family=None):
        family = family or secrets.token_hex(16)
        now = int(time.time())
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        common = dict(client_id=client_id, scopes=scopes, resource=self.config.resource, subject=self.config.email)
        self.put("access", access, dict(**common, expires_at=now + 3600), now + 3600, family)
        self.put("refresh", refresh, dict(**common, expires_at=now + 30 * 86400, family=family), now + 30 * 86400, family)
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=3600, refresh_token=refresh, scope=" ".join(scopes))

    async def load_refresh_token(self, client, refresh_token):
        data = self.get("refresh", refresh_token)
        if not data or data["client_id"] != client.client_id:
            return None
        return RefreshToken(token=refresh_token, **{k: v for k, v in data.items() if k != "family"})

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        data = self.get("refresh", refresh_token.token, consume=True)
        if not data:
            raise TokenError("invalid_grant", "Refresh token already used or expired")
        if not set(scopes).issubset(data["scopes"]):
            raise TokenError("invalid_scope", "Cannot increase scopes")
        return self.issue(client.client_id, scopes, data["family"])

    async def load_access_token(self, token):
        data = self.get("access", token)
        return AccessToken(token=token, **data) if data else None

    async def revoke_token(self, token):
        with self.connect() as db:
            row = db.execute("SELECT family FROM records WHERE key=? AND kind IN ('access','refresh')", (self.key(token.token),)).fetchone()
            if row:
                db.execute("DELETE FROM records WHERE family=?", (row[0],))

    def login_limited(self):
        now = time.monotonic()
        while self.login_attempts and self.login_attempts[0] < now - 300:
            self.login_attempts.popleft()
        if len(self.login_attempts) >= 10:
            return True
        self.login_attempts.append(now)
        return False

    async def login(self, request: Request):
        ticket = request.query_params.get("ticket", "")
        pending = self.get("pending", ticket)
        if not pending:
            return HTMLResponse("Login request expired. Reconnect the connector in Claude.", status_code=400)
        csrf = pending["csrf"]
        if request.method == "GET":
            callback = html.escape(str(pending["params"]["redirect_uri"]))
            response = HTMLResponse(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>GeekBI MCP sign in</title>
<body><main><h1>Sign in to GeekBI Temu MCP</h1><p>Allow this connector to use your Temu research tools.</p><p>Return to: {callback}</p>
<form method="post"><input type="hidden" name="csrf" value="{html.escape(csrf)}"><p><label>Email <input name="email" type="email" autocomplete="username" maxlength="254" required></label></p><p><label>Password <input name="password" type="password" autocomplete="current-password" maxlength="1024" required></label></p><button type="submit">Sign in and authorize</button></form></main></body></html>''')
            response.set_cookie("geekbi_login", csrf, httponly=True, secure=self.config.public_url.startswith("https:"), samesite="lax", max_age=600, path="/login")
            return response
        if request.headers.get("origin") not in (None, self.config.public_url):
            return HTMLResponse("Invalid login origin", status_code=403)
        form = await request.form(max_fields=3, max_files=0)
        if not hmac.compare_digest(str(form.get("csrf", "")).encode(), csrf.encode()) or not hmac.compare_digest(request.cookies.get("geekbi_login", "").encode(), csrf.encode()):
            return HTMLResponse("Invalid login request. Reconnect in Claude.", status_code=403)
        if self.login_limited():
            return HTMLResponse("Too many sign-in attempts. Try again in five minutes.", status_code=429, headers={"Retry-After": "300"})
        password_ok = await anyio.to_thread.run_sync(verify_password, str(form.get("password", "")), self.config.password_hash)
        email_ok = hmac.compare_digest(str(form.get("email", "")).strip().casefold().encode(), self.config.email.casefold().encode())
        if not (email_ok and password_ok):
            return HTMLResponse("Incorrect email or password. Go back to retry.", status_code=401)
        pending = self.get("pending", ticket, consume=True)
        if not pending:
            return HTMLResponse("Login request already used or expired", status_code=400)
        params = AuthorizationParams.model_validate(pending["params"])
        code = secrets.token_urlsafe(32)
        record = AuthorizationCode(code=code, scopes=params.scopes or [SCOPE], expires_at=time.time() + 300, client_id=pending["client_id"], code_challenge=params.code_challenge, redirect_uri=params.redirect_uri, redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly, resource=self.config.resource, subject=self.config.email)
        self.put("code", code, record.model_dump(mode="json", exclude={"code"}), record.expires_at)
        response = RedirectResponse(construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state), status_code=303)
        response.delete_cookie("geekbi_login", path="/login")
        return response


class SecurityHeaders:
    def __init__(self, app):
        self.app = app
        self.windows: dict[str, deque[float]] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Global limits suit this single-account server and cannot be bypassed by spoofing proxy headers.
        path = scope["path"]
        limit = {"/register": 10, "/authorize": 30, "/token": 120, "/mcp": 120, "/login": 60}.get(path)
        if limit:
            window = self.windows.setdefault(path, deque())
            now = time.monotonic()
            while window and window[0] < now - 60:
                window.popleft()
            if len(window) >= limit:
                return await JSONResponse({"error": "rate_limited"}, status_code=429, headers={"Retry-After": "60"})(scope, receive, send)
            window.append(now)
        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers = [(key, value) for key, value in headers if key.lower() != b"cache-control"]
                headers.extend([(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"), (b"content-security-policy", b"default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")])
                message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, secure_send)


def create_app(config: RemoteConfig | None = None):
    from mcp.server import MCPServer
    from . import server
    config = config or RemoteConfig.from_env()
    # Upstream GeekBI login also needs durable state, separate from connector OAuth tokens.
    os.environ["GEEKBI_AUTH_PATH"] = str(config.state_dir / "geekbi-auth.json")
    os.environ["GEEKBI_REMOTE_MODE"] = "1"
    provider = OAuthProvider(config)
    auth = AuthSettings(issuer_url=config.public_url, resource_server_url=config.resource, validate_token_resource=True, required_scopes=[SCOPE], client_registration_options=ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]), revocation_options=RevocationOptions(enabled=True))
    mcp = MCPServer(name="geekbi-temu-research", title="GeekBI Temu Market Research", description="Temu market research tools", instructions=server.SERVER_INSTRUCTIONS, auth=auth, auth_server_provider=provider)
    for name in ("temu_site_list", "temu_goods_search", "temu_image_search", "temu_mall_search", "temu_category_search", "temu_keyword_search", "temu_review_search"):
        mcp.add_tool(getattr(server, name))
    host = urlsplit(config.public_url).netloc
    app = mcp.streamable_http_app(json_response=True, stateless_http=True, max_request_body_size=15 * 1024 * 1024, transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[host, "localhost:*", "127.0.0.1:*"], allowed_origins=[config.public_url]))
    # SDK protocol handlers validate PKCE/client/redirect; explicitly reject foreign token resources.
    from mcp.server.auth.handlers.token import TokenHandler
    from mcp.server.auth.handlers.metadata import MetadataHandler
    from mcp.server.auth.middleware.client_auth import ClientAuthenticator
    from mcp.server.auth.routes import build_metadata, cors_middleware

    class BoundTokenHandler(TokenHandler):
        async def handle(self, request):
            form = await request.form()
            if form.get("resource") not in (None, config.resource):
                return JSONResponse({"error": "invalid_target"}, status_code=400)
            return await super().handle(request)

    token_handler = BoundTokenHandler(provider, ClientAuthenticator(provider))
    metadata = build_metadata(auth.issuer_url, None, auth.client_registration_options, auth.revocation_options)
    metadata.token_endpoint_auth_methods_supported = ["client_secret_post", "client_secret_basic", "none"]
    replacements = {
        "/token": Route("/token", cors_middleware(token_handler.handle, ["POST", "OPTIONS"]), methods=["POST", "OPTIONS"]),
        "/.well-known/oauth-authorization-server": Route("/.well-known/oauth-authorization-server", cors_middleware(MetadataHandler(metadata).handle, ["GET", "OPTIONS"]), methods=["GET", "OPTIONS"]),
    }
    app.router.routes = [replacements.get(route.path, route) for route in app.routes]
    app.routes.extend([Route("/login", provider.login, methods=["GET", "POST"]), Route("/healthz", lambda request: JSONResponse({"status": "ok"}))])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(config.public_url).hostname, "localhost", "127.0.0.1"])
    app.add_middleware(RequestBodyLimitMiddleware, max_body_size=15 * 1024 * 1024)
    app.add_middleware(SecurityHeaders)
    app.state.oauth_provider = provider
    return app
