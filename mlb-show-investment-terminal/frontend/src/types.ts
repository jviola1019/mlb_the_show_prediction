export type Tone = "neutral" | "good" | "bad" | "warn" | "info";

export type FlipResult = {
  action: string;
  sell_price?: number | null;
  buy_price?: number | null;
  after_tax_sale?: number | null;
  profit?: number | null;
  roi?: number | null;
  spread_pct?: number | null;
  liquidity_score?: number | null;
  liquidity_n?: number | null;
  liquidity_recent?: number | null;
  reason_codes?: string[];
  reason_codes_csv?: string;
};

export type UpgradeResult = {
  action: string;
  current_ovr?: number | null;
  rarity?: string | null;
  new_rank?: number | null;
  next_threshold?: number | null;
  distance_to_threshold?: number | null;
  distance_to_85?: number | null;
  distance_to_90?: number | null;
  p_upgrade?: number | null;
  p_downgrade?: number | null;
  p_cross_next_threshold?: number | null;
  p_cross_85?: number | null;
  p_cross_90?: number | null;
  confidence?: number | null;
  upgrade_score?: number | null;
  reason_codes?: string[];
};

export type ForecastResult = {
  status: string;
  diagnostic_only: boolean;
  direction?: string;
  expected_ret?: number | null;
  p_profit?: number | null;
  p5_ret?: number | null;
  p95_ret?: number | null;
  n_prices?: number;
  reason?: string;
  cone?: Array<{ step: number; p5?: number | null; p50?: number | null; p95?: number | null }>;
  horizons?: Array<Record<string, unknown>>;
  diagnostics?: Record<string, unknown>;
  walk_forward?: Record<string, unknown>;
  calibration?: { status?: string; bins?: Array<Record<string, unknown>> };
  gates?: { status?: string; failed?: string[]; failed_csv?: string; note?: string };
  tier?: string;
  verdict?: { status?: string; reason?: string };
};

export type CardRow = {
  uuid?: string;
  name?: string;
  rarity?: string;
  team?: string;
  team_short_name?: string;
  display_position?: string;
  series?: string;
  img?: string;
  baked_img?: string;
  current_ovr?: number | null;
  new_rank?: number | null;
  raw_ask?: number | null;
  raw_bid?: number | null;
  liquidity_score?: number | null;
  liquidity_n?: number | null;
  liquidity_recent?: number | null;
};

export type ScoreRecord = {
  uuid?: string;
  name?: string;
  status?: string;
  reason?: string;
  card?: CardRow & Record<string, unknown>;
  flip?: FlipResult;
  upgrade?: UpgradeResult;
  forecast?: ForecastResult;
  validation?: Record<string, unknown>;
  decision_channels?: Record<string, string>;
  fetched_at?: string;
  source_url?: string;
  raw_bid?: number | null;
  raw_ask?: number | null;
  after_tax_sale?: number | null;
  flip_profit?: number | null;
  flip_roi?: number | null;
  spread_pct?: number | null;
  ovr?: number | null;
  new_rank?: number | null;
  next_threshold?: number | null;
  distance_to_threshold?: number | null;
  distance_to_85?: number | null;
  distance_to_90?: number | null;
  p_upgrade?: number | null;
  p_downgrade?: number | null;
  p_cross_next_threshold?: number | null;
  p_cross_85?: number | null;
  p_cross_90?: number | null;
  upgrade_confidence?: number | null;
  upgrade_score?: number | null;
  flip_action?: string;
  upgrade_action?: string;
  forecast_direction?: string;
  forecast_ev_7d?: number | null;
  flip_reason_codes?: string;
  upgrade_reason_codes?: string;
  gates_failed_csv?: string;
  scan_status?: string;
  verdict_status?: string;
  tier?: string;
  scan_index?: number;
  scan_total?: number;
};

export type ScanResponse = {
  uuid_parse: {
    uuids: string[];
    duplicates: string[];
    invalid_tokens: string[];
    raw_count: number;
  };
  mode?: string;
  rarity?: string;
  top_n?: number;
  discovered?: TopListingsResponse | null;
  progress?: {
    total: number;
    completed: number;
    current_uuid?: string | null;
    current_name?: string | null;
    dropped_count?: number;
    invalid_count?: number;
    status?: string;
    elapsed_seconds?: number;
    rate_limit_message: string;
  };
  records: ScoreRecord[];
  partitions: Record<"flip_buys" | "upgrade_buys" | "holds" | "sells" | "dropped", ScoreRecord[]>;
  counts: Record<string, number>;
  tier_distribution?: Record<string, number>;
  market_health?: Record<string, number | null>;
  dropped_summary?: Record<string, number>;
};

export type ScanJob = {
  job_id: string;
  status: "queued" | "running" | "complete" | "error";
  total: number;
  completed: number;
  current_uuid?: string | null;
  current_name?: string | null;
  dropped_count: number;
  invalid_count: number;
  started_at: string;
  updated_at: string;
  completed_at?: string | null;
  elapsed_seconds?: number | null;
  rate_limit_message?: string;
  result?: ScanResponse | null;
  error?: string | null;
};

export type SearchListing = {
  listing_name?: string;
  best_sell_price?: number;
  best_buy_price?: number;
  fetched_at?: string;
  item?: CardRow & {
    ovr?: number;
    uuid?: string;
    name?: string;
  };
  search?: {
    normalized_query: string;
    normalized_name: string;
    exact_name_match: boolean;
    partial_name_match: boolean;
    match_score: number;
  };
};

export type SearchResponse = {
  query?: string;
  normalized_query?: string;
  listings: SearchListing[];
  year?: number;
  source_url?: string;
  fetched_at?: string;
};

export type TopListingsResponse = {
  rarity: string;
  top_n: number;
  listings: SearchListing[];
  uuids: string[];
  year?: number;
  source_url?: string;
  fetched_at?: string;
};

export type SessionSummary = {
  status: string;
  server_time: string;
  started_at: string;
  runtime_seconds: number;
  runtime_writes: string;
  historical_data: string;
};

export type ParityAudit = {
  status: string;
  generated_at: string;
  counts: Record<string, number>;
  features: Array<Record<string, unknown>>;
};

export type MLBStatsResponse = {
  recent: Record<string, unknown>;
  season: Record<string, unknown>;
  role: "hitter" | "pitcher";
  player: null | {
    id: number;
    full_name: string;
    primary_position?: string;
    primary_position_code?: string;
  };
  recent_start?: string;
  season_start?: string;
  end?: string;
  source?: string;
};
