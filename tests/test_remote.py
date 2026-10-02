import base64
import hashlib
import json
import re
from urllib.parse import parse_qs, urlsplit

import anyio
import httpx
import pytest

from geekbi_temu_mcp.remote import DEFAULT_REDIRECTS, RemoteConfig, create_app, hash_password

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
PASSWORD = "test-password-for-login"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def remote_config(tmp_path, monkeypatch):
    # create_app configures single-process remote-mode environment; keep it scoped to this test.
    monkeypatch.setenv("GEEKBI_REMOTE_MODE", "0")
    monkeypatch.setenv("GEEKBI_AUTH_PATH", str(tmp_path / "old-auth.json"))
    return RemoteConfig("https://mcp.example.com", "owner@example.com", hash_password(PASSWORD), tmp_path, (CALLBACK,))


async def register(client, redirect=CALLBACK):
    return await client.post("/register", json={"client_name": "Claude", "redirect_uris": [redirect], "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "client_secret_post"})


async def login_code(client, credentials, password=PASSWORD):
    verifier = "a" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    response = await client.get("/authorize", params={"client_id": credentials["client_id"], "redirect_uri": CALLBACK, "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256", "scope": "temu:read", "resource": "https://mcp.example.com/mcp", "state": "client-state"})
    assert response.status_code == 302, response.text
    login_url = response.headers["location"]
    page = await client.get(login_url)
    assert page.status_code == 200
    csrf = re.search('name="csrf" value="([^"]+)"', page.text).group(1)
    form = {"csrf": csrf, "email": "owner@example.com", "password": password}
    denied = await client.post(login_url, data={**form, "csrf": "wrong"})
    assert denied.status_code == 403
    denied = await client.post(login_url, data={**form, "password": "wrong-password"})
    assert denied.status_code == 401
    response = await client.post(login_url, data=form)
    assert response.status_code == 303, response.text
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["state"] == ["client-state"]
    return query["code"][0], verifier


@pytest.mark.anyio
async def test_full_oauth_and_mcp_protocol(remote_config):
    app = create_app(remote_config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=remote_config.public_url) as client:
            denied = await client.post("/mcp", json={})
            assert denied.status_code == 401
            assert 'resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp"' in denied.headers["www-authenticate"]
            metadata = (await client.get("/.well-known/oauth-authorization-server")).json()
            assert metadata["code_challenge_methods_supported"] == ["S256"]
            resource = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()
            assert resource["resource"] == remote_config.resource
            assert (await register(client, "https://attacker.example/callback")).status_code == 400
            credentials = (await register(client)).json()
            code, verifier = await login_code(client, credentials)
            grant = {"grant_type": "authorization_code", "client_id": credentials["client_id"], "client_secret": credentials["client_secret"], "code": code, "redirect_uri": CALLBACK, "code_verifier": verifier, "resource": remote_config.resource}
            bad_pkce = await client.post("/token", data={**grant, "code_verifier": "wrong"})
            assert bad_pkce.status_code == 400
            assert (await client.post("/token", data={**grant, "resource": "https://attacker.example/mcp"})).status_code == 400
            response = await client.post("/token", data=grant)
            assert response.status_code == 200, response.text
            tokens = response.json()
            assert (await client.post("/token", data=grant)).status_code == 400
            headers = {"Authorization": "Bearer " + tokens["access_token"], "Accept": "application/json, text/event-stream"}
            init = await client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
            assert init.status_code == 200, init.text
            assert init.json()["result"]["serverInfo"]["name"] == "geekbi-temu-research"
            headers["MCP-Protocol-Version"] = "2025-11-25"
            tools = await client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            assert tools.status_code == 200, tools.text
            listed_tools = tools.json()["result"]["tools"]
            assert len(listed_tools) == 7
            assert not re.search(r"[\u4e00-\u9fff]", str(listed_tools))
            # Execute a data tool through the authenticated transport, with a mocked upstream.
            from unittest.mock import patch
            from geekbi_temu_mcp.client import GeekBIClient
            with patch.object(GeekBIClient, "goods", return_value={"code": 0, "data": {"list": [], "total": 0}}):
                called = await client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "temu_goods_search", "arguments": {"query": {"keyword": "desk lamp"}}}})
            assert called.status_code == 200, called.text
            assert called.json()["result"]["structuredContent"]["data"]["total"] == 0
            refresh = {"grant_type": "refresh_token", "client_id": credentials["client_id"], "client_secret": credentials["client_secret"], "refresh_token": tokens["refresh_token"], "resource": remote_config.resource}
            rotated = await client.post("/token", data=refresh)
            assert rotated.status_code == 200, rotated.text
            assert rotated.json()["refresh_token"] != tokens["refresh_token"]
            assert (await client.post("/token", data=refresh)).status_code == 400
            # State is durable across creating a new provider/server process.
            from geekbi_temu_mcp.remote import OAuthProvider
            restarted = OAuthProvider(remote_config)
            assert await restarted.load_access_token(rotated.json()["access_token"])
            token = await restarted.load_access_token(tokens["access_token"])
            await restarted.revoke_token(token)
            assert await restarted.load_access_token(rotated.json()["access_token"]) is None


