//! A menu screen recomposed as one PC picture.
//!
//! While the presentation composes a menu (`set_composing`), the game still
//! draws its lower screen, but over a transparent buffer and without its
//! full-screen backdrops, with the alpha it writes turned into coverage. The
//! presenter can then lay parts of that picture (the save select's books, its
//! Back and How to Play buttons) anywhere over the upper picture: still the
//! game's own art, animation, sounds and touch handling, with no second screen
//! around them. Guest memory keeps what the game wrote; only the GPU copy
//! changes. Pure policy here; the renderer hooks are in `raster::hardware`
//! (draws, display transfers) and `Gpu::memory_fill`.

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

static COMPOSING: AtomicBool = AtomicBool::new(false);
/// the lower screen's color buffer: address in the high half, bytes low.
static BOTTOM: AtomicU64 = AtomicU64::new(0);

/// The presentation lays parts of the lower screen over the upper one.
pub fn set_composing(on: bool) {
    if COMPOSING.swap(on, Ordering::Relaxed) != on {
        log::info!("menu composition {}", if on { "on: the lower screen is drawn transparent" } else { "off" });
    }
}

pub(crate) fn composing() -> bool { COMPOSING.load(Ordering::Relaxed) }

/// The lower screen was drawn into this buffer (physical address, bytes).
pub(crate) fn note_bottom_target(address: u32, bytes: u32) {
    BOTTOM.store((address as u64) << 32 | bytes as u64, Ordering::Relaxed);
}

/// Whether a display transfer out of the buffer at `address` should keep
/// its alpha in the GPU copy: the lower screen's buffer while composing.
pub(crate) fn keeps_alpha(address: u32) -> bool {
    composing() && (BOTTOM.load(Ordering::Relaxed) >> 32) as u32 == address
}

/// The part of a fill over `start..start+len` that lands on the lower
/// screen's buffer, as offsets into the fill, while composing: the GPU copy
/// is cleared to transparent instead of the game's background colour.
pub(crate) fn transparent_part(start: u32, len: u32) -> Option<std::ops::Range<usize>> {
    if !composing() { return None; }
    let packed = BOTTOM.load(Ordering::Relaxed);
    overlap(start, len, (packed >> 32) as u32, packed as u32)
}

fn overlap(start: u32, len: u32, address: u32, bytes: u32) -> Option<std::ops::Range<usize>> {
    if bytes == 0 { return None; }
    let (lo, hi) = (start.max(address), start.saturating_add(len).min(address.saturating_add(bytes)));
    (lo < hi).then(|| (lo - start) as usize..(hi - start) as usize)
}

/// The PICA blend function a lower-screen draw uses while composing: the
/// colour is blended as the game asks, and alpha accumulates coverage
/// (premultiplied "over"), so the presenter can lay the picture over
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

/// A draw whose triangles (in the lower screen's 320x240 pixels) cover most
/// of the screen is a backdrop, a tiled sky, a frame or a full-screen tint:
/// not part of the menu. Button groups leave gaps between buttons.
pub(crate) fn is_backdrop(triangles: impl Iterator<Item = [[f32; 2]; 3]>) -> bool {
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
        // SRC_ALPHA, ONE_MINUS_SRC_ALPHA colour, alpha ONE/ZERO: alpha becomes ONE, 1-SRC
        assert_eq!(coverage_blend(0x0176_0000), 0x7176_0000);
        assert_eq!(coverage_blend(0x7676_0000), 0x7176_0000);
        // additive colour keeps coverage: ZERO, ONE
        assert_eq!(coverage_blend(0x1616_0000), 0x1016_0000);
        // the colour equation is kept, the alpha one becomes ADD
        assert_eq!(coverage_blend(0x0176_0004) & 0xFF, 0x04);
        assert_eq!(coverage_blend(0x0176_0400) & 0xFF00, 0);
    }
    #[test]
    fn fills_are_cleared_only_where_they_meet_the_lower_screen() {
        assert_eq!(overlap(0x100, 0x100, 0x180, 0x100), Some(0x80..0x100));
        assert_eq!(overlap(0x200, 0x100, 0x100, 0x180), Some(0..0x80));
        assert_eq!(overlap(0x100, 0x100, 0x300, 0x100), None);
        assert_eq!(overlap(0x100, 0x100, 0x100, 0), None);
    }
    fn quad(l: f32, t: f32, r: f32, b: f32) -> [[[f32; 2]; 3]; 2] {
        [[[l, t], [r, t], [l, b]], [[r, t], [r, b], [l, b]]]
    }
    #[test]
    fn draws_covering_the_screen_are_backdrops_and_button_groups_are_not() {
        assert!(is_backdrop(quad(0.0, 0.0, 320.0, 240.0).into_iter()));
        assert!(is_backdrop(quad(-284.0, -240.0, 604.0, 480.0).into_iter()), "the lined frame drawn past the edges");
        let tiles = (0..16).flat_map(|i| quad((i % 4) as f32 * 80.0, (i / 4) as f32 * 60.0, (i % 4 + 1) as f32 * 80.0, (i / 4 + 1) as f32 * 60.0));
        assert!(is_backdrop(tiles), "a sky of tiles");
        let books = (0..3).flat_map(|i| quad(i as f32 * 100.0 + 20.0, 30.0, i as f32 * 100.0 + 110.0, 160.0));
        assert!(!is_backdrop(books), "the save select's books");
        assert!(!is_backdrop(quad(0.0, 0.0, 320.0, 200.0).into_iter().take(1)));
    }
}
