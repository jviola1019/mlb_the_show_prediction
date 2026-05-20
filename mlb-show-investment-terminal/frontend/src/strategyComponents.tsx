import { AlertTriangle, CheckCircle2, Clock3, ExternalLink, ShieldAlert } from "lucide-react";
import type { ScoreRecord, Tone } from "./types";
import { fmtNum, fmtPct, fmtStubs, formatDateTime, Panel, Pill, ReasonCodes, SignalPill, Stat } from "./components";

export function finalAction(record?: ScoreRecord | null): string {
  return String(record?.strategy?.composite?.final_action ?? record?.final_action ?? record?.decision?.action ?? record?.decision_action ?? "-");
}

export function actionTone(action?: string | null): Tone {
  const value = String(action ?? "").toUpperCase();
  if (value.includes("AVOID")) return "bad";
  if (value.includes("MANUAL")) return "warn";
  if (value.includes("WATCHLIST")) return "info";
  if (value.includes("SPECULATIVE")) return "info";
  if (value.includes("FLIP") || value.includes("SPREAD")) return "good";
  return "neutral";
}

export function StrategySummary({ record }: { record: ScoreRecord }) {
  const strategy = record.strategy ?? {};
  const composite = strategy.composite ?? {};
  const flip = strategy.flip ?? {};
  const directional = strategy.directional ?? {};
  const inventory = strategy.inventory ?? {};
  const action = finalAction(record);
  return (
    <div className="strategy-summary" role="region" aria-label="Strategy verdict summary">
      <div className="strategy-primary">
        <div className="stat-label">Final Action</div>
        <SignalPill action={action} />
        <p className="muted">{composite.explanation ?? record.decision?.explanation ?? "-"}</p>
      </div>
      <div className="strategy-pill-row">
        <Pill tone={flip.verdict === "FLIP PASS" ? "good" : flip.verdict === "FLIP MARGINAL" ? "warn" : "neutral"}>Flip: {flip.verdict ?? "-"}</Pill>
        <Pill tone={directional.verdict === "BULLISH" ? "good" : directional.verdict === "BEARISH" ? "bad" : directional.verdict === "INSUFFICIENT DATA" ? "warn" : "info"}>
          Direction: {directional.verdict ?? "-"}
        </Pill>
        <Pill tone={inventory.verdict === "DEAD INVENTORY" ? "bad" : inventory.verdict === "THIN" ? "warn" : "good"}>
          Inventory: {inventory.verdict ?? "-"}
        </Pill>
        <Pill tone="neutral">Strategy: {composite.strategy_type ?? "unclassified"}</Pill>
        <Pill tone={composite.investable_label === "INVESTABLE" ? "good" : "neutral"}>
          Directional label: {composite.investable_label ?? "not investable"}
        </Pill>
      </div>
      <div className="stat-grid strategy-stats">
        <Stat label="Net flip stubs" value={fmtStubs(flip.expected_net_stubs ?? record.flip_profit ?? record.flip?.profit)} tone={(flip.expected_net_stubs ?? 0) > 0 ? "good" : "neutral"} />
        <Stat label="Friction ROI" value={fmtPct(flip.expected_roi_after_tax_and_friction ?? record.flip_roi ?? record.flip?.roi, 2)} />
        <Stat label="P(exit)" value={fmtPct(flip.p_successful_exit, 1)} />
        <Stat label="Exit time" value={flip.expected_holding_time_hours != null ? `${fmtNum(flip.expected_holding_time_hours, 1)}h` : "-"} />
        <Stat label="Forecast EV 7d" value={fmtPct(directional.expected_return_by_horizon?.["7d"] ?? record.forecast?.expected_ret, 2)} tone={(directional.expected_return_by_horizon?.["7d"] ?? 0) < 0 ? "bad" : "neutral"} />
        <Stat label="P(profit)" value={fmtPct(directional.p_profit ?? record.forecast?.p_profit, 1)} />
        <Stat label="Coverage tier" value={String(directional.data_coverage_tier ?? record.data_coverage_tier ?? record.provenance?.data_coverage_tier ?? "-")} />
        <Stat label="Performance tier" value={String(directional.performance_validation_tier ?? record.performance_validation_tier ?? directional.validation_tier ?? record.validation_tier ?? "-")} />
        <Stat label="Inventory risk" value={fmtPct(inventory.inventory_risk_score, 0)} tone={(inventory.inventory_risk_score ?? 0) > 0.7 ? "bad" : (inventory.inventory_risk_score ?? 0) > 0.4 ? "warn" : "good"} />
      </div>
      {composite.holding_instruction ? <p className="muted hold-note"><Clock3 size={13} /> {composite.holding_instruction}</p> : null}
    </div>
  );
}

