//! The main menu's scene, drawn by the PC behind the redrawn buttons
//! (native_menu): the v11 "Ink & Paper" design (tools/idols/menu_v7).
//!
//! Everything is the game's own art, prepared once from the player's ROM into
//! a scene pack (tools/idols/menu_v7/scene_pack.py ->
//! build/texture-work/menu-pc/scene-040, local only): the striped paper and
//! the mode's emblem, the mode's stage in a slanted window with the mode's
//! character relit for it, ink ornaments, the ground band, the heading,
//! caption and controls. This module plays it live, following the game's
//! own selection:
//!
//! - entry: the paper wipes in from the left, the window pulls back and slams
//!   in, the character rides in after it, the band rises, heading, caption and
//!   controls arrive one after the other;
//! - holds never stop: a slow handheld camera drifts the stage, the character
//!   and the ink at different depths, the key light breathes, rays turn,
//!   particles drift, a soft light sweeps the paper;
//! - a change of selection: an ink brush sweeps the window right to left, the
//!   new mode's paper colour is revealed by its edge behind it, the old stage
//!   and character are pushed out, the new ones arrive in depth layers, the old
//!   heading falls away and the new one drops and squashes on landing;
//! - confirm: the menu leaves, the character does its move (Together: the
//!   throw and the kick, with impact frames and hit-stop), an ink line cuts
//!   the picture and its halves part once the game shows its next screen;
//! - leaving another way (Back, keyboard): the menu leaves and the same cut
//!   reveals the game.
//!
//! Times are in frames at 60 per second, counted from real time, so it is
//! smooth at any refresh rate. Positions are in the design's 1920x1080
//! pixels, scaled to cover the window.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::Arc;

use egui::{Color32, Mesh, Pos2, Rect, TextureHandle};
use serde::Deserialize;

use crate::native_menu::{load as load_picture, Picture};

const W: f32 = 1920.0;
const H: f32 = 1080.0;
const GOLD: [u8; 3] = [255, 208, 84];
const INK: [u8; 3] = [12, 8, 14];

// --- the pack ----------------------------------------------------------------------