@pytest.mark.anyio
async def test_login_rate_limit_and_credential_change(remote_config):
    from geekbi_temu_mcp.remote import OAuthProvider
    provider = OAuthProvider(remote_config)
    tokens = provider.issue("test-client", ["temu:read"])
    assert [provider.login_limited() for _ in range(11)] == [False] * 10 + [True]
    updated = RemoteConfig(remote_config.public_url, remote_config.email, hash_password("new-strong-password"), remote_config.state_dir, remote_config.redirect_uris)
    assert await OAuthProvider(updated).load_access_token(tokens.access_token) is None


@pytest.mark.anyio
async def test_login_origin_check_matches_browser_headers(remote_config):
    app = create_app(remote_config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=remote_config.public_url) as client:
            credentials = (await register(client)).json()
            response = await client.get("/authorize", params={"client_id": credentials["client_id"], "redirect_uri": CALLBACK, "response_type": "code", "code_challenge": "a" * 43, "code_challenge_method": "S256", "scope": "temu:read", "resource": remote_config.resource, "state": "s"})
            login_url = response.headers["location"]
            page = await client.get(login_url)
            assert page.headers["referrer-policy"] == "same-origin"
            form = {"csrf": re.search('name="csrf" value="([^"]+)"', page.text).group(1), "email": "owner@example.com", "password": PASSWORD}
            for origin in ("null", "https://attacker.example", "https://mcp.example.com.attacker.example"):
                denied = await client.post(login_url, data=form, headers={"Origin": origin})
                assert (denied.status_code, denied.text) == (403, "Invalid login origin")
            accepted = await client.post(login_url, data=form, headers={"Origin": remote_config.public_url})
            assert accepted.status_code == 303
            assert accepted.headers["location"].startswith(CALLBACK + "?")


@pytest.mark.anyio
async def test_login_csp_allows_only_callback_origins(tmp_path, monkeypatch):
    monkeypatch.setenv("GEEKBI_REMOTE_MODE", "0")
    monkeypatch.setenv("GEEKBI_AUTH_PATH", str(tmp_path / "old-auth.json"))
    redirects = tuple(DEFAULT_REDIRECTS.split(",")) + ("https://claude.ai/other_callback",)
    app = create_app(RemoteConfig("https://mcp.example.com", "owner@example.com", hash_password(PASSWORD), tmp_path, redirects))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://mcp.example.com") as client:
        login_csp = (await client.get("/login?ticket=missing")).headers["content-security-policy"]
        other_csp = (await client.get("/healthz")).headers["content-security-policy"]
    assert "form-action 'self' https://claude.ai https://claude.com;" in login_csp
    assert login_csp.count("https://claude.ai") == 1 and "attacker.example" not in login_csp and "/api/" not in login_csp
    assert login_csp.replace(" https://claude.ai https://claude.com", "") == other_csp == "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"


