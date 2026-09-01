# Cortex integration: the Sense panel

Branch `feat/crowe-sense` in `~/Projects/crowe-cortex`, cut from `integration/v0.16`
(fba44ed), commit **ff55119**. Worktree at
`/private/tmp/claude-501/-Users-crowelogic/0d11f324-01d8-4814-b567-2cf68377d5e1/scratchpad/cortex-sense`
(left in place). Patch: `patches/0001-Sense-the-Crowe-Sense-node-as-a-workbench-panel-read.patch`
(`git am` it onto integration/v0.16 or merge the branch). Not pushed, version not bumped.

## What was added

A workbench panel of type `sense`, labeled "Sense", beside Projects. It renders the
contract read `GET /api/data?hours=6` (contracts/telemetry-v1.md) from either the node's
own API (direct) or the relay's `/v1/nodes/<node>` mount (cloud, Crowe ID bearer).

| file | role |
|---|---|
| `src/config/sense.ts` | source `off / direct / cloud`, node address, node id, relay, in localStorage (`crowe-sense-*`), same pattern as `config/farm.ts`; `senseEndpoint(cfg, path)` resolves contract paths for both modes and refuses to build a URL it cannot stand behind |
| `src/lib/sense-client.ts` | `fetchHealth`, `fetchData(hours)`, `fetchLatest`, `fetchHistory({metric, zone, hours, step})`; 10 s AbortController timeout; bearer from `useAuth.getState().accessToken()` in cloud mode with `crowe-sense-token` as a pasted fallback; every failure becomes a `SenseRequestError` carrying the contract `{error, detail}` |
| `src/components/SenseTab.tsx` | header (dot ok/down/unpaired/pending, node id, zones, reading count, "updated N s ago"); per grow zone a tile row (temperature, humidity, CO2, VPD, then fruiting score by band, dew point, CO2 trend, light) and three 6 h inline-SVG sparklines; Flow hood section (`hood-*` zones, face velocity, prefilter load/life/dP, laminar flag); Controller section (`pi`: SoC temp, clock, volts, undervoltage/throttled flags); settings row that persists and refetches; 15 s refresh while mounted; empty state when off, error state with the detail text on failure. No sample data anywhere |
| `src/components/SenseTab.css` | tokens only: stepped surfaces, `--hair-top` bevel, `--shadow-card`, square radii, Fraunces titles, Inter body, JetBrains Mono values |
| `src/components/Icons.tsx` | `IconSense` |
| `src/csep/tabs.ts`, `src/csep/panels.ts`, `src/csep/panel-graph.ts`, `src/components/Workspace.tsx`, `src/components/LeftRail.tsx`, `src/components/CommandPalette.tsx`, `src/App.tsx` | the `sense` key registered at every seam Projects (`farm`) is registered at |
| `src/components/SenseTab.test.tsx` | 8 cases |

Crowe ID: Cortex keeps tokens in the OS keychain via `csep/auth.ts` (never localStorage),
so cloud mode asks `useAuth` for the access token at request time. The `Token` field in
the settings row is only for an operator who is not signed in and pastes one.

## Test commands and actual output

```
$ npx vitest run src/components/SenseTab.test.tsx
 RUN  v4.1.5 .../cortex-sense
 Test Files  1 passed (1)
      Tests  8 passed (8)
   Duration  752ms

$ npx vitest run src/csep/panel-graph src/csep/tabs src/csep/panels src/components/CommandPalette src/components/LeftRail src/components/Workspace src/components/OperatingSurface src/components/FarmTab
 Test Files  8 passed (8)
      Tests  28 passed (28)

$ npx tsc --noEmit -p tsconfig.json
(no output, exit 0)

$ npx vite build
✓ built in 4.30s   (the pre-existing >600 kB chunk warning only)
```

## Not done

- Not run against a live node or relay; the relay does not exist yet and the Pi has been
  off the tailnet since 2026-07-07. The payload in the test is contract-shaped, not captured.
- The full vitest suite was not run, only the eight files that touch the registries.
- `fetchLatest` and `fetchHistory` are implemented and typed but the panel only uses
  `fetchData`; history charts beyond 6 h are a follow-up.
- Mobile shell (GlassTabBar) is untouched: `sense` is a workbench panel, not a nav surface.
