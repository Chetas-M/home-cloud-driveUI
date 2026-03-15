import unittest

from backend.app.routers.files import build_content_disposition


class ContentDispositionTests(unittest.TestCase):
    def test_uses_rfc_6266_filename_star_encoding(self):
        header = build_content_disposition("attachment", 'report "final"\r\nInjected: 1.txt')

        self.assertIn("filename*=UTF-8''report%20%22final%22__Injected%3A%201.txt", header)
        self.assertIn('filename="report _final__Injected_ 1.txt"', header)
        self.assertNotIn("\r", header)
        self.assertNotIn("\n", header)


if __name__ == "__main__":
    unittest.main()
