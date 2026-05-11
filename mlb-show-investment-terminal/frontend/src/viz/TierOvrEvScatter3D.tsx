import { useEffect, useMemo, useRef } from "react";
import type { ScoreRecord } from "../types";

/**
 * 3D scatter for the OVERALL tab: OVR x tier x expected_return.
 *
 * Encodes verdict status as point color so the user can see at a glance which
 * cards passed the 7-gate governance vs which were demoted to OBSERVATIONAL.
 * NOT INVESTABLE records are excluded entirely (they're already in the dropped
 * partition).
 */

const TIER_AXIS: Record<string, number> = { BRONZE: 0, SILVER: 1, GOLD: 2, DIAMOND: 3, UNRATED: -1 };
const VERDICT_COLOR: Record<string, string> = {
  INVESTABLE: "#34d399",
  "OBSERVATIONAL ONLY": "#fbbf24",
  "NOT INVESTABLE": "#f87171",
};

export function TierOvrEvScatter3D({
  records,
  height = 320,
}: {
  records: ScoreRecord[];
  height?: number;
}) {
  const container = useRef<HTMLDivElement | null>(null);

  const data = useMemo(() => {
    return records
      .filter((r) => r.status !== "dropped")
      .map((r) => {
        const ovr = Number(r.ovr ?? r.upgrade?.current_ovr ?? 0);
        const tier = String(r.tier ?? r.forecast?.tier ?? "UNRATED");
        const ev = Number((r.forecast?.expected_ret ?? r.forecast_ev_7d ?? 0) * 100);
        const verdict = String(r.verdict?.status ?? r.verdict_status ?? "OBSERVATIONAL ONLY");
        return {
          name: r.name ?? r.uuid ?? "card",
          value: [ovr, TIER_AXIS[tier] ?? -1, ev, verdict, tier],
          itemStyle: { color: VERDICT_COLOR[verdict] ?? "#94a3b8" },
        };
      })
      .filter((p) => Number.isFinite(p.value[0]) && Number.isFinite(p.value[2]));
  }, [records]);

  useEffect(() => {
    if (!container.current || data.length === 0) return;
    let cancelled = false;
    let dispose: (() => void) | null = null;

    (async () => {
      const echarts = await import("echarts");
      await import("echarts-gl");
      if (cancelled || !container.current) return;
      const inst = echarts.init(container.current, undefined, { renderer: "canvas" });
      inst.setOption({
        backgroundColor: "transparent",
        tooltip: {
          formatter: (p: { name: string; value: [number, number, number, string, string] }) =>
            `${p.name}<br/>OVR ${p.value[0]} · ${p.value[4]} · EV ${p.value[2].toFixed(2)}%<br/>${p.value[3]}`,
        },
        xAxis3D: { type: "value", name: "OVR", min: 60, max: 99, axisLabel: { color: "#94a3b8" } },
        yAxis3D: {
          type: "category",
          name: "Tier",
          data: ["BRONZE", "SILVER", "GOLD", "DIAMOND"],
          axisLabel: { color: "#94a3b8" },
        },
        zAxis3D: { type: "value", name: "EV %", axisLabel: { color: "#94a3b8" } },
        grid3D: {
          viewControl: { projection: "perspective", autoRotate: false, distance: 200 },
          axisLine: { lineStyle: { color: "#1f2937" } },
          splitLine: { lineStyle: { color: "#0f1d2b" } },
          light: {
            main: { intensity: 1, shadow: false },
            ambient: { intensity: 0.4 },
          },
        },
        series: [
          {
            type: "scatter3D",
            symbolSize: 9,
            data,
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
        No scan records to plot.
      </div>
    );
  }

  return <div ref={container} className="tier-ovr-ev-3d" style={{ height, width: "100%" }} />;
}

export default TierOvrEvScatter3D;
