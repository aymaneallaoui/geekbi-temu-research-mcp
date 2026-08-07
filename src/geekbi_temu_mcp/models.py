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


def as_jsonable(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value

