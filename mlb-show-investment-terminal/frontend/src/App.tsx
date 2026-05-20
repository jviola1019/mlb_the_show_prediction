import { lazy, Suspense, useMemo, useState } from "react";
import type { TerminalContext, TerminalSessionState } from "./appState";
import { TerminalShell, type Tab } from "./TerminalShell";
import type { ScanResponse, ScoreRecord, SearchResponse } from "./types";

const nowIso = () => new Date().toISOString();
const CommandCenterTab = lazy(() => import("./tabs/OverallTab").then((m) => ({ default: m.OverallTab })));
const MarketScannerTab = lazy(() => import("./tabs/ScanTab").then((m) => ({ default: m.ScanTab })));
const TargetTradeTicketTab = lazy(() => import("./tabs/CardTab").then((m) => ({ default: m.CardTab })));
const StrategyMatrixTab = lazy(() => import("./tabs/TerminalTabs").then((m) => ({ default: m.StrategyMatrixTab })));
const ForecastLabTab = lazy(() => import("./tabs/TerminalTabs").then((m) => ({ default: m.ForecastLabTab })));
const BacktestingValidationTab = lazy(() => import("./tabs/ValidateTab").then((m) => ({ default: m.ValidateTab })));
const ExecutionLedgerTab = lazy(() => import("./tabs/TerminalTabs").then((m) => ({ default: m.ExecutionLedgerTab })));
const RiskInventoryTab = lazy(() => import("./tabs/TerminalTabs").then((m) => ({ default: m.RiskInventoryTab })));
const DataAuditTab = lazy(() => import("./tabs/TerminalTabs").then((m) => ({ default: m.DataAuditTab })));
const OperationsTab = lazy(() => import("./tabs/MethodTab").then((m) => ({ default: m.MethodTab })));

export default function App() {
  const [active, setActive] = useState<Tab>("command");
  const [state, setState] = useState<TerminalSessionState>({ loadedUuids: [] });

  const ctx = useMemo<TerminalContext>(() => ({
    ...state,
    addLoadedUuid: (uuid: string) => setState((prev) => {
      const clean = uuid.trim().toLowerCase();
      if (!clean || prev.loadedUuids.includes(clean)) return prev;
      return { ...prev, loadedUuids: [...prev.loadedUuids, clean] };
    }),
    setCurrentRecord: (record: ScoreRecord) => setState((prev) => ({
      ...prev,
      currentRecord: record,
      lastListingAt: record.fetched_at || record.provenance?.pull_timestamp || nowIso(),
    })),
    setLastSearch: (payload: SearchResponse) => setState((prev) => ({
      ...prev,
      lastSearch: payload,
      lastSearchAt: payload.fetched_at || nowIso(),
    })),
    setLastScan: (payload: ScanResponse) => setState((prev) => ({
      ...prev,
      lastScan: payload,
      lastScanAt: nowIso(),
    })),
    markApiOk: () => setState((prev) => ({ ...prev, apiOkAt: nowIso() })),
    markApiErr: () => setState((prev) => ({ ...prev, apiErrAt: nowIso() })),
    openTab: (tab) => setActive(tab),
  }), [state]);

  const body = {
    command: <CommandCenterTab ctx={ctx} />,
    scanner: <MarketScannerTab ctx={ctx} />,
    target: <TargetTradeTicketTab ctx={ctx} />,
    matrix: <StrategyMatrixTab ctx={ctx} />,
    forecast: <ForecastLabTab ctx={ctx} />,
    validation: <BacktestingValidationTab ctx={ctx} />,
    ledger: <ExecutionLedgerTab ctx={ctx} />,
    risk: <RiskInventoryTab ctx={ctx} />,
    audit: <DataAuditTab ctx={ctx} />,
    ops: <OperationsTab />,
  }[active];

  return (
    <TerminalShell active={active} setActive={setActive}>
      <Suspense fallback={<div className="panel"><div className="empty">Loading tab...</div></div>}>
        {body}
      </Suspense>
    </TerminalShell>
  );
}
