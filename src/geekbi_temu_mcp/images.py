"""Image loading, validation, and multipart encoding."""

from __future__ import annotations

import base64
import binascii
import mimetypes
import ipaddress
import socket
import ssl
from http.client import HTTPConnection, HTTPSConnection
from urllib.error import HTTPError
import os
import re
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse, urljoin
from urllib.request import Request, url2pathname, urlopen, build_opener, ProxyHandler, HTTPHandler, HTTPSHandler, HTTPRedirectHandler


MAX_IMAGE_SIZE = 10 * 1024 * 1024


def _content_type(value: str | None) -> str | None:
    return value.split(";", 1)[0].strip().lower() if value else None


def _detect(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"avif", b"avis"}:
            return "image/avif"
        if brand in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}:
            return "image/heic"
    return None


def _extension(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
        "image/avif": ".avif",
        "image/heic": ".heic",
        "image/heif": ".heic",
    }.get(content_type, ".img")


def _validate(data: bytes, declared: str | None = None) -> str:
    if not data:
        raise ValueError("Image is empty")
    if len(data) > MAX_IMAGE_SIZE:
        raise ValueError("Image must not exceed 10 MB")
    detected = _detect(data)
    declared = _content_type(declared)
    if detected:
        return detected
    raise ValueError("Unrecognized image format. Use a supported image file.")


def _decode_base64(encoded: str, declared: str | None = None) -> tuple[bytes, str, str]:
    if len(encoded) > (MAX_IMAGE_SIZE * 4 // 3) + 16:
        raise ValueError("Image must not exceed 10 MB")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("Invalid Base64 image") from error
    content_type = _validate(data, declared)
    return data, content_type, "image" + _extension(content_type)


def _read_data_uri(source: str) -> tuple[bytes, str, str]:
    match = re.fullmatch(
        r"data:([^;,]+)?(?:;charset=[^;,]+)?;base64,(.+)",
        source,
        re.DOTALL,
    )
    if not match:
        raise ValueError("Invalid image Data URI")
    return _decode_base64(match.group(2), match.group(1))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public_image_opener(source: str):
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Image URL must be HTTP(S) without credentials")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in (80, 443):
        raise ValueError("Remote image URLs must use port 80 or 443")
    addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    def unsafe_address(value):
        address = ipaddress.ip_address(value)
        return not address.is_global or address.is_multicast or address.is_reserved

    if not addresses or any(unsafe_address(item[4][0]) for item in addresses):
        raise ValueError("Remote images must use public IP addresses; private networks are blocked")
    pinned_ip = addresses[0][4][0]

    class PinnedHTTPConnection(HTTPConnection):
        def connect(self):
            self.sock = socket.create_connection((pinned_ip, port), self.timeout)

    class PinnedHTTPSConnection(HTTPSConnection):
        def connect(self):
            raw = socket.create_connection((pinned_ip, port), self.timeout)
            try:
                self.sock = self._context.wrap_socket(raw, server_hostname=parsed.hostname)
            except BaseException:
                raw.close()
                raise

    class PinnedHTTPHandler(HTTPHandler):
        def http_open(self, req):
            return self.do_open(PinnedHTTPConnection, req)

    class PinnedHTTPSHandler(HTTPSHandler):
        def https_open(self, req):
            return self.do_open(PinnedHTTPSConnection, req, context=ssl.create_default_context())

    return build_opener(ProxyHandler({}), _NoRedirect(), PinnedHTTPHandler(), PinnedHTTPSHandler())


def _read_remote(source: str, timeout: float) -> tuple[bytes, str, str]:
    remote = os.getenv("GEEKBI_REMOTE_MODE") == "1"
    for _ in range(6):
        request = Request(source, headers={"User-Agent": "GeekBI-Temu-Research-MCP"})
        opener = _public_image_opener(source).open if remote else urlopen
        try:
            with opener(request, timeout=timeout) as response:
                data = response.read(MAX_IMAGE_SIZE + 1)
                content_type = _validate(data, response.headers.get_content_type())
                filename = Path(unquote(urlparse(response.geturl()).path)).name
                return data, content_type, filename or "image" + _extension(content_type)
        except HTTPError as error:
            location = error.headers.get("Location")
            if not remote or error.code not in (301, 302, 303, 307, 308) or not location:
                raise
            source = urljoin(source, location)
            error.close()
    raise ValueError("Too many image URL redirects")


def _read_local(source: str) -> tuple[bytes, str, str]:
    parsed = urlparse(source)
    if parsed.scheme == "file":
        path_text = unquote(parsed.path)
        if parsed.netloc and parsed.netloc != "localhost":
            path_text = f"//{parsed.netloc}{path_text}"
        path_text = url2pathname(path_text)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:", path_text):
            path_text = path_text[1:]
        path = Path(path_text)
    else:
        path = Path(source).expanduser()
    if not path.is_file():
        raise ValueError(f"Image file not found: {path}")
    if path.stat().st_size > MAX_IMAGE_SIZE:
        raise ValueError("Image must not exceed 10 MB")
    with path.open("rb") as handle:
        data = handle.read(MAX_IMAGE_SIZE + 1)
    guessed, _ = mimetypes.guess_type(path.name)
    return data, _validate(data, guessed), path.name


def read_image(source: str, timeout: float) -> tuple[bytes, str, str]:
    if source.startswith("data:"):
        return _read_data_uri(source)
    if source.startswith("base64:"):
        return _decode_base64(source.removeprefix("base64:"))
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        return _read_remote(source, timeout)
    if parsed.scheme not in {"", "file"}:
        raise ValueError("Supported image sources: local file, file/http/https URL, Data URI, or Base64")
    if os.getenv("GEEKBI_REMOTE_MODE") == "1":
        raise ValueError("Local image files are disabled on the remote server; use a public URL or Base64")
    return _read_local(source)


def build_multipart(data: bytes, content_type: str, filename: str) -> tuple[bytes, str]:
    boundary = "----GeekBIBoundary" + uuid.uuid4().hex
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    if not safe_filename:
        safe_filename = "image" + _extension(content_type)
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    body = header + data + f"\r\n--{boundary}--\r\n".encode("ascii")
    return body, f"multipart/form-data; boundary={boundary}"
