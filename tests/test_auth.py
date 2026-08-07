import unittest
from pathlib import Path
from unittest.mock import patch

import geekbi_temu_mcp.auth as auth
from geekbi_temu_mcp.auth import ActionRequired, AuthManager, VERSION_HEADER


class AuthTests(unittest.TestCase):
    def test_default_auth_path_uses_platform_user_config_directory(self):
        config_root = Path("/runtime-selected-config")
        with patch.object(auth, "user_config_path", return_value=config_root) as resolver:
            path = auth.default_auth_path()

        resolver.assert_called_once_with(
            "GeekBI",
            appauthor=False,
            ensure_exists=True,
        )
        self.assertEqual(
            config_root / "temu-research-mcp" / "agent-auth.json",
            path,
        )

    def test_version_header_identifies_mcp_client(self):
        manager = AuthManager("https://openapi.geekbi.com")
        headers = manager._headers()
        self.assertEqual("0.1.0", headers[VERSION_HEADER])
        self.assertIn("GeekBI-Temu-Research-MCP", headers["User-Agent"])

    def test_action_payload_does_not_expose_device_code(self):
        payload = ActionRequired(
            "需要登录后继续",
            "https://example.test/login",
            action="AUTH_REQUIRED",
            expires_in=600,
        ).public_payload()
        self.assertEqual("https://example.test/login", payload["jumpUrl"])
        self.assertNotIn("deviceCode", payload)


if __name__ == "__main__":
    unittest.main()
