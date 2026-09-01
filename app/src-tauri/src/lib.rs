// Crowe Sense app backend. The Rust side performs the HTTP fetch (reqwest + rustls) so
// requests are NOT subject to iOS/macOS App Transport Security or browser CORS. That
// lets a node stay plain-HTTP on the LAN or over Tailscale with no certs, and lets the
// cloud relay be reached with a bearer the webview never has to expose in a URL.
//
// The webview decides WHERE to read (contracts/telemetry-v1.md): direct mode is the
// node's own API, cloud mode is the relay under /v1/nodes/<node>. This side only fetches.

#[tauri::command]
async fn fetch_json(url: String, token: Option<String>) -> Result<String, String> {
    if !(url.starts_with("http://") || url.starts_with("https://")) {
        return Err("url must start with http:// or https://".into());
    }
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(20))
        .build()
        .map_err(|e| e.to_string())?;
    let mut req = client.get(&url).header("accept", "application/json");
    if let Some(t) = token.filter(|t| !t.trim().is_empty()) {
        req = req.header("authorization", format!("Bearer {}", t.trim()));
    }
    let resp = req.send().await.map_err(|e| e.to_string())?;
    let status = resp.status();
    let text = resp.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        // The contract promises {"error","detail"}; surface the detail when it is there.
        let detail = serde_json::from_str::<serde_json::Value>(&text)
            .ok()
            .and_then(|v| v.get("detail").and_then(|d| d.as_str()).map(String::from))
            .unwrap_or_else(|| text.chars().take(200).collect());
        return Err(format!("{} {}", status.as_u16(), detail));
    }
    Ok(text)
}

/// Kept for one release so a webview built against 0.1.0 still works.
#[tauri::command]
async fn fetch_telemetry(hours: f64) -> Result<String, String> {
    fetch_json(format!("http://100.123.229.57:8078/api/data?hours={hours}"), None).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![fetch_json, fetch_telemetry])
        .run(tauri::generate_context!())
        .expect("error while running Crowe Sense");
}
