//! The PC layouts of the game's screens (menus, pause), read from a TOML file
//! (`KIU_MENU_LAYOUTS`, normally `tools/recomp/menu_layouts.toml`) into
//! `zakuro_gpu::recipes`, and read again whenever the file changes, so a
//! layout can be tuned while the game runs. A file that does not parse keeps
//! the layouts already in use and says why in the log.
//!
//! ```toml
//! [[screen]]
//! name = "save_select"
//! when = ["020"]            # menu archives whose own art the lower screen draws; "pause"
//! unless = []               # archives that mean another screen
//! page = "#F6F5F1"          # the window's background
//! compose = true            # lower screen drawn transparent, backdrops left out
//! hide = [[56, 186, 190, 240]]   # lower-screen parts left out (3DS-only)
//!
//! [[screen.piece]]
//! from = "upper"            # or "lower"
//! src = [0, 0, 400, 240]    # console pixels (default: the whole screen)
//! anchor = "top"            # window point it hangs from: top-left, top, top-right,
//!                           # left, center, right, bottom-left, bottom, bottom-right, or [x, y]
//! at = [0, 0]               # units (the window is 240 units tall) from the anchor
//! scale = 0.6               # units per console pixel
//! fill = "height"           # or "cover", "contain": overrides scale
//! feather = [0.03, 0.02, 0.03, 0.12]
//! opacity = 1.0
//! touch = true              # default: true for lower pieces
//! ```
use std::path::PathBuf;
use std::time::SystemTime;

