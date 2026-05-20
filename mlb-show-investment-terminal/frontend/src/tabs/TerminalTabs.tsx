import { useMutation, useQuery } from "@tanstack/react-query";
import { Save, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "../api";
import type { TerminalContext } from "../appState";
import {
  CardIdentity,
  fmtNum,
  fmtPct,
  fmtStubs,
  formatDateTime,
  Panel,
  Pill,
  ReasonCodes,
  RecordsTable,
  SignalPill,
  Stat,
} from "../components";
import { finalAction, InventoryRiskPanel, ProvenancePanel, StrategyMatrixView, StrategySummary } from "../strategyComponents";
import type { ScoreRecord } from "../types";

export function StrategyMatrixTab({ ctx }: { ctx: TerminalContext }) {
  const record = ctx.currentRecord;
  return (
    <div className="grid">
      <Panel title="Strategy Matrix" kicker="deterministic final-action table">
        <p className="muted">
          Final action is assigned from flip edge, directional forecast, and inventory quality. Directional INVESTABLE is not a final action.
        </p>
        <StrategyMatrixView record={record} />
      </Panel>
      {record ? (
        <Panel title="Selected Card Placement" kicker={finalAction(record)}>
          <CardIdentity record={record} />
          <StrategySummary record={record} />
        </Panel>
      ) : (
        <Panel title="Selected Card Placement" kicker="none">
          <p className="muted">Load a card or click a scanner row to plot it in the matrix.</p>
        </Panel>
      )}
    </div>
  );
}

export function ForecastLabTab({ ctx }: { ctx: TerminalContext }) {
  const record = ctx.currentRecord;
  const horizons = record?.strategy?.directional?.expected_return_by_horizon ?? {};
  const quantiles = record?.strategy?.directional?.quantile_forecasts ?? {};
  return (
    <div className="grid">
      <Panel title="Forecast Lab" kicker={record?.strategy?.directional?.verdict ?? "not loaded"}>
        {record ? (
          <>
            <CardIdentity record={record} />
            <StrategySummary record={record} />
            <div className="stat-grid">
              <Stat label="1d EV" value={fmtPct(horizons["1d"], 2)} />
              <Stat label="3d EV" value={fmtPct(horizons["3d"], 2)} />
              <Stat label="7d EV" value={fmtPct(horizons["7d"] ?? record.forecast?.expected_ret, 2)} />
              <Stat label="P(profit)" value={fmtPct(record.strategy?.directional?.p_profit ?? record.forecast?.p_profit, 1)} />
              <Stat label="P5" value={fmtPct(quantiles.p5 ?? record.forecast?.p5_ret, 2)} />
              <Stat label="Median" value={fmtPct(quantiles.median ?? record.forecast?.p50_ret, 2)} />
              <Stat label="P95" value={fmtPct(quantiles.p95 ?? record.forecast?.p95_ret, 2)} />
              <Stat label="Hold duration" value={record.strategy?.composite?.hold_duration ?? "manual review"} />
            </div>
            <MiniTable
              rows={record.forecast?.horizons ?? []}
              columns={["horizon", "expected_ret", "p_profit", "p5_ret", "p50_ret", "p95_ret", "half_kelly"]}
              percentCols={["expected_ret", "p_profit", "p5_ret", "p50_ret", "p95_ret", "half_kelly"]}
            />
          </>
        ) : <p className="muted">No current card. Load a target first.</p>}
      </Panel>
      {record ? (
        <Panel title="Model Inputs And Diagnostics" kicker={record.forecast?.tier ?? "UNVALIDATED"}>
          <MiniTable
            rows={[record.forecast?.diagnostics ?? {}]}
            columns={["z30", "drift_per_day", "drift_p_value", "hurst", "annualized_vol", "spread_pct"]}
            percentCols={["drift_per_day", "annualized_vol", "spread_pct"]}
          />
          <div className="reason-block">
            <div>
              <div className="stat-label">Directional reasons</div>
              <ReasonCodes codes={record.strategy?.directional?.reason_codes} />
            </div>
            <div>
              <div className="stat-label">Failed forecast gates</div>
              <ReasonCodes codes={record.strategy?.directional?.gates_failed} emptyLabel="No failed gates reported" />
            </div>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}

export function ExecutionLedgerTab({ ctx }: { ctx: TerminalContext }) {
  const record = ctx.currentRecord;
  const [buyPrice, setBuyPrice] = useState(String(record?.raw_bid ?? record?.flip?.buy_price ?? ""));
  const [sellPrice, setSellPrice] = useState("");
  const [status, setStatus] = useState("open");
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const persistence = useQuery({ queryKey: ["persistence"], queryFn: api.persistence, refetchInterval: 60_000 });

  const summary = useMutation({
    mutationFn: (ledgerRows: Array<Record<string, unknown>>) => api.ledgerSummary({ rows: ledgerRows }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr,
  });
  const persist = useMutation({
    mutationFn: (row: Record<string, unknown>) => api.ledgerLog({ row }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr,
  });

  function addRow() {
    const row = {
      card_uuid: record?.uuid ?? record?.card?.uuid ?? "manual",
      card_name: record?.name ?? record?.card?.name ?? "manual",
      strategy_type: record?.strategy?.composite?.strategy_type ?? "manual",
      buy_price: Number(buyPrice),
      sell_price: sellPrice ? Number(sellPrice) : undefined,
      fill_status: status,
      expected_net_stubs: record?.strategy?.flip?.expected_net_stubs ?? record?.flip?.profit,
      timestamp: new Date().toISOString(),
      model_prediction: record?.strategy ?? {},
    };
    const next = [...rows, row];
    setRows(next);
    summary.mutate(next);
  }

  return (
    <div className="grid">
      <Panel title="Manual Trade Logging" kicker="server-side writes only">
        <div className="warning-callout">
          Browser clients never receive Supabase service credentials. Durable writes require server-side persistence plus a trusted write-token flow; otherwise rows remain local for export/import.
        </div>
        <div className="status-line">
          <Pill tone={persistence.data?.status === "configured" ? "good" : "warn"}>persistence {String(persistence.data?.status ?? "checking")}</Pill>
          <Pill tone={persistence.data?.write_auth_configured ? "good" : "warn"}>write auth {String(persistence.data?.write_auth_configured ?? false)}</Pill>
        </div>
        <div className="form-row three">
          <input value={buyPrice} onChange={(e) => setBuyPrice(e.target.value)} placeholder="buy price" aria-label="buy price" />
          <input value={sellPrice} onChange={(e) => setSellPrice(e.target.value)} placeholder="sell price / blank if open" aria-label="sell price" />
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="fill status">
            <option>open</option>
            <option>filled</option>
            <option>failed</option>
            <option>expired</option>
          </select>
        </div>
        <div className="run-row">
          <button onClick={addRow}><Save size={15} /> Add local row</button>
          <button onClick={() => rows.at(-1) && persist.mutate(rows.at(-1) as Record<string, unknown>)} disabled={!rows.length || persist.isPending}>
            <Upload size={15} /> Write to Supabase
          </button>
        </div>
        {persist.data ? <pre>{JSON.stringify(persist.data, null, 2)}</pre> : null}
        {persist.error ? <div className="error" role="alert">{persist.error.message}</div> : null}
      </Panel>
      <Panel title="Realized Edge" kicker="expected vs realized">
        <div className="stat-grid">
          <Stat label="Closed trades" value={fmtNum(summary.data?.closed_trades, 0)} />
          <Stat label="Realized profit" value={fmtStubs(summary.data?.realized_profit)} />
          <Stat label="Realized ROI" value={fmtPct(summary.data?.realized_roi, 2)} />
          <Stat label="Edge decay" value={fmtPct(summary.data?.average_edge_decay, 1)} />
          <Stat label="Expected minus realized" value={fmtStubs(summary.data?.expected_vs_realized_stubs)} />
          <Stat label="Failed exit rate" value={fmtPct(summary.data?.failed_exit_rate, 1)} />
        </div>
        <MiniTable rows={rows} columns={["card_name", "strategy_type", "buy_price", "sell_price", "fill_status", "expected_net_stubs", "timestamp"]} />
      </Panel>
    </div>
  );
}

export function RiskInventoryTab({ ctx }: { ctx: TerminalContext }) {
  const riskyRows = useMemo(() => (ctx.lastScan?.records ?? []).filter((r) => {
    const action = finalAction(r);
    return action.includes("AVOID") || action.includes("MANUAL") || r.strategy?.inventory?.verdict === "THIN" || r.strategy?.inventory?.verdict === "DEAD INVENTORY";
  }), [ctx.lastScan]);
  return (
    <div className="grid">
      <InventoryRiskPanel record={ctx.currentRecord} />
      <Panel title="Risk Controls" kicker="hard caps">
        <div className="stat-grid">
          <Stat label="Max thin-card position" value="2,500s" />
          <Stat label="Dead inventory cap" value="0s" tone="bad" />
          <Stat label="Max holding time" value={ctx.currentRecord?.strategy?.composite?.hold_duration ?? "manual review"} />
          <Stat label="Auto downgrade" value="thin/stale -> watchlist" />
        </div>
      </Panel>
      <Panel title="Suggested Review Queue" kicker={`${riskyRows.length} rows`}>
        <RecordsTable rows={riskyRows} kind="no_trade" onRowClick={(row) => { ctx.setCurrentRecord(row); ctx.openTab("target"); }} />
      </Panel>
    </div>
  );
}

export function DataAuditTab({ ctx }: { ctx: TerminalContext }) {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 60_000 });
  const persistence = useQuery({ queryKey: ["persistence"], queryFn: api.persistence, refetchInterval: 60_000 });
  const record = ctx.currentRecord;
  return (
    <div className="grid">
      <ProvenancePanel record={record} />
      <Panel title="API And Persistence" kicker={String(health.data?.status ?? "checking")}>
        <div className="stat-grid">
          <Stat label="Health" value={String(health.data?.status ?? "-")} />
          <Stat label="Version" value={String(health.data?.version ?? "-")} />
          <Stat label="Persistence" value={String(persistence.data?.status ?? "-")} tone={persistence.data?.status === "configured" ? "good" : "warn"} />
          <Stat label="Mode" value={String(persistence.data?.mode ?? "-")} />
          <Stat label="Server writes" value={String(persistence.data?.server_side_writes ?? false)} />
          <Stat label="Write auth" value={String(persistence.data?.write_auth_configured ?? false)} tone={persistence.data?.write_auth_configured ? "good" : "warn"} />
          <Stat label="Credential exposure" value={String(persistence.data?.credential_exposure ?? "none")} />
          <Stat label="Server time" value={formatDateTime(String(health.data?.server_time ?? ""))} />
          <Stat label="Last scan" value={formatDateTime(ctx.lastScanAt)} />
        </div>
      </Panel>
      <Panel title="Audit Cards" kicker="current deployment evidence">
        <div className="audit-pill-row">
          <Pill tone="good">OK schema</Pill>
          <Pill tone={record?.fetched_at ? "good" : "warn"}>OK freshness</Pill>
          <Pill tone={record?.strategy?.directional?.data_coverage_tier === "UNVALIDATED" ? "warn" : "info"}>coverage {record?.strategy?.directional?.data_coverage_tier ?? "UNVALIDATED"}</Pill>
          <Pill tone={record?.strategy?.directional?.performance_validation_tier === "UNVALIDATED" ? "warn" : "info"}>performance {record?.strategy?.directional?.performance_validation_tier ?? "UNVALIDATED"}</Pill>
          <Pill tone="warn">calibration limited</Pill>
          <Pill tone="warn">backtest limited</Pill>
          <Pill tone="info">mobile checked by smoke</Pill>
          <Pill tone="info">accessibility smoke</Pill>
        </div>
      </Panel>
    </div>
  );
}

function MiniTable({
  rows,
  columns,
  percentCols = [],
}: {
  rows: Array<Record<string, unknown>>;
  columns: string[];
  percentCols?: string[];
}) {
  const safeRows = rows.length ? rows : [{}];
  return (
    <div className="table-wrap mini-table">
      <table aria-label="diagnostic table">
        <caption className="sr-only">diagnostic table</caption>
        <thead><tr>{columns.map((col) => <th key={col} scope="col">{col.replaceAll("_", " ")}</th>)}</tr></thead>
        <tbody>
          {safeRows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => {
                const value = row?.[col];
                const text = percentCols.includes(col) && typeof value === "number"
                  ? fmtPct(value, 2)
                  : typeof value === "number"
                    ? fmtNum(value, 3)
                    : String(value ?? "-");
                return <td key={col}>{text}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
