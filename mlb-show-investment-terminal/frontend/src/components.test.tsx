import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FreshnessBadge, HighlightedName, RecordsTable } from "./components";
import { tabs } from "./TerminalShell";
import { GuardedVisual } from "./verdictGuard";

describe("RecordsTable", () => {
  it("renders an empty state", () => {
    render(<RecordsTable rows={[]} />);
    expect(screen.getByText("No rows in this partition.")).toBeInTheDocument();
  });

  it("renders scan rows without requiring frontend quant math", () => {
    render(<RecordsTable rows={[{ name: "Flip", flip: { action: "BUY", roi: 0.125 }, upgrade: { action: "HOLD" } }]} />);
    expect(screen.getAllByText("Flip").length).toBeGreaterThan(0);
    expect(screen.getAllByText("OBSERVE").length).toBeGreaterThan(0);
    expect(screen.queryByText("BUY")).not.toBeInTheDocument();
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
    expect(screen.queryByText("-18.00%")).not.toBeInTheDocument();
  });

  it("only renders forecast EV values for investable rows", () => {
    render(<RecordsTable
      rows={[
        {
          name: "Investable",
          forecast_ev_7d: 0.12,
          verdict_status: "INVESTABLE",
          decision_action: "HOLD",
        },
        {
          name: "Observed",
          forecast_ev_7d: -0.18,
          verdict_status: "OBSERVATIONAL ONLY",
          decision_action: "WATCH",
        },
      ]}
    />);
    expect(screen.getByText("12.00%")).toBeInTheDocument();
    expect(screen.queryByText("-18.00%")).not.toBeInTheDocument();
  });

  it("suppresses raw BUY actions when verdict is not investable", () => {
    render(<RecordsTable
      rows={[
        {
          name: "Blocked Buy",
          decision_action: "BUY FLIP",
          flip: { action: "BUY" },
          verdict_status: "NOT INVESTABLE",
        },
        {
          name: "Observed Buy",
          decision_action: "BUY SPECULATIVE",
          upgrade: { action: "BUY SPECULATIVE" },
          verdict_status: "OBSERVATIONAL ONLY",
          forecast_direction: "FORECAST BULLISH",
        },
      ]}
    />);
    expect(screen.getAllByText("ABSTAIN").length).toBeGreaterThan(0);
    expect(screen.getAllByText("OBSERVE UP").length).toBeGreaterThan(0);
    expect(screen.queryByText("BUY FLIP")).not.toBeInTheDocument();
    expect(screen.queryByText("BUY SPECULATIVE")).not.toBeInTheDocument();
  });

  it("exposes the required ten terminal tabs", () => {
    expect(tabs.map((tab) => tab.id)).toEqual([
      "command",
      "scanner",
      "target",
      "matrix",
      "forecast",
      "validation",
      "ledger",
      "risk",
      "audit",
      "ops",
    ]);
  });

  it("renders strategy final action instead of generic investable", () => {
    render(<RecordsTable
      rows={[{
        name: "Matt Olson",
        verdict_status: "INVESTABLE",
        decision_action: "INVESTABLE",
        strategy: {
          composite: { final_action: "INSTANT FLIP ONLY" },
          flip: { verdict: "FLIP PASS" },
          directional: { verdict: "BEARISH" },
          inventory: { verdict: "HIGH LIQUIDITY" },
        },
      }]}
    />);
    expect(screen.getAllByText("INSTANT FLIP ONLY").length).toBeGreaterThan(0);
    expect(screen.queryByText("INVESTABLE")).not.toBeInTheDocument();
  });

  it("suppresses guarded visual children for observational verdicts", () => {
    render(
      <GuardedVisual record={{ verdict_status: "OBSERVATIONAL ONLY" }}>
        <div>EV 99.00%</div>
      </GuardedVisual>
    );
    expect(screen.queryByText("EV 99.00%")).not.toBeInTheDocument();
    expect(screen.getByText(/DIRECTIONAL ONLY/i)).toBeInTheDocument();
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
