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

//!
//! A recipe that *redraws* goes further: the lower picture becomes a canvas
//! the size of the whole window, and each of the game's lower-screen draws
//! is drawn whole at the place its element has in the PC layout (`Element`,
//! `set_elements`), at the window's resolution, by the game's own pipeline.
//! Nothing is cut out of a picture: a button is its own draws, moved.

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, RwLock};

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

/// A part of the lower screen's interface and where the PC layout draws it.
/// The canvas is the lower picture stretched over the whole window, so
/// places on it are in the lower screen's own 320x240 pixels.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Element {
    /// where the game draws it: left, top, right, bottom on the lower screen.
    pub home: [f32; 4],
    /// canvas pixels per screen pixel, across and down.
    pub scale: [f32; 2],
    /// where the lower screen's corner lands on the canvas.
    pub origin: [f32; 2],
}

impl Element {
    /// A screen point on the canvas.
    pub fn place(&self, p: [f32; 2]) -> [f32; 2] {
        [p[0] * self.scale[0] + self.origin[0], p[1] * self.scale[1] + self.origin[1]]
    }
    /// The same move for the buffer the screen is drawn into, which lies on
    /// its side: buffer x runs up the screen (240), buffer y from its right
    /// to its left (320). A coordinate `x` becomes `x * scale + offset`.
    fn buffer(&self) -> ([f32; 2], [f32; 2]) {
        let (ax, ay) = (self.scale[0], self.scale[1]);
        ([ay, ax], [240.0 - 240.0 * ay - self.origin[1], 320.0 - 320.0 * ax - self.origin[0]])
    }
    /// A point of the buffer (a vertex placed on the CPU), moved.
    pub(crate) fn buffer_point(&self, x: f32, y: f32) -> (f32, f32) {
        let (scale, offset) = self.buffer();
        (x * scale[0] + offset[0], y * scale[1] + offset[1])
    }
    /// A viewport of the buffer (left, bottom, width, height), moved.
    pub(crate) fn viewport(&self, v: (f32, f32, f32, f32)) -> (f32, f32, f32, f32) {
        let (scale, offset) = self.buffer();
        (v.0 * scale[0] + offset[0], v.1 * scale[1] + offset[1], v.2 * scale[0], v.3 * scale[1])
    }
    /// A scissor of the buffer (left, bottom, right, top), moved, rounded
    /// outwards.
    pub(crate) fn scissor(&self, s: [i32; 4]) -> [i32; 4] {
        let (scale, offset) = self.buffer();
        let at = |v: i32, axis: usize| v as f32 * scale[axis] + offset[axis];
        [at(s[0], 0).floor() as i32, at(s[1], 1).floor() as i32, at(s[2], 0).ceil() as i32, at(s[3], 1).ceil() as i32]
    }
}

fn elements_cell() -> &'static RwLock<Option<Arc<Vec<Element>>>> {
    static ELEMENTS: std::sync::OnceLock<RwLock<Option<Arc<Vec<Element>>>>> = std::sync::OnceLock::new();
    ELEMENTS.get_or_init(|| RwLock::new(None))
}

/// The elements of the screen being redrawn, first match first; None when
/// the lower picture is drawn as the game lays it out.
pub fn set_elements(elements: Option<Vec<Element>>) {
    if let Ok(mut cell) = elements_cell().write() {
        if cell.as_deref().map(|e| &e[..]) != elements.as_deref() {
            if cell.is_some() != elements.is_some() {
                log::info!("menu redraw {}", if elements.is_some() { "on: each lower-screen element is drawn at its PC place" } else { "off" });
            }
            *cell = elements.map(Arc::new);
        }
    }
}

pub(crate) fn elements() -> Option<Arc<Vec<Element>>> {
    if !composing() { return None; }
    elements_cell().read().ok().and_then(|cell| cell.clone())
}

/// The element a piece of interface belongs to, from where the game draws
/// it (its bounds on the lower screen): the first whose home holds its
/// centre. A piece is never shared: it moves whole or is left out.
pub fn element_for(elements: &[Element], bounds: [f32; 4]) -> Option<Element> {
    let (x, y) = ((bounds[0] + bounds[2]) * 0.5, (bounds[1] + bounds[3]) * 0.5);
    elements.iter().copied().find(|e| x >= e.home[0] && x < e.home[2] && y >= e.home[1] && y < e.home[3])
}

