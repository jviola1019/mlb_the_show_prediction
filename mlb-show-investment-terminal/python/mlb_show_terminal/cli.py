"""Command line entrypoint for the Python model/data backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .artifacts import score_row, score_rows, write_csv, write_json
from .audit import audit_parity, audit_repo, parity_markdown
from .historical import evaluate_backtest, read_records
from .snapshots import (
    backtest_upgrade_files,
    build_upgrade_labels,
    read_csv_records,
    score_snapshot,
    snapshot_live_cards,
    write_records_csv,
)
from .uuid_tools import parse_uuid_tokens


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        payload = payload["records"]
    if isinstance(payload, dict):
        payload = [payload]
    return [dict(row) for row in payload if isinstance(row, dict)]


def cmd_score_row(args: argparse.Namespace) -> int:
    payload = _read_json(args.input)
    result = score_row(dict(payload))
    write_json(args.output, result)
    return 0


def cmd_score_scan(args: argparse.Namespace) -> int:
    payload = _read_json(args.input)
    rows = score_rows(_records_from_payload(payload))
    if args.output_json:
        write_json(args.output_json, {"records": rows})
    if args.output_csv:
        write_csv(args.output_csv, rows)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    predictions = read_records(args.predictions)
    labels = read_records(args.labels)
    result = evaluate_backtest(
        predictions,
        labels,
        id_col=args.id_col,
        prob_col=args.prob_col,
        outcome_col=args.outcome_col,
        n_bins=args.n_bins,
    )
    write_json(args.output, result)
    return 0


def cmd_snapshot_live_cards(args: argparse.Namespace) -> int:
    raw = Path(args.uuids).read_text(encoding="utf-8")
    parsed = parse_uuid_tokens(raw)
    rows = snapshot_live_cards(parsed.uuids, snapshot_id=args.snapshot_id, year=args.year)
    write_records_csv(args.output, rows)
    return 0


def cmd_build_upgrade_labels(args: argparse.Namespace) -> int:
    labels = build_upgrade_labels(read_csv_records(args.pre), read_csv_records(args.post))
    write_records_csv(args.output, labels)
    return 0


def cmd_score_snapshot(args: argparse.Namespace) -> int:
    rows = read_records(args.input)
    if not rows:
        rows = read_csv_records(args.input)
    scored = score_snapshot(rows)
    if args.output_json:
        write_json(args.output_json, {"records": scored})
    if args.output_csv:
        write_records_csv(args.output_csv, scored)
    return 0


def cmd_backtest_upgrades(args: argparse.Namespace) -> int:
    result = backtest_upgrade_files(args.predictions, args.labels, n_bins=args.n_bins)
    write_json(args.output, result)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    result = audit_repo(args.repo)
    write_json(args.output, result)
    return 0


def cmd_audit_parity(args: argparse.Namespace) -> int:
    result = audit_parity(args.repo)
    if args.output_json:
        write_json(args.output_json, result)
    if args.output_md:
        Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_md).write_text(parity_markdown(result), encoding="utf-8")
    if not args.output_json and not args.output_md:
        print(parity_markdown(result), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mlb_show_terminal")
    sub = parser.add_subparsers(dest="command", required=True)

    score_row_p = sub.add_parser("score-row")
    score_row_p.add_argument("--input", required=True)
    score_row_p.add_argument("--output", required=True)
    score_row_p.set_defaults(func=cmd_score_row)

    score_scan_p = sub.add_parser("score-scan")
    score_scan_p.add_argument("--input", required=True)
    score_scan_p.add_argument("--output-json")
    score_scan_p.add_argument("--output-csv")
    score_scan_p.set_defaults(func=cmd_score_scan)

    backtest_p = sub.add_parser("backtest")
    backtest_p.add_argument("--predictions", required=True)
    backtest_p.add_argument("--labels", required=True)
    backtest_p.add_argument("--output", required=True)
    backtest_p.add_argument("--id-col", default="uuid")
    backtest_p.add_argument("--prob-col", default="p_cross_next_threshold")
    backtest_p.add_argument("--outcome-col", default="crossed_next_threshold")
    backtest_p.add_argument("--n-bins", type=int, default=5)
    backtest_p.set_defaults(func=cmd_backtest)

    snapshot_p = sub.add_parser("snapshot-live-cards")
    snapshot_p.add_argument("--uuids", required=True, help="Text file containing UUIDs.")
    snapshot_p.add_argument("--snapshot-id", required=True)
    snapshot_p.add_argument("--output", required=True)
    snapshot_p.add_argument("--year", type=int, default=26)
    snapshot_p.set_defaults(func=cmd_snapshot_live_cards)

    labels_p = sub.add_parser("build-upgrade-labels")
    labels_p.add_argument("--pre", required=True)
    labels_p.add_argument("--post", required=True)
    labels_p.add_argument("--output", required=True)
    labels_p.set_defaults(func=cmd_build_upgrade_labels)

    score_snapshot_p = sub.add_parser("score-snapshot")
    score_snapshot_p.add_argument("--input", required=True)
    score_snapshot_p.add_argument("--output-json")
    score_snapshot_p.add_argument("--output-csv")
    score_snapshot_p.set_defaults(func=cmd_score_snapshot)

    backtest_upgrades_p = sub.add_parser("backtest-upgrades")
    backtest_upgrades_p.add_argument("--predictions", required=True)
    backtest_upgrades_p.add_argument("--labels", required=True)
    backtest_upgrades_p.add_argument("--output", required=True)
    backtest_upgrades_p.add_argument("--n-bins", type=int, default=5)
    backtest_upgrades_p.set_defaults(func=cmd_backtest_upgrades)

    audit_p = sub.add_parser("audit")
    audit_p.add_argument("--repo", default=".")
    audit_p.add_argument("--output", required=True)
    audit_p.set_defaults(func=cmd_audit)

    audit_repo_p = sub.add_parser("audit-repo")
    audit_repo_p.add_argument("--repo", default=".")
    audit_repo_p.add_argument("--output", required=True)
    audit_repo_p.set_defaults(func=cmd_audit)

    audit_parity_p = sub.add_parser("audit-parity")
    audit_parity_p.add_argument("--repo", default=".")
    audit_parity_p.add_argument("--output-json")
    audit_parity_p.add_argument("--output-md")
    audit_parity_p.set_defaults(func=cmd_audit_parity)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
