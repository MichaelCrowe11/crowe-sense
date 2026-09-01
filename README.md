# crowe-sense

Crowe Sense is a sensing node for a growing room and the software that carries its
readings to every Crowe Logic surface. This repository is the whole of it: the device,
the firmware, the cloud relay, the apps' integrations, the enclosures, the archive with
its correction, and the documents a funder needs.

**Status, 2026-09-01.** Software: built and tested end to end against a scripted node.
Hardware: no node has yet run with physical sensors in a room; `docs/investor-report.md`
is the plan and the ask that changes that. Read `docs/device-spec.md` for what is proven
and what is not.

```
contracts/      telemetry-v1.md, reading.schema.json, schema.sql: the one contract every surface shares
firmware/       Pi-side services (0.2.0): sampler, local API + kiosk page, signed uploader, watchdog; 51 tests
relay/          Cloudflare Worker: signed ingest -> D1 + R2, Crowe ID gated reads; 7 tests
app/            Tauri client for iPhone and Mac (0.2.0), direct or cloud source
integrations/   cli, desktop, web, mobile, cortex, house: patches, READMEs, test output
hardware/       bom.csv, SHOPPING-LIST.md (priced 2026-08-31), field enclosure (OpenSCAD), pinouts
site/           the founding-grower site and the indoor radiation-shield enclosure (site/model/)
analysis/       practice envelope checker, provenance test, stage and harvest logs (own git history)
archive/        the 2026 stream extracts and the provenance correction (read PROVENANCE-CORRECTION.md first)
server/         the 2026-07 Pi dashboard server and heartbeat monitor, kept for reference; superseded by firmware/crowe/api.py
docs/           device-spec, setup-pipeline, investor-report, investors-30.csv, linkedin-post, analytics
```

## Run the tests

```
cd firmware && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest -q && .venv/bin/ruff check crowe tests
cd relay && npm test
cd app/src-tauri && cargo check
```

## Read the readings

Direct, on the node's network: `http://<node>:8078/` is the dashboard, `/health`,
`/api/data?hours=6`, `/v1/latest`, `/v1/history?metric=co2_ppm` are the contract.
Anywhere else: pair the node once (`crowe sense pair <node> <key>`), then
`https://sense.crowelogic.com/v1/nodes/<node>/...` with a Crowe ID bearer, or through
`crowelogic.com/app/sense/...` with the web session.

## The correction

The dataset published from the 2026 rig (10.5281/zenodo.20722953) described its tent
channels as sensor measurements. They were not; see `archive/PROVENANCE-CORRECTION.md`.
`analysis/provenance_check.py` is the test that found it and now gates every dataset
this repository produces. Nothing in `archive/` is evidence about conditions inside a
growing room.

## Where the pieces came from

`~/crowe-sense-app` and `~/crowe-sense-archive` moved in (symlinks remain at the old
paths); `~/crowe-sense-analysis` and `~/crowe-sense-site` were added as subtrees with
their history; the firmware and field enclosure were already here.

Apache 2.0.
