import { useMutation } from "@tanstack/react-query";
import { ClipboardCheck, Search } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import type { TerminalContext } from "../appState";
import {
  CardIdentity,
  DensityDots,
  FreshnessBadge,
  fmtNum,
  fmtPct,
  fmtStubs,
  Panel,
  ReasonCodes,
  SearchResultRow,
  SignalPill,
  SourceLink,
  Stat
} from "../components";
import type { ScoreRecord, SearchResponse } from "../types";
import { useState } from "react";
import {
  GuardedVisual,
  VerdictBanner,
  blankIf,
  isInvestable,
  verdictOf,
} from "../verdictGuard";
import { Suspense, lazy } from "react";

const ForecastSurface3D = lazy(() => import("../viz/ForecastSurface3D"));

export function CardTab({ ctx }: { ctx: TerminalContext }) {
  const [name, setName] = useState("Mike Trout");
  const [uuid, setUuid] = useState("");
  const [rawJson, setRawJson] = useState("");

  const search = useMutation({
    mutationFn: () => api.search(name),
    onSuccess: (payload) => {
      ctx.setLastSearch(payload);
      ctx.markApiOk();
    },
    onError: ctx.markApiErr
  });

  const load = useMutation({
    mutationFn: async (targetUuid: string) => {
      const clean = targetUuid.trim().toLowerCase();
      const listing = await api.listing(clean);
      setRawJson(JSON.stringify(listing, null, 2));
      const scored = await api.analyze({ listing }) as ScoreRecord;
      return { scored, listing };
    },
    onSuccess: ({ scored }, targetUuid) => {
      setUuid(targetUuid.trim().toLowerCase());
      ctx.addLoadedUuid(targetUuid.trim().toLowerCase());
      ctx.setCurrentRecord(scored);
      ctx.markApiOk();
    },
    onError: ctx.markApiErr
  });

  const analyze = useMutation({
    mutationFn: () => api.analyze({ listing: JSON.parse(rawJson) }) as Promise<ScoreRecord>,
    onSuccess: (scored) => {
      ctx.setCurrentRecord(scored);
      if (scored.uuid) ctx.addLoadedUuid(scored.uuid);
      ctx.markApiOk();
    },
    onError: ctx.markApiErr
  });

  const data = (search.data ?? ctx.lastSearch) as SearchResponse | undefined;
  const result = ctx.currentRecord;

  return (
    <div className="grid">
      <Panel title="Find Card" kicker={<span>The Show API proxy</span>}>
        <div className="form-row">
          <input value={name} onChange={(e) => setName(e.target.value)} aria-label="Player name" />
          <button onClick={() => search.mutate()} disabled={search.isPending}><Search size={15} /> Search</button>
        </div>
        <div className="status-line">
          {data?.normalized_query ? <span className="muted">normalized: <code>{data.normalized_query}</code></span> : null}
          {data?.year ? <span className="muted">year={data.year}</span> : null}
          <SourceLink url={data?.source_url} />
          {data?.fetched_at ? <FreshnessBadge at={data.fetched_at} label="SEARCH" /> : null}
        </div>
        {search.error ? <div className="error">{search.error.message}</div> : null}
        {data?.listings?.length ? (
          <div className="result-list">
            {data.listings.slice(0, 10).map((row, idx) => (
              <SearchResultRow key={row.item?.uuid || idx} listing={row} query={data.normalized_query || name} onLoad={(id) => load.mutate(id)} />
            ))}
          </div>
        ) : <div className="empty">No search results loaded.</div>}
      </Panel>

      <Panel title="Analyze Listing" kicker="same-origin /api/card/analyze">
        <div className="form-row">
          <input value={uuid} onChange={(e) => setUuid(e.target.value)} placeholder="32-hex UUID" />
          <button onClick={() => load.mutate(uuid)} disabled={!uuid || load.isPending}>Load UUID</button>
        </div>
        <textarea value={rawJson} onChange={(e) => setRawJson(e.target.value)} placeholder="Paste listing.json here" rows={7} />
        <button onClick={() => analyze.mutate()} disabled={!rawJson || analyze.isPending}><ClipboardCheck size={15} /> Analyze pasted JSON</button>
      </Panel>

      {result ? <TargetPanel record={result} /> : null}
      {result ? <DiagnosticsPanel record={result} /> : null}
    </div>
  );
}

