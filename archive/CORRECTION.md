# Zenodo 10.5281/zenodo.20722953: exact correction text

Status: DRAFTED 2026-08-04, NOT YET PUSHED. Requires a Zenodo token or a browser
session; neither is available to the agent.

Record: https://zenodo.org/records/20722953
Edit:   https://zenodo.org/uploads/20722953
State:  published 2026-06-16, CC-BY-4.0, one file (crowe-sense-aggregated.tar.gz)

Metadata edits on a published Zenodo record keep the same DOI. Replacing the file
requires publishing a New Version, which mints a versioned DOI under the same concept
DOI. Do the metadata edit first; it is the part that shows up in a citation.

---

## Field 1: Title (replace)

Crowe Sense: Mushroom Cultivation Environmental Telemetry (Aggregated) [CORRECTED 2026-08-04: not verified sensor measurements]

## Field 2: Description (replace entirely)

HTML, paste as-is into the description editor.

```html
<p><strong>CORRECTION NOTICE, issued 2026-08-04 by the depositor.</strong> The
original description of this record, published 2026-06-16, presented these data as
sensor readings from a commercial mushroom cultivation facility. That description is
withdrawn. The zone channels in this deposit are not verified sensor measurements of
the zones they are labelled with. No physical sensors were installed in the tents
named tent-1 and tent-2. This correction is issued voluntarily and was not prompted
by a third party.</p>

<p><strong>Basis for the correction.</strong> Two structural tests were applied to the
hourly table. The first measures day-to-day offset scatter against the channel's own
sampling-noise floor: real days inherit an offset from outside weather and hold it
across all 24 hours. The second measures lag-1 autocorrelation of residuals from the
hour-of-day curve: thermal mass makes real residuals positively autocorrelated. Across
20 days, 0 of the 6 tested tent channels (temperature, humidity and CO2 for both
tents) show day-to-day variation distinguishable from sampling noise, and their
residuals are negatively autocorrelated, which physical heat capacity cannot produce.
As an illustration that needs no statistics: the hourly mean temperature in tent-1 at
11:00 UTC falls between 23.949 and 23.978 C on every one of those 20 days, a spread of
0.029 C, in a column whose daily swing runs from 18.0 to 24.0 C. The widest across-day
spread at any fixed hour in that column is 0.212 C. Simulation of the same diurnal
curve with realistic weather produces day-to-day scatter 27 to 135 times the noise
floor. Thresholds were calibrated by simulation rather than chosen by hand.</p>

<p><strong>What this asserts, and what it does not.</strong> It asserts that the tent
temperature, humidity and light channels, and the VPD, dew point and fruiting score
channels derived from them, must not be treated as measurements of a growing
environment. It does not assert that every value in the deposit was fabricated. CO2,
in a separate higher-cadence export, shows lag-1 autocorrelation of +0.72 decaying
across successive lags, a structure consistent with a physical process; its origin has
not been established, and it is described here as unverified rather than as either
measured or synthetic. The provenance of the channels labelled hood-1 (flow hood) and
pi (controller health) was not tested and is likewise unestablished. The daemon that
produced the data could not be examined: its host has been unreachable since
2026-07-07.</p>

<p><strong>What remains accurate.</strong> The file inventory is unchanged and
correctly describes the files: 469 hourly rows across 13 features and one timestamp
column, per-metric summary statistics, and the metric and zone inventory. The scope
note in the original release also stands: no cultivation outcome labels (yield or
quality) are included, and supervised yield or quality prediction was and remains out
of scope.</p>

<p><strong>Recommended use.</strong> These files remain usable as a time series of
unverified provenance, for example for pipeline testing, tooling development or
teaching. They are not evidence about conditions inside a mushroom cultivation
facility, must not be cited as measured environmental telemetry, and must not be used
to tune or benchmark a growing environment. Readers who have already cited this record
as measured data are asked to note this correction. The test code that produced the
figures above is available from the depositor on request.</p>

<p><em>Original description, retained for the record:</em> A continuously operating,
multi-zone environmental telemetry dataset from a commercial mushroom cultivation
facility (Southwest Mushrooms, Phoenix, Arizona). The full raw stream comprises
3,596,420 sensor readings spanning 2026-05-24 to 2026-06-16 (23.16 continuous days),
20 metrics across two fruiting tents, a laminar flow hood, and controller health, with
derived agronomic channels (VPD, dew point, fruiting score, CO2 trend). This deposit
provides aggregated and derived tables (hourly means and per-metric summary statistics)
that characterize the dataset; the full raw stream is proprietary and retained by Crowe
Logic, Inc. Environmental data only; cultivation outcome labels (yield and quality) are
not included and supervised prediction is out of scope for this release.</p>
```

## Field 3: Keywords (edit)

Remove: `environmental telemetry`
Add:    `simulated data`, `data provenance`, `correction`

Keep: mushroom cultivation, agtech, VPD, carbon dioxide, time series,
controlled environment agriculture, mycology

## Field 4: Version (edit)

`2026-06-16` becomes `2026-06-16 (corrected 2026-08-04)`

---

## Then: New Version, to put the correction inside the archive

The web description is not carried inside the downloaded tarball. Anyone who already
downloaded `crowe-sense-aggregated.tar.gz` has an archive whose README still makes the
original claim. To fix that, publish a New Version whose tarball contains the rewritten
`README.md` and `PROVENANCE-CORRECTION.md` from this directory alongside the unchanged
CSV and JSON files. The data files themselves are not altered; they are the evidence.

## Verification, after pushing

    curl -s https://zenodo.org/api/records/20722953 | python3 -c "import sys,json; m=json.load(sys.stdin)['metadata']; print(m['title']); print(m['description'][:400])"

Read the returned title and description text. An HTTP 200 is not verification.

## If you prefer to escalate

Full withdrawal remains available: Zenodo support can tombstone a published record on
the depositor's request, leaving the DOI resolving to a withdrawal notice. That is the
stronger remedy for data that was never measured, and it is one email away.
