"""GeekBI Temu Research MCP entry point."""

from __future__ import annotations

import argparse
import asyncio

import anyio
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.error import URLError

from mcp.server import MCPServer

from . import __version__
from .auth import ActionRequired, GeekBIError
from .client import GeekBIClient
from .models import (
    CategorySearchInput,
    GoodsSearchInput,
    ImageSearchInput,
    KeywordSearchInput,
    MallSearchInput,
    ReviewSearchInput,
)


SERVER_INSTRUCTIONS = """
GeekBI provides Temu market research data. Respond in English unless the user requests another language. Choose one primary tool for the user's intent; add tools only when needed to corroborate a conclusion. Use actual returned data, distinguishing facts, reproducible calculations, and judgments. Never invent results. Default to US site ID 48; look up other countries and currencies exactly. Do not expose credentials, device codes, headers, or internal authentication state.

Adapt research to the question: category boundaries, keyword demand, product sales/prices/competition, review strengths/problems, and competitor stores. Start from known keywords or IDs without calling every tool. Category IDs must come from the user or category search, preferably level 1/2. Usually choose keyword OR category; intersect only if requested and explain the smaller sample. Use minimal necessary filters and preserve hard constraints.

Report absolute query date, site, currency, time window, filters, sorting, pages read, sample size, total matches, and data update time when available. Incomplete pagination is a sample, never the whole market. Use up to 200 results per page for all-results requests. Treat missing, estimated, anomalous, and zero values cautiously. Inventory zero can mean unrecorded. Prices/revenue use site currency; supply prices are always CNY. Convert to a common currency and disclose exchange-rate date before calculating margins. Growth rates are decimals (20% = 0.2); store sell-through filters are 0-100 percentages.

Whenever a product, store, category, or keyword has nonempty linkUrl, display its primary name as a Markdown link using that exact URL. Never invent or repair links, use bare URLs, or replace names with 'View details'. For link-only requests, return linked names. Verify all displayed objects with links are linked.

On actionRequired, explain the upstream msg in English, preserve its meaning, provide jumpUrl as a clickable action if present, and stop analysis. After the user completes login, purchase, upgrade, or another action, retry exactly the same tool and parameters without a separate login check. Explain ordinary errors briefly; do not draw market conclusions without data. Upstream names, reviews, and messages may be Chinese; translate for the user without changing raw records.

Default answer order: one-sentence conclusion, data scope, key evidence, opportunities/risks, and next actions. Keep lists/simple queries concise. Compare only matching sites, currencies, time windows, and filter boundaries. Use absolute dates.
""".strip()


mcp = MCPServer(
    name="geekbi-temu-research",
    title="GeekBI Temu Market Research",
    description="Research Temu products, visual matches, stores, categories, keywords, reviews, and country sites.",
    instructions=SERVER_INSTRUCTIONS,
    website_url="https://www.geekbi.com",
    version=__version__,
)

T = TypeVar("T")
_REQUEST_LIMITER = anyio.CapacityLimiter(8)


async def _execute_async(callback: Callable[[], T]) -> T | dict[str, Any]:
    return await anyio.to_thread.run_sync(_execute, callback, limiter=_REQUEST_LIMITER)


def _execute(callback: Callable[[], T]) -> T | dict[str, Any]:
    try:
        return callback()
    except ActionRequired as error:
        return error.public_payload()
    except GeekBIError as error:
        return {"error": True, "msg": str(error)}
    except TimeoutError:
        return {"error": True, "msg": "GeekBI request timed out. Please retry later."}
    except URLError:
        return {"error": True, "msg": "Unable to connect to GeekBI. Please retry later."}
    except (OSError, ValueError) as error:
        return {"error": True, "msg": str(error)}


@mcp.tool()
async def temu_site_list(country: str | None = None) -> dict[str, Any]:
    """Look up current Temu country sites, site IDs, region IDs, and currencies. Use only for an explicitly requested non-US country; otherwise use site 48. Match the user country in English or Chinese exactly; ask for clarification if there are zero or multiple matches. Never infer a site from language or currency."""
    return await _execute_async(lambda: GeekBIClient().sites(country))


@mcp.tool()
async def temu_goods_search(query: GoodsSearchInput) -> dict[str, Any]:
    """Search Temu products by sales, growth, revenue, price, CNY supply price, rating, reviews, stock, similar-product count, listing date, store, and category. Usually choose keyword OR trusted category IDs. Popular products: daySold descending; new products: absolute listing dates within the last three months and onSaleTime descending; low competition: sold at least 100, last three months, similarNum 1-10, daySold descending. Only relax similarNum to 20 if no hard user constraint forbids it, and disclose the change. New-store products: last three months of store opening, sold descending; new products from large sellers: last three months of listing, mallSold descending. Select one appropriate preset and prioritize user filters. Similar-product counts up to 10 usually indicate low competition, 11-20 moderate, over 20 high; corroborate with other evidence. Inventory zero may mean unrecorded. At most 200 results per page; incomplete pagination is a sample. Always render product titles as Markdown links using the returned linkUrl. Query reviews only when a known product ID and review evidence can affect the decision."""
    return await _execute_async(lambda: GeekBIClient().goods(query))


