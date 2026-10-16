//! Where relocated original bottom-screen layers go in the PC window.
//!
//! Pure geometry so it can be tested without the game. Source coordinates are
//! the guest bottom screen (320x240, origin top left). Window coordinates are
//! host pixels, origin top left. Nothing here invents UI; it only places the
//! game's own draws.

/// A rectangle, `[left, top, right, bottom]`.
pub type Rect = [f32; 4];

/// A group of original bottom-screen draws that is moved as one unit, so the
/// game's own relative layout and animation inside it are preserved.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Island {
    pub name: &'static str,
    /// Region of the guest bottom screen the group lives in.
    pub source: Rect,
    pub anchor: Anchor,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Anchor {
    /// Under the game's own health bar, top left (design v2).
    BelowHealthLeft,
    /// Right window edge, below the game's own top-screen score.
    BelowScoreRight,
}

/// Air special gauges and the land Power Palette share the lower-left corner
/// of the original screen (October 2026 captures `frame-audit.png`:
/// orbs at about x 5-95 / y 190-237, palette x 0-125 / y 200-240).
pub const ACTION: Island = Island { name: "action", source: [0.0, 150.0, 170.0, 240.0], anchor: Anchor::BelowHealthLeft };
/// Intensity, hearts collected and the heart bank, top right of the original
/// screen (about x 215-318 / y 2-40 in the same captures).
pub const COUNTERS: Island = Island { name: "counters", source: [196.0, 0.0, 320.0, 48.0], anchor: Anchor::BelowScoreRight };
pub const ISLANDS: [Island; 2] = [ACTION, COUNTERS];

/// Draws larger than this are panels/backgrounds, never an island element.
const MAX_ELEMENT: [f32; 2] = [200.0, 150.0];

/// Axis-aligned bounds of four points.
pub fn bounds(points: &[[f32; 2]; 4]) -> Rect {
    let mut r = [f32::INFINITY, f32::INFINITY, f32::NEG_INFINITY, f32::NEG_INFINITY];
    for p in points {
        r[0] = r[0].min(p[0]); r[1] = r[1].min(p[1]);
        r[2] = r[2].max(p[0]); r[3] = r[3].max(p[1]);
    }
    r
}

pub fn center(r: Rect) -> [f32; 2] { [(r[0] + r[2]) * 0.5, (r[1] + r[3]) * 0.5] }

fn inside(p: [f32; 2], r: Rect) -> bool { p[0] >= r[0] && p[0] < r[2] && p[1] >= r[1] && p[1] < r[3] }

/// Which island an element belongs to, by its original screen position.
/// Background panels and full-screen frames are never island elements.
pub fn island_for(xy: &[[f32; 2]; 4]) -> Option<Island> {
    let b = bounds(xy);
    if !(b[2] - b[0] <= MAX_ELEMENT[0] && b[3] - b[1] <= MAX_ELEMENT[1]) { return None; }
    let c = center(b);
    ISLANDS.into_iter().find(|island| inside(c, island.source))
}

/// The original stylus marker is drawn at the touch point. It is a 3DS
/// affordance, and the PC reticle already shows aim on the main view.
pub fn is_touch_marker(xy: &[[f32; 2]; 4], touch: Option<[f32; 2]>) -> bool {
    let Some(t) = touch else { return false };
    let b = bounds(xy);
    let c = center(b);
    (c[0] - t[0]).abs() <= 3.0 && (c[1] - t[1]).abs() <= 3.0 && b[2] - b[0] <= 64.0 && b[3] - b[1] <= 64.0
}

/// Host pixels per guest pixel for relocated HUD islands.
pub fn hud_scale(height: f32, hud: f32) -> f32 { height / 240.0 * 0.5 * hud.clamp(0.5, 2.0) }

/// Design v2 (doc/PC_INTERFACE_DESIGN_DIRECTION.md, user choice of October
/// 15): portraits stand in the bottom corners beside the subtitles, at most
/// this share of the view width each, so captions keep the middle.
pub const PORTRAIT_HEIGHT: f32 = 0.27;
pub const PORTRAIT_WIDTH: f32 = 0.14;

/// Host pixels per guest pixel for portraits.
pub fn portrait_scale(width: f32, height: f32) -> f32 {
    (height * PORTRAIT_HEIGHT / 240.0).min(width * PORTRAIT_WIDTH / 256.0)
}

/// The game draws its subtitles in the lower quarter of the main view
/// (October 14 captures: caption text between about 76% and 92% of the
/// height, roughly 15% to 85% of the width).
pub const SUBTITLE_TOP: f32 = 0.74;

