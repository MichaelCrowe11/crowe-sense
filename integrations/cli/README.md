# CLI integration: `crowe sense`

Branch `feat/crowe-sense` in `~/Projects/crowe-logic-foundry`, built in the worktree
`$SCRATCH/foundry-sense` (left in place for review). Commit `ea5224cf` on top of
main `5cfa5ab3`. Patch: `patches/0001-*.patch` (apply with `git am`). Not pushed.

## What was added

`crowe sense` is a click group in `cli/commands/sense.py`, registered in
`cli/crowe_logic.py` after `doctor`. Every read goes through one resolver,
`endpoint(cfg, path)`: direct mode uses the contract paths verbatim, cloud mode
nests them under `/v1/nodes/{node}` on the relay (`/v1/latest` becomes
`/v1/nodes/cs-a1b2c3/latest`; `/health` and `/api/data` keep their names) and
carries the Crowe ID bearer from `cli.auth.current_access_token()`.

| command | example | reads |
|---|---|---|
| `use` | `crowe sense use direct http://100.123.229.57:8078` or `crowe sense use cloud cs-a1b2c3 --relay https://sense.crowelogic.com` | writes `~/.crowe-logic/sense.json` (`CROWE_SENSE_CONFIG` overrides) |
| `status` | `crowe sense status` | `/health`; exit 1 when `ok` is false or unreachable |
| `latest` | `crowe sense latest` | `/v1/latest`, one table per zone |
| `history` | `crowe sense history --metric co2_ppm --zone tent-1 --hours 24 --step 300` | `/v1/history`; min, mean, max, block-character sparkline, first and last stamp |
| `nodes` | `crowe sense nodes` | `GET /v1/nodes` on the relay with the bearer |
| `pair` | `crowe sense pair cs-a1b2c3 <base64-pubkey> --zone tent-1 --label "North tent"` | `POST /v1/nodes` with the bearer |
| `check` | `crowe sense check --hours 72 [--zone tent-1] [--stage fruiting]` | pulls temperature_c, humidity_pct, co2_ppm per zone from `/v1/history` into a SQLite `readings(epoch, metric, value, sensor)` and runs `~/crowe-sense/analysis/sense_check.py --db ... --zone ...` per zone (`CROWE_SENSE_ANALYSIS` overrides the path); exit 2 when the analysis checkout is absent, else the worst script exit code |

No new dependencies. Errors from either surface are printed as `error: detail`
verbatim. Without a Crowe ID session, cloud reads and `nodes`/`pair` exit 1 with
"Run `<cmd> login`" (the command name comes from the active profile).

```
Usage: sense [OPTIONS] COMMAND [ARGS]...

  The sensor node: live readings, history, pairing, and the practice check.

Options:
  --help  Show this message and exit.

Commands:
  check    Judge the last window against documented practice (needs the...
  history  One metric over a window: min, mean, max and a sparkline.
  latest   The newest reading of every zone and metric.
  nodes    The nodes paired to this Crowe ID, from the relay.
  pair     Register a node's public key to this Crowe ID on the relay.
  status   Is the node up? Reads /health; exits 1 when it is down or...
  use      Point this machine at a node: `use direct http://host:8078` or...
```

## Files touched

- `cli/commands/sense.py` (new)
- `cli/crowe_logic.py` (import + `main.add_command(sense_cmd)` after doctor)
- `tests/test_sense_cmd.py` (new, 25 tests against a stub node+relay on an ephemeral port)
- `tests/test_profile_branding.py` (adds `cli/commands/sense.py` to the file list that
  is grepped for a hardcoded `crowe-logic login`)

Deliberate wording: the group's help line is "The sensor node: ..." rather than
"Crowe Sense" because `test_customer_help_mentions_crowe_only_in_the_tagline_and_crowe_id`
greps a customer profile's `--help` for the word Crowe. The first draft failed that test.

## Test command and result

```
cd $SCRATCH/foundry-sense
PYTHONPATH=$PWD:$HOME/Projects/crowe-agent-core COLORTERM=truecolor TERM=xterm-256color \
  ~/Projects/crowe-logic-foundry/.venv-cp/bin/python -m pytest -q -p no:cacheprovider
```

Targeted run (`tests/test_sense_cmd.py tests/test_version_metadata.py tests/test_profile_branding.py`):

```
.....................................                                    [100%]
37 passed in 8.52s
```

Full suite in the worktree:

```
FAILED tests/test_cli_models_sync.py::test_models_sync_warns_when_output_is_shadowed
1 failed, 2215 passed, 78 warnings in 70.29s (0:01:10)
```

The one failure is not from this change: that test asserts
`project_root.name == "crowe-logic-foundry"`, so it fails in any worktree whose
directory has another name. The same test passes on the main checkout
(`1 passed in 0.22s`, run there read-only). Left as is, out of scope.

## Not done

- Not pushed; not merged; version not bumped (next release carries it).
- `check` depends on `~/crowe-sense/analysis/sense_check.py`, which lands when the
  analysis package is subtreed into the monorepo. Until then it exits 2 and says so.
- No `crowe sense serve` or local API here; the node's own API is the firmware's job.
