# House

House is named in the product brief as the fifth surface of the suite (desktop, web,
mobile, Cortex, House). As of 2026-09-01 there is no House repo, domain, memory note or
code anywhere on this machine or in the index; the CLI next-steps report of 2026-08-31
recorded the same finding. So this directory does not guess what House is. It gives House
the two things it will need whatever it turns out to be, and both are already built:

1. **`crowe-sense-panel.js`**: the whole Crowe Sense read surface as one dependency-free
   web component that any page can mount with a single tag. It reads the same contract
   the desktop, web, mobile and Cortex surfaces read, from a node directly or from the
   relay (with a bearer, or through the crowelogic.com session at `/app/sense/...`).
   `demo.html` shows it on the light editorial surface; the default theme is the dark
   console. Events `sense:data` and `sense:error` let a host page react.

2. **`kiosk/`**: the in-house display. The node itself serves its dashboard on :8078
   (`crowe-api.service`), and the kiosk autostart puts it fullscreen on a screen wired to
   the node, so a grow room has a live readout with no cloud, no phone and no login.
   Install on the node:
   ```
   sudo install -m 755 kiosk/crowe-sense-kiosk /usr/local/bin/crowe-sense-kiosk
   install -Dm644 kiosk/crowe-sense-kiosk.desktop ~/.config/autostart/crowe-sense-kiosk.desktop
   ```
   (The 2026-07 Pi had the dashboard service but no autostart; this closes that gap.)

When House gets a definition, the integration is: mount the panel, pass it the node path,
and pair nodes through the same `POST /v1/nodes` every other surface uses. Nothing in the
contract needs to change for it.
