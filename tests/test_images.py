import base64
import unittest

from geekbi_temu_mcp.images import build_multipart, read_image


class ImageTests(unittest.TestCase):
    def test_base64_image_and_multipart(self):
        png = b"\x89PNG\r\n\x1a\n" + b"payload"
        source = "base64:" + base64.b64encode(png).decode("ascii")

        data, content_type, filename = read_image(source, 1)
        body, multipart_type = build_multipart(data, content_type, filename)

        self.assertEqual(png, data)
        self.assertEqual("image/png", content_type)
        self.assertIn(b'Content-Disposition: form-data; name="file"', body)
        self.assertTrue(multipart_type.startswith("multipart/form-data; boundary="))


if __name__ == "__main__":
    unittest.main()

