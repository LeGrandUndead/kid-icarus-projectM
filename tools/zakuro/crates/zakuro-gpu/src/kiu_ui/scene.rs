//! What the original bottom screen is showing, from the identity of the
//! textures it draws. Evidence is the ROM atlas a draw samples and the part of
//! the atlas it samples; never pixel colors, framebuffer contents or timers.

use super::Role;

/// Normalized atlas rectangle `[u0, v0, u1, v1]`, rows counted in the
/// texture's stored order (the order `cgfx_textures.py` decodes).
type UvRect = [f32; 4];

/// The "Resume" label of the in-game pause menu inside `common/info` atlas
/// `gm_01` (pixels 3-80 x 214-246 of 256x256, measured from the ROM atlas).
const RESUME_LABEL: UvRect = [3.0 / 256.0, 214.0 / 256.0, 80.0 / 256.0, 246.0 / 256.0];

/// The "Retreat" label beside it (pixels 80-160 x 214-246).
const RETREAT_LABEL: UvRect = [80.0 / 256.0, 214.0 / 256.0, 160.0 / 256.0, 246.0 / 256.0];

/// The October 15 census confirmed Resume and Retreat at UV
/// 0-0.3125 / 0.3125-0.625 x 0.0273-0.168 (PICA V) sliding in from the sides.
/// `gm_01` also holds the ornate corners of the ordinary gameplay frame, so
/// only these labels, never the atlas alone, count as the pause menu.
const PAUSE_LABELS: [UvRect; 3] = [RESUME_LABEL, RETREAT_LABEL, REMOVE_DISPLAY_LABEL];

/// End cap of the option bars (pixels 238-253 x 0-30): drawn on the pause
/// menu's Options bar and on every bar of the Options sub-screen (October 15
/// census, frames 11339+), never in ordinary gameplay. While it is drawn the
/// player is in a menu even though no pause label is.
const OPTION_BAR_CAP: UvRect = [0.9297, 0.0, 0.9883, 0.1172];

/// The "Remove Display" label of the same pause menu (pixels 0-96 x 146-178).
/// The October 15 census shows it is the first pause art drawn, sliding in
/// from the bottom edge, sampled at UV 0-0.375 x 0.3047-0.4297 (PICA V).
const REMOVE_DISPLAY_LABEL: UvRect = [0.0, 146.0 / 256.0, 96.0 / 256.0, 178.0 / 256.0];

/// One bottom-screen frame, summarized.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct BottomScene {
    /// Emulated frame the summary belongs to.
    pub frame: u64,
    /// The game drew its bottom screen this frame (otherwise the previous
    /// complete summary is repeated).
    pub fresh: bool,
    /// Original portrait layers, any speaker.
    pub portraits: u8,
    /// Picture inserts the dialogue refers to.
    pub inserts: u8,
    /// Original HUD elements that were relocated into the PC HUD.
    pub hud: u16,
    /// The original pause menu's Resume label is on the bottom screen.
    pub pause_menu: bool,
    /// A pause-menu label or an option bar is drawn: the player is in the
    /// pause menu or one of its sub-screens (Options).
    pub menu: bool,
    /// The game's save select is up (its speech bubble or books were drawn
    /// this frame, on either screen).
    pub save_select: bool,
    /// The land Power Palette is on screen (power icons from atlas `mr` in
    /// the action island). Air special orbs come from `gc_00` instead.
    pub palette: bool,
}

/// A layer, as far as classification is concerned.
pub struct Evidence<'a> {
    pub role: Role,
    pub atlas: &'a str,
    pub uv: [[f32; 2]; 4],
    pub island: bool,
}

fn uv_bounds(uv: &[[f32; 2]; 4]) -> UvRect {
    let mut r = [f32::INFINITY, f32::INFINITY, f32::NEG_INFINITY, f32::NEG_INFINITY];
    for p in uv {
        r[0] = r[0].min(p[0]); r[1] = r[1].min(p[1]);
        r[2] = r[2].max(p[0]); r[3] = r[3].max(p[1]);
    }
    r
}

/// The sampled rectangle is the label, in either V convention: PICA counts V
/// from the opposite end of the stored rows, and some layout tools flip it.
fn samples_label(uv: &[[f32; 2]; 4], label: UvRect) -> bool {
    let b = uv_bounds(uv);
    let (w, h) = (b[2] - b[0], b[3] - b[1]);
    let (lw, lh) = (label[2] - label[0], label[3] - label[1]);
    // the whole word, not one glyph or a stretched strip
    if !(w > lw * 0.6 && w < lw * 1.6 && h > lh * 0.5 && h < lh * 1.8) { return false; }
    let c = [(b[0] + b[2]) * 0.5, (b[1] + b[3]) * 0.5];
    let within = |v: f32, lo: f32, hi: f32| v >= lo - 0.02 && v <= hi + 0.02;
    within(c[0], label[0], label[2])
        && (within(c[1], label[1], label[3]) || within(1.0 - c[1], label[1], label[3]))
}

pub fn classify<'a>(frame: u64, fresh: bool, layers: impl Iterator<Item = Evidence<'a>>) -> BottomScene {
    let mut scene = BottomScene { frame, fresh, ..BottomScene::default() };
    for layer in layers {
        match layer.role {
            Role::Portrait => scene.portraits = scene.portraits.saturating_add(1),
            Role::Menu if layer.atlas == "gm_01" => {
                if PAUSE_LABELS.iter().any(|label| samples_label(&layer.uv, *label)) {
                    scene.pause_menu = true;
                    scene.menu = true;
                } else if samples_label(&layer.uv, OPTION_BAR_CAP) {
                    scene.menu = true;
                }
            }
            Role::Menu => {}
            Role::Insert => scene.inserts = scene.inserts.saturating_add(1),
            Role::Hud | Role::Decor | Role::Unlisted | Role::Screen => {}
        }
        if layer.island {
            scene.hud = scene.hud.saturating_add(1);
            if layer.atlas == "mr" { scene.palette = true; }
        }
    }
    scene
}

