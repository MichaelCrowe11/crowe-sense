# NSF SBIR Phase I (America's Seed Fund)

DRAFT, not sent. Type: non-dilutive. Stage or award: $305,000 maximum (solicitation NSF 26-510), award ceiling not guaranteed.  
Verified 2026-08-31/09-01 at https://seedfund.nsf.gov/solicitations/  
Fit: NSF explicitly funds small-business deep-tech hardware R&D, and a multi-sensor Pi-based node with a Cloudflare relay is exactly that kind of hardware-plus-software integration project.  
Caveat: 6 to 18 month project period, no cost share; recurring deadlines including Nov 4 2026; applicant is the for-profit small business directly.

---

To: (named person, verified this week)  
Subject: Project Pitch: Crowe Sense, verifiable environmental sensing for indoor agriculture

The technical innovation is not the sensors; it is the provenance layer. Grow-room telemetry today cannot be told from a plausible simulation, and I proved that on my own data. Crowe Sense pairs a low-cost multi-sensor node with a structural test of the variation (day-to-day offset against the noise floor, residual autocorrelation) that rejects data a physical room could not have produced, and a practice envelope that judges readings against cited grower knowledge. The Phase I question is whether that test holds across sensor types and room regimes on real deployments.

Crowe Sense is a sensing node for a growing room: a Raspberry Pi 5 and four Sensirion and Bosch sensors under a louvered radiation shield, in a 3D-printed housing, about $280 in parts. Every reading stays on the node and a signed copy goes to a relay, so the same numbers show up in the desktop app, the web app, the phone, the terminal and any screen in the room. The readings are judged against 43 condition bands taken from my own cultivation videos, each cited to the clip it came from.

The software is built and tested end to end. No node has yet run with physical sensors in a room, and I say that first because in August my own provenance test showed an earlier dataset of mine was not sensor data, and I pulled the claim and wrote the correction. That test now gates everything this company publishes. I have grown mushrooms since 2005, about ten of those years commercially, and roughly 195,000 people follow the channel where I teach it.

This is a draft of the Project Pitch NSF requires before a full proposal; the next window opens November 4, 2026.

The investor report is attached. The code, the firmware and the enclosure are public at https://github.com/MichaelCrowe11/crowe-sense

Michael Crowe
Founder, Crowe Logic
Cultivation intelligence for serious growers. Grower since 2005.

michael@crowelogic.com  |  crowelogic.com
Southwest Mushrooms on YouTube: youtube.com/@SouthwestMushrooms
