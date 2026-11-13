//! The characters' frames: read into memory from start-up (one packed file
//! per character, or the single files), decoded by 2-4 threads from a to-do
//! list replaced every frame (needed now first, then what comes next, never
//! what already went by), shown through one texture per character updated
//! in place.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::mpsc::{channel, Receiver};
use std::sync::{Arc, Condvar, Mutex};

use egui::{Color32, TextureHandle};

use crate::pc_menus::picture::{load as load_picture, Picture};

use super::manifest::Manifest;
use super::timeline::idle_index;

/// One frame: colour (JPEG) and coverage (grey PNG), premultiplied; older
/// packs: one WebP.
pub(super) fn load_frame(dir: &Path, index: i32, files: Option<&FrameFiles>) -> Option<Picture> {
    let read;
    let (jpg, png) = match files {
        Some(f) => (&f.0, &f.1),
        None => {
            if !dir.join(format!("{index:04}.jpg")).is_file() { return load_picture(&dir.join(format!("{index:04}.webp"))); }
            read = read_frame(dir, index)?;
            (&read.0, &read.1)
        }
    };
    let rgb = image::load_from_memory_with_format(jpg, image::ImageFormat::Jpeg).ok()?.to_rgb8();
    let cover = image::load_from_memory_with_format(png, image::ImageFormat::Png).ok()?.to_luma8();
    if rgb.dimensions() != cover.dimensions() { return None; }
    let (w, h) = rgb.dimensions();
    let mut rgba = vec![0u8; w as usize * h as usize * 4];
    for ((out, c), &a) in rgba.chunks_exact_mut(4).zip(rgb.as_raw().chunks_exact(3)).zip(cover.as_raw()) {
        for k in 0..3 { out[k] = ((c[k] as u32 * a as u32 + 127) / 255) as u8; }
        out[3] = a;
    }
    Some(Picture { width: w as usize, height: h as usize, rgba })
}

/// A frame: its mode and index.
pub(super) type Key = (usize, i32);

/// A frame's two files as read from disk (JPEG colour, PNG coverage).
pub(super) type FrameFiles = (Vec<u8>, Vec<u8>);

/// A character's frames packed in one file (tools/idols/menu_v7/frame_pak.py:
/// "KIUFRAM1", the count, then index / JPEG length / PNG length per frame,
/// then the bytes in that order), read in one go.
pub(super) fn read_pak(path: &Path) -> Option<Vec<(i32, FrameFiles)>> {
    let data = std::fs::read(path).ok()?;
    let word = |at: usize| -> Option<u32> { Some(u32::from_le_bytes(data.get(at..at + 4)?.try_into().ok()?)) };
    if data.get(..8)? != b"KIUFRAM1" { return None; }
    let n = word(8)? as usize;
    let mut at = 12 + n * 12;
    let mut out = Vec::with_capacity(n);
    for k in 0..n {
        let row = 12 + k * 12;
        let (index, jl, pl) = (word(row)? as i32, word(row + 4)? as usize, word(row + 8)? as usize);
        let jpg = data.get(at..at + jl)?.to_vec();
        let png = data.get(at + jl..at + jl + pl)?.to_vec();
        at += jl + pl;
        out.push((index, (jpg, png)));
    }
    Some(out)
}

pub(super) fn read_frame(dir: &Path, index: i32) -> Option<FrameFiles> {
    Some((std::fs::read(dir.join(format!("{index:04}.jpg"))).ok()?, std::fs::read(dir.join(format!("{index:04}_a.png"))).ok()?))
}

/// Every frame's files, read into memory on their own thread from start-up
/// (about 270 MB), so decoding never waits on the disk: the first time
/// through an animation, a cold disk read per frame (two files) could not
/// keep up with 60 a second.
pub(super) type InMemory = Arc<Mutex<HashMap<Key, Arc<FrameFiles>>>>;

