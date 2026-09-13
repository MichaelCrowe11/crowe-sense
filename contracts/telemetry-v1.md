# Crowe Sense telemetry contract, v1

One contract, served in two places:

| where | base | auth | who reads it |
|---|---|---|---|
| on the node (local API, `crowe-api.service`) | `http://<node>:8078` | none (LAN or Tailscale only) | the Tauri app in direct mode, the kiosk display, `crowe sense` on the same network |
| in the cloud (relay Worker) | `https://sense.crowelogic.com/v1/nodes/{node}` | `Authorization: Bearer <Crowe ID access token>` | desktop, web, mobile, Cortex, House, `crowe sense` anywhere |

Every surface speaks to exactly these paths and exactly these shapes. A surface that
needs something else changes this file first.

## The reading

```json
{"ts": 1756700000.0, "node": "cs-a1b2c3", "zone": "tent-1", "sensor": "scd41",
 "metric": "co2_ppm", "value": 812.0, "unit": "ppm", "quality": "ok"}
```

| field | type | meaning |
|---|---|---|
| `ts` | number | unix seconds, UTC, float |
| `node` | string | device id, `cs-` + 6 lowercase hex, assigned at provision |
| `zone` | string | where the node's sensor head sits, from node config (`tent-1`, `hood-1`, `incubation`). Defaults to the node id |
| `sensor` | string | driver that produced it: `scd41`, `sht45`, `bme688`, `veml7700`, `sdp810`, `pi`, `derived` |
| `metric` | string | one of the vocabulary below |
| `value` | number | |
| `unit` | string | |
| `quality` | string | `ok`, `warming` (sensor not yet stable), `stale` (older than 3 periods), `est` (derived from other readings), `fault` |

Metric vocabulary (a reading with a metric outside this list is stored but never charted):

`temperature_c` `humidity_pct` `co2_ppm` `vpd_kpa` `dew_point_c` `light_lux`
`gas_ohms` `pressure_hpa` `prefilter_dp_pa` `hood_face_velocity_fpm`
`hood_laminar_ok` `prefilter_load_pct` `prefilter_days_left` `co2_trend_ppm_min`
`fruiting_score` `soc_temp_c` `arm_clock_mhz` `core_volts` `undervoltage_now` `throttled_now`

`vpd_kpa` and `dew_point_c` are derived from `temperature_c` and `humidity_pct` of the
same zone (Tetens, air VPD: `0.6108 * exp(17.27 t / (t + 237.3)) * (1 - rh / 100)`) and
carry `sensor: "derived", quality: "est"`.

## Read endpoints (identical on node and relay)

`GET /health`
```json
{"ok": true, "node": "cs-a1b2c3", "zone": "tent-1", "readings": 5048780,
 "last_ts": 1756700000.0, "age_s": 4.2, "uptime_s": 86400, "version": "0.2.0"}
```
`ok` is false when `age_s` exceeds 180. A monitor polls this and nothing else.

`GET /api/data?hours=6` (the shape the apps already render; unchanged from the 2026-07 dashboard)
```json
{"generated": 1756700000.0, "node": "cs-a1b2c3", "count": 5048780, "hours": 6,
 "snapshot": {"tent-1": {"co2_ppm": {"value": 812, "unit": "ppm", "quality": "ok", "age": 4.2}}},
 "series": {"tent-1|co2_ppm": [[1756678400.0, 790.0], [1756678520.0, 801.0]]}}
```
`snapshot` carries the newest reading of every zone and metric. `series` carries
`temperature_c`, `humidity_pct` and `co2_ppm` for every zone, downsampled to at most 200
points. Derived metrics appear under `"<zone>-derived"` in `snapshot`, which is what the
existing app expects.

`GET /v1/latest` -> `[reading, ...]`, one per zone and metric, newest.

`GET /v1/history?metric=co2_ppm&zone=tent-1&hours=24&step=60` ->
`{"metric": "co2_ppm", "zone": "tent-1", "unit": "ppm", "points": [[ts, value], ...]}`
where `step` is the bucket width in seconds (mean per bucket) and points are ordered by `ts`.

## Write endpoint (relay only)

`POST /v1/ingest`

| header | value |
|---|---|
| `content-type` | `application/x-ndjson` |
| `content-encoding` | `gzip` (optional) |
| `x-crowe-node` | node id |
| `x-crowe-signature` | base64 Ed25519 signature over the exact request body bytes (after gzip, if gzipped) |

Body: one reading per line, as above. The relay:

1. looks the node up, verifies the signature against its registered public key,
2. appends the raw body unchanged to R2 at `raw/<node>/<YYYY-MM-DD>/<unix-ms>.ndjson.gz`,
3. inserts the readings into D1, ignoring exact duplicates,
4. answers `{"accepted": n, "node": "cs-a1b2c3"}` with 202.

401 on an unknown node or a bad signature, 413 over 5 MB, 400 on a line that is not a
reading. The uploader marks rows sent only after a 2xx, so a rejected batch is retried,
never lost.

## Pairing (relay only)

`POST /v1/nodes` with a Crowe ID bearer, body `{"node": "cs-a1b2c3", "public_key": "<base64 raw 32-byte Ed25519>", "zone": "tent-1", "label": "North tent"}`.
Registers the node to the caller's email. A node already owned by someone else is 409.

`GET /v1/nodes` lists the caller's nodes with `last_seen_ts`.

All `/v1/nodes/{node}/...` reads require that the bearer's email owns the node.

## Errors

Every error is `{"error": "<slug>", "detail": "<sentence>"}` with the right status. No
HTML error pages on either surface.

## Beside this contract: the descriptor and the operations door

`GET /v1/describe` (node) and `GET /v1/nodes/{node}/describe` (relay) serve the device
descriptor, and `POST /v1/operations/{operation}` (node only, operator bearer) is the one
write a node accepts. Both are specified in `device-descriptor-v0.md`. They are additive
to this contract and do not bump it.

## Versioning

This is v1. Additive changes (new metrics, new fields) do not bump it. A field rename or a
shape change goes to `/v2` and both are served for a release.
