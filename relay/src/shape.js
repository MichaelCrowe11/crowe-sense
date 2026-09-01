// Turning stored rows into the contract's read shapes. Pure; tested in test/shape.test.js.
import { CHART_METRICS } from "./readings.js";

// When several drivers report one metric, the first listed wins (mirrors firmware/crowe/metrics.py).
export const PREFERRED = {
  temperature_c: ["sht45", "scd41", "bme688"],
  humidity_pct: ["sht45", "scd41", "bme688"],
  pressure_hpa: ["bme688"],
};
const rank = (metric, sensor) => {
  const o = PREFERRED[metric];
  if (!o) return 0;
  const i = o.indexOf(sensor);
  return i < 0 ? o.length : i;
};

/** Keep, per (zone, metric), only the rows from the preferred driver present. */
export function preferred(rows) {
  const best = new Map();
  for (const r of rows) {
    const k = `${r.zone}|${r.metric}`;
    const cur = best.get(k);
    if (cur === undefined || rank(r.metric, r.sensor) < rank(r.metric, cur)) best.set(k, r.sensor);
  }
  return rows.filter((r) => best.get(`${r.zone}|${r.metric}`) === r.sensor);
}

/** rows: newest reading per (zone, metric). -> the `snapshot` object of /api/data. */
export function snapshot(rows, now) {
  const out = {};
  for (const r of preferred(rows)) {
    const zone = r.sensor === "derived" ? `${r.zone}-derived` : r.zone;
    (out[zone] ||= {})[r.metric] = {
      value: r.value, unit: r.unit, quality: r.quality || "ok",
      age: Math.round((now - r.ts) * 10) / 10,
    };
  }
  return out;
}

/** rows ordered by ts, chart metrics only. -> the `series` object, <=200 points per key. */
export function series(rows, maxPoints = 200) {
  const ser = {};
  for (const r of preferred(rows)) {
    if (!CHART_METRICS.includes(r.metric) || r.sensor === "derived") continue;
    (ser[`${r.zone}|${r.metric}`] ||= []).push([Math.round(r.ts * 10) / 10, r.value]);
  }
  for (const k of Object.keys(ser)) ser[k] = downsample(ser[k], maxPoints);
  return ser;
}

export function downsample(pts, n) {
  if (pts.length <= n) return pts;
  const step = pts.length / n;
  const out = [];
  for (let i = 0; i < n; i++) out.push(pts[Math.floor(i * step)]);
  return out;
}

export function health(node, now, staleAfter) {
  const last = node.last_seen_ts || null;
  const age = last ? Math.round((now - last) * 10) / 10 : null;
  return {
    ok: age !== null && age <= staleAfter,
    node: node.node_id, zone: node.zone, readings: node.readings_count || 0,
    last_ts: last, age_s: age, version: "relay-0.1.0",
  };
}

/** Mean per bucket for /v1/history. rows: [{ts, value}] in ts order. */
export function bucket(rows, step) {
  const sums = new Map();
  for (const r of rows) {
    const b = Math.floor(r.ts / step) * step;
    const s = sums.get(b) || { n: 0, sum: 0 };
    s.n++; s.sum += r.value; sums.set(b, s);
  }
  return [...sums.entries()].sort((a, b) => a[0] - b[0]).map(([b, s]) => [b, Math.round((s.sum / s.n) * 1000) / 1000]);
}