function TargetPanel({ record }: { record: ScoreRecord }) {
  const card = record.card ?? {};
  const investable = isInvestable(record);
  // Under non-INVESTABLE verdicts, blank executable/Kelly-shaped fields so the
  // UI never implies a tradeable signal under failed governance. The raw
  // bid/ask/spread stay visible (they're factual, not predictive).
  const profit = blankIf(record, fmtStubs(record.flip?.profit));
  const roi = blankIf(record, fmtPct(record.flip?.roi, 2));
  const afterTax = blankIf(record, fmtStubs(record.flip?.after_tax_sale));
  const pCross = blankIf(record, fmtPct(record.upgrade?.p_cross_next_threshold, 1));
  const pUp = blankIf(record, fmtPct(record.upgrade?.p_upgrade, 1));
  const pDown = blankIf(record, fmtPct(record.upgrade?.p_downgrade, 1));
  return (
    <Panel title="Target" kicker={<FreshnessBadge at={record.fetched_at} label="LISTING" />} className="target-panel">
      <CardIdentity record={record} />
      <VerdictBanner record={record} />
      <div className="target-signal-row">
        <div>
          <div className="stat-label">Flip signal</div>
          <SignalPill action={investable ? record.flip?.action : "OBSERVE"} />
        </div>
        <div>
          <div className="stat-label">Upgrade signal</div>
          <SignalPill action={investable ? record.upgrade?.action : "OBSERVE"} />
        </div>
        <div className="score-density">
          <div className="stat-label">Liquidity</div>
          <DensityDots score={record.flip?.liquidity_score ?? card.liquidity_score} />
        </div>
        <SourceLink url={record.source_url} />
      </div>
      <div className="stat-grid">
        <Stat label="Raw ask" value={fmtStubs(record.flip?.sell_price ?? card.raw_ask)} />
        <Stat label="Raw bid" value={fmtStubs(record.flip?.buy_price ?? card.raw_bid)} />
        <Stat label="After tax" value={afterTax} />
        <Stat label="Profit" value={profit} tone={investable && (record.flip?.profit ?? 0) > 0 ? "good" : investable ? "bad" : "neutral"} />
        <Stat label="ROI" value={roi} />
        <Stat label="P(Cross)" value={pCross} />
        <Stat label="P(Up)" value={pUp} />
        <Stat label="P(Down)" value={pDown} />
      </div>
      <div className="reason-block">
        <div>
          <div className="stat-label">Flip reasons</div>
          <ReasonCodes codes={record.flip?.reason_codes ?? record.flip?.reason_codes_csv} />
        </div>
        <div>
          <div className="stat-label">Upgrade reasons</div>
          <ReasonCodes codes={record.upgrade?.reason_codes} />
        </div>
      </div>
    </Panel>
  );
}

