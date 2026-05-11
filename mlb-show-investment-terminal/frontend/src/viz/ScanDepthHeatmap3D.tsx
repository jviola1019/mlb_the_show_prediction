import { useEffect, useMemo, useRef } from "react";
import type { ScoreRecord } from "../types";

/**
 * Order-book-style 3D depth heatmap for the MARKET SCAN tab.
 *
 * Inspired by bookmap / lob-regime-scanner: a 3D bar field of ROI x liquidity
 * across the scanned universe, colored by validation tier. The heatmap renders
 * final BUY decisions so forecast gates do not hide executable flip ROI.
 *
 * Uses echarts-gl via dynamic import so a fresh MARKET SCAN page that has no
 * data yet doesn't ship 420 KB of GL bundle to the user.
 */

const TIER_COLOR: Record<string, string> = {
  DIAMOND: "#67e8f9",
  GOLD: "#facc15",
  SILVER: "#cbd5e1",
  BRONZE: "#fb923c",
};

function tierIndex(t: string | undefined | null): number {
  switch (t) {
    case "DIAMOND":
      return 3;
    case "GOLD":
      return 2;
    case "SILVER":
      return 1;
    default:
      return 0;
  }
}

export function ScanDepthHeatmap3D({
  records,
  height = 360,
}: {
  records: ScoreRecord[];
  height?: number;
}) {
  const container = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<unknown>(null);

  // Build a 3D scatter dataset: x = OVR, y = liquidity_recent, z = ROI%
  const data = useMemo(() => {
    return records
      .filter((r) => {
        const action = r.decision?.action ?? r.decision_action;
        return action === "BUY FLIP" || action === "BUY SPECULATIVE";
      })
      .map((r) => {
        const ovr = Number(r.ovr ?? r.upgrade?.current_ovr ?? 0);
        const liq = Number(r.liquidity_recent ?? r.flip?.liquidity_recent ?? 0);
        const roi = Number((r.flip_roi ?? r.flip?.roi ?? 0) * 100);
        const tier = String(r.validation_tier ?? r.decision_tier ?? r.tier ?? r.forecast?.tier ?? "UNRATED");
        return {
          value: [ovr, liq, roi, tier],
          itemStyle: { color: TIER_COLOR[tier] ?? "#94a3b8" },
        };
      })
      .filter((p) => Number.isFinite(p.value[0]) && Number.isFinite(p.value[1]) && Number.isFinite(p.value[2]));
  }, [records]);

  useEffect(() => {
    if (!container.current || data.length === 0) {
      return;
    }
    let cancelled = false;
    let dispose: (() => void) | null = null;

    (async () => {
      const echarts = await import("echarts");
      await import("echarts-gl");
      if (cancelled || !container.current) return;
      const inst = echarts.init(container.current, undefined, { renderer: "canvas" });
      instanceRef.current = inst;
      inst.setOption({
        backgroundColor: "transparent",
        tooltip: {
          formatter: (p: { value: [number, number, number, string] }) =>
            `OVR ${p.value[0]} · LIQ ${p.value[1]} · ROI ${p.value[2].toFixed(2)}% · ${p.value[3]}`,
        },
        xAxis3D: { type: "value", name: "OVR", axisLabel: { color: "#94a3b8" } },
        yAxis3D: { type: "value", name: "LIQ (recent)", axisLabel: { color: "#94a3b8" } },
        zAxis3D: { type: "value", name: "ROI %", axisLabel: { color: "#94a3b8" } },
        grid3D: {
          viewControl: { projection: "perspective", autoRotate: true, autoRotateSpeed: 6, distance: 220 },
          axisLine: { lineStyle: { color: "#1f2937" } },
          splitLine: { lineStyle: { color: "#0f1d2b" } },
          axisPointer: { lineStyle: { color: "#10b981" } },
          environment: "auto",
          light: {
            main: { intensity: 1.05, shadow: false },
            ambient: { intensity: 0.35 },
          },
        },
        series: [
          {
            type: "scatter3D",
            symbolSize: (val: number[]) => 8 + Math.max(0, Math.min(18, val[2] / 1.5)),
            data,
            blendMode: "additive",
            emphasis: { itemStyle: { borderColor: "#fff", borderWidth: 1 } },
          },
        ],
      });

      const onResize = () => inst.resize();
      window.addEventListener("resize", onResize);
      dispose = () => {
        window.removeEventListener("resize", onResize);
        inst.dispose();
      };
    })();

    return () => {
      cancelled = true;
      if (dispose) dispose();
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <div className="empty" style={{ height }}>
        No INVESTABLE cards in this scan to plot.
      </div>
    );
  }

  return <div ref={container} className="scan-depth-3d" style={{ height, width: "100%" }} />;
}

export default ScanDepthHeatmap3D;