#[derive(Deserialize, Clone)]
pub struct Placed { pub file: String, pub at: [f32; 2] }
#[derive(Deserialize, Clone)]
pub struct Based { pub file: String, pub base: [f32; 2] }
#[derive(Deserialize, Clone)]
pub struct Panel { pub x0: f32, pub lean: f32 }
#[derive(Deserialize, Clone)]
pub struct Sprites { pub feather: String, pub spark: String, pub powder: String, pub leaves: Vec<String>, pub flash: String }
#[derive(Deserialize, Clone)]
pub struct Seq { pub range: [i32; 2], #[serde(default)] pub play: Option<String>, #[serde(default)] pub impact: Option<i32> }
#[derive(Deserialize, Clone)]
pub struct Character {
    pub dir: String,
    /// [index, x, y]: each frame's file and top-left corner
    pub frames: Vec<[i32; 3]>,
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
    crate::native_menu::pack().map(|p| p.join("scene-040")).filter(|p| p.join("manifest.toml").is_file())
}

// --- motion helpers (tools/idols/menu_v7/anim.py) ------------------------------------

fn clamp01(t: f32) -> f32 { t.clamp(0.0, 1.0) }
#[derive(Clone, Copy)]
enum Ease { Out, In, InOut, OutBack, Spring }
fn ease(e: Ease, t: f32) -> f32 {
    match e {
        Ease::Out => 1.0 - (1.0 - t).powi(4),
        Ease::In => t * t * t,
        Ease::InOut => if t < 0.5 { 4.0 * t * t * t } else { 1.0 - (-2.0 * t + 2.0).powi(3) / 2.0 },
        Ease::OutBack => { let (s, t) = (1.7, t - 1.0); t * t * ((s + 1.0) * t + s) + 1.0 }
        Ease::Spring => 1.0 - (-9.0 * t).exp() * (2.0 * std::f32::consts::PI * 2.5 * t).cos(),
    }
}
/// A value keyed at frames; each key says how it is reached.
fn track(f: f32, keys: &[(f32, f32, Ease)]) -> f32 {
    if f <= keys[0].0 { return keys[0].1; }
    for w in keys.windows(2) {
        let (a, b) = (w[0], w[1]);
        if f <= b.0 { return a.1 + (b.1 - a.1) * ease(b.2, clamp01((f - a.0) / (b.0 - a.0).max(1e-6))); }
    }
    keys[keys.len() - 1].1
}
fn k2(f0: f32, v0: f32, f1: f32, v1: f32, e: Ease, f: f32) -> f32 { track(f, &[(f0, v0, Ease::Out), (f1, v1, e)]) }
/// A decaying shake, alternating sides each frame.
fn shake(f: f32, start: f32, frames: f32, amp: f32, seed: u32) -> f32 {
    let t = (f - start).floor();
    if t < 0.0 || t >= frames { return 0.0; }
    let a = amp * (1.0 - t / frames).powi(2);
    let s = if (t as i32) % 2 == 1 { -1.0 } else { 1.0 };
    a * s * (0.6 + 0.4 * hash01(seed * 1000 + t as u32))
}
fn hash01(n: u32) -> f32 {
    let mut x = n.wrapping_mul(0x9E37_79B9) ^ 0x85EB_CA6B;
    x ^= x >> 15; x = x.wrapping_mul(0x2C1B_3C6D); x ^= x >> 12; x = x.wrapping_mul(0x297A_2D39); x ^= x >> 15;
    (x as f32) / (u32::MAX as f32)
}
/// A small deterministic random sequence.
struct Rng(u32);
impl Rng {
    fn f(&mut self, a: f32, b: f32) -> f32 { self.0 = self.0.wrapping_add(1); a + (b - a) * hash01(self.0) }
}
/// The slow handheld camera.
fn cam(v: f32) -> [f32; 2] {
    use std::f32::consts::TAU;
    [18.0 * (TAU * v / 240.0).sin() + 7.0 * (TAU * v / 97.0 + 1.0).sin(),
     9.0 * (TAU * v / 300.0 + 2.0).sin() + 4.0 * (TAU * v / 131.0).sin()]
}

// --- drawing: meshes in design pixels --------------------------------------------------

/// A point and its texture coordinate.
#[derive(Clone, Copy)]
struct Vx { p: [f32; 2], uv: [f32; 2], c: Color32 }
/// The half-plane a*x + b*y + c >= 0.
#[derive(Clone, Copy)]
struct Half { a: f32, b: f32, c: f32 }
impl Half {
    fn at(&self, p: [f32; 2]) -> f32 { self.a * p[0] + self.b * p[1] + self.c }
    /// Right of the slanted line through x0 (at the top, y = -40) leaning `lean` to the bottom (y = H + 40).
    fn right_of(x0: f32, lean: f32) -> Half { let k = lean / (H + 80.0); Half { a: 1.0, b: k, c: 40.0 * k - x0 } }
    fn left_of(x0: f32, lean: f32) -> Half { let r = Half::right_of(x0, lean); Half { a: -r.a, b: -r.b, c: -r.c } }
}
fn lerp_vx(a: Vx, b: Vx, t: f32) -> Vx {
    let l = |x: f32, y: f32| x + (y - x) * t;
    let lc = |x: u8, y: u8| (x as f32 + (y as f32 - x as f32) * t).round() as u8;
    Vx { p: [l(a.p[0], b.p[0]), l(a.p[1], b.p[1])], uv: [l(a.uv[0], b.uv[0]), l(a.uv[1], b.uv[1])],
         c: Color32::from_rgba_premultiplied(lc(a.c.r(), b.c.r()), lc(a.c.g(), b.c.g()), lc(a.c.b(), b.c.b()), lc(a.c.a(), b.c.a())) }
}
/// Sutherland-Hodgman: the part of a convex polygon inside `h`.
fn clip(poly: &[Vx], h: Half) -> Vec<Vx> {
    let mut out = Vec::with_capacity(poly.len() + 2);
    for i in 0..poly.len() {
        let (a, b) = (poly[i], poly[(i + 1) % poly.len()]);
        let (da, db) = (h.at(a.p), h.at(b.p));
        if da >= 0.0 { out.push(a); }
        if (da >= 0.0) != (db >= 0.0) { out.push(lerp_vx(a, b, da / (da - db))); }
    }
    out
}

/// The picture being built: meshes in design pixels, in drawing order.
#[derive(Default)]
struct Canvas { meshes: Vec<Mesh>, clips: Vec<Half> }
impl Canvas {
    /// A convex polygon, clipped by the current clips.
    fn poly(&mut self, tex: egui::TextureId, pts: &[Vx]) {
        let mut poly = pts.to_vec();
        for h in &self.clips { poly = clip(&poly, *h); if poly.len() < 3 { return; } }
        let mut m = Mesh::with_texture(tex);
        for v in &poly { m.vertices.push(egui::epaint::Vertex { pos: Pos2::new(v.p[0], v.p[1]), uv: Pos2::new(v.uv[0], v.uv[1]), color: v.c }); }
        for i in 1..poly.len() as u32 - 1 { m.add_triangle(0, i, i + 1); }
        self.meshes.push(m);
    }
    /// A picture over the rectangle (x, y, w, h), turned `deg` about `pivot`, tinted.
    fn image(&mut self, tex: &TextureHandle, r: [f32; 4], deg: f32, pivot: [f32; 2], tint: Color32) {
        let (s, c) = deg.to_radians().sin_cos();
        let rot = |x: f32, y: f32| [pivot[0] + (x - pivot[0]) * c - (y - pivot[1]) * s, pivot[1] + (x - pivot[0]) * s + (y - pivot[1]) * c];
        let [x, y, w, h] = r;
        let pts = [Vx { p: rot(x, y), uv: [0.0, 0.0], c: tint }, Vx { p: rot(x + w, y), uv: [1.0, 0.0], c: tint },
                   Vx { p: rot(x + w, y + h), uv: [1.0, 1.0], c: tint }, Vx { p: rot(x, y + h), uv: [0.0, 1.0], c: tint }];
        self.poly(tex.id(), &pts);
    }
    fn image_at(&mut self, tex: &TextureHandle, at: [f32; 2], tint: Color32) {
        let s = tex.size();
        self.image(tex, [at[0], at[1], s[0] as f32, s[1] as f32], 0.0, at, tint);
    }
    /// An untextured convex polygon, one colour per corner.
    fn fill(&mut self, pts: &[([f32; 2], Color32)]) {
        let v: Vec<Vx> = pts.iter().map(|&(p, c)| Vx { p, uv: [0.0, 0.0], c }).collect();
        let mut v = v; for x in &mut v { x.uv = [egui::epaint::WHITE_UV.x, egui::epaint::WHITE_UV.y]; }
        self.poly(egui::TextureId::default(), &v);
    }
    /// Draws everything, mapped from design pixels to the window; with a cut,
    /// each side of the line moved apart by `gap` along its normal.
    fn emit(self, painter: &egui::Painter, map: &Map, cut: Option<(Half, [f32; 2], f32)>) {
        for mesh in self.meshes {
            let parts: Vec<(Mesh, [f32; 2])> = match cut {
                None => vec![(mesh, [0.0, 0.0])],
                Some((h, n, gap)) => {
                    let other = Half { a: -h.a, b: -h.b, c: -h.c };
                    vec![(split(&mesh, h), [n[0] * gap, n[1] * gap]), (split(&mesh, other), [-n[0] * gap, -n[1] * gap])]
                }
            };
            for (mut m, d) in parts {
                if m.vertices.is_empty() { continue; }
                for v in &mut m.vertices { v.pos = map.pos([v.pos.x + d[0], v.pos.y + d[1]]); }
                painter.add(egui::Shape::mesh(m));
            }
        }
    }
}
/// The part of a mesh's triangles inside `h`.
fn split(mesh: &Mesh, h: Half) -> Mesh {
    let mut out = Mesh::with_texture(mesh.texture_id);
    let vx = |i: u32| { let v = mesh.vertices[i as usize]; Vx { p: [v.pos.x, v.pos.y], uv: [v.uv.x, v.uv.y], c: v.color } };
    for t in mesh.indices.chunks_exact(3) {
        let poly = clip(&[vx(t[0]), vx(t[1]), vx(t[2])], h);
        if poly.len() < 3 { continue; }
        let base = out.vertices.len() as u32;
        for v in &poly { out.vertices.push(egui::epaint::Vertex { pos: Pos2::new(v.p[0], v.p[1]), uv: Pos2::new(v.uv[0], v.uv[1]), color: v.c }); }
        for i in 1..poly.len() as u32 - 1 { out.add_triangle(base, base + i, base + i + 1); }
    }
    out
}

/// Design pixels to window points: the 1920x1080 design covers the window.
struct Map { origin: Pos2, scale: f32 }
impl Map {
    fn new(window: Rect) -> Map {
        let scale = (window.width() / W).max(window.height() / H);
        let origin = Pos2::new(window.center().x - W * scale / 2.0, window.center().y - H * scale / 2.0);
        Map { origin, scale }
    }
    fn pos(&self, p: [f32; 2]) -> Pos2 { Pos2::new(self.origin.x + p[0] * self.scale, self.origin.y + p[1] * self.scale) }
    fn design(&self, p: Pos2) -> [f32; 2] { [(p.x - self.origin.x) / self.scale, (p.y - self.origin.y) / self.scale] }
}

fn faded(a: f32) -> Color32 { let k = (clamp01(a) * 255.0) as u8; Color32::from_rgba_premultiplied(k, k, k, k) }
/// Tint for an added light (its texture holds the colour with alpha 0).
fn light(a: f32) -> Color32 { let k = (clamp01(a) * 255.0) as u8; Color32::from_rgba_premultiplied(k, k, k, 0) }
fn rgba(c: [u8; 3], a: f32) -> Color32 {
    let k = clamp01(a);
    Color32::from_rgba_premultiplied((c[0] as f32 * k) as u8, (c[1] as f32 * k) as u8, (c[2] as f32 * k) as u8, (k * 255.0) as u8)
}
fn additive(c: [u8; 3], a: f32) -> Color32 {
    let k = clamp01(a);
    Color32::from_rgba_premultiplied((c[0] as f32 * k) as u8, (c[1] as f32 * k) as u8, (c[2] as f32 * k) as u8, 0)
}
fn mix(a: [u8; 3], b: [u8; 3], k: f32) -> [u8; 3] {
    [0, 1, 2].map(|i| (a[i] as f32 + (b[i] as f32 - a[i] as f32) * k) as u8)
}

// --- character frames, decoded off the main thread -------------------------------------

struct Decoded { mode: usize, index: i32, picture: Picture }

/// One mode's character: its frames on disk, the decoded ones near the
/// playhead, and the texture showing the current one.
struct Frames {
    dir: PathBuf,
    at: HashMap<i32, [f32; 2]>,
    cache: HashMap<i32, Arc<Picture>>,
    asked: HashSet<i32>,
    tex: Option<TextureHandle>,
    shown: Option<i32>,
}

struct Stream { to: Sender<(usize, i32, PathBuf)>, from: Receiver<Decoded>, frames: Vec<Frames> }
impl Stream {
    fn new(root: &Path, man: &Manifest) -> Stream {
        let (to, rx) = channel::<(usize, i32, PathBuf)>();
        let (tx, from) = channel::<Decoded>();
        // two decoders share the requests
        let rx = Arc::new(std::sync::Mutex::new(rx));
        for n in 0..2 {
            let (rx, tx) = (rx.clone(), tx.clone());
            let _ = std::thread::Builder::new().name(format!("menu-scene-decode-{n}")).spawn(move || loop {
                let job = { let Ok(r) = rx.lock() else { return }; r.recv() };
                let Ok((mode, index, path)) = job else { return };
                if let Some(picture) = load_picture(&path) { if tx.send(Decoded { mode, index, picture }).is_err() { return; } }
            });
        }
        let frames = man.modes.iter().map(|m| Frames {
            dir: root.join(&m.character.dir),
            at: m.character.frames.iter().map(|f| (f[0], [f[1] as f32, f[2] as f32])).collect(),
            cache: HashMap::new(), asked: HashSet::new(), tex: None, shown: None,
        }).collect();
        Stream { to, from, frames }
    }
    fn ask(&mut self, mode: usize, index: i32) {
        let f = &mut self.frames[mode];
        if !f.at.contains_key(&index) || f.cache.contains_key(&index) || f.asked.contains(&index) { return; }
        f.asked.insert(index);
        let _ = self.to.send((mode, index, f.dir.join(format!("{index:04}.webp"))));
    }
    /// Whether frames asked for are still being decoded.
    #[cfg(test)]
    fn pending(&self) -> bool { self.frames.iter().any(|f| !f.asked.is_empty()) }
    fn receive(&mut self) {
        while let Ok(d) = self.from.try_recv() {
            let f = &mut self.frames[d.mode];
            f.asked.remove(&d.index);
            f.cache.insert(d.index, Arc::new(d.picture));
        }
    }
    /// The texture for `index` (or the nearest frame already decoded), and its corner;
    /// asks for the frames coming next.
    fn get(&mut self, ctx: &egui::Context, mode: usize, index: i32, ahead: &[i32]) -> Option<(TextureHandle, [f32; 2])> {
        self.ask(mode, index);
        for &i in ahead { self.ask(mode, i); }
        let f = &mut self.frames[mode];
        // keep the cache near the playhead
        if f.cache.len() > 48 {
            let keep: HashSet<i32> = std::iter::once(index).chain(ahead.iter().copied()).collect();
            f.cache.retain(|i, _| keep.contains(i) || (i - index).abs() < 6);
        }
        let best = if f.cache.contains_key(&index) { Some(index) } else { f.shown.filter(|s| f.cache.contains_key(s)).or(f.shown) };
        let best = best?;
        if f.shown != Some(best) {
            if let Some(p) = f.cache.get(&best) {
                let image = egui::ColorImage::from_rgba_premultiplied([p.width, p.height], &p.rgba);
                match &mut f.tex {
                    Some(t) => t.set(image, egui::TextureOptions::LINEAR),
                    None => f.tex = Some(ctx.load_texture(format!("kiu-scene-char-{mode}"), image, egui::TextureOptions::LINEAR)),
                }
                f.shown = Some(best);
            }
        }
        let at = *f.at.get(&best)?;
        f.tex.clone().map(|t| (t, at))
    }
}

/// Which character frame a mode shows `t` frames after it was selected.
fn idle_index(c: &Character, t: f32) -> i32 {
    let mut t = t.max(0.0);
    if let Some(intro) = &c.intro {
        let len = (intro.range[1] - intro.range[0]) as f32;
        if t < len { return intro.range[0] + t as i32; }
        t -= len;
    }
    let [a, b] = c.idle.range;
    let len = (b - a).max(1) as f32;
    match c.idle.play.as_deref() {
        Some("pingpong") => {
            // back and forth, slowing into each turn (a moving hold)
            let p = (t / len) % 2.0;
            let tri = if p < 1.0 { p } else { 2.0 - p };
            let s = tri * tri * (3.0 - 2.0 * tri);
            a + (s * len).round() as i32
        }
        _ => a + (t as i32).rem_euclid(len as i32 + 1),
    }
}

// --- the scene ------------------------------------------------------------------------

struct Tex { paper: TextureHandle, stage: TextureHandle, emblem: TextureHandle, rays: TextureHandle, heading: TextureHandle, caption: TextureHandle, glow: Option<TextureHandle> }
struct Art {
    modes: Vec<Tex>,
    band: TextureHandle, controls: TextureHandle, swirl: TextureHandle, sprig: TextureHandle,
    feather: TextureHandle, spark: TextureHandle, powder: TextureHandle, leaves: Vec<TextureHandle>, flash: TextureHandle,
}

fn load_tex(ctx: &egui::Context, root: &Path, file: &str, light: bool) -> Option<TextureHandle> {
    let mut p = load_picture(&root.join(file))?;
    if light { for px in p.rgba.chunks_exact_mut(4) { px[3] = 0; } }    // an added light
    let image = egui::ColorImage::from_rgba_premultiplied([p.width, p.height], &p.rgba);
    Some(ctx.load_texture(format!("kiu-scene-{file}"), image, egui::TextureOptions::LINEAR))
}

/// What the scene is doing.
#[derive(Clone, Copy, PartialEq, Debug)]
enum Phase {
    Shown,
    /// the player confirmed this mode at this time (seconds)
    Confirming { mode: usize, at: f64 },
    /// the menu went away another way
    Leaving { at: f64 },
}

pub struct Scene {
    man: Manifest,
    art: Art,
    stream: Stream,
    /// when it appeared (seconds)
    start: f64,
    selected: usize,
    previous: usize,
    /// when the selection last changed
    changed: Option<f64>,
    /// when each mode became selected (its character's clock)
    chosen_at: [f64; 4],
    phase: Phase,
    /// when the game left the menu (the cut waits for it)
    game_left: Option<f64>,
    time: f64,
    /// where the pressed button was (design pixels)
    pressed_at: Option<[f32; 2]>,
}

impl Scene {
    pub fn load(ctx: &egui::Context, root: &Path) -> Option<Scene> {
        let text = std::fs::read_to_string(root.join("manifest.toml")).ok()?;
        let man: Manifest = toml::from_str(&text).map_err(|e| log::warn!("Menu scene: manifest unreadable: {e}")).ok()?;
        if man.modes.len() < 4 { return None; }
        let t = |f: &str| load_tex(ctx, root, f, false);
        let l = |f: &str| load_tex(ctx, root, f, true);
        let mut modes = Vec::new();
        for m in &man.modes {
            modes.push(Tex { paper: t(&m.paper)?, stage: t(&m.stage)?, emblem: t(&m.emblem.file)?, rays: l(&m.rays)?,
                             heading: t(&m.heading.file)?, caption: t(&m.caption.file)?, glow: m.glow.as_deref().and_then(l) });
        }
        let s = &man.sprites;
        let art = Art { modes, band: t(&man.band.file)?, controls: t(&man.controls.file)?, swirl: t(&man.swirl.file)?, sprig: t(&man.sprig.file)?,
                        feather: t(&s.feather)?, spark: t(&s.spark)?, powder: t(&s.powder)?,
                        leaves: s.leaves.iter().filter_map(|f| t(f)).collect(), flash: t(&s.flash)? };
        let mut stream = Stream::new(root, &man);
        // the first frames of every mode, so the first change has its character ready
        for m in 0..4 {
            let c = &man.modes[m].character;
            for k in 0..6 { stream.ask(m, idle_index(c, k as f32)); }
        }
        let now = ctx.input(|i| i.time);
        log::info!("Main menu scene: the PC's ink and paper menu ({} character frames)", man.modes.iter().map(|m| m.character.frames.len()).sum::<usize>());
        Some(Scene { man, art, stream, start: now, selected: 0, previous: 0, changed: None,
                     chosen_at: [now; 4], phase: Phase::Shown, game_left: None, time: now, pressed_at: None })
    }

