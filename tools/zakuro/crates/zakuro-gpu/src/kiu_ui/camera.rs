//! Gameplay lens scale (moved from the October 14 `dialogue` module). Saved
//! beside the profile's settings, never in the game's save data.
//!
//! A scale below 1 widens the projection only: the game still culls, aims
//! and draws screen effects for its original frustum, so enemies pop in at
//! the new edges and the reticle/damage effects keep the original frame.
//! The PC interface therefore starts at 1 (original view) and keeps the
//! wider view as an option until culling and aim follow it.
//!
//! They do when the game library has `tools/recomp/overrides/kiu-wide-view.c`:
//! the game's own camera is then widened (zakuro-core `kiu_wide_view.rs`),
//! which says so through `set_game_view`, and the renderer leaves the
//! world's projection alone.
use std::sync::{atomic::{AtomicBool, AtomicU32, Ordering}, OnceLock};

static GAME_VIEW: AtomicBool = AtomicBool::new(false);
static WORLD_SEEN: AtomicBool = AtomicBool::new(false);

/// The game widens its own camera (16:9 and the zoom): the world, markers
/// and reticle are already where they belong.
pub fn game_view() -> bool { GAME_VIEW.load(Ordering::Relaxed) }
pub fn set_game_view(on: bool) { GAME_VIEW.store(on, Ordering::Relaxed); }

/// A gameplay world draw (the perspective programs the wide view knows)
/// reached the top screen.
pub(crate) fn note_world() { WORLD_SEEN.store(true, Ordering::Relaxed); }
/// Whether one did since the last call.
pub fn take_world_seen() -> bool { WORLD_SEEN.swap(false, Ordering::Relaxed) }

/// The PC interface keeps its own value so the October 14 preview keeps its.
fn pc_interface() -> bool { std::env::var_os("KIU_NATIVE_UI").is_some() }

fn path() -> Option<std::path::PathBuf> {
    let name = if pc_interface() { "zakuro/pc-interface-camera.txt" } else { "zakuro/gameplay-camera.txt" };
    std::env::var_os("APPDATA").map(|p| std::path::PathBuf::from(p).join(name))
}

fn value() -> &'static AtomicU32 {
    static VALUE: OnceLock<AtomicU32> = OnceLock::new();
    VALUE.get_or_init(|| {
        let saved = path().and_then(|p| std::fs::read_to_string(p).ok());
        let value = std::env::var("KIU_GAMEPLAY_CAMERA_SCALE").ok().or(saved)
            .and_then(|v| v.trim().parse::<f32>().ok()).filter(|v| v.is_finite())
            .unwrap_or(if pc_interface() { 1.0 } else { 0.85 }).clamp(0.75, 1.0);
        AtomicU32::new(value.to_bits())
    })
}

pub fn scale() -> f32 {
    if !super::enabled() { return 1.0; }
    f32::from_bits(value().load(Ordering::Relaxed))
}

pub fn set_scale(v: f32) {
    if super::enabled() && v.is_finite() {
        let v = v.clamp(0.75, 1.0);
        value().store(v.to_bits(), Ordering::Relaxed);
        if let Some(path) = path() {
            if let Some(parent) = path.parent() { let _ = std::fs::create_dir_all(parent); }
            if let Err(error) = std::fs::write(path, format!("{v}\n")) {
                log::warn!("Could not save gameplay camera setting: {error}");
            }
        }
    }
}
