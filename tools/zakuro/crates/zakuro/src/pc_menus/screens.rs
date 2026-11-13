//! The screens the PC redraws, as data: each button's place in the game's
//! sheet and in the window, the touch that presses it on the hidden lower
//! screen, and the game's own navigation map between the choices.

use crate::pc_menus::cursor::Graph;

/// One button: where it is in the sheet and where it goes in the window.
pub struct Button {
    pub name: &'static str,
    /// the button in the game's sheet, in its own pixels (the sheet is
    /// `sheet_size` wide); the shapes whose middle lies inside are its own.
    pub sheet: [u32; 4],
    /// the sheet draws it on its side (turned a quarter left).
    pub turned: bool,
    /// top-left corner in window units (the window is 240 units tall).
    pub at: [f32; 2],
    /// units per sheet pixel.
    pub scale: f32,
    /// a slight tilt, degrees clockwise, so they hang like leaves.
    pub tilt: f32,
    /// where touching the 3DS lower screen presses it.
    pub touch: (u16, u16),
    /// its choice in the game's navigation map (`Screen::graph`).
    pub node: usize,
}

/// A screen redrawn this way.
pub struct Screen {
    /// the menu archive whose art identifies the screen.
    pub id: u16,
    /// the sheet's name in the pack: `<w>x<h>-<fingerprint>.png`.
    pub sheet: &'static str,
    pub sheet_size: u32,
    pub buttons: &'static [Button],
    /// the game's navigation map between its choices (its menu parameters:
    /// each choice's up, down, left and right neighbour).
    pub graph: Graph,
    /// for each choice of the map, the upper-screen art the game shows
    /// while it is selected (texture fingerprint, 0 unknown).
    pub selected_art: &'static [u64],
}

impl Screen {
    /// Whether choice `node` of the game's map is one of the shown buttons.
    pub fn shows(&self, node: usize) -> bool { self.buttons.iter().any(|b| b.node == node) }

    /// Whether the watched upper-screen art shows any choice's art.
    pub fn any_selected(&self, watched: u32) -> bool {
        (0..self.selected_art.len()).any(|i| self.selected_art[i] != 0 && watched & (1 << i) != 0)
    }

    /// The choice the game shows selected, from the watched upper-screen
    /// art drawn this frame (kiu_ui::watch_top, in `selected_art` order):
    /// one, or none while two cross-fade.
    pub fn selected(&self, watched: u32) -> Option<usize> {
        let known = (0..self.selected_art.len()).filter(|&i| self.selected_art[i] != 0 && watched & (1 << i) != 0);
        let mut it = known;
        let first = it.next()?;
        it.next().is_none().then_some(first)
    }
}

/// The game's Back arrow, the same on every menu screen.
pub const BACK_SHEET: &str = "64x32-230262A22CA913D6.png";
pub const BACK_AT: [f32; 2] = [12.0, 210.0];
pub const BACK_SCALE: f32 = 0.5;

/// The main menu's choices in the game's map (MENUID_TOP's SelMenuParams):
/// 0 SinglePlay, 1 MultiPlay, 2 Collection, 3 Option, 4 Present
/// (StreetPass), 5 Return, 6 HowToPlay, 7 Pong. Up, down, left, right.
const MAIN_MENU_MAP: [[usize; 4]; 8] = [
    [5, 2, 4, 4], [4, 3, 2, 2], [0, 5, 1, 1], [1, 4, 5, 7],
    [3, 1, 0, 0], [2, 0, 6, 3], [1, 4, 7, 5], [1, 4, 3, 6],
];

/// The main menu: Solo, Together, Vault and Options hang from a vine on
/// the left, under the PC scene's heading (pc_menus::scene) and clear of its
/// black ground band (from 201 units), as in the v11 design. One scale for
/// all four (the art's own proportions keep Solo first), inside the safe
/// margins. StreetPass and AR Cards (3DS only) are left out.
pub const MAIN_MENU: Screen = Screen { id: 40, sheet: "256x256-701C2B1F2A647930.png", sheet_size: 256,
    buttons: &[
        Button { name: "Solo", sheet: [1, 1, 193, 86], turned: false, at: [18.0, 60.3], scale: 0.40, tilt: -2.0, touch: (104, 52), node: 0 },
        Button { name: "Together", sheet: [1, 91, 184, 180], turned: false, at: [26.0, 97.7], scale: 0.40, tilt: 2.0, touch: (224, 128), node: 1 },
        Button { name: "Vault", sheet: [0, 182, 118, 255], turned: false, at: [18.0, 136.6], scale: 0.40, tilt: -1.5, touch: (64, 140), node: 2 },
        Button { name: "Options", sheet: [203, 1, 255, 174], turned: true, at: [26.0, 171.2], scale: 0.40, tilt: 1.5, touch: (142, 211), node: 3 },
    ],
    graph: Graph { edges: &MAIN_MENU_MAP },
    // menu040/MenCmnBgUp0007Sg, 0002Ml, 0007Cl, 0007Op: the section art
    selected_art: &[0xE6C4C19E3FFA6CBC, 0xB1AD9D130D2C0DCE, 0xA19D56343FECD3C8, 0xAD4E16B8C71A4066],
};

pub const SCREENS: [&Screen; 1] = [&MAIN_MENU];

/// The back arrow's touch on the lower screen, per screen.
pub fn back_touch(id: u16) -> (u16, u16) {
    match id { 40 => (26, 220), _ => (24, 218) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn the_main_menu_stays_in_the_window_and_touches_its_screen() {
        for b in MAIN_MENU.buttons {
            let (w, h) = ((b.sheet[2] - b.sheet[0]) as f32, (b.sheet[3] - b.sheet[1]) as f32);
            let (w, h) = if b.turned { (h, w) } else { (w, h) };
            assert!(b.at[0] + w * b.scale < 426.0 && b.at[1] + h * b.scale <= 240.0, "{}", b.name);
            assert!(b.touch.0 < 320 && b.touch.1 < 240);
        }
        // the column sits under the heading (to 58 units) and above the
        // scene's black ground band (from 201), one scale, no overlaps,
        // inside the safe margin
        let mut bottom: Option<f32> = None;
        for b in MAIN_MENU.buttons {
            let h = if b.turned { b.sheet[2] - b.sheet[0] } else { b.sheet[3] - b.sheet[1] } as f32 * b.scale;
            if let Some(previous) = bottom { assert!(b.at[1] > previous, "{}", b.name); }
            bottom = Some(b.at[1] + h);
            assert_eq!(b.scale, MAIN_MENU.buttons[0].scale);
            assert!(b.at[0] >= 12.0 && b.at[1] >= 58.0);
        }
        assert!(bottom.unwrap() < 201.0);
        assert_eq!(MAIN_MENU.selected(0b0010), Some(1));
        assert_eq!(MAIN_MENU.selected(0b0110), None, "two cross-fading");
        assert_eq!(MAIN_MENU.selected(0b10000), None, "not one of the choices");
        assert_eq!(MAIN_MENU.graph.first_step(0, 2, |n| MAIN_MENU.shows(n)), Some(crate::pc_menus::cursor::Dir::Down), "Solo, then Vault below it");
        // Together to Solo goes by Vault, not by the hidden StreetPass
        assert_eq!(MAIN_MENU.graph.first_step(1, 0, |n| MAIN_MENU.shows(n)), Some(crate::pc_menus::cursor::Dir::Left));
        assert!(BACK_AT[0] >= 12.0 && BACK_AT[1] + 32.0 * BACK_SCALE <= 228.0);
    }
}