    /// The game's selected choice this frame (its node: 0 Solo .. 3 Options).
    pub fn select(&mut self, node: Option<usize>) {
        let Some(node) = node.filter(|&n| n < 4) else { return };
        if node != self.selected && self.phase == Phase::Shown {
            self.previous = self.selected;
            self.selected = node;
            self.changed = Some(self.time);
            self.chosen_at[node] = self.time;
        }
    }

    /// The player confirmed choice `node` (a click on its button, at `at`).
    pub fn confirm(&mut self, node: usize, at: Option<Pos2>, window: Rect) {
        if node >= 4 || self.phase != Phase::Shown { return; }
        if node != self.selected { self.previous = self.selected; self.selected = node; self.changed = Some(self.time); }
        self.pressed_at = at.map(|p| Map::new(window).design(p));
        self.phase = Phase::Confirming { mode: node, at: self.time };
    }

    /// The game has left the menu screen.
    pub fn game_left(&mut self) {
        if self.game_left.is_none() { self.game_left = Some(self.time); }
        if self.phase == Phase::Shown { self.phase = Phase::Leaving { at: self.time }; }
    }

    /// The player is going back (the Back arrow).
    pub fn back(&mut self) { if self.phase == Phase::Shown { self.phase = Phase::Leaving { at: self.time }; } }

    /// Whether the menu's own pieces (buttons) take input.
    pub fn interactive(&self) -> bool { self.phase == Phase::Shown }

    fn frames_since(&self, t: f64) -> f32 { ((self.time - t) * 60.0) as f32 }

    /// How far the menu has left (0 here .. 1 gone), for element `i` of the
    /// leaving order (0 heading, 1 buttons, 3 caption, 4 controls).
    fn out_k(&self, i: usize) -> f32 {
        let c = match self.phase {
            Phase::Shown => return 0.0,
            Phase::Confirming { at, .. } => self.frames_since(at) - 4.0,
            Phase::Leaving { at } => self.frames_since(at),
        };
        k2(0.0, 0.0, 12.0, 1.0, Ease::In, c - 3.0 * i as f32)
    }

