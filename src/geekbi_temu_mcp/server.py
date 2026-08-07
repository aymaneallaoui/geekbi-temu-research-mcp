"""GeekBI Temu Research MCP 服务入口。"""

from __future__ import annotations

import argparse
import asyncio
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
通过极鲸云查询真实 Temu 商品、图搜同款、店铺、类目、关键词、评论和站点数据，用于跨境选品与市场调研。
默认使用美国站 siteId 48；用户指定其他国家或地区时，先调用 temu_site_list 实时取得 siteId 和币种。
商品、店铺、类目、关键词结果中的 linkUrl 必须用于对应名称的可点击链接，不自行拼接链接。
请求多页时记录实际页数和条数；未读取全部分页时明确说明是样本。只根据接口真实返回数据形成结论。
服务返回 actionRequired 时，向用户展示 msg；存在 jumpUrl 时提供可点击链接，用户完成操作后原样重试查询。
面向用户使用中文业务名称，不展示访问令牌、设备码、内部请求头或原始认证状态。
""".strip()


mcp = MCPServer(
    name="geekbi-temu-research",
    title="极鲸云 Temu 数据分析与市场调研",
    description="极鲸云提供的 Temu 商品、店铺、类目、关键词、评论和图搜同款数据服务",
    instructions=SERVER_INSTRUCTIONS,
    website_url="https://www.geekbi.com",
    version=__version__,
)

T = TypeVar("T")


def _execute(callback: Callable[[], T]) -> T | dict[str, Any]:
    try:
        return callback()
    except ActionRequired as error:
        return error.public_payload()
    except GeekBIError as error:
        return {"error": True, "msg": str(error)}
    except TimeoutError:
        return {"error": True, "msg": "极鲸云请求超时，请稍后重试"}
    except URLError:
        return {"error": True, "msg": "暂时无法连接极鲸云，请稍后重试"}
    except (OSError, ValueError) as error:
        return {"error": True, "msg": str(error)}


@mcp.tool()
def temu_site_list(country: str | None = None) -> dict[str, Any]:
    """查询 Temu 站点。美国站直接使用 48；其他国家传中文名或英文名精确解析站点 ID、内部地区 ID 和币种。"""
    return _execute(lambda: GeekBIClient().sites(country))


@mcp.tool()
def temu_goods_search(query: GoodsSearchInput) -> dict[str, Any]:
    """搜索 Temu 商品，用于热销、新品、低竞争、价格带和竞品分析。商品标题必须使用返回的 linkUrl 展示为可点击链接。"""
    return _execute(lambda: GeekBIClient().goods(query))


@mcp.tool()
def temu_image_search(query: ImageSearchInput) -> dict[str, Any]:
    """上传图片搜索 Temu 视觉同款，并叠加商品销量、价格、类目、同款数、时间、排序和分页筛选。"""
    return _execute(lambda: GeekBIClient().image(query))


@mcp.tool()
def temu_mall_search(query: MallSearchInput) -> dict[str, Any]:
    """搜索 Temu 店铺，分析经营规模、动销效率、主营类目、增长和竞品表现。店铺名必须使用返回的 linkUrl。"""
    return _execute(lambda: GeekBIClient().malls(query))


@mcp.tool()
def temu_category_search(query: CategorySearchInput) -> dict[str, Any]:
    """搜索 Temu 类目并分析市场容量、供需、价格带和增长。返回的类目 ID 可继续用于商品、店铺和关键词筛选。"""
    return _execute(lambda: GeekBIClient().categories(query))


@mcp.tool()
def temu_keyword_search(query: KeywordSearchInput) -> dict[str, Any]:
    """搜索 Temu 关键词，分析需求、销量、销售额、商品供给、店铺供给、增长和蓝海机会。"""
    return _execute(lambda: GeekBIClient().keywords(query))


@mcp.tool()
def temu_review_search(query: ReviewSearchInput) -> dict[str, Any]:
    """按商品搜索 Temu 评论，可按评分、规格、时间和有用数筛选排序，用于提炼卖点、差评原因、场景与改良方向。"""
    return _execute(lambda: GeekBIClient().reviews(query))


GUIDES = {
    "overview": """
# Temu 市场调研总则

