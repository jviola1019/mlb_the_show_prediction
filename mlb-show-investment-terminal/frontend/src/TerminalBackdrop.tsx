import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function TerminalBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      preserveDrawingBuffer: true,
      powerPreference: "high-performance"
    });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 80);
    camera.position.set(0, 4.4, 9.2);

    const group = new THREE.Group();
    scene.add(group);

    const grid = new THREE.GridHelper(30, 46, 0x10b981, 0x15463b);
    grid.position.y = -1.7;
    group.add(grid);

    const pointCount = 420;
    const positions = new Float32Array(pointCount * 3);
    for (let i = 0; i < pointCount; i += 1) {
      const ix = i * 3;
      const x = (Math.random() - 0.5) * 28;
      const z = (Math.random() - 0.5) * 24;
      positions[ix] = x;
      positions[ix + 1] = Math.sin(x * 0.35) * 0.18 + Math.cos(z * 0.2) * 0.16 - 0.65;
      positions[ix + 2] = z;
    }
    const pointsGeometry = new THREE.BufferGeometry();
    pointsGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const points = new THREE.Points(
      pointsGeometry,
      new THREE.PointsMaterial({
        color: 0x10b981,
        size: 0.035,
        transparent: true,
        opacity: 0.72
      })
    );
    group.add(points);

    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.18 });
    for (let i = 0; i < 9; i += 1) {
      const curve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(-13, -1.2 + i * 0.08, -9 + i * 1.7),
        new THREE.Vector3(-5, -0.5 + Math.sin(i) * 0.4, -5 + i * 0.6),
        new THREE.Vector3(3, -0.2 + Math.cos(i) * 0.35, -2 + i * 0.3),
        new THREE.Vector3(13, -1.1 + i * 0.07, 6 + i * 0.3)
      ]);
      const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(80));
      group.add(new THREE.Line(geometry, lineMaterial));
    }

    const resize = () => {
      const { innerWidth: width, innerHeight: height } = window;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(1, height);
      camera.updateProjectionMatrix();
    };
    resize();
    window.addEventListener("resize", resize);

    let frame = 0;
    let raf = 0;
    let hidden = false;
    const onVisibility = () => { hidden = document.hidden; };
    document.addEventListener("visibilitychange", onVisibility);

    const render = () => {
      frame += 1;
      if (!hidden && !reduceMotion) {
        group.rotation.y = Math.sin(frame * 0.002) * 0.035;
        group.position.x = Math.sin(frame * 0.0015) * 0.15;
        points.rotation.y += 0.0009;
      }
      camera.lookAt(0, -0.9, 0);
      renderer.render(scene, camera);
      if (!reduceMotion) raf = window.requestAnimationFrame(render);
    };
    render();

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
      pointsGeometry.dispose();
      lineMaterial.dispose();
      grid.clear();
      renderer.dispose();
    };
  }, []);

  return <canvas ref={canvasRef} className="terminal-3d-canvas" aria-hidden="true" data-testid="terminal-3d-canvas" />;
}
