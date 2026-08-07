import unittest

from pydantic import ValidationError

from geekbi_temu_mcp.models import (
    CategorySearchInput,
    GoodsSearchInput,
    ImageSearchInput,
    KeywordSearchInput,
    MallSearchInput,
    ReviewSearchInput,
)


GOODS_BASE = {"keyword", "catIds", "siteId", "page", "size", "sort", "order", "hostingMode"}
GOODS_RANGES = {
    "sold",
    "daySold",
    "weekSold",
    "monthSold",
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
    "quantity",
    "mallSold",
    "similarNum",
    "price",
    "supplyPrice",
    "goodsScore",
    "reviewNum",
    "onSaleTime",
    "mallOpenTime",
}
MALL_BASE = GOODS_BASE
MALL_RANGES = {
    "mallSold",
    "mallSales",
    "mallStar",
    "reviewNum",
    "goodsNum",
    "followerNum",
    "avgPrice",
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
}
MARKET_RANGES = {
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
}


def ranged(names):
    return {f"{name}{suffix}" for name in names for suffix in ("Min", "Max")}


class SearchModelTests(unittest.TestCase):
    def test_all_skill_query_fields_are_migrated(self):
        self.assertEqual(GOODS_BASE | ranged(GOODS_RANGES), set(GoodsSearchInput.model_fields))
        self.assertEqual((MALL_BASE | ranged(MALL_RANGES)), set(MallSearchInput.model_fields))
        self.assertEqual(
            {"keyword", "catLevel", "parentCatId", "siteId", "page", "size", "sort", "order"}
            | ranged(MARKET_RANGES),
            set(CategorySearchInput.model_fields),
        )
        self.assertEqual(
            {"keyword", "catIds", "siteId", "page", "size", "sort", "order"}
            | ranged(MARKET_RANGES | {"firstOnSaleTime"}),
            set(KeywordSearchInput.model_fields),
        )
        self.assertEqual(set(GoodsSearchInput.model_fields) | {"image"}, set(ImageSearchInput.model_fields))
        self.assertEqual(
            {
                "goodsId",
                "siteId",
                "skuId",
                "scoreMin",
                "scoreMax",
                "helpfulMin",
                "helpfulMax",
                "commentTimeMin",
                "commentTimeMax",
                "sort",
                "order",
                "page",
                "size",
            },
            set(ReviewSearchInput.model_fields),
        )

    def test_query_items_repeat_category_ids_and_include_defaults(self):
        query = GoodsSearchInput(catIds=[101, 202], similarNumMax=10)
        items = query.query_items()
        self.assertEqual([("catIds", "101"), ("catIds", "202")], [item for item in items if item[0] == "catIds"])
        self.assertIn(("siteId", "48"), items)
        self.assertIn(("similarNumMax", "10.0"), items)

    def test_invalid_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            GoodsSearchInput(monthSoldMin=100, monthSoldMax=10)

    def test_review_window_is_limited_to_first_ten_thousand(self):
        with self.assertRaises(ValidationError):
            ReviewSearchInput(goodsId="601", page=51, size=200)


if __name__ == "__main__":
    unittest.main()

