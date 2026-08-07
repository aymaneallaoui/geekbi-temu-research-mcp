"""极鲸云 Temu 数据接口客户端。"""

from __future__ import annotations

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
        raise GeekBIError("GEEKBI_REQUEST_TIMEOUT 必须是数字") from error
    if timeout <= 0 or timeout > 300:
        raise GeekBIError("请求超时时间必须大于 0 且不超过 300 秒")
    return timeout


def _base_url() -> str:
    value = os.getenv("GEEKBI_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise GeekBIError("GEEKBI_BASE_URL 必须是有效的 HTTP 或 HTTPS 地址")
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
            raise GeekBIError(f"{label}响应格式不正确")
        if payload.get("code") != 0:
            raise GeekBIError(response_message(payload, f"{label}失败"))
        data = payload.get("data")
        if not isinstance(data, dict):
            raise GeekBIError(f"{label}响应缺少数据")
        if not isinstance(data.get("list"), list):
            raise GeekBIError(f"{label}响应缺少结果列表")
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
            raise GeekBIError(response_message(payload, "站点查询失败"))
        sites = payload.get("data")
        if not isinstance(sites, list):
            raise GeekBIError("站点查询响应缺少站点列表")
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
            raise GeekBIError("未找到该 Temu 站点，请确认国家或地区名称")
        return {"code": 0, "data": {"matches": matches}}

    def goods(self, query: GoodsSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["goods"], query, "商品查询")

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
        return self._search_result(payload, "图搜同款")

    def malls(self, query: MallSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["malls"], query, "店铺查询")

    def categories(self, query: CategorySearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["categories"], query, "类目查询")

    def keywords(self, query: KeywordSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["keywords"], query, "关键词查询")

    def reviews(self, query: ReviewSearchInput) -> dict[str, Any]:
        return self._search(ENDPOINTS["reviews"], query, "评论查询")
