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
        <pre>{`flip.after_tax_sale = sell_price * (1 - tax_rate)
flip.profit = after_tax_sale - buy_price
flip.roi = profit / buy_price
flip.spread_pct = (sell_price - buy_price) / sell_price
tax_rate defaults to 0.10

upgrade = scenario threshold model until real historical backtests calibrate it
forecast = diagnostic-only price-history bootstrap
forecast_ev = ((terminal_price * spread_ratio * (1 - tax_rate)) - current_price) / current_price

strategy.flip = executable spread capture
strategy.directional = holding EV and recommended hold duration
strategy.inventory = exit risk and position cap
strategy.composite = deterministic final action from the matrix`}</pre>
      </Panel>
      <Panel title="Decision Policy">
        <ul className="rule-list">
          <li>INSTANT FLIP ONLY means spread capture is positive, but the directional model says not to hold.</li>
          <li>SPREAD CAPTURE ONLY means a flip edge exists while the directional forecast is neutral.</li>
          <li>SPECULATIVE HOLD is allowed only when directional EV is positive and inventory quality is acceptable.</li>
          <li>WATCHLIST / NO MODEL TRADE means real history, freshness, or validation is insufficient.</li>
          <li>INVESTABLE is directional-only and must include a hold duration.</li>
        </ul>
      </Panel>
      <Panel title="Execution Timing">
        <div className="table-wrap mini-table">
          <table>
            <thead><tr><th>Action</th><th>Entry</th><th>Exit clock</th></tr></thead>
            <tbody>
              <tr><td><code>INSTANT FLIP ONLY</code></td><td>limit bid only</td><td>relist immediately; default cap about 2h</td></tr>
              <tr><td><code>SPREAD CAPTURE ONLY</code></td><td>only while after-tax spread survives friction</td><td>relist immediately; cancel/reassess if queue misses expected exit window</td></tr>
              <tr><td><code>FLIP OR SHORT HOLD</code></td><td>limit bid only</td><td>take early spread exit or hold only to the selected 1d/3d/7d horizon</td></tr>
              <tr><td><code>SPECULATIVE HOLD</code></td><td>freshness, liquidity, and size gates must pass</td><td>hold up to stated horizon unless risk gate trips first</td></tr>
              <tr><td><code>WATCHLIST / AVOID</code></td><td>no model entry</td><td>manual liquidation only for existing inventory</td></tr>
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Analytics Design">
        <p>WebGL/3D charts were removed. The terminal now uses 2D EV bars, forecast fans, spread/liquidity scatter, calibration reliability, and equity/drawdown views because those directly support trading decisions on desktop and mobile.</p>
      </Panel>
      <Panel title="Deployment">
        <p>Hugging Face serves FastAPI and the React build from one process. Supabase writes are server-side only and the app degrades to read-only mode when credentials are absent.</p>
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