/// The decoders' to-do list: the frames wanted now, most urgent first. The
/// scene replaces it every frame, so a frame that went by before its turn is
/// simply dropped, and the decoders work on what is needed now.
pub(super) struct Board { pub(super) wanted: Vec<Key>, pub(super) busy: HashSet<Key>, pub(super) quit: bool }
pub(super) struct Shared { pub(super) board: Mutex<Board>, pub(super) wake: Condvar }

pub(super) struct Decoded { pub(super) key: Key, pub(super) picture: Option<Picture>, pub(super) ms: f32 }

/// One mode's character: its frames on disk, the decoded ones near the
/// playhead, and the one texture showing the current frame.
pub(super) struct Frames {
    /// corner and size of each frame
    pub(super) at: HashMap<i32, [f32; 4]>,
    pub(super) cache: HashMap<i32, Picture>,
    /// kept whatever the playhead: the first frames of its entrance, hold
    /// and confirm, so a mode always starts on its own frames
    pub(super) pinned: HashSet<i32>,
    /// the biggest frame (+1 for a clear edge): the texture's size
    pub(super) most: [usize; 2],
    pub(super) tex: Option<TextureHandle>,
    pub(super) shown: Option<i32>,
}

/// A character frame on screen: its texture, corner and size (design
/// pixels), and how much of the texture it covers.
#[derive(Clone)]
pub(super) struct Shown { pub(super) tex: TextureHandle, pub(super) at: [f32; 2], pub(super) size: [f32; 2], pub(super) uv: [f32; 2] }

pub(super) struct Stream {
    pub(super) shared: Arc<Shared>,
    pub(super) from: Receiver<Decoded>,
    pub(super) frames: Vec<Frames>,
    /// this frame's requests: needed now, then needed next
    pub(super) now: Vec<Key>,
    pub(super) next: Vec<Key>,
    /// every frame named this frame (kept in the caches), and each mode's playhead
    pub(super) named: HashSet<Key>,
    pub(super) playhead: [Option<i32>; 4],
    /// frames that could not be read (asked for once only)
    pub(super) failed: HashSet<Key>,
    /// frames shown on time, frames shown late, and the most frames late
    pub stats: [u32; 3],
    /// frames decoded, and the time they took (ms)
    pub(super) decoded: (u32, f32),
    pub(super) threads: usize,
}

impl Drop for Stream {
    fn drop(&mut self) {
        if let Ok(mut b) = self.shared.board.lock() { b.quit = true; }
        self.shared.wake.notify_all();
    }
}

