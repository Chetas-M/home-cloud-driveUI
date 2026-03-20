import os
import tempfile
import unittest

from app.models import File
from app.search_index import build_match_context, build_search_document


class SearchIndexTests(unittest.TestCase):
    def test_build_search_document_extracts_text_for_text_files(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write("# Release Notes\nSearch indexing should find this sentence.\n")
            temp_path = handle.name

        try:
            indexed = build_search_document(temp_path, "notes.md", "text/markdown", "text")
            self.assertIn("Search indexing should find this sentence.", indexed)
        finally:
            os.remove(temp_path)

    def test_build_match_context_prefers_content_snippet(self):
        file = File(
            name="quarterly-report.txt",
            type="text",
            mime_type="text/plain",
            path='["finance"]',
            content_index="Revenue increased sharply after the new search launch and support stayed stable.",
        )

        snippet = build_match_context(file, "search", ["finance"])

        self.assertIn("search launch", snippet.lower())
        self.assertTrue(snippet.startswith("...") or len(snippet) <= 180)


if __name__ == "__main__":
    unittest.main()
