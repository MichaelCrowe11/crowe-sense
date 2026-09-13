// Crowe Sense relay. See contracts/telemetry-v1.md for every path and shape served here.
import { parseNdjson, bodyText } from "./readings.js";
import { verifyBatch, verifyBearer } from "./verify.js";
import { snapshot, series, health, bucket, preferred } from "./shape.js";
import { d1Store } from "./store-d1.js";

const NODE_RE = /^cs-[0-9a-f]{6}$/;
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, x-crowe-node, x-crowe-signature, content-encoding",
  "access-control-max-age": "86400",
};

function json(status, body, extra = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...CORS, ...extra } });
}
const err = (status, error, detail) => json(status, { error, detail });

/** Build the handler with injectable store and bearer verifier, so tests run it whole. */
const MAX_DESCRIPTOR_BYTES = 64 * 1024;

export function makeHandler({ store, bearer, now = () => Date.now() / 1000, staleAfter = 180, maxBody = 5 * 1024 * 1024 }) {
  async function owner(req) {
    const who = await bearer(req.headers.get("authorization"));
    return who;
  }

  return async function handle(req) {
    const url = new URL(req.url);
    const p = url.pathname.replace(/\/+$/, "") || "/";
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });

    if (p === "/" || p === "/health") return json(200, { ok: true, service: "crowe-sense-relay", contract: "v1" });

    // --- ingest -----------------------------------------------------------------------
    if (p === "/v1/ingest") {
      if (req.method !== "POST") return err(405, "method_not_allowed", "POST a signed NDJSON batch here.");
      const nodeId = req.headers.get("x-crowe-node") || "";
      const sig = req.headers.get("x-crowe-signature") || "";
      if (!NODE_RE.test(nodeId)) return err(401, "unknown_node", "x-crowe-node is missing or malformed.");
      const len = Number(req.headers.get("content-length") || 0);
      if (len > maxBody) return err(413, "too_large", `Batches are capped at ${maxBody} bytes.`);
      const bytes = new Uint8Array(await req.arrayBuffer());
      if (bytes.byteLength > maxBody) return err(413, "too_large", `Batches are capped at ${maxBody} bytes.`);
      const node = await store.getNode(nodeId);
      if (!node) return err(401, "unknown_node", `Node ${nodeId} is not paired. Run: crowe sense pair.`);
      if (!(await verifyBatch(node.public_key, sig, bytes))) return err(401, "bad_signature", "The batch signature did not verify against the node's registered key.");
      let readings;
      try {
        readings = parseNdjson(await bodyText(bytes, req.headers.get("content-encoding")), nodeId);
      } catch (e) {
        if (e && e.status) return err(e.status, e.error, e.detail);
        return err(400, "bad_body", String(e && e.message || e));
      }
      const t = now();
      const day = new Date(t * 1000).toISOString().slice(0, 10);
      const gz = (req.headers.get("content-encoding") || "").toLowerCase() === "gzip" ? ".gz" : "";
      await store.putRaw(`raw/${nodeId}/${day}/${Math.round(t * 1000)}.ndjson${gz}`, bytes);
      const added = await store.insertReadings(readings);
      const lastTs = readings.reduce((m, r) => Math.max(m, r.ts), 0);
      await store.touchNode(nodeId, lastTs || t, added);
      return json(202, { accepted: added, received: readings.length, node: nodeId });
    }

    // --- descriptor publish: signed by the node like a batch -----------------------------
    // The relay stores the document and serves it read-only. It never carries a write
    // back to the node; the descriptor itself says so (access.write_path: direct-only).
    if (p === "/v1/descriptor") {
      if (req.method !== "POST") return err(405, "method_not_allowed", "POST the node's signed descriptor here.");
      const nodeId = req.headers.get("x-crowe-node") || "";
      const sig = req.headers.get("x-crowe-signature") || "";
      if (!NODE_RE.test(nodeId)) return err(401, "unknown_node", "x-crowe-node is missing or malformed.");
      const bytes = new Uint8Array(await req.arrayBuffer());
      if (bytes.byteLength > MAX_DESCRIPTOR_BYTES) return err(413, "too_large", `Descriptors are capped at ${MAX_DESCRIPTOR_BYTES} bytes.`);
      const node = await store.getNode(nodeId);
      if (!node) return err(401, "unknown_node", `Node ${nodeId} is not paired. Run: crowe sense pair.`);
      if (!(await verifyBatch(node.public_key, sig, bytes))) return err(401, "bad_signature", "The descriptor signature did not verify against the node's registered key.");
      let doc;
      try { doc = JSON.parse(new TextDecoder().decode(bytes)); } catch { return err(400, "bad_body", "The descriptor must be a JSON object."); }
      if (!doc || typeof doc !== "object" || Array.isArray(doc)) return err(400, "bad_body", "The descriptor must be a JSON object.");
      if (typeof doc.schema !== "string" || !doc.identity || doc.identity.node !== nodeId)
        return err(400, "bad_descriptor", "A descriptor carries a schema id and identity.node equal to the signing node.");
      const t = now();
      await store.putDescriptor(nodeId, JSON.stringify(doc), t);
      return json(202, { node: nodeId, revision: doc.revision || null, stored_ts: t });
    }

    // --- everything else needs a Crowe ID ---------------------------------------------
    const who = await owner(req);
    if (!who) return err(401, "unauthorized", "Sign in with Crowe ID and send the access token as a bearer.");

    if (p === "/v1/nodes") {
      if (req.method === "GET") return json(200, { nodes: await store.listNodes(who.email) });
      if (req.method === "POST") {
        let b;
        try { b = await req.json(); } catch { return err(400, "bad_body", "Send JSON: {node, public_key, zone, label}."); }
        if (!NODE_RE.test(b.node || "")) return err(400, "bad_node", "node must match cs-xxxxxx.");
        if (typeof b.public_key !== "string" || b.public_key.length < 40) return err(400, "bad_key", "public_key must be the base64 raw Ed25519 public key.");
        const zone = String(b.zone || b.node).slice(0, 32);
        const existing = await store.getNode(b.node);
        if (existing && existing.owner_email !== who.email) return err(409, "owned", "That node is paired to another Crowe ID.");
        if (existing) return json(200, { node: b.node, zone: existing.zone, already: true });
        await store.registerNode({ node_id: b.node, owner_email: who.email, public_key: b.public_key, zone, label: String(b.label || "").slice(0, 64), created_ts: now() });
        return json(201, { node: b.node, zone, owner: who.email });
      }
      return err(405, "method_not_allowed", "GET lists your nodes; POST pairs one.");
    }

    const m = /^\/v1\/nodes\/(cs-[0-9a-f]{6})(\/.*)?$/.exec(p);
    if (!m) return err(404, "not_found", "See contracts/telemetry-v1.md for the paths served here.");
    const nodeId = m[1], sub = m[2] || "/health";
    const node = await store.getNode(nodeId);
    if (!node || node.owner_email !== who.email) return err(404, "not_found", "No such node on this Crowe ID.");
    const t = now();

    if (sub === "/health") return json(200, health(node, t, staleAfter));
    if (sub === "/describe") {
      const d = await store.getDescriptor(nodeId);
      if (!d) return err(404, "no_descriptor", "This node has not published a descriptor yet. Its uploader does so on start once its firmware knows how.");
      return new Response(d.descriptor, { status: 200, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-crowe-stored-ts": String(d.ts), ...CORS } });
    }
    if (sub === "/latest") {
      const rows = preferred(await store.latest(nodeId));
      return json(200, rows.map((r) => ({ ts: r.ts, node: nodeId, zone: r.zone, sensor: r.sensor, metric: r.metric, value: r.value, unit: r.unit, quality: r.quality || "ok" })));
    }
    if (sub === "/api/data") {
      const hours = Math.min(Math.max(Number(url.searchParams.get("hours") || 6), 0.1), 24 * 14);
      const [latest, rows] = await Promise.all([store.latest(nodeId), store.chartRows(nodeId, t - hours * 3600)]);
      return json(200, { generated: t, node: nodeId, zone: node.zone, count: node.readings_count || 0, hours, snapshot: snapshot(latest, t), series: series(rows) });
    }
    if (sub === "/history") {
      const metric = url.searchParams.get("metric") || "";
      const zone = url.searchParams.get("zone") || node.zone;
      const hours = Math.min(Math.max(Number(url.searchParams.get("hours") || 24), 0.1), 24 * 90);
      const step = Math.min(Math.max(Number(url.searchParams.get("step") || 60), 1), 86400);
      if (!/^[a-z][a-z0-9_]{1,40}$/.test(metric)) return err(400, "bad_metric", "metric is required.");
      const rows = preferred((await store.historyRows(nodeId, zone, metric, t - hours * 3600)).map((r) => ({ ...r, zone, metric })));
      return json(200, { metric, zone, unit: rows[0]?.unit || "", step, points: bucket(rows, step) });
    }
    return err(404, "not_found", "Paths under a node: /health, /describe, /latest, /api/data, /history.");
  };
}

export default {
  async fetch(req, env) {
    const handle = makeHandler({
      store: d1Store(env.DB, env.RAW),
      bearer: (auth) => verifyBearer(auth, env.ISSUER),
      staleAfter: Number(env.STALE_AFTER_S || 180),
      maxBody: Number(env.MAX_BODY_BYTES || 5 * 1024 * 1024),
    });
    try { return await handle(req); }
    catch (e) { return json(500, { error: "internal", detail: String(e && e.message || e).slice(0, 200) }); }
  },
};