- 默认美国站使用站点 ID 48；其他国家先实时查询站点，不猜测站点 ID。
- 简单问题只调用一个主工具；综合调研按“类目 → 关键词 → 商品 → 评论 → 店铺”逐步验证。
- 分页未完成时只能称为样本，不能冒充全量市场。
- 商品、店铺、类目和关键词名称必须使用接口返回的 linkUrl 作为可点击链接。
- 价格使用当前站点币种；供货价固定为人民币。计算利润前先统一币种并说明汇率日期。
- 缺失值和估算值保持原样。库存返回 0 时按“暂未统计到，需核实”处理，不直接判断缺货。
""".strip(),
    "goods": """
# 商品选品口径

- 一般只使用关键词或类目之一；同时使用代表交叉筛选，样本会明显减少。
- 类目筛选优先一级或二级类目；更细的需求优先使用关键词。
- 同款数不超过 10 通常为较低竞争，11–20 为中等竞争，超过 20 竞争较高；仍需结合销量、价格、评分和上架时间。
- 热销看销量及稳定性，新品看上架时间与增长，蓝海需要同时验证需求、增长、供给和同款竞争。
""".strip(),
    "image": """
# 图搜同款口径

- 图片支持本地路径、文件地址、图片网址、Data URI 和带 base64: 前缀的 Base64，最大 10MB。
- 图搜结果与商品搜索使用相同字段和筛选条件。未指定排序时按图片相似度；指定排序后在视觉候选内按业务字段排序。
- 请求多页必须保持同一图片和同一组筛选条件，只改变页码。
""".strip(),
    "mall": """
# 店铺研究口径

- 结合总销量、销售额、商品数、粉丝数、平均价格、增长和动销率判断经营质量。
- 动销率查询值使用 0–100 的百分比；其他增长率使用小数，例如 20% 传 0.2。
- 区分全托管和半托管，避免直接比较不同经营模式的绝对指标。
""".strip(),
    "category": """
# 类目研究口径

- 类目搜索用于确认可信类目 ID、上下级路径、市场容量、供需、价格带和增长。
- 用于商品和店铺筛选时优先一级或二级类目，不根据类目名称猜测 ID。
- 商品数和店铺数的周期字段是变化量，可能为负数；增长率使用小数。
""".strip(),
    "keyword": """
# 关键词研究口径

- 关键词数据用于判断买家需求、供给拥挤度、增长和蓝海机会，不等同于广告平台搜索量。
- 市场时间表示该关键词下最早商品的上架时间。
- 结合销量、销售额、商品数和店铺数共同判断机会，不能只依赖单一蓝海指数。
""".strip(),
    "review": """
# 评论研究口径

- 优先组合读取 1–3 星高有用数评论和最新评论，区分长期结构性问题与近期偶发反馈。
- 有用数表示该评论的参考价值，不代表同一主题出现次数。
- 评论为空时先核对商品、站点、SKU、评分和时间范围；仍为空则说明暂未收录，不生成虚构结论。
""".strip(),
}


@mcp.resource("geekbi://guides/{topic}")
def temu_research_guide(topic: str) -> str:
    """读取 Temu 调研口径。topic 支持 overview、goods、image、mall、category、keyword、review。"""
    guide = GUIDES.get(topic)
    if guide is None:
        raise ValueError("未知调研指南")
    return guide


@mcp.prompt()
def temu_market_research(
    objective: str,
    country: str = "美国",
    focus: str = "市场需求、增长、价格带、竞争强度、消费者痛点和进入建议",
) -> str:
    """生成一份调用多个 Temu 数据工具完成市场调研的任务提示。"""
    return f"""
请使用 GeekBI Temu Research MCP，为“{objective}”完成 {country}站调研，重点分析：{focus}。

执行要求：
1. {"直接使用美国站 ID 48" if country == "美国" else "先调用 temu_site_list 精确解析站点 ID 和币种"}。
2. 先用类目或关键词确认市场范围，再查商品样本；需要消费者证据时查评论，需要竞品经营证据时查店铺。
3. 记录查询日期、站点、筛选、排序、实际页数、样本量和总命中数。
4. 将商品、店铺、类目和关键词名称绑定各自返回的 linkUrl。
5. 区分接口事实、可复算指标和分析判断；未完成全部分页时明确标为样本。
6. 给出机会优先级、主要风险和下一步小规模验证方案。
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 GeekBI Temu Research MCP")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP 传输方式，默认 stdio",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 监听地址")
    parser.add_argument("--port", type=int, default=8000, help="HTTP 监听端口")
    args = parser.parse_args()

    try:
        if args.transport == "streamable-http":
            mcp.run(
                transport="streamable-http",
                host=args.host,
                port=args.port,
                json_response=True,
            )
            return
        mcp.run(transport="stdio")
    except (KeyboardInterrupt, asyncio.CancelledError):
        return
