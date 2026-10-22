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
/// lower-screen draws and fills still to describe in the log after the
/// overlay comes on (to see what a menu is made of)
static TRACE: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);

/// Describes the next lower-screen draw or fill in the log, a bounded
/// number after each time the overlay comes on.
pub(crate) fn trace(what: std::fmt::Arguments) {
    if TRACE.load(Ordering::Relaxed) == 0 { return; }
    TRACE.fetch_sub(1, Ordering::Relaxed);
    log::info!(target: "zakuro::menu_trace", "{what}");
}
/// the lower screen's color buffer: address in the high half, bytes low.
static BOTTOM: AtomicU64 = AtomicU64::new(0);

/// The frontend shows a menu screen as one picture over the other.
pub fn set_menu_overlay(on: bool) {
    if OVERLAY.swap(on, Ordering::Relaxed) != on {
        log::info!("menu screen overlay {}", if on { "on" } else { "off" });
        if on { TRACE.store(120, Ordering::Relaxed); }
    }
}

pub(crate) fn menu_overlay() -> bool { OVERLAY.load(Ordering::Relaxed) }

/// The lower screen was drawn into this buffer (physical address, bytes).
pub(crate) fn note_bottom_target(address: u32, bytes: u32) {
    BOTTOM.store((address as u64) << 32 | bytes as u64, Ordering::Relaxed);
}

/// Whether a display transfer from the buffer at `address` should keep its
/// alpha in the GPU copy: the lower screen's buffer while the overlay is on.
pub(crate) fn keeps_alpha(address: u32) -> bool {
    menu_overlay() && (BOTTOM.load(Ordering::Relaxed) >> 32) as u32 == address
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

/// A draw whose triangles (in the lower screen's 320x240 pixels) cover
/// most of the screen is a background, a tiled sky, a frame or a full-screen
/// tint: not part of the menu. Button groups leave gaps between buttons.
pub(crate) fn is_background(triangles: impl Iterator<Item = [[f32; 2]; 3]>) -> bool {
    let clamp = |p: [f32; 2]| [p[0].clamp(0.0, 320.0), p[1].clamp(0.0, 240.0)];
    let area: f32 = triangles.map(|t| {
        let [a, b, c] = t.map(clamp);
        ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])).abs() * 0.5
    }).sum();
    area >= 0.85 * 320.0 * 240.0
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
    fn quad(l: f32, t: f32, r: f32, b: f32) -> [[[f32; 2]; 3]; 2] {
        [[[l, t], [r, t], [l, b]], [[r, t], [r, b], [l, b]]]
    }
    #[test]
    fn draws_covering_the_screen_are_backgrounds_and_button_groups_are_not() {
        assert!(is_background(quad(0.0, 0.0, 320.0, 240.0).into_iter()));
        assert!(is_background(quad(-10.0, -2.0, 330.0, 250.0).into_iter()));
        // a sky of 4x4 tiles
        let tiles = (0..16).flat_map(|i| quad((i % 4) as f32 * 80.0, (i / 4) as f32 * 60.0, (i % 4 + 1) as f32 * 80.0, (i / 4 + 1) as f32 * 60.0));
        assert!(is_background(tiles));
        // six buttons spread over the screen, gaps between them
        let buttons = (0..6).flat_map(|i| quad((i % 3) as f32 * 107.0 + 8.0, (i / 3) as f32 * 120.0 + 10.0, (i % 3) as f32 * 107.0 + 98.0, (i / 3) as f32 * 120.0 + 105.0));
        assert!(!is_background(buttons));
        assert!(!is_background(quad(0.0, 0.0, 320.0, 200.0).into_iter().take(1)));
    }
}