/// Lower-screen picture inserts (gag art, cutaway comics, boss and rival
/// title cards) get a picture area on the left, below the health/power
/// group and above the bottom-left portrait, never the middle of the action.
/// The whole original lower-screen space is mapped into it, so the game's
/// own position, arrows, labels and motion stay together.
pub const PICTURE_TOP: f32 = 0.30;
pub const PICTURE_BOTTOM: f32 = 0.71;
pub const PICTURE_WIDTH: f32 = 0.34;

pub fn insert_scale(width: f32, height: f32) -> f32 {
    (height * (PICTURE_BOTTOM - PICTURE_TOP) / 240.0).min(width * PICTURE_WIDTH / 320.0)
}

/// Maps a point of an insert layer into the picture area.
pub fn place_insert(p: [f32; 2], width: f32, height: f32) -> [f32; 2] {
    let s = insert_scale(width, height);
    [margin(height) + p[0] * s, height * PICTURE_TOP + p[1] * s]
}

pub fn margin(height: f32) -> f32 { height * 0.015 }

/// Top of the counters island: just below the game's own score (its digits
/// end at about 13% of the view height).
const BELOW_SCORE: f32 = 0.145;
/// Top of the action group: just below the game's own health bar (its wing
/// ends at about 13% of the height), indented past the wing.
const BELOW_HEALTH: f32 = 0.135;
const HEALTH_INDENT: f32 = 0.045;
/// Orbs and the Power Palette sit in the lower part of the action source
/// (y 180-240); this guest row is placed at BELOW_HEALTH.
const ACTION_CONTENT_TOP: f32 = 180.0;

/// Pickups (an icon box rising with an "xN" count, October 15 census:
/// y 135-182) are drawn above the orbs/palette row on the 3DS. Above that
/// row on PC is the game's own health bar, so the strip above the row is
/// placed under it instead, keeping its motion.
pub fn above_action_row(layer_center_y: f32) -> bool { layer_center_y < ACTION_CONTENT_TOP }

/// Maps an island element point into the window. `above_row`: the element
/// belongs to the strip above the orbs/palette row (see above_action_row).
pub fn place_island(p: [f32; 2], island: Island, width: f32, height: f32, hud: f32) -> [f32; 2] {
    place_island_element(p, island, width, height, hud, false)
}

pub fn place_island_element(p: [f32; 2], island: Island, width: f32, height: f32, hud: f32, above_row: bool) -> [f32; 2] {
    let s = hud_scale(height, hud);
    let m = margin(height);
    let [l, t, r, _] = island.source;
    // the strip above the row moves below it: one strip height (60) down,
    // plus the 60 the strip itself spans
    let shift = if above_row { 120.0 } else { 0.0 };
    match island.anchor {
        Anchor::BelowHealthLeft => [width * HEALTH_INDENT + (p[0] - l) * s, height * BELOW_HEALTH + (p[1] - ACTION_CONTENT_TOP + shift) * s],
        Anchor::BelowScoreRight => [width - m - (r - p[0]) * s, height * BELOW_SCORE + (p[1] - t) * s],
    }
}

/// Maps a portrait point into the window. Speakers on the left half of the
/// original screen stay on the left, the others on the right; both stand on
/// the bottom edge in their corner, beside the subtitles.
pub fn place_portrait(p: [f32; 2], right: bool, width: f32, height: f32) -> [f32; 2] {
    let s = portrait_scale(width, height);
    let m = margin(height);
    [if right { width - m - (320.0 - p[0]) * s } else { m + p[0] * s },
     height - (240.0 - p[1]) * s]
}

#[cfg(test)]
mod tests {
    use super::*;
    fn quad(l: f32, t: f32, r: f32, b: f32) -> [[f32; 2]; 4] { [[l, t], [r, t], [l, b], [r, b]] }
    const SIZES: [(f32, f32); 5] = [(1920.0, 1080.0), (1280.0, 720.0), (2560.0, 1440.0), (3840.0, 2160.0), (1024.0, 768.0)];

    #[test]
    fn orbs_and_palette_join_the_action_island() {
        assert_eq!(island_for(&quad(5.0, 195.0, 47.0, 237.0)), Some(ACTION));
        assert_eq!(island_for(&quad(45.0, 205.0, 80.0, 238.0)), Some(ACTION));
        assert_eq!(island_for(&quad(250.0, 4.0, 318.0, 20.0)), Some(COUNTERS));
    }

