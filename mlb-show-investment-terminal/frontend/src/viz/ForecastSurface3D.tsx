import { Canvas, useFrame } from "@react-three/fiber";
import { Line, OrbitControls, Text } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { ScoreRecord } from "../types";
import { isInvestable } from "../verdictGuard";

/**
 * 3D forecast cone for the CARD tab.
 *
 * The cone block from the Python backend is `[{step, p5, p50, p95}]`. We
 * extrude two ribbons (lower p5..p50 and upper p50..p95) into a translucent
 * surface so the user reads variance and direction at a glance. Falls back to
 * the recharts 2D line chart (delegated up the tree via <GuardedVisual>) when
 * verdict isn't INVESTABLE.
 */

type ConePoint = { step: number; p5?: number | null; p50?: number | null; p95?: number | null };

function isFinite(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function buildSurface(cone: ConePoint[]): {
  geometry: THREE.BufferGeometry;
  bandGeometry: THREE.BufferGeometry;
  median: [number, number, number][];
  bounds: { xMin: number; xMax: number; yMin: number; yMax: number };
} | null {
  const points = cone.filter((p) => isFinite(p.p5) && isFinite(p.p50) && isFinite(p.p95));
  if (points.length < 2) return null;

  const yMin = Math.min(...points.map((p) => p.p5 as number));
  const yMax = Math.max(...points.map((p) => p.p95 as number));
  const xMin = points[0].step;
  const xMax = points[points.length - 1].step;
  const sx = (v: number) => ((v - xMin) / Math.max(1e-9, xMax - xMin)) * 5 - 2.5;
  const sy = (v: number) => ((v - yMin) / Math.max(1e-9, yMax - yMin)) * 2.5 - 1.25;

  // Top ribbon (p50..p95) and bottom ribbon (p5..p50) share the p50 edge.
  const positions: number[] = [];
  const colors: number[] = [];
  const bandPositions: number[] = [];

  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    const xa = sx(a.step);
    const xb = sx(b.step);
    const ya5 = sy(a.p5 as number);
    const ya50 = sy(a.p50 as number);
    const ya95 = sy(a.p95 as number);
    const yb5 = sy(b.p5 as number);
    const yb50 = sy(b.p50 as number);
    const yb95 = sy(b.p95 as number);

    // Upper band quad (median..p95) as two triangles
    positions.push(xa, ya50, 0, xb, yb50, 0, xb, yb95, 0);
    positions.push(xa, ya50, 0, xb, yb95, 0, xa, ya95, 0);
    for (let k = 0; k < 6; k++) colors.push(0.06, 0.74, 0.51); // emerald accent

    // Lower band quad (p5..median)
    positions.push(xa, ya5, 0, xb, yb5, 0, xb, yb50, 0);
    positions.push(xa, ya5, 0, xb, yb50, 0, xa, ya50, 0);
    for (let k = 0; k < 6; k++) colors.push(0.98, 0.74, 0.14); // amber accent

    // Outline band (top + bottom edges)
    bandPositions.push(xa, ya95, 0, xb, yb95, 0);
    bandPositions.push(xa, ya5, 0, xb, yb5, 0);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();

  const bandGeometry = new THREE.BufferGeometry();
  bandGeometry.setAttribute("position", new THREE.Float32BufferAttribute(bandPositions, 3));

  const median: [number, number, number][] = points.map((p) => [sx(p.step), sy(p.p50 as number), 0.01]);

  return { geometry, bandGeometry, median, bounds: { xMin, xMax, yMin, yMax } };
}

function Mesh({ geometry, bandGeometry, median }: { geometry: THREE.BufferGeometry; bandGeometry: THREE.BufferGeometry; median: [number, number, number][] }) {
  const meshRef = useRef<THREE.Mesh>(null);
  useFrame((_, dt) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += dt * 0.08;
      meshRef.current.rotation.x = -0.18;
    }
  });
  return (
    <mesh ref={meshRef}>
      <primitive object={geometry} attach="geometry" />
      <meshStandardMaterial
        vertexColors
        transparent
        opacity={0.55}
        side={THREE.DoubleSide}
        roughness={0.4}
        metalness={0.05}
      />
      <lineSegments>
        <primitive object={bandGeometry} attach="geometry" />
        <lineBasicMaterial color="#10b981" linewidth={1} transparent opacity={0.7} />
      </lineSegments>
      <Line points={median} color="#34d399" lineWidth={2} dashed={false} />
    </mesh>
  );
}

export function ForecastSurface3D({ record, height = 240 }: { record: ScoreRecord; height?: number }) {
  const cone = (record.forecast?.cone ?? []) as ConePoint[];
  const surface = useMemo(() => buildSurface(cone), [cone]);
  const investable = isInvestable(record);

  if (!surface || !investable) {
    // Defer to the 2D chart in CardTab when we don't have enough points OR
    // governance hasn't blessed the cone. CardTab already wraps this in
    // <GuardedVisual> so the visible fallback is handled upstream.
    return null;
  }

  return (
    <div className="forecast-surface-3d" style={{ height, position: "relative" }}>
      <Canvas
        camera={{ position: [0, 1.2, 5.2], fov: 38 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 2]}
      >
        <ambientLight intensity={0.55} />
        <directionalLight position={[3, 4, 5]} intensity={0.8} />
        <Mesh geometry={surface.geometry} bandGeometry={surface.bandGeometry} median={surface.median} />
        <gridHelper args={[6, 12, "#1f2937", "#0f1d2b"]} position={[0, -1.6, 0]} />
        <Text position={[-2.7, 1.4, 0]} fontSize={0.18} color="#9ca3af">
          p95
        </Text>
        <Text position={[-2.7, -1.45, 0]} fontSize={0.18} color="#9ca3af">
          p5
        </Text>
        <Text position={[2.7, -1.7, 0]} fontSize={0.18} color="#9ca3af">
          horizon
        </Text>
        <OrbitControls
          enablePan={false}
          enableZoom={false}
          enableRotate={true}
          autoRotate={false}
        />
      </Canvas>
    </div>
  );
}

export default ForecastSurface3D;
