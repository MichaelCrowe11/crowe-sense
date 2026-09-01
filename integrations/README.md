# Integrations: one contract, six surfaces

Every directory here carries a surface's Crowe Sense integration in the form that
surface's repo can take it: a `format-patch` series on a `feat/crowe-sense` branch cut
from that repo's current head, a README with the exact test commands and their pasted
output, and what is not done. None of the branches is pushed or merged; each was built
in a worktree so the shared checkouts (which other sessions had uncommitted work in)
were never touched.

| Surface | Repo | Branch and state | Read |
|---|---|---|---|
| CLI (`crowe sense`) | ~/Projects/crowe-logic-foundry | `feat/crowe-sense`, commit ea5224cf, 25 tests, full suite 2,215 green | `cli/README.md` |
| Desktop (Electron, Cultivation space) | ~/Projects/crowe-logic-desktop | `feat/crowe-sense`, commit 68e74f6, 14 tests + 67 parity | `desktop/README.md` |
| Web (crowelogic.com edge) | ~/crowe-logic-web (no git) | patch applied, backups kept, awaiting `wrangler deploy` by Michael | `web/README.md` |
| Mobile and macOS (Tauri) | `../app` | 0.2.0, `cargo check` clean | `mobile/README.md` |
| Cortex | ~/Projects/crowe-cortex | `feat/crowe-sense` off `integration/v0.16`, commit ff55119, 8 tests + 28 adjacent, tsc and vite build clean | `cortex/README.md` |
| House | undefined surface; assets ready | `<crowe-sense-panel>` web component + kiosk autostart | `house/HOUSE.md` |

Worktrees (kept for review, remove with `git worktree remove`):
`/private/tmp/claude-501/-Users-crowelogic/0d11f324-01d8-4814-b567-2cf68377d5e1/scratchpad/{foundry,desktop,cortex}-sense`.

The rule the fork agents were given and kept: cloud mode is `{relay}/v1/nodes/{node}`
with the leading `/v1` stripped from a per-node read (`/health`, `/api/data`, `/latest`,
`/history`); direct mode is the contract paths verbatim. Every surface has a unit test
for both.