    /// Where button `i` is (a horizontal offset in window units of 240 per
    /// height) and how visible: it arrives from the left on entry, staggered,
    /// and leaves to the left.
    pub fn button_presence(&self, i: usize) -> (f32, f32) {
        let v = self.frames_since(self.start) - 28.0 - 3.0 * i as f32;
        let arrive = track(v, &[(0.0, 0.0, Ease::Out), (18.0, 1.0, Ease::OutBack)]);
        let alpha = k2(0.0, 0.0, 12.0, 1.0, Ease::Out, v);
        let leave = { let c = match self.phase { Phase::Shown => -1.0, Phase::Confirming { at, .. } => self.frames_since(at) - 4.0, Phase::Leaving { at } => self.frames_since(at) };
                      k2(0.0, 0.0, 12.0, 1.0, Ease::In, c - 3.0 - 2.0 * i as f32) };
        let dx_px = -560.0 * (1.0 - arrive) - 900.0 * leave;
        (dx_px / 4.5, alpha * (1.0 - leave))
    }

    /// Frames since the confirm, when the character's move hits (Together), and when the cut comes.
    fn confirm_plan(&self, mode: usize) -> (f32, Option<f32>, f32) {
        let c = &self.man.modes[mode].character.confirm;
        let len = (c.range[1] - c.range[0]) as f32;
        let speed = if len > 70.0 { 1.5 } else { 1.0 };
        let hit = c.impact.map(|i| 4.0 + (i - c.range[0]) as f32 / speed);
        let cut = match hit { Some(h) => h + 26.0, None => 4.0 + len / speed + 4.0 };
        (speed, hit, cut.min(80.0))
    }

    /// Draws the scene. Returns false once it has finished leaving.
    pub fn show(&mut self, ctx: &egui::Context, window: Rect) -> bool {
        self.time = ctx.input(|i| i.time);
        self.stream.receive();
        // Enter or Space confirms the selection, as the game itself will
        if self.phase == Phase::Shown && ctx.input(|i| i.key_pressed(egui::Key::Enter) || i.key_pressed(egui::Key::Space)) {
            self.phase = Phase::Confirming { mode: self.selected, at: self.time };
        }
        let map = Map::new(window);
        let v = self.frames_since(self.start);
        let mut cv = Canvas::default();
        let cut = self.draw(ctx, &mut cv, v);
        let painter = ctx.layer_painter(egui::LayerId::new(egui::Order::Background, egui::Id::new("kiu-menu-scene")));
        let done = matches!(cut, Some((_, _, gap)) if gap >= 2200.0);
        let cut = cut.map(|(h, n, gap)| (h, n, gap));
        cv.emit(&painter, &map, cut);
        ctx.request_repaint();
        !done
    }

