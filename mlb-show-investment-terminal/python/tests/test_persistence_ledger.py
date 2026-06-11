import os
import sys
import unittest
from unittest.mock import patch

from mlb_show_terminal.ledger import realized_trade_metrics, validate_ledger_row
from mlb_show_terminal.persistence import persistence_status, write_table


class PersistenceLedgerTests(unittest.TestCase):
    def test_persistence_is_safely_disabled_without_server_env(self):
        with patch.dict(os.environ, {}, clear=True):
            status = persistence_status()
            self.assertEqual(status["status"], "disabled")
            self.assertFalse(status["server_side_writes"])
            self.assertEqual(write_table("market_snapshots", {"card_uuid": "a"})["status"], "disabled")

    def test_persistence_rejects_non_whitelisted_tables_and_empty_payloads(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(write_table("not_a_table", {"card_uuid": "a"})["status"], "rejected")
            self.assertEqual(write_table("market_snapshots", {"bad_column": "a"})["status"], "rejected")

    def test_postgres_mode_does_not_reach_dynamic_sql_for_untrusted_payload_shape(self):
        with patch.dict(os.environ, {"SUPABASE_DB_URL": "postgresql://example"}, clear=True):
            with patch.dict(sys.modules, {"psycopg": None}):
                result = write_table("execution_ledger", {"card_uuid": "a", "bad);drop table x;--": "x"})
                self.assertEqual(result["status"], "disabled")
                self.assertIn("psycopg", result["reason"])

    def test_ledger_validation_and_realized_edge_metrics(self):
        self.assertFalse(validate_ledger_row({"card_uuid": "a"})["valid"])
        rows = [
            {
                "card_uuid": "a",
                "timestamp": "2026-05-13T12:00:00Z",
                "strategy_type": "flip",
                "buy_price": 1000,
                "sell_price": 1200,
                "expected_net_stubs": 100,
                "slippage": 2,
                "tax": 0.10,
                "time_to_fill_minutes": 12,
                "holding_time_hours": 1.5,
            }
        ]
        metrics = realized_trade_metrics(rows)
        self.assertEqual(metrics["closed_trades"], 1)
        self.assertAlmostEqual(metrics["realized_profit"], 78)
        self.assertAlmostEqual(metrics["expected_vs_realized_stubs"], -22)
        self.assertAlmostEqual(metrics["average_time_to_fill_minutes"], 12)
        self.assertAlmostEqual(metrics["average_holding_time_hours"], 1.5)
        self.assertEqual(metrics["by_strategy"]["flip"]["closed_trades"], 1)

    def test_ledger_metrics_track_lifecycle_states_and_row_tax(self):
        rows = [
            {
                "card_uuid": "a",
                "timestamp": "2026-05-13T12:00:00Z",
                "strategy_type": "flip",
                "buy_price": 1000,
                "sell_price": 1100,
                "tax": 5,
                "expected_net_stubs": 80,
                "fill_status": "filled",
            },
            {
                "card_uuid": "b",
                "timestamp": "2026-05-13T12:00:00Z",
                "strategy_type": "hold",
                "buy_price": 1000,
                "fill_status": "open",
            },
            {
                "card_uuid": "c",
                "timestamp": "2026-05-13T12:00:00Z",
                "strategy_type": "flip",
                "buy_price": 1000,
                "fill_status": "expired",
            },
        ]
        metrics = realized_trade_metrics(rows)
        self.assertEqual(metrics["rows"], 3)
        self.assertEqual(metrics["open_positions"], 1)
        self.assertEqual(metrics["failed_exits"], 1)
        self.assertAlmostEqual(metrics["realized_profit"], 45)
        self.assertAlmostEqual(metrics["failed_exit_rate"], 1 / 3)


if __name__ == "__main__":
    unittest.main()
