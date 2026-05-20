import type { MLBStatsResponse, ParityAudit, ScanJob, ScanResponse, SearchResponse, SessionSummary, TopListingsResponse } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail ?? parsed);
    } catch {
      detail = body;
    }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Record<string, unknown>>("/api/health"),
  session: () => request<SessionSummary>("/api/session/summary"),
  parity: () => request<ParityAudit>("/api/audit/parity"),
  rosterUpdates: () => request<Record<string, unknown>>("/api/roster/updates"),
  search: (name: string, year = 26) => request<SearchResponse>(`/api/search?name=${encodeURIComponent(name)}&year=${year}`),
  topListings: (rarity: string, topN: number, year = 26) => request<TopListingsResponse>(`/api/live/top-listings?rarity=${encodeURIComponent(rarity)}&top_n=${topN}&year=${year}`),
  mlbStats: (name: string, role = "auto", days = 14) => request<MLBStatsResponse>(`/api/mlb/player-stats?name=${encodeURIComponent(name)}&role=${encodeURIComponent(role)}&days=${days}`),
  listing: (uuid: string, year = 26) => request<Record<string, unknown>>(`/api/listing/${uuid}?year=${year}`),
  analyze: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/card/analyze", { method: "POST", body: JSON.stringify(payload) }),
  cardValidate: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/card/validate", { method: "POST", body: JSON.stringify(payload) }),
  scan: (payload: Record<string, unknown>) => request<ScanResponse>("/api/scan", { method: "POST", body: JSON.stringify(payload) }),
  startScanJob: (payload: Record<string, unknown>) => request<ScanJob>("/api/scan/jobs", { method: "POST", body: JSON.stringify(payload) }),
  scanJob: (jobId: string) => request<ScanJob>(`/api/scan/jobs/${jobId}`),
  upgrade: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/upgrade/score", { method: "POST", body: JSON.stringify(payload) }),
  backtest: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/backtest/upgrades", { method: "POST", body: JSON.stringify(payload) }),
  strategyBacktest: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/backtest/strategy", { method: "POST", body: JSON.stringify(payload) }),
  completedOrderBacktest: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/backtest/completed-orders", { method: "POST", body: JSON.stringify(payload) }),
  historicalSnapshotBacktest: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/backtest/historical-snapshots", { method: "POST", body: JSON.stringify(payload) }),
  persistence: () => request<Record<string, unknown>>("/api/persistence/status"),
  ledgerLog: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/ledger/log", { method: "POST", body: JSON.stringify(payload) }),
  ledgerSummary: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/api/ledger/summary", { method: "POST", body: JSON.stringify(payload) })
};
