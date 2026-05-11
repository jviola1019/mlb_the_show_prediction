import unittest

from mlb_show_terminal.scan import scan_payload
from mlb_show_terminal.uuid_tools import parse_uuid_tokens


UUID_TEXT = """
1baa8f3043c881ac39373bebaad2e452
4cd5d752f840a66c41a812b2c87fd1db
3ad82b308c619a30af8f7ed3428417d0
dfac371ba3d128f372218dbe91469198
28f604e21ac1964af3f09ed7ce811a6c
0e07052fd941f0ae83ddf986fbff60fe
1db8c408ccc6a61a8d65f43b8754549e
f40d34d36b7103d1b0cc8cef6b2bb9c6
76ef7e9d2fac836db23a76579f733024
c947f75a502b342295c8fcf68d5b9590
df54709556e526558a05bd4825bc73c9
effe2ba20c0c40fc4887e6b536c3639c
5451cf8b33e3895bc038ac427478d907
01d3a492b101d1248e94f1e6849b8fbd
2202836a6595b48e61f9c0f063ec5390
8cb6ef3efa9fdef784ece7cb0bfe292f
326429edc16a998e0a3020886cca8891
a1a576f02d863b09d77a7ceeb79592fb
3e6f045aba05631c48da29aacc9b6261
79ec96dacdb53fcbc78cb826f9620c04
cce51b3e9feff60ef004d79cfd848221
55fb77566aba38ade96f2da28aae64d1
ad61e144abe6cd16d8132eb82b26d44d
42618a363c407b4e589478a9b9db2139
3d07a2e52ec2996a939d11568a374fb8
"""


class ScanDecisionTests(unittest.TestCase):
    def test_25_uuid_fixture_shape_has_no_mutation_or_silent_row_loss(self):
        parsed = parse_uuid_tokens(UUID_TEXT)
        self.assertEqual(len(parsed.uuids), 25)
        self.assertEqual(parsed.invalid_tokens, [])
        rows = [
            {
                "uuid": uuid,
                "name": f"Fixture {idx}",
                "rarity": "Gold",
                "current_ovr": 80 + (idx % 5),
                "raw_ask": 1200,
                "raw_bid": 1000 if idx % 3 else None,
                "liquidity_score": 1 if idx % 3 else 0.01,
                "liquidity_n": 25,
                "liquidity_recent": 25,
            }
            for idx, uuid in enumerate(parsed.uuids)
        ]

        payload = scan_payload({"rows": rows, "rate_delay": 0, "enrich_mlb_stats": False})
        self.assertEqual(len(payload["records"]), 25)
        self.assertEqual(payload["progress"]["completed"], 25)
        self.assertEqual(payload["counts"]["dropped"], 0)
        self.assertEqual([row["uuid"] for row in payload["records"]], parsed.uuids)
        for row in payload["records"]:
            self.assertIn(row["decision_action"], {"BUY FLIP", "NO TRADE", "HOLD", "WATCH", "SELL", "BUY SPECULATIVE"})
            self.assertTrue(row["decision_reason_codes"])
            self.assertEqual(row["rarity"], "Gold")
            self.assertNotEqual(row["rarity"], row.get("decision_tier"))

    def test_valid_not_investable_market_data_routes_to_no_trade_not_dropped(self):
        payload = scan_payload({
            "rows": [
                {
                    "uuid": "a" * 32,
                    "name": "Missing Bid",
                    "rarity": "Gold",
                    "current_ovr": 84,
                    "raw_ask": 1200,
                    "raw_bid": None,
                    "liquidity_score": 1,
                }
            ],
            "rate_delay": 0,
        })
        self.assertEqual(payload["counts"]["dropped"], 0)
        self.assertEqual(payload["counts"]["no_trade"], 1)
        row = payload["partitions"]["no_trade"][0]
        self.assertEqual(row["decision_action"], "NO TRADE")
        self.assertIn("MISSING_BUY_PRICE", row["decision_blockers"])


if __name__ == "__main__":
    unittest.main()
