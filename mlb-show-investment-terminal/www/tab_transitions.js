/* tab_transitions.js — subtle fade-in on Bootstrap tab change.
 * Pure CSS animations live in theme.css; this script just re-triggers them. */
(function () {
  if (typeof document === "undefined") return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  document.addEventListener("shown.bs.tab", function (ev) {
    var pane = document.querySelector(ev.target.getAttribute("href") || "");
    if (!pane) return;
    var inner = pane.querySelector(".tab-panel");
    if (!inner) return;
    inner.style.animation = "none";
    /* trigger reflow */
    void inner.offsetWidth;
    inner.style.animation = "";
  });
})();
