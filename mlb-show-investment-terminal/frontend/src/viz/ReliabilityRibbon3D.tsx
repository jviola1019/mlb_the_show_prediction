import { Canvas } from "@react-three/fiber";
import { Line, OrbitControls, Text } from "@react-three/drei";
import { useMemo } from "react";
import type { CalibrationBin } from "../types";

/**
 * 3D reliability ribbon for the VALIDATE tab.
 *
 * Maps each calibration bin to a 3D bar (mean_pred -> observed_rate, depth
 * encoding bin sample count). A 45-degree reference plane shows perfect
 * calibration; bars above the plane are over-confident, bars below are
 * under-confident.
 */

function isFinite(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

export function ReliabilityRibbon3D({
  bins,
  height = 280,
}: {
  bins: CalibrationBin[] | undefined;
  height?: number;
}) {
  const usable = useMemo(
    () => (bins ?? []).filter((b) => isFinite(b.mean_pred) && isFinite(b.observed_rate)),
    [bins],
  );

  const bars = useMemo(() => {
    if (!usable.length) return [];
    const maxN = Math.max(...usable.map((b) => b.n || 1));
    return usable.map((b) => {
      const x = ((b.mean_pred as number) - 0.5) * 4;
      const y = ((b.observed_rate as number) - 0.5) * 4;
      const z = ((b.n || 0) / Math.max(1, maxN)) * 1.2;
      return { x, y, z, predicted: b.mean_pred as number, observed: b.observed_rate as number, n: b.n };
    });
  }, [usable]);

  if (!bars.length) {
    return (
      <div className="empty" style={{ height }}>
        No reliable calibration bins (need at least 5 non-empty bins).
      </div>
    );
  }

  // Reference diagonal: perfect calibration plane (predicted == observed).
  const refLine: [number, number, number][] = [
    [-2, -2, 0],
    [2, 2, 0],
  ];

  return (
    <div className="reliability-ribbon-3d" style={{ height, position: "relative" }}>
      <Canvas camera={{ position: [3.2, 2.4, 4.5], fov: 38 }} dpr={[1, 2]}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[4, 4, 4]} intensity={0.8} />
        <gridHelper args={[5, 10, "#1f2937", "#0f1d2b"]} position={[0, 0, 0]} rotation={[Math.PI / 2, 0, 0]} />
        <Line points={refLine} color="#94a3b8" lineWidth={1.5} dashed dashScale={4} />
        {bars.map((bar, idx) => (
          <group key={idx} position={[bar.x, bar.y, bar.z / 2]}>
            <mesh>
              <boxGeometry args={[0.32, 0.32, bar.z]} />
              <meshStandardMaterial
                color={Math.abs(bar.predicted - bar.observed) < 0.05 ? "#34d399" : "#fbbf24"}
                transparent
                opacity={0.85}
                roughness={0.4}
              />
            </mesh>
            <Text position={[0, 0, bar.z / 2 + 0.18]} fontSize={0.12} color="#cbd5e1">
              n={bar.n}
            </Text>
          </group>
        ))}
        <Text position={[-2.1, 2.2, 0]} fontSize={0.16} color="#9ca3af">
          observed
        </Text>
        <Text position={[2.1, -2.3, 0]} fontSize={0.16} color="#9ca3af">
          predicted
        </Text>
        <OrbitControls enablePan={false} enableZoom={true} />
      </Canvas>
    </div>
  );
}

export default ReliabilityRibbon3D;
