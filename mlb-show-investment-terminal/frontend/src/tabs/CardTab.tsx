import { useMutation } from "@tanstack/react-query";
import { ClipboardCheck, Search } from "lucide-react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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
  const decision = record.decision_action ?? record.decision?.action ?? (investable ? record.flip?.action : "WATCH");
  const profit = fmtStubs(record.flip?.profit);
  const roi = fmtPct(record.flip?.roi, 2);
  const afterTax = fmtStubs(record.flip?.after_tax_sale);
  const pCross = fmtPct(record.upgrade?.p_cross_next_threshold, 1);
  const pUp = fmtPct(record.upgrade?.p_upgrade, 1);
  const pDown = fmtPct(record.upgrade?.p_downgrade, 1);
  return (
    <Panel title="Target" kicker={<FreshnessBadge at={record.fetched_at} label="LISTING" />} className="target-panel">
      <CardIdentity record={record} />
      <VerdictBanner record={record} />
      <div className="target-signal-row">
        <div>
          <div className="stat-label">Flip signal</div>
          <SignalPill action={decision} />
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
        <Stat label="Flip ROI" value={roi} />
        <Stat label="Scenario P(Cross)" value={pCross} />
        <Stat label="Scenario P(Up)" value={pUp} />
        <Stat label="Scenario P(Down)" value={pDown} />
      </div>
      <div className="reason-block single">
        <div>
          <div className="stat-label">Decision explanation</div>
          <p className="muted">{record.decision?.explanation ?? "-"}</p>
          <ReasonCodes codes={record.decision?.reason_codes ?? record.decision_reason_codes} />
        </div>
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
  const cone = record.forecast?.cone ?? [];
  const hasCone = cone.length > 0;
  // Bank-of-England-style fan chart: shaded band between p5 and p95 with the
  // p50 median line on top. Recharts AreaChart shades from baseline 0, so we
  // synthesize a "band" series = (p95 - p5) stacked on a base series = p5.
  const fanData = cone.map((p) => {
    const p5 = typeof p.p5 === "number" ? p.p5 : null;
    const p95 = typeof p.p95 === "number" ? p.p95 : null;
    return {
      step: p.step,
      p5,
      p50: p.p50 ?? null,
      p95,
      base: p5,
      band: p5 != null && p95 != null ? p95 - p5 : null,
    };
  });
  const askPrice = Number(record.flip?.sell_price ?? record.card?.raw_ask) || null;
  // Multi-horizon EV bars: read horizons[] from the diagnostic payload and
  // colour-code positive vs negative expected return so the user gets the
  // signal at a glance instead of reading a numeric table.
  const horizons = (record.forecast?.horizons ?? []) as Array<Record<string, unknown>>;
  const horizonData = horizons.map((h) => ({
    horizon: `${h.horizon ?? "-"}d`,
    expected_ret: typeof h.expected_ret === "number" ? h.expected_ret : 0,
    p_profit: typeof h.p_profit === "number" ? h.p_profit : null,
    half_kelly: typeof h.half_kelly === "number" ? h.half_kelly : null,
    p5_ret: typeof h.p5_ret === "number" ? h.p5_ret : null,
    p95_ret: typeof h.p95_ret === "number" ? h.p95_ret : null,
  }));
  const gates = record.forecast?.gates ?? {};
  const failedGates = Object.entries(gates)
    .filter(([, g]) => g && !g.passed)
    .map(([k]) => k);
  const status = verdictOf(record);
  return (
    <Panel title="Forecast Diagnostics" kicker={`verdict: ${status}`}>
      <div className="stat-grid">
        <Stat label="Direction" value={record.forecast?.direction ?? record.forecast?.status ?? "-"} />
        <Stat label="Forecast EV" value={fmtPct(record.forecast?.expected_ret, 2)} />
        <Stat label="Forecast P(profit)" value={fmtPct(record.forecast?.p_profit, 1)} />
        <Stat label="N prices" value={fmtNum(record.forecast?.n_prices, 0)} />
        <Stat label="Validation Tier" value={record.validation_tier ?? record.decision_tier ?? record.forecast?.tier ?? record.tier ?? "-"} />
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
        {hasCone ? (
          <>
            <div className="stat-label">Forecast cone · 90% band + median (after-tax stubs)</div>
            <div className="chart tall">
              <ResponsiveContainer width="100%" height={220}>
                <ComposedChart data={fanData} margin={{ top: 12, right: 18, left: 6, bottom: 4 }}>
                  <defs>
                    <linearGradient id="fanBand" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0.08} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(63,63,70,0.28)" vertical={false} />
                  <XAxis dataKey="step" tick={{ fill: "#9ca3af", fontSize: 11 }} label={{ value: "horizon step", position: "insideBottom", offset: -2, fill: "#9ca3af", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} tickFormatter={(v) => fmtStubs(v)} domain={["auto", "auto"]} />
                  <Tooltip
                    contentStyle={{ background: "#0a0e10", border: "1px solid rgba(63,63,70,0.6)" }}
                    formatter={(v: unknown, name) => {
                      const key = String(name ?? "");
                      if (key === "base" || key === "band") return ["", ""];
                      return [fmtStubs(v), key];
                    }}
                    labelFormatter={(label) => `step ${label}`}
                  />
                  {askPrice ? <ReferenceLine y={askPrice} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: "ask", position: "right", fill: "#94a3b8", fontSize: 10 }} /> : null}
                  <Area type="monotone" dataKey="base" stackId="fan" stroke="transparent" fill="transparent" isAnimationActive={false} />
                  <Area type="monotone" dataKey="band" stackId="fan" stroke="transparent" fill="url(#fanBand)" isAnimationActive={false} />
                  <Line type="monotone" dataKey="p50" stroke="#34d399" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="p95" stroke="#38bdf8" strokeWidth={1} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="p5" stroke="#fbbf24" strokeWidth={1} strokeDasharray="2 4" dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </>
        ) : null}
        {horizonData.length ? (
          <>
            <div className="stat-label">Multi-horizon expected return</div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={170}>
                <BarChart data={horizonData} margin={{ top: 8, right: 18, left: 6, bottom: 4 }}>
                  <CartesianGrid stroke="rgba(63,63,70,0.28)" vertical={false} />
                  <XAxis dataKey="horizon" tick={{ fill: "#9ca3af", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} tickFormatter={(v) => `${(Number(v) * 100).toFixed(0)}%`} />
                  <Tooltip
                    contentStyle={{ background: "#0a0e10", border: "1px solid rgba(63,63,70,0.6)" }}
                    formatter={(v: unknown, name) => {
                      const key = String(name ?? "");
                      return [key === "expected_ret" ? fmtPct(v, 2) : String(v), key.replaceAll("_", " ")];
                    }}
                  />
                  <ReferenceLine y={0} stroke="#475569" />
                  <Bar dataKey="expected_ret" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                    {horizonData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.expected_ret >= 0 ? "#10b981" : "#f43f5e"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        ) : null}
        <div className="split">
          <div>
            <div className="stat-label">Multi-horizon EV detail</div>
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
          <div className="stat-label">Forecast formula</div>
          <MiniTable rows={[record.forecast?.formula ?? {}]} columns={["price_basis", "current_price", "ask", "bid", "spread_ratio", "tax_rate", "return_formula"]} percentCols={["spread_ratio", "tax_rate"]} />
        </div>
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
