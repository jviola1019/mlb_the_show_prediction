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
  return (
    <Panel title="Target" kicker={<FreshnessBadge at={record.fetched_at} label="LISTING" />} className="target-panel">
      <CardIdentity record={record} />
      <div className="target-signal-row">
        <div>
          <div className="stat-label">Flip signal</div>
          <SignalPill action={record.flip?.action} />
        </div>
        <div>
          <div className="stat-label">Upgrade signal</div>
          <SignalPill action={record.upgrade?.action} />
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
        <Stat label="After tax" value={fmtStubs(record.flip?.after_tax_sale)} />
        <Stat label="Profit" value={fmtStubs(record.flip?.profit)} tone={(record.flip?.profit ?? 0) > 0 ? "good" : "bad"} />
        <Stat label="ROI" value={fmtPct(record.flip?.roi, 2)} />
        <Stat label="P(Cross)" value={fmtPct(record.upgrade?.p_cross_next_threshold, 1)} />
        <Stat label="P(Up)" value={fmtPct(record.upgrade?.p_upgrade, 1)} />
        <Stat label="P(Down)" value={fmtPct(record.upgrade?.p_downgrade, 1)} />
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
  return (
    <Panel title="Forecast Diagnostics" kicker="not executable">
      <div className="stat-grid">
        <Stat label="Direction" value={record.forecast?.direction ?? record.forecast?.status ?? "-"} />
        <Stat label="E[ret]" value={fmtPct(record.forecast?.expected_ret, 2)} />
        <Stat label="P(profit)" value={fmtPct(record.forecast?.p_profit, 1)} />
        <Stat label="N prices" value={fmtNum(record.forecast?.n_prices, 0)} />
        <Stat label="Tier" value={record.forecast?.tier ?? record.tier ?? "-"} />
        <Stat label="Verdict" value={record.forecast?.verdict?.status ?? record.verdict_status ?? "-"} />
        <Stat label="Gates" value={(record.forecast?.gates?.failed ?? []).length ? "warning" : "pass"} tone={(record.forecast?.gates?.failed ?? []).length ? "warn" : "good"} />
        <Stat label="Diagnostic" value={record.forecast?.diagnostic_only ? "yes" : "no"} />
      </div>
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
      <div className="split">
        <div>
          <div className="stat-label">Quant diagnostics</div>
          <MiniTable rows={[record.forecast?.diagnostics ?? {}]} columns={["z30", "drift_per_day", "drift_p_value", "hurst", "annualized_vol", "spread_pct"]} percentCols={["drift_per_day", "annualized_vol", "spread_pct"]} />
        </div>
        <div>
          <div className="stat-label">Forecast gates</div>
          <ReasonCodes codes={record.forecast?.gates?.failed ?? record.gates_failed_csv} />
          <p className="muted">{record.forecast?.gates?.note ?? "Forecast gates do not block executable flip or upgrade signals."}</p>
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
