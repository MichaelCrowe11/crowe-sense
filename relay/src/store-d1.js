// D1 + R2 implementation of the store interface. Schema: contracts/schema.sql.
export function d1Store(DB, RAW) {
  return {
    async getNode(id) {
      return await DB.prepare("SELECT node_id, owner_email, public_key, zone, label, created_ts, last_seen_ts, readings_count FROM nodes WHERE node_id = ?").bind(id).first();
    },
    async listNodes(email) {
      const { results } = await DB.prepare("SELECT node_id, zone, label, created_ts, last_seen_ts, readings_count FROM nodes WHERE owner_email = ? ORDER BY created_ts").bind(email).all();
      return results;
    },
    async registerNode(n) {
      await DB.prepare("INSERT INTO nodes (node_id, owner_email, public_key, zone, label, created_ts, readings_count) VALUES (?, ?, ?, ?, ?, ?, 0)")
        .bind(n.node_id, n.owner_email, n.public_key, n.zone, n.label, n.created_ts).run();
    },
    async insertReadings(rs) {
      const stmt = DB.prepare("INSERT OR IGNORE INTO readings (node_id, ts, zone, sensor, metric, value, unit, quality) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
      let added = 0;
      for (let i = 0; i < rs.length; i += 200) {
        const chunk = rs.slice(i, i + 200).map((r) => stmt.bind(r.node, r.ts, r.zone, r.sensor, r.metric, r.value, r.unit, r.quality || "ok"));
        const res = await DB.batch(chunk);
        for (const x of res) added += x.meta?.changes || 0;
      }
      return added;
    },
    async touchNode(id, ts, added) {
      await DB.prepare("UPDATE nodes SET last_seen_ts = MAX(COALESCE(last_seen_ts, 0), ?), readings_count = readings_count + ? WHERE node_id = ?").bind(ts, added, id).run();
    },
    async putRaw(key, bytes) { await RAW.put(key, bytes); },
    // contracts/migrations/0002-node-descriptor.sql adds the two columns to a live DB.
    async putDescriptor(id, text, ts) {
      await DB.prepare("UPDATE nodes SET descriptor = ?, descriptor_ts = ? WHERE node_id = ?").bind(text, ts, id).run();
    },
    async getDescriptor(id) {
      const r = await DB.prepare("SELECT descriptor, descriptor_ts AS ts FROM nodes WHERE node_id = ?").bind(id).first();
      return r && r.descriptor ? r : null;
    },
    async latest(id) {
      const { results } = await DB.prepare(
        "SELECT r.zone, r.sensor, r.metric, r.value, r.unit, r.quality, r.ts FROM readings r " +
        "JOIN (SELECT zone, metric, sensor, MAX(ts) AS mts FROM readings WHERE node_id = ? GROUP BY zone, metric, sensor) m " +
        "ON r.zone = m.zone AND r.metric = m.metric AND r.sensor = m.sensor AND r.ts = m.mts WHERE r.node_id = ?").bind(id, id).all();
      return results.map((r) => ({ ...r, node: id }));
    },
    async chartRows(id, since) {
      const { results } = await DB.prepare(
        "SELECT zone, sensor, metric, value, ts FROM readings WHERE node_id = ? AND ts >= ? AND metric IN ('temperature_c','humidity_pct','co2_ppm') ORDER BY ts").bind(id, since).all();
      return results;
    },
    async historyRows(id, zone, metric, since) {
      const { results } = await DB.prepare(
        "SELECT ts, value, unit, sensor FROM readings WHERE node_id = ? AND zone = ? AND metric = ? AND ts >= ? ORDER BY ts").bind(id, zone, metric, since).all();
      return results;
    },
  };
}
