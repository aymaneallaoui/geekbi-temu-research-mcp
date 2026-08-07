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
这是极鲸云 Temu 数据分析服务。根据用户的选品、图搜同款、店铺、类目、关键词或评论意图，自主选择一个主工具；只有结论确需交叉验证时才追加其他工具。只依据工具真实返回的数据回答，区分数据事实、可复算指标和分析判断，不编造结果。默认美国站使用站点 ID 48；用户指定其他国家或地区时，先用站点工具实时取得唯一匹配的站点 ID 和币种，不猜测。面向用户只说中文业务名称，不展示英文参数、请求命令、原始 JSON、访问令牌、设备码、请求头或内部认证状态。

简单查询只用对应主工具。完整市场调研按问题裁剪“类目确认市场边界 → 关键词验证需求 → 商品核验价格、销量和同款竞争 → 评论验证卖点与痛点 → 店铺核验竞品经营表现”；已有明确关键词、商品或店铺时可从相应工具开始，不机械调用全部工具。商品、店铺、关键词和类目共用同一站点与类目 ID 体系；类目 ID 只能来自用户或类目查询，优先一级、二级，不根据名称猜测。关键词和类目通常二选一，只有用户明确要求交叉限定时才同时使用，并说明样本会减少。所有工具只生成解决问题所需的最小条件，不擅自放宽用户硬性条件。

每次记录并说明查询日期、站点、币种、时间范围、筛选与排序、实际页数、样本量、命中总数和数据更新时间。未覆盖全部分页时明确称为样本，不外推为全平台或全市场；用户要求全部结果时按每页最多 200 条继续翻页。缺失、异常、估算和零值保持谨慎：库存为 0 表示可能暂未统计到，不能直接判断缺货；金额和销售额使用当前站点币种，供货价固定为人民币，计算价差或利润前必须统一币种并说明汇率日期。增长率通常使用小数，20% 对应 0.2；店铺动销率筛选例外，使用 0 至 100 的百分比值。

商品、店铺、关键词和类目只要返回非空 linkUrl，每一次展示该对象时都必须把主要名称写成可点击 Markdown 链接，不设置裸链接列，不写纯文本 URL，不用“查看详情”替代名称，不自行拼接或修复链接。用户单独索要链接时只返回可点击名称，不解释字段或链接来源。发送答复前核对非空链接对象数与可点击名称数一致。

服务返回 actionRequired 时，原样展示一级中文 msg；存在 jumpUrl 时提供可点击入口，然后停止分析。用户完成登录、充值、开通、升级或解除限制并回复继续后，直接用完全相同的业务工具和参数重试，不额外检查登录状态。普通错误只展示一级 msg；没有有效 msg 时才给简短中文错误。未取得数据前不生成市场结论。