    /// Builds the picture; returns the cut (line, its normal, how far apart) once it runs.
    fn draw(&mut self, ctx: &egui::Context, cv: &mut Canvas, v: f32) -> Option<(Half, [f32; 2], f32)> {
        let cur = self.selected;
        let prev = self.previous;
        let ts = self.changed.map_or(1e6, |t| self.frames_since(t));
        let swapping = ts < 26.0;
        let show = if ts >= 9.0 { cur } else { prev };
        let [cx, cy] = cam(v);
        let man = self.man.clone();
        let p0 = man.panel.x0; let lean = man.panel.lean;
        // the confirm, its hit and cut
        let (conf, conf_c) = match self.phase { Phase::Confirming { mode, at } => (Some(mode), self.frames_since(at)), _ => (None, 0.0) };
        let (speed, hit, cut_at) = conf.map_or((1.0, None, 1e6), |m| self.confirm_plan(m));
        let hold = 10.0;
        let hitstop = hit.is_some_and(|h| conf_c >= h && conf_c < h + hold);
        let after_hit = hit.map(|h| conf_c - h);
        // 1. paper: wipes in from the left; a new mode's colour is revealed by its edge behind the brush
        let px = k2(0.0, -W, 8.0, 0.0, Ease::Out, v);
        let paper = |cv: &mut Canvas, m: usize, x0: f32| {
            let t = &self.art.modes[m].paper;
            cv.poly(t.id(), &[Vx { p: [x0 + px, 0.0], uv: [x0 / W, 0.0], c: Color32::WHITE }, Vx { p: [W + px, 0.0], uv: [1.0, 0.0], c: Color32::WHITE },
                               Vx { p: [W + px, H], uv: [1.0, 1.0], c: Color32::WHITE }, Vx { p: [x0 + px, H], uv: [x0 / W, 1.0], c: Color32::WHITE }]);
        };
        if swapping {
            paper(cv, prev, 0.0);
            let pe = track(ts, &[(3.0, W + 500.0, Ease::Out), (24.0, -700.0, Ease::InOut)]);
            cv.clips.push(Half::right_of(pe, 330.0)); paper(cv, cur, 0.0); cv.clips.pop();
        } else { paper(cv, cur, 0.0); }
        // the window's light spilling on the paper, and a soft sweep across it
        if v >= 8.0 {
            let hi = man.modes[show].high;
            let (a, b) = (additive(hi, 0.16), additive(hi, 0.0));
            cv.fill(&[([p0 - 520.0, -40.0], b), ([p0, -40.0], a), ([p0 - lean, H + 40.0], a), ([p0 - 520.0 - lean, H + 40.0], b)]);
            let p = ((v % 300.0) / 300.0) * 2600.0 - 700.0;
            let (z, w) = (additive([255, 255, 255], 0.0), additive([255, 248, 235], 0.10));
            for (x0, x1, c0, c1) in [(p - 160.0, p, z, w), (p, p + 160.0, w, z)] {
                cv.fill(&[([x0, 0.0], c0), ([x1, 0.0], c1), ([x1 - 0.6 * H, H], c1), ([x0 - 0.6 * H, H], c0)]);
            }
        }
        // 2. the watermark: turns in for the new mode, keeps breathing
        let breathe = 1.5 * (std::f32::consts::TAU * v / 420.0).sin();
        let emblem = |cv: &mut Canvas, m: usize, sc: f32, rot: f32, a: f32| {
            if a <= 0.01 { return; }
            let t = &self.art.modes[m].emblem; let at = man.modes[m].emblem.at; let s = t.size();
            let (w, h) = (s[0] as f32 * sc, s[1] as f32 * sc);
            let c = [at[0] + s[0] as f32 / 2.0 + 10.0 * (std::f32::consts::TAU * v / 360.0).sin(), at[1] + s[1] as f32 / 2.0 + 8.0 * (std::f32::consts::TAU * v / 290.0).sin()];
            cv.image(t, [c[0] - w / 2.0, c[1] - h / 2.0, w, h], rot, c, faded(a));
        };
        if self.changed.is_some() {
            if ts < 12.0 { let k = k2(0.0, 0.0, 10.0, 1.0, Ease::In, ts); emblem(cv, prev, 1.0 - 0.12 * k, breathe - 8.0 * k, 1.0 - k); }
            emblem(cv, cur, track(ts, &[(6.0, 0.8, Ease::Out), (24.0, 1.0, Ease::OutBack)]), breathe + track(ts, &[(6.0, 10.0, Ease::Out), (24.0, 0.0, Ease::OutBack)]), k2(6.0, 0.0, 12.0, 1.0, Ease::Out, ts));
        } else {
            emblem(cv, cur, track(v, &[(10.0, 0.86, Ease::Out), (28.0, 1.0, Ease::OutBack)]), breathe, k2(10.0, 0.0, 18.0, 1.0, Ease::Out, v));
        }
        // 3. the window: pulls back and slams in on entry
        let pdx = track(v, &[(0.0, 1500.0, Ease::Out), (6.0, 1500.0, Ease::Out), (20.0, 0.0, Ease::OutBack)]);
        let sx_hit = hit.map_or(0.0, |h| shake(conf_c, h, hold + 10.0, 6.0, 2));
        let vx_hit = hit.map_or(0.0, |h| shake(conf_c, h, hold + 10.0, 20.0, 3));
        let kx = shake(v, 20.0, 8.0, 7.0, 1);
        let panel_clip = Half::right_of(p0 + pdx, lean);
        let impact_frame = hit.is_some_and(|h| conf_c >= h && conf_c < h + 2.0);
        // the character's frame for a mode now
        let char_index = |s: &Scene, m: usize| -> (i32, Vec<i32>) {
            let c = &s.man.modes[m].character;
            if conf == Some(m) && conf_c >= 4.0 {
                let mut f = (conf_c - 4.0) * speed;
                if let (Some(h), Some(i)) = (hit, c.confirm.impact) {
                    let hit_f = (h - 4.0) * speed;
                    if f >= hit_f { f = if f < hit_f + hold { hit_f } else { f - hold }; }
                    let _ = i;
                }
                let i = (c.confirm.range[0] + f as i32).min(c.confirm.range[1]);
                return (i, (1..5).map(|k| (i + k).min(c.confirm.range[1])).collect());
            }
            let t = s.frames_since(s.chosen_at[m]);
            let i = idle_index(c, t);
            let ahead: Vec<i32> = (1..6).map(|k| idle_index(c, t + k as f32)).collect();
            // a confirm may come any time: keep its first frames ready
            let mut ahead = ahead; ahead.extend((0..3).map(|k| c.confirm.range[0] + k));
            (i, ahead)
        };
        let content = |s: &mut Scene, cv: &mut Canvas, m: usize, slide: f32, sslide: f32| -> Option<(TextureHandle, [f32; 4])> {
            let art = &s.art.modes[m]; let ma = &man.modes[m];
            let stage = &art.stage; let ss = stage.size(); let (sw, sh) = (ss[0] as f32, ss[1] as f32);
            let z = 1.03 + 0.02 * (std::f32::consts::TAU * v / 400.0).sin();
            let (cw, chh) = (W / z, H / z);
            let mut o = 60.0 + cx + sslide;
            if ma.stage_scroll > 0.0 { o = (v * ma.stage_scroll + cx).rem_euclid(W); }
            let o = o.clamp(0.0, sw - cw);
            let oy = (35.0 + cy - (chh - H) / 2.0).clamp(0.0, sh - chh);
            let shx = sx_hit + kx;
            let uv = |x: f32, y: f32| [(o + (x - shx) * cw / W) / sw, (oy + y * chh / H) / sh];
            let corners = [[p0 + pdx - 2000.0, -40.0], [W + 400.0, -40.0], [W + 400.0, H + 40.0], [p0 + pdx - 2000.0, H + 40.0]];
            cv.clips.push(panel_clip);
            cv.poly(stage.id(), &corners.map(|p| Vx { p, uv: uv(p[0], p[1]), c: Color32::WHITE }));
            // the key light breathes; rays turn slowly about it
            let pulse = 0.88 + 0.12 * (std::f32::consts::TAU * v / 180.0).sin();
            if let Some(g) = &art.glow { cv.image(g, [0.0, 0.0, W, H], 0.0, [0.0, 0.0], light(pulse)); }
            let ra = k2(16.0, 0.0, 38.0, 1.0, Ease::Out, v) * pulse;
            let ang = (v * 0.12).to_radians(); let c0 = ma.rays_at;
            let (s_, c_) = (-ang).sin_cos();
            let ruv = |x: f32, y: f32| { let (dx, dy) = (x - c0[0], y - c0[1]); [(c0[0] + dx * c_ - dy * s_) / W, (c0[1] + dx * s_ + dy * c_) / H] };
            cv.poly(art.rays.id(), &[[0.0, 0.0], [W, 0.0], [W, H], [0.0, H]].map(|p| Vx { p, uv: ruv(p[0], p[1]), c: light(ra) }));
            // speed lines from the action
            if v >= 20.0 {
                let strong = if m == 1 { if v < 32.0 || hitstop { 1.0 } else { 0.21 } } else { 0.15 };
                let centre = if m == 1 { man.impact } else { [1400.0, 500.0] };
                let col = mix(ma.color, [255, 255, 255], 0.6);
                speed_lines(cv, centre, if hitstop { 999 } else { (v / 2.0) as u32 }, strong, col, 60);
            }
            cv.clips.pop();
            // the character
            let (i, ahead) = char_index(s, m);
            let (tex, at) = s.stream.get(ctx, m, i, &ahead)?;
            let sz = tex.size();
            let mut r = [at[0] + slide + vx_hit + 1.7 * cx, at[1] + 1.7 * cy, sz[0] as f32, sz[1] as f32];
            if conf == Some(1) && m == 1 {
                if let Some(h) = hit {
                    let cz = track(conf_c, &[(h - 6.0, 1.0, Ease::Out), (h, 0.98, Ease::InOut), (h + 4.0, 1.06, Ease::Out), (cut_at, 1.03, Ease::Out)]);
                    let ip = man.impact;
                    r = [ip[0] + (r[0] - ip[0]) * cz, ip[1] + (r[1] - ip[1]) * cz, r[2] * cz, r[3] * cz];
                }
            }
            Some((tex, r))
        };
        let mut character: Option<(TextureHandle, [f32; 4])> = None;
        let mut swap_chars: Vec<(TextureHandle, [f32; 4], Half)> = Vec::new();
        let brush_at = if swapping && ts < 20.0 { Some(track(ts, &[(0.0, 2800.0, Ease::Out), (18.0, 300.0, Ease::InOut)])) } else { None };
        if !impact_frame {
            if v < 0.0 || self.changed.is_none() {
                let slide = track(v, &[(0.0, 1500.0, Ease::Out), (9.0, 1500.0, Ease::Out), (23.0, 0.0, Ease::OutBack)]);
                character = content(self, cv, cur, slide, 0.0);
            } else if let Some(bx) = brush_at {
                let out_k = k2(0.0, 0.0, 16.0, 1.0, Ease::In, ts);
                let old_side = Half::left_of(bx - 520.0, lean); let new_side = Half::right_of(bx, lean);
                cv.clips.push(old_side);
                if let Some((t, r)) = content(self, cv, prev, -180.0 * out_k, -90.0 * out_k) { swap_chars.push((t, r, old_side)); }
                cv.clips.pop();
                cv.clips.push(new_side);
                let slide = track(ts, &[(4.0, 340.0, Ease::Out), (26.0, 0.0, Ease::OutBack)]);
                let sslide = track(ts, &[(2.0, 160.0, Ease::Out), (22.0, 0.0, Ease::Out)]);
                if let Some((t, r)) = content(self, cv, cur, slide, sslide) { swap_chars.push((t, r, new_side)); }
                cv.clips.pop();
                // the brush: ragged, with a dry tail
                cv.clips.push(panel_clip);
                ink_brush(cv, bx, self.changed.map_or(0, |t| (t * 10.0) as u32), lean);
                cv.clips.pop();
            } else {
                let slide = track(ts, &[(4.0, 340.0, Ease::Out), (26.0, 0.0, Ease::OutBack)]);
                let sslide = track(ts, &[(2.0, 160.0, Ease::Out), (22.0, 0.0, Ease::Out)]);
                character = content(self, cv, cur, slide, sslide);
            }
        }
        // the window's edge: ink, with the mode's colour inside it
        let edge_col = if swapping { mix(man.modes[prev].color, man.modes[cur].color, k2(0.0, 0.0, 18.0, 1.0, Ease::Out, ts)) } else { man.modes[cur].color };
        let e0 = p0 + pdx;
        cv.fill(&[([e0 - 12.0, -40.0], rgba(INK, 1.0)), ([e0 + 12.0, -40.0], rgba(INK, 1.0)), ([e0 + 12.0 - lean, H + 40.0], rgba(INK, 1.0)), ([e0 - 12.0 - lean, H + 40.0], rgba(INK, 1.0))]);
        cv.fill(&[([e0 + 10.0, -40.0], rgba(edge_col, 1.0)), ([e0 + 16.0, -40.0], rgba(edge_col, 1.0)), ([e0 + 16.0 - lean, H + 40.0], rgba(edge_col, 1.0)), ([e0 + 10.0 - lean, H + 40.0], rgba(edge_col, 1.0))]);
        if impact_frame {
            // the impact in KIU's own ink: black silhouettes and lines on bare paper
            let t = &self.art.modes[1].paper;
            cv.image(t, [0.0, 0.0, W, H], 0.0, [0.0, 0.0], Color32::WHITE);
            speed_lines(cv, man.impact, 1000 + conf_c as u32, 1.0, INK, 90);
            let (i, _) = char_index(self, 1);
            if let Some((tex, at)) = self.stream.get(ctx, 1, i, &[]) {
                let s = tex.size();
                cv.image(&tex, [at[0] + vx_hit + 1.7 * cx, at[1] + 1.7 * cy, s[0] as f32, s[1] as f32], 0.0, [0.0, 0.0], Color32::from_rgba_premultiplied(0, 0, 0, 255));
            }
        } else {
            for (t, r, side) in &swap_chars { cv.clips.push(*side); cv.image(t, *r, 0.0, [0.0, 0.0], Color32::WHITE); cv.clips.pop(); }
            if let Some((t, r)) = &character {
                // a crossfade into the confirm's first frames is not needed: the move starts from the idle pose
                cv.image(t, *r, 0.0, [0.0, 0.0], Color32::WHITE);
            }
            if v >= 14.0 { self.particles(cv, show, v / 60.0); }
            // the kick lands: flash, feathers, a white flash over everything
            if let Some(t) = after_hit.filter(|&t| t >= 2.0).map(|t| t - 2.0) {
                if t < 22.0 {
                    let sz = 400.0 + 1000.0 * ease(Ease::Out, clamp01(t / 6.0)); let fa = 1.0 - clamp01((t - 4.0) / 18.0);
                    let ip = man.impact;
                    cv.image(&self.art.flash.clone(), [ip[0] - sz / 2.0, ip[1] - sz / 2.0, sz, sz], 0.0, ip, additive([255, 220, 160], fa));
                }
                if t < 70.0 { self.feathers(cv, t); }
                if t < 8.0 { let a = 150.0 / 255.0 * (1.0 - t / 8.0); cv.fill(&[([0.0, 0.0], rgba([255, 244, 220], a)), ([W, 0.0], rgba([255, 244, 220], a)), ([W, H], rgba([255, 244, 220], a)), ([0.0, H], rgba([255, 244, 220], a))]); }
            }
        }
        // ink ornaments framing the window (they move the most), the ground band, the sprig
        let kick = if self.changed.is_some() { track(ts, &[(4.0, 60.0, Ease::Out), (24.0, 0.0, Ease::OutBack)]) } else { 0.0 };
        let sw_at = man.swirl.at;
        cv.image_at(&self.art.swirl.clone(), [sw_at[0] + pdx + 2.4 * cx + kick, sw_at[1] + 2.4 * cy], Color32::WHITE);
        let band_y = k2(6.0, 200.0, 20.0, 0.0, Ease::Out, v);
        cv.image_at(&self.art.band.clone(), [man.band.at[0], man.band.at[1] + band_y], Color32::WHITE);
        {
            let t = self.art.sprig.clone(); let s = t.size(); let b = man.sprig.base;
            let sway = 2.5 * (std::f32::consts::TAU * v / 200.0).sin();
            let y = b[1] + k2(8.0, 260.0, 22.0, 0.0, Ease::Out, v);
            let x = b[0] + 1.4 * cx;
            cv.image(&t, [x - s[0] as f32 / 2.0, y - s[1] as f32, s[0] as f32, s[1] as f32], sway, [x, y], Color32::WHITE);
        }
        // a soft vignette
        vignette(cv);
        // 5. the menu's words: heading, caption, controls
        let ok0 = self.out_k(0);
        let head = |cv: &mut Canvas, m: usize, a: f32, s: f32, yoff: f32, rot: f32, sq: [f32; 2]| {
            if a <= 0.01 { return; }
            let t = &self.art.modes[m].heading; let sz = t.size(); let b = man.modes[m].heading.base;
            let float = 4.0 * (std::f32::consts::TAU * v / 150.0).sin(); let r = rot + 0.6 * (std::f32::consts::TAU * v / 210.0).sin();
            let (w, h) = (sz[0] as f32 * s * sq[0], sz[1] as f32 * s * sq[1]);
            let y1 = b[1] + yoff + float;
            cv.image(t, [b[0] - w / 2.0, y1 - h, w, h], r, [b[0], y1 - h / 2.0], faded(a));
        };
        if self.changed.is_none() {
            head(cv, cur, k2(24.0, 0.0, 30.0, 1.0, Ease::Out, v) * (1.0 - ok0), track(v, &[(24.0, 0.6, Ease::Out), (38.0, 1.0, Ease::OutBack)]), -260.0 * ok0, 0.0, [1.0, 1.0]);
        } else {
            if ts < 9.0 { let k = k2(0.0, 0.0, 8.0, 1.0, Ease::In, ts); head(cv, prev, 1.0 - k, 1.0, 60.0 * k, -5.0 * k, [1.0, 1.0]); }
            if ts >= 8.0 {
                let drop = k2(8.0, -90.0, 17.0, 0.0, Ease::In, ts);
                let sq = track(ts, &[(17.0, 1.0, Ease::Out), (19.0, 0.86, Ease::Out), (30.0, 1.0, Ease::Spring)]);
                head(cv, cur, k2(8.0, 0.0, 11.0, 1.0, Ease::Out, ts) * (1.0 - ok0), 1.0, drop - 260.0 * ok0, 0.0, [2.0 - sq, sq]);
            }
        }
        let ok3 = self.out_k(3); let ok4 = self.out_k(4);
        let caption = |cv: &mut Canvas, m: usize, a: f32, dy: f32| {
            if a <= 0.01 { return; }
            let p = &man.modes[m].caption; cv.image_at(&self.art.modes[m].caption, [p.at[0], p.at[1] + dy], faded(a));
        };
        if self.changed.is_none() {
            caption(cv, cur, k2(40.0, 0.0, 56.0, 1.0, Ease::Out, v) * (1.0 - ok3), k2(40.0, 30.0, 56.0, 0.0, Ease::Out, v) + 160.0 * ok3);
        } else {
            if ts < 7.0 { caption(cv, prev, 1.0 - k2(0.0, 0.0, 6.0, 1.0, Ease::In, ts), 0.0); }
            if ts >= 11.0 { caption(cv, cur, k2(11.0, 0.0, 19.0, 1.0, Ease::Out, ts) * (1.0 - ok3), k2(11.0, 24.0, 23.0, 0.0, Ease::Out, ts) + 160.0 * ok3); }
        }
        cv.image_at(&self.art.controls.clone(), [man.controls.at[0], man.controls.at[1] + 160.0 * ok4], faded(k2(46.0, 0.0, 60.0, 1.0, Ease::Out, v) * (1.0 - ok4)));
        // the press: a gold ring from the button
        if let (Phase::Confirming { .. }, Some(p)) = (self.phase, self.pressed_at) {
            if conf_c < 18.0 { ring(cv, p, conf_c / 18.0); }
        }
        // 6. the cut: an ink line, then the halves part once the game shows its next screen
        let cut_start = match self.phase {
            Phase::Confirming { .. } => Some(conf_c - cut_at),
            Phase::Leaving { at } => Some(self.frames_since(at) - 14.0),
            Phase::Shown => None,
        }?;
        if cut_start < 0.0 { return None; }
        let ang = (-62.0f32).to_radians(); let (ux, uy) = (ang.cos(), ang.sin()); let n = [-uy, ux];
        let c0 = [W * 0.55, H * 0.5];
        // the line through c0 along (ux, uy): n . (p - c0) >= 0 is one side
        let h = Half { a: n[0], b: n[1], c: -(n[0] * c0[0] + n[1] * c0[1]) };
        let lt = k2(0.0, 0.0, 4.0, 1.0, Ease::Out, cut_start);
        // the halves wait for the game (at most 3 s)
        let ready = self.game_left.map(|t| self.frames_since(t)).unwrap_or(if cut_start > 180.0 { 1e6 } else { -1.0 });
        let part = if ready >= 2.0 { ready.min(cut_start) - 2.0 } else { -1.0 };
        let gap = if part < 0.0 { 0.0 } else { 2600.0 * ease(Ease::In, clamp01(part / 16.0)) };
        let la = if part < 0.0 { 1.0 } else { 1.0 - clamp01(part / 8.0) };
        if la > 0.0 {
            let lh = 2600.0 * lt; let wd = 16.0 * la + 3.0;
            let (a, b) = ([c0[0] - ux * lh, c0[1] - uy * lh], [c0[0] + ux * lh, c0[1] + uy * lh]);
            let col = rgba(INK, la);
            cv.fill(&[([a[0] + n[0] * wd / 2.0, a[1] + n[1] * wd / 2.0], col), ([b[0] + n[0] * wd / 2.0, b[1] + n[1] * wd / 2.0], col),
                      ([b[0] - n[0] * wd / 2.0, b[1] - n[1] * wd / 2.0], col), ([a[0] - n[0] * wd / 2.0, a[1] - n[1] * wd / 2.0], col)]);
        }
        Some((h, n, gap))
    }

