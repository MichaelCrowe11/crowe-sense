import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import { gzipSync } from "node:zlib";
import { makeHandler } from "../src/index.js";
import { memoryStore } from "../src/store-memory.js";
import { validate, parseNdjson } from "../src/readings.js";
import { snapshot, series, downsample, bucket, health, preferred } from "../src/shape.js";

const NOW = 1788236000; // 2026-09-01T04:13:20Z
const { publicKey, privateKey } = generateKeyPairSync("ed25519");
const pubRaw = publicKey.export({ type: "spki", format: "der" }).subarray(-32);
const pubB64 = Buffer.from(pubRaw).toString("base64");

function setup() {
  const store = memoryStore();
  const bearer = async (auth) => (auth === "Bearer good" ? { email: "michael@example.com" } : auth === "Bearer other" ? { email: "someone@example.com" } : null);
  const handle = makeHandler({ store, bearer, now: () => NOW, staleAfter: 180 });
  return { store, handle };
}
const reading = (over = {}) => ({ ts: NOW - 5, node: "cs-a1b2c3", zone: "tent-1", sensor: "scd41", metric: "co2_ppm", value: 812, unit: "ppm", ...over });
const ndjson = (rs) => rs.map((r) => JSON.stringify(r)).join("\n") + "\n";
const signed = (bytes) => Buffer.from(sign(null, bytes, privateKey)).toString("base64");
const req = (path, init = {}) => new Request(`https://sense.crowelogic.com${path}`, init);

async function pair(handle, node = "cs-a1b2c3", auth = "Bearer good") {
  return handle(req("/v1/nodes", { method: "POST", headers: { authorization: auth, "content-type": "application/json" }, body: JSON.stringify({ node, public_key: pubB64, zone: "tent-1", label: "North tent" }) }));
}

test("validate accepts the contract reading and rejects the wrong shapes", () => {
  assert.equal(validate(reading()), null);
  assert.match(validate(reading({ node: "pi" })), /cs-xxxxxx/);
  assert.match(validate(reading({ value: "812" })), /finite number/);
  assert.match(validate(reading({ extra: 1 })), /unknown field/);
  assert.match(validate(reading({ quality: "great" })), /not known/);
});

test("parseNdjson rejects a foreign node and a broken line with a line number", () => {
  assert.equal(parseNdjson(ndjson([reading(), reading({ metric: "temperature_c", unit: "C", value: 21 })]), "cs-a1b2c3").length, 2);
  assert.throws(() => parseNdjson(ndjson([reading({ node: "cs-ffffff" })]), "cs-a1b2c3"), (e) => e.status === 400 && /line 1: node cs-ffffff/.test(e.detail));
  assert.throws(() => parseNdjson("{oops\n", "cs-a1b2c3"), (e) => /line 1 is not JSON/.test(e.detail));
});

test("shapes: snapshot puts derived under zone-derived, series keeps chart metrics, buckets average", () => {
  const rows = [reading(), reading({ sensor: "derived", metric: "vpd_kpa", unit: "kPa", value: 0.4, quality: "est" })];
  const s = snapshot(rows, NOW);
  assert.equal(s["tent-1"].co2_ppm.value, 812);
  assert.equal(s["tent-1"].co2_ppm.age, 5);
  assert.equal(s["tent-1-derived"].vpd_kpa.quality, "est");
  const ser = series([reading({ ts: NOW - 20 }), reading({ ts: NOW - 10, value: 820 }), reading({ metric: "light_lux" })]);
  assert.deepEqual(Object.keys(ser), ["tent-1|co2_ppm"]);
  assert.equal(ser["tent-1|co2_ppm"].length, 2);
  assert.equal(downsample(Array.from({ length: 1000 }, (_, i) => [i, i]), 200).length, 200);
  assert.deepEqual(bucket([{ ts: 100, value: 1 }, { ts: 110, value: 3 }, { ts: 200, value: 10 }], 60), [[60, 2], [180, 10]]);
  assert.equal(health({ node_id: "cs-a1b2c3", zone: "tent-1", last_seen_ts: NOW - 4, readings_count: 9 }, NOW, 180).ok, true);
  assert.equal(health({ node_id: "cs-a1b2c3", zone: "tent-1", last_seen_ts: NOW - 400 }, NOW, 180).ok, false);
});

test("ingest: unknown node, bad signature, then a good signed gzip batch lands in R2 and the store", async () => {
  const { store, handle } = setup();
  const body = Buffer.from(ndjson([reading(), reading({ metric: "temperature_c", unit: "C", value: 21.2, sensor: "sht45" })]));
  let r = await handle(req("/v1/ingest", { method: "POST", headers: { "x-crowe-node": "cs-a1b2c3", "x-crowe-signature": signed(body) }, body }));
  assert.equal(r.status, 401); assert.equal((await r.json()).error, "unknown_node");

  assert.equal((await pair(handle)).status, 201);
  r = await handle(req("/v1/ingest", { method: "POST", headers: { "x-crowe-node": "cs-a1b2c3", "x-crowe-signature": Buffer.alloc(64).toString("base64") }, body }));
  assert.equal(r.status, 401); assert.equal((await r.json()).error, "bad_signature");

  const gz = gzipSync(body);
  r = await handle(req("/v1/ingest", { method: "POST", headers: { "x-crowe-node": "cs-a1b2c3", "x-crowe-signature": signed(gz), "content-encoding": "gzip" }, body: gz }));
  assert.equal(r.status, 202);
  assert.deepEqual(await r.json(), { accepted: 2, received: 2, node: "cs-a1b2c3" });
  assert.equal(store._raw.length, 1);
  assert.match(store._raw[0].key, /^raw\/cs-a1b2c3\/2026-09-01\/\d+\.ndjson\.gz$/);

  // the same batch again is a no-op, not a duplicate
  r = await handle(req("/v1/ingest", { method: "POST", headers: { "x-crowe-node": "cs-a1b2c3", "x-crowe-signature": signed(gz), "content-encoding": "gzip" }, body: gz }));
  assert.equal((await r.json()).accepted, 0);

  // a tampered body fails even with the old signature
  const tampered = Buffer.from(ndjson([reading({ value: 9999 })]));
  r = await handle(req("/v1/ingest", { method: "POST", headers: { "x-crowe-node": "cs-a1b2c3", "x-crowe-signature": signed(body) }, body: tampered }));
  assert.equal(r.status, 401);
});

