import { lazy, Suspense, useMemo, useState } from "react";
import type { TerminalContext, TerminalSessionState } from "./appState";
import { TerminalShell, type Tab } from "./TerminalShell";
import type { ScanResponse, ScoreRecord, SearchResponse } from "./types";

const nowIso = () => new Date().toISOString();
const OverallTab = lazy(() => import("./tabs/OverallTab").then((m) => ({ default: m.OverallTab })));
const CardTab = lazy(() => import("./tabs/CardTab").then((m) => ({ default: m.CardTab })));
const OvrTab = lazy(() => import("./tabs/OvrTab").then((m) => ({ default: m.OvrTab })));
const ScanTab = lazy(() => import("./tabs/ScanTab").then((m) => ({ default: m.ScanTab })));
const ValidateTab = lazy(() => import("./tabs/ValidateTab").then((m) => ({ default: m.ValidateTab })));
const MethodTab = lazy(() => import("./tabs/MethodTab").then((m) => ({ default: m.MethodTab })));

export default function App() {
  const [active, setActive] = useState<Tab>("overall");
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
      lastListingAt: record.fetched_at || nowIso()
    })),
    setLastSearch: (payload: SearchResponse) => setState((prev) => ({
      ...prev,
      lastSearch: payload,
      lastSearchAt: payload.fetched_at || nowIso()
    })),
    setLastScan: (payload: ScanResponse) => setState((prev) => ({
      ...prev,
      lastScan: payload,
      lastScanAt: nowIso()
    })),
    markApiOk: () => setState((prev) => ({ ...prev, apiOkAt: nowIso() })),
    markApiErr: () => setState((prev) => ({ ...prev, apiErrAt: nowIso() })),
    openTab: (tab) => setActive(tab)
  }), [state]);

  const body = {
    overall: <OverallTab ctx={ctx} />,
    card: <CardTab ctx={ctx} />,
    ovr: <OvrTab ctx={ctx} />,
    scan: <ScanTab ctx={ctx} />,
    validate: <ValidateTab ctx={ctx} />,
    method: <MethodTab />
  }[active];

  return (
    <TerminalShell active={active} setActive={setActive}>
      <Suspense fallback={<div className="panel"><div className="empty">Loading tab...</div></div>}>
        {body}
      </Suspense>
    </TerminalShell>
  );
}
