# Analytics: PostHog, and what goes in it

Michael asked on 2026-09-01 whether PostHog should be used for analytics, with $50k of
PostHog credit available and $13,500 in other unclaimed credits.

**Yes for product analytics. No for the sensor stream.**

PostHog is already the estate's identity spine (email is the person key everywhere, see
the unified email identity rule), so every Crowe Sense event joins the same person the
gateway, the desktop app and the store already know. What belongs there is the product
funnel, one event per human or node action:

| Event | Sent by | Properties |
|---|---|---|
| `sense_node_paired` | relay, on `POST /v1/nodes` | node, zone, tier |
| `sense_first_batch` | relay, first accepted ingest per node | node, minutes since pairing |
| `sense_node_seen_daily` | relay, one per node per day | node, readings that day, uptime share |
| `sense_panel_viewed` | each surface, on open | surface (desktop, web, mobile, cortex, cli, house), source (direct, cloud) |
| `sense_check_run` | CLI `crowe sense check` | zones judged, hours out of band |
| `sense_alert_fired` | later, the envelope alerts | metric, stage, duration |

That is a few hundred events a day at pilot scale. The funnel that matters to an investor
(paired -> first batch within an hour -> still reporting on day 7 -> panel opened weekly)
is a PostHog insight with no code.

What does not belong there: readings. A node produces about 150,000 readings a day; ten
nodes are 1.5 million events a day, which turns a $50k credit into a countdown and buys
nothing, because the apps read time series from the relay (D1 hot, R2 forever), not from
an event store. The credit is better spent on session replay for the web app during the
pilot, feature flags to roll the relay out node by node, and error tracking across the
surfaces.

The relay already has the seam: `sense_node_paired` and `sense_first_batch` fire from the
two places in `relay/src/index.js` that create a node and accept its first batch. Adding
them is a `fetch` to PostHog's capture endpoint with the project key as a Worker secret;
it is not wired today because the project key is not in this repo.

Credits, as of 2026-09-01, all unspent on this product: Cloudflare $99,657 (to 2027-06-16),
Azure $20,000 (Founders Hub), PostHog $50,000, other unclaimed $13,500 (provider to be
named). The software side of Crowe Sense runs on the first and the fourth; the raise in
`investor-report.md` therefore funds hardware and people, not servers.
