import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_score_row_cli_writes_python_backend_payload(self):
        row = {
            "raw_ask": 1538,
            "raw_bid": 1120,
            "liquidity_score": 1,
            "liquidity_n": 8,
            "liquidity_recent": 3,
            "current_ovr": 84,
            "rarity": "gold",
            "recent": {"ops": 0.950, "avg": 0.320, "plateAppearances": 42},
            "season": {"ops": 0.780, "avg": 0.270, "plateAppearances": 180},
        }
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.json"
            out = Path(tmp) / "output.json"
            inp.write_text(json.dumps(row), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mlb_show_terminal.cli",
                    "score-row",
                    "--input",
                    str(inp),
                    "--output",
                    str(out),
                ],
                check=True,
            )
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(payload["python_backend"])
        self.assertEqual(payload["flip"]["action"], "BUY")
        self.assertIn("PYTHON_BACKEND", payload["upgrade"]["reason_codes"])
        self.assertFalse(payload["validation"]["mismatch"])


if __name__ == "__main__":
    unittest.main()