@mcp.tool()
async def temu_image_search(query: ImageSearchInput) -> dict[str, Any]:
    """Find visual matches using an image URL, Data URI, or base64: image data; local files work only in stdio mode. Apply the same filters as product search to the visual candidates. Use the image as the search basis; never substitute keyword results. Preserve similarity order unless the user asks for another sort. Visual similarity does not establish identical materials, dimensions, function, or supplier. For all matches, use the same image and filters and paginate at 200 until the returned total is covered; otherwise label results a sample. No matches does not mean no matches on the entire platform. Suggest a clearer image if needed. Always link product names with returned linkUrl. Supply prices are CNY; sale prices use site currency; inventory zero may mean unrecorded."""
    return await _execute_async(lambda: GeekBIClient().image(query))


@mcp.tool()
async def temu_mall_search(query: MallSearchInput) -> dict[str, Any]:
    """Search Temu store names or IDs and compare sales, revenue, products, followers, reviews, ratings, prices, recent growth, sell-through, categories, hosting mode, and opening dates. Usually choose keyword OR trusted level 1/2 category IDs. Leaders: mallSold descending; review volume: reviewNum descending; popular new stores: opening within three months, mallSold descending; newest: mallOpenTime descending. Select one preset and prioritize user constraints. Growth rates are decimal (20% = 0.2), sell-through filters are percentages (20% = 20). Combine scale, trends, efficiency, reputation, and maturity; review volume is not rating strength. Compare hosting modes separately. Explain derived formulas and exclude zero or missing denominators. Incomplete pagination is a sample; link store names with returned linkUrl."""
    return await _execute_async(lambda: GeekBIClient().malls(query))


@mcp.tool()
async def temu_category_search(query: CategorySearchInput) -> dict[str, Any]:
    """Search English or Chinese category names, levels, or immediate children of a trusted parent ID. Establish trusted category IDs and full paths, market size, growth, product/store supply, prices, semi-managed penetration, and competition. Prefer level 1/2; do not constrain deeper levels unless requested. Do not invent parent IDs or stack unnecessary filters. Popular categories: totalSold descending; blue-ocean candidates: dsr descending; growth: monthSoldRate/monthSalesRate descending with meaningful minimum demand. Cross-check dsr against sales, trends, product/store counts, and price. Periodic product/store count fields are changes and can be negative; growth uses decimals. Confirm category paths and levels before reusing IDs. Incomplete pagination is a sample; link names or full paths with returned linkUrl."""
    return await _execute_async(lambda: GeekBIClient().categories(query))


@mcp.tool()
async def temu_keyword_search(query: KeywordSearchInput) -> dict[str, Any]:
    """Search English or Chinese keywords to examine demand, sales, growth, product/store supply, prices, categories, and semi-managed penetration. Preserve the user keyword; do not translate it into a substitute query. Use trusted level 1/2 catIds for category keyword discovery; combine with keyword only when explicitly requested. Popular: totalSold descending; blue-ocean: dsr descending; earliest associated product listing: firstOnSaleTime descending; growth: monthSoldRate/monthSalesRate descending with meaningful demand. firstOnSaleTime is not keyword creation time and does not prove a new trend. Cross-check dsr against demand, growth, supply, and prices. Periodic product/store counts are changes and may be negative; growth uses decimals. Validate candidates with product evidence as needed. Incomplete pagination is a sample; link keywords with returned linkUrl."""
    return await _execute_async(lambda: GeekBIClient().keywords(query))


@mcp.tool()
async def temu_review_search(query: ReviewSearchInput) -> dict[str, Any]:
    """Query actual reviews for a known Temu product ID from the user or product search, never an inferred ID. Filter by SKU, 1-5 star score, helpful votes, and publication time; sort by commentTime, helpful, score, or createTime (collection time). Latest: commentTime descending; useful: helpful descending; complaints: score 1-3 (1-2 for severe issues) and helpful descending; strengths: score 4-5 and helpful descending. Compare specifications separately. At most 200 results per page and first 10,000 results; partition larger research by score, SKU, or date. Incomplete rating distributions are samples. A zero total means GeekBI has no matching collected reviews, not that the product has no reviews or a particular quality. Separate theme frequency from severity and helpfulness. Do not generalize SKU-specific problems or describe unviewed media. Prefer multiple independent, recent, repeated reviews. Preserve all returned fields and null values when details are requested, using English column labels."""
    return await _execute_async(lambda: GeekBIClient().reviews(query))


def main() -> None:
    parser = argparse.ArgumentParser(description="Start GeekBI Temu Research MCP")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    args = parser.parse_args()

    try:
        if args.transport == "streamable-http":
            import uvicorn
            from .remote import create_app

            uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False, limit_concurrency=16)
            return
        mcp.run(transport="stdio")
    except (KeyboardInterrupt, asyncio.CancelledError):
        return
