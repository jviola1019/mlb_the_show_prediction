import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FreshnessBadge, HighlightedName, RecordsTable } from "./components";

describe("RecordsTable", () => {
  it("renders an empty state", () => {
    render(<RecordsTable rows={[]} />);
    expect(screen.getByText("No rows in this partition.")).toBeInTheDocument();
  });

  it("renders scan rows without requiring frontend quant math", () => {
    render(<RecordsTable rows={[{ name: "Flip", flip: { action: "BUY", roi: 0.125 }, upgrade: { action: "HOLD" } }]} />);
    expect(screen.getAllByText("Flip").length).toBeGreaterThan(0);
    expect(screen.getByText("BUY")).toBeInTheDocument();
  });

  it("renders partition-specific flip columns and supports row selection", () => {
    let selected = "";
    render(<RecordsTable
      kind="flip"
      rows={[{
        uuid: "abcdef0123456789abcdef0123456789",
        name: "Flip",
        raw_bid: 1120,
        raw_ask: 1538,
        after_tax_sale: 1384.2,
        flip_profit: 264.2,
        flip_roi: 0.2359,
        spread_pct: 0.2718,
        flip_reason_codes: "POSITIVE_AFTER_TAX_EDGE",
        decision_action: "BUY FLIP",
        decision_reason_codes: "EXECUTABLE_FLIP_EDGE,POSITIVE_AFTER_TAX_EDGE",
        forecast_ev_7d: -0.12
      }]}
      onRowClick={(row) => { selected = row.uuid ?? ""; }}
    />);
    expect(screen.getByText("After Tax")).toBeInTheDocument();
    expect(screen.getByText("Flip ROI")).toBeInTheDocument();
    expect(screen.getByText("Forecast EV")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Flip"));
    expect(selected).toBe("abcdef0123456789abcdef0123456789");
  });

  it("renders marketplace rarity separately from validation tier", () => {
    render(<RecordsTable
      kind="observational"
      rows={[{
        name: "Gold Card",
        rarity: "Gold",
        card: { rarity: "Gold", current_ovr: 83 },
        validation_tier: "BRONZE",
        forecast_ev_7d: -0.18,
        gates_failed_csv: "calibration_present",
        decision_action: "WATCH",
        decision_reason_codes: "FORECAST_DIAGNOSTIC_ONLY"
      }]}
    />);
    expect(screen.getByText("Rarity")).toBeInTheDocument();
    expect(screen.getByText("Validation Tier")).toBeInTheDocument();
    expect(screen.getAllByText("Gold").length).toBeGreaterThan(0);
    expect(screen.getByText("BRONZE")).toBeInTheDocument();
  });

  it("empty no-trade table explains blockers instead of generic no rows", () => {
    render(<RecordsTable kind="no_trade" rows={[]} />);
    expect(screen.getByText(/No no-trade rows/i)).toBeInTheDocument();
    expect(screen.queryByText("no reasons")).not.toBeInTheDocument();
  });

  it("highlights exact search substrings", () => {
    render(<div><HighlightedName name="Mike Trout" query="Trout" /></div>);
    expect(screen.getByText("Trout").tagName).toBe("MARK");
  });

  it("renders freshness badges with the supplied label", () => {
    render(<FreshnessBadge at="2026-05-06T12:00:00Z" label="LISTING" />);
    expect(screen.getByText(/LISTING/i)).toBeInTheDocument();
  });
});
