//! The pack becoming textures without holding the game up: read and decoded
//! on its own thread from start-up (`prepare`), then uploaded about 12 MB a
//! frame (`Upload`), once, kept for every visit.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::mpsc::{channel, Receiver};

use egui::TextureHandle;

use crate::pc_menus::picture::{load as load_picture, Picture};

use super::manifest::Manifest;
use super::Scene;

/// One mode's layers, as textures.
pub(super) struct Tex {
    pub(super) paper: TextureHandle,
    pub(super) stage: TextureHandle,
    pub(super) emblem: TextureHandle,
    /// added light (alpha cleared)
    pub(super) rays: TextureHandle,
    pub(super) heading: TextureHandle,
    pub(super) caption: TextureHandle,
    /// added light, Solo only
    pub(super) glow: Option<TextureHandle>,
}

/// Every layer of the scene, as textures.
pub(super) struct Art {
    pub(super) modes: Vec<Tex>,
    pub(super) band: TextureHandle,
    pub(super) controls: TextureHandle,
    pub(super) swirl: TextureHandle,
    pub(super) sprig: TextureHandle,
    /// particle shapes, white, tinted when drawn
    pub(super) feather: TextureHandle,
    pub(super) spark: TextureHandle,
    pub(super) leaves: Vec<TextureHandle>,
    pub(super) flash: TextureHandle,
}

/// The pack read and decoded: its manifest and every layer's picture, ready
/// to become textures.
pub struct Prepared {
    pub(super) root: PathBuf,
    pub(super) man: Manifest,
    pub(super) pictures: Vec<(String, Picture)>,
}

/// Starts reading the pack on its own thread (at start-up), so the main menu
/// opens without decoding anything on the game's thread.
pub fn prepare(root: PathBuf) -> Receiver<Option<Prepared>> {
    let (tx, rx) = channel();
    let _ = std::thread::Builder::new().name("menu-scene-read".into()).spawn(move || { let _ = tx.send(Prepared::read(root)); });
    rx
}

impl Prepared {
    pub(super) fn read(root: PathBuf) -> Option<Prepared> {
        let start = std::time::Instant::now();
        let text = std::fs::read_to_string(root.join("manifest.toml")).ok()?;
        let man: Manifest = toml::from_str(&text).map_err(|e| log::warn!("Main menu scene: manifest unreadable: {e}")).ok()?;
        if man.modes.len() < 4 { return None; }
        // (file, an added light: its alpha is cleared)
        let mut files: Vec<(String, bool)> = Vec::new();
        for m in &man.modes {
            for f in [&m.paper, &m.stage, &m.emblem.file, &m.heading.file, &m.caption.file] { files.push((f.clone(), false)); }
            files.push((m.rays.clone(), true));
            if let Some(g) = &m.glow { files.push((g.clone(), true)); }
        }
        let sp = &man.sprites;
        for f in [&man.band.file, &man.controls.file, &man.swirl.file, &man.sprig.file, &sp.feather, &sp.spark, &sp.flash].into_iter().chain(&sp.leaves) {
            files.push((f.clone(), false));
        }
        let mut pictures = Vec::new();
        for (f, light) in files {
            let Some(mut p) = load_picture(&root.join(&f)) else { log::warn!("Main menu scene: {f} unreadable"); return None };
            if light { for px in p.rgba.chunks_exact_mut(4) { px[3] = 0; } }
            pictures.push((f, p));
        }
        log::info!("Main menu scene: pack read in {} ms (on its own thread)", start.elapsed().as_millis());
        Some(Prepared { root, man, pictures })
    }
}

/// A prepared pack becoming textures, about 12 MB a frame, so the upload
/// never holds a frame up; then the scene.
pub struct Upload {
    pub(super) prepared: Prepared,
    made: HashMap<String, TextureHandle>,
}

impl Upload {
    pub fn new(prepared: Prepared) -> Upload { Upload { prepared, made: HashMap::new() } }

    /// Uploads the next few layers; the scene once all are up.
    pub fn step(&mut self, ctx: &egui::Context) -> Option<Scene> {
        let mut budget = 12usize << 20;
        while budget > 0 {
            let Some((f, p)) = self.prepared.pictures.pop() else { break };
            budget = budget.saturating_sub(p.rgba.len());
            let image = egui::ColorImage::from_rgba_premultiplied([p.width, p.height], &p.rgba);
            self.made.insert(f.clone(), ctx.load_texture(format!("kiu-scene-{f}"), image, egui::TextureOptions::LINEAR));
        }
        if !self.prepared.pictures.is_empty() { return None; }
        Scene::build(ctx, &self.prepared.root, self.prepared.man.clone(), &self.made)
    }
}
