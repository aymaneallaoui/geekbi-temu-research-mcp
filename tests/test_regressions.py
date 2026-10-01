import io
import json
import math
import socket
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError

from geekbi_temu_mcp.auth import ActionRequired, AuthManager, GeekBIError
from geekbi_temu_mcp.client import _environment_timeout
from geekbi_temu_mcp.images import _public_image_opener, _validate, read_image
from geekbi_temu_mcp.models import GoodsSearchInput


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0", "301"])
def test_nonfinite_and_invalid_timeouts_are_rejected(monkeypatch, value):
    monkeypatch.setenv("GEEKBI_REQUEST_TIMEOUT", value)
    with pytest.raises(GeekBIError):
        _environment_timeout()


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_query_values_are_rejected(value):
    with pytest.raises(ValidationError):
        GoodsSearchInput(soldMin=value)


def test_mixed_date_timezones_raise_validation_error():
    with pytest.raises(ValidationError, match="timezone"):
        GoodsSearchInput(onSaleTimeMin=datetime(2026, 1, 1), onSaleTimeMax=datetime(2026, 2, 1, tzinfo=timezone.utc))


def test_remote_local_file_access_is_blocked(monkeypatch, tmp_path):
    image = tmp_path / "private.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nprivate-data")
    monkeypatch.setenv("GEEKBI_REMOTE_MODE", "1")
    for source in (str(image), image.as_uri()):
        with pytest.raises(ValueError, match="disabled"):
            read_image(source, 1)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1", "0.0.0.0", "224.0.0.1"])
def test_private_and_nonpublic_image_addresses_are_blocked(ip):
    with patch("geekbi_temu_mcp.images.socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]):
        with pytest.raises(ValueError, match="public IP"):
            _public_image_opener("https://image.example/file.png")


def test_mixed_public_and_private_dns_is_blocked():
    addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ("8.8.8.8", "10.0.0.1")]
    with patch("geekbi_temu_mcp.images.socket.getaddrinfo", return_value=addresses):
        with pytest.raises(ValueError, match="public IP"):
            _public_image_opener("https://image.example/file.png")


def test_content_type_cannot_disguise_nonimage_data():
    with pytest.raises(ValueError, match="Unrecognized"):
        _validate(b"private server data", "image/png")


def test_oversized_upstream_response_is_rejected():
    response = MagicMock()
    response.read.return_value = b"a" * (20 * 1024 * 1024 + 1)
    with pytest.raises(GeekBIError, match="20 MB"):
        AuthManager._read_json_response(response)


def test_upstream_device_login_and_authenticated_retry(tmp_path):
    manager = AuthManager("https://api.example", state_path=tmp_path / "state.json")
    challenge = {"code": 401, "msg": "Sign in", "data": {"error": "AUTH_REQUIRED", "deviceCode": "private-device-code", "jumpUrl": "https://example/login", "expiresIn": 600}}
    error = HTTPError("https://api.example/data", 401, "unauthorized", {}, io.BytesIO(json.dumps(challenge).encode()))
    with patch("geekbi_temu_mcp.auth.urlopen", side_effect=error):
        with pytest.raises(ActionRequired) as action:
            manager.request_json("https://api.example/data", 1)
        assert "private-device-code" not in str(action.value.public_payload())
    token_response = MagicMock()
    token_response.__enter__.return_value.read.return_value = json.dumps({"code": 0, "data": {"accessToken": "upstream-token", "expiresIn": 3600}}).encode()
    data_response = MagicMock()
    data_response.__enter__.return_value.read.return_value = b'{"code":0,"data":{"list":[]}}'
    with patch("geekbi_temu_mcp.auth.urlopen", side_effect=[token_response, data_response]) as opener:
        result = manager.request_json("https://api.example/data", 1)
        assert result["code"] == 0
        assert opener.call_args_list[1].args[0].get_header("Token") == "Bearer upstream-token"
    assert (tmp_path / "state.json").stat().st_mode & 0o777 == 0o600


def test_upstream_redirects_do_not_leak_tokens():
    from geekbi_temu_mcp.auth import _SameOriginRedirect
    from urllib.request import Request
    request = Request("https://api.example/data", headers={"token": "Bearer private"})
    with pytest.raises(GeekBIError, match="different origin"):
        _SameOriginRedirect().redirect_request(request, None, 302, "redirect", {}, "https://attacker.example/data")
    with pytest.raises(GeekBIError, match="different origin"):
        _SameOriginRedirect().redirect_request(request, None, 302, "redirect", {}, "http://api.example/data")
