import {
  BarChart3,
  BookOpen,
  ClipboardList,
  Database,
  FileText,
  Gauge,
  Grid3X3,
  Layers,
  Search,
  ShieldAlert,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import type { TerminalTab } from "./appState";
import { BootScreen } from "./BootScreen";
import { Pill } from "./components";

const TerminalBackdrop = lazy(() => import("./TerminalBackdrop"));

export type Tab = TerminalTab;

export const tabs: Array<{ id: Tab; label: string; icon: typeof Gauge }> = [
  { id: "command", label: "Command Center", icon: Gauge },
  { id: "scanner", label: "Market Scanner", icon: BarChart3 },
  { id: "target", label: "Trade Ticket", icon: Search },
  { id: "matrix", label: "Strategy Matrix", icon: Grid3X3 },
  { id: "forecast", label: "Forecast Lab", icon: Layers },
  { id: "validation", label: "Validation", icon: ShieldAlert },
  { id: "ledger", label: "Execution Ledger", icon: ClipboardList },
  { id: "risk", label: "Risk Inventory", icon: Database },
  { id: "audit", label: "Data Audit", icon: FileText },
  { id: "ops", label: "Operations", icon: BookOpen },
];

export function TerminalShell({
  active,
  setActive,
  children,
}: {
  active: Tab;
  setActive: (tab: Tab) => void;
  children: ReactNode;
}) {
  const [booting, setBooting] = useState(true);
  const reduceMotion = useReducedMotion();
  useEffect(() => {
    const id = window.setTimeout(() => setBooting(false), 1150);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <>
      <Suspense fallback={null}>
        <TerminalBackdrop />
      </Suspense>
      <div className="scanline-overlay" aria-hidden="true" />
      {booting ? <BootScreen /> : null}
      <div className="app">
        <header className="topbar">
          <div className="title-lockup">
            <span className="title-glyph">[+]</span>
            <div>
              <div className="eyebrow">PYTHON QUANT OWNER</div>
              <h1>MLB The Show 26 Investment Terminal</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <Pill tone="info">Strategy ontology build</Pill>
            <Pill>v1.3.0</Pill>
          </div>
        </header>

        <label className="mobile-tab-select">
          <span>Section</span>
          <select value={active} onChange={(event) => setActive(event.target.value as Tab)} aria-label="Terminal section">
            {tabs.map(({ id, label }) => <option key={id} value={id}>{label}</option>)}
          </select>
        </label>

        <nav className="tabs" aria-label="Terminal tabs">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button key={id} className={active === id ? "active" : ""} onClick={() => setActive(id)} aria-label={label}>
              <Icon size={15} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <motion.main
          key={active}
          initial={reduceMotion ? false : { opacity: 0, y: 8, filter: "blur(2px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: reduceMotion ? 0 : 0.22, ease: [0.2, 0.6, 0.2, 1] }}
        >
          {children}
        </motion.main>
      </div>
    </>
  );
}