    #[test]
    fn backgrounds_titles_and_frames_are_not_island_elements() {
        assert_eq!(island_for(&quad(0.0, 0.0, 320.0, 240.0)), None);
        assert_eq!(island_for(&quad(0.0, 0.0, 200.0, 40.0)), None, "chapter title is centered outside the counters");
        assert_eq!(island_for(&quad(150.0, 60.0, 320.0, 240.0)), None, "portrait-sized art");
    }

    #[test]
    fn touch_marker_is_recognized_only_at_the_touch_point() {
        let marker = quad(20.0, 200.0, 50.0, 230.0);
        assert!(is_touch_marker(&marker, Some([35.0, 215.0])));
        assert!(!is_touch_marker(&marker, Some([100.0, 100.0])));
        assert!(!is_touch_marker(&marker, None));
        assert!(!is_touch_marker(&quad(0.0, 0.0, 320.0, 240.0), Some([160.0, 120.0])));
    }

    fn action_box(w: f32, h: f32, hud: f32) -> Rect {
        let a = place_island([0.0, ACTION_CONTENT_TOP], ACTION, w, h, hud);
        let b = place_island([170.0, 240.0], ACTION, w, h, hud);
        [a[0], a[1], b[0], b[1]]
    }

    #[test]
    fn hud_groups_sit_under_health_and_score_on_screen() {
        for (w, h) in SIZES {
            for hud in [0.5, 1.0, 2.0] {
                let a = action_box(w, h, hud);
                let c = [place_island([196.0, 0.0], COUNTERS, w, h, hud), place_island([320.0, 48.0], COUNTERS, w, h, hud)];
                for p in [[a[0], a[1]], [a[2], a[3]], c[0], c[1]] {
                    assert!(p[0] >= 0.0 && p[0] <= w && p[1] >= 0.0 && p[1] <= h, "{p:?} {w}x{h} {hud}");
                }
                assert!((a[1] - h * 0.135).abs() < 0.01, "content starts under the health bar");
                assert!(a[2] < c[0][0], "action left of counters");
                assert!(c[0][1] >= h * 0.14 && a[3] < h * SUBTITLE_TOP, "under the score, above captions");
                let (aw, ah) = (a[2] - a[0], a[3] - a[1]);
                assert!((aw / ah - 170.0 / 60.0).abs() < 0.001, "the group keeps its aspect");
            }
        }
    }

    #[test]
    fn pickups_never_cover_the_health_bar() {
        for (w, h) in SIZES {
            for hud in [0.5, 1.0, 2.0] {
                // the rising pickup box, top of its animation
                let y = place_island_element([23.0, 135.0], ACTION, w, h, hud, above_action_row((135.0 + 175.0) / 2.0))[1];
                assert!(y >= h * 0.135 - 0.01, "{w}x{h} {hud}: {y}");
                // and it sits under the orbs/palette row
                assert!(y >= action_box(w, h, hud)[3] - 0.01);
            }
        }
        assert!(!above_action_row(212.0), "orbs and palette stay where they are");
    }

    #[test]
    fn portraits_stand_in_the_bottom_corners_beside_the_subtitles() {
        for (w, h) in SIZES {
            let left = [place_portrait([0.0, 0.0], false, w, h), place_portrait([256.0, 240.0], false, w, h)];
            let right = [place_portrait([64.0, 0.0], true, w, h), place_portrait([320.0, 240.0], true, w, h)];
            assert!((left[1][1] - h).abs() < 0.01 && (right[1][1] - h).abs() < 0.01, "on the bottom edge");
            assert!(left[0][1] >= h * 0.72, "no taller than the caption band");
            assert!(left[1][0] <= w * 0.16 + 0.01, "left one stays left of the captions");
            assert!(right[0][0] >= w * 0.84 - 0.01, "right one stays right of the captions");
            assert!((right[1][0] - (w - margin(h))).abs() < 0.01);
            assert!(left[0][1] > action_box(w, h, 2.0)[3], "below the HUD at any size");
        }
    }

    #[test]
    fn pictures_use_the_left_area_between_hud_and_portrait() {
        for (w, h) in SIZES {
            let a = place_insert([0.0, 0.0], w, h);
            let b = place_insert([320.0, 240.0], w, h);
            assert!(a[0] >= 0.0 && b[0] <= w * (PICTURE_WIDTH + 0.02), "left side, not the middle");
            assert!(a[1] > action_box(w, h, 1.25)[3], "below the power group up to a 125% HUD");
            assert!(b[1] <= place_portrait([0.0, 0.0], false, w, h)[1] + 0.01, "above the bottom-left portrait");
            assert!(((b[0] - a[0]) / (b[1] - a[1]) - 320.0 / 240.0).abs() < 0.001, "aspect kept");
        }
    }
}