test("reads: bearer required, ownership enforced, all four node paths return the contract shapes", async () => {
  const { handle } = setup();
  await pair(handle);
  const body = Buffer.from(ndjson([
    reading({ ts: NOW - 3000 }), reading({ ts: NOW - 5, value: 830 }),
    reading({ ts: NOW - 5, metric: "temperature_c", unit: "C", value: 21.2, sensor: "sht45" }),
    reading({ ts: NOW - 5, metric: "vpd_kpa", unit: "kPa", value: 0.41, sensor: "derived", quality: "est" }),
  ]));
  await handle(req("/v1/ingest", { method: "POST", headers: { "x-crowe-node": "cs-a1b2c3", "x-crowe-signature": signed(body) }, body }));

  assert.equal((await handle(req("/v1/nodes/cs-a1b2c3/health"))).status, 401);
  assert.equal((await handle(req("/v1/nodes/cs-a1b2c3/health", { headers: { authorization: "Bearer other" } }))).status, 404);

  const h = await (await handle(req("/v1/nodes/cs-a1b2c3/health", { headers: { authorization: "Bearer good" } }))).json();
  assert.equal(h.ok, true); assert.equal(h.readings, 4); assert.equal(h.age_s, 5);

  const latest = await (await handle(req("/v1/nodes/cs-a1b2c3/latest", { headers: { authorization: "Bearer good" } }))).json();
  assert.equal(latest.length, 3);
  assert.equal(latest.find((r) => r.metric === "co2_ppm").value, 830);

  const data = await (await handle(req("/v1/nodes/cs-a1b2c3/api/data?hours=6", { headers: { authorization: "Bearer good" } }))).json();
  assert.equal(data.snapshot["tent-1"].co2_ppm.value, 830);
  assert.equal(data.snapshot["tent-1-derived"].vpd_kpa.value, 0.41);
  assert.equal(data.series["tent-1|co2_ppm"].length, 2);
  assert.equal(data.count, 4);

  const hist = await (await handle(req("/v1/nodes/cs-a1b2c3/history?metric=co2_ppm&zone=tent-1&hours=2&step=60", { headers: { authorization: "Bearer good" } }))).json();
  assert.equal(hist.unit, "ppm");
  assert.deepEqual(hist.points.map((p) => p[1]), [812, 830]);

  const list = await (await handle(req("/v1/nodes", { headers: { authorization: "Bearer good" } }))).json();
  assert.equal(list.nodes[0].node_id, "cs-a1b2c3");
  assert.equal((await handle(req("/v1/nodes", { headers: { authorization: "Bearer other" } })).then((r) => r.json())).nodes.length, 0);

  // pairing someone else's node is refused
  assert.equal((await pair(handle, "cs-a1b2c3", "Bearer other")).status, 409);
});

test("three drivers report temperature; the SHT45 wins the snapshot, the latest list, and history", async () => {
  const rows = [
    reading({ metric: "temperature_c", unit: "C", value: 21.0, sensor: "scd41" }),
    reading({ metric: "temperature_c", unit: "C", value: 21.4, sensor: "sht45", ts: NOW - 6 }),
    reading({ metric: "temperature_c", unit: "C", value: 22.0, sensor: "bme688" }),
  ];
  assert.deepEqual(preferred(rows).map((r) => r.sensor), ["sht45"]);
  assert.equal(snapshot(rows, NOW)["tent-1"].temperature_c.value, 21.4);
  const { handle } = setup();
  await pair(handle);
  const body = Buffer.from(ndjson(rows));
  await handle(req("/v1/ingest", { method: "POST", headers: { "x-crowe-node": "cs-a1b2c3", "x-crowe-signature": signed(body) }, body }));
  const latest = await (await handle(req("/v1/nodes/cs-a1b2c3/latest", { headers: { authorization: "Bearer good" } }))).json();
  assert.deepEqual(latest.map((r) => r.sensor), ["sht45"]);
  const hist = await (await handle(req("/v1/nodes/cs-a1b2c3/history?metric=temperature_c&zone=tent-1&hours=1&step=60", { headers: { authorization: "Bearer good" } }))).json();
  assert.deepEqual(hist.points.map((p) => p[1]), [21.4]);
});

test("errors are JSON with error and detail, never HTML", async () => {
  const { handle } = setup();
  const r = await handle(req("/v1/nowhere", { headers: { authorization: "Bearer good" } }));
  assert.equal(r.status, 404);
  assert.equal(r.headers.get("content-type"), "application/json; charset=utf-8");
  const b = await r.json();
  assert.ok(b.error && b.detail);
});
