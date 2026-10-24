//! How each of the game's screens is laid out on one PC window: a table of
//! recipes, one per screen, read from `tools/recomp/menu_layouts.toml` by the
//! frontend (and read again whenever the file changes, so layouts can be
//! tuned while the game runs). A recipe says which pieces of the game's two
//! pictures go where; the game keeps drawing them, with its own art,
//! animation, sounds and touch handling (see `pieces`, `kiu_ui::compose`).
//!
//! Placement is in *units*: the window is 240 units tall (a console pixel at
//! scale 1 is one unit, the size the upper screen has when it fills the
//! height). A window narrower than 16:9 shrinks the unit so a 16:9 layout
//! still fits across it. Each piece hangs from an anchor point of the window
//! (`anchor`, 0..1 across and down) by the same point of itself, moved by
//! `at` units.

use std::sync::{Arc, RwLock};

/// One screen of the game laid out for the PC window.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct ScreenRecipe {
    pub name: String,
    /// What identifies the screen: menu archives (`"020"`) whose own art the
    /// lower screen draws, any of them; `"pause"` for the in-game pause menu.
    pub when: Vec<String>,
    /// Menu archives that, drawn at the same time, mean another screen.
    pub unless: Vec<String>,
    /// The window's background (premultiplied RGBA).
    pub page: [f32; 4],
    /// The lower screen is drawn transparent, without its full-screen
    /// backdrops, so its pieces can lie over the scene (kiu_ui::compose).
    pub compose: bool,
    /// Parts of the lower screen left out (3DS-only art: HOME buttons...),
    /// console pixels, left, top, right, bottom; a draw entirely inside one
    /// is skipped.
    pub hide: Vec<[f32; 4]>,
    pub pieces: Vec<PieceSpec>,
}

/// How a piece fills the window, overriding its scale.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Fill {
    /// `scale` as given.
    #[default]
    Scale,
    /// as tall as the window.
    Height,
    /// covers the whole window, cropping what does not fit.
    Cover,
    /// as large as fits inside the window.
    Contain,
}

/// A part of one of the game's pictures and where it goes.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PieceSpec {
    /// 0 the upper screen, 1 the lower one.
    pub screen: usize,
    /// console pixels, left, top, right, bottom (the upper picture counts 400
    /// wide even when the wide view draws it at 16:9).
    pub source: [f32; 4],
    pub anchor: [f32; 2],
    pub at: [f32; 2],
    /// units per console pixel.
    pub scale: f32,
    pub fill: Fill,
    /// fade into the page from each edge, share of the piece.
    pub feather: [f32; 4],
    pub opacity: f32,
    /// clicks on it touch the lower screen there.
    pub touch: bool,
}

impl Default for PieceSpec {
    fn default() -> Self {
        Self { screen: 0, source: [0.0, 0.0, 400.0, 240.0], anchor: [0.5, 0.5], at: [0.0; 2], scale: 1.0,
            fill: Fill::Scale, feather: [0.0; 4], opacity: 1.0, touch: false }
    }
}

struct Registry {
    recipes: Arc<Vec<ScreenRecipe>>,
    generation: u32,
}

fn registry() -> &'static RwLock<Registry> {
    static REGISTRY: std::sync::OnceLock<RwLock<Registry>> = std::sync::OnceLock::new();
    REGISTRY.get_or_init(|| RwLock::new(Registry { recipes: Arc::new(Vec::new()), generation: 0 }))
}

/// Replaces the table (a fresh read of the layout file).
pub fn set_recipes(recipes: Vec<ScreenRecipe>) {
    if let Ok(mut r) = registry().write() {
        r.recipes = Arc::new(recipes);
        r.generation = r.generation.wrapping_add(1);
    }
}

/// The table as it is now.
pub fn recipes() -> Arc<Vec<ScreenRecipe>> {
    registry().read().map(|r| r.recipes.clone()).unwrap_or_default()
}

/// Bumped on every new table, so a layout drawn from it is redrawn.
pub fn generation() -> u32 { registry().read().map_or(0, |r| r.generation) }

/// The recipe at `index`, if the table still has one there.
pub fn recipe(index: u16) -> Option<ScreenRecipe> { recipes().get(index as usize).cloned() }

/// The menu archives a lower screen drew art of, one bit each.
pub type MenuSet = [u64; MENU_WORDS];
pub const MENU_WORDS: usize = 12;

pub fn menu_bit(set: &MenuSet, id: u16) -> bool {
    let (word, bit) = (id as usize / 64, id % 64);
    word < MENU_WORDS && set[word] & (1 << bit) != 0
}

/// The archive ids in a set, for logs and capture names.
pub fn menu_ids(set: &MenuSet) -> Vec<u16> {
    (0..(MENU_WORDS * 64) as u16).filter(|&id| menu_bit(set, id)).collect()
}

fn matches(token: &str, menus: &MenuSet, pause: bool) -> bool {
    if token == "pause" { return pause; }
    token.trim_start_matches("menu").parse::<u16>().is_ok_and(|id| menu_bit(menus, id))
}

/// The first recipe for what the screens show: art of these menu archives on
/// the lower screen, or the in-game pause menu.
pub fn find(menus: &MenuSet, pause: bool) -> Option<u16> {
    recipes().iter().position(|r| {
        r.when.iter().any(|t| matches(t, menus, pause)) && !r.unless.iter().any(|t| matches(t, menus, pause))
    }).map(|i| i as u16)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn set(ids: &[u16]) -> MenuSet {
        let mut s = [0u64; MENU_WORDS];
        for &id in ids { s[id as usize / 64] |= 1 << (id % 64); }
        s
    }
    #[test]
    fn screens_are_found_by_their_menu_art() {
        let make = |name: &str, when: &[&str], unless: &[&str]| ScreenRecipe { name: name.into(),
            when: when.iter().map(|s| s.to_string()).collect(), unless: unless.iter().map(|s| s.to_string()).collect(), ..Default::default() };
        set_recipes(vec![make("solo", &["030"], &["010"]), make("chapters", &["010", "menu011"], &[]), make("pause", &["pause"], &[])]);
        assert_eq!(find(&set(&[30]), false), Some(0));
        assert_eq!(find(&set(&[30, 10]), false), Some(1), "unless hands it to the next");
        assert_eq!(find(&set(&[11]), false), Some(1));
        assert_eq!(find(&set(&[]), true), Some(2));
        assert_eq!(find(&set(&[520]), false), None);
        assert_eq!(menu_ids(&set(&[3, 64, 700])), vec![3, 64, 700]);
        assert_eq!(recipe(1).unwrap().name, "chapters");
        let g = generation();
        set_recipes(Vec::new());
        assert_ne!(generation(), g);
    }
}
