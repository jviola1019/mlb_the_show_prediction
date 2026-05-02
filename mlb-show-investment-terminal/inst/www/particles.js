/* particles.js — emerald spark backdrop, GPU-friendly.
 * Disabled when prefers-reduced-motion or innerWidth < 480 (iPhone portrait).
 * Pauses when document.hidden to save battery. */
(function () {
  if (typeof window === "undefined") return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (window.innerWidth < 480) return;

  var canvas = document.createElement("canvas");
  canvas.id = "particle-canvas";
  Object.assign(canvas.style, {
    position: "fixed",
    inset: 0,
    width: "100%",
    height: "100%",
    pointerEvents: "none",
    zIndex: 0,
    mixBlendMode: "screen",
    opacity: 0.65
  });
  document.body.appendChild(canvas);
  var ctx = canvas.getContext("2d");
  var particles = [];
  var W = 0, H = 0;
  var dpr = Math.max(1, window.devicePixelRatio || 1);
  var paused = false;

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width  = W + "px";
    canvas.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener("resize", resize);

  for (var i = 0; i < 56; i++) {
    particles.push({
      x: Math.random() * W,
      y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.18,
      vy: (Math.random() - 0.5) * 0.18 - 0.04,
      r: Math.random() * 1.6 + 0.4,
      a: Math.random() * 0.6 + 0.3
    });
  }

  function tick() {
    if (paused) { requestAnimationFrame(tick); return; }
    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = "lighter";
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0)  p.x += W;
      if (p.x > W)  p.x -= W;
      if (p.y < 0)  p.y += H;
      if (p.y > H)  p.y -= H;
      var grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
      grad.addColorStop(0, "rgba(16,185,129," + p.a + ")");
      grad.addColorStop(1, "rgba(16,185,129,0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(tick);
  }
  document.addEventListener("visibilitychange", function () {
    paused = document.hidden;
  });
  requestAnimationFrame(tick);
})();
