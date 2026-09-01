# Mobile (and macOS): the Tauri app in `app/`

`app/` is the Crowe Sense client for iPhone and Mac, 0.2.0. The Rust side does the
fetch (`fetch_json`), so the node can stay plain HTTP on the LAN or over Tailscale and
the relay bearer never sits in a URL. The page in `app/dist/index.html` chooses the
source per the contract: direct (node URL) or cloud (relay + node id + Crowe ID token).

Verified 2026-09-01: `cargo check` on the backend finishes clean (38 s, host target).
Not verified: an iOS build this session (the keychain step below needs Michael at the
Mac), and a run against a live node (none reachable).

## Build

macOS: `cd app && npm install && npm run tauri -- build` produces `Crowe Sense.app` and a
`.dmg` under `app/src-tauri/target/release/bundle`.

iOS (from the 2026-07 notes, all still true):
1. `export PATH="$HOME/.cargo/bin:$PATH"` first; Homebrew's cargo shadows rustup and has no iOS std.
2. Team `6QLMV9UCPP` is already in `tauri.conf.json`; the only valid identity in the keychain is `Apple Development: Created via API (7M3Q52T3PW)`.
3. Once per login session, at the Mac (needs the login password):
   `security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k '<pw>' ~/Library/Keychains/login.keychain-db`
4. `set -a; source ~/.config/crowe/secrets.env; set +a; export PATH="$HOME/.cargo/bin:/tmp/xcbwrap:$PATH"; npm run tauri -- ios build --debug`
   (the `xcbwrap` shim injects the App Store Connect key flags Tauri does not pass).
5. `xcrun devicectl device install app --device 00008140-000A113A3611801C <path>.ipa`

## Not done

Crowe ID sign-in inside the app. Today cloud mode takes a pasted access token (from
`crowe whoami --token`). The next step is the same PKCE flow the web edge runs, opened
in the system browser from Tauri and returned by a custom URL scheme; the relay needs
nothing new for it.
