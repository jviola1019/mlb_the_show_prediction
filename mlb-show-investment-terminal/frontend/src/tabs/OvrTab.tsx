import { useMutation } from "@tanstack/react-query";
import { Activity, DatabaseZap } from "lucide-react";
import { api } from "../api";
import type { TerminalContext } from "../appState";
import { fmtNum, fmtPct, Panel, Pill, ReasonCodes, SignalPill, SourceLink, Stat } from "../components";
import type { MLBStatsResponse, SearchResponse } from "../types";
import { useEffect, useRef, useState } from "react";

type FormState = {
  role: "hitter" | "pitcher";
  rarity: string;
  current_ovr: string;
  new_rank: string;
  recent_ops: string;
  season_ops: string;
  recent_avg: string;
  season_avg: string;
  recent_pa: string;
  season_pa: string;
};

const BLANK_FORM: FormState = {
  role: "hitter",
  rarity: "",
  current_ovr: "",
  new_rank: "",
  recent_ops: "",
  season_ops: "",
  recent_avg: "",
  season_avg: "",
  recent_pa: "",
  season_pa: "",
};

function formFromMLBStats(payload: MLBStatsResponse): Partial<FormState> {
  const role = (payload.role ?? "hitter") as "hitter" | "pitcher";
  const recent = (payload.recent ?? {}) as Record<string, unknown>;
  const season = (payload.season ?? {}) as Record<string, unknown>;
  if (role === "pitcher") {
    return {
      role,
      recent_ops: String(recent.era ?? ""),
      season_ops: String(season.era ?? ""),
      recent_avg: String(recent.whip ?? ""),
      season_avg: String(season.whip ?? ""),
      recent_pa: String(recent.inningsPitched ?? recent.ip ?? ""),
      season_pa: String(season.inningsPitched ?? season.ip ?? ""),
    };
  }
  return {
    role,
    recent_ops: String(recent.ops ?? ""),
    season_ops: String(season.ops ?? ""),
    recent_avg: String(recent.avg ?? ""),
    season_avg: String(season.avg ?? ""),
    recent_pa: String(recent.plateAppearances ?? recent.pa ?? recent.atBats ?? ""),
    season_pa: String(season.plateAppearances ?? season.pa ?? season.atBats ?? ""),
  };
}

function formFromCardSearch(payload: SearchResponse): Partial<FormState> {
  const first = payload.listings?.[0];
  const item = first?.item;
  if (!item) return {};
  return {
    rarity: String(item.rarity ?? ""),
    current_ovr: String(item.ovr ?? ""),
  };
}

