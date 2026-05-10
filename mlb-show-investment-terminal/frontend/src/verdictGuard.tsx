import { AlertOctagon, Eye } from "lucide-react";
import type { ReactNode } from "react";
import type { ScoreRecord, Verdict, VerdictStatus } from "./types";

/**
 * Shared governance guard.
 *
 * The 7-gate Python governance system (governance.py) is the single source
 * of truth for whether a card should render its full forecast/EV/Kelly UI.
 * Every visualization in the app must accept the verdict status and degrade:
 *   - INVESTABLE         -> full render
 *   - OBSERVATIONAL ONLY -> render direction only; suppress Kelly/EV; amber tone
 *   - NOT INVESTABLE     -> render BlockedPlaceholder with failed-gate reasons
 */

export function verdictOf(record: ScoreRecord | null | undefined): VerdictStatus {
  if (!record) return "NOT INVESTABLE";
  const v = record.verdict?.status ?? record.forecast?.verdict?.status ?? record.verdict_status;
  if (v === "INVESTABLE" || v === "OBSERVATIONAL ONLY" || v === "NOT INVESTABLE") {
    return v;
  }
  // No verdict block -> treat as observational (row-only scan) rather than blocked.
  return "OBSERVATIONAL ONLY";
}

export function isInvestable(record: ScoreRecord | null | undefined): boolean {
  return verdictOf(record) === "INVESTABLE";
}

export function isBlocked(record: ScoreRecord | null | undefined): boolean {
  return verdictOf(record) === "NOT INVESTABLE";
}

export function isObservational(record: ScoreRecord | null | undefined): boolean {
  return verdictOf(record) === "OBSERVATIONAL ONLY";
}

export function blankIf<T>(record: ScoreRecord | null | undefined, value: T): T | string {
  return isInvestable(record) ? value : "—";
}

function verdictMeta(status: VerdictStatus): { tone: string; label: string; icon: ReactNode } {
  if (status === "INVESTABLE") {
    return { tone: "bull", label: "INVESTABLE", icon: null };
  }
  if (status === "OBSERVATIONAL ONLY") {
    return {
      tone: "warn",
      label: "OBSERVATIONAL ONLY",
      icon: <Eye size={14} aria-hidden />,
    };
  }
  return {
    tone: "bear",
    label: "NOT INVESTABLE",
    icon: <AlertOctagon size={14} aria-hidden />,
  };
}

export function VerdictBanner({ record }: { record: ScoreRecord | null | undefined }) {
  const status = verdictOf(record);
  const verdict: Verdict | undefined = record?.verdict ?? record?.forecast?.verdict;
  const meta = verdictMeta(status);
  const headline = verdict?.headline ?? meta.label;
  const reasons = verdict?.reasons ?? [];
  return (
    <div className={`verdict-banner verdict-${meta.tone}`} role="status">
      <div className="verdict-banner-head">
        {meta.icon}
        <span className="verdict-banner-label">{headline}</span>
      </div>
      {reasons.length ? (
        <ul className="verdict-banner-reasons">
          {reasons.map((r, idx) => (
            <li key={idx}>{r}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function BlockedPlaceholder({
  reasons,
  title = "BLOCKED · GATE FAILURE",
}: {
  reasons?: string[];
  title?: string;
}) {
  return (
    <div className="blocked-placeholder" role="alert">
      <div className="blocked-placeholder-head">
        <AlertOctagon size={18} aria-hidden />
        <span>{title}</span>
      </div>
      <p className="muted">
        Forecast suppressed. The 7-gate governance system failed on one or more hard gates;
        showing this view would overstate confidence.
      </p>
      {reasons?.length ? (
        <ul className="blocked-placeholder-reasons">
          {reasons.map((r, idx) => (
            <li key={idx}>{r}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function ObservationalOverlay({ children }: { children: ReactNode }) {
  return (
    <div className="observational-overlay" role="group" aria-label="Directional only — no action verb">
      <div className="observational-watermark">DIRECTIONAL ONLY</div>
      <div className="observational-content">{children}</div>
    </div>
  );
}

export function GuardedVisual({
  record,
  children,
  blockedTitle,
}: {
  record: ScoreRecord | null | undefined;
  children: ReactNode;
  blockedTitle?: string;
}) {
  const status = verdictOf(record);
  const verdict: Verdict | undefined = record?.verdict ?? record?.forecast?.verdict;
  if (status === "NOT INVESTABLE") {
    return <BlockedPlaceholder reasons={verdict?.reasons} title={blockedTitle} />;
  }
  if (status === "OBSERVATIONAL ONLY") {
    return <ObservationalOverlay>{children}</ObservationalOverlay>;
  }
  return <>{children}</>;
}
