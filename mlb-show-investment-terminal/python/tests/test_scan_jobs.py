"""Tests for the scan-job runner: lifecycle, LRU eviction, snapshot isolation."""

from __future__ import annotations

import time
import unittest

from mlb_show_terminal import scan_jobs


class ScanJobLifecycleTests(unittest.TestCase):
    def setUp(self):
        scan_jobs.clear_scan_jobs()

    def tearDown(self):
        scan_jobs.clear_scan_jobs()

    def test_completes_with_row_payload(self):
        info = scan_jobs.start_scan_job({
            "rows": [
                {
                    "uuid": "a",
                    "name": "Flip",
                    "raw_ask": 1538,
                    "raw_bid": 1120,
                    "liquidity_score": 1,
                    "current_ovr": 84,
                    "rarity": "Gold",
                }
            ],
            "rate_delay": 0,
        })
        job_id = info["job_id"]
        for _ in range(40):
            current = scan_jobs.get_scan_job(job_id)
            if current and current.get("status") == "complete":
                break
            time.sleep(0.02)
        self.assertEqual(current["status"], "complete")
        self.assertGreaterEqual(current["completed"], 1)
        self.assertIsNotNone(current["result"])

    def test_lru_caps_at_max_jobs(self):
        cap = scan_jobs.MAX_JOBS
        # Start more than the cap; older jobs should be evicted.
        ids: list[str] = []
        for _ in range(cap + 5):
            info = scan_jobs.start_scan_job({"rows": [], "rate_delay": 0})
            ids.append(info["job_id"])
        # Let any background work settle so we don't race on dict updates
        for _ in range(20):
            time.sleep(0.01)
        active = scan_jobs.list_scan_jobs()
        self.assertLessEqual(len(active), cap)
        # First five should have been evicted
        for evicted_id in ids[:5]:
            self.assertIsNone(
                scan_jobs.get_scan_job(evicted_id),
                f"job {evicted_id} should have been evicted",
            )
        # Most recent should still be present
        self.assertIsNotNone(scan_jobs.get_scan_job(ids[-1]))

    def test_get_scan_job_unknown_id_returns_none(self):
        self.assertIsNone(scan_jobs.get_scan_job("does-not-exist"))

    def test_snapshot_is_a_deep_copy(self):
        info = scan_jobs.start_scan_job({"rows": [], "rate_delay": 0})
        snap = scan_jobs.get_scan_job(info["job_id"])
        snap["status"] = "tampered"
        again = scan_jobs.get_scan_job(info["job_id"])
        self.assertNotEqual(again["status"], "tampered")


if __name__ == "__main__":
    unittest.main()