默认输出顺序是一句话结论、数据口径、关键证据、机会与风险、行动建议；用户只要列表或简单结果时保持简洁。比较不同对象必须统一站点、币种、时间窗和筛选边界；不可比时停止直接排名。所有日期使用绝对日期。
""".strip()


mcp = MCPServer(
    name="geekbi-temu-research",
    title="极鲸云 Temu 数据分析与市场调研",
    description=(
        "极鲸云提供的 Temu 跨境选品与市场调研数据服务，可自主查询商品、图搜同款、店铺、"
        "类目、关键词、评论和国家站点，分析需求、增长、价格带、竞争、用户痛点与进入机会。"
    ),
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
    """实时查询 Temu 国家站点、站点 ID、内部地区 ID 和币种。仅当用户明确指定美国以外的国家或地区时调用；未指定站点或指定美国站时直接让业务工具使用默认站点 ID 48，不调用本工具。country 使用用户给出的中文名或英文名做精确匹配，不按语言、币种或相似名称猜测；无匹配或多个匹配时请用户确认。取得唯一匹配的 siteId 后，将它用于商品、图搜、店铺、类目、关键词或评论查询，并用返回币种解释站点售价、平均价格和销售额。"""
    return _execute(lambda: GeekBIClient().sites(country))


@mcp.tool()
def temu_goods_search(query: GoodsSearchInput) -> dict[str, Any]:
    """搜索和筛选 Temu 商品，用于找热销款、日销榜、新品、低竞争商品、新店商品、大卖新品、价格带和竞品，并分析销量及增长、销售额、站点售价、人民币供货价、评分、评论数、库存、同款竞争、上架时间、店铺和类目。未指定站点时使用美国站 48；其他国家先调用站点工具。商品意图一般在 keyword 与 catIds 中二选一：可信一级或二级类目 ID 用 catIds，更细意图用 keyword；类目 ID 不可猜测，同时使用代表交叉筛选且会减少结果。热销/日销按 daySold 降序；近三个月新品限定绝对上架时间并按 onSaleTime 降序；低竞争蓝海可用总销量至少 100、近三个月、同款数 1 至 10并按日销量降序，样本不足时最多放宽同款数至 20且必须说明；新店商品限定近三个月开店并按总销量降序；大卖新品限定近三个月上架并按店铺销量降序。每次只选一个最接近用户意图的预设，用户条件优先。同款数不超过 10通常竞争较低，11 至 20中等，超过 20较高；不能单独凭同款数或销量下结论。库存为 0按暂未统计到处理。单页最多 200；未翻完页时标为样本。返回商品每次出现都必须用服务端 linkUrl 将商品标题写成可点击链接，不自行拼接。取得明确商品 ID 后，只有评论证据会影响决策时再调用评论搜索。"""
    return _execute(lambda: GeekBIClient().goods(query))


@mcp.tool()
def temu_image_search(query: ImageSearchInput) -> dict[str, Any]:
    """用用户上传的商品图、实拍图、供应商图、网页图片、Data URI 或 Base64 图片搜索 Temu 视觉同款，再叠加与商品搜索完全相同的站点、关键词、类目、销量、销售额、价格、人民币供货价、评分、评论数、库存、同款数、托管模式、时间、排序和分页条件。用户要求以图找同款时必须以图片为主检索依据，不先主观描述图片并改用关键词冒充。图片与条件取交集，只生成最小必要筛选；未指定 sort 时保持图片相似度顺序，要求热销、低价、新品或低竞争时才在视觉候选内使用相应商品排序。图搜返回与商品搜索完全相同的商品结构和字段，视觉相似不等于规格、材质、尺寸、功能或供应链相同。用户要求全部同款或完整市场分析时，先读取命中总数，再以每页 200条、同一图片和同一条件逐页查询直至覆盖全部命中；部分分页必须称为样本，命中数不能表述为全平台全部同款。无结果时如实说明，可建议换主体更清晰、遮挡更少、背景更简单的图片，不能用普通关键词结果替代。所有商品名称必须使用返回 linkUrl 展示为可点击链接，并沿用商品搜索的币种、库存和同款竞争口径。"""
    return _execute(lambda: GeekBIClient().image(query))


@mcp.tool()
def temu_mall_search(query: MallSearchInput) -> dict[str, Any]:
    """搜索 Temu 店铺名称或店铺 ID，筛选头部店、竞品店、新店和高成长店铺，分析总销量、总销售额、商品数、粉丝数、评论规模、评分、平均价格、日周月经营表现、增长、动销商品数、动销率、主营类目、托管模式和开店时间。未指定站点时使用美国站 48；其他国家先调用站点工具。keyword 与 catIds 通常二选一；主营类目 ID 与其他工具共用，只能使用用户或类目工具给出的可信一级、二级 ID。热销店铺按 mallSold 降序，高评论店铺按 reviewNum 降序，热销新店限定近三个月开店并按 mallSold 降序，最近开店按 mallOpenTime 降序；每次只选一个预设且用户条件优先。增长率筛选使用小数，例如 20%传 0.2；动销率筛选使用 0至100，例如 20%传 20。评估时结合规模、近期趋势、动销效率、口碑和发展阶段，评论多不等于高评分，少量评论的高分不构成强证据；全托管与半托管分开比较，热度不单独作为结论。派生店均、品均或占比时说明公式并排除分母为零或缺失样本。分页未完成时标为样本。每次展示店铺都必须把店铺名称绑定返回的 linkUrl，不自行拼接。"""
    return _execute(lambda: GeekBIClient().malls(query))


@mcp.tool()
def temu_category_search(query: CategorySearchInput) -> dict[str, Any]:
    """搜索 Temu 中文或英文类目名称、类目层级或父类目的直接子类目，用于取得可信类目 ID、确认完整路径，并研究市场容量、需求增长、商品与店铺供给、价格带、半托管渗透、竞争格局和进入机会。未指定站点时使用美国站 48；其他国家先调用站点工具。名称使用模糊搜索；优先查询一级或二级类目，用户未要求下钻时不主动限制三级、四级；已知父类目 ID 才使用 parentCatId，不根据名称猜 ID，也不为更准无条件叠加关键词、层级和父类目。热销类目按 totalSold 降序，蓝海类目按 dsr 降序；近期需求增长可按 monthSoldRate 或 monthSalesRate 降序并设置最低需求规模，避免小基数极端增长。蓝海指数只作供需综合信号，必须与总销量、月度趋势、商品数、店铺数和平均价格交叉验证。商品数和店铺数的周期字段是变化量，可能为负；增长率使用小数。用完整路径和层级核验返回的 catId，可信 ID 可直接交给商品、店铺或关键词工具。分页未完成时标为样本。每次展示类目都必须把类目名称或完整路径绑定返回的 linkUrl，不自行拼接。"""
    return _execute(lambda: GeekBIClient().categories(query))


@mcp.tool()
def temu_keyword_search(query: KeywordSearchInput) -> dict[str, Any]:
    """搜索 Temu 中文或英文关键词，用于查特定词、热销词、蓝海词、新词、需求增长和品类搜索词机会，分析总销量、总销售额、日周月需求及增长、商品供给、店铺供给、平均价格、市场阶段、关联类目和半托管渗透。未指定站点时使用美国站 48；其他国家先调用站点工具。查特定词优先 keyword，不自行翻译替换用户输入；做品类词挖掘优先 catIds，类目 ID 只能来自用户或类目工具且优先一级、二级；只有明确要求在某品类查特定词时才组合。热销词按 totalSold 降序，蓝海词按 dsr 降序，最近新词按 firstOnSaleTime 降序；近期增长可按 monthSoldRate 或 monthSalesRate 降序并设置最低需求规模。firstOnSaleTime 表示该词下最早商品的上架时间，不是关键词创建时间，也不能单独证明新趋势。蓝海指数不能单独作为进入依据，要结合需求规模、增长、商品数、店铺数和价格带；商品数和店铺数的周期字段是可为负的变化量，增长率使用小数。候选词可继续交给商品工具验证同款竞争、价格、评论和上架时间。分页未完成时标为样本。每次展示关键词都必须把关键词名称绑定返回的 linkUrl，不自行拼接。"""
    return _execute(lambda: GeekBIClient().keywords(query))


@mcp.tool()
def temu_review_search(query: ReviewSearchInput) -> dict[str, Any]:
    """查询一个明确 Temu 商品 ID 的真实评论，可限定站点、SKU规格、1至5星评分、有用数、评论时间并按评论时间、有用数、评分或采集时间排序，用于分析购买动机、使用场景、正向卖点、差评原因、规格风险、时间变化和产品改良方向；不能用于全站找商品。用户没有明确商品 ID时先用商品搜索定位，不猜测。默认按评论时间降序看最新评论；高参考价值评论按 helpful 降序；差评痛点筛选1至3星后按 helpful 降序，严重问题可看1至2星；正向卖点筛选4至5星后按 helpful 降序；规格差异使用 skuId或规格分组。全量研究逐页读取，单页最多200，最多前10000条，超出时按评分、规格或时间分批；部分分页的评分结构只能称为样本。total为0只表示极鲸云当前条件下暂未收录，不能解释为商品没有评论或质量好坏。分析时把主题出现次数与低评分、高有用数代表的严重度分开；有用数表示参考价值，不代表观点频率；问题集中于特定规格时不能归因整个商品；未实际查看图片或视频时不能描述媒体内容；评论时间是发表时间，采集时间不是。只依据实际评论，避免单条评论外推；优先使用多条独立、跨规格重复、近期持续且有较高有用数的证据。用户要求明细时用中文列名完整保留所有返回字段和空值。"""
    return _execute(lambda: GeekBIClient().reviews(query))


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
