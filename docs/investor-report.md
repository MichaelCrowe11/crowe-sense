# Crowe Sense, investor report (September 2026)

Crowe Logic, Inc., Phoenix, Arizona. Prepared 2026-09-01 for a list of thirty investors
and funders (`docs/investors-30.csv`). Every number below is either measured in this
repository on that date or marked as a proposal. Nothing in it is a projection dressed
as a fact.

## In one paragraph

Crowe Sense is a sensing node for a growing room: a Raspberry Pi 5, four Sensirion and
Bosch sensors under a louvered radiation shield, a 3D-printed housing, about $280 in
parts. It keeps every reading on the node, serves them on the local network, and pushes
signed batches to a relay so the same numbers appear on six surfaces the company already
ships: the desktop app, the web app, the phone, Cortex, the terminal, and any screen that
mounts one tag. Readings are judged against 43 condition bands extracted from the
founder's own 68-video cultivation corpus, each cited to the clip it came from. The
software is built and tested. No node has yet run with physical sensors in a room. This
raise puts twenty-five of them in ten growers' rooms and proves the data with the same
test that caught the company's own synthetic stream in August.

## What exists today (measured 2026-09-01)

| Piece | State | Evidence |
|---|---|---|
| Firmware 0.2.0 (sampler, uploader, local API, watchdog, 6 drivers) | built | 51 tests, ruff clean, `firmware/` |
| Relay (Cloudflare Worker: signed ingest, D1, R2, Crowe ID reads) | built, not deployed | 7 end-to-end tests, `relay/` |
| Contract every surface shares | written | `contracts/telemetry-v1.md` |
| Desktop app integration (Environment lane fills itself) | branch `feat/crowe-sense` | 14 tests + 67 parity tests |
| Terminal (`crowe sense`, 7 subcommands) | branch `feat/crowe-sense` | 25 tests; full suite 2,215 green |
| Cortex panel | branch `feat/crowe-sense` | 8 tests + 28 adjacent, typecheck and build clean |
| Web edge (`/app/sense/*`) | patched, awaiting deploy | `integrations/web/` |
| Phone and Mac client 0.2.0 (direct or cloud source) | compiles | `app/` |
| House: embeddable panel + kiosk | built | `integrations/house/` |
| Enclosures: indoor radiation-shield head; field variant with drive and hotspot bays | parametric OpenSCAD | `site/model/`, `hardware/enclosure/` |
| Practice envelope: 43 cited condition bands, provenance test, stage and harvest logs | built | `analysis/` |
| Node BOM | priced live 2026-08-31 | $278 per node at 4 GB, `hardware/SHOPPING-LIST.md` |

## What is not proven, said first

**No Crowe Sense node has run with physical sensors in a growing room.** An earlier
daemon ran the whole software path for 23 days in May and June 2026 and produced
3,596,420 rows across 20 metrics. On 2026-08-04 the founder's own provenance test
(`analysis/provenance_check.py`) showed the tent temperature, humidity and light channels
were not sensor measurements; no sensors had been installed in those tents. The founder
confirmed it the same day and drafted a correction to the published Zenodo record
(10.5281/zenodo.20722953). That correction is written and, as of this report, not yet
pushed to Zenodo; it goes up before this report goes out.

**No revenue on this product.** The company's software surfaces have no paying
subscribers. The founder's businesses have sold cultivation products and courses; none of
that is attributed here.

**Yield prediction is not built.** The dataset that would train it (sensor windows joined
to harvest outcomes) has zero labelled rows. The tools to log stages and harvests exist;
the pilot fills them.

The reason to say this first: the provenance test is the asset. A company that caught
its own synthetic data, published the method, and gates every future dataset on it is
selling something a sensor vendor cannot: numbers a grower can trust.

## Why this founder

Michael Crowe has grown mushrooms since 2005, starting at fifteen, about ten of those
years commercially (Southwest Mushrooms, Phoenix; the farm closed in February 2025).
About 195,000 people subscribe to his cultivation channel; 68 of those videos were
parsed into 642 numeric constants, of which 43 survive as condition bands a sensor can be
judged against, with a documented rule that a band needs two independent statements
before it judges anything. Nobody else can ship that layer, because nobody else has the
corpus. He also built every surface in the table above.

## The device, in one table