    /// Particles drifting round the character, the mode's own (ui_v4.particles).
    fn particles(&self, cv: &mut Canvas, mode: usize, t: f32) {
        let mut rnd = Rng([4, 1, 2, 3][mode] * 7919);
        let (cx, band) = (1400.0, self.man.band_y);
        for k in 0..44 {
            let x0 = rnd.f(cx - 620.0, cx + 520.0); let sp = rnd.f(25.0, 70.0); let ph = rnd.f(0.0, 1.0);
            let sway = rnd.f(20.0, 60.0); let size = rnd.f(0.7, 1.4); let spin = rnd.f(-90.0, 90.0);
            let span = H + 200.0;
            let y = if mode == 3 { ((t * sp + ph * span) % span) - 100.0 } else { H + 100.0 - ((t * sp + ph * span) % span) };
            let x = x0 + (t * 0.9 + k as f32).sin() * sway;
            let fade = clamp01((band - y) / 120.0) * clamp01((y + 60.0) / 160.0);
            if fade <= 0.0 { continue; }
            let (tex, col, w, h, rot) = match mode {
                0 | 1 => (&self.art.feather, if k % 3 != 0 { [255, 255, 255] } else { [255, 200, 220] }, 44.0 * size, 22.0 * size, spin + t * 40.0),
                2 => { let tw = 0.5 + 0.5 * (t * 4.0 + k as f32 * 1.7).sin(); let s = 26.0 * size * (0.6 + 0.6 * tw); (&self.art.spark, [200, 255, 240], s, s, 0.0) }
                _ if k % 3 == 0 => (&self.art.powder, [255, 235, 248], 56.0 * size, 28.0 * size, 0.0),
                _ => (&self.art.leaves[k % self.art.leaves.len().max(1)], if k % 2 != 0 { [255, 228, 240] } else { [255, 160, 205] }, 48.0 * size, 48.0 * size, spin + t * 60.0),
            };
            cv.image(tex, [x - w / 2.0, y - h / 2.0, w, h], rot, [x, y], rgba(col, fade));
        }
    }

