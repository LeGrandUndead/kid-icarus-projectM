//! The game's out-of-stage menus on one PC screen.
//!
//! While a menu screen is up (`set_menu_overlay`), the game still draws its
//! lower screen, but without its full-screen backgrounds and over a clear,
//! transparent buffer, with the alpha it writes turned into coverage. The
//! presenter then lays that picture over the full-window upper picture (the
//! room, the previews): the game's own buttons, text, animation, sounds and
//! touch handling, with no second screen around them. Pure policy here; the
//! renderer hooks are in `raster::hardware` and `memory_fill`.

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

static OVERLAY: AtomicBool = AtomicBool::new(false);
/// the lower screen's color buffer: address in the high half, bytes low.
static BOTTOM: AtomicU64 = AtomicU64::new(0);

/// The frontend shows a menu screen as one picture over the other.
pub fn set_menu_overlay(on: bool) {
    if OVERLAY.swap(on, Ordering::Relaxed) != on {
        log::info!("menu screen overlay {}", if on { "on" } else { "off" });
    }
}

pub(crate) fn menu_overlay() -> bool { OVERLAY.load(Ordering::Relaxed) }

/// The lower screen was drawn into this buffer (physical address, bytes).
pub(crate) fn note_bottom_target(address: u32, bytes: u32) {
    BOTTOM.store((address as u64) << 32 | bytes as u64, Ordering::Relaxed);
}

/// The part of a fill over `start..start+len` that lands on the lower
/// screen's buffer, as offsets into the fill, while the overlay is on: it
/// is cleared to transparent instead of the game's background colour.
pub(crate) fn transparent_part(start: u32, len: u32) -> Option<std::ops::Range<usize>> {
    if !menu_overlay() { return None; }
    let packed = BOTTOM.load(Ordering::Relaxed);
    let (address, bytes) = ((packed >> 32) as u32, packed as u32);
    overlap(start, len, address, bytes)
}

fn overlap(start: u32, len: u32, address: u32, bytes: u32) -> Option<std::ops::Range<usize>> {
    if bytes == 0 { return None; }
    let (lo, hi) = (start.max(address), (start + len).min(address + bytes));
    (lo < hi).then(|| (lo - start) as usize..(hi - start) as usize)
}

/// The PICA blend function a lower-screen draw uses under the overlay: the
/// colour is blended as the game asks, and alpha accumulates coverage
/// (`over`, premultiplied), so the presenter can lay the picture over
/// another. Additive draws (glows) leave coverage alone, they only add light.
pub(crate) fn coverage_blend(config: u32) -> u32 {
    const ONE: u32 = 1;
    const ZERO: u32 = 0;
    const ONE_MINUS_SRC_ALPHA: u32 = 7;
    let additive = (config >> 20) & 0xF == ONE;
    let (src, dst) = if additive { (ZERO, ONE) } else { (ONE, ONE_MINUS_SRC_ALPHA) };
    // keep the colour equation and factors; alpha equation ADD
    (config & 0x00FF_00FF) | src << 24 | dst << 28
}

/// A draw covering the whole lower screen (bounds in its 320x240 pixels) is
/// a background, a frame or a full-screen tint: not part of the menu.
pub(crate) fn is_background(bounds: [f32; 4]) -> bool {
    bounds[0] <= 4.0 && bounds[1] <= 4.0 && bounds[2] >= 316.0 && bounds[3] >= 236.0
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn coverage_replaces_only_the_alpha_factors() {
        // SRC_ALPHA, ONE_MINUS_SRC_ALPHA for both: alpha becomes ONE, 1-SRC
        assert_eq!(coverage_blend(0x7676_0000), 0x7176_0000);
        // additive colour keeps coverage: ZERO, ONE
        assert_eq!(coverage_blend(0x1616_0000), 0x1016_0000);
        // the colour equation is kept, the alpha one becomes ADD
        assert_eq!(coverage_blend(0x7676_0304), 0x7176_0004);
    }
    #[test]
    fn only_the_lower_screens_bytes_of_a_fill_are_cleared() {
        assert_eq!(overlap(0x100, 0x100, 0x180, 0x200), Some(0x80..0x100));
        assert_eq!(overlap(0x100, 0x100, 0x000, 0x140), Some(0..0x40));
        assert_eq!(overlap(0x100, 0x100, 0x300, 0x100), None);
        assert_eq!(overlap(0x100, 0x100, 0x100, 0), None);
    }
    #[test]
    fn full_screen_draws_are_backgrounds() {
        assert!(is_background([0.0, 0.0, 320.0, 240.0]));
        assert!(is_background([-10.0, -2.0, 330.0, 250.0]));
        assert!(!is_background([0.0, 0.0, 320.0, 200.0]));
        assert!(!is_background([20.0, 20.0, 300.0, 220.0]));
    }
}
