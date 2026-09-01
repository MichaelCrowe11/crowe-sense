/* <crowe-sense-panel>: the Crowe Sense read surface as one framework-free web component.
 *
 * Reads contracts/telemetry-v1.md from either place:
 *   <crowe-sense-panel src="http://192.168.1.40:8078"></crowe-sense-panel>            direct
 *   <crowe-sense-panel src="https://sense.crowelogic.com/v1/nodes/cs-a1b2c3" token="..."></crowe-sense-panel>
 *   <crowe-sense-panel src="/app/sense/v1/nodes/cs-a1b2c3"></crowe-sense-panel>       behind crowelogic.com (cookie session)
 *
 * Attributes: src (required), token (bearer, cloud only), hours (default 6), refresh (seconds, default 15),
 * theme ("dark" default, or "light" for the editorial cream surface).
 * Events: "sense:data" (detail = the /api/data payload), "sense:error" (detail = message).
 * House, or any page, mounts this and gets the same tiles and sparklines as the app.
 */
(() => {
  const CM = ["temperature_c", "humidity_pct", "co2_ppm"];
  const LBL = { temperature_c: "Temperature", humidity_pct: "Humidity", co2_ppm: "CO2", vpd_kpa: "VPD", light_lux: "Light",
    fruiting_score: "Fruiting score", dew_point_c: "Dew point", co2_trend_ppm_min: "CO2 trend", hood_face_velocity_fpm: "Face velocity",
    prefilter_load_pct: "Prefilter load", prefilter_days_left: "Prefilter life", prefilter_dp_pa: "Prefilter dP", hood_laminar_ok: "Laminar flow",
    soc_temp_c: "SoC temp", arm_clock_mhz: "ARM clock", core_volts: "Core volts", undervoltage_now: "Undervoltage", gas_ohms: "Gas", pressure_hpa: "Pressure" };
  const THEMES = {
    dark: { bg: "#0f1210", panel: "#171b18", panel2: "#1d221e", line: "#2a312c", ink: "#e9e6dc", muted: "#8b9188", gold: "#c9a227", green: "#5aa469", amber: "#d19a3a", red: "#c9563f" },
    light: { bg: "#F5F2EB", panel: "#FBF8F2", panel2: "#FFFFFF", line: "#E3DDD2", ink: "#1A1410", muted: "#6F665C", gold: "#C4A86C", green: "#5A6B4A", amber: "#B8862B", red: "#A53A2A" },
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (v) => (Math.abs(v) >= 100 ? Math.round(v) : Number(v).toFixed(2)).toLocaleString();
  const ago = (s) => (s < 90 ? Math.round(s) + " s" : Math.round(s / 60) + " min");

  function tile(k, o) {
    const q = o.quality && o.quality !== "ok" ? `<span class="q">${esc(o.quality)}</span>` : "";
    return `<div class="card"><div class="k">${esc(LBL[k] || k)}</div><div class="v">${fmt(o.value)}<span class="u">${esc(o.unit)}</span>${q}</div></div>`;
  }
  function chart(pts, unit, gold, ink) {
    if (!pts || pts.length < 2) return '<svg viewBox="0 0 520 112"></svg><div class="row"><span>no data in this window</span></div>';
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x0 = xs[0], x1 = xs[xs.length - 1];
    let lo = Math.min(...ys), hi = Math.max(...ys);
    if (hi - lo < 1e-6) { hi += 1; lo -= 1; }
    const pad = (hi - lo) * 0.12; lo -= pad; hi += pad;
    const W = 520, H = 112, L = 6, R = 6, T = 8, B = 8;
    const sx = (v) => L + (v - x0) / (x1 - x0 || 1) * (W - L - R);
    const sy = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
    const d = pts.map((p, i) => (i ? "L" : "M") + sx(p[0]).toFixed(1) + " " + sy(p[1]).toFixed(1)).join(" ");
    const area = d + ` L ${sx(x1).toFixed(1)} ${H - B} L ${sx(x0).toFixed(1)} ${H - B} Z`;
    const id = "g" + Math.random().toString(36).slice(2, 8);
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${gold}" stop-opacity=".28"/><stop offset="1" stop-color="${gold}" stop-opacity="0"/></linearGradient></defs><path d="${area}" fill="url(#${id})"/><path d="${d}" fill="none" stroke="${gold}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${sx(x1).toFixed(1)}" cy="${sy(ys[ys.length - 1]).toFixed(1)}" r="3" fill="${ink}"/></svg><div class="row"><span>${lo.toFixed(1)}</span><span>min ${Math.min(...ys).toFixed(1)} / max ${Math.max(...ys).toFixed(1)} ${esc(unit)}</span><span>${hi.toFixed(1)}</span></div>`;
  }

  class CroweSensePanel extends HTMLElement {
    static get observedAttributes() { return ["src", "token", "hours", "refresh", "theme"]; }
    constructor() { super(); this.attachShadow({ mode: "open" }); this._timer = null; }
    connectedCallback() { this._render(); this._tick(); }
    disconnectedCallback() { clearInterval(this._timer); }
    attributeChangedCallback() { if (this.isConnected) { this._render(); this._tick(); } }
    get theme() { return THEMES[this.getAttribute("theme") || "dark"] || THEMES.dark; }

    _render() {
      const t = this.theme;
      this.shadowRoot.innerHTML = `<style>
        :host{display:block;font-family:Inter,system-ui,sans-serif;color:${t.ink};background:${t.bg};border-radius:12px;overflow:hidden}
        header{padding:14px 18px 10px;border-bottom:1px solid ${t.line};display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
        h1{font-family:Fraunces,Georgia,serif;font-weight:600;font-size:20px;margin:0}
        .dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:${t.muted};margin-right:8px;vertical-align:middle}
        .sub{color:${t.muted};font-size:12px;font-family:"JetBrains Mono",monospace}.sub b{color:${t.gold};font-weight:600}
        main{padding:14px 18px 18px}
        .sec{font-family:Fraunces,serif;font-size:13px;color:${t.gold};text-transform:uppercase;letter-spacing:2px;margin:18px 0 8px;font-weight:600}
        .grid{display:grid;gap:10px}.g4{grid-template-columns:repeat(4,1fr)}.g2{grid-template-columns:repeat(2,1fr)}
        @media(max-width:720px){.g4{grid-template-columns:repeat(2,1fr)}}@media(max-width:420px){.g4,.g2{grid-template-columns:1fr}}
        .card{background:linear-gradient(180deg,${t.panel2},${t.panel});border:1px solid ${t.line};border-radius:10px;padding:12px 14px;box-shadow:0 1px 0 rgba(255,255,255,.04) inset,0 6px 16px rgba(0,0,0,.18)}
        .k{color:${t.muted};font-size:11px;letter-spacing:.4px;text-transform:uppercase}
        .v{font-family:"JetBrains Mono",monospace;font-size:24px;font-weight:600;margin-top:5px;line-height:1}
        .u{font-size:12px;color:${t.muted};font-weight:400;margin-left:5px}.q{color:${t.amber};font-size:10px;margin-left:6px}
        .chart{padding-bottom:4px}svg{display:block;width:100%;height:100px}
        .row{font-family:"JetBrains Mono",monospace;font-size:11px;color:${t.muted};display:flex;justify-content:space-between;margin-top:4px}
        .score{font-size:36px}.err{color:${t.red};font-size:13px;font-family:"JetBrains Mono",monospace;padding:14px 0}
        .foot{color:${t.muted};font-size:11px;margin-top:18px;font-family:"JetBrains Mono",monospace}
      </style>
      <header><h1><span class="dot" id="dot"></span>Crowe Sense</h1><span class="sub">node <b id="node">-</b> &nbsp; readings <b id="count">-</b> &nbsp; updated <b id="upd">-</b></span></header>
      <main id="app"><p class="sub">reading the node...</p></main>`;
    }

    _tick() {
      clearInterval(this._timer);
      const every = Math.max(5, Number(this.getAttribute("refresh") || 15)) * 1000;
      this._load();
      this._timer = setInterval(() => this._load(), every);
    }

    async _load() {
      const src = (this.getAttribute("src") || "").replace(/\/+$/, "");
      const hours = Number(this.getAttribute("hours") || 6);
      const $ = (id) => this.shadowRoot.getElementById(id);
      if (!src) { $("app").innerHTML = '<p class="err">No src attribute. Point me at a node or a relay node path.</p>'; return; }
      const headers = {};
      const token = this.getAttribute("token");
      if (token) headers.authorization = `Bearer ${token}`;
      let d;
      try {
        const r = await fetch(`${src}/api/data?hours=${hours}`, { headers, cache: "no-store", credentials: src.startsWith("/") ? "include" : "omit" });
        if (!r.ok) { const e = await r.json().catch(() => ({ detail: r.statusText })); throw new Error(`${r.status} ${e.detail || e.error || ""}`); }
        d = await r.json();
      } catch (e) {
        $("dot").style.background = this.theme.red;
        $("app").innerHTML = `<p class="err">Cannot read the node. ${esc(e.message || e)}</p>`;
        this.dispatchEvent(new CustomEvent("sense:error", { detail: String(e.message || e) }));
        return;
      }
      const t = this.theme;
      $("node").textContent = d.node; $("count").textContent = Number(d.count || 0).toLocaleString();
      $("upd").textContent = new Date(d.generated * 1000).toLocaleTimeString();
      const S = d.snapshot || {}, SE = d.series || {};
      let h = "";
      const zones = Object.keys(S).filter((z) => !z.endsWith("-derived") && z !== "pi" && !z.startsWith("hood"));
      for (const z of zones) {
        const s = S[z], der = S[z + "-derived"] || {};
        h += `<div class="sec">${esc(z.replace("-", " "))}</div><div class="grid g4">`;
        for (const m of ["temperature_c", "humidity_pct", "co2_ppm"]) if (s[m]) h += tile(m, s[m]);
        if (der.vpd_kpa) h += tile("vpd_kpa", der.vpd_kpa);
        h += "</div>";
        const chips = [];
        if (der.fruiting_score) { const fv = der.fruiting_score.value, col = fv >= 75 ? t.green : fv >= 50 ? t.amber : t.red; chips.push(`<div class="card"><div class="k">Fruiting score</div><div class="v score" style="color:${col}">${fmt(fv)}</div></div>`); }
        if (der.dew_point_c) chips.push(tile("dew_point_c", der.dew_point_c));
        if (s.light_lux) chips.push(tile("light_lux", s.light_lux));
        if (s.pressure_hpa) chips.push(tile("pressure_hpa", s.pressure_hpa));
        if (chips.length) h += `<div class="grid g4" style="margin-top:10px">${chips.join("")}</div>`;
        h += `<div class="grid g2" style="margin-top:10px">`;
        for (const m of CM) h += `<div class="card chart"><div class="k">${esc(LBL[m])} &middot; ${hours}h</div>${chart(SE[`${z}|${m}`], s[m] ? s[m].unit : "", t.gold, t.ink)}</div>`;
        h += "</div>";
      }
      const hd = S["hood-1"] || {}, hde = S["hood-1-derived"] || {};
      if (Object.keys(hd).length || Object.keys(hde).length) {
        h += `<div class="sec">flow hood</div><div class="grid g4">`;
        for (const [k, o] of Object.entries({ ...hd, ...hde })) if (k !== "hood_laminar_ok") h += tile(k, o);
        h += "</div>";
      }
      const p = S.pi || {};
      if (Object.keys(p).length) {
        h += `<div class="sec">controller</div><div class="grid g4">`;
        for (const k of ["soc_temp_c", "arm_clock_mhz", "core_volts"]) if (p[k]) h += tile(k, p[k]);
        h += "</div>";
      }
      if (!zones.length && !Object.keys(p).length) h += '<p class="sub">No readings yet in this window.</p>';
      h += `<div class="foot">Crowe Sense &middot; node ${esc(d.node)}${d.zone ? " &middot; zone " + esc(d.zone) : ""} &middot; contract v1</div>`;
      $("app").innerHTML = h;
      $("dot").style.background = t.green;
      this.dispatchEvent(new CustomEvent("sense:data", { detail: d }));
    }
  }
  if (!customElements.get("crowe-sense-panel")) customElements.define("crowe-sense-panel", CroweSensePanel);
})();
