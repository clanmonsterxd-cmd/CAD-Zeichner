use serde::{Deserialize, Serialize};
use std::error::Error;

const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");
const GITHUB_REPO: &str = "clanmonsterxd-cmd/CAD-Zeichner";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateInfo {
    pub available: bool,
    pub current_version: String,
    pub latest_version: String,
    pub download_url: Option<String>,
}

#[derive(Debug, Deserialize)]
struct GitHubRelease {
    tag_name: String,
    assets: Vec<GitHubAsset>,
}

#[derive(Debug, Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
}

pub async fn check_for_updates() -> Result<UpdateInfo, Box<dyn Error>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", GITHUB_REPO);
    
    let client = reqwest::Client::builder()
        .user_agent("simple-cad-updater")
        .build()?;
    
    let response = client.get(&url).send().await?;
    
    if !response.status().is_success() {
        return Ok(UpdateInfo {
            available: false,
            current_version: CURRENT_VERSION.to_string(),
            latest_version: CURRENT_VERSION.to_string(),
            download_url: None,
        });
    }
    
    let release: GitHubRelease = response.json().await?;
    
    // Entferne 'v' prefix falls vorhanden
    let latest_version = release.tag_name.trim_start_matches('v');
    
    // Finde Windows .exe Asset
    let exe_asset = release.assets.iter().find(|asset| {
        asset.name.ends_with(".exe") && asset.name.to_lowercase().contains("windows")
    });
    
    let download_url = exe_asset.map(|a| a.browser_download_url.clone());
    
    // Vergleiche Versionen
    let is_newer = is_version_newer(CURRENT_VERSION, latest_version);
    
    Ok(UpdateInfo {
        available: is_newer && download_url.is_some(),
        current_version: CURRENT_VERSION.to_string(),
        latest_version: latest_version.to_string(),
        download_url,
    })
}

pub async fn download_and_install_update(download_url: &str) -> Result<(), Box<dyn Error>> {
    // Download neue Version
    let client = reqwest::Client::builder()
        .user_agent("simple-cad-updater")
        .build()?;
    
    let response = client.get(download_url).send().await?;
    let bytes = response.bytes().await?;
    
    // Aktuellen Pfad ermitteln
    let current_exe = std::env::current_exe()?;
    let temp_exe = current_exe.with_extension("exe.new");
    
    // Neue Version temporär speichern
    std::fs::write(&temp_exe, bytes)?;
    
    // Self-update durchführen
    self_replace::self_replace(&temp_exe)?;
    
    // Cleanup
    let _ = std::fs::remove_file(&temp_exe);
    
    Ok(())
}

fn is_version_newer(current: &str, latest: &str) -> bool {
    let parse_version = |v: &str| -> Vec<u32> {
        v.split('.')
            .filter_map(|s| s.parse().ok())
            .collect()
    };
    
    let current_parts = parse_version(current);
    let latest_parts = parse_version(latest);
    
    for (c, l) in current_parts.iter().zip(latest_parts.iter()) {
        if l > c {
            return true;
        } else if l < c {
            return false;
        }
    }
    
    latest_parts.len() > current_parts.len()
}

// Alternative: Verwende self_update crate
pub async fn auto_update_with_crate() -> Result<self_update::Status, Box<dyn Error>> {
    let status = self_update::backends::github::Update::configure()
        .repo_owner("clanmonsterxd-cmd")
        .repo_name("simple-cad")
        .bin_name("simple_cad")
        .current_version(CURRENT_VERSION)
        .build()?
        .update()?;
    
    Ok(status)
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_version_comparison() {
        assert!(is_version_newer("0.1.0", "0.2.0"));
        assert!(is_version_newer("0.1.0", "0.1.1"));
        assert!(!is_version_newer("0.2.0", "0.1.0"));
        assert!(!is_version_newer("0.1.1", "0.1.1"));
    }
}