//! Research aid for laying out the game's screens (KIU_MENU_CAPTURE=<folder>,
//! launcher `--menu-capture`): each time the lower screen settles on a new
//! menu screen (another set of menu archives drawing their art, or the pause
//! menu), both pictures are saved at the console's resolution as
//! `<n>-<archives>-upper.png` / `-lower.png`, so each screen can be measured
//! in console pixels. F12 saves the current pair at any moment. The files are
//! pictures of the game and stay local.
use std::collections::HashSet;
use std::path::PathBuf;

use zakuro_common::Screen;
use zakuro_core::System;
use zakuro_gpu::kiu_ui::BottomScene;
use zakuro_gpu::recipes::{self, MenuSet};

/// Frames a screen must stay before it is saved (the game's own slide-ins
/// and fades are over by then).
const SETTLE: u32 = 40;

pub struct MenuCapture {
    folder: Option<PathBuf>,
    key: Option<(MenuSet, bool)>,
    steady: u32,
    saved: HashSet<(MenuSet, bool)>,
    count: u32,
}

impl MenuCapture {
    pub fn from_environment() -> Self {
        Self { folder: std::env::var_os("KIU_MENU_CAPTURE").map(PathBuf::from), key: None, steady: 0, saved: HashSet::new(), count: 0 }
    }

    pub fn enabled(&self) -> bool { self.folder.is_some() }

    /// After each emulated frame.
    pub fn frame(&mut self, system: &mut System, scene: &BottomScene) {
        if self.folder.is_none() || !scene.fresh { return; }
        let key = (scene.lower_menus, scene.pause_menu);
        let any = scene.pause_menu || scene.lower_menus.iter().any(|w| *w != 0);
        if Some(key) != self.key { self.key = Some(key); self.steady = 0; return; }
        self.steady += 1;
        if any && self.steady == SETTLE && self.saved.insert(key) {
            self.save(system, &key, "auto");
        }
    }

    /// F12: both pictures as they are now.
    pub fn save_now(&mut self, system: &mut System) {
        let key = self.key.unwrap_or(([0; recipes::MENU_WORDS], false));
        self.save(system, &key, "f12");
    }

    fn save(&mut self, system: &mut System, key: &(MenuSet, bool), why: &str) {
        let Some(folder) = &self.folder else { return };
        let _ = std::fs::create_dir_all(folder);
        self.count += 1;
        let mut label: Vec<String> = recipes::menu_ids(&key.0).iter().map(|id| format!("{id:03}")).collect();
        if key.1 { label.push("pause".into()); }
        if label.is_empty() { label.push("none".into()); }
        let stem = format!("{:03}-{}-{}", self.count, label.join("+"), why);
        for (screen, part) in [(Screen::Top, "upper"), (Screen::Bottom, "lower")] {
            let (pixels, width, height) = system.read_screen_scaled(screen);
            let path = folder.join(format!("{stem}-{part}.png"));
            let image = native(&pixels, width, height, screen.width(), screen.height());
            match image.save(&path) {
                Ok(()) => log::info!("Screen capture: {}", path.display()),
                Err(error) => log::warn!("Screen capture failed: {error}"),
            }
        }
    }
}

/// A picture brought back to the console's resolution (averaging the scaled
/// pixels), RGBA as the presenter gets it.
fn native(pixels: &[u8], width: u32, height: u32, out_w: u32, out_h: u32) -> image::RgbaImage {
    let mut out = image::RgbaImage::new(out_w, out_h);
    if width == 0 || height == 0 || pixels.len() < (width * height * 4) as usize { return out; }
    let (sx, sy) = ((width / out_w).max(1), (height / out_h).max(1));
    for y in 0..out_h {
        for x in 0..out_w {
            let mut sum = [0u32; 4];
            for dy in 0..sy {
                for dx in 0..sx {
                    let (px, py) = ((x * sx + dx).min(width - 1), (y * sy + dy).min(height - 1));
                    let at = ((py * width + px) * 4) as usize;
                    for c in 0..4 { sum[c] += pixels[at + c] as u32; }
                }
            }
            let n = sx * sy;
            out.put_pixel(x, y, image::Rgba(sum.map(|v| (v / n) as u8)));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn scaled_pictures_come_back_to_console_pixels() {
        // a 2x picture: each console pixel is a 2x2 block
        let (w, h) = (4u32, 2u32);
        let mut pixels = vec![0u8; (w * 2 * h * 2 * 4) as usize];
        for y in 0..h * 2 { for x in 0..w * 2 {
            let at = ((y * w * 2 + x) * 4) as usize;
            pixels[at..at + 4].copy_from_slice(&[(x / 2 * 60) as u8, (y / 2 * 100) as u8, 7, 255]);
        } }
        let image = super::native(&pixels, w * 2, h * 2, w, h);
        assert_eq!(image.get_pixel(3, 1).0, [180, 100, 7, 255]);
        assert_eq!(super::native(&[], 0, 0, 4, 2).dimensions(), (4, 2));
    }
}
