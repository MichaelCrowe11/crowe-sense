-- Adds the device descriptor columns to a relay database created before 2026-09-13.
-- Apply once: cd relay && npm run schema:migrate
-- (a fresh database gets them from contracts/schema.sql and does not need this.)
ALTER TABLE nodes ADD COLUMN descriptor TEXT;
ALTER TABLE nodes ADD COLUMN descriptor_ts REAL;