def test_configuration_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        RemoteConfig("http://public.example", "owner@example.com", hash_password(PASSWORD), tmp_path, (CALLBACK,))
    with pytest.raises(ValueError):
        RemoteConfig("https://public.example", "owner@example.com", "plaintext-password", tmp_path, (CALLBACK,))


@pytest.fixture
def generated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GEEKBI_REMOTE_MODE", "0")
    monkeypatch.setenv("GEEKBI_AUTH_PATH", str(tmp_path / "old-auth.json"))
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp.example.com")
    monkeypatch.setenv("MCP_LOGIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("MCP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("MCP_PASSWORD_HASH", raising=False)
    return tmp_path / "state" / "owner-password.json"


def generated_password(output):
    found = re.findall(r"GENERATED OWNER PASSWORD .*: (\S+)$", output, re.MULTILINE)
    assert len(found) == 1, output
    return found[0]


def load_token(provider, token):
    return anyio.run(provider.load_access_token, token)


def test_generated_password_persists_and_tokens_survive_restart(generated_env, capsys):
    from geekbi_temu_mcp.remote import OAuthProvider, verify_password
    first = RemoteConfig.from_env()
    password = generated_password(capsys.readouterr().err)
    assert len(password) >= 32 and verify_password(password, first.password_hash)
    assert generated_env.stat().st_mode & 0o777 == 0o600
    stored = generated_env.read_text()
    assert password not in stored and json.loads(stored) == {"password_hash": first.password_hash}
    tokens = OAuthProvider(first).issue("test-client", ["temu:read"])
    second = RemoteConfig.from_env()
    assert second.password_hash == first.password_hash
    assert password not in capsys.readouterr().err
    assert load_token(OAuthProvider(second), tokens.access_token)


def test_deleting_stored_hash_rotates_password(generated_env, capsys):
    from geekbi_temu_mcp.remote import OAuthProvider
    first = RemoteConfig.from_env()
    old_password = generated_password(capsys.readouterr().err)
    tokens = OAuthProvider(first).issue("test-client", ["temu:read"])
    generated_env.unlink()
    rotated = RemoteConfig.from_env()
    assert generated_password(capsys.readouterr().err) != old_password
    assert rotated.password_hash != first.password_hash
    assert not load_token(OAuthProvider(rotated), tokens.access_token)


def test_explicit_password_hash_wins(generated_env, capsys, monkeypatch):
    explicit = hash_password(PASSWORD)
    monkeypatch.setenv("MCP_PASSWORD_HASH", explicit)
    assert RemoteConfig.from_env().password_hash == explicit
    assert not generated_env.exists()
    assert "PASSWORD" not in capsys.readouterr().err
    monkeypatch.delenv("MCP_PASSWORD_HASH")
    generated = RemoteConfig.from_env()
    monkeypatch.setenv("MCP_PASSWORD_HASH", explicit)
    assert RemoteConfig.from_env().password_hash == explicit != generated.password_hash


def test_invalid_configuration_does_not_consume_generated_password(generated_env, capsys, monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://public.example")
    with pytest.raises(ValueError):
        RemoteConfig.from_env()
    assert not generated_env.exists()
    assert "PASSWORD" not in capsys.readouterr().err
    generated_env.parent.mkdir()
    generated_env.write_text("not json")
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp.example.com")
    with pytest.raises(ValueError, match="delete it"):
        RemoteConfig.from_env()


@pytest.mark.anyio
async def test_login_with_generated_password(generated_env, capsys):
    config = RemoteConfig.from_env()
    password = generated_password(capsys.readouterr().err)
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=config.public_url) as client:
            credentials = (await register(client)).json()
            code, _ = await login_code(client, credentials, password)
            assert code
