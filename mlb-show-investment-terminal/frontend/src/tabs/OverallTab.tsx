import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { SpreadLiquidityScatter } from "../analytics";
import type { TerminalContext } from "../appState";
import {
  CardIdentity,
  DensityDots,
  FreshnessBadge,
  fmtNum,
  fmtPct,
  fmtStubs,
  formatDateTime,
  Panel,
  Pill,
  SignalPill,
  Stat,
} from "../components";
import { finalAction, StrategySummary } from "../strategyComponents";
import { VerdictBanner, blankIf, governedAction, isInvestable, verdictOf } from "../verdictGuard";

export function OverallTab({ ctx }: { ctx: TerminalContext }) {
  const [now, setNow] = useState(() => new Date());
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 60_000 });
  const session = useQuery({ queryKey: ["session"], queryFn: api.session, refetchInterval: 60_000 });
  const roster = useQuery({ queryKey: ["roster-updates"], queryFn: api.rosterUpdates, refetchInterval: 300_000 });

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const counts = ctx.lastScan?.counts;
  const healthTone = health.data?.status === "ok" ? "good" : health.error ? "bad" : "warn";

  const record = ctx.currentRecord;
  const cardStatus = record ? verdictOf(record) : null;
  const overallTone = cardStatus === "INVESTABLE" ? "good" : cardStatus === "OBSERVATIONAL ONLY" ? "warn" : cardStatus ? "bad" : "neutral";
  const scanScatter = useMemo(() => (ctx.lastScan?.records ?? []).map((row) => ({
    label: String(row.name ?? row.card?.name ?? row.uuid ?? "-"),
    spreadPct: Number(row.spread_pct ?? row.flip?.spread_pct ?? 0),
    liquidity: Number(row.liquidity_recent ?? row.flip?.liquidity_recent ?? row.card?.liquidity_recent ?? 0),
    ev: Number(row.flip_roi ?? row.flip?.roi ?? row.forecast_ev_7d ?? row.forecast?.expected_ret ?? 0),
  })), [ctx.lastScan?.records]);

  return (
    <div className="grid">
      {record ? (
        <Panel
          title="Command Center"
          kicker={
            <span className="kicker-row">
              <Pill tone={overallTone}>{String(record.name ?? record.card?.name ?? "loaded")}</Pill>
              {record.fetched_at ? <FreshnessBadge at={record.fetched_at} label="LISTING" /> : null}
            </span>
          }
          className="current-card-panel"
        >
          <CardIdentity record={record} />
          <StrategySummary record={record} />
          <VerdictBanner record={record} />
          <div className="stat-grid">
            <Stat
              label="Final Action"
              value={<SignalPill action={finalAction(record)} />}
              tone={overallTone}
            />
            <Stat
              label="Validation Tier"
              value={String(record.validation_tier ?? record.decision_tier ?? record.tier ?? record.forecast?.tier ?? "-")}
            />
            <Stat
              label="Current OVR"
              value={String(record.ovr ?? record.card?.current_ovr ?? "-")}
            />
            <Stat
              label="Rarity"
              value={String(record.card?.rarity ?? "-")}
            />
            <Stat
              label="Strategy type"
              value={String(record.strategy?.composite?.strategy_type ?? record.responsible_channel ?? "-")}
            />
            <Stat
              label="Legacy verdict"
              value={String(cardStatus ?? "-")}
              tone={overallTone}
            />
            <Stat
              label="Flip channel"
              value={<SignalPill action={governedAction(record, record.decision_action ?? record.decision?.action ?? record.flip?.action)} />}
            />
            <Stat
              label="Upgrade signal"
              value={<SignalPill action={governedAction(record, record.upgrade?.action)} />}
            />
            <Stat
              label="Raw ask"
              value={fmtStubs(record.flip?.sell_price ?? record.card?.raw_ask)}
            />
            <Stat
              label="Raw bid"
              value={fmtStubs(record.flip?.buy_price ?? record.card?.raw_bid)}
            />
            <Stat
              label="After-tax profit"
              value={fmtStubs(record.flip?.profit)}
              tone={isInvestable(record) && (record.flip?.profit ?? 0) > 0 ? "good" : "neutral"}
            />
            <Stat label="Flip ROI" value={fmtPct(record.flip?.roi, 2)} />
            <Stat
              label="Scenario P(Cross 85)"
              value={fmtPct(record.upgrade?.p_cross_85, 1)}
            />
            <Stat
              label="Forecast EV"
              value={blankIf(record, fmtPct(record.forecast?.expected_ret, 2))}
            />
            <Stat
              label="Direction"
              value={String(record.forecast?.direction ?? "-")}
            />
            <Stat
              label="N prices"
              value={fmtNum(record.forecast?.n_prices, 0)}
            />
            <Stat
              label="Liquidity"
              value={<DensityDots score={record.flip?.liquidity_score ?? record.card?.liquidity_score} />}
            />
            <Stat
              label="Block length"
              value={fmtNum(record.forecast?.block_length as number | undefined, 0)}
            />
          </div>
          {record.forecast?.gate_pills?.length ? (
            <div className="gates-pills">
              {record.forecast.gate_pills.map((pill) => (
                <span key={pill.key} className={`pill pill-${pill.tone}`} title={pill.reason}>
                  {pill.mark} {pill.label}
                </span>
              ))}
            </div>
          ) : null}
        </Panel>
      ) : (
        <Panel title="Current Card" kicker="not loaded">
          <p className="muted">
            Search a player on the Trade Ticket tab and click Load. Their final action, validation tier, OVR, forecast,
            and flip economics will populate here automatically.
          </p>
        </Panel>
      )}

      <Panel title="App Health" kicker={<Pill tone={healthTone}>{String(health.data?.status ?? "checking")}</Pill>}>
        <div className="stat-grid">
          <Stat label="Quant owner" value={String(health.data?.quant_owner ?? "-")} />
          <Stat label="Frontend" value={String(health.data?.frontend ?? "react")} />
          <Stat label="Version" value={String(health.data?.version ?? "-")} />
          <Stat label="App time" value={now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} sub={now.toLocaleDateString()} />
          <Stat label="Last API OK" value={formatDateTime(ctx.apiOkAt)} tone={ctx.apiOkAt ? "good" : "neutral"} />
          <Stat label="Last API ERR" value={formatDateTime(ctx.apiErrAt)} tone={ctx.apiErrAt ? "bad" : "neutral"} />
          <Stat label="Server started" value={formatDateTime(session.data?.started_at)} />
          <Stat label="Runtime writes" value={runtimeWrites(session.data?.runtime_writes)} />
        </div>
      </Panel>

      <Panel title="Last Scan" kicker={ctx.lastScanAt ? formatDateTime(ctx.lastScanAt) : "not run"}>
        <div className="stat-grid">
          <Stat label="Cards scanned" value={String(ctx.lastScan?.records.length ?? 0)} />
          <Stat label="Flip candidates" value={String(counts?.flip_buys ?? 0)} tone={(counts?.flip_buys ?? 0) > 0 ? "good" : "neutral"} />
          <Stat label="Hold candidates" value={String(counts?.upgrade_buys ?? 0)} tone={(counts?.upgrade_buys ?? 0) > 0 ? "info" : "neutral"} />
          <Stat label="Watch" value={String(counts?.watch ?? 0)} tone={(counts?.watch ?? 0) > 0 ? "info" : "neutral"} />
          <Stat label="No trade" value={String(counts?.no_trade ?? 0)} tone={(counts?.no_trade ?? 0) > 0 ? "warn" : "neutral"} />
          <Stat label="Holds" value={String(counts?.holds ?? 0)} />
          <Stat label="Sells" value={String(counts?.sells ?? 0)} tone={(counts?.sells ?? 0) > 0 ? "bad" : "neutral"} />
          <Stat label="Dropped" value={String(counts?.dropped ?? 0)} tone={(counts?.dropped ?? 0) > 0 ? "warn" : "neutral"} />
          <Stat label="Loaded UUIDs" value={String(ctx.loadedUuids.length)} />
          <Stat label="Last listing" value={formatDateTime(ctx.lastListingAt)} />
        </div>
      </Panel>

      <Panel title="Roster Updates" kicker={String(roster.data?.status ?? "checking")}>
        <div className="stat-grid">
          <Stat label="Source" value={String(roster.data?.source ?? "-")} />
          <Stat label="Updates" value={String((roster.data?.updates as unknown[] | undefined)?.length ?? 0)} />
          <Stat label="Server time" value={formatDateTime(String(roster.data?.server_time ?? ""))} />
          <Stat label="Status" value={String(roster.data?.status ?? "-")} tone={roster.data?.status === "available" ? "good" : "warn"} />
        </div>
        {roster.data?.reason ? <div className="muted">{String(roster.data.reason)}</div> : null}
      </Panel>

      <Panel title="Market Health" kicker="last scan medians">
        <div className="stat-grid">
          <Stat label="Median spread" value={pct(ctx.lastScan?.market_health?.median_spread)} />
          <Stat label="Median liquidity" value={num(ctx.lastScan?.market_health?.median_liquidity_recent)} />
          <Stat label="Forecast warnings" value={num(ctx.lastScan?.market_health?.cards_with_forecast_warnings)} tone={(ctx.lastScan?.market_health?.cards_with_forecast_warnings ?? 0) > 0 ? "warn" : "neutral"} />
          <Stat label="Positive flip ROI" value={num(ctx.lastScan?.market_health?.cards_with_positive_flip_roi)} />
        </div>
        <div className="reason-list">
          {Object.entries(ctx.lastScan?.tier_distribution ?? {}).length
            ? Object.entries(ctx.lastScan?.tier_distribution ?? {}).map(([tier, count]) => <Pill key={tier}>{tier}: {count}</Pill>)
            : <span className="empty">No validation tier distribution until a scan runs.</span>}
          {Object.entries(ctx.lastScan?.rarity_distribution ?? {}).map(([rarity, count]) => <Pill key={rarity} tone="info">{rarity}: {count}</Pill>)}
        </div>
      </Panel>

      {ctx.lastScan?.records?.length ? (
        <Panel title="Opportunity Analytics" kicker="liquidity, spread, and expected edge">
          <SpreadLiquidityScatter data={scanScatter} />
        </Panel>
      ) : null}

      <Panel title="Operating Rules" kicker="hard constraints">
        <ul className="rule-list">
          <li>Final action comes from the strategy matrix, not from a single BUY ladder.</li>
          <li>INVESTABLE is directional-only and appears only when positive holding EV clears gates.</li>
          <li>Positive spread plus bearish forecast becomes INSTANT FLIP ONLY, never INVESTABLE.</li>
          <li>Historical calibration and Supabase snapshots control validation tier promotion.</li>
          <li>When real history is insufficient, the model state is data collection / no execution.</li>
        </ul>
      </Panel>
    </div>
  );
}

function pct(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%` : "-";
}

function num(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("en-US") : "-";
}

function runtimeWrites(value: unknown): string {
  if (!value) return "read-only degraded";
  if (typeof value === "string") return value;
  if (typeof value === "object") {
    const status = (value as Record<string, unknown>).status ?? "unknown";
    const mode = (value as Record<string, unknown>).mode ?? "";
    return `${status}${mode ? ` / ${mode}` : ""}`;
  }
  return String(value);
}
