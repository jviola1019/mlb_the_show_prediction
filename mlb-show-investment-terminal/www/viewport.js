/* viewport.js — broadcast innerWidth and self-dismiss the bootscreen. */
(function () {
  if (typeof window === "undefined") return;

  function hideBoot() {
    var el = document.getElementById("bootscreen");
    if (el && !el.classList.contains("done")) el.classList.add("done");
  }
  /* Hide as soon as Shiny reports it's connected. */
  document.addEventListener("shiny:connected", function () {
    setTimeout(hideBoot, 600);
  });
  /* Hard fallback: dismiss after 2.5s no matter what. */
  setTimeout(hideBoot, 2500);

  function send() {
    if (window.Shiny && Shiny.setInputValue) {
      Shiny.setInputValue("viewport_w", window.innerWidth,
                          { priority: "event" });
      Shiny.setInputValue("viewport_h", window.innerHeight,
                          { priority: "event" });
    }
  }
  window.addEventListener("load", send);
  document.addEventListener("shiny:connected", send);
  window.addEventListener("resize", function () {
    clearTimeout(window.__vpDebounce);
    window.__vpDebounce = setTimeout(send, 200);
  });
})();
