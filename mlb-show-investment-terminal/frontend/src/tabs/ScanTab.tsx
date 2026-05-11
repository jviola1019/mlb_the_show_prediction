import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, ListChecks } from "lucide-react";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";

const ScanDepthHeatmap3D = lazy(() => import("../viz/ScanDepthHeatmap3D"));
import { api } from "../api";
import type { TerminalContext } from "../appState";
import { FreshnessBadge, Panel, Pill, RecordsTable, SourceLink, Stat } from "../components";
import type { ScanJob, ScoreRecord } from "../types";
import { parseUuidTokens } from "../uuid";

type ScanMode = "top_live" | "paste_uuids" | "session_history";

export function ScanTab({ ctx }: { ctx: TerminalContext }) {
  const [mode, setMode] = useState<ScanMode>("paste_uuids");
  const [rarity, setRarity] = useState("Gold");
  const [topN, setTopN] = useState("10");
  const [uuidText, setUuidText] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [selectedUuid, setSelectedUuid] = useState<string | undefined>();
  const parsed = useMemo(() => parseUuidTokens(uuidText), [uuidText]);

  const preview = useMutation({
    mutationFn: () => api.topListings(rarity, Number(topN || 10)),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr
  });

  const startScan = useMutation({
    mutationFn: () => api.startScanJob({
      mode,
      rarity,
      top_n: Number(topN || 10),
      uuid_text: uuidText,
      session_uuids: ctx.loadedUuids,
      rate_delay: 1.5,
      enrich_mlb_stats: true
    }),
    onSuccess: (payload: ScanJob) => {
      setJobId(payload.job_id);
      ctx.markApiOk();
    },
    onError: ctx.markApiErr
  });

  const job = useQuery({
    queryKey: ["scan-job", jobId],
    queryFn: () => api.scanJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "complete" || status === "error" ? false : 1000;
    }
  });

  useEffect(() => {
    if (job.data?.status === "complete" && job.data.result) {
      ctx.setLastScan(job.data.result);
      ctx.markApiOk();
    }
    if (job.data?.status === "error") {
      ctx.markApiErr();
    }
  }, [job.data?.status, job.data?.result]);

  const data = job.data?.result ?? ctx.lastScan;
  const activeJob = (job.data ?? startScan.data) as ScanJob | undefined;
  const canRun = mode === "top_live" || (mode === "paste_uuids" && parsed.uuids.length > 0) || (mode === "session_history" && ctx.loadedUuids.length > 0);
  const isRunning = startScan.isPending || activeJob?.status === "queued" || activeJob?.status === "running";
  const progressPct = activeJob?.total ? Math.max(0, Math.min(100, (activeJob.completed / activeJob.total) * 100)) : 0;

  function selectRecord(record: ScoreRecord) {
    const uuid = record.uuid ?? record.card?.uuid;
    if (!uuid || record.status === "dropped") return;
    setSelectedUuid(uuid);
    ctx.addLoadedUuid(uuid);
    ctx.setCurrentRecord(record);
    ctx.openTab("card");
  }

  return (
    <div className="grid">
      <Panel title="Universe" kicker="server-side scan modes">
        <div className="segmented" role="group" aria-label="Scan mode">
          <button className={mode === "top_live" ? "active" : ""} onClick={() => setMode("top_live")}>Top live rarity</button>
          <button className={mode === "paste_uuids" ? "active" : ""} onClick={() => setMode("paste_uuids")}>Paste UUIDs</button>
          <button className={mode === "session_history" ? "active" : ""} onClick={() => setMode("session_history")}>Session history</button>
        </div>

        {mode === "top_live" ? (
          <>
            <div className="form-row">
              <select value={rarity} onChange={(e) => setRarity(e.target.value)} aria-label="rarity">
                <option>Gold</option>
                <option>Diamond</option>
                <option>Silver</option>
                <option>Bronze</option>
              </select>
              <input value={topN} onChange={(e) => setTopN(e.target.value)} aria-label="top n" />
              <button onClick={() => preview.mutate()} disabled={preview.isPending}><ListChecks size={15} /> Preview</button>
            </div>
            {preview.data ? (
              <div className="status-line">
                <Pill tone="info">{preview.data.uuids.length} discovered</Pill>
                <span className="muted">year={preview.data.year ?? "-"}</span>
                <FreshnessBadge at={preview.data.fetched_at} label="UNIVERSE" />
                <SourceLink url={preview.data.source_url} />
              </div>
            ) : <div className="empty">Preview fetches the current top rarity universe without starting the full scan.</div>}
          </>
        ) : null}

        {mode === "paste_uuids" ? (
          <>
            <textarea value={uuidText} onChange={(e) => setUuidText(e.target.value)} placeholder="Paste UUIDs, URLs, or text containing UUIDs" rows={6} />
            <div className="status-line">
              <Pill tone="info">{parsed.uuids.length} valid</Pill>
              <Pill tone={parsed.duplicates.length ? "warn" : "neutral"}>{parsed.duplicates.length} duplicates</Pill>
              <Pill tone={parsed.invalidTokens.length ? "bad" : "neutral"}>{parsed.invalidTokens.length} invalid tokens</Pill>
            </div>
          </>
        ) : null}

        {mode === "session_history" ? (
          <div className="session-list">
            {ctx.loadedUuids.length ? ctx.loadedUuids.map((id) => <code key={id}>{id}</code>) : <div className="empty">No cards loaded this session.</div>}
          </div>
        ) : null}

        <div className="run-row">
          <button onClick={() => startScan.mutate()} disabled={isRunning || !canRun}><BarChart3 size={15} /> Run scan</button>
          <span className="muted">Rate-limited live APIs can make larger scans slow; decisions remain partitioned by engine.</span>
        </div>
        {activeJob ? (
          <div className="scan-progress">
            <div className="progress-strip determinate"><span style={{ width: `${progressPct}%` }} /></div>
            <div className="status-line">
              <Pill tone={activeJob.status === "error" ? "bad" : activeJob.status === "complete" ? "good" : "info"}>{activeJob.status}</Pill>
              <span className="muted">{activeJob.completed}/{activeJob.total} scanned</span>
              {activeJob.current_name ? <span className="muted">current: <code>{activeJob.current_name}</code></span> : null}
              {activeJob.current_uuid ? <code>{activeJob.current_uuid}</code> : null}
              <Pill tone={(activeJob.dropped_count ?? 0) ? "warn" : "neutral"}>{activeJob.dropped_count ?? 0} dropped</Pill>
              <Pill tone={(activeJob.invalid_count ?? 0) ? "bad" : "neutral"}>{activeJob.invalid_count ?? 0} invalid</Pill>
            </div>
          </div>
        ) : null}
        {startScan.error ? <div className="error">{startScan.error.message}</div> : null}
        {job.data?.error ? <div className="error">{job.data.error}</div> : null}
      </Panel>

      {data ? (
        <>
          <Panel title="Scan Summary" kicker={ctx.lastScanAt ? <FreshnessBadge at={ctx.lastScanAt} label="SCAN" /> : undefined}>
            <div className="stat-grid">
              <Stat label="Mode" value={data.mode ?? mode} />
              <Stat label="Cards" value={String(data.records.length)} />
              <Stat label="Flip buys" value={String(data.counts.flip_buys ?? 0)} tone={(data.counts.flip_buys ?? 0) ? "good" : "neutral"} />
              <Stat label="Upgrade buys" value={String(data.counts.upgrade_buys ?? 0)} tone={(data.counts.upgrade_buys ?? 0) ? "info" : "neutral"} />
              <Stat label="Watch" value={String(data.counts.watch ?? 0)} tone={(data.counts.watch ?? 0) ? "info" : "neutral"} />
              <Stat label="No trade" value={String(data.counts.no_trade ?? 0)} tone={(data.counts.no_trade ?? 0) ? "warn" : "neutral"} />
              <Stat label="Holds" value={String(data.counts.holds ?? 0)} />
              <Stat label="Sells" value={String(data.counts.sells ?? 0)} tone={(data.counts.sells ?? 0) ? "bad" : "neutral"} />
              <Stat label="Dropped" value={String(data.counts.dropped ?? 0)} tone={(data.counts.dropped ?? 0) ? "warn" : "neutral"} />
              <Stat label="UUID invalid" value={String(data.uuid_parse.invalid_tokens.length)} />
              <Stat label="Elapsed" value={`${data.progress?.elapsed_seconds ?? "-"}s`} />
            </div>
            <div className="muted">{data.progress?.rate_limit_message}</div>
          </Panel>
          <Panel title="Flip Buys" kicker="executable bid/ask math">
            <RecordsTable rows={data.partitions.flip_buys} kind="flip" onRowClick={selectRecord} selectedUuid={selectedUuid} />
          </Panel>
          <Panel title="Market Depth 3D" kicker="OVR x liquidity x flip ROI, color = validation tier">
            <Suspense fallback={<div className="empty">loading 3D heatmap...</div>}>
              <ScanDepthHeatmap3D records={data.records} />
            </Suspense>
          </Panel>
          <Panel title="Upgrade Buys" kicker="scenario threshold edge, uncalibrated unless backtested">
            <RecordsTable rows={data.partitions.upgrade_buys} kind="upgrade" onRowClick={selectRecord} selectedUuid={selectedUuid} />
          </Panel>
          <Panel title="Watch" kicker="informational or uncalibrated signals">
            <p className="muted">Watch rows keep flip ROI, forecast EV, and scenario probabilities separate. They are not buy signals.</p>
            <RecordsTable rows={data.partitions.watch ?? []} kind="watch" onRowClick={selectRecord} selectedUuid={selectedUuid} />
          </Panel>
          <Panel title="Holds">
            <RecordsTable rows={data.partitions.holds} kind="holds" onRowClick={selectRecord} selectedUuid={selectedUuid} />
          </Panel>
          <Panel title="Sells">
            <RecordsTable rows={data.partitions.sells} kind="sells" onRowClick={selectRecord} selectedUuid={selectedUuid} />
          </Panel>
          <Panel title="No Trade" kicker="blocked by executable book, ROI, liquidity, or data gates">
            <RecordsTable rows={data.partitions.no_trade ?? []} kind="no_trade" onRowClick={selectRecord} selectedUuid={selectedUuid} />
          </Panel>
          <Panel title="Observational Legacy" kicker="compatibility bucket">
            <RecordsTable rows={data.partitions.observational ?? []} kind="observational" onRowClick={selectRecord} selectedUuid={selectedUuid} />
          </Panel>
          <Panel title="Dropped / Invalid" kicker={`${Object.values(data.dropped_summary ?? {}).reduce((a, b) => a + b, 0)} grouped`}>
            <DroppedSummary summary={data.dropped_summary} />
            <RecordsTable rows={data.partitions.dropped} kind="dropped" />
          </Panel>
        </>
      ) : null}
    </div>
  );
}

function DroppedSummary({ summary }: { summary?: Record<string, number> }) {
  const entries = Object.entries(summary ?? {});
  if (!entries.length) return <div className="empty">No dropped or invalid cards in this scan.</div>;
  return (
    <div className="reason-list dropped-summary">
      {entries.map(([reason, count]) => <Pill key={reason} tone="warn">{reason}: {count}</Pill>)}
    </div>
  );
}
