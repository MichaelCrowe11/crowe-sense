// In-memory store with the same interface as store-d1.js. Used by the tests and by
// `wrangler dev` when no D1 is bound, never in production.
export function memoryStore() {
  const nodes = new Map();
  const readings = [];
  const raw = [];
  const descriptors = new Map();
  return {
    async getNode(id) { return nodes.get(id) || null; },
    async listNodes(email) { return [...nodes.values()].filter((n) => n.owner_email === email); },
    async registerNode(n) { nodes.set(n.node_id, { readings_count: 0, last_seen_ts: null, ...n }); },
    async insertReadings(rs) {
      let added = 0;
      for (const r of rs) {
        if (readings.some((x) => x.node === r.node && x.zone === r.zone && x.metric === r.metric && x.sensor === r.sensor && x.ts === r.ts)) continue;
        readings.push(r); added++;
      }
      return added;
    },
    async touchNode(id, ts, added) { const n = nodes.get(id); n.last_seen_ts = Math.max(n.last_seen_ts || 0, ts); n.readings_count += added; },
    async putRaw(key, bytes) { raw.push({ key, size: bytes.byteLength }); },
    async latest(id) {
      const best = new Map();
      for (const r of readings) if (r.node === id) {
        const k = `${r.zone}|${r.metric}|${r.sensor}`;
        if (!best.has(k) || best.get(k).ts < r.ts) best.set(k, r);
      }
      return [...best.values()];
    },
    async chartRows(id, since) {
      return readings.filter((r) => r.node === id && r.ts >= since).sort((a, b) => a.ts - b.ts);
    },
    async historyRows(id, zone, metric, since) {
      return readings.filter((r) => r.node === id && r.zone === zone && r.metric === metric && r.ts >= since).sort((a, b) => a.ts - b.ts);
    },
    async putDescriptor(id, text, ts) { descriptors.set(id, { descriptor: text, ts }); },
    async getDescriptor(id) { return descriptors.get(id) || null; },
    _raw: raw, _readings: readings,
  };
}
