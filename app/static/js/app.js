/* Spendwise front-end helpers: theme, shortcuts, toasts, chart defaults. */
(function () {
  const root = document.documentElement;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;

  // ---- Theme toggle (persists to the user's profile) ----
  window.swToggleTheme = function () {
    const next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-bs-theme", next);
    document.dispatchEvent(new CustomEvent("sw:theme", { detail: next }));
    fetch("/settings/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({ theme: next }),
    }).catch(() => {});
  };

  // ---- Keyboard shortcuts: Ctrl/Cmd+K focuses search, N opens quick add ----
  document.addEventListener("keydown", (e) => {
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      document.getElementById("sw-search")?.focus();
    } else if (!typing && e.key.toLowerCase() === "n" && !e.ctrlKey && !e.metaKey) {
      const m = document.getElementById("quickAdd");
      if (m) bootstrap.Modal.getOrCreateInstance(m).show();
    }
  });

  // ---- Toasts auto-dismiss ----
  document.querySelectorAll(".sw-toast").forEach((t, i) => {
    setTimeout(() => {
      t.style.transition = "opacity .4s, transform .4s";
      t.style.opacity = "0";
      t.style.transform = "translateY(-8px)";
      setTimeout(() => t.remove(), 400);
    }, 4200 + i * 400);
  });

  // ---- Quick-add modal: focus amount when it opens ----
  document.getElementById("quickAdd")?.addEventListener("shown.bs.modal", () => {
    document.querySelector("#quickAdd input[name=amount]")?.focus();
  });

  // ---- Chart helpers shared by pages ----
  window.swChartTheme = function () {
    const dark = root.getAttribute("data-bs-theme") === "dark";
    return {
      mode: dark ? "dark" : "light",
      text: dark ? "#94a3b8" : "#64748b",
      grid: dark ? "#1f2937" : "#eef1f6",
    };
  };
  window.swCharts = [];
  window.swRegisterChart = function (build) {
    const chart = build(window.swChartTheme());
    chart.render();
    window.swCharts.push({ chart, build });
  };
  document.addEventListener("sw:theme", () => {
    window.swCharts.forEach((c) => {
      const t = window.swChartTheme();
      c.chart.updateOptions({
        theme: { mode: t.mode },
        chart: { background: "transparent", foreColor: t.text },
        grid: { borderColor: t.grid },
      });
    });
  });
  window.swMoney = function (v, symbol) {
    const n = Math.round(Number(v) || 0);
    return (symbol || "₹") + n.toLocaleString("en-IN");
  };
})();
