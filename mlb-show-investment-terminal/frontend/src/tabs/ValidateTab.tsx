import { useMutation } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";
import { api } from "../api";
import type { TerminalContext } from "../appState";
import { fmtNum, fmtPct, fmtStubs, Panel, Stat } from "../components";
import { VerdictBanner, verdictOf } from "../verdictGuard";
import { Suspense, lazy, useEffect } from "react";
import type { CalibrationBin } from "../types";

const ReliabilityRibbon3D = lazy(() => import("../viz/ReliabilityRibbon3D"));

export function ValidateTab({ ctx }: { ctx: TerminalContext }) {
  const [predictions, setPredictions] = useState("[]");
  const [labels, setLabels] = useState("[]");
  const currentAsk = ctx.currentRecord?.raw_ask ?? ctx.currentRecord?.flip?.sell_price ?? "";
  const currentBid = ctx.currentRecord?.raw_bid ?? ctx.currentRecord?.flip?.buy_price ?? "";
  const [ask, setAsk] = useState(String(currentAsk));
  const [bid, setBid] = useState(String(currentBid));
  const manual = useMutation({
    mutationFn: (prices: { ask: string; bid: string }) => api.cardValidate({ sell_price: Number(prices.ask), buy_price: Number(prices.bid) }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr
  });

  // When CardTab loads a card, copy its bid/ask into the validate form and
  // run the manual-flip check automatically. The user sees their loaded
  // card's flip economics validated without any extra typing.
  useEffect(() => {
    const newAsk = ctx.currentRecord?.raw_ask ?? ctx.currentRecord?.flip?.sell_price;
    const newBid = ctx.currentRecord?.raw_bid ?? ctx.currentRecord?.flip?.buy_price;
    if (newAsk != null && newBid != null) {
      const nextAsk = String(newAsk);
      const nextBid = String(newBid);
      setAsk(nextAsk);
      setBid(nextBid);
      manual.mutate({ ask: nextAsk, bid: nextBid });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.currentRecord?.uuid]);
  const backtest = useMutation({
    mutationFn: () => api.backtest({ predictions: parseJsonRows(predictions, "prediction rows"), labels: parseJsonRows(labels, "label rows"), n_bins: 5 }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr
  });
  const strategyBacktest = useMutation({
    mutationFn: () => api.strategyBacktest({ snapshots: ctx.lastScan?.records ?? [], min_snapshots: 30 }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr
  });
  const completedOrderBacktest = useMutation({
    mutationFn: () => api.completedOrderBacktest({
      uuids: Array.from(new Set([
        ...(ctx.currentRecord?.uuid ? [ctx.currentRecord.uuid] : []),
        ...ctx.loadedUuids
      ])),
      min_orders: 30,
      lookback_orders: 20,
      horizons_days: [1, 3, 7]
    }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr
  });
  const historicalSnapshotBacktest = useMutation({
    mutationFn: () => api.historicalSnapshotBacktest({
      uuids: Array.from(new Set([
        ...(ctx.currentRecord?.uuid ? [ctx.currentRecord.uuid] : []),
        ...ctx.loadedUuids
      ])),
      min_snapshots: 30,
      lookback_snapshots: 9,
      horizons_days: [1, 3, 7]
    }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr
  });
  const data = backtest.data;
  const curve = (data?.calibration_curve as Array<Record<string, number>> | undefined) ?? [];
  const currentVerdict = ctx.currentRecord ? verdictOf(ctx.currentRecord) : null;
  const scanSummary = {
    cards: ctx.lastScan?.records.length ?? 0,
    flip_buys: ctx.lastScan?.counts.flip_buys ?? 0,
    upgrade_buys: ctx.lastScan?.counts.upgrade_buys ?? 0,
    watch: ctx.lastScan?.counts.watch ?? 0,
    no_trade: ctx.lastScan?.counts.no_trade ?? 0,
    sells: ctx.lastScan?.counts.sells ?? 0,
    dropped: ctx.lastScan?.counts.dropped ?? 0,
    positive_flip_roi: ctx.lastScan?.market_health?.cards_with_positive_flip_roi ?? 0,
    forecast_warnings: ctx.lastScan?.market_health?.cards_with_forecast_warnings ?? 0,
  };
  function useLastScanPredictions() {
    const rows = (ctx.lastScan?.records ?? [])
      .filter((row) => row.uuid && row.upgrade?.p_cross_next_threshold != null)
      .map((row) => ({
        uuid: row.uuid,
        p_cross_next_threshold: row.upgrade?.p_cross_next_threshold,
      }));
    setPredictions(JSON.stringify(rows, null, 2));
  }
  return (
    <div className="grid">
      {ctx.currentRecord ? (
        <Panel title="Loaded Card Verdict" kicker={currentVerdict ?? "no verdict"}>
          <VerdictBanner record={ctx.currentRecord} />
          {ctx.currentRecord.forecast?.gate_pills?.length ? (
            <div className="gates-pills">
              {ctx.currentRecord.forecast.gate_pills.map((pill) => (
                <span key={pill.key} className={`pill pill-${pill.tone}`} title={pill.reason}>
                  {pill.mark} {pill.label}
                </span>
              ))}
            </div>
          ) : null}
        </Panel>
      ) : null}
      <Panel title="Manual Flip Validation" kicker="same formula as backend">
        <div className="form-row three">
          <input value={ask} onChange={(e) => setAsk(e.target.value)} placeholder="raw ask / sell price" aria-label="manual ask" />
          <input value={bid} onChange={(e) => setBid(e.target.value)} placeholder="raw bid / buy price" aria-label="manual bid" />
          <button onClick={() => manual.mutate({ ask, bid })} disabled={manual.isPending || !ask || !bid}><CheckCircle2 size={15} /> Validate</button>
        </div>
        {manual.error ? <div className="error" role="alert">{manual.error.message}</div> : null}
        {manual.data ? (
          <div className="stat-grid">
            <Stat label="After tax" value={fmtStubs((manual.data.validation as Record<string, unknown>)?.manual_after_tax_sale)} />
            <Stat label="Profit" value={fmtStubs((manual.data.validation as Record<string, unknown>)?.manual_profit)} />
            <Stat label="ROI" value={fmtPct((manual.data.validation as Record<string, unknown>)?.manual_roi, 2)} />
            <Stat label="Mismatch" value={String((manual.data.validation as Record<string, unknown>)?.mismatch)} tone={(manual.data.validation as Record<string, unknown>)?.mismatch ? "bad" : "good"} />
          </div>
        ) : null}
      </Panel>
      <Panel title="Scan Universe Validation Summary" kicker="last real scan only">
        <div className="stat-grid">
          <Stat label="Cards" value={String(scanSummary.cards)} />
          <Stat label="Flip buys" value={String(scanSummary.flip_buys)} tone={scanSummary.flip_buys ? "good" : "neutral"} />
          <Stat label="Upgrade buys" value={String(scanSummary.upgrade_buys)} tone={scanSummary.upgrade_buys ? "info" : "neutral"} />
          <Stat label="Watch" value={String(scanSummary.watch)} />
          <Stat label="No trade" value={String(scanSummary.no_trade)} tone={scanSummary.no_trade ? "warn" : "neutral"} />
          <Stat label="Sells" value={String(scanSummary.sells)} tone={scanSummary.sells ? "bad" : "neutral"} />
          <Stat label="Positive flip ROI" value={String(scanSummary.positive_flip_roi)} />
          <Stat label="Forecast warnings" value={String(scanSummary.forecast_warnings)} />
        </div>
        <pre>{JSON.stringify(scanSummary, null, 2)}</pre>
      </Panel>
      <Panel title="Composite Strategy Backtest" kicker="real snapshots only">
        <p className="muted">Runs only on timestamped real market snapshots. If the scan/session has insufficient real history, the verdict stays UNVALIDATED.</p>
        <button onClick={() => strategyBacktest.mutate()} disabled={strategyBacktest.isPending || !ctx.lastScan?.records.length}><CheckCircle2 size={15} /> Run strategy backtest</button>
        {strategyBacktest.error ? <div className="error" role="alert">{strategyBacktest.error.message}</div> : null}
        {strategyBacktest.data ? (
          <>
            <div className="stat-grid">
              <Stat label="Status" value={String(strategyBacktest.data.status ?? "-")} tone={strategyBacktest.data.status === "available" ? "good" : "warn"} />
              <Stat label="Verdict" value={String(strategyBacktest.data.validation_verdict ?? "-")} />
              <Stat label="Coverage tier" value={String(strategyBacktest.data.data_coverage_tier ?? "UNVALIDATED")} />
              <Stat label="Performance tier" value={String(strategyBacktest.data.performance_validation_tier ?? "UNVALIDATED")} />
              <Stat label="Snapshots" value={fmtNum(strategyBacktest.data.snapshots, 0)} />
              <Stat label="Trades" value={fmtNum(strategyBacktest.data.trades_taken, 0)} />
              <Stat label="Total stubs" value={fmtStubs((strategyBacktest.data.metrics as Record<string, unknown> | undefined)?.total_stubs)} />
              <Stat label="Hit rate" value={fmtPct((strategyBacktest.data.metrics as Record<string, unknown> | undefined)?.hit_rate, 1)} />
            </div>
            <pre>{JSON.stringify({ baselines: strategyBacktest.data.baselines, baseline_comparison: strategyBacktest.data.baseline_comparison, reason_codes: strategyBacktest.data.reason_codes }, null, 2)}</pre>
          </>
        ) : null}
      </Panel>
      <Panel title="Completed-Order Historical Backtest" kicker="The Show sale snapshots">
        <p className="muted">Fetches loaded UUIDs server-side and uses real completed sales as historical sale snapshots. It does not infer historical bid/ask depth, so spread-flip validation remains unavailable from this source.</p>
        <button onClick={() => completedOrderBacktest.mutate()} disabled={completedOrderBacktest.isPending || (!ctx.currentRecord?.uuid && !ctx.loadedUuids.length)}><CheckCircle2 size={15} /> Backtest completed orders</button>
        {completedOrderBacktest.error ? <div className="error" role="alert">{completedOrderBacktest.error.message}</div> : null}
        {completedOrderBacktest.data ? (
          <>
            <div className="stat-grid">
              <Stat label="Status" value={String(completedOrderBacktest.data.status ?? "-")} tone={completedOrderBacktest.data.status === "available" ? "good" : "warn"} />
              <Stat label="Coverage tier" value={String(completedOrderBacktest.data.data_coverage_tier ?? "UNVALIDATED")} />
              <Stat label="Performance tier" value={String(completedOrderBacktest.data.performance_validation_tier ?? "UNVALIDATED")} />
              <Stat label="Sale snapshots" value={fmtNum(completedOrderBacktest.data.snapshots, 0)} />
              <Stat label="Opportunities" value={fmtNum(completedOrderBacktest.data.evaluated_opportunities, 0)} />
              <Stat label="Trades" value={fmtNum(completedOrderBacktest.data.trades_taken, 0)} />
              <Stat label="Total stubs" value={fmtStubs((completedOrderBacktest.data.metrics as Record<string, unknown> | undefined)?.total_stubs)} />
            </div>
            <pre>{JSON.stringify({
              reason_codes: completedOrderBacktest.data.reason_codes,
              leakage_guard: completedOrderBacktest.data.leakage_guard,
              source_limitations: completedOrderBacktest.data.source_limitations,
              horizons: completedOrderBacktest.data.horizons,
              baselines: completedOrderBacktest.data.baselines,
              baseline_comparison: completedOrderBacktest.data.baseline_comparison
            }, null, 2)}</pre>
          </>
        ) : null}
      </Panel>
      <Panel title="Historical Bid/Ask Snapshot Backtest" kicker="The Show price_history">
        <p className="muted">Fetches loaded UUIDs and uses real The Show daily price_history bid/ask rows for rolling-origin 1d/3d/7d strategy validation. If fewer than 30 real snapshots are available, it stays UNVALIDATED.</p>
        <button onClick={() => historicalSnapshotBacktest.mutate()} disabled={historicalSnapshotBacktest.isPending || (!ctx.currentRecord?.uuid && !ctx.loadedUuids.length)}><CheckCircle2 size={15} /> Backtest historical snapshots</button>
        {historicalSnapshotBacktest.error ? <div className="error" role="alert">{historicalSnapshotBacktest.error.message}</div> : null}
        {historicalSnapshotBacktest.data ? (
          <>
            <div className="stat-grid">
              <Stat label="Status" value={String(historicalSnapshotBacktest.data.status ?? "-")} tone={historicalSnapshotBacktest.data.status === "available" ? "good" : "warn"} />
              <Stat label="Coverage tier" value={String(historicalSnapshotBacktest.data.data_coverage_tier ?? "UNVALIDATED")} />
              <Stat label="Performance tier" value={String(historicalSnapshotBacktest.data.performance_validation_tier ?? "UNVALIDATED")} />
              <Stat label="Bid/ask snapshots" value={fmtNum(historicalSnapshotBacktest.data.snapshots, 0)} />
              <Stat label="Opportunities" value={fmtNum(historicalSnapshotBacktest.data.evaluated_opportunities, 0)} />
              <Stat label="Trades" value={fmtNum(historicalSnapshotBacktest.data.trades_taken, 0)} />
              <Stat label="Total stubs" value={fmtStubs((historicalSnapshotBacktest.data.metrics as Record<string, unknown> | undefined)?.total_stubs)} />
            </div>
            <pre>{JSON.stringify({
              reason_codes: historicalSnapshotBacktest.data.reason_codes,
              leakage_guard: historicalSnapshotBacktest.data.leakage_guard,
              source_limitations: historicalSnapshotBacktest.data.source_limitations,
              horizons: historicalSnapshotBacktest.data.horizons,
              baselines: historicalSnapshotBacktest.data.baselines,
              baseline_comparison: historicalSnapshotBacktest.data.baseline_comparison
            }, null, 2)}</pre>
          </>
        ) : null}
      </Panel>
      <Panel title="Upgrade Backtest" kicker="real labels required">
        <p className="muted">Predictions can come from the last scan; labels must be real historical roster-update outcomes.</p>
        <div className="split">
          <label>prediction rows<textarea value={predictions} onChange={(e) => setPredictions(e.target.value)} rows={7} /></label>
          <label>label rows<textarea value={labels} onChange={(e) => setLabels(e.target.value)} rows={7} /></label>
        </div>
        <button onClick={useLastScanPredictions} disabled={!ctx.lastScan?.records.length}><CheckCircle2 size={15} /> Use last scan predictions</button>
        <button onClick={() => backtest.mutate()} disabled={backtest.isPending}><CheckCircle2 size={15} /> Run backtest</button>
        {backtest.error ? <div className="error" role="alert">{backtest.error.message}</div> : null}
        {data ? (
          <>
            <div className="stat-grid">
              <Stat label="Status" value={String(data.status)} tone={data.status === "available" ? "good" : "warn"} />
              <Stat label="N" value={String(data.n ?? 0)} />
              <Stat label="Brier" value={fmtNum(data.brier_score, 3)} />
              <Stat label="Precision" value={fmtPct(data.precision, 1)} />
              <Stat label="Recall" value={fmtPct(data.recall, 1)} />
            </div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={curve}>
                  <XAxis dataKey="mean_predicted" tickFormatter={(v) => `${(Number(v) * 100).toFixed(0)}%`} />
                  <YAxis tickFormatter={(v) => `${(Number(v) * 100).toFixed(0)}%`} />
                  <Tooltip />
                  <Line type="monotone" dataKey="observed_rate" stroke="#10b981" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {curve.length ? (
              <Suspense fallback={<div className="empty">loading reliability ribbon…</div>}>
                <ReliabilityRibbon3D
                  bins={curve.map((row, idx) => ({
                    bin_lo: idx / Math.max(1, curve.length),
                    bin_hi: (idx + 1) / Math.max(1, curve.length),
                    bin_mid: Number(row.mean_predicted ?? row.bin_mid ?? 0),
                    n: Number(row.n ?? 1),
                    mean_pred: Number(row.mean_predicted ?? null),
                    observed_rate: Number(row.observed_rate ?? null),
                  })) as CalibrationBin[]}
                />
              </Suspense>
            ) : null}
          </>
        ) : null}
      </Panel>
    </div>
  );
}

function parseJsonRows(value: string, label: string): Array<Record<string, unknown>> {
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) throw new Error(`${label} must be a JSON array`);
    return parsed as Array<Record<string, unknown>>;
  } catch (error) {
    throw new Error(`${label}: ${error instanceof Error ? error.message : "invalid JSON"}`);
  }
}
