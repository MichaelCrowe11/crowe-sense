-- Crowe Sense relay, D1. Applied with: wrangler d1 execute crowe-sense --file=contracts/schema.sql
CREATE TABLE IF NOT EXISTS nodes (
  node_id      TEXT PRIMARY KEY,
  owner_email  TEXT NOT NULL,
  public_key   TEXT NOT NULL,           -- base64, raw 32-byte Ed25519 public key
  zone         TEXT NOT NULL,
  label        TEXT NOT NULL DEFAULT '',
  created_ts   REAL NOT NULL,
  last_seen_ts REAL,
  readings_count INTEGER NOT NULL DEFAULT 0,
  descriptor   TEXT,                    -- the node's device descriptor, verbatim (contracts/device-descriptor-v0.md)
  descriptor_ts REAL                    -- when the node last published it
);
CREATE INDEX IF NOT EXISTS idx_nodes_owner ON nodes(owner_email);

CREATE TABLE IF NOT EXISTS readings (
  node_id  TEXT NOT NULL,
  ts       REAL NOT NULL,
  zone     TEXT NOT NULL,
  sensor   TEXT NOT NULL,
  metric   TEXT NOT NULL,
  value    REAL NOT NULL,
  unit     TEXT NOT NULL,
  quality  TEXT NOT NULL DEFAULT 'ok',
  PRIMARY KEY (node_id, zone, metric, sensor, ts)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_readings_node_metric_ts ON readings(node_id, metric, ts);