#[cfg(test)]
mod tests {
    use super::*;
    fn uv(l: f32, t: f32, r: f32, b: f32) -> [[f32; 2]; 4] { [[l, t], [r, t], [l, b], [r, b]] }
    fn ev(role: Role, atlas: &str, uv: [[f32; 2]; 4]) -> Evidence<'_> { Evidence { role, atlas, uv, island: false } }

    #[test]
    fn resume_label_identifies_the_pause_menu_in_both_v_conventions() {
        let stored = uv(3.0 / 256.0, 214.0 / 256.0, 80.0 / 256.0, 246.0 / 256.0);
        let flipped = uv(3.0 / 256.0, 1.0 - 246.0 / 256.0, 80.0 / 256.0, 1.0 - 214.0 / 256.0);
        for label in [stored, flipped] {
            let s = classify(7, true, [ev(Role::Menu, "gm_01", label)].into_iter());
            assert!(s.pause_menu && s.menu && s.frame == 7);
        }
    }

    #[test]
    fn census_pause_draws_identify_the_pause_menu() {
        // exact rectangles recorded on October 15 (frame 13533+)
        let remove_display = uv(0.0, 0.3047, 0.3750, 0.4297);
        let separator = uv(0.9941, 0.9141, 0.9941, 1.0);
        let icon = uv(0.75, 0.3984, 0.8281, 0.4766);
        let s = classify(1, true, [ev(Role::Menu, "gm_01", separator), ev(Role::Menu, "gm_01", icon)].into_iter());
        assert!(!s.menu && !s.pause_menu);
        for label in [remove_display, uv(0.0, 0.0273, 0.3125, 0.1680), uv(0.3125, 0.0273, 0.6250, 0.1680)] {
            let s = classify(1, true, [ev(Role::Menu, "gm_01", label)].into_iter());
            assert!(s.pause_menu && s.menu);
        }
    }

    #[test]
    fn options_sub_screen_bars_keep_the_menu_without_a_pause_label() {
        // October 15 census, frame 11343: Options sub-screen, no Resume/Retreat
        let cap = uv(0.9297, 0.8828, 0.9883, 1.0);
        let bar = uv(0.9844, 0.8828, 0.9844, 1.0);
        let s = classify(1, true, [ev(Role::Menu, "gm_01", bar), ev(Role::Menu, "gm_01", cap)].into_iter());
        assert!(s.menu && !s.pause_menu);
    }

    #[test]
    fn gameplay_frame_corners_from_the_menu_atlas_are_not_a_menu() {
        // October 15 census, frame 5022: ordinary chapter frame pieces in gm_01
        let corners = [uv(0.4609, 0.7578, 0.7031, 1.0), uv(0.0, 0.5391, 0.4609, 1.0),
            uv(0.7012, 0.9688, 0.7012, 1.0), uv(0.4609, 0.7598, 0.4922, 0.7598), uv(0.4590, 0.5391, 0.4590, 0.5703)];
        let s = classify(1, true, corners.into_iter().map(|c| ev(Role::Menu, "gm_01", c)));
        assert!(!s.menu && !s.pause_menu);
    }

    #[test]
    fn other_menu_art_or_other_atlases_are_not_the_pause_menu() {
        // "Retreat" beside it, a single glyph, and the same rectangle in another atlas
        let middle_retreat = uv(0.45, 0.30, 0.75, 0.40);
        let glyph = uv(3.0 / 256.0, 214.0 / 256.0, 15.0 / 256.0, 246.0 / 256.0);
        let label = uv(3.0 / 256.0, 214.0 / 256.0, 80.0 / 256.0, 246.0 / 256.0);
        let s = classify(1, true, [ev(Role::Menu, "gm_01", middle_retreat), ev(Role::Menu, "gm_01", glyph),
            ev(Role::Hud, "gc_00", label)].into_iter());
        assert!(!s.pause_menu && !s.menu);
    }

    #[test]
    fn power_icons_in_the_action_island_mean_the_land_palette() {
        let mut icon = ev(Role::Hud, "mr", uv(0.375, 0.625, 0.5, 0.75));
        icon.island = true;
        let mut orb = ev(Role::Hud, "gc_00", uv(0.0, 0.55, 0.16, 0.71));
        orb.island = true;
        assert!(classify(1, true, [icon].into_iter()).palette);
        assert!(!classify(1, true, [orb].into_iter()).palette);
        // the same icons elsewhere (menus) are not the gameplay palette
        assert!(!classify(1, true, [ev(Role::Hud, "mr", uv(0.375, 0.625, 0.5, 0.75))].into_iter()).palette);
    }

    #[test]
    fn counts_portraits_and_relocated_hud() {
        let mut hud = ev(Role::Hud, "gc_00", uv(0.0, 0.0, 0.1, 0.1));
        hud.island = true;
        let s = classify(3, true, [ev(Role::Portrait, "FB_000", uv(0.0, 0.0, 1.0, 1.0)), hud].into_iter());
        assert_eq!((s.portraits, s.hud, s.menu, s.pause_menu), (1, 1, false, false));
    }
}
