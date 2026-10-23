//! What the presenter draws into the window: parts of the two screens.
//!
//! Every arrangement comes down to a list of pieces, each a rectangle of one
//! screen's picture drawn into a rectangle of the window. The usual layouts
//! show whole screens. A recomposed menu (`ScreenLayout::Composed`) shows the
//! upper picture as the scene and lays parts of the lower picture (drawn
//! transparent, kiu_ui::compose) where a PC layout wants them. Clicks are
//! found back through the same pieces (`touch_at`), so what is seen is what
//! is touched.

use super::{feather, layout, ScreenLayout, Viewport};

/// A menu screen with its own one-screen composition.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Recipe {
    /// The save select: the speech bubble scene above, the three books
    /// below it on the page, Back and How to Play in the window's corners.
    SaveSelect,
}

/// A part of a screen's picture drawn into the window.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Piece {
    /// 0 the upper screen, 1 the lower one.
    pub screen: usize,
    /// the part of the screen, left, top, right, bottom in its own console
    /// pixels (400 or 320 by 240; a wide upper picture still counts 400).
    pub source: [f32; 4],
    pub dest: Viewport,
    /// how far in from each edge the piece fades out (share of the piece).
    pub feather: [f32; 4],
    /// the picture carries coverage in its alpha (premultiplied), for laying
    /// it over another; otherwise it is opaque.
    pub coverage: bool,
    /// clicks on it touch the lower screen there.
    pub touch: bool,
}

pub const TOP_SIZE: [f32; 2] = [400.0, 240.0];
pub const BOTTOM_SIZE: [f32; 2] = [320.0, 240.0];

fn whole(screen: usize) -> [f32; 4] {
    let size = if screen == 0 { TOP_SIZE } else { BOTTOM_SIZE };
    [0.0, 0.0, size[0], size[1]]
}

/// The pieces of an arrangement, drawn in order (later ones over earlier).
pub fn pieces(width: u32, height: u32, arrangement: ScreenLayout) -> Vec<Piece> {
    if let ScreenLayout::Composed { recipe, .. } = arrangement {
        return composed(width as f32, height as f32, recipe);
    }
    let (top, bottom) = layout(width, height, arrangement);
    let (top_edges, bottom_edges) = feather(arrangement);
    let mut out = Vec::with_capacity(2);
    if let Some(dest) = top {
        out.push(Piece { screen: 0, source: whole(0), dest, feather: top_edges, coverage: false, touch: false });
    }
    if let Some(dest) = bottom {
        out.push(Piece { screen: 1, source: whole(1), dest, feather: bottom_edges, coverage: false, touch: true });
    }
    out
}

/// Where a click at window pixel (x, y) touches the lower screen, through
/// the topmost touchable piece under it.
pub fn touch_at(width: u32, height: u32, arrangement: ScreenLayout, x: f32, y: f32) -> Option<[f32; 2]> {
    pieces(width, height, arrangement).into_iter().rev().filter(|p| p.touch && p.screen == 1).find_map(|p| {
        let (u, v) = ((x - p.dest.x) / p.dest.width, (y - p.dest.y) / p.dest.height);
        ((0.0..1.0).contains(&u) && (0.0..1.0).contains(&v)).then(|| {
            let [l, t, r, b] = p.source;
            [l + u * (r - l), t + v * (b - t)]
        })
    })
}

// ---------------------------------------------------------------- recipes

/// The save select's bubble and books, in console pixels: the lower picture
/// above this row is the books (and the bubble's tail, which starts at its
/// top edge); below it Back and How to Play.
const SAVE_SELECT_BOOKS_FOOT: f32 = 188.0;
/// Rows of the upper picture the books' part overlaps: the bubble's black
/// ground, where the tail comes out of it as on the console (no bezel gap).
const SAVE_SELECT_JOIN: f32 = 30.0;
/// Back (bottom left) and How to Play (bottom right) on the lower picture.
const SAVE_SELECT_BACK: [f32; 4] = [0.0, 188.0, 64.0, 240.0];
const SAVE_SELECT_HELP: [f32; 4] = [176.0, 184.0, 320.0, 240.0];

fn composed(w: f32, h: f32, recipe: Recipe) -> Vec<Piece> {
    match recipe {
        Recipe::SaveSelect => save_select(w, h),
    }
}

