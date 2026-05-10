import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FreshnessBadge, HighlightedName, RecordsTable } from "./components";

describe("RecordsTable", () => {
  it("renders an empty state", () => {
    render(<RecordsTable rows={[]} />);
    expect(screen.getByText("No rows.")).toBeInTheDocument();
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
        flip_reason_codes: "POSITIVE_AFTER_TAX_EDGE"
      }]}
      onRowClick={(row) => { selected = row.uuid ?? ""; }}
    />);
    expect(screen.getByText("After Tax")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Flip"));
    expect(selected).toBe("abcdef0123456789abcdef0123456789");
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
