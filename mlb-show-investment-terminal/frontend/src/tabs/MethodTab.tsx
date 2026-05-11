import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { Panel, Pill } from "../components";

export function MethodTab() {
  const parity = useQuery({ queryKey: ["parity-audit"], queryFn: api.parity });
  return (
    <div className="grid">
      <Panel title="Architecture">
        <p>React renders the terminal. FastAPI serves `/api` and the static React build from the same origin. Python owns every quant decision and reproducible CLI command.</p>
      </Panel>
      <Panel title="Engine Contracts">
        <pre>{`flip.after_tax_sale = sell_price * 0.90
flip.profit = after_tax_sale - buy_price
flip.roi = profit / buy_price
flip.spread_pct = (sell_price - buy_price) / sell_price

upgrade = scenario threshold model until real historical backtests calibrate it
forecast = diagnostic-only price-history bootstrap
forecast_ev = ((terminal_price * spread_ratio * (1 - tax_rate)) - current_price) / current_price

final decision = explicit policy over separate flip, upgrade, forecast, and data-quality channels`}</pre>
      </Panel>
      <Panel title="Decision Policy">
        <ul className="rule-list">
          <li>BUY FLIP requires executable bid/ask math after tax, positive ROI, and sufficient liquidity.</li>
          <li>BUY SPECULATIVE requires a threshold-crossing roster scenario and executable market data.</li>
          <li>WATCH keeps informational signals visible without issuing a buy.</li>
          <li>NO TRADE shows the exact blocker: missing price, non-executable book, low liquidity, or failed data gate.</li>
          <li>SELL can override a positive flip edge only when downgrade risk is explicit.</li>
        </ul>
      </Panel>
      <Panel title="Deployment">
        <p>Render and Hugging Face use one Docker image. Runtime storage is ephemeral; historical labels are committed artifacts, not written by the hosted app.</p>
      </Panel>
      <Panel title="Known Limitations">
        <ul className="rule-list">
          <li>The Show API rate limits and missing bid/ask data can block executable trades.</li>
          <li>Short, stale, or illiquid price histories make forecast diagnostics observational.</li>
          <li>SDS roster updates are discretionary; scenario probabilities are not guaranteed outcomes.</li>
          <li>Upgrade probabilities are uncalibrated unless real historical roster-update labels are supplied.</li>
          <li>No output guarantees profit.</li>
        </ul>
      </Panel>
      <Panel title="Parity Audit" kicker={parity.data?.generated_at ?? "checking"}>
        <div className="status-line">
          <Pill tone={parity.data?.status === "ok" ? "good" : "warn"}>{parity.data?.status ?? "loading"}</Pill>
          <Pill>parity {parity.data?.counts?.parity ?? 0}</Pill>
          <Pill tone="warn">partial {parity.data?.counts?.partial ?? 0}</Pill>
          <Pill tone="bad">missing {parity.data?.counts?.missing ?? 0}</Pill>
        </div>
        <div className="table-wrap mini-table">
          <table>
            <thead><tr><th>Feature</th><th>Group</th><th>Status</th></tr></thead>
            <tbody>
              {(parity.data?.features ?? []).map((row) => (
                <tr key={String(row.feature_id)}>
                  <td><code>{String(row.feature_id)}</code></td>
                  <td>{String(row.group)}</td>
                  <td>{String(row.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
