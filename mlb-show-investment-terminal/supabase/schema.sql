-- Supabase/Postgres schema for the MLB Show Investment Terminal.
-- Apply manually in Supabase SQL editor or with psql against SUPABASE_DB_URL.

create table if not exists market_snapshots (
  id bigserial primary key,
  card_uuid text not null,
  card_name text,
  rarity text,
  team text,
  position text,
  raw_ask numeric,
  raw_bid numeric,
  source_url text,
  source_timestamp timestamptz,
  pulled_at timestamptz not null default now(),
  raw_hash text not null,
  strategy jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (card_uuid, raw_hash)
);

create table if not exists execution_ledger (
  id bigserial primary key,
  card_uuid text not null,
  card_name text,
  strategy_type text not null,
  buy_price numeric not null,
  sell_price numeric,
  exit_price numeric,
  tax numeric default 0.10,
  slippage numeric default 0,
  fill_status text,
  time_to_fill_minutes numeric,
  holding_time_hours numeric,
  expected_net_stubs numeric,
  model_prediction jsonb not null default '{}'::jsonb,
  validation jsonb not null default '{}'::jsonb,
  timestamp timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists model_predictions (
  id bigserial primary key,
  card_uuid text not null,
  prediction_timestamp timestamptz not null,
  final_action text not null,
  strategy jsonb not null,
  provenance jsonb not null default '{}'::jsonb,
  raw_hash text not null,
  realized_ledger_id bigint references execution_ledger(id),
  created_at timestamptz not null default now(),
  unique (card_uuid, raw_hash)
);

create table if not exists validation_runs (
  id bigserial primary key,
  run_timestamp timestamptz not null default now(),
  validation_tier text not null,
  data_coverage_tier text not null default 'UNVALIDATED',
  performance_validation_tier text not null default 'UNVALIDATED',
  sample_size integer not null default 0,
  horizons jsonb not null default '{}'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  baselines jsonb not null default '{}'::jsonb,
  verdict text not null default 'INSUFFICIENT DATA',
  created_at timestamptz not null default now()
);

create table if not exists audit_events (
  id bigserial primary key,
  event_timestamp timestamptz not null default now(),
  event_type text not null,
  severity text not null default 'info',
  card_uuid text,
  payload jsonb not null default '{}'::jsonb,
  app_version text,
  git_commit text,
  created_at timestamptz not null default now()
);

create index if not exists idx_market_snapshots_card_time on market_snapshots(card_uuid, pulled_at desc);
create index if not exists idx_model_predictions_card_time on model_predictions(card_uuid, prediction_timestamp desc);
create index if not exists idx_execution_ledger_card_time on execution_ledger(card_uuid, timestamp desc);
create index if not exists idx_audit_events_type_time on audit_events(event_type, event_timestamp desc);
