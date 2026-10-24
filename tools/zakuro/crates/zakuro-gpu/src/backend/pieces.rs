//! What the presenter draws into the window: parts of the two screens.
//!
//! Every arrangement comes down to a list of pieces, each a rectangle of one
//! screen's picture drawn into a rectangle of the window. The usual layouts
//! show whole screens. A recomposed screen (`ScreenLayout::Composed`) follows
//! its recipe (`recipes`): parts of the upper and lower pictures (the lower
//! one drawn transparent, kiu_ui::compose) laid where the PC layout wants
//! them. Clicks are found back through the same pieces (`touch_at`), so what
//! is seen is what is touched.

use super::recipes::{self, Fill, ScreenRecipe};
use super::{feather, layout, ScreenLayout, Viewport};

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
    /// how much of it shows over what is under it.
    pub opacity: f32,
}

pub const TOP_SIZE: [f32; 2] = [400.0, 240.0];
pub const BOTTOM_SIZE: [f32; 2] = [320.0, 240.0];
/// The window is this many units tall; a 16:9 layout is this wide.
pub const UNITS_TALL: f32 = 240.0;
pub const UNITS_WIDE: f32 = 240.0 * 16.0 / 9.0;

fn whole(screen: usize) -> [f32; 4] {
    let size = if screen == 0 { TOP_SIZE } else { BOTTOM_SIZE };
    [0.0, 0.0, size[0], size[1]]
}

