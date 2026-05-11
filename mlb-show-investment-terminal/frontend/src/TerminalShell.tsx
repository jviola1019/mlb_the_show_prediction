import { Activity, BarChart3, CheckCircle2, FileText, Gauge, Search } from "lucide-react";
import { motion } from "motion/react";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { BootScreen } from "./BootScreen";
import { Pill } from "./components";

const TerminalBackdrop = lazy(() => import("./TerminalBackdrop"));

export type Tab = "overall" | "card" | "ovr" | "scan" | "validate" | "method";

const tabs: Array<{ id: Tab; label: string; icon: typeof Activity }> = [
  { id: "overall", label: "Overall", icon: Gauge },
  { id: "card", label: "Card Analysis", icon: Search },
  { id: "ovr", label: "OVR Predictor", icon: Activity },
  { id: "scan", label: "Market Scan", icon: BarChart3 },
  { id: "validate", label: "Validate", icon: CheckCircle2 },
  { id: "method", label: "Method", icon: FileText }
];

export function TerminalShell({ active, setActive, children }: { active: Tab; setActive: (tab: Tab) => void; children: ReactNode }) {
  const [booting, setBooting] = useState(true);
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
            <span className="title-glyph">◢◤</span>
            <div>
              <div className="eyebrow">PYTHON QUANT OWNER</div>
              <h1>MLB The Show 26 Investment Terminal</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <Pill tone="info">React parity build</Pill>
            <Pill>v1.2.0</Pill>
          </div>
        </header>
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
          initial={{ opacity: 0, y: 8, filter: "blur(2px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.22, ease: [0.2, 0.6, 0.2, 1] }}
        >
          {children}
        </motion.main>
      </div>
    </>
  );
}
