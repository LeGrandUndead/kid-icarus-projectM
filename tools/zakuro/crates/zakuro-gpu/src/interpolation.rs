//! The 60 FPS setting: frame interpolation on or off.
//!
//! The game keeps running its own 30 frames a second; the renderer draws
//! each frame a second time halfway towards the one before and shows that
//! picture in between (raster/hardware/twin.rs). Nothing the game runs or
//! keeps in memory changes, so this cannot break it the way running its
//! logic at 60 did (the white screens of chapter 9; that mode is gone, see
//! doc/FRAME_INTERPOLATION.md).
//!
//! Kept in `%APPDATA%/zakuro/frame-interpolation.txt` ("1" or "0"), on when
//! there is none. `KIU_INTERPOLATION=1`/`0` overrides it for one run. The
//! renderer picks the setting up at the end of each frame.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;

fn path() -> Option<std::path::PathBuf> {
    std::env::var_os("APPDATA")
        .map(|p| std::path::PathBuf::from(p).join("zakuro/frame-interpolation.txt"))
}

fn setting() -> &'static AtomicBool {
    static VALUE: OnceLock<AtomicBool> = OnceLock::new();
    VALUE.get_or_init(|| {
        let saved = path().and_then(|p| std::fs::read_to_string(p).ok());
        let on = std::env::var("KIU_INTERPOLATION")
            .ok()
            .or(saved)
            .map(|v| v.trim() == "1")
            .unwrap_or(true);
        AtomicBool::new(on)
    })
}

/// fast-forward shows frames back to back, nothing to show in between.
static FAST_FORWARD: AtomicBool = AtomicBool::new(false);

/// whether the player wants 60 FPS.
pub fn enabled() -> bool {
    setting().load(Ordering::Relaxed)
}

/// turns 60 FPS on or off from the next frame, and keeps the choice for the
/// next start.
pub fn set_enabled(on: bool) {
    setting().store(on, Ordering::Relaxed);
    if let Some(path) = path() {
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Err(error) = std::fs::write(path, if on { "1\n" } else { "0\n" }) {
            log::warn!("could not save the 60 FPS setting: {error}");
        }
    }
}

/// while on, no in-between frames are drawn; the setting itself is kept.
pub fn set_fast_forward(on: bool) {
    FAST_FORWARD.store(on, Ordering::Relaxed);
}

/// whether the renderer should draw in-between frames now.
pub(crate) fn wanted() -> bool {
    enabled() && !FAST_FORWARD.load(Ordering::Relaxed)
}
