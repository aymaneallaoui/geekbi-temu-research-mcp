"""MCP tool inputs and query serialization."""

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
    """Shared query validation and URL parameter conversion."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

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
            if minimum is not None and maximum is not None:
                if isinstance(minimum, datetime) and (minimum.tzinfo is None) != (maximum.tzinfo is None):
                    raise ValueError(f"{name} and {maximum_name} must use consistent timezone awareness")
                if minimum > maximum:
                    raise ValueError(f"{name} must not exceed {maximum_name}")
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
    siteId: int = Field(48, ge=1, description="GeekBI site ID; defaults to 48 (United States)")
    page: int = Field(1, ge=1, description="Page number, starting at 1")
    size: int = Field(20, ge=1, le=200, description="Results per page, at most 200")
    order: Order = Field("desc", description="Sort direction")


class GoodsSearchInput(PagingInput):
    """Shared product and image search filters."""

    keyword: str | None = Field(None, max_length=300, description="Product name or brand keyword")
    catIds: list[int] | None = Field(None, description="Temu category IDs; matches any supplied category")
    hostingMode: Literal[1, 2] | None = Field(None, description="1 = fully managed; 2 = semi-managed")
    sort: GoodsSort | None = Field(None, description="Sort field; image search defaults to similarity order")

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
    similarNumMin: float | None = Field(None, description="Minimum similar-product count")
    similarNumMax: float | None = Field(None, description="Maximum similar-product count; low competition usually at most 10")
    priceMin: float | None = Field(None, description="Minimum product price in site currency")
    priceMax: float | None = Field(None, description="Maximum product price in site currency")
    supplyPriceMin: float | None = Field(None, description="Minimum supply price in CNY")
    supplyPriceMax: float | None = Field(None, description="Maximum supply price in CNY")
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
            "Image URL, Data URI, or base64: data (10 MB maximum). Local files are supported only in stdio mode."
        )
    )


class MallSearchInput(PagingInput):
    keyword: str | None = Field(None, max_length=300, description="Store name keyword")
    catIds: list[int] | None = Field(None, description="Main category IDs; matches any supplied category")
    hostingMode: Literal[1, 2] | None = Field(None, description="1 = fully managed; 2 = semi-managed")
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
    keyword: str | None = Field(None, max_length=300, description="Category name in English or Chinese")
    catLevel: Literal[1, 2, 3, 4] | None = Field(None, description="Category level")
    parentCatId: int | None = Field(None, ge=0, description="Parent category ID; 0 is the root")
    sort: CategorySort | None = None


class KeywordSearchInput(MarketSearchInput):
    keyword: str | None = Field(None, max_length=300, description="Keyword in English or Chinese")
    catIds: list[int] | None = Field(None, description="Temu category ID")
    sort: KeywordSort | None = None
    firstOnSaleTimeMin: datetime | None = Field(None, description="Earliest associated product listing time, lower bound")
    firstOnSaleTimeMax: datetime | None = Field(None, description="Earliest associated product listing time, upper bound")


class ReviewSearchInput(PagingInput):
    goodsId: str = Field(min_length=1, max_length=100, description="Temu product ID")
    skuId: str | None = Field(None, max_length=100, description="Optional SKU ID")
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
            raise ValueError("Reviews are limited to the first 10,000 results; narrow your filters")
        return self



_METRICS = {
    "sold": "Total units sold", "sales": "Total revenue in site currency",
    "mallSold": "Store total units sold", "mallSales": "Store total revenue in site currency",
    "mallStar": "Store rating", "goodsScore": "Product rating", "reviewNum": "Review count",
    "goodsNum": "Store product count", "followerNum": "Store follower count",
    "avgPrice": "Average price in site currency", "price": "Product price in site currency",
    "supplyPrice": "Supply price in CNY (convert currencies before calculating margins)",
    "similarNum": "Similar-product count (up to 10 usually low competition; 11-20 moderate; over 20 high)",
    "quantity": "Inventory snapshot; zero may mean unrecorded, not out of stock",
    "dsr": "Blue-ocean supply/demand index; cross-check demand, growth, supply, and price",
    "totalSold": "Total units sold", "totalSales": "Total revenue in site currency",
    "itemCount": "Associated product count", "mallCount": "Associated store count",
    "semiManagedItemCount": "Associated semi-managed product count",
    "semiManagedMallCount": "Associated semi-managed store count",
    "onSaleTime": "Product listing time (absolute ISO 8601 timestamp)",
    "mallOpenTime": "Store opening time (absolute ISO 8601 timestamp)",
    "firstOnSaleTime": "Earliest product listing under the keyword, not keyword creation time (ISO 8601)",
    "commentTime": "Review publication time, not collection time (ISO 8601)",
    "score": "Review rating, 1-5", "helpful": "Helpful votes; indicates usefulness, not theme frequency",
}
_COMMON_DESCRIPTIONS = {
    "siteId": "GeekBI site ID; 48 = US. Look up other countries with temu_site_list; never guess.",
    "page": "Page number starting at 1; keep all other filters unchanged across pages.",
    "size": "Results per page (1-200). Use 200 and continue pagination for complete results.",
    "order": "desc = highest/newest first; asc = lowest/oldest first.",
    "catIds": "Trusted level 1 or 2 category IDs from the user or category search; matches any ID. Usually choose keyword OR category.",
    "hostingMode": "1 = fully managed; 2 = semi-managed. Compare these modes separately.",
    "catLevel": "Category level (1-4); prefer level 1 or 2 unless deeper analysis is requested.",
    "parentCatId": "Trusted parent category ID; returns immediate children. 0 = root.",
    "goodsId": "Required product ID from the user or product search; never infer it from a name.",
    "skuId": "Optional SKU ID to filter a particular color, size, or model.",
}


def _describe_inputs() -> None:
    for model in (GoodsSearchInput, ImageSearchInput, MallSearchInput, CategorySearchInput, KeywordSearchInput, ReviewSearchInput):
        for name, field in model.model_fields.items():
            if name in _COMMON_DESCRIPTIONS:
                field.description = _COMMON_DESCRIPTIONS[name]
            elif name == "keyword":
                subject = {MallSearchInput: "Store name or ID", CategorySearchInput: "Category name", KeywordSearchInput: "Keyword"}.get(model, "Product name or brand")
                field.description = subject + " in English or Chinese, at most 300 characters. Preserve user input; usually choose keyword OR category."
            elif name == "sort":
                field.description = {
                    MallSearchInput: "Store sort: mallSold/mallSales for leaders, reviewNum for review volume, mallOpenTime for new stores, SoldRate/SalesRate for growth, SellthroughRate for efficiency.",
                    CategorySearchInput: "Category sort: totalSold for popularity, dsr for supply/demand, monthSoldRate/monthSalesRate for growth; require meaningful demand volume.",
                    KeywordSearchInput: "Keyword sort: totalSold for popularity, dsr for supply/demand, firstOnSaleTime for earliest product listing (not keyword age), monthSoldRate/monthSalesRate for growth.",
                    ReviewSearchInput: "Review sort: commentTime (publication), helpful (usefulness), score (rating), createTime (collection).",
                }.get(model, "Product sort: daySold (popular), sold (cumulative), minPrice (price), onSaleTime (new), similarNum (competition). Omit for image similarity order.")
            elif name.endswith(("Min", "Max")):
                metric = name[:-3]
                label = _METRICS.get(metric)
                for prefix, period in (("day", "1-day"), ("week", "7-day"), ("month", "30-day")):
                    if metric.startswith(prefix):
                        suffix = metric[len(prefix):]
                        label = {"Sold": "Units sold", "Sales": "Revenue in site currency", "ItemCount": "Product count change (may be negative)", "MallCount": "Store count change (may be negative)", "Follower": "Follower count", "SellthroughCount": "Products with sales", "SellthroughRate": "Sell-through percentage (0-100; 20% = 20)"}.get(suffix)
                        if suffix.endswith("Rate") and suffix != "SellthroughRate":
                            label = suffix[:-4] + " growth rate (decimal; 20% = 0.2)"
                        if model == MallSearchInput and label and suffix in ("Sold", "Sales", "ItemCount", "Follower"):
                            label = {"Sold": "Average units sold", "Sales": "Average revenue in site currency", "ItemCount": "Average product count", "Follower": "Average follower count"}[suffix]
                        if label:
                            label = period + " " + label
                        break
                if label:
                    bound = "Lower" if name.endswith("Min") else "Upper"
                    field.description = f"{bound} bound: {label}. Either bound may be supplied alone."
        model.model_rebuild(force=True)


_describe_inputs()


def as_jsonable(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value