/// The pieces of an arrangement, drawn in order (later ones over earlier).
pub fn pieces(width: u32, height: u32, arrangement: ScreenLayout) -> Vec<Piece> {
    if let ScreenLayout::Composed { wide, recipe, room } = arrangement {
        return recipes::recipe(recipe).map_or_else(Vec::new, |r| composed(width as f32, height as f32, &r, wide && room));
    }
    let (top, bottom) = layout(width, height, arrangement);
    let (top_edges, bottom_edges) = feather(arrangement);
    let mut out = Vec::with_capacity(2);
    if let Some(dest) = top {
        out.push(Piece { screen: 0, source: whole(0), dest, feather: top_edges, coverage: false, touch: false, opacity: 1.0 });
    }
    if let Some(dest) = bottom {
        out.push(Piece { screen: 1, source: whole(1), dest, feather: bottom_edges, coverage: false, touch: true, opacity: 1.0 });
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

/// A recipe's pieces in a `w` x `h` window. `room`: the upper picture is a
/// 3D room drawn by the wide view, shown 16:9 rather than at the 5:3 the
/// game's 2D art needs.
pub fn composed(w: f32, h: f32, recipe: &ScreenRecipe, room: bool) -> Vec<Piece> {
    let unit = (h / UNITS_TALL).min(w / UNITS_WIDE);
    recipe.pieces.iter().filter(|s| s.source[2] > s.source[0] && s.source[3] > s.source[1]).map(|spec| {
        let (sw, sh) = (spec.source[2] - spec.source[0], spec.source[3] - spec.source[1]);
        // the upper picture's room is wider than its 400 console pixels
        let stretch = if spec.screen == 0 && room { 16.0 / 15.0 } else { 1.0 };
        let scale = match spec.fill {
            Fill::Scale => spec.scale,
            Fill::Height => h / unit / sh,
            Fill::Cover => (h / unit / sh).max(w / unit / (sw * stretch)),
            Fill::Contain => (h / unit / sh).min(w / unit / (sw * stretch)),
        };
        let (dw, dh) = (sw * stretch * scale * unit, sh * scale * unit);
        let (ax, ay) = (spec.anchor[0] * w, spec.anchor[1] * h);
        let dest = Viewport {
            x: ax - spec.anchor[0] * dw + spec.at[0] * unit,
            y: ay - spec.anchor[1] * dh + spec.at[1] * unit,
            width: dw,
            height: dh,
        };
        Piece { screen: spec.screen.min(1), source: spec.source, dest, feather: spec.feather,
            coverage: spec.screen == 1 && recipe.compose, touch: spec.touch && spec.screen == 1, opacity: spec.opacity.clamp(0.0, 1.0) }
    }).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::recipes::PieceSpec;
    const SIZES: [(u32, u32); 5] = [(1920, 1080), (1280, 720), (2560, 1440), (2560, 1080), (1024, 768)];

    #[test]
    fn usual_layouts_are_their_two_screens() {
        for (w, h) in SIZES {
            let p = pieces(w, h, ScreenLayout::Stacked);
            assert_eq!(p.len(), 2);
            assert_eq!((p[0].screen, p[1].screen), (0, 1));
            assert!(!p[0].touch && p[1].touch && !p[1].coverage);
            assert!(p.iter().all(|p| p.opacity == 1.0));
            assert_eq!(pieces(w, h, ScreenLayout::TopWide).len(), 1);
            // a click in the middle of the lower screen touches its middle
            let b = p[1].dest;
            let t = touch_at(w, h, ScreenLayout::Stacked, b.x + b.width * 0.5, b.y + b.height * 0.5).unwrap();
            assert!((t[0] - 160.0).abs() < 0.01 && (t[1] - 120.0).abs() < 0.01);
            assert_eq!(touch_at(w, h, ScreenLayout::TopWide, 10.0, 10.0), None);
        }
    }

    fn save_select() -> ScreenRecipe {
        // the October 24 save select: scene above, books under the bubble,
        // Back and How to Play in the corners
        let s = 240.0 / (240.0 + 188.0 - 30.0);
        ScreenRecipe { name: "save_select".into(), compose: true, pieces: vec![
            PieceSpec { screen: 0, anchor: [0.5, 0.0], scale: s, feather: [0.03, 0.02, 0.03, 0.125], ..Default::default() },
            PieceSpec { screen: 1, source: [0.0, 0.0, 320.0, 188.0], anchor: [0.5, 0.0], at: [0.0, 210.0 * s], scale: s, touch: true, ..Default::default() },
            PieceSpec { screen: 1, source: [0.0, 188.0, 64.0, 240.0], anchor: [0.0, 1.0], at: [4.8, -4.8], scale: s, touch: true, ..Default::default() },
            PieceSpec { screen: 1, source: [176.0, 184.0, 320.0, 240.0], anchor: [1.0, 1.0], at: [-4.8, -4.8], scale: s, touch: true, ..Default::default() },
        ], ..Default::default() }
    }

    #[test]
    fn a_recipe_places_its_pieces_in_units_of_the_window() {
        let r = save_select();
        for (w, h) in SIZES {
            let p = composed(w as f32, h as f32, &r, false);
            let (scene, books, back, help) = (p[0].dest, p[1].dest, p[2].dest, p[3].dest);
            for d in [scene, books, back, help] {
                assert!(d.x >= -0.01 && d.y >= -0.01 && d.x + d.width <= w as f32 + 0.01 && d.y + d.height <= h as f32 + 0.01, "{d:?} in {w}x{h}");
            }
            assert!((scene.width / scene.height - 5.0 / 3.0).abs() < 0.001, "the scene keeps its proportions");
            let unit = scene.height / 240.0;
            assert!((books.width / unit - 320.0).abs() < 0.01, "books at the scene's scale");
            assert!(((scene.x + scene.width * 0.5) - (books.x + books.width * 0.5)).abs() < 0.01, "centred under it");
            assert!((scene.y + scene.height - books.y - 30.0 * unit).abs() < 0.01, "the tail comes out of the bubble's ground");
            assert!(p[1].coverage && p[2].coverage && !p[0].coverage && !p[0].touch);
            assert!(back.x < books.x && help.x + help.width > books.x + books.width);
            assert!((back.y + back.height - help.y - help.height).abs() < 0.01);
        }
        let p = composed(1920.0, 1080.0, &r, false);
        assert!((p[0].dest.y).abs() < 0.01 && (p[1].dest.y + p[1].dest.height - 1080.0).abs() < 0.5, "fills the height at 1080p");
    }

    #[test]
    fn fills_and_rooms() {
        let mut r = ScreenRecipe { pieces: vec![PieceSpec { fill: Fill::Height, ..Default::default() }], ..Default::default() };
        let flat = composed(1920.0, 1080.0, &r, false)[0].dest;
        assert!((flat.height - 1080.0).abs() < 0.01 && (flat.width - 1800.0).abs() < 0.01 && (flat.x - 60.0).abs() < 0.01);
        let room = composed(1920.0, 1080.0, &r, true)[0].dest;
        assert!((room.width - 1920.0).abs() < 0.01 && room.x.abs() < 0.01, "a 3D room fills 16:9");
        r.pieces[0].fill = Fill::Cover;
        let cover = composed(2560.0, 1080.0, &r, true)[0].dest;
        assert!(cover.width >= 2559.9 && cover.height >= 1079.9);
        r.pieces[0].fill = Fill::Contain;
        let contain = composed(1024.0, 768.0, &r, false)[0].dest;
        assert!((contain.width - 1024.0).abs() < 0.01 && contain.height < 768.0);
    }

    #[test]
    fn clicks_go_through_the_topmost_touchable_piece() {
        let r = save_select();
        let p = composed(1920.0, 1080.0, &r, false);
        let at = |x: f32, y: f32| p.iter().rev().filter(|p| p.touch && p.screen == 1).find_map(|p| {
            let (u, v) = ((x - p.dest.x) / p.dest.width, (y - p.dest.y) / p.dest.height);
            ((0.0..1.0).contains(&u) && (0.0..1.0).contains(&v)).then(|| [p.source[0] + u * (p.source[2] - p.source[0]), p.source[1] + v * (p.source[3] - p.source[1])])
        });
        let back = p[2].dest;
        let b = at(back.x + back.width * 0.5, back.y + back.height * 0.5).unwrap();
        assert!((b[0] - 32.0).abs() < 0.05 && (b[1] - 214.0).abs() < 0.05);
        assert_eq!(at(960.0, 1.0), None, "the scene is not touchable");
    }
}
