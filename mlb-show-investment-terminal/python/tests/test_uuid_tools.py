import unittest

from mlb_show_terminal.uuid_tools import parse_uuid_tokens


class UUIDToolsTests(unittest.TestCase):
    def test_extracts_lowercases_and_preserves_order(self):
        a = "ABCDEF0123456789ABCDEF0123456789"
        b = "11111111111111111111111111111111"
        out = parse_uuid_tokens(f"{a}\nzzzzzzzz {b}, {a}")
        self.assertEqual(out.uuids, [a.lower(), b])
        self.assertEqual(out.duplicates, [a.lower()])
        self.assertIn("zzzzzzzz", out.invalid_tokens)


if __name__ == "__main__":
    unittest.main()