fn save_select(w: f32, h: f32) -> Vec<Piece> {
    // the scene (upper picture) and the books under it keep the console's
    // proportions and alignment, as large as the window allows
    let tall = TOP_SIZE[1] + SAVE_SELECT_BOOKS_FOOT - SAVE_SELECT_JOIN;
    let unit = (h / tall).min(w / TOP_SIZE[0]);
    let y = (h - tall * unit) * 0.5;
    let scene = Viewport { x: (w - TOP_SIZE[0] * unit) * 0.5, y, width: TOP_SIZE[0] * unit, height: TOP_SIZE[1] * unit };
    let books = Viewport {
        x: (w - BOTTOM_SIZE[0] * unit) * 0.5,
        y: y + (TOP_SIZE[1] - SAVE_SELECT_JOIN) * unit,
        width: BOTTOM_SIZE[0] * unit,
        height: SAVE_SELECT_BOOKS_FOOT * unit,
    };
    // Back and How to Play go to the window's corners, at the same scale
    let margin = h * 0.02;
    let corner = |source: [f32; 4], right: bool| {
        let (cw, ch) = ((source[2] - source[0]) * unit, (source[3] - source[1]) * unit);
        Viewport { x: if right { w - margin - cw } else { margin }, y: h - margin - ch, width: cw, height: ch }
    };
    vec![
        // the page fades in at the scene's sides and under its black ground
        Piece { screen: 0, source: whole(0), dest: scene, feather: [0.03, 0.02, 0.03, SAVE_SELECT_JOIN / TOP_SIZE[1]], coverage: false, touch: false },
        Piece { screen: 1, source: [0.0, 0.0, BOTTOM_SIZE[0], SAVE_SELECT_BOOKS_FOOT], dest: books, feather: [0.0; 4], coverage: true, touch: true },
        Piece { screen: 1, source: SAVE_SELECT_BACK, dest: corner(SAVE_SELECT_BACK, false), feather: [0.0; 4], coverage: true, touch: true },
        Piece { screen: 1, source: SAVE_SELECT_HELP, dest: corner(SAVE_SELECT_HELP, true), feather: [0.0; 4], coverage: true, touch: true },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    const SIZES: [(u32, u32); 5] = [(1920, 1080), (1280, 720), (2560, 1440), (2560, 1080), (1024, 768)];

    #[test]
    fn usual_layouts_are_their_two_screens() {
        for (w, h) in SIZES {
            let p = pieces(w, h, ScreenLayout::Stacked);
            assert_eq!(p.len(), 2);
            assert_eq!((p[0].screen, p[1].screen), (0, 1));
            assert!(!p[0].touch && p[1].touch && !p[1].coverage);
            assert_eq!(pieces(w, h, ScreenLayout::TopWide).len(), 1);
            // a click in the middle of the lower screen touches its middle
            let b = p[1].dest;
            let t = touch_at(w, h, ScreenLayout::Stacked, b.x + b.width * 0.5, b.y + b.height * 0.5).unwrap();
            assert!((t[0] - 160.0).abs() < 0.01 && (t[1] - 120.0).abs() < 0.01);
            assert_eq!(touch_at(w, h, ScreenLayout::TopWide, 10.0, 10.0), None);
        }
    }

    #[test]
    fn the_save_select_is_one_scene_with_the_books_under_the_bubble() {
        let layout = ScreenLayout::Composed { wide: true, recipe: Recipe::SaveSelect };
        for (w, h) in SIZES {
            let p = pieces(w, h, layout);
            let (scene, books, back, help) = (p[0].dest, p[1].dest, p[2].dest, p[3].dest);
            for d in [scene, books, back, help] {
                assert!(d.x >= -0.01 && d.y >= -0.01 && d.x + d.width <= w as f32 + 0.01 && d.y + d.height <= h as f32 + 0.01, "{d:?} in {w}x{h}");
            }
            assert!((scene.width / scene.height - 5.0 / 3.0).abs() < 0.001, "the scene keeps its proportions");
            let unit = scene.height / 240.0;
            assert!((books.width / unit - 320.0).abs() < 0.01, "books at the scene's scale");
            assert!(((scene.x + scene.width * 0.5) - (books.x + books.width * 0.5)).abs() < 0.01, "centred under it as on the console");
            assert!((scene.y + scene.height - books.y - SAVE_SELECT_JOIN * unit).abs() < 0.01, "the tail comes out of the bubble's ground");
            assert!(p[1].coverage && p[2].coverage && p[3].coverage && !p[0].coverage);
            // Back and How to Play sit in the bottom corners, away from the books
            assert!(back.x < books.x + 1.0 && help.x + help.width > books.x + books.width - 1.0);
            assert!((back.y + back.height - help.y - help.height).abs() < 0.01);
            // clicking a book touches it, clicking Back touches Back
            let book_one = touch_at(w, h, layout, books.x + 60.0 * unit, books.y + 100.0 * unit).unwrap();
            assert!((book_one[0] - 60.0).abs() < 0.05 && (book_one[1] - 100.0).abs() < 0.05);
            let b = touch_at(w, h, layout, back.x + back.width * 0.5, back.y + back.height * 0.5).unwrap();
            assert!((b[0] - 32.0).abs() < 0.05 && (b[1] - 214.0).abs() < 0.05);
            // the page around them touches nothing
            assert_eq!(touch_at(w, h, layout, w as f32 * 0.5, 1.0), None);
        }
        let p = pieces(1920, 1080, layout);
        assert!(p[0].dest.height > 600.0, "the scene is large at 1080p: {:?}", p[0].dest);
    }
}