function DiagnosticsPanel({ record }: { record: ScoreRecord }) {
  const chart = [
    { metric: "P5", value: record.forecast?.p5_ret ?? null },
    { metric: "E", value: record.forecast?.expected_ret ?? null },
    { metric: "P95", value: record.forecast?.p95_ret ?? null }
  ];
  const hasCone = Boolean(record.forecast?.cone?.length);
  const chartData = hasCone ? record.forecast?.cone ?? [] : chart;
  const gates = record.forecast?.gates ?? {};
  const failedGates = Object.entries(gates)
    .filter(([, g]) => g && !g.passed)
    .map(([k]) => k);
  const status = verdictOf(record);
  return (
    <Panel title="Forecast Diagnostics" kicker={`verdict: ${status}`}>
      <div className="stat-grid">
        <Stat label="Direction" value={record.forecast?.direction ?? record.forecast?.status ?? "-"} />
        <Stat label="E[ret]" value={blankIf(record, fmtPct(record.forecast?.expected_ret, 2))} />
        <Stat label="P(profit)" value={blankIf(record, fmtPct(record.forecast?.p_profit, 1))} />
        <Stat label="N prices" value={fmtNum(record.forecast?.n_prices, 0)} />
        <Stat label="Tier" value={record.forecast?.tier ?? record.tier ?? "-"} />
        <Stat label="Verdict" value={status} tone={status === "INVESTABLE" ? "good" : status === "OBSERVATIONAL ONLY" ? "warn" : "bad"} />
        <Stat label="Gates" value={failedGates.length ? `${failedGates.length} failed` : "all pass"} tone={failedGates.length ? "warn" : "good"} />
        <Stat label="Diagnostic" value={record.forecast?.diagnostic_only ? "yes" : "no"} />
      </div>
      <GuardedVisual record={record} blockedTitle="FORECAST BLOCKED · GATE FAILURE">
        {isInvestable(record) && hasCone ? (
          <Suspense fallback={<div className="empty">loading 3D surface…</div>}>
            <ForecastSurface3D record={record} />
          </Suspense>
        ) : null}
        <div className="chart tall">
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={chartData as Array<Record<string, unknown>>}>
              <XAxis dataKey={hasCone ? "step" : "metric"} />
              <YAxis tickFormatter={(v) => hasCone ? fmtStubs(v) : `${(Number(v) * 100).toFixed(0)}%`} />
              <Tooltip formatter={(v) => hasCone ? fmtStubs(v) : fmtPct(v, 2)} />
              {hasCone ? (
                <>
                  <Line type="monotone" dataKey="p95" stroke="#38bdf8" dot={false} />
                  <Line type="monotone" dataKey="p50" stroke="#10b981" dot={false} />
                  <Line type="monotone" dataKey="p5" stroke="#fbbf24" dot={false} />
                </>
              ) : <Line type="monotone" dataKey="value" stroke="#60a5fa" dot />}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="split">
          <div>
            <div className="stat-label">Multi-horizon EV</div>
            <MiniTable rows={record.forecast?.horizons ?? []} columns={["horizon", "expected_ret", "p_profit", "p5_ret", "p95_ret", "half_kelly"]} percentCols={["expected_ret", "p_profit", "p5_ret", "p95_ret", "half_kelly"]} />
          </div>
          <div>
            <div className="stat-label">Walk-forward CV</div>
            <MiniTable rows={[record.forecast?.walk_forward ?? {}]} columns={["status", "n_trades", "brier_point", "ic_point", "hit_rate", "ci_method"]} percentCols={["brier_point", "ic_point", "hit_rate"]} />
          </div>
        </div>
      </GuardedVisual>
      <div className="split">
        <div>
          <div className="stat-label">Quant diagnostics</div>
          <MiniTable rows={[record.forecast?.diagnostics ?? {}]} columns={["z30", "drift_per_day", "drift_p_value", "hurst", "annualized_vol", "spread_pct"]} percentCols={["drift_per_day", "annualized_vol", "spread_pct"]} />
        </div>
        <div>
          <div className="stat-label">Gate status</div>
          <div className="gates-pills">
            {(record.forecast?.gate_pills ?? []).map((pill) => (
              <span key={pill.key} className={`pill pill-${pill.tone}`} title={pill.reason}>
                {pill.mark} {pill.label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function MiniTable({ rows, columns, percentCols = [] }: { rows: Array<Record<string, unknown>>; columns: string[]; percentCols?: string[] }) {
  const safeRows = rows.length ? rows : [{}];
  return (
    <div className="table-wrap mini-table">
      <table>
        <thead><tr>{columns.map((col) => <th key={col}>{col.replaceAll("_", " ")}</th>)}</tr></thead>
        <tbody>
          {safeRows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => {
                const value = row?.[col];
                const text = percentCols.includes(col) && typeof value === "number" ? fmtPct(value, 2) : typeof value === "number" ? fmtNum(value, 3) : String(value ?? "-");
                return <td key={col}>{text}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
