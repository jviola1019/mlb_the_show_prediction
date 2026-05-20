"""Server-side persistence adapter for Supabase/Postgres.

Browser clients never receive service credentials. If Supabase is not
configured, every write returns a degraded no-op status and the app remains
read-only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


SERVICE_KEY_ENV = ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY")
TABLE_COLUMNS: dict[str, set[str]] = {
    "market_snapshots": {
        "card_uuid",
        "card_name",
        "rarity",
        "team",
        "position",
        "raw_ask",
        "raw_bid",
        "source_url",
        "source_timestamp",
        "pulled_at",
        "raw_hash",
        "strategy",
    },
    "execution_ledger": {
        "card_uuid",
        "card_name",
        "strategy_type",
        "buy_price",
        "sell_price",
        "exit_price",
        "tax",
        "slippage",
        "fill_status",
        "time_to_fill_minutes",
        "holding_time_hours",
        "expected_net_stubs",
        "model_prediction",
        "validation",
        "timestamp",
    },
    "model_predictions": {
        "card_uuid",
        "prediction_timestamp",
        "final_action",
        "strategy",
        "provenance",
        "raw_hash",
        "realized_ledger_id",
    },
    "validation_runs": {
        "run_timestamp",
        "validation_tier",
        "data_coverage_tier",
        "performance_validation_tier",
        "sample_size",
        "horizons",
        "metrics",
        "baselines",
        "verdict",
    },
    "audit_events": {
        "event_timestamp",
        "event_type",
        "severity",
        "card_uuid",
        "payload",
        "app_version",
        "git_commit",
    },
}


def persistence_status() -> dict[str, Any]:
    url = os.environ.get("SUPABASE_URL")
    key = _service_key()
    db_url = os.environ.get("SUPABASE_DB_URL")
    if url and key:
        return {
            "status": "configured",
            "mode": "supabase-rest",
            "server_side_writes": True,
            "credential_exposure": "server-only",
            "write_auth": "required",
            "write_auth_configured": _write_token_configured(),
        }
    if db_url:
        if not _psycopg_available():
            return {
                "status": "disabled",
                "mode": "postgres-url missing driver",
                "server_side_writes": False,
                "credential_exposure": "server-only",
                "reason": "SUPABASE_DB_URL is set but psycopg is not installed",
                "write_auth": "required",
                "write_auth_configured": _write_token_configured(),
            }
        return {
            "status": "configured",
            "mode": "postgres-url",
            "server_side_writes": True,
            "credential_exposure": "server-only",
            "write_auth": "required",
            "write_auth_configured": _write_token_configured(),
        }
    return {
        "status": "disabled",
        "mode": "read-only degraded",
        "server_side_writes": False,
        "credential_exposure": "none",
        "reason": "SUPABASE_URL + service key or SUPABASE_DB_URL is not set",
    }


def write_table(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    if table not in TABLE_COLUMNS:
        return {"status": "rejected", "table": table, "reason": "table is not persistence-whitelisted"}
    payload = _sanitize_payload(table, payload)
    if not payload:
        return {"status": "rejected", "table": table, "reason": "payload contains no whitelisted columns"}
    status = persistence_status()
    if status["status"] != "configured":
        return {"status": "disabled", "table": table, "reason": status.get("reason")}
    if status["mode"] == "supabase-rest":
        return _write_rest(table, payload)
    return _write_postgres(table, payload)


def _service_key() -> str | None:
    for name in SERVICE_KEY_ENV:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _write_token_configured() -> bool:
    return bool(os.environ.get("TERMINAL_WRITE_TOKEN") or os.environ.get("MLB_SHOW_WRITE_TOKEN"))


def _psycopg_available() -> bool:
    try:
        import psycopg  # noqa: F401
    except Exception:
        return False
    return True


def _write_rest(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = _service_key()
    if not key:
        return {"status": "disabled", "table": table, "reason": "service key missing"}
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}",
        data=json.dumps(payload, default=str).encode("utf-8"),
        headers={
            "apikey": key,
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
            "prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310: configured user endpoint
            return {"status": "ok", "table": table, "http_status": resp.status}
    except urllib.error.HTTPError as exc:
        return {"status": "error", "table": table, "http_status": exc.code, "reason": exc.read().decode("utf-8", "replace")}
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return {"status": "error", "table": table, "reason": str(exc)}


def _write_postgres(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        import psycopg  # type: ignore
    except Exception:
        return {
            "status": "disabled",
            "table": table,
            "reason": "SUPABASE_DB_URL set but psycopg is not installed",
        }
    columns = list(payload)
    placeholders = ", ".join(["%s"] * len(columns))
    names = ", ".join(_quote_identifier(column) for column in columns)
    values = [json.dumps(payload[c], default=str) if isinstance(payload[c], (dict, list)) else payload[c] for c in columns]
    sql = f"insert into {_quote_identifier(table)} ({names}) values ({placeholders}) on conflict do nothing"
    with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, values)
        conn.commit()
    return {"status": "ok", "table": table}


def _sanitize_payload(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = TABLE_COLUMNS[table]
    return {key: value for key, value in payload.items() if key in allowed}


def _quote_identifier(identifier: str) -> str:
    if identifier not in TABLE_COLUMNS and not any(identifier in columns for columns in TABLE_COLUMNS.values()):
        raise ValueError(f"identifier is not whitelisted: {identifier}")
    return '"' + identifier.replace('"', '""') + '"'
