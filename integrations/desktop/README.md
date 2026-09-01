# Desktop integration (crowe-logic-desktop, Electron)

Branch `feat/crowe-sense` in `~/Projects/crowe-logic-desktop`, commit `68e74f6` on top of
`77a4f18` (release 0.24.3). Worktree at
`/private/tmp/claude-501/-Users-crowelogic/0d11f324-01d8-4814-b567-2cf68377d5e1/scratchpad/desktop-sense`
(node_modules symlinked from the main checkout, untracked).
Patch: `patches/0001-Crowe-Sense-writes-into-the-Environment-lane.patch`
(`git am` it onto main, or merge the branch).

## What it does

Instrument readings land in the Cultivation space's existing `env` store, the seam
main.js and renderer.js already promised ("Crowe Sense will write room readings into
this same store when it lands"). One row per room per UTC hour, id
`sense:<zone>:<YYYY-MM-DD-HH>`, rewritten on every poll, `source: "crowe-sense"`,
temperature in Fahrenheit like the hand-entered rows. Derived pseudo-zones, the flow
hood and the controller's own health are not rooms and are skipped.

Two sources, both from `contracts/telemetry-v1.md`:

| source | reads | auth |
|---|---|---|
| direct | `<url>/health`, `<url>/api/data?hours=1` | none (LAN or tailnet) |
| cloud | `<relay>/v1/nodes/<node>/health`, `.../api/data?hours=1` | the Crowe ID bearer the gateway bridge already sends |

Polls once a minute, 10 s timeout, only while a source is configured. Off is the default.

## Files

| file | change |
|---|---|
| `sense.js` | new. `normalizeSense`, `endpoint`, `toEnvRecords`, `isStale`, `SensePoller` (deps injected: config store, fetch, clock, timers, record sink) |
| `main.js` | `DEFAULTS.sense`, normalised in `loadConfig`; `sense` exposed by get/set-config; `growWrite` inserts under a caller-supplied id only for the `sense:` prefix (every other id must already exist, as before); `senseUpsert` validates through `growValidate` then `growWrite`; IPC `crowe:sense:status` / `crowe:sense:configure`; `crowe:sense:changed` pushed after a write; poller started in `whenReady` |
| `grow-schema.js` | `env.source` field ("who wrote it: blank for a person, crowe-sense for the instrument") |
| `preload.js` | `window.crowe.sense.{status, configure, onChange}` |
| `renderer/renderer.js` | `GROW.env` gets `source` and a "measured" flag; Overview card "Crowe Sense" (not paired / node, zone, last reading, ok-stale-down, reason); footnote names the node once measured rows exist in the last 7 days; Settings fields; redraw on `onChange` |
| `renderer/app.html` | Settings section: Source, Node URL, Node id. Placed below Guardrails, above plugins, so the Spaces checkboxes stay where test-panels hit-tests them (the directive said next to the gateway URL; the test constraint won) |
| `renderer/web-bridge.js` | `sense` surface, cloud only, through `/app/sense/v1/nodes/<node>/health` with credentials; config in localStorage `crowe.web.sense` |
| `renderer/preview-shim.js` | `sense` stub for the preview and test-panels |
| `mobile/src/mobile-bridge.js` | `sense` surface, cloud only, straight to the relay with the phone's Crowe ID |
| `scripts/test-sense.js` | new, 14 checks; in the `npm test` chain right after test-harness |
| `package.json` | test chain only; version untouched |

## Tests run

```
$ node scripts/test-sense.js
crowe sense
ok      normalizeSense is a closed set and falls to off
ok      endpoint: direct is url + path
ok      endpoint: cloud is relay/v1/nodes/<node> + path, with a per-node read's /v1 dropped
ok      endpoint: off resolves to nothing
ok      toEnvRecords: one row per room, none for derived, hood or pi
ok      toEnvRecords: id is sense:<zone>:<UTC hour>, date is the UTC day
ok      toEnvRecords: Fahrenheit to 0.1, RH to 0.1, CO2 whole, source marked
ok      toEnvRecords: a zone with none of the three room metrics is skipped
ok      isStale: past 180 s without a reading, or with no health at all
ok      poller: polls health and data, writes rows through the sink, reports status
ok      poller: a node that answers 503 is reported as an error, not thrown
ok      poller: direct mode sends no bearer
ok      poller: configure persists a normalised config and turning it off stops polling
ok      fmtAge reads like a person would say it

14 passed, 0 failed

$ node scripts/test-web-bridge.js             -> all passed
$ node scripts/test-mobile-bridge.js          -> all mobile bridge checks passed
$ node scripts/test-harness.js                -> harness: 79 tests passed
$ npx electron scripts/test-panels.js         -> 67/67 passed  (includes "grow-schema.js matches the GROW table in renderer.js")
$ npx electron scripts/test-install-spaces.js -> exit 0
```

## Not done

- No build, no release, version not bumped (still 0.24.3). Nothing pushed.
- Not run against a live node: the Pi has been off the tailnet since 2026-07-07 and the
  relay Worker is not deployed. The poller was exercised against a scripted node only.
- The web build shows the node's status but does not write rows (its `grow.list` is
  empty by design). The edge route `/app/sense/*` it reads through belongs to the web
  integration (`integrations/web`).
- The Environment form now shows a Source field. Leaving it blank is the intended path
  for a person; nothing stops someone typing "crowe-sense" by hand.
- `check-contrast.js` not run: no styles were touched.
- The full `npm test` chain was not run end to end (it takes several Electron launches);
  the six suites above are the ones this change can reach.