/// The triangles of a draw gathered into the pieces they form (triangles
/// sharing a vertex are one piece: a glyph, a panel): for each vertex, the
/// number of its piece, and each piece's bounds. `points` are the vertices
/// on the lower screen.
pub fn pieces_of(points: &[[f32; 2]], indices: &[u32]) -> (Vec<u32>, Vec<[f32; 4]>) {
    let mut parent: Vec<u32> = (0..points.len() as u32).collect();
    fn root(parent: &mut [u32], mut i: u32) -> u32 {
        while parent[i as usize] != i {
            parent[i as usize] = parent[parent[i as usize] as usize];
            i = parent[i as usize];
        }
        i
    }
    for t in indices.chunks_exact(3) {
        if t.iter().any(|&i| i as usize >= points.len()) { continue; }
        let a = root(&mut parent, t[0]);
        for &i in &t[1..] {
            let b = root(&mut parent, i);
            parent[b as usize] = a;
        }
    }
    let mut number = vec![u32::MAX; points.len()];
    let mut bounds: Vec<[f32; 4]> = Vec::new();
    let mut piece = vec![0u32; points.len()];
    for i in 0..points.len() as u32 {
        let r = root(&mut parent, i) as usize;
        if number[r] == u32::MAX {
            number[r] = bounds.len() as u32;
            bounds.push([f32::INFINITY, f32::INFINITY, f32::NEG_INFINITY, f32::NEG_INFINITY]);
        }
        let (n, p) = (number[r], points[i as usize]);
        let b = &mut bounds[n as usize];
        *b = [b[0].min(p[0]), b[1].min(p[1]), b[2].max(p[0]), b[3].max(p[1])];
        piece[i as usize] = n;
    }
    (piece, bounds)
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
    #[test]
    fn an_element_moves_the_screen_and_its_buffer_alike() {
        // twice the size, its corner at (30, 10) of the canvas
        let e = Element { home: [100.0, 50.0, 200.0, 100.0], scale: [2.0, 1.5], origin: [30.0, 10.0] };
        assert_eq!(e.place([100.0, 50.0]), [230.0, 85.0]);
        // a screen point (sx, sy) is buffer (240 - sy, 320 - sx), before and after
        for (sx, sy) in [(100.0f32, 50.0f32), (0.0, 0.0), (320.0, 240.0), (17.5, 201.0)] {
            let [cx, cy] = e.place([sx, sy]);
            let (bx, by) = e.buffer_point(240.0 - sy, 320.0 - sx);
            assert!((bx - (240.0 - cy)).abs() < 1e-3 && (by - (320.0 - cx)).abs() < 1e-3, "{sx},{sy}");
        }
        // the whole-screen viewport becomes the whole screen's place
        let v = e.viewport((0.0, 0.0, 240.0, 320.0));
        assert!((v.2 - 360.0).abs() < 1e-3 && (v.3 - 640.0).abs() < 1e-3);
        assert!((v.0 - (240.0 - 10.0 - 360.0)).abs() < 1e-3 && (v.1 - (320.0 - 30.0 - 640.0)).abs() < 1e-3);
        let s = e.scissor([0, 0, 240, 320]);
        assert_eq!(s, [-130, -350, 230, 290]);
        let same = Element { home: [0.0, 0.0, 320.0, 240.0], scale: [1.0, 1.0], origin: [0.0, 0.0] };
        assert_eq!(same.viewport((0.0, 0.0, 240.0, 320.0)), (0.0, 0.0, 240.0, 320.0));
        assert_eq!(same.scissor([3, 4, 200, 300]), [3, 4, 200, 300]);
    }
    #[test]
    fn a_piece_goes_whole_to_the_element_holding_its_centre() {
        let left = Element { home: [0.0, 0.0, 100.0, 240.0], scale: [1.0, 1.0], origin: [0.0, 0.0] };
        let right = Element { home: [200.0, 0.0, 320.0, 240.0], scale: [1.0, 1.0], origin: [50.0, 0.0] };
        let all = [left, right];
        assert_eq!(element_for(&all, [80.0, 10.0, 110.0, 30.0]), Some(left), "sticking out of its home");
        assert_eq!(element_for(&all, [210.0, 10.0, 300.0, 30.0]), Some(right));
        assert_eq!(element_for(&all, [120.0, 10.0, 180.0, 30.0]), None, "nobody's: left out");
        assert_eq!(element_for(&all, [330.0, 10.0, 400.0, 30.0]), None, "still sliding in from outside");
    }
    #[test]
    fn glyphs_of_one_draw_are_separate_pieces() {
        // two quads (two triangles each, sharing vertices) and a lone triangle
        let points = [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0], [10.0, 10.0],
            [50.0, 0.0], [60.0, 0.0], [50.0, 10.0], [60.0, 10.0], [100.0, 100.0], [110.0, 100.0], [100.0, 110.0]];
        let indices = [0, 1, 2, 1, 3, 2, 4, 5, 6, 5, 7, 6, 8, 9, 10];
        let (piece, bounds) = pieces_of(&points, &indices);
        assert_eq!(bounds.len(), 3);
        assert_eq!(piece[..4], [piece[0]; 4]);
        assert_eq!(piece[4..8], [piece[4]; 4]);
        assert_ne!(piece[0], piece[4]);
        assert_eq!(bounds[piece[4] as usize], [50.0, 0.0, 60.0, 10.0]);
        assert_eq!(bounds[piece[8] as usize], [100.0, 100.0, 110.0, 110.0]);
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
