import unittest

from app.db_utils import LIKE_ESCAPE_CHAR, escape_like_literal


class EscapeLikeLiteralTests(unittest.TestCase):
    """escape_like_literal() must treat % and _ as literal characters."""

    def test_percent_is_escaped(self):
        result = escape_like_literal("50%")
        self.assertEqual(result, r"50\%")

    def test_underscore_is_escaped(self):
        result = escape_like_literal("file_name")
        self.assertEqual(result, r"file\_name")

    def test_backslash_is_escaped_first(self):
        # A literal backslash must become \\ so it doesn't accidentally
        # escape the % or _ that follows it.
        result = escape_like_literal("C:\\path")
        self.assertEqual(result, r"C:\\path")

    def test_backslash_before_percent(self):
        # "\%" in input should become "\\%" (escaped backslash + escaped percent),
        # not "\\%" treated as an escaped percent.
        result = escape_like_literal("\\%")
        self.assertEqual(result, r"\\\%")

    def test_plain_text_unchanged(self):
        result = escape_like_literal("hello world")
        self.assertEqual(result, "hello world")

    def test_empty_string_unchanged(self):
        self.assertEqual(escape_like_literal(""), "")

    def test_multiple_metacharacters(self):
        result = escape_like_literal("%100_off%")
        self.assertEqual(result, r"\%100\_off\%")

    def test_escape_char_constant_is_backslash(self):
        self.assertEqual(LIKE_ESCAPE_CHAR, "\\")

    def test_wrapped_pattern_does_not_match_everything(self):
        # Wrapping the escaped result in %…% should not produce %% (match-all).
        escaped = escape_like_literal("%")
        like_pattern = f"%{escaped}%"
        # The pattern must contain the literal escaped percent, not collapse to %%
        self.assertIn(r"\%", like_pattern)
        self.assertNotEqual(like_pattern, "%%")


if __name__ == "__main__":
    unittest.main()