    /// Feathers bursting from the kick.
    fn feathers(&self, cv: &mut Canvas, t: f32) {
        let mut rnd = Rng(8 * 7919); let ip = self.man.impact;
        for n in 0..30 {
            let an = rnd.f(0.0, std::f32::consts::TAU); let sp = rnd.f(10.0, 26.0);
            let d = 100.0 + sp * 14.0 * ease(Ease::Out, clamp01(t / 14.0)) + sp * (t - 14.0).max(0.0) * 0.6;
            let col = if n % 3 != 0 { [255, 255, 255] } else { [120, 90, 170] };
            let p = [ip[0] + an.cos() * d, ip[1] + an.sin() * d + 0.12 * t * t];
            cv.image(&self.art.feather, [p[0] - 42.0, p[1] - 21.0, 84.0, 42.0], -an.to_degrees() + t * 6.0, p, rgba(col, 1.0 - clamp01((t - 40.0) / 30.0)));
        }
    }
}

/// Speed lines fanning out from `c` (thin wedges).
fn speed_lines(cv: &mut Canvas, c: [f32; 2], seed: u32, strength: f32, col: [u8; 3], n: usize) {
    let mut rnd = Rng(seed.wrapping_mul(2654435761));
    for _ in 0..n {
        let a = rnd.f(0.0, std::f32::consts::TAU); let r0 = rnd.f(300.0, 460.0); let r1 = r0 + rnd.f(500.0, 1400.0); let w = rnd.f(0.003, 0.010);
        let alpha = rnd.f(60.0, 150.0) / 255.0 * strength;
        let colr = rgba(col, alpha);
        cv.fill(&[([c[0] + a.cos() * r0, c[1] + a.sin() * r0], colr), ([c[0] + (a - w).cos() * r1, c[1] + (a - w).sin() * r1], colr),
                  ([c[0] + (a + w).cos() * r1, c[1] + (a + w).sin() * r1], colr)]);
    }
}

/// The ink brush: a ragged stroke 520 wide whose leading edge is at `bx`, with dry streaks behind it.
fn ink_brush(cv: &mut Canvas, bx: f32, seed: u32, lean: f32) {
    let mut rnd = Rng(seed.wrapping_mul(40503) ^ 0x5bd1e995);
    let rows = 22;
    let ink = rgba(INK, 1.0);
    let mut left = Vec::new(); let mut right = Vec::new();
    for k in 0..=rows {
        let y = -40.0 + k as f32 * (H + 80.0) / rows as f32; let l = lean * (y + 40.0) / (H + 80.0);
        right.push([bx - l + rnd.f(-22.0, 22.0), y]); left.push([bx - 520.0 - l + rnd.f(-60.0, 30.0), y]);
    }
    for k in 0..rows { cv.fill(&[(left[k], ink), (right[k], ink), (right[k + 1], ink), (left[k + 1], ink)]); }
    for _ in 0..26 {
        let y = rnd.f(-40.0, H + 40.0); let l = lean * (y + 40.0) / (H + 80.0); let x0 = bx - 520.0 - l;
        let (a, b) = ([x0 + rnd.f(-10.0, 40.0), y], [x0 + rnd.f(60.0, 260.0), y + rnd.f(-6.0, 6.0)]);
        let w = rnd.f(2.0, 9.0) / 2.0; let col = rgba(INK, rnd.f(0.55, 1.0));
        cv.fill(&[([a[0], a[1] - w], col), ([b[0], b[1] - w], col), ([b[0], b[1] + w], col), ([a[0], a[1] + w], col)]);
    }
}

/// A gold ring opening from the pressed button.
fn ring(cv: &mut Canvas, p: [f32; 2], t: f32) {
    let r = 60.0 + 340.0 * ease(Ease::Out, t); let w = 10.0 * (1.0 - t) + 2.0; let a = 1.0 - t;
    let col = rgba(GOLD, a);
    let n = 48;
    for i in 0..n {
        let (a0, a1) = (i as f32 / n as f32 * std::f32::consts::TAU, (i + 1) as f32 / n as f32 * std::f32::consts::TAU);
        let pt = |a: f32, rr: f32| [p[0] + a.cos() * rr, p[1] + a.sin() * rr * 0.55];
        cv.fill(&[(pt(a0, r - w / 2.0), col), (pt(a1, r - w / 2.0), col), (pt(a1, r + w / 2.0), col), (pt(a0, r + w / 2.0), col)]);
    }
}

/// Darker corners, very gently.
fn vignette(cv: &mut Canvas) {
    let (clear, dark) = (rgba(INK, 0.0), rgba(INK, 0.16));
    cv.fill(&[([0.0, 0.0], dark), ([W, 0.0], dark), ([W, 140.0], clear), ([0.0, 140.0], clear)]);
    cv.fill(&[([0.0, H - 140.0], clear), ([W, H - 140.0], clear), ([W, H], dark), ([0.0, H], dark)]);
    cv.fill(&[([0.0, 0.0], dark), ([220.0, 0.0], clear), ([220.0, H], clear), ([0.0, H], dark)]);
    cv.fill(&[([W - 220.0, 0.0], clear), ([W, 0.0], dark), ([W, H], dark), ([W - 220.0, H], clear)]);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn tracks_reach_their_keys() {
        let k = [(0.0, 10.0, Ease::Out), (10.0, 20.0, Ease::OutBack), (20.0, 0.0, Ease::In)];
        assert_eq!(track(-5.0, &k), 10.0);
        assert!((track(10.0, &k) - 20.0).abs() < 1e-4);
        assert!(track(8.0, &k) > 20.0, "overshoots on the way in");
        assert_eq!(track(30.0, &k), 0.0);
    }
    #[test]
    fn clipping_keeps_one_side() {
        let sq = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]].map(|p| Vx { p, uv: [p[0] / 10.0, p[1] / 10.0], c: Color32::WHITE });
        let half = clip(&sq, Half { a: 1.0, b: 0.0, c: -4.0 });     // x >= 4
        assert!(half.iter().all(|v| v.p[0] >= 4.0 - 1e-4));
        assert!(half.iter().any(|v| (v.uv[0] - 0.4).abs() < 1e-4), "texture coordinates follow the cut");
        assert!(clip(&sq, Half { a: 1.0, b: 0.0, c: -20.0 }).is_empty());
    }
    #[test]
    fn idle_loops_and_turns_back() {
        let c = Character { dir: String::new(), frames: vec![], intro: Some(Seq { range: [150, 195], play: None, impact: None }),
            idle: Seq { range: [195, 225], play: Some("pingpong".into()), impact: None }, confirm: Seq { range: [225, 259], play: None, impact: None } };
        assert_eq!(idle_index(&c, 0.0), 150);
        assert_eq!(idle_index(&c, 45.0), 195);
        assert_eq!(idle_index(&c, 45.0 + 30.0), 225, "the far end");
        assert_eq!(idle_index(&c, 45.0 + 60.0), 195, "and back");
        let l = Character { intro: None, idle: Seq { range: [0, 359], play: Some("loop".into()), impact: None }, ..c };
        assert_eq!(idle_index(&l, 360.0), 0);
        assert_eq!(idle_index(&l, 361.0), 1);
    }
    #[test]
    fn the_brush_leaves_the_window_edge_alone() {
        let r = Half::right_of(900.0, 330.0);
        assert!(r.at([901.0, -40.0]) > 0.0 && r.at([899.0, -40.0]) < 0.0);
        assert!(r.at([900.0 - 330.0 + 1.0, H + 40.0]) > 0.0, "the edge leans left toward the bottom");
    }
}