use serde::Deserialize;
use zakuro_gpu::recipes::{self, Fill, PieceSpec, ScreenRecipe};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct File {
    #[serde(default)]
    screen: Vec<Screen>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Screen {
    name: String,
    when: Vec<String>,
    #[serde(default)]
    unless: Vec<String>,
    page: Option<String>,
    #[serde(default)]
    compose: bool,
    #[serde(default)]
    hide: Vec<[f32; 4]>,
    #[serde(default)]
    piece: Vec<Piece>,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum Anchor { Named(String), Point([f32; 2]) }

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Piece {
    from: String,
    src: Option<[f32; 4]>,
    anchor: Option<Anchor>,
    #[serde(default)]
    at: [f32; 2],
    scale: Option<f32>,
    fill: Option<String>,
    #[serde(default)]
    feather: [f32; 4],
    opacity: Option<f32>,
    touch: Option<bool>,
}

fn anchor(a: &Option<Anchor>) -> Result<[f32; 2], String> {
    Ok(match a {
        None => [0.5, 0.5],
        Some(Anchor::Point(p)) => *p,
        Some(Anchor::Named(name)) => match name.as_str() {
            "top-left" => [0.0, 0.0], "top" => [0.5, 0.0], "top-right" => [1.0, 0.0],
            "left" => [0.0, 0.5], "center" | "centre" => [0.5, 0.5], "right" => [1.0, 0.5],
            "bottom-left" => [0.0, 1.0], "bottom" => [0.5, 1.0], "bottom-right" => [1.0, 1.0],
            other => return Err(format!("unknown anchor {other:?}")),
        },
    })
}

fn colour(text: &str) -> Result<[f32; 4], String> {
    let hex = text.trim().trim_start_matches('#');
    let value = u32::from_str_radix(hex, 16).map_err(|_| format!("bad colour {text:?}"))?;
    if hex.len() != 6 { return Err(format!("bad colour {text:?} (use #RRGGBB)")); }
    let c = |shift: u32| ((value >> shift) & 0xFF) as f32 / 255.0;
    Ok([c(16), c(8), c(0), 1.0])
}

/// The recipes a layout file describes.
pub fn parse(text: &str) -> Result<Vec<ScreenRecipe>, String> {
    let file: File = toml::from_str(text).map_err(|e| e.to_string())?;
    file.screen.into_iter().map(|screen| {
        let pieces = screen.piece.iter().map(|p| {
            let index = match p.from.as_str() { "upper" | "top" => 0, "lower" | "bottom" => 1,
                other => return Err(format!("{}: piece from {other:?} (upper or lower)", screen.name)) };
            let fill = match p.fill.as_deref() { None => Fill::Scale, Some("height") => Fill::Height,
                Some("cover") => Fill::Cover, Some("contain") => Fill::Contain,
                Some(other) => return Err(format!("{}: fill {other:?}", screen.name)) };
            Ok(PieceSpec {
                screen: index,
                source: p.src.unwrap_or(if index == 0 { [0.0, 0.0, 400.0, 240.0] } else { [0.0, 0.0, 320.0, 240.0] }),
                anchor: anchor(&p.anchor).map_err(|e| format!("{}: {e}", screen.name))?,
                at: p.at,
                scale: p.scale.unwrap_or(1.0),
                fill,
                feather: p.feather,
                opacity: p.opacity.unwrap_or(1.0),
                touch: p.touch.unwrap_or(index == 1),
            })
        }).collect::<Result<Vec<_>, String>>()?;
        Ok(ScreenRecipe {
            page: match &screen.page { Some(c) => colour(c).map_err(|e| format!("{}: {e}", screen.name))?, None => [0.0, 0.0, 0.0, 1.0] },
            name: screen.name, when: screen.when, unless: screen.unless, compose: screen.compose, hide: screen.hide, pieces,
        })
    }).collect()
}

/// Watches the layout file and keeps `zakuro_gpu::recipes` up to date.
pub struct MenuLayouts {
    path: Option<PathBuf>,
    modified: Option<SystemTime>,
    frames: u32,
}

impl MenuLayouts {
    pub fn from_environment() -> Self {
        let path = std::env::var_os("KIU_MENU_LAYOUTS").map(PathBuf::from);
        let mut layouts = Self { path, modified: None, frames: 0 };
        layouts.reload();
        layouts
    }

    /// Once a frame: reads the file again about twice a second if it changed.
    pub fn poll(&mut self) {
        if self.path.is_none() { return; }
        self.frames += 1;
        if self.frames % 30 == 0 { self.reload(); }
    }

    fn reload(&mut self) {
        let Some(path) = &self.path else { return };
        let modified = std::fs::metadata(path).and_then(|m| m.modified()).ok();
        if modified.is_none() || modified == self.modified { return; }
        self.modified = modified;
        match std::fs::read_to_string(path).map_err(|e| e.to_string()).and_then(|text| parse(&text)) {
            Ok(table) => {
                log::info!("Screen layouts: {} from {} ({})", table.len(), path.display(),
                    table.iter().map(|r| r.name.as_str()).collect::<Vec<_>>().join(", "));
                recipes::set_recipes(table);
            }
            Err(error) => log::warn!("Screen layouts in {} not used: {error}", path.display()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn a_layout_file_becomes_recipes() {
        let table = parse(r##"
            [[screen]]
            name = "save_select"
            when = ["020"]
            page = "#F6F5F1"
            compose = true
            hide = [[56, 186, 190, 240]]
            [[screen.piece]]
            from = "upper"
            anchor = "top"
            scale = 0.6
            feather = [0.03, 0.02, 0.03, 0.12]
            [[screen.piece]]
            from = "lower"
            src = [0, 188, 64, 240]
            anchor = [0.0, 1.0]
            at = [4, -4]
            scale = 0.6
            [[screen]]
            name = "pause"
            when = ["pause"]
            [[screen.piece]]
            from = "upper"
            fill = "cover"
            opacity = 0.4
        "##).unwrap();
        assert_eq!(table.len(), 2);
        let s = &table[0];
        assert!(s.compose && s.when == ["020"] && s.hide == vec![[56.0, 186.0, 190.0, 240.0]]);
        assert!((s.page[0] - 0xF6 as f32 / 255.0).abs() < 1e-6);
        assert_eq!(s.pieces[0].anchor, [0.5, 0.0]);
        assert!(!s.pieces[0].touch && s.pieces[1].touch, "lower pieces are touchable by default");
        assert_eq!(s.pieces[1].source, [0.0, 188.0, 64.0, 240.0]);
        assert_eq!(table[1].pieces[0].fill, Fill::Cover);
        assert_eq!(table[1].pieces[0].source, [0.0, 0.0, 400.0, 240.0]);
        assert!(parse("[[screen]]\nname = \"x\"\nwhen = []\n[[screen.piece]]\nfrom = \"side\"\n").is_err());
        assert!(parse("[[screen]]\nname = \"x\"\nwhen = []\nbogus = 1\n").is_err(), "typos are reported");
    }

    #[test]
    fn the_shipped_layout_file_parses() {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../recomp/menu_layouts.toml");
        if let Ok(text) = std::fs::read_to_string(&path) {
            let table = parse(&text).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
            assert!(!table.is_empty());
        }
    }
}
