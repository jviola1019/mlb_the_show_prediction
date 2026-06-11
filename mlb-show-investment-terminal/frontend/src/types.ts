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

export type DecisionResult = {
  action: string;
  responsible_channel: "flip" | "upgrade" | "forecast" | "data_quality" | "invalid" | string;
  reason_codes?: string[];
  reason_codes_csv?: string;
  blockers?: string[];
  blockers_csv?: string;
  formula_inputs?: Record<string, unknown>;
  confidence?: number | null;
  model_status?: string;
  probability_kind?: string;
  explanation?: string;
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
  model_status?: string;
  probability_kind?: string;
  probability_note?: string;
  reason_codes?: string[];
};

export type VerdictStatus = "INVESTABLE" | "OBSERVATIONAL ONLY" | "NOT INVESTABLE";

export type Verdict = {
  status: VerdictStatus;
  headline?: string;
  badge_tone?: "bull" | "warn" | "bear";
  reasons?: string[];
  failed?: string[];
  failed_csv?: string;
};

export type GatePill = {
  key: string;
  label: string;
  tone: "bull" | "bear";
  mark: string;
  passed: boolean;
  reason: string;
};

export type CalibrationBin = {
  bin_lo: number;
  bin_hi: number;
  bin_mid: number;
  n: number;
  mean_pred: number | null;
  observed_rate: number | null;
};

export type ForecastResult = {
  status: string;
  diagnostic_only: boolean;
  direction?: string;
  expected_ret?: number | null;
  p_profit?: number | null;
  p5_ret?: number | null;
  p50_ret?: number | null;
  p95_ret?: number | null;
  n_prices?: number;
  tax_rate?: number;
  formula?: {
    price_basis?: string;
    current_price?: number | null;
    ask?: number | null;
    bid?: number | null;
    spread_ratio?: number | null;
    tax_rate?: number | null;
    return_formula?: string;
    note?: string;
  };
  block_length?: number;
  reason?: string;
  cone?: Array<{ step: number; p5?: number | null; p50?: number | null; p95?: number | null }>;
  horizons?: Array<Record<string, unknown>>;
  diagnostics?: Record<string, unknown>;
  walk_forward?: Record<string, unknown>;
  calibration?: { status?: string; bins?: CalibrationBin[] };
  gates?: Record<string, { passed: boolean; reason: string }>;
  gate_pills?: GatePill[];
  tier?: string;
  verdict?: Verdict;
};

export type StrategyBlock = {
  rule_version?: string;
  flip?: {
    verdict?: string;
    raw_ask?: number | null;
    raw_bid?: number | null;
    after_tax_resale_value?: number | null;
    expected_net_stubs?: number | null;
    expected_roi_after_tax_and_friction?: number | null;
    p_successful_exit?: number | null;
    expected_holding_time_hours?: number | null;
    worst_case_liquidation_value?: number | null;
    action?: string;
    reason_codes?: string[];
    gates_passed?: string[];
    gates_failed?: string[];
  };
  directional?: {
    verdict?: string;
    investable_label?: string | null;
    expected_return_by_horizon?: Record<string, number | null>;
    p_up?: number | null;
    p_down?: number | null;
    p_profit?: number | null;
    prediction_interval?: Record<string, number | null>;
    quantile_forecasts?: Record<string, number | null>;
    forecast_cone?: Array<Record<string, unknown>>;
    model_confidence?: number | null;
    validation_tier?: string;
    data_coverage_tier?: string;
    performance_validation_tier?: string;
    recommended_holding_horizon?: string;
    holding_instruction?: string;
    source_verdict?: string | null;
    reason_codes?: string[];
    gates_passed?: string[];
    gates_failed?: string[];
  };
  inventory?: {
    verdict?: string;
    inventory_risk_score?: number | null;
    expected_exit_time_hours?: number | null;
    liquidity_score?: number | null;
    liquidity_recent?: number | null;
    dead_inventory_warning?: string | null;
    position_size_recommendation?: string;
    max_position_stubs?: number;
    reason_codes?: string[];
    gates_passed?: string[];
    gates_failed?: string[];
  };
  composite?: {
    final_action?: string;
    strategy_type?: string;
    investable_label?: string | null;
    hold_duration?: string;
    holding_instruction?: string;
    entry_timing?: string;
    exit_timing?: string;
    max_hold_hours?: number | null;
    explanation?: string;
    gates_passed?: string[];
    gates_failed?: string[];
    reason_codes?: string[];
    confidence?: number | null;
  };
};

export type Provenance = {
  source?: string;
  source_url?: string | null;
  listing_timestamp?: string | null;
  pull_timestamp?: string | null;
  api_response_timestamp?: string | null;
  data_freshness?: string;
  sample_size?: number | null;
  validation_tier?: string | null;
  data_coverage_tier?: string | null;
  performance_validation_tier?: string | null;
  raw_data_hash?: string;
  model_version?: string;
  rule_version?: string;
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
  decision?: DecisionResult;
  strategy?: StrategyBlock;
  provenance?: Provenance;
  fetched_at?: string;
  source_url?: string;
  rarity?: string;
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
  liquidity_score?: number | null;
  liquidity_n?: number | null;
  liquidity_recent?: number | null;
  flip_action?: string;
  upgrade_action?: string;
  forecast_direction?: string;
  forecast_ev_7d?: number | null;
  forecast_formula?: string | null;
  flip_reason_codes?: string;
  upgrade_reason_codes?: string;
  decision_action?: string;
  final_action?: string;
  strategy_type?: string;
  flip_verdict?: string;
  directional_verdict?: string;
  inventory_verdict?: string;
  holding_horizon?: string;
  holding_instruction?: string;
  entry_timing?: string;
  exit_timing?: string;
  max_hold_hours?: number | null;
  investable_label?: string | null;
  inventory_risk_score?: number | null;
  expected_exit_time_hours?: number | null;
  responsible_channel?: string;
  decision_reason_codes?: string;
  decision_blockers?: string;
  model_status?: string;
  probability_kind?: string;
  gates_failed_csv?: string;
  scan_status?: string;
  verdict?: Verdict;
  verdict_status?: VerdictStatus | string;
  decision_tier?: string;
  validation_tier?: string;
  data_coverage_tier?: string;
  performance_validation_tier?: string;
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
  partitions: Record<"flip_buys" | "upgrade_buys" | "watch" | "holds" | "sells" | "no_trade" | "observational" | "dropped", ScoreRecord[]>;
  counts: Record<string, number>;
  tier_distribution?: Record<string, number>;
  rarity_distribution?: Record<string, number>;
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
  runtime_writes: string | Record<string, unknown>;
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
