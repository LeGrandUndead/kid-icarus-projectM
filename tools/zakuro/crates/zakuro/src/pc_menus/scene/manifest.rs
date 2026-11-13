//! The scene pack's manifest (manifest.toml, written by the pack builder in
//! tools/idols): where each layer of each mode goes, and each character's
//! frames and sequences.

use std::path::PathBuf;

use serde::Deserialize;

#[derive(Deserialize, Clone)]
pub struct Placed { pub file: String, pub at: [f32; 2] }
#[derive(Deserialize, Clone)]
pub struct Based { pub file: String, pub base: [f32; 2] }
#[derive(Deserialize, Clone)]
pub struct Panel { pub x0: f32, pub lean: f32 }
#[derive(Deserialize, Clone)]
pub struct Sprites { pub feather: String, pub spark: String, pub leaves: Vec<String>, pub flash: String }
#[derive(Deserialize, Clone)]
pub struct Seq { pub range: [i32; 2], #[serde(default)] pub play: Option<String>, #[serde(default)] pub impact: Option<i32> }
#[derive(Deserialize, Clone)]
pub struct Character {
    pub dir: String,
    /// [index, x, y, width, height]: each frame's file, top-left corner and
    /// size (older packs: [index, x, y])
    pub frames: Vec<Vec<i32>>,
    #[serde(default)] pub intro: Option<Seq>,
    pub idle: Seq,
    pub confirm: Seq,
}
#[derive(Deserialize, Clone)]
pub struct ModeArt {
    pub color: [u8; 3],
    pub high: [u8; 3],
    pub paper: String,
    pub stage: String,
    pub stage_scroll: f32,
    pub emblem: Placed,
    pub rays: String,
    pub rays_at: [f32; 2],
    pub heading: Based,
    pub caption: Placed,
    #[serde(default)] pub glow: Option<String>,
    pub character: Character,
}
#[derive(Deserialize, Clone)]
pub struct Manifest {
    pub band_y: f32,
    pub panel: Panel,
    pub impact: [f32; 2],
    pub band: Placed,
    pub controls: Placed,
    pub swirl: Placed,
    pub sprig: Based,
    pub sprites: Sprites,
    pub modes: Vec<ModeArt>,
}

/// The scene pack's folder: `scene-040` in the menu art pack.
pub fn pack() -> Option<PathBuf> {
    crate::pc_menus::menu_art_pack().map(|p| p.join("scene-040")).filter(|p| p.join("manifest.toml").is_file())
}
