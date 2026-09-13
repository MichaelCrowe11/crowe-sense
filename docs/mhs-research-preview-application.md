# Model Hardware Standard research preview: application draft

For Michael to submit at https://www.modelhardwarestandard.com/ (Apply for access).
Drafted 2026-09-13. Everything below is true of the repository on that date; nothing
is promised that is not built. Adjust the contact block and send.

## Organization

Crowe Logic, Inc. (Phoenix, Arizona). Michael Crowe, founder. michael@crowelogic.com.
Also operating Southwest Mushrooms, a commercial mushroom farm, which is where the
hardware runs.

## Use case, in one paragraph

Environmental sensing and, next, environmental control for controlled-environment
agriculture: mushroom fruiting rooms, incubation and laminar flow hoods. Today an
agent reads CO2, temperature, humidity, VPD, light and hood prefilter pressure from a
Raspberry Pi node and reasons about a grow against documented practice. The next
step is closing the loop on fresh-air exchange, humidification and lighting, where a
wrong write spoils a crop and a stuck actuator can flood a room. We want to do that
on a shared standard with device-enforced limits rather than on bespoke integrations.

## Hardware

- Crowe Sense v1 node: Raspberry Pi 5, Sensirion SCD41 (NDIR CO2, T, RH), Sensirion
  SHT45, Bosch BME688, Vishay VEML7700, Sensirion SDP810-500Pa on the hood variant;
  three status LEDs and a hotspot power-cycle line on GPIO. Open hardware: BOM,
  enclosures (OpenSCAD) and pinouts in the repository.
- Planned actuators: 24 V exhaust fan via relay, ultrasonic humidifier via relay,
  LED lighting via PWM driver, all on the same node.
- Software today: Python firmware (sampler, local HTTP API, signed uploader,
  watchdog), a Cloudflare relay, a device descriptor, an operations registry with
  bounds and cooldowns enforced on the node, an MCP server, a CLI, and an Electron
  agent harness that requires a per-call operator approval for any physical write.

## What we have built toward the standard, and what we have not

Built, from the public description of MHS: a descriptor that lists what the device
measures, what can be adjusted and which limits are enforced, with each limit naming
its enforcer and carrying a test; `read` and `write` as the only primitives, reached
over MCP, a CLI and HTTP; operator notes ("tags") compiled into the descriptor and
kept descriptive; limits enforced by the one process that owns the pins,
independent of the model; honest operation states including `unknown`.

Not built: any claim of conformance. The specification is not public, so our
descriptor uses a Crowe schema id and the repository says so. We would like to
replace that with the real thing.

## Why us

- A real, small, safety-relevant physical domain where the failure modes are
  well understood (a room, not a laser) and where an agent already has work to do.
- Raspberry Pi is already an MHS partner; our node is a Pi with I2C sensors, which
  should make a reference driver straightforward and reusable by other Pi users.
- We publish: Apache 2.0 firmware, a versioned contract, and a provenance test that
  caught our own bad dataset. Findings from the preview would be reported the same way.

## What we would do in the preview

1. Port the Crowe Sense driver to the MHS driver format and ship it as open source.
2. Add the first actuator (exhaust fan) under MHS-enforced bounds and interlocks, and
   run a two-week fruiting cycle with an agent in the loop and a person on approval.
3. Report integration time, refusals, near misses and operator-approval load, with
   the data.

## Repository

https://github.com/MichaelCrowe11/crowe-sense (device, firmware, relay, contracts)
