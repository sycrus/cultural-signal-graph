/* Light / dark (#46). A classic script loaded in <head>, before the stylesheets apply,
   so the page never flashes the wrong theme. The choice is "system", "light" or
   "dark", remembered per browser; it sets data-theme on <html>, which tokens.css
   keys off. Same-origin frames (the Graph tab's Cytoscape page) follow via the
   storage event. Listen for the "csg-theme" window event to restyle canvas-drawn
   views; read a token with csgTheme.token("--name"). */
(function () {
  var KEY = "csg-theme";
  var ORDER = ["system", "light", "dark"];
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function pref() {
    try { return localStorage.getItem(KEY) || "system"; } catch (e) { return "system"; }
  }
  function resolved(p) {
    return p === "system" ? (mq && mq.matches ? "dark" : "light") : p;
  }
  function apply() {
    var t = resolved(pref());
    document.documentElement.setAttribute("data-theme", t);
    document.documentElement.setAttribute("data-theme-pref", pref()); // labels the switch
    window.dispatchEvent(new CustomEvent("csg-theme", { detail: t }));
  }
  function set(p) {
    try {
      if (p === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, p);
    } catch (e) { /* storage blocked: applies to this page only */ }
    apply();
  }
  function cycle() {
    set(ORDER[(ORDER.indexOf(pref()) + 1) % ORDER.length]);
  }

  if (mq && mq.addEventListener) mq.addEventListener("change", apply);
  window.addEventListener("storage", function (e) { if (e.key === KEY || e.key === null) apply(); });
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-theme-toggle]");
    if (b) cycle();
  });

  window.csgTheme = {
    pref: pref,
    set: set,
    cycle: cycle,
    current: function () { return resolved(pref()); },
    token: function (name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); },
  };
  apply();
})();
