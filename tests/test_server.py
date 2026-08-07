import os
import unittest

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

from geekbi_temu_mcp.auth import ActionRequired
from geekbi_temu_mcp.server import _execute, mcp


EXPECTED_TOOLS = {
    "temu_site_list",
    "temu_goods_search",
    "temu_image_search",
    "temu_mall_search",
    "temu_category_search",
    "temu_keyword_search",
    "temu_review_search",
}


class ServerRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_data_tools_are_registered(self):
        tools = await mcp.list_tools()
        self.assertEqual(EXPECTED_TOOLS, {tool.name for tool in tools})
        self.assertTrue(all(tool.output_schema for tool in tools))
        self.assertEqual([], await mcp.list_resource_templates())
        self.assertEqual([], await mcp.list_prompts())

    async def test_stdio_protocol_can_discover_tools(self):
        parameters = StdioServerParameters(
            command=os.path.abspath(".venv/bin/python"),
            args=["-m", "geekbi_temu_mcp"],
            cwd=os.getcwd(),
        )
        async with Client(stdio_client(parameters), mode="legacy") as client:
            tools = await client.list_tools()

            self.assertEqual(EXPECTED_TOOLS, {tool.name for tool in tools.tools})
            self.assertEqual("geekbi-temu-research", client.server_info.name)


class ToolResultTests(unittest.TestCase):
    def test_action_required_is_returned_as_structured_result(self):
        def requires_action():
            raise ActionRequired(
                "需要登录后继续",
                "https://example.test/login",
                action="AUTH_REQUIRED",
            )

        result = _execute(requires_action)

        self.assertTrue(result["actionRequired"])
        self.assertEqual("https://example.test/login", result["jumpUrl"])


if __name__ == "__main__":
    unittest.main()
