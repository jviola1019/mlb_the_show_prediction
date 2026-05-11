import { useMutation } from "@tanstack/react-query";
import { Activity, DatabaseZap } from "lucide-react";
import { api } from "../api";
import type { TerminalContext } from "../appState";
import { fmtNum, fmtPct, Panel, Pill, ReasonCodes, SignalPill, SourceLink, Stat } from "../components";
import { useEffect, useState } from "react";

export function OvrTab({ ctx }: { ctx: TerminalContext }) {
  const recordName = ctx.currentRecord?.name ?? ctx.currentRecord?.card?.name;
  const recordOvr = ctx.currentRecord?.ovr ?? ctx.currentRecord?.card?.current_ovr;
  const recordRarity = ctx.currentRecord?.card?.rarity;
  const [playerName, setPlayerName] = useState(String(recordName ?? "Mike Trout"));
  const [roleMode, setRoleMode] = useState("auto");
  const [form, setForm] = useState({
    role: "hitter",
    rarity: String(recordRarity ?? "Gold"),
    current_ovr: String(recordOvr ?? "84"),
    new_rank: "",
    recent_ops: "0.950",
    season_ops: "0.780",
    recent_avg: "0.320",
    season_avg: "0.270",
    recent_pa: "42",
    season_pa: "180"
  });
  const stats = useMutation({
    mutationFn: () => api.mlbStats(playerName, roleMode),
    onSuccess: (payload) => {
      ctx.markApiOk();
      const role = payload.role ?? "hitter";
      const recent = payload.recent ?? {};
      const season = payload.season ?? {};
      if (role === "pitcher") {
        setForm((prev) => ({
          ...prev,
          role,
          recent_ops: String(recent.era ?? ""),
          season_ops: String(season.era ?? ""),
          recent_avg: String(recent.whip ?? ""),
          season_avg: String(season.whip ?? ""),
          recent_pa: String(recent.inningsPitched ?? recent.ip ?? ""),
          season_pa: String(season.inningsPitched ?? season.ip ?? "")
        }));
      } else {
        setForm((prev) => ({
          ...prev,
          role,
          recent_ops: String(recent.ops ?? ""),
          season_ops: String(season.ops ?? ""),
          recent_avg: String(recent.avg ?? ""),
          season_avg: String(season.avg ?? ""),
          recent_pa: String(recent.plateAppearances ?? recent.pa ?? recent.atBats ?? ""),
          season_pa: String(season.plateAppearances ?? season.pa ?? season.atBats ?? "")
        }));
      }
    },
    onError: ctx.markApiErr
  });

  // When CARD tab loads a player, propagate name + OVR + rarity into this form
  // and auto-fetch their MLB stats so the user doesn't have to retype.
  useEffect(() => {
    if (!recordName) return;
    setPlayerName(String(recordName));
    setForm((prev) => ({
      ...prev,
      current_ovr: String(recordOvr ?? prev.current_ovr),
      rarity: String(recordRarity ?? prev.rarity),
    }));
    stats.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordName, recordOvr, recordRarity]);
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
  return (
    <Panel title="Threshold Model" kicker="MLB Stats API + Python /api/upgrade/score">
      <div className="lookup-strip">
        <label>player name<input value={playerName} onChange={(e) => setPlayerName(e.target.value)} placeholder="e.g. Bobby Witt Jr." /></label>
        <label>stats role
          <select value={roleMode} onChange={(e) => setRoleMode(e.target.value)}>
            <option value="auto">auto</option>
            <option value="hitter">hitter</option>
            <option value="pitcher">pitcher</option>
          </select>
        </label>
        <button onClick={() => stats.mutate()} disabled={!playerName || stats.isPending}><DatabaseZap size={15} /> Load MLB stats</button>
      </div>
      {stats.data ? (
        <div className="status-line">
          {stats.data.player ? <Pill tone="good">{stats.data.player.full_name}</Pill> : <Pill tone="warn">no player match</Pill>}
          <Pill tone="info">{stats.data.role}</Pill>
          <span className="muted">{stats.data.recent_start} to {stats.data.end}</span>
          <SourceLink url="https://statsapi.mlb.com" />
        </div>
      ) : <div className="empty">Load MLB stats to fill the recent and season inputs automatically.</div>}
      {stats.error ? <div className="error">{stats.error.message}</div> : null}
      <div className="control-grid">
        {Object.entries(form).map(([key, value]) => (
          <label key={key}>{labelFor(key)}<input value={value} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /></label>
        ))}
      </div>
      <button onClick={() => score.mutate()} disabled={score.isPending}><Activity size={15} /> Score upgrade probability</button>
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
