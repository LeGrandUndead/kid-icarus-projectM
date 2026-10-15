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
    /// Bottom-left window corner.
    BottomLeft,
    /// Right window edge, below the game's own top-screen score.
    BelowScoreRight,
}

/// Air special gauges and the land Power Palette share the lower-left corner
/// of the original screen (October 2026 captures `frame-audit.png`:
/// orbs at about x 5-95 / y 190-237, palette x 0-125 / y 200-240).
pub const ACTION: Island = Island { name: "action", source: [0.0, 150.0, 170.0, 240.0], anchor: Anchor::BottomLeft };
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

/// Host pixels per guest pixel for portraits: a portrait column is about 30%
/// of the window height (the October 14 preview used 28%).
pub fn portrait_scale(width: f32, height: f32) -> f32 { (height * 0.30 / 240.0).min(width * 0.22 / 256.0) }

/// The game draws its subtitles in the lower quarter of the main view
/// (October 14 captures: caption baseline at about 83% of the height).
/// Portraits stand on this line so they never cover a caption.
pub const SUBTITLE_TOP: f32 = 0.74;

/// Lower-screen picture inserts (gag art, cutaway comics, boss and rival
/// title cards) are shown on a surface above the action, top center, the
/// whole original lower-screen space scaled to this share of the height.
/// The art covers part of that space; at 0.5 the chapter 1 NES insert is
/// about a quarter of the view height (0.34 looked too small in play).
pub const INSERT_HEIGHT: f32 = 0.5;
pub const INSERT_TOP: f32 = 0.05;

pub fn insert_scale(width: f32, height: f32) -> f32 { (height * INSERT_HEIGHT / 240.0).min(width * 0.6 / 320.0) }

/// Maps a point of an insert layer into the window, keeping the game's own
/// position and motion inside the original screen.
pub fn place_insert(p: [f32; 2], width: f32, height: f32) -> [f32; 2] {
    let s = insert_scale(width, height);
    [width * 0.5 + (p[0] - 160.0) * s, height * INSERT_TOP + p[1] * s]
}

pub fn margin(height: f32) -> f32 { height * 0.015 }

/// Top of the counters island: below the game's own score, which occupies
/// about the top 18% of the main view.
const BELOW_SCORE: f32 = 0.19;

/// Maps an island element point into the window.
pub fn place_island(p: [f32; 2], island: Island, width: f32, height: f32, hud: f32) -> [f32; 2] {
    let s = hud_scale(height, hud);
    let m = margin(height);
    let [l, t, r, b] = island.source;
    match island.anchor {
        Anchor::BottomLeft => [m + (p[0] - l) * s, height - m - (b - p[1]) * s],
        Anchor::BelowScoreRight => [width - m - (r - p[0]) * s, height * BELOW_SCORE + (p[1] - t) * s],
    }
}

/// Maps a portrait point into the window. Speakers on the left half of the
/// original screen stay on the left, the others on the right; both stand on
/// the subtitle line, above the action island (bottom left).
pub fn place_portrait(p: [f32; 2], right: bool, width: f32, height: f32) -> [f32; 2] {
    let s = portrait_scale(width, height);
    let m = margin(height);
    [if right { width - m - (320.0 - p[0]) * s } else { m + p[0] * s },
     height * SUBTITLE_TOP - (240.0 - p[1]) * s]
}

#[cfg(test)]
mod tests {
    use super::*;
    fn quad(l: f32, t: f32, r: f32, b: f32) -> [[f32; 2]; 4] { [[l, t], [r, t], [l, b], [r, b]] }

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

    #[test]
    fn islands_stay_on_screen_and_do_not_overlap_at_common_sizes() {
        for (w, h) in [(1920.0, 1080.0), (1280.0, 720.0), (2560.0, 1440.0), (3840.0, 2160.0), (1024.0, 768.0)] {
            for hud in [0.5, 1.0, 2.0] {
                let a = [place_island([0.0, 150.0], ACTION, w, h, hud), place_island([170.0, 240.0], ACTION, w, h, hud)];
                let c = [place_island([196.0, 0.0], COUNTERS, w, h, hud), place_island([320.0, 48.0], COUNTERS, w, h, hud)];
                for p in a.iter().chain(&c) { assert!(p[0] >= 0.0 && p[0] <= w && p[1] >= 0.0 && p[1] <= h, "{p:?} {w}x{h} {hud}"); }
                assert!(a[1][1] <= h && a[0][1] > c[1][1], "action below counters");
                // the island keeps its aspect
                let (aw, ah) = (a[1][0] - a[0][0], a[1][1] - a[0][1]);
                assert!((aw / ah - 170.0 / 90.0).abs() < 0.001);
            }
        }
    }

    #[test]
    fn portraits_stay_out_of_the_subtitles_and_the_action_island() {
        for (w, h) in [(1920.0, 1080.0), (1280.0, 720.0), (2560.0, 1440.0), (3840.0, 2160.0)] {
            for right in [false, true] {
                let top = place_portrait([0.0, 0.0], right, w, h)[1];
                let bottom = place_portrait([320.0, 240.0], right, w, h)[1];
                assert!(bottom <= h * SUBTITLE_TOP + 0.01, "covers subtitles");
                assert!(top >= h * BELOW_SCORE, "covers health/score");
                // above the action island up to a 125% HUD (larger sizes may overlap by choice)
                assert!(bottom <= place_island([0.0, 150.0], ACTION, w, h, 1.25)[1] + 0.01);
            }
            assert!((place_portrait([320.0, 240.0], true, w, h)[0] - (w - margin(h))).abs() < 0.01);
        }
    }

    #[test]
    fn inserts_are_centered_above_portraits_and_subtitles() {
        for (w, h) in [(1920.0, 1080.0), (1280.0, 720.0), (1024.0, 768.0), (3840.0, 2160.0)] {
            let a = place_insert([0.0, 0.0], w, h);
            let b = place_insert([320.0, 240.0], w, h);
            assert!(((a[0] + b[0]) * 0.5 - w * 0.5).abs() < 0.01);
            assert!(a[0] >= 0.0 && b[0] <= w && a[1] > 0.0 && b[1] < h * SUBTITLE_TOP);
            assert!(((b[0] - a[0]) / (b[1] - a[1]) - 320.0 / 240.0).abs() < 0.001);
        }
    }
}