export function StrategyMatrixView({ record }: { record?: ScoreRecord | null }) {
  const current = finalAction(record);
  const rows = [
    ["FLIP PASS", "BEARISH", "HIGH/MEDIUM", "INSTANT FLIP ONLY"],
    ["FLIP PASS", "BULLISH", "HIGH/MEDIUM", "FLIP OR SHORT HOLD"],
    ["FLIP PASS", "NEUTRAL", "HIGH/MEDIUM", "SPREAD CAPTURE ONLY"],
    ["NO FLIP EDGE", "BULLISH", "HIGH/MEDIUM", "SPECULATIVE HOLD"],
    ["NO FLIP EDGE", "BEARISH", "ANY", "AVOID"],
    ["FLIP MARGINAL", "BEARISH", "THIN/DEAD", "AVOID"],
    ["FLIP PASS", "ANY", "DEAD", "AVOID / MANUAL REVIEW"],
    ["ANY", "INSUFFICIENT DATA", "ANY", "WATCHLIST / NO MODEL TRADE"],
  ];
  return (
    <div className="table-wrap strategy-matrix-table">
      <table>
        <thead><tr><th>Flip</th><th>Directional</th><th>Inventory</th><th>Final Action</th></tr></thead>
        <tbody>
          {rows.map(([flip, dir, inv, action]) => (
            <tr key={`${flip}-${dir}-${inv}`} className={action === current ? "selected-row" : ""}>
              <td>{flip}</td>
              <td>{dir}</td>
              <td>{inv}</td>
              <td><SignalPill action={action} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function InventoryRiskPanel({ record }: { record?: ScoreRecord | null }) {
  const inv = record?.strategy?.inventory;
  return (
    <Panel title="Inventory Quality" kicker={inv?.verdict ?? "not loaded"}>
      <div className="stat-grid">
        <Stat label="Verdict" value={inv?.verdict ?? "-"} tone={inv?.verdict === "DEAD INVENTORY" ? "bad" : inv?.verdict === "THIN" ? "warn" : "good"} />
        <Stat label="Risk score" value={fmtPct(inv?.inventory_risk_score, 0)} />
        <Stat label="Exit time" value={inv?.expected_exit_time_hours != null ? `${fmtNum(inv.expected_exit_time_hours, 1)}h` : "-"} />
        <Stat label="Position cap" value={fmtStubs(inv?.max_position_stubs)} />
      </div>
      {inv?.dead_inventory_warning ? (
        <div className="warning-callout"><AlertTriangle size={16} /> {inv.dead_inventory_warning}</div>
      ) : null}
      <div className="reason-block">
        <div>
          <div className="stat-label">Passed</div>
          <ReasonCodes codes={inv?.gates_passed} emptyLabel="No passed gates reported" />
        </div>
        <div>
          <div className="stat-label">Failed</div>
          <ReasonCodes codes={inv?.gates_failed} emptyLabel="No failed gates reported" />
        </div>
      </div>
    </Panel>
  );
}

export function ProvenancePanel({ record }: { record?: ScoreRecord | null }) {
  const p = record?.provenance;
  return (
    <Panel title="Data Provenance" kicker={p?.performance_validation_tier ?? p?.validation_tier ?? record?.performance_validation_tier ?? "UNVALIDATED"}>
      <div className="stat-grid">
        <Stat label="Source" value={p?.source ?? "mlb-the-show-community-market"} />
        <Stat label="Pulled" value={formatDateTime(p?.pull_timestamp ?? record?.fetched_at)} />
        <Stat label="Freshness" value={p?.data_freshness ?? "-"} />
        <Stat label="Sample size" value={fmtNum(p?.sample_size ?? record?.forecast?.n_prices, 0)} />
        <Stat label="Model" value={p?.model_version ?? "-"} />
        <Stat label="Rules" value={p?.rule_version ?? record?.strategy?.rule_version ?? "-"} />
        <Stat label="Coverage tier" value={p?.data_coverage_tier ?? record?.data_coverage_tier ?? "-"} />
        <Stat label="Performance tier" value={p?.performance_validation_tier ?? record?.performance_validation_tier ?? p?.validation_tier ?? "-"} />
        <Stat label="Hash" value={p?.raw_data_hash ? `${p.raw_data_hash.slice(0, 12)}...` : "-"} />
        <Stat label="Source link" value={p?.source_url || record?.source_url ? <a className="source-link" href={String(p?.source_url ?? record?.source_url)} target="_blank" rel="noreferrer">open <ExternalLink size={12} /></a> : "-"} />
      </div>
      <div className="audit-pill-row">
        <Pill tone="good"><CheckCircle2 size={12} /> OK schema</Pill>
        <Pill tone={record?.fetched_at || p?.pull_timestamp ? "good" : "warn"}>freshness visible</Pill>
        <Pill tone={record?.strategy?.directional?.performance_validation_tier === "UNVALIDATED" ? "warn" : "info"}>performance {record?.strategy?.directional?.performance_validation_tier ?? "UNVALIDATED"}</Pill>
        <Pill tone="warn"><ShieldAlert size={12} /> calibration limited</Pill>
      </div>
    </Panel>
  );
}
