import unittest
from urllib.parse import parse_qs, urlparse

from geekbi_temu_mcp.client import GeekBIClient
from geekbi_temu_mcp.models import GoodsSearchInput


class StubAuth:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def request_json(self, url, timeout, **kwargs):
        self.urls.append(url)
        return self.payload


class GeekBIClientTests(unittest.TestCase):
    def test_site_lookup_preserves_site_and_region_ids(self):
        client = GeekBIClient(base_url="https://example.test", timeout=1)
        client.auth = StubAuth(
            {
                "code": 0,
                "data": [
                    {
                        "siteId": 48,
                        "regionId": 211,
                        "name": "United States",
                        "cnName": "美国",
                        "currency": "USD",
                    }
                ],
            }
        )

        result = client.sites("美国站")

        self.assertEqual(48, result["data"]["matches"][0]["siteId"])
        self.assertEqual(211, result["data"]["matches"][0]["regionId"])

    def test_goods_query_repeats_category_ids(self):
        client = GeekBIClient(base_url="https://example.test", timeout=1)
        auth = StubAuth({"code": 0, "data": {"total": 0, "list": []}})
        client.auth = auth

        client.goods(GoodsSearchInput(catIds=[10, 20], sort="monthSold"))

        query = parse_qs(urlparse(auth.urls[0]).query)
        self.assertEqual(["10", "20"], query["catIds"])
        self.assertEqual(["48"], query["siteId"])
        self.assertEqual(["monthSold"], query["sort"])


if __name__ == "__main__":
    unittest.main()