impl Stream {
    pub(super) fn new(root: &Path, man: &Manifest) -> Stream {
        let shared = Arc::new(Shared { board: Mutex::new(Board { wanted: Vec::new(), busy: HashSet::new(), quit: false }), wake: Condvar::new() });
        let (tx, from) = channel::<Decoded>();
        let dirs: Vec<PathBuf> = man.modes.iter().map(|m| root.join(&m.character.dir)).collect();
        let memory: InMemory = Arc::default();
        {
            // in playing order: each mode's first frames, then each mode's
            // entrance and hold, then the rest
            let mut order: Vec<Key> = Vec::new();
            for (m, mode) in man.modes.iter().enumerate() {
                order.extend((0..10).map(|k| (m, idle_index(&mode.character, k as f32))));
            }
            for (m, mode) in man.modes.iter().enumerate() {
                let c = &mode.character;
                let span = c.intro.as_ref().map_or(0, |i| i.range[1] - i.range[0]) + c.idle.range[1] - c.idle.range[0] + 1;
                order.extend((0..span.max(0)).map(|k| (m, idle_index(c, k as f32))));
            }
            for (m, mode) in man.modes.iter().enumerate() { order.extend(mode.character.frames.iter().map(|f| (m, f[0]))); }
            let (memory, dirs) = (memory.clone(), dirs.clone());
            let _ = std::thread::Builder::new().name("menu-scene-files".into()).spawn(move || {
                let start = std::time::Instant::now();
                let mut bytes = 0usize;
                // packed characters first: one long read each
                for (m, dir) in dirs.iter().enumerate() {
                    let pak = dir.with_extension("pak");
                    if let Some(frames) = read_pak(&pak) {
                        if let Ok(mut mem) = memory.lock() {
                            for (i, files) in frames { bytes += files.0.len() + files.1.len(); mem.insert((m, i), Arc::new(files)); }
                        }
                    }
                }
                for key in order {
                    if memory.lock().map_or(true, |m| m.contains_key(&key)) { continue; }
                    let Some(files) = dirs.get(key.0).and_then(|d| read_frame(d, key.1)) else { continue };
                    bytes += files.0.len() + files.1.len();
                    if let Ok(mut m) = memory.lock() { m.insert(key, Arc::new(files)); }
                }
                log::info!("Main menu scene: character frames read into memory ({} MB) in {:.1} s", bytes >> 20, start.elapsed().as_secs_f32());
            });
        }
        // two to four decoders, leaving the game its own cores
        let n = std::thread::available_parallelism().map_or(2, |n| n.get()).saturating_sub(2).clamp(2, 4);
        for k in 0..n {
            let (shared, tx, dirs, memory) = (shared.clone(), tx.clone(), dirs.clone(), memory.clone());
            let _ = std::thread::Builder::new().name(format!("menu-scene-decode-{k}")).spawn(move || loop {
                // the most urgent frame nobody is decoding yet
                let key = {
                    let Ok(mut b) = shared.board.lock() else { return };
                    loop {
                        if b.quit { return; }
                        if let Some(&key) = b.wanted.iter().find(|key| !b.busy.contains(key)) { b.busy.insert(key); break key; }
                        b = match shared.wake.wait(b) { Ok(b) => b, Err(_) => return };
                    }
                };
                let clock = std::time::Instant::now();
                let files = memory.lock().ok().and_then(|m| m.get(&key).cloned());
                let picture = dirs.get(key.0).and_then(|d| load_frame(d, key.1, files.as_deref()));
                let ms = clock.elapsed().as_secs_f32() * 1000.0;
                if let Ok(mut b) = shared.board.lock() { b.busy.remove(&key); b.wanted.retain(|k| *k != key); }
                if tx.send(Decoded { key, picture, ms }).is_err() { return; }
            });
        }
        let frames = man.modes.iter().map(|m| {
            let c = &m.character;
            let at: HashMap<i32, [f32; 4]> = c.frames.iter().filter(|f| f.len() >= 3)
                .map(|f| (f[0], [f[1] as f32, f[2] as f32, f.get(3).copied().unwrap_or(0) as f32, f.get(4).copied().unwrap_or(0) as f32])).collect();
            let most = at.values().fold([0usize; 2], |m, r| [m[0].max(r[2] as usize + 1), m[1].max(r[3] as usize + 1)]);
            let mut pinned: HashSet<i32> = (0..10).map(|k| idle_index(c, k as f32)).collect();
            pinned.extend((0..4).map(|k| c.confirm.range[0] + k));
            Frames { at, cache: HashMap::new(), pinned, most, tex: None, shown: None }
        }).collect();
        let mut stream = Stream { shared, from, frames, now: Vec::new(), next: Vec::new(), named: HashSet::new(), playhead: [None; 4], failed: HashSet::new(), stats: [0; 3], decoded: (0, 0.0), threads: n };
        // every mode's first frames, so each starts on its own pose
        for m in 0..stream.frames.len() {
            let mut first: Vec<i32> = stream.frames[m].pinned.iter().copied().collect();
            first.sort();
            for i in first { stream.wish(m, i, false); }
        }
        stream.publish();
        stream
    }

    pub(super) fn wish(&mut self, mode: usize, index: i32, urgent: bool) {
        let key = (mode, index);
        self.named.insert(key);
        let f = &self.frames[mode];
        if !f.at.contains_key(&index) || f.cache.contains_key(&index) || self.failed.contains(&key) { return; }
        if self.now.contains(&key) || self.next.contains(&key) { return; }
        if urgent { self.now.push(key) } else { self.next.push(key) }
    }