/// A preview without the game: the scene's real drawing, through egui's own
/// tessellator, filled into pictures by a small software rasterizer.
///   KIU_SCENE_PACK=<scene-040> KIU_SCENE_OUT=<folder> [KIU_SCENE_FRAMES=n] \
///     cargo test --release -p zakuro --lib menu_scene::preview -- --nocapture
/// The script: Solo shown, Together at 130, Vault at 230, Options at 320,
/// Together at 420, confirmed at 452, the game leaves at 500.
#[cfg(test)]
mod preview {
    use super::*;
    use egui::epaint::{ImageDelta, Primitive};

    struct Img { w: usize, h: usize, px: Vec<[f32; 4]> }
    fn apply(textures: &mut HashMap<egui::TextureId, Img>, id: egui::TextureId, d: &ImageDelta) {
        let egui::ImageData::Color(c) = &d.image;
        let conv = |p: &Color32| [p.r() as f32, p.g() as f32, p.b() as f32, p.a() as f32];
        match d.pos {
            None => { textures.insert(id, Img { w: c.size[0], h: c.size[1], px: c.pixels.iter().map(conv).collect() }); }
            Some([x0, y0]) => if let Some(t) = textures.get_mut(&id) {
                for y in 0..c.size[1] { for x in 0..c.size[0] { t.px[(y0 + y) * t.w + x0 + x] = conv(&c.pixels[y * c.size[0] + x]); } }
            },
        }
    }
    fn sample(t: &Img, u: f32, v: f32) -> [f32; 4] {
        let (x, y) = ((u * t.w as f32 - 0.5).clamp(0.0, t.w as f32 - 1.0), (v * t.h as f32 - 0.5).clamp(0.0, t.h as f32 - 1.0));
        let (x0, y0) = (x.floor() as usize, y.floor() as usize); let (x1, y1) = ((x0 + 1).min(t.w - 1), (y0 + 1).min(t.h - 1));
        let (fx, fy) = (x - x0 as f32, y - y0 as f32);
        let g = |xx: usize, yy: usize| t.px[yy * t.w + xx];
        let (a, b, c, d) = (g(x0, y0), g(x1, y0), g(x0, y1), g(x1, y1));
        [0, 1, 2, 3].map(|i| a[i] * (1.0 - fx) * (1.0 - fy) + b[i] * fx * (1.0 - fy) + c[i] * (1.0 - fx) * fy + d[i] * fx * fy)
    }
    fn raster(img: &mut [[f32; 3]], (w, h): (usize, usize), mesh: &Mesh, clip: Rect, ppp: f32, textures: &HashMap<egui::TextureId, Img>) {
        let tex = textures.get(&mesh.texture_id);
        for t in mesh.indices.chunks_exact(3) {
            let v = [mesh.vertices[t[0] as usize], mesh.vertices[t[1] as usize], mesh.vertices[t[2] as usize]];
            let p = v.map(|v| [v.pos.x * ppp, v.pos.y * ppp]);
            let area = (p[1][0] - p[0][0]) * (p[2][1] - p[0][1]) - (p[2][0] - p[0][0]) * (p[1][1] - p[0][1]);
            if area.abs() < 1e-6 { continue; }
            let minx = (p.iter().map(|q| q[0]).fold(f32::MAX, f32::min).max(clip.min.x * ppp).max(0.0)) as usize;
            let maxx = (p.iter().map(|q| q[0]).fold(f32::MIN, f32::max).min(clip.max.x * ppp).min(w as f32 - 1.0)).max(-1.0) as isize;
            let miny = (p.iter().map(|q| q[1]).fold(f32::MAX, f32::min).max(clip.min.y * ppp).max(0.0)) as usize;
            let maxy = (p.iter().map(|q| q[1]).fold(f32::MIN, f32::max).min(clip.max.y * ppp).min(h as f32 - 1.0)).max(-1.0) as isize;
            for y in miny as isize..=maxy { for x in minx as isize..=maxx {
                let (fx, fy) = (x as f32 + 0.5, y as f32 + 0.5);
                let w0 = ((p[1][0] - fx) * (p[2][1] - fy) - (p[2][0] - fx) * (p[1][1] - fy)) / area;
                let w1 = ((p[2][0] - fx) * (p[0][1] - fy) - (p[0][0] - fx) * (p[2][1] - fy)) / area;
                let w2 = 1.0 - w0 - w1;
                if w0 < -1e-4 || w1 < -1e-4 || w2 < -1e-4 { continue; }
                let col = |i: usize| [v[i].color.r() as f32, v[i].color.g() as f32, v[i].color.b() as f32, v[i].color.a() as f32];
                let (c0, c1, c2) = (col(0), col(1), col(2));
                let vc = [0, 1, 2, 3].map(|k| (c0[k] * w0 + c1[k] * w1 + c2[k] * w2) / 255.0);
                let (u, vv) = (v[0].uv.x * w0 + v[1].uv.x * w1 + v[2].uv.x * w2, v[0].uv.y * w0 + v[1].uv.y * w1 + v[2].uv.y * w2);
                let s = tex.map_or([255.0; 4], |t| sample(t, u, vv));
                let src = [0, 1, 2, 3].map(|k| s[k] * vc[k]);
                let d = &mut img[y as usize * w + x as usize];
                let a = src[3] / 255.0;
                for k in 0..3 { d[k] = (src[k] + d[k] * (1.0 - a)).min(255.0); }
            } }
        }
    }

    #[test]
    fn render() {
        let (Some(pack), Some(out)) = (std::env::var_os("KIU_SCENE_PACK"), std::env::var_os("KIU_SCENE_OUT")) else { return };
        let out = PathBuf::from(out); std::fs::create_dir_all(&out).unwrap();
        let n: usize = std::env::var("KIU_SCENE_FRAMES").ok().and_then(|s| s.parse().ok()).unwrap_or(600);
        let only: Option<Vec<usize>> = std::env::var("KIU_SCENE_ONLY").ok().map(|s| s.split(',').filter_map(|x| x.parse().ok()).collect());
        let ctx = egui::Context::default();
        let (w, h, ppp) = (960usize, 540usize, 0.5f32);
        let screen = Rect::from_min_size(Pos2::ZERO, egui::vec2(W, H));
        let mut textures: HashMap<egui::TextureId, Img> = HashMap::new();
        let mut scene: Option<Scene> = None;
        for f in 0..n {
            let t = f as f64 / 60.0;
            let input = egui::RawInput { time: Some(t), screen_rect: Some(screen), ..Default::default() };
            let output = ctx.run_ui(input, |ui| {
                let ctx = ui.ctx().clone();
                if scene.is_none() { scene = Scene::load(&ctx, std::path::Path::new(&pack)); }
                let s = scene.as_mut().unwrap();
                let sel = [(0usize, 0usize), (130, 1), (230, 2), (320, 3), (420, 1)].iter().rev().find(|(at, _)| f >= *at).map(|x| x.1);
                // wait for the frames the character needs (the game would show the previous one)
                for _ in 0..200 { s.stream.receive(); if !s.stream.pending() { break; } std::thread::sleep(std::time::Duration::from_millis(5)); }
                if f < 452 { s.select(sel); }
                if f == 452 { s.confirm(1, Some(Pos2::new(281.0, 520.0)), screen); }
                if f >= 500 { s.game_left(); }
                s.show(&ctx, screen);
                // the buttons' entry, for the record
                let _ = s.button_presence(0);
            });
            for (id, ds) in &output.textures_delta.set { for d in ds.iter() { apply(&mut textures, *id, d); } }
            if only.as_ref().is_some_and(|o| !o.contains(&f)) { continue; }
            let prims = ctx.tessellate(output.shapes, 1.0);
            let mut img = vec![[0.0f32; 3]; w * h];
            for p in &prims { if let Primitive::Mesh(m) = &p.primitive { raster(&mut img, (w, h), m, p.clip_rect, ppp, &textures); } }
            let bytes: Vec<u8> = img.iter().flat_map(|c| c.map(|x| x as u8)).collect();
            image::RgbImage::from_raw(w as u32, h as u32, bytes).unwrap().save(out.join(format!("{f:04}.png"))).unwrap();
        }
    }
}
