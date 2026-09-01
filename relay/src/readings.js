// Parsing and validation of readings, per contracts/reading.schema.json.
// Pure functions: no bindings, no fetch, fully covered by test/readings.test.js.

export const METRICS = new Set([
  "temperature_c", "humidity_pct", "co2_ppm", "vpd_kpa", "dew_point_c", "light_lux",
  "gas_ohms", "pressure_hpa", "prefilter_dp_pa", "hood_face_velocity_fpm",
  "hood_laminar_ok", "prefilter_load_pct", "prefilter_days_left", "co2_trend_ppm_min",
  "fruiting_score", "soc_temp_c", "arm_clock_mhz", "core_volts", "undervoltage_now", "throttled_now",
]);
export const CHART_METRICS = ["temperature_c", "humidity_pct", "co2_ppm"];
const SENSORS = new Set(["scd41", "sht45", "bme688", "veml7700", "sdp810", "pi", "derived", "manual"]);
const QUALITIES = new Set(["ok", "warming", "stale", "est", "fault"]);
const NODE_RE = /^cs-[0-9a-f]{6}$/;
const METRIC_RE = /^[a-z][a-z0-9_]{1,40}$/;

/** Returns null when the object is a valid reading, else a one-sentence reason. */
export function validate(r) {
  if (!r || typeof r !== "object" || Array.isArray(r)) return "reading is not an object";
  for (const k of Object.keys(r)) {
    if (!["ts", "node", "zone", "sensor", "metric", "value", "unit", "quality"].includes(k)) return `unknown field ${k}`;
  }
  if (typeof r.ts !== "number" || !Number.isFinite(r.ts) || r.ts < 1600000000) return "ts must be unix seconds";
  if (typeof r.node !== "string" || !NODE_RE.test(r.node)) return "node must match cs-xxxxxx";
  if (typeof r.zone !== "string" || r.zone.length < 1 || r.zone.length > 32) return "zone must be 1 to 32 characters";
  if (!SENSORS.has(r.sensor)) return `sensor ${r.sensor} is not known`;
  if (typeof r.metric !== "string" || !METRIC_RE.test(r.metric)) return "metric must be a lowercase identifier";
  if (typeof r.value !== "number" || !Number.isFinite(r.value)) return "value must be a finite number";
  if (typeof r.unit !== "string" || r.unit.length > 12) return "unit must be a short string";
  if (r.quality !== undefined && !QUALITIES.has(r.quality)) return `quality ${r.quality} is not known`;
  return null;
}

/** NDJSON text -> readings. Throws {status, error, detail} on the first bad line. */
export function parseNdjson(text, node) {
  const out = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    let obj;
    try { obj = JSON.parse(line); } catch { throw bad(`line ${i + 1} is not JSON`); }
    const why = validate(obj);
    if (why) throw bad(`line ${i + 1}: ${why}`);
    if (node && obj.node !== node) throw bad(`line ${i + 1}: node ${obj.node} does not match the signing node ${node}`);
    out.push({ quality: "ok", ...obj });
  }
  return out;
}

function bad(detail) { return { status: 400, error: "bad_reading", detail }; }

/** Decode a request body that may be gzipped. Returns text. */
export async function bodyText(bytes, contentEncoding) {
  if ((contentEncoding || "").toLowerCase() === "gzip") {
    const ds = new DecompressionStream("gzip");
    const stream = new Blob([bytes]).stream().pipeThrough(ds);
    return await new Response(stream).text();
  }
  return new TextDecoder().decode(bytes);
}
