import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { CheckCircle2, Clock3, ExternalLink, ImageOff } from "lucide-react";
import type { ReactNode } from "react";
import type { CardRow, ScoreRecord, SearchListing, Tone } from "./types";

export function fmtPct(value: unknown, digits = 1): string {
  const n = Number(value);
  return Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : "-";
}

export function fmtNum(value: unknown, digits = 0): string {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }) : "-";
}

export function fmtStubs(value: unknown): string {
  const n = Number(value);
  return Number.isFinite(n) ? `${Math.round(n).toLocaleString("en-US")}s` : "-";
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "-";
  return dt.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function toneForAction(action?: string): Tone {
  if (!action) return "neutral";
  if (action.includes("BUY")) return "good";
  if (action.includes("SELL") || action.includes("AVOID")) return "bad";
  if (action.includes("WATCH") || action.includes("OBSERVE")) return "info";
  if (action.includes("NO TRADE")) return "warn";
  return "neutral";
}

export function Pill({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return <span className={`pill pill-${tone}`} title={title}>{children}</span>;
}

export function SignalPill({ action }: { action?: string }) {
  return <Pill tone={toneForAction(action)}>{action ?? "-"}</Pill>;
}

export function RarityPill({ rarity }: { rarity?: string | null }) {
  const lower = String(rarity ?? "").toLowerCase();
  const tone: Tone = lower.includes("diamond") ? "info" : lower.includes("gold") ? "warn" : "neutral";
  return <Pill tone={tone}>{rarity || "-"}</Pill>;
}

export function FreshnessBadge({ at, label = "FETCHED" }: { at?: string | null; label?: string }) {
  const ts = at ? new Date(at).getTime() : NaN;
  const ageHours = Number.isFinite(ts) ? (Date.now() - ts) / 36e5 : Infinity;
  const tone: Tone = ageHours < 1 ? "good" : ageHours < 24 ? "warn" : Number.isFinite(ageHours) ? "bad" : "neutral";
  return (
    <Pill tone={tone} title={at ?? undefined}>
      <Clock3 size={12} /> {label} {formatDateTime(at)}
    </Pill>
  );
}

export function Panel({ title, kicker, children, className = "" }: { title: string; kicker?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <h2>{title}</h2>
        {kicker ? <span>{kicker}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, tone = "neutral" }: { label: string; value: ReactNode; sub?: ReactNode; tone?: Tone }) {
  return (
    <div className={`stat stat-${tone}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub ? <div className="stat-sub">{sub}</div> : null}
    </div>
  );
}

export const MetricTile = Stat;

export function SectionHeader({ index, title }: { index: number | string; title: string }) {
  return (
    <div className="section-header">
      <span>{String(index).padStart(2, "0")}</span>
      <strong>{title}</strong>
    </div>
  );
}

export function ReasonCodes({ codes }: { codes?: string[] | string | null }) {
  const parts = Array.isArray(codes)
    ? codes
    : String(codes || "").split(",").map((x) => x.trim()).filter(Boolean);
  if (!parts.length) return <span className="empty">no reasons</span>;
  return <div className="reason-list">{parts.slice(0, 6).map((code) => <Pill key={code}>{code}</Pill>)}</div>;
}

export function DensityDots({ score }: { score?: number | null }) {
  const n = Number(score);
  const filled = Number.isFinite(n) ? Math.max(0, Math.min(5, Math.round(n * 5))) : 0;
  return (
    <div className="density-dots" title={`liquidity ${fmtPct(score, 0)}`}>
      {Array.from({ length: 5 }, (_, idx) => <span key={idx} className={idx < filled ? "on" : ""} />)}
    </div>
  );
}

export function HighlightedName({ name, query }: { name: string; query?: string }) {
  const q = String(query || "").trim();
  if (!q) return <>{name}</>;
  const idx = name.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return <>{name}</>;
  return (
    <>
      {name.slice(0, idx)}
      <mark>{name.slice(idx, idx + q.length)}</mark>
      {name.slice(idx + q.length)}
    </>
  );
}

function cardFromRecord(record: ScoreRecord): CardRow {
  return (record.card ?? {}) as CardRow;
}

export function CardIdentity({ record, compact = false }: { record: ScoreRecord; compact?: boolean }) {
  const card = cardFromRecord(record);
  const name = record.name || card.name || record.uuid || "-";
  const image = card.baked_img || card.img;
  return (
    <div className={`card-identity ${compact ? "compact" : ""}`}>
      <div className="card-art">
        {image ? <img src={image} alt="" /> : <ImageOff size={20} />}
      </div>
      <div className="card-meta">
        <strong>{name}</strong>
        <div>
          <RarityPill rarity={card.rarity} />
          <span>OVR {String(card.current_ovr ?? "-")}</span>
          <span>{card.team_short_name || card.team || "-"}</span>
          <span>{card.display_position || card.series || "-"}</span>
        </div>
      </div>
    </div>
  );
}

export function SearchResultRow({ listing, query, onLoad }: { listing: SearchListing; query?: string; onLoad: (uuid: string) => void }) {
  const item = listing.item ?? {};
  const uuid = String(item.uuid ?? "");
  const name = String(item.name ?? listing.listing_name ?? "-");
  const exact = Boolean(listing.search?.exact_name_match);
  return (
    <button className={`search-row ${exact ? "exact" : ""}`} onClick={() => uuid && onLoad(uuid)} disabled={!uuid}>
      <span className="search-name"><HighlightedName name={name} query={query} /></span>
      <RarityPill rarity={item.rarity} />
      <span>OVR {String(item.ovr ?? item.current_ovr ?? "-")}</span>
      <span>{item.team_short_name || item.team || "-"}</span>
      <span>{fmtStubs(listing.best_sell_price)}</span>
      <span className="match-score">{fmtPct(listing.search?.match_score, 0)}</span>
      {exact ? <CheckCircle2 size={14} className="exact-icon" /> : null}
    </button>
  );
}

const columns: ColumnDef<ScoreRecord>[] = [
  {
    header: "Player",
    cell: (ctx) => <CardIdentity record={ctx.row.original} compact />
  },
  { header: "OVR", accessorFn: (r) => String(cardFromRecord(r).current_ovr ?? "-") },
  { header: "Raw Bid", cell: (ctx) => fmtStubs(ctx.row.original.flip?.buy_price ?? cardFromRecord(ctx.row.original).raw_bid) },
  { header: "Raw Ask", cell: (ctx) => fmtStubs(ctx.row.original.flip?.sell_price ?? cardFromRecord(ctx.row.original).raw_ask) },
  { header: "After Tax", cell: (ctx) => fmtStubs(ctx.row.original.flip?.after_tax_sale) },
  { header: "Profit", cell: (ctx) => fmtStubs(ctx.row.original.flip?.profit) },
  { header: "ROI", cell: (ctx) => fmtPct(ctx.row.original.flip?.roi, 2) },
  { header: "Spread", cell: (ctx) => fmtPct(ctx.row.original.flip?.spread_pct, 1) },
  { header: "Liq", cell: (ctx) => <DensityDots score={ctx.row.original.flip?.liquidity_score ?? cardFromRecord(ctx.row.original).liquidity_score} /> },
  { header: "Flip", cell: (ctx) => <SignalPill action={ctx.row.original.flip?.action} /> },
  { header: "Upgrade", cell: (ctx) => <SignalPill action={ctx.row.original.upgrade?.action} /> },
  { header: "P(Cross)", cell: (ctx) => fmtPct(ctx.row.original.upgrade?.p_cross_next_threshold, 1) },
  { header: "Forecast", accessorFn: (r) => r.forecast?.direction ?? r.forecast?.status ?? "-" },
  { header: "Reasons", cell: (ctx) => <ReasonCodes codes={ctx.row.original.flip?.reason_codes ?? ctx.row.original.flip?.reason_codes_csv} /> }
];

export type ScanTableKind = "all" | "flip" | "upgrade" | "holds" | "sells" | "dropped";

function field<T>(record: ScoreRecord, key: keyof ScoreRecord, fallback?: T): T | unknown {
  const value = record[key];
  return value ?? fallback;
}

const scanColumns: Record<ScanTableKind, ColumnDef<ScoreRecord>[]> = {
  all: columns,
  flip: [
    { header: "Player", cell: (ctx) => <CardIdentity record={ctx.row.original} compact /> },
    { header: "OVR", accessorFn: (r) => String(field(r, "ovr", cardFromRecord(r).current_ovr) ?? "-") },
    { header: "Raw Bid", cell: (ctx) => fmtStubs(field(ctx.row.original, "raw_bid", ctx.row.original.flip?.buy_price)) },
    { header: "Raw Ask", cell: (ctx) => fmtStubs(field(ctx.row.original, "raw_ask", ctx.row.original.flip?.sell_price)) },
    { header: "After Tax", cell: (ctx) => fmtStubs(field(ctx.row.original, "after_tax_sale", ctx.row.original.flip?.after_tax_sale)) },
    { header: "Profit", cell: (ctx) => fmtStubs(field(ctx.row.original, "flip_profit", ctx.row.original.flip?.profit)) },
    { header: "ROI", cell: (ctx) => fmtPct(field(ctx.row.original, "flip_roi", ctx.row.original.flip?.roi), 2) },
    { header: "Spread", cell: (ctx) => fmtPct(field(ctx.row.original, "spread_pct", ctx.row.original.flip?.spread_pct), 1) },
    { header: "Liq", cell: (ctx) => <DensityDots score={ctx.row.original.flip?.liquidity_score ?? cardFromRecord(ctx.row.original).liquidity_score} /> },
    { header: "Forecast", accessorFn: (r) => String(r.forecast_direction ?? r.forecast?.direction ?? "-") },
    { header: "Flip Reasons", cell: (ctx) => <ReasonCodes codes={ctx.row.original.flip_reason_codes ?? ctx.row.original.flip?.reason_codes ?? ctx.row.original.flip?.reason_codes_csv} /> }
  ],
  upgrade: [
    { header: "Player", cell: (ctx) => <CardIdentity record={ctx.row.original} compact /> },
    { header: "OVR", accessorFn: (r) => String(field(r, "ovr", cardFromRecord(r).current_ovr) ?? "-") },
    { header: "New", accessorFn: (r) => String(r.new_rank ?? r.upgrade?.new_rank ?? "-") },
    { header: "Next", accessorFn: (r) => String(r.next_threshold ?? r.upgrade?.next_threshold ?? "-") },
    { header: "Dist", accessorFn: (r) => String(r.distance_to_threshold ?? r.upgrade?.distance_to_threshold ?? "-") },
    { header: "Dist 85", accessorFn: (r) => String(r.distance_to_85 ?? r.upgrade?.distance_to_85 ?? "-") },
    { header: "P(Cross)", cell: (ctx) => fmtPct(ctx.row.original.p_cross_next_threshold ?? ctx.row.original.upgrade?.p_cross_next_threshold, 1) },
    { header: "P(Up)", cell: (ctx) => fmtPct(ctx.row.original.p_upgrade ?? ctx.row.original.upgrade?.p_upgrade, 1) },
    { header: "P(Down)", cell: (ctx) => fmtPct(ctx.row.original.p_downgrade ?? ctx.row.original.upgrade?.p_downgrade, 1) },
    { header: "Conf", cell: (ctx) => fmtNum(ctx.row.original.upgrade_confidence ?? ctx.row.original.upgrade?.confidence, 0) },
    { header: "Score", cell: (ctx) => fmtNum(ctx.row.original.upgrade_score ?? ctx.row.original.upgrade?.upgrade_score, 0) },
    { header: "Upgrade", cell: (ctx) => <SignalPill action={ctx.row.original.upgrade_action ?? ctx.row.original.upgrade?.action} /> },
    { header: "Reasons", cell: (ctx) => <ReasonCodes codes={ctx.row.original.upgrade_reason_codes ?? ctx.row.original.upgrade?.reason_codes} /> }
  ],
  holds: [
    { header: "Player", cell: (ctx) => <CardIdentity record={ctx.row.original} compact /> },
    { header: "OVR", accessorFn: (r) => String(field(r, "ovr", cardFromRecord(r).current_ovr) ?? "-") },
    { header: "Flip", cell: (ctx) => <SignalPill action={ctx.row.original.flip_action ?? ctx.row.original.flip?.action} /> },
    { header: "Upgrade", cell: (ctx) => <SignalPill action={ctx.row.original.upgrade_action ?? ctx.row.original.upgrade?.action} /> },
    { header: "Forecast", accessorFn: (r) => String(r.forecast_direction ?? r.forecast?.direction ?? "-") },
    { header: "Forecast EV", cell: (ctx) => fmtPct(ctx.row.original.forecast_ev_7d ?? ctx.row.original.forecast?.expected_ret, 2) },
    { header: "ROI", cell: (ctx) => fmtPct(ctx.row.original.flip_roi ?? ctx.row.original.flip?.roi, 2) },
    { header: "Dist 85", accessorFn: (r) => String(r.distance_to_85 ?? r.upgrade?.distance_to_85 ?? "-") },
    { header: "P(Cross)", cell: (ctx) => fmtPct(ctx.row.original.p_cross_next_threshold ?? ctx.row.original.upgrade?.p_cross_next_threshold, 1) },
    { header: "Flip Reasons", cell: (ctx) => <ReasonCodes codes={ctx.row.original.flip_reason_codes ?? ctx.row.original.flip?.reason_codes} /> },
    { header: "Upgrade Reasons", cell: (ctx) => <ReasonCodes codes={ctx.row.original.upgrade_reason_codes ?? ctx.row.original.upgrade?.reason_codes} /> }
  ],
  sells: [
    { header: "Player", cell: (ctx) => <CardIdentity record={ctx.row.original} compact /> },
    { header: "OVR", accessorFn: (r) => String(field(r, "ovr", cardFromRecord(r).current_ovr) ?? "-") },
    { header: "Flip", cell: (ctx) => <SignalPill action={ctx.row.original.flip_action ?? ctx.row.original.flip?.action} /> },
    { header: "Upgrade", cell: (ctx) => <SignalPill action={ctx.row.original.upgrade_action ?? ctx.row.original.upgrade?.action} /> },
    { header: "ROI", cell: (ctx) => fmtPct(ctx.row.original.flip_roi ?? ctx.row.original.flip?.roi, 2) },
    { header: "P(Down)", cell: (ctx) => fmtPct(ctx.row.original.p_downgrade ?? ctx.row.original.upgrade?.p_downgrade, 1) },
    { header: "Forecast", accessorFn: (r) => String(r.forecast_direction ?? r.forecast?.direction ?? "-") },
    { header: "Flip Reasons", cell: (ctx) => <ReasonCodes codes={ctx.row.original.flip_reason_codes ?? ctx.row.original.flip?.reason_codes} /> },
    { header: "Upgrade Reasons", cell: (ctx) => <ReasonCodes codes={ctx.row.original.upgrade_reason_codes ?? ctx.row.original.upgrade?.reason_codes} /> }
  ],
  dropped: [
    { header: "UUID", cell: (ctx) => <code>{ctx.row.original.uuid ?? "-"}</code> },
    { header: "Player", accessorFn: (r) => r.name ?? "-" },
    { header: "Status", accessorFn: (r) => r.scan_status ?? r.status ?? "-" },
    { header: "Reason", accessorFn: (r) => r.reason ?? r.flip_reason_codes ?? "-" },
    { header: "Failed Gates", cell: (ctx) => <ReasonCodes codes={ctx.row.original.gates_failed_csv} /> }
  ]
};

export function RecordsTable({
  rows,
  kind = "all",
  onRowClick,
  selectedUuid
}: {
  rows: ScoreRecord[];
  kind?: ScanTableKind;
  onRowClick?: (record: ScoreRecord) => void;
  selectedUuid?: string;
}) {
  const table = useReactTable({ data: rows, columns: scanColumns[kind], getCoreRowModel: getCoreRowModel() });
  if (!rows.length) return <div className="empty">No rows.</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={`${onRowClick ? "clickable-row" : ""} ${selectedUuid && row.original.uuid === selectedUuid ? "selected-row" : ""}`}
              onClick={() => onRowClick?.(row.original)}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>
                  {cell.column.columnDef.cell
                    ? flexRender(cell.column.columnDef.cell, cell.getContext())
                    : String(cell.getValue() ?? "-")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SourceLink({ url }: { url?: string | null }) {
  if (!url) return null;
  return (
    <a className="source-link" href={url} target="_blank" rel="noreferrer">
      source <ExternalLink size={12} />
    </a>
  );
}
