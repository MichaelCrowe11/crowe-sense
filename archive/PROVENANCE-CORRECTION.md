# Provenance correction

Issued 2026-08-04 by the depositor, Michael Crowe (Crowe Logic, Inc.), voluntarily and
not at the prompting of any third party.

Applies to Zenodo record 10.5281/zenodo.20722953, published 2026-06-16 under CC-BY-4.0.

## The claim being withdrawn

The original release described this deposit as aggregated tables from "a continuously
operating, multi-zone environmental telemetry dataset from a commercial mushroom
cultivation facility," derived from "3,596,420 sensor readings."

The zone channels are not verified sensor measurements of the zones they are labelled
with. No physical sensors were installed in the tents named tent-1 and tent-2.

## How it was found

The defect was not visible in the values. Every number in the file is agronomically
plausible: over the source stream, temperature runs 17.4 to 24.5 C, humidity 75.6 to
94.3 percent, and CO2 550 to 1600 ppm. It is visible only in the structure of the
variation.

**Test 1, weather.** Remove the hour-of-day mean from each channel, average the
remainder over each calendar day, and compare that day-to-day scatter against the floor
that sampling noise alone would produce. Real days inherit an offset from outside
conditions and hold it across all 24 hours, so real data sits well above its noise
floor. A ratio near 1 means there is no weather in the file.

**Test 2, inertia.** Take the residuals from the diurnal curve hour to hour. Heat
capacity makes real residuals positively autocorrelated: a room that is warm at 14:00
is still warm at 15:00. Negative autocorrelation means each sample is an independent
draw around a smooth curve.

Thresholds were calibrated by simulation, 200 trials of `f(hour) + noise` over 20 days,
rather than chosen by hand:

| condition | day-offset ratio | hourly lag-1 |
|---|---|---|
| pure noise, no weather | ~1.0 | -0.00 |
| 0.3 C day-to-day offset | ~135 | +0.96 |
| persistent AR(1) weather | ~27 | +0.66 |

## Result

0 of 6 tested channels are consistent with measurement.

| channel | day SD | noise floor | ratio | lag-1 |
|---|---|---|---|---|
| tent-1 temperature | 0.0024 | 0.0035 | 0.68 | -0.288 |
| tent-1 humidity | 0.0073 | 0.0097 | 0.76 | -0.154 |
| tent-1 CO2 | 14.23 | 10.93 | 1.30 | +0.138 |
| tent-2 temperature | 0.0026 | 0.0041 | 0.63 | -0.331 |
| tent-2 humidity | 0.0092 | 0.0105 | 0.88 | -0.236 |
| tent-2 CO2 | 10.37 | 10.99 | 0.94 | -0.128 |

Every channel sits at or below its own noise floor, and the temperature and humidity
residuals are negatively autocorrelated, which physical thermal mass cannot produce.

The plainest illustration needs no statistics. In `cs_hourly.csv`, the hourly mean
temperature in tent-1 at 11:00 UTC falls between 23.949 and 23.978 C on every one of
the 20 days in the file. That is a spread of 0.029 C, across three weeks of late May
and June in Phoenix, Arizona, in a column whose daily swing runs from 18.0 to 24.0 C.
The widest across-day spread at any fixed hour in that column is 0.212 C. Light behaves
the same way: at a fixed hour the median across-day spread is 16 lux against a column
range of 70 to 11,940 lux.

## What this does not establish

**CO2 is not described here as synthetic.** In a separate, higher-cadence export at
17-second sampling, CO2 shows lag-1 autocorrelation of +0.72, decaying to +0.47 and
then -0.11 across successive lags, which is what a physical process looks like. In the
same export, temperature and humidity are white noise on a smooth curve at both
timescales. Whatever produced these files did not treat every channel alike. The origin
of the CO2 channel has not been established and it is described as unverified.

**The hood-1 and pi channels were not tested.** They are not carried in the aggregated
tables. Their provenance is unestablished, not disproved.

**The generator was not found.** The daemon and its data store are on a host that has
been unreachable since 2026-07-07, so the raw stream was never examined at source. The
conclusion above rests on the structure of the published data, corroborated by the
depositor's direct confirmation on 2026-08-04 that no physical tent sensors existed.

## A test that was run, and retracted

An earlier version of this analysis reported a third finding: that tent-1 and tent-2
were "one signal, two names," on the evidence that their hourly means differed by only
0.0135 C. That was wrong, and it is recorded here because a correction notice that
hides its own errors is worth less. Two tents in one climate-controlled space, averaged
over roughly 200 samples per hour, will differ by about that much even with two
independent sensors. Measured per-sensor noise of 0.150 C predicts an hourly twinning
SD of 0.0149 C against the 0.0135 C observed. The test was measuring arithmetic. It was
removed.

## Reproducing this

The test code (`provenance_check.py`) is available from the depositor on request. It
takes a SQLite database or the published `cs_hourly.csv` and exits 0 on pass, 1 on
fail, 2 on inconclusive. None of its tests ask whether the numbers look plausible. They
do. All of them ask whether the structure of the variation is one a sensor could
produce.

## What was done about it

The record's title and description were corrected on 2026-08-04 rather than withdrawn,
so that the DOI continues to resolve and this notice travels with any existing
citation. The three data files are unaltered. They are the evidence.

Anyone who cited this record as measured environmental telemetry is asked to note the
correction. Correspondence: through the Zenodo record.
