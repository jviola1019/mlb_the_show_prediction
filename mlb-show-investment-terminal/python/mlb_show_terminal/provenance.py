"""Source provenance and audit metadata helpers."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any


MODEL_VERSION = "forecast-governance-v1.3.0"


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def provenance_for_listing(
    listing: dict[str, Any] | None,
    *,
    sample_size: int | None = None,
    validation_tier: str | None = None,
    data_coverage_tier: str | None = None,
    performance_validation_tier: str | None = None,
    rule_version: str | None = None,
) -> dict[str, Any]:
    listing = listing or {}
    fetched_at = listing.get("fetched_at")
    source_timestamp = listing.get("source_timestamp") or listing.get("listing_timestamp") or fetched_at
    pulled_at = _utc_now()
    return {
        "source": "mlb-the-show-community-market",
        "source_url": listing.get("source_url"),
        "listing_timestamp": source_timestamp,
        "pull_timestamp": fetched_at or pulled_at,
        "api_response_timestamp": fetched_at or pulled_at,
        "data_freshness": "unknown" if not fetched_at else "reported",
        "sample_size": sample_size,
        "validation_tier": performance_validation_tier or validation_tier,
        "data_coverage_tier": data_coverage_tier,
        "performance_validation_tier": performance_validation_tier or validation_tier,
        "raw_data_hash": stable_hash(listing),
        "model_version": MODEL_VERSION,
        "rule_version": rule_version,
    }


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