    /// Takes in what the decoders finished.
    pub(super) fn receive(&mut self) {
        while let Ok(d) = self.from.try_recv() {
            self.decoded.0 += 1; self.decoded.1 += d.ms;
            match d.picture {
                Some(p) => { self.frames[d.key.0].cache.insert(d.key.1, p); }
                None => {
                    if self.failed.insert(d.key) { log::warn!("Menu scene: character frame {:?} unreadable", d.key); }
                }
            }
        }
    }

    /// Hands the decoders this frame's to-do list and lets go of frames no
    /// playhead is near.
    pub(super) fn publish(&mut self) {
        for (m, f) in self.frames.iter_mut().enumerate() {
            let Some(head) = self.playhead.get(m).copied().flatten() else { continue };
            let Frames { cache, pinned, shown, .. } = f;
            let named = &self.named;
            cache.retain(|i, _| pinned.contains(i) || (i - head).abs() <= 16 || Some(*i) == *shown || named.contains(&(m, *i)));
        }
        let mut wanted = std::mem::take(&mut self.now);
        wanted.append(&mut self.next);
        if let Ok(mut b) = self.shared.board.lock() { b.wanted = wanted; }
        self.shared.wake.notify_all();
        self.named.clear();
        self.playhead = [None; 4];
    }

    /// Whether frames asked for are still being decoded.
    #[cfg(test)]
    pub(super) fn pending(&self) -> bool { self.shared.board.lock().map_or(false, |b| !b.wanted.is_empty() || !b.busy.is_empty()) }

    /// The frame to show for `index` of `mode` (or the closest one before it
    /// already decoded), and the frames to have ready next.
    pub(super) fn get(&mut self, ctx: &egui::Context, mode: usize, index: i32, ahead: &[i32]) -> Option<Shown> {
        self.playhead[mode] = Some(index);
        self.wish(mode, index, true);
        for &i in ahead { self.wish(mode, i, false); }
        let f = &mut self.frames[mode];
        let best = if f.cache.contains_key(&index) { Some(index) } else {
            f.cache.keys().copied().filter(|&i| i < index && index - i <= 12).max().or(f.shown)
        }?;
        if f.shown != Some(best) {
            if let Some(p) = f.cache.get(&best) {
                // the frame and a clear row and column after it (filtering
                // never picks up what an earlier, bigger frame left there)
                let need = [p.width + 1, p.height + 1];
                if f.tex.is_none() || f.most[0] < need[0] || f.most[1] < need[1] {
                    // one texture as big as the biggest frame, made once
                    f.most = [f.most[0].max(need[0]), f.most[1].max(need[1])];
                    f.tex = Some(ctx.load_texture(format!("kiu-scene-char-{mode}"), egui::ColorImage::filled(f.most, Color32::TRANSPARENT), egui::TextureOptions::LINEAR));
                }
                let mut pixels = vec![Color32::TRANSPARENT; need[0] * need[1]];
                for (row, src) in pixels.chunks_exact_mut(need[0]).zip(p.rgba.chunks_exact(p.width * 4)) {
                    for (o, c) in row.iter_mut().zip(src.chunks_exact(4)) { *o = Color32::from_rgba_premultiplied(c[0], c[1], c[2], c[3]); }
                }
                if let Some(t) = &mut f.tex { t.set_partial([0, 0], egui::ColorImage::new(need, pixels), egui::TextureOptions::LINEAR); }
                f.shown = Some(best);
            }
        }
        let shown = f.shown?;
        if shown == index { self.stats[0] += 1; } else { self.stats[1] += 1; self.stats[2] = self.stats[2].max((index - shown).unsigned_abs()); }
        let r = *f.at.get(&shown)?;
        let tex = f.tex.clone()?;
        let p = f.cache.get(&shown).map(|p| [p.width as f32, p.height as f32]).unwrap_or([r[2], r[3]]);
        Some(Shown { tex, at: [r[0], r[1]], size: p, uv: [p[0] / f.most[0] as f32, p[1] / f.most[1] as f32] })
    }
}
