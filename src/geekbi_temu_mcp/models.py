"""MCP 工具输入模型与查询参数序列化。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Order = Literal["asc", "desc"]
GoodsSort = Literal[
    "sold",
    "daySold",
    "weekSold",
    "monthSold",
    "mallSold",
    "daySoldRate",
    "weekSoldRate",
    "monthSoldRate",
    "sales",
    "daySales",
    "weekSales",
    "monthSales",
    "daySalesRate",
    "weekSalesRate",
    "monthSalesRate",
    "minPrice",
    "maxPrice",
    "supplyPrice",
    "minSupplyPrice",
    "medianSupplyPrice",
    "maxSupplyPrice",
    "quantity",
    "goodsScore",
    "reviewNum",
    "similarNum",
    "onSaleTime",
    "mallOpenTime",
]
MallSort = Literal[
    "mallSold",
    "mallSales",
    "mallStar",
    "reviewNum",
    "goodsNum",
    "followerNum",
    "avgPrice",
    "hot",
    "daySold",
    "weekSold",
    "monthSold",
    "daySoldRate",
    "weekSoldRate",
    "monthSoldRate",
    "daySales",
    "weekSales",
    "monthSales",
    "daySalesRate",
    "weekSalesRate",
    "monthSalesRate",
    "dayItemCount",
    "weekItemCount",
    "monthItemCount",
    "dayItemCountRate",
    "weekItemCountRate",
    "monthItemCountRate",
    "dayFollower",
    "weekFollower",
    "monthFollower",
    "dayFollowerRate",
    "weekFollowerRate",
    "monthFollowerRate",
    "daySellthroughCount",
    "weekSellthroughCount",
    "monthSellthroughCount",
    "daySellthroughRate",
    "weekSellthroughRate",
    "monthSellthroughRate",
    "mallOpenTime",
    "updateTime",
]
MarketSort = Literal[
    "dsr",
    "totalSold",
    "avgPrice",
    "totalSales",
    "itemCount",
    "semiManagedItemCount",
    "mallCount",
    "semiManagedMallCount",
    "daySold",
    "weekSold",
    "monthSold",
    "daySoldRate",
    "weekSoldRate",
    "monthSoldRate",
    "daySales",
    "weekSales",
    "monthSales",
    "daySalesRate",
    "weekSalesRate",
    "monthSalesRate",
    "dayItemCount",
    "weekItemCount",
    "monthItemCount",
    "dayItemCountRate",
    "weekItemCountRate",
    "monthItemCountRate",
    "dayMallCount",
    "weekMallCount",
    "monthMallCount",
    "dayMallCountRate",
    "weekMallCountRate",
    "monthMallCountRate",
    "createTime",
    "updateTime",
]
CategorySort = MarketSort | Literal["catLevel"]
KeywordSort = MarketSort | Literal["firstOnSaleTime"]
ReviewSort = Literal["commentTime", "helpful", "score", "createTime"]


class QueryInput(BaseModel):
    """所有查询模型的共同校验与 URL 参数转换。"""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_ranges(self) -> QueryInput:
        fields = type(self).model_fields
        for name in fields:
            if not name.endswith("Min"):
                continue
            maximum_name = f"{name[:-3]}Max"
            if maximum_name not in fields:
                continue
            minimum = getattr(self, name)
            maximum = getattr(self, maximum_name)
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"{name} 不能大于 {maximum_name}")
        return self

    def query_items(self, *, exclude: set[str] | None = None) -> list[tuple[str, str]]:
        payload = self.model_dump(mode="json", exclude_none=True, exclude=exclude or set())
        items: list[tuple[str, str]] = []
        for key, value in payload.items():
            values = value if isinstance(value, list) else [value]
            for item in values:
                items.append((key, str(item)))
        return items


class PagingInput(QueryInput):
    siteId: int = Field(48, ge=1, description="极鲸云站点 ID；默认 48 为美国站")
    page: int = Field(1, ge=1, description="页码，从 1 开始")
    size: int = Field(20, ge=1, le=200, description="每页数量，最大 200")
    order: Order = Field("desc", description="排序方向")


class GoodsSearchInput(PagingInput):
    """商品搜索及图搜同款共用筛选条件。"""

    keyword: str | None = Field(None, max_length=300, description="商品名称或品牌关键词")
    catIds: list[int] | None = Field(None, description="Temu 类目 ID；多个值匹配任一类目")
    hostingMode: Literal[1, 2] | None = Field(None, description="1 为全托管，2 为半托管")
    sort: GoodsSort | None = Field(None, description="排序字段；图搜未指定时按图片相似度")

    soldMin: float | None = None
    soldMax: float | None = None
    daySoldMin: float | None = None
    daySoldMax: float | None = None
    weekSoldMin: float | None = None
    weekSoldMax: float | None = None
    monthSoldMin: float | None = None
    monthSoldMax: float | None = None
    daySoldRateMin: float | None = None
    daySoldRateMax: float | None = None
    weekSoldRateMin: float | None = None
    weekSoldRateMax: float | None = None
    monthSoldRateMin: float | None = None
    monthSoldRateMax: float | None = None
    salesMin: float | None = None
    salesMax: float | None = None
    daySalesMin: float | None = None
    daySalesMax: float | None = None
    weekSalesMin: float | None = None
    weekSalesMax: float | None = None
    monthSalesMin: float | None = None
    monthSalesMax: float | None = None
    daySalesRateMin: float | None = None
    daySalesRateMax: float | None = None
    weekSalesRateMin: float | None = None
    weekSalesRateMax: float | None = None
    monthSalesRateMin: float | None = None
    monthSalesRateMax: float | None = None
    quantityMin: float | None = None
    quantityMax: float | None = None
    mallSoldMin: float | None = None
    mallSoldMax: float | None = None
    similarNumMin: float | None = Field(None, description="最小同款数（跟卖数）")
    similarNumMax: float | None = Field(None, description="最大同款数；低竞争通常不超过 10")
    priceMin: float | None = Field(None, description="最低商品价格，使用当前站点币种")
    priceMax: float | None = Field(None, description="最高商品价格，使用当前站点币种")
    supplyPriceMin: float | None = Field(None, description="最低供货价，单位人民币")
    supplyPriceMax: float | None = Field(None, description="最高供货价，单位人民币")
    goodsScoreMin: float | None = None
    goodsScoreMax: float | None = None
    reviewNumMin: float | None = None
    reviewNumMax: float | None = None
    onSaleTimeMin: datetime | None = None
    onSaleTimeMax: datetime | None = None
    mallOpenTimeMin: datetime | None = None
    mallOpenTimeMax: datetime | None = None


class ImageSearchInput(GoodsSearchInput):
    image: str = Field(
        description=(
            "图片输入：本地路径、file/http/https 地址、Data URI，"
            "或带 base64: 前缀的 Base64；最大 10MB"
        )
    )


class MallSearchInput(PagingInput):
    keyword: str | None = Field(None, max_length=300, description="店铺名称关键词")
    catIds: list[int] | None = Field(None, description="主营类目 ID；多个值匹配任一类目")
    hostingMode: Literal[1, 2] | None = Field(None, description="1 为全托管，2 为半托管")
    sort: MallSort | None = None

    mallSoldMin: float | None = None
    mallSoldMax: float | None = None
    mallSalesMin: float | None = None
    mallSalesMax: float | None = None
    mallStarMin: float | None = None
    mallStarMax: float | None = None
    reviewNumMin: float | None = None
    reviewNumMax: float | None = None
    goodsNumMin: float | None = None
    goodsNumMax: float | None = None
    followerNumMin: float | None = None
    followerNumMax: float | None = None
    avgPriceMin: float | None = None
    avgPriceMax: float | None = None
    daySoldMin: float | None = None
    daySoldMax: float | None = None
    weekSoldMin: float | None = None
    weekSoldMax: float | None = None
    monthSoldMin: float | None = None
    monthSoldMax: float | None = None
    daySoldRateMin: float | None = None
    daySoldRateMax: float | None = None
    weekSoldRateMin: float | None = None
    weekSoldRateMax: float | None = None
    monthSoldRateMin: float | None = None
    monthSoldRateMax: float | None = None
    daySalesMin: float | None = None
    daySalesMax: float | None = None
    weekSalesMin: float | None = None
    weekSalesMax: float | None = None
    monthSalesMin: float | None = None
    monthSalesMax: float | None = None
    daySalesRateMin: float | None = None
    daySalesRateMax: float | None = None
    weekSalesRateMin: float | None = None
    weekSalesRateMax: float | None = None
    monthSalesRateMin: float | None = None
    monthSalesRateMax: float | None = None
    dayItemCountMin: float | None = None
    dayItemCountMax: float | None = None
    weekItemCountMin: float | None = None
    weekItemCountMax: float | None = None
    monthItemCountMin: float | None = None
    monthItemCountMax: float | None = None
    dayItemCountRateMin: float | None = None
    dayItemCountRateMax: float | None = None
    weekItemCountRateMin: float | None = None
    weekItemCountRateMax: float | None = None
    monthItemCountRateMin: float | None = None
    monthItemCountRateMax: float | None = None
    dayFollowerMin: float | None = None
    dayFollowerMax: float | None = None
    weekFollowerMin: float | None = None
    weekFollowerMax: float | None = None
    monthFollowerMin: float | None = None
    monthFollowerMax: float | None = None
    dayFollowerRateMin: float | None = None
    dayFollowerRateMax: float | None = None
    weekFollowerRateMin: float | None = None
    weekFollowerRateMax: float | None = None
    monthFollowerRateMin: float | None = None
    monthFollowerRateMax: float | None = None
    daySellthroughCountMin: float | None = None
    daySellthroughCountMax: float | None = None
    weekSellthroughCountMin: float | None = None
    weekSellthroughCountMax: float | None = None
    monthSellthroughCountMin: float | None = None
    monthSellthroughCountMax: float | None = None
    daySellthroughRateMin: float | None = Field(None, ge=0, le=100)
    daySellthroughRateMax: float | None = Field(None, ge=0, le=100)
    weekSellthroughRateMin: float | None = Field(None, ge=0, le=100)
    weekSellthroughRateMax: float | None = Field(None, ge=0, le=100)
    monthSellthroughRateMin: float | None = Field(None, ge=0, le=100)
    monthSellthroughRateMax: float | None = Field(None, ge=0, le=100)
    mallOpenTimeMin: datetime | None = None
    mallOpenTimeMax: datetime | None = None


class MarketSearchInput(PagingInput):
    dsrMin: float | None = None
    dsrMax: float | None = None
    totalSoldMin: float | None = None
    totalSoldMax: float | None = None
    avgPriceMin: float | None = None
    avgPriceMax: float | None = None
    totalSalesMin: float | None = None
    totalSalesMax: float | None = None
    itemCountMin: float | None = None
    itemCountMax: float | None = None
    semiManagedItemCountMin: float | None = None
    semiManagedItemCountMax: float | None = None
    mallCountMin: float | None = None
    mallCountMax: float | None = None
    semiManagedMallCountMin: float | None = None
    semiManagedMallCountMax: float | None = None
    daySoldMin: float | None = None
    daySoldMax: float | None = None
    weekSoldMin: float | None = None
    weekSoldMax: float | None = None
    monthSoldMin: float | None = None
    monthSoldMax: float | None = None
    daySoldRateMin: float | None = None
    daySoldRateMax: float | None = None
    weekSoldRateMin: float | None = None
    weekSoldRateMax: float | None = None
    monthSoldRateMin: float | None = None
    monthSoldRateMax: float | None = None
    daySalesMin: float | None = None
    daySalesMax: float | None = None
    weekSalesMin: float | None = None
    weekSalesMax: float | None = None
    monthSalesMin: float | None = None
    monthSalesMax: float | None = None
    daySalesRateMin: float | None = None
    daySalesRateMax: float | None = None
    weekSalesRateMin: float | None = None
    weekSalesRateMax: float | None = None
    monthSalesRateMin: float | None = None
    monthSalesRateMax: float | None = None
    dayItemCountMin: float | None = None
    dayItemCountMax: float | None = None
    weekItemCountMin: float | None = None
    weekItemCountMax: float | None = None
    monthItemCountMin: float | None = None
    monthItemCountMax: float | None = None
    dayItemCountRateMin: float | None = None
    dayItemCountRateMax: float | None = None
    weekItemCountRateMin: float | None = None
    weekItemCountRateMax: float | None = None
    monthItemCountRateMin: float | None = None
    monthItemCountRateMax: float | None = None
    dayMallCountMin: float | None = None
    dayMallCountMax: float | None = None
    weekMallCountMin: float | None = None
    weekMallCountMax: float | None = None
    monthMallCountMin: float | None = None
    monthMallCountMax: float | None = None
    dayMallCountRateMin: float | None = None
    dayMallCountRateMax: float | None = None
    weekMallCountRateMin: float | None = None
    weekMallCountRateMax: float | None = None
    monthMallCountRateMin: float | None = None
    monthMallCountRateMax: float | None = None


class CategorySearchInput(MarketSearchInput):
    keyword: str | None = Field(None, max_length=300, description="类目中文名或英文名")
    catLevel: Literal[1, 2, 3, 4] | None = Field(None, description="类目层级")
    parentCatId: int | None = Field(None, ge=0, description="父类目 ID，0 代表根层")
    sort: CategorySort | None = None


class KeywordSearchInput(MarketSearchInput):
    keyword: str | None = Field(None, max_length=300, description="中文或英文关键词")
    catIds: list[int] | None = Field(None, description="Temu 类目 ID")
    sort: KeywordSort | None = None
    firstOnSaleTimeMin: datetime | None = Field(None, description="关联商品最早上架时间下限")
    firstOnSaleTimeMax: datetime | None = Field(None, description="关联商品最早上架时间上限")


class ReviewSearchInput(PagingInput):
    goodsId: str = Field(min_length=1, max_length=100, description="Temu 商品 ID")
    skuId: str | None = Field(None, max_length=100, description="可选 SKU ID")
    scoreMin: int | None = Field(None, ge=1, le=5)
    scoreMax: int | None = Field(None, ge=1, le=5)
    helpfulMin: int | None = Field(None, ge=0)
    helpfulMax: int | None = Field(None, ge=0)
    commentTimeMin: datetime | None = None
    commentTimeMax: datetime | None = None
    sort: ReviewSort = "commentTime"

    @model_validator(mode="after")
    def validate_review_window(self) -> ReviewSearchInput:
        if self.page * self.size > 10_000:
            raise ValueError("评论查询最多翻到前 10000 条，请缩小筛选范围")
        return self


def _range_descriptions(metrics: dict[str, str]) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for field, label in metrics.items():
        descriptions[f"{field}Min"] = f"{label}下限；只需下限时单独传入"
        descriptions[f"{field}Max"] = f"{label}上限；只需上限时单独传入"
    return descriptions


def _apply_descriptions(
    model: type[BaseModel],
    descriptions: dict[str, str],
) -> None:
    for field_name, description in descriptions.items():
        field = model.model_fields.get(field_name)
        if field is not None:
            field.description = description
    model.model_rebuild(force=True)


PAGING_DESCRIPTIONS = {
    "siteId": "极鲸云 Temu 站点 ID；默认 48 为美国站，其他国家必须先由站点查询取得，不猜测",
    "page": "页码，从 1 开始；多页查询保持其他条件不变",
    "size": "每页数量，1 至 200；需要全部结果时优先使用 200 并根据命中总数继续翻页",
    "order": "排序方向：desc 从高到低或从新到旧，asc 从低到高或从旧到新",
}

GOODS_DESCRIPTIONS = {
    **PAGING_DESCRIPTIONS,
    "keyword": "商品名称或品牌关键词，最长 300 字符，使用模糊搜索；通常与类目 ID 二选一",
    "catIds": "Temu 类目 ID 列表，多个 ID 匹配任一类目；只使用用户或类目查询给出的可信一级、二级 ID",
    "hostingMode": "托管模式：1 全托管，2 半托管",
    "sort": (
        "商品排序字段；热销常用 daySold，累计表现用 sold，近期趋势用 day/week/monthSoldRate，"
        "销售额用 sales 或 day/week/monthSales，价格用 minPrice，上新用 onSaleTime，"
        "低竞争比较可用 similarNum；图搜不传时保持图片相似度顺序"
    ),
    **_range_descriptions(
        {
            "sold": "商品总销量",
            "daySold": "近 1 日销量",
            "weekSold": "近 7 日销量",
            "monthSold": "近 30 日销量",
            "daySoldRate": "近 1 日销量增长率，小数口径，例如 20% 传 0.2",
            "weekSoldRate": "近 7 日销量增长率，小数口径，例如 20% 传 0.2",
            "monthSoldRate": "近 30 日销量增长率，小数口径，例如 20% 传 0.2",
            "sales": "商品总销售额，使用当前站点币种",
            "daySales": "近 1 日销售额，使用当前站点币种",
            "weekSales": "近 7 日销售额，使用当前站点币种",
            "monthSales": "近 30 日销售额，使用当前站点币种",
            "daySalesRate": "近 1 日销售额增长率，小数口径，例如 20% 传 0.2",
            "weekSalesRate": "近 7 日销售额增长率，小数口径，例如 20% 传 0.2",
            "monthSalesRate": "近 30 日销售额增长率，小数口径，例如 20% 传 0.2",
            "quantity": "库存快照；0 可能是暂未统计到，不能直接解释为缺货",
            "mallSold": "商品所属店铺总销量",
            "similarNum": "同款数（跟卖数）；不超过 10通常较优，11至20中等，超过20竞争较高",
            "price": "商品站点售价，使用当前查询站点币种",
            "supplyPrice": "供货价，固定使用人民币 CNY",
            "goodsScore": "商品评分",
            "reviewNum": "商品评论数",
            "onSaleTime": "商品上架时间，ISO 8601 绝对时间",
            "mallOpenTime": "商品所属店铺开店时间，ISO 8601 绝对时间",
        }
    ),
}

MALL_DESCRIPTIONS = {
    **PAGING_DESCRIPTIONS,
    "keyword": "店铺名称或店铺 ID，最长 300 字符；通常与主营类目 ID 二选一",
    "catIds": "主营 Temu 类目 ID 列表，多个 ID 匹配任一类目；只使用可信一级、二级类目 ID",
    "hostingMode": "托管模式：1 全托管，2 半托管；不同模式的店铺应分开比较",
    "sort": (
        "店铺排序字段；头部店常用 mallSold 或 mallSales，高评论用 reviewNum，新店用 mallOpenTime，"
        "成长用 day/week/monthSoldRate 或 SalesRate，效率用 SellthroughRate"
    ),
    **_range_descriptions(
        {
            "mallSold": "店铺总销量",
            "mallSales": "店铺总销售额，使用当前站点币种",
            "mallStar": "店铺评分",
            "reviewNum": "店铺评论数",
            "goodsNum": "店铺商品数量",
            "followerNum": "店铺粉丝数",
            "avgPrice": "店铺平均商品价格，使用当前站点币种",
            "daySold": "店铺日均销量",
            "weekSold": "店铺周均销量",
            "monthSold": "店铺月均销量",
            "daySoldRate": "店铺日均销量增长率，小数口径，例如 20% 传 0.2",
            "weekSoldRate": "店铺周均销量增长率，小数口径，例如 20% 传 0.2",
            "monthSoldRate": "店铺月均销量增长率，小数口径，例如 20% 传 0.2",
            "daySales": "店铺日均销售额，使用当前站点币种",
            "weekSales": "店铺周均销售额，使用当前站点币种",
            "monthSales": "店铺月均销售额，使用当前站点币种",
            "daySalesRate": "店铺日均销售额增长率，小数口径，例如 20% 传 0.2",
            "weekSalesRate": "店铺周均销售额增长率，小数口径，例如 20% 传 0.2",
            "monthSalesRate": "店铺月均销售额增长率，小数口径，例如 20% 传 0.2",
            "dayItemCount": "店铺日均商品数",
            "weekItemCount": "店铺周均商品数",
            "monthItemCount": "店铺月均商品数",
            "dayItemCountRate": "店铺日均商品数增长率，小数口径，例如 20% 传 0.2",
            "weekItemCountRate": "店铺周均商品数增长率，小数口径，例如 20% 传 0.2",
            "monthItemCountRate": "店铺月均商品数增长率，小数口径，例如 20% 传 0.2",
            "dayFollower": "店铺日均粉丝数",
            "weekFollower": "店铺周均粉丝数",
            "monthFollower": "店铺月均粉丝数",
            "dayFollowerRate": "店铺日均粉丝数增长率，小数口径，例如 20% 传 0.2",
            "weekFollowerRate": "店铺周均粉丝数增长率，小数口径，例如 20% 传 0.2",
            "monthFollowerRate": "店铺月均粉丝数增长率，小数口径，例如 20% 传 0.2",
            "daySellthroughCount": "店铺近 1 日动销商品数",
            "weekSellthroughCount": "店铺近 7 日动销商品数",
            "monthSellthroughCount": "店铺近 30 日动销商品数",
            "daySellthroughRate": "近 1 日动销率筛选，使用 0至100 的百分比值，例如 20% 传 20",
            "weekSellthroughRate": "近 7 日动销率筛选，使用 0至100 的百分比值，例如 20% 传 20",
            "monthSellthroughRate": "近 30 日动销率筛选，使用 0至100 的百分比值，例如 20% 传 20",
            "mallOpenTime": "店铺开店时间，ISO 8601 绝对时间",
        }
    ),
}

MARKET_DESCRIPTIONS = {
    **PAGING_DESCRIPTIONS,
    **_range_descriptions(
        {
            "dsr": "蓝海指数，只作供需综合信号，不能单独作为进入依据",
            "totalSold": "累计总销量",
            "avgPrice": "平均价格，使用当前站点币种",
            "totalSales": "累计总销售额，使用当前站点币种",
            "itemCount": "关联商品总数",
            "semiManagedItemCount": "关联半托管商品数",
            "mallCount": "关联店铺总数",
            "semiManagedMallCount": "关联半托管店铺数",
            "daySold": "近 1 日销量",
            "weekSold": "近 7 日销量",
            "monthSold": "近 30 日销量",
            "daySoldRate": "近 1 日销量增长率，小数口径，例如 20% 传 0.2",
            "weekSoldRate": "近 7 日销量增长率，小数口径，例如 20% 传 0.2",
            "monthSoldRate": "近 30 日销量增长率，小数口径，例如 20% 传 0.2",
            "daySales": "近 1 日销售额，使用当前站点币种",
            "weekSales": "近 7 日销售额，使用当前站点币种",
            "monthSales": "近 30 日销售额，使用当前站点币种",
            "daySalesRate": "近 1 日销售额增长率，小数口径，例如 20% 传 0.2",
            "weekSalesRate": "近 7 日销售额增长率，小数口径，例如 20% 传 0.2",
            "monthSalesRate": "近 30 日销售额增长率，小数口径，例如 20% 传 0.2",
            "dayItemCount": "近 1 日商品数变化量，可为负数",
            "weekItemCount": "近 7 日商品数变化量，可为负数",
            "monthItemCount": "近 30 日商品数变化量，可为负数",
            "dayItemCountRate": "近 1 日商品数增长率，小数口径，例如 20% 传 0.2",
            "weekItemCountRate": "近 7 日商品数增长率，小数口径，例如 20% 传 0.2",
            "monthItemCountRate": "近 30 日商品数增长率，小数口径，例如 20% 传 0.2",
            "dayMallCount": "近 1 日店铺数变化量，可为负数",
            "weekMallCount": "近 7 日店铺数变化量，可为负数",
            "monthMallCount": "近 30 日店铺数变化量，可为负数",
            "dayMallCountRate": "近 1 日店铺数增长率，小数口径，例如 20% 传 0.2",
            "weekMallCountRate": "近 7 日店铺数增长率，小数口径，例如 20% 传 0.2",
            "monthMallCountRate": "近 30 日店铺数增长率，小数口径，例如 20% 传 0.2",
        }
    ),
}

CATEGORY_DESCRIPTIONS = {
    **MARKET_DESCRIPTIONS,
    "keyword": "类目中文名或英文名，最长 300 字符，使用模糊搜索",
    "catLevel": "类目层级 1至4；用于后续商品、店铺或关键词筛选时优先一级、二级",
    "parentCatId": "父类目 ID，只返回该父类目的直接子类目；0 表示根层，只在已知可信 ID 时使用",
    "sort": (
        "类目排序字段；热销用 totalSold，蓝海用 dsr，近期需求增长用 monthSoldRate 或 monthSalesRate，"
        "供给变化用 ItemCount/MallCount 及其 Rate"
    ),
}

KEYWORD_DESCRIPTIONS = {
    **MARKET_DESCRIPTIONS,
    "keyword": "中文或英文关键词，最长 300 字符，同时匹配两种语言；不要自行翻译替换用户输入",
    "catIds": "Temu 类目 ID 列表，多个 ID 匹配任一类目；用于品类词挖掘，只使用可信一级、二级 ID",
    "sort": (
        "关键词排序字段；热销用 totalSold，蓝海用 dsr，最近新词用 firstOnSaleTime，"
        "近期需求增长用 monthSoldRate 或 monthSalesRate"
    ),
    "firstOnSaleTimeMin": "市场时间下限，ISO 8601；表示关键词下最早商品上架时间，不是关键词创建时间",
    "firstOnSaleTimeMax": "市场时间上限，ISO 8601；表示关键词下最早商品上架时间，不是关键词创建时间",
}

REVIEW_DESCRIPTIONS = {
    **PAGING_DESCRIPTIONS,
    "goodsId": "必填 Temu 商品 ID；必须来自用户或商品查询，不根据商品名称猜测",
    "skuId": "可选 SKU ID，用于限定颜色、尺寸、型号等具体规格",
    "scoreMin": "最低评分，1至5；正向卖点通常使用 4",
    "scoreMax": "最高评分，1至5；差评痛点通常使用 3，严重问题可使用 2",
    "helpfulMin": "最小有用数，不小于 0；有用数表示参考价值，不代表观点出现次数",
    "helpfulMax": "最大有用数，不小于 0；有用数表示参考价值，不代表观点出现次数",
    "commentTimeMin": "最早评论发表时间，ISO 8601；不是数据采集时间",
    "commentTimeMax": "最晚评论发表时间，ISO 8601；不是数据采集时间",
    "sort": "评论排序字段：commentTime 评论时间、helpful 有用数、score 评分、createTime 采集时间",
}

_apply_descriptions(GoodsSearchInput, GOODS_DESCRIPTIONS)
_apply_descriptions(ImageSearchInput, {**GOODS_DESCRIPTIONS, "image": ImageSearchInput.model_fields["image"].description or "图片"})
_apply_descriptions(MallSearchInput, MALL_DESCRIPTIONS)
_apply_descriptions(CategorySearchInput, CATEGORY_DESCRIPTIONS)
_apply_descriptions(KeywordSearchInput, KEYWORD_DESCRIPTIONS)
_apply_descriptions(ReviewSearchInput, REVIEW_DESCRIPTIONS)


def as_jsonable(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value