| | |
|---|---|
| Compute | Raspberry Pi 5, 4 GB, active cooler, 64 GB microSD |
| Sensors | SCD41 (NDIR CO2, T, RH), SHT45 (reference T, RH), BME688 (VOC, pressure), VEML7700 (lux); SDP810 on the flow-hood node |
| Housing | 3D-printed PETG, louvered radiation-shield head, about 350 g, 14 h print |
| On the node | SQLite (WAL), local API on :8078 with a kiosk page, Ed25519-signed uploads |
| Cloud | one Cloudflare Worker, D1 (30 days hot), R2 (raw batches forever), Crowe ID on every read |
| Parts cost | $278 (4 GB), $343 (8 GB); prices read live 2026-08-31 |
| Proposed price | $449 per node, relay included with any paid Crowe ID tier (to be set after the pilot) |

## The ask: $175,000 on a SAFE

| Use | Amount |
|---|---|
| Pilot hardware: 25 nodes, printer, reference instruments, spares | $12,000 |
| Hardware engineering, contract: sensor-head thermal validation, calibration jig, enclosure DFM, pre-compliance | $35,000 |
| Founder, twelve months | $60,000 |
| Pilot program: ten growers, installs, travel, stipends | $15,000 |
| Compliance and safety review, product insurance | $10,000 |
| Legal: SAFE, IP assignment, provisional filing on the envelope method | $8,000 |
| Calibration and reference instruments | $4,000 |
| Contingency (18%) | $31,000 |
| **Total** | **$175,000** |
| Cloud, analytics, model inference | $0: covered by credits already held (below) |

Credits on hand, 2026-09-01, all unspent on this product: Cloudflare $99,657 (to June
2027, under 1% used), Azure $20,000, PostHog $50,000, and $13,500 in other unclaimed
credits. The relay, the archive, the analytics and the inference behind the apps run on
those for the life of the pilot, which is why the raise buys hardware and people only.

A $60,000 first tranche (angel or grant) funds lines one, two, seven and half of four,
and reaches the day-90 milestone.

## Milestones (dated from close)

| Day | Milestone | How it is verified |
|---|---|---|
| 30 | Five nodes in real rooms at the founder's site and two pilot growers | first week of data passes `provenance_check.py` (exit 0), published with the run log |
| 90 | Twenty-five nodes at ten growers; all six surfaces in weekly use | relay `sense_node_seen_daily` shows 25 nodes reporting on 6 of 7 days; PostHog funnel paired to day-7 retention above 80% |
| 180 | Twenty labelled harvests; Western SARE application submitted (due 2026-10-28, $35,000, non-dilutive) | `datasets/outcomes.csv` row count; SARE confirmation |
| 365 | One hundred nodes shipped at $449; the supervised yield model trained on real labels or a published reason it cannot be yet | shipping records; a model card with held-out error, or the negative result |

## Unit economics, proposed

| | Per node |
|---|---|
| Parts | $278 |
| Print, assembly, test (1.5 h) | $40 |
| Landed cost | $318 |
| Price | $449 |
| Gross margin | 29% at pilot volume; parts fall about 20% at 100 units |
| Cloud cost | $0 through June 2027 on credit; under $1 per node-month after |

## Risks, plainly

| Risk | What is done about it |
|---|---|
| Pi 5 pricing (DRAM shortage doubled 2024 prices) | 4 GB board, and the firmware runs on a Pi 4 or a Compute Module if it comes to that |
| Sensor drift, especially NDIR CO2 | SHT45 as reference, SCD41 automatic self-calibration on, every reading carries its driver and a quality flag; reference instruments in the budget |
| A second provenance failure | the test runs on every node's first week and is published with the data |
| Founder dependence | every surface, the contract and the setup pipeline are documented in this repo; a contractor built the desktop and Cortex integrations from the contract alone |
| Market size | not claimed here; the pilot measures whether ten growers keep the nodes plugged in |

## The list of thirty

`docs/investors-30.csv`: ten agtech and controlled-environment funds that do pre-seed,
six hardware and climate seed funds, eight Arizona programs and angel groups, six
non-dilutive programs. Each row carries the one-sentence reason it fits and a URL
verified active in 2025 or 2026. Contact names are deliberately absent; they change,
and a wrong one costs more than a blank.

## Where everything is

`github.com/MichaelCrowe11/crowe-sense`, branch `integrate/2026-09-01`: firmware,
relay, contract, enclosures, archive with the correction, analysis, the six integrations,
the shopping list, the setup pipeline, and this report.
