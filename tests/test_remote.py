import base64
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from geekbi_temu_mcp.remote import RemoteConfig, create_app, hash_password

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


async def login_code(client, credentials):
    verifier = "a" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    response = await client.get("/authorize", params={"client_id": credentials["client_id"], "redirect_uri": CALLBACK, "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256", "scope": "temu:read", "resource": "https://mcp.example.com/mcp", "state": "client-state"})
    assert response.status_code == 302, response.text
    login_url = response.headers["location"]
    page = await client.get(login_url)
    assert page.status_code == 200
    csrf = re.search('name="csrf" value="([^"]+)"', page.text).group(1)
    form = {"csrf": csrf, "email": "owner@example.com", "password": PASSWORD}
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


def test_configuration_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        RemoteConfig("http://public.example", "owner@example.com", hash_password(PASSWORD), tmp_path, (CALLBACK,))
    with pytest.raises(ValueError):
        RemoteConfig("https://public.example", "owner@example.com", "plaintext-password", tmp_path, (CALLBACK,))
