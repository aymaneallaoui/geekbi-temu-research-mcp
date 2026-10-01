"""GeekBI Temu API client."""

from __future__ import annotations

import math
import os
from typing import Any
from urllib.parse import urlencode, urlparse

from .auth import AuthManager, GeekBIError, response_message
from .images import build_multipart, read_image
from .models import (
    CategorySearchInput,
    GoodsSearchInput,
    ImageSearchInput,
    KeywordSearchInput,
    MallSearchInput,
    QueryInput,
    ReviewSearchInput,
)


DEFAULT_BASE_URL = "https://openapi.geekbi.com"
ENDPOINTS = {
    "sites": "/api/v1/temu/site/ai-list",
    "goods": "/api/v1/temu/goods/ai-search",
    "image": "/api/v1/temu/goods/ai-image-search",
    "malls": "/api/v1/temu/mall/ai-search",
    "categories": "/api/v1/temu/category/ai-search",
    "keywords": "/api/v1/temu/keyword/ai-search",
    "reviews": "/api/v1/temu/review/ai-search",
}


def _environment_timeout() -> float:
    raw = os.getenv("GEEKBI_REQUEST_TIMEOUT", "30").strip()
    try:
        timeout = float(raw)
    except ValueError as error:
        raise GeekBIError("GEEKBI_REQUEST_TIMEOUT must be a number") from error
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 300:
        raise GeekBIError("Request timeout must be greater than 0 and at most 300 seconds")
    return timeout


def _base_url() -> str:
    value = os.getenv("GEEKBI_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GeekBIError("GEEKBI_BASE_URL must be a valid HTTP or HTTPS URL")
    if os.getenv("GEEKBI_REMOTE_MODE") == "1" and parsed.scheme != "https":
        raise GeekBIError("Remote GeekBI API requests require HTTPS")
    return value


def _normalize_country(value: str) -> str:
    normalized = value.strip().casefold()
    for suffix in ("站点", "站"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)].strip()
    return normalized


class GeekBIClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or _base_url()).rstrip("/")
        self.timeout = timeout if timeout is not None else _environment_timeout()
        self.auth = AuthManager(self.base_url)

    def _url(self, endpoint: str, params: list[tuple[str, str]] | None = None) -> str:
        url = f"{self.base_url}{endpoint}"
        query = urlencode(params or [])
        return f"{url}?{query}" if query else url

    @staticmethod
    def _search_result(payload: Any, label: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise GeekBIError(f"{label} returned an invalid response format")
        if payload.get("code") != 0:
            raise GeekBIError(response_message(payload, f"{label} failed"))
        data = payload.get("data")
        if not isinstance(data, dict):
            raise GeekBIError(f"{label} response is missing data")
        if not isinstance(data.get("list"), list):
            raise GeekBIError(f"{label} response is missing a result list")
        return {"code": 0, "data": data}

    def _search(self, endpoint: str, query: QueryInput, label: str) -> dict[str, Any]:
        payload = self.auth.request_json(
            self._url(endpoint, query.query_items()),
            self.timeout,
        )
        return self._search_result(payload, label)

    def sites(self, country: str | None = None) -> dict[str, Any]:
        payload = self.auth.request_json(
            self._url(ENDPOINTS["sites"]),
            self.timeout,
        )
        if payload.get("code") != 0:
            raise GeekBIError(response_message(payload, "Site lookup failed"))
        sites = payload.get("data")
        if not isinstance(sites, list):
            raise GeekBIError("Site response is missing the site list")
        valid_sites = [site for site in sites if isinstance(site, dict)]
        if country is None or not country.strip():
            return {"code": 0, "data": {"list": valid_sites}}

        target = _normalize_country(country)
        matches: list[dict[str, Any]] = []
        seen: set[tuple[Any, Any, Any]] = set()
        for site in valid_sites:
            names = {
                _normalize_country(name)
                for name in (site.get("name"), site.get("cnName"))
                if isinstance(name, str)
            }
            if target not in names:
                continue
            key = (site.get("siteId"), site.get("name"), site.get("cnName"))
            if key not in seen:
                seen.add(key)
                matches.append(site)
        if not matches:
            raise GeekBIError("No matching Temu site. Please confirm the country or region name.")
        return {"code": 0, "data": {"matches": matches}}

    def goods(self, query: GoodsSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["goods"], query, "Product search")

    def image(self, query: ImageSearchInput) -> dict[str, Any]:
        data, content_type, filename = read_image(query.image, max(self.timeout, 60))
        body, multipart_type = build_multipart(data, content_type, filename)
        payload = self.auth.request_json(
            self._url(ENDPOINTS["image"], query.query_items(exclude={"image"})),
            max(self.timeout, 60),
            method="POST",
            body=body,
            headers={"Content-Type": multipart_type},
        )
        return self._search_result(payload, "Image search")

    def malls(self, query: MallSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["malls"], query, "Store search")

    def categories(self, query: CategorySearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["categories"], query, "Category search")

    def keywords(self, query: KeywordSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["keywords"], query, "Keyword search")

    def reviews(self, query: ReviewSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["reviews"], query, "Review search")