export function OvrTab({ ctx }: { ctx: TerminalContext }) {
  const recordName = ctx.currentRecord?.name ?? ctx.currentRecord?.card?.name;
  const recordOvr = ctx.currentRecord?.ovr ?? ctx.currentRecord?.card?.current_ovr;
  const recordRarity = ctx.currentRecord?.card?.rarity;
  const [playerName, setPlayerName] = useState(String(recordName ?? "Mike Trout"));
  const [roleMode, setRoleMode] = useState("auto");
  const [form, setForm] = useState<FormState>({
    ...BLANK_FORM,
    rarity: String(recordRarity ?? "Gold"),
    current_ovr: String(recordOvr ?? "84"),
  });
  const [loadedFor, setLoadedFor] = useState<string | null>(recordName ? String(recordName) : null);

  const score = useMutation({
    mutationFn: () => api.upgrade({
      role: form.role,
      rarity: form.rarity,
      current_ovr: Number(form.current_ovr),
      new_rank: form.new_rank ? Number(form.new_rank) : null,
      recent: form.role === "pitcher"
        ? { era: Number(form.recent_ops), whip: Number(form.recent_avg), inningsPitched: Number(form.recent_pa) }
        : { ops: Number(form.recent_ops), avg: Number(form.recent_avg), plateAppearances: Number(form.recent_pa) },
      season: form.role === "pitcher"
        ? { era: Number(form.season_ops), whip: Number(form.season_avg), inningsPitched: Number(form.season_pa) }
        : { ops: Number(form.season_ops), avg: Number(form.season_avg), plateAppearances: Number(form.season_pa) }
    }),
    onSuccess: ctx.markApiOk,
    onError: ctx.markApiErr
  });

  // Fetch BOTH endpoints (MLB stats + The Show card) in parallel so a name
  // search fully resets every form field. Returns nullable structs so partial
  // failures (e.g. unknown player on MLB Stats API) still update what we have.
  const loadPlayer = useMutation({
    mutationFn: async () => {
      const stats = api.mlbStats(playerName, roleMode).catch(() => null);
      const card = api.search(playerName).catch(() => null);
      const [statsPayload, cardPayload] = await Promise.all([stats, card]);
      return { stats: statsPayload, card: cardPayload };
    },
    onSuccess: ({ stats, card }) => {
      // Reset the form to BLANK before applying any new data so stale numbers
      // from the previous player can never bleed through a partial fetch.
      setForm((prev) => {
        const next: FormState = { ...BLANK_FORM, new_rank: "" };
        if (card) Object.assign(next, formFromCardSearch(card));
        if (stats) Object.assign(next, formFromMLBStats(stats));
        // Preserve role override if the user explicitly chose one.
        if (roleMode === "hitter" || roleMode === "pitcher") {
          next.role = roleMode;
        }
        // Fall back to previous values for any field where neither endpoint
        // returned data (so totally-empty rows render as "" not "undefined").
        (Object.keys(BLANK_FORM) as (keyof FormState)[]).forEach((key) => {
          const value = next[key];
          if (value === undefined || value === "undefined") {
            if (key === "role") {
              next.role = prev.role;
            } else {
              next[key] = prev[key];
            }
          }
        });
        return next;
      });
      setLoadedFor(playerName);
      // Clear any prior upgrade-score readout so the displayed result always
      // matches the active player.
      score.reset();
      ctx.markApiOk();
    },
    onError: ctx.markApiErr,
  });

  // Propagate CARD-tab loads into this tab. The full reset goes through
  // loadPlayer.mutate() so behavior is identical to clicking "Load player".
  const lastSyncedUuid = useRef<string | null>(null);
  useEffect(() => {
    const uuid = ctx.currentRecord?.uuid ?? null;
    if (!uuid || !recordName) return;
    if (uuid === lastSyncedUuid.current) return;
    lastSyncedUuid.current = uuid;
    setPlayerName(String(recordName));
    loadPlayer.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.currentRecord?.uuid, recordName]);

  const stats = loadPlayer.data?.stats ?? null;
  const card = loadPlayer.data?.card ?? null;
  const cardItem = card?.listings?.[0]?.item;
  const data = score.data;

  const labelFor = (key: string) => {
    if (form.role !== "pitcher") return key.replaceAll("_", " ");
    const pitcherLabels: Record<string, string> = {
      recent_ops: "recent ERA",
      season_ops: "season ERA",
      recent_avg: "recent WHIP",
      season_avg: "season WHIP",
      recent_pa: "recent IP",
      season_pa: "season IP"
    };
    return pitcherLabels[key] ?? key.replaceAll("_", " ");
  };
  const playerChanged = loadedFor != null && playerName.trim() !== loadedFor.trim();
  return (
    <Panel title="Threshold Model" kicker="MLB Stats API + The Show + /api/upgrade/score">
      <div className="lookup-strip">
        <label>player name<input value={playerName} onChange={(e) => setPlayerName(e.target.value)} placeholder="e.g. Bobby Witt Jr." /></label>
        <label>stats role
          <select value={roleMode} onChange={(e) => setRoleMode(e.target.value)}>
            <option value="auto">auto</option>
            <option value="hitter">hitter</option>
            <option value="pitcher">pitcher</option>
          </select>
        </label>
        <button onClick={() => loadPlayer.mutate()} disabled={!playerName || loadPlayer.isPending}>
          <DatabaseZap size={15} /> Load player
        </button>
      </div>
      {loadPlayer.isPending ? (
        <div className="status-line">
          <Pill tone="info">resetting form…</Pill>
          <span className="muted">fetching MLB stats + The Show card for {playerName}</span>
        </div>
      ) : stats || card ? (
        <div className="status-line">
          {stats?.player ? <Pill tone="good">{stats.player.full_name}</Pill> : <Pill tone="warn">no MLB player match</Pill>}
          {stats?.role ? <Pill tone="info">{stats.role}</Pill> : null}
          {cardItem ? <Pill tone="info">OVR {cardItem.ovr ?? "-"} {cardItem.rarity ?? ""}</Pill> : <Pill tone="warn">no The Show match</Pill>}
          {stats?.recent_start ? <span className="muted">{stats.recent_start} to {stats.end}</span> : null}
          <SourceLink url="https://statsapi.mlb.com" />
          {playerChanged ? <Pill tone="warn">player changed — click Load to reset</Pill> : null}
        </div>
      ) : (
        <div className="empty">Click "Load player" to fully reset every field from the player's MLB stats and The Show card.</div>
      )}
      {loadPlayer.error ? <div className="error">{loadPlayer.error.message}</div> : null}
      <div className="control-grid">
        {Object.entries(form).map(([key, value]) => (
          <label key={key}>
            {labelFor(key)}
            <input
              value={value}
              onChange={(e) => {
                const v = e.target.value;
                if (key === "role") {
                  setForm({ ...form, role: v === "pitcher" ? "pitcher" : "hitter" });
                } else {
                  setForm({ ...form, [key]: v } as FormState);
                }
              }}
            />
          </label>
        ))}
      </div>
      <button onClick={() => score.mutate()} disabled={score.isPending}>
        <Activity size={15} /> Score upgrade probability
      </button>
      {score.error ? <div className="error">{score.error.message}</div> : null}
      {data ? (
        <>
          <div className="stat-grid">
            <Stat label="Action" value={<SignalPill action={String(data.action)} />} />
            <Stat label="P(Cross next)" value={fmtPct(data.p_cross_next_threshold, 1)} />
            <Stat label="P(Cross 85)" value={fmtPct(data.p_cross_85, 1)} />
            <Stat label="P(Up)" value={fmtPct(data.p_upgrade, 1)} />
            <Stat label="P(Down)" value={fmtPct(data.p_downgrade, 1)} />
            <Stat label="Confidence" value={fmtNum(data.confidence, 0)} />
            <Stat label="Upgrade score" value={fmtNum(data.upgrade_score, 0)} />
            <Stat label="Exact delta" value={String(data.exact_delta_ovr ?? "-")} />
          </div>
          <div className="reason-block single">
            <div>
              <div className="stat-label">Reason codes</div>
              <ReasonCodes codes={data.reason_codes as string[] | undefined} />
            </div>
          </div>
        </>
      ) : null}
    </Panel>
  );
}
