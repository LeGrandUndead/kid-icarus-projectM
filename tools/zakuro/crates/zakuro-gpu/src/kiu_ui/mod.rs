//! KIU PC presentation layer: the original bottom-screen UI, recomposed.
//!
//! The game keeps rendering both screens. Draws on the bottom screen that
//! sample a catalogued original ROM texture (identified by the fingerprint of
//! its encoded bytes) are copied, with their real transforms, UVs and texture
//! combiner, and redrawn by the host overlay in PC positions:
//!
//! - portraits (`FB_*`) beside the gameplay view;
//! - HUD elements (special gauges, Power Palette, counters) as islands that
//!   keep the game's own relative layout and animation;
//! - menu atlases only as evidence of which original panel is up.
//!
//! No framebuffer readback, crop, OCR, color guess, invented timer or redrawn
//! art. Unknown or unmatched draws simply stay in the original bottom screen,
//! which remains reachable with Tab.
mod bake;
pub mod camera;
pub mod config;
pub mod layout;
pub mod scene;

use std::collections::{HashMap, HashSet};
use std::sync::{Mutex, OnceLock};

use crate::{Overlay, OverlayMesh, OverlayTexture, OverlayVertex};
pub use scene::BottomScene;

/// What a catalogued original texture is for.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    /// Dialogue portrait art.
    Portrait,
    /// Atlas holding gameplay HUD elements.
    Hud,
    /// Atlas of the original pause/menu panels.
    Menu,
    /// Picture the dialogue refers to: gag art, cutaway comics, retro
    /// screenshots, boss and rival title cards (`CI_*`, `SP_*`, `BL_/BR_*`).
    Insert,
    /// Known but decorative bottom-screen art (backgrounds, chapter titles).
    Decor,
    /// Not in the catalog, typically system-font text (power names). Only
    /// relocated when it lies inside a HUD island, as part of that layout.
    Unlisted,
}

impl Role {
    fn parse(text: &str) -> Option<Role> {
        Some(match text {
            "portrait" => Role::Portrait,
            "hud" => Role::Hud,
            "menu" => Role::Menu,
            "decor" => Role::Decor,
            "insert" => Role::Insert,
            _ => return None,
        })
    }
}

struct Source { role: Role, name: String }

/// One relocated original draw.
struct Layer {
    role: Role,
    name: usize,
    texture: u64,
    xy: [[f32; 2]; 4],
    uv: [[f32; 2]; 4],
    /// vertex alpha for fades the combiner applies linearly.
    alpha: f32,
    island: Option<layout::Island>,
}

const MAX_LAYERS: usize = 256;
const CACHE_LIMIT: usize = 128;
/// Frames the last complete bottom screen is kept while the game does not
/// redraw it (some scenes update the lower screen at a lower rate).
const STALE_FRAMES: u32 = 6;

#[derive(Default)]
struct State {
    catalog: HashMap<u64, Source>,
    names: Vec<String>,
    /// baked texture per (texture, combiner state): host id, and whether it
    /// is already the HD version.
    cache: HashMap<Vec<u32>, (u64, bool)>,
    next: u64,
    pending: Vec<Layer>,
    shown: Vec<Layer>,
    bottom_draws: u32,
    stale: u32,
    frame: u64,
    scene: BottomScene,
    touch: Option<[f32; 2]>,
    uploads: Vec<OverlayTexture>,
    free: Vec<u64>,
    census: Option<census::Census>,
    /// HD versions of catalogued textures from the local pack
    /// (KIU_HUD_PACK, tools/recomp/build_hud_hd_pack.py), by catalog hash.
    hd: HashMap<u64, HdState>,
    /// HD loads and bakes run off the emulation thread (no audio hitch);
    /// until one is ready the original-resolution texture is shown.
    jobs: Option<std::sync::mpsc::Sender<Done>>,
    done: Option<std::sync::mpsc::Receiver<Done>>,
    baking: HashSet<Vec<u32>>,
    /// Portraits and pictures by texture name: first and last frame seen in
    /// an unbroken run, and the fade it has now (see `PICTURE_LIMIT`).
    runs: HashMap<usize, (u64, u64, u64)>,
    fades: HashMap<usize, f32>,
}

/// On the 3DS some lower-screen art stays up for minutes: a boss's portrait
/// for the whole fight (user report, October 16). On one screen that would
/// cover the action, so a portrait or picture that has not changed for this
/// many frames fades out; a new expression or picture shows again. Dialogue
/// changes expression often, so portraits get longer than pictures.
const PICTURE_LIMIT: u64 = 720;   // 12 s
const PORTRAIT_LIMIT: u64 = 1200; // 20 s
const PICTURE_FADE: u64 = 30;

enum HdState { Loading, Ready(std::sync::Arc<Hd>), Missing }

enum Done {
    Loaded(u64, Option<std::sync::Arc<Hd>>),
    Baked(Vec<u32>, [u32; 2], Vec<u8>),
}

/// Base level of an enlarged original (same UV layout, more texels).
struct Hd { width: u32, height: u32, texels: Vec<[u8; 4]> }

/// Parses `ui-sources.tsv` (`hash<TAB>role<TAB>name…`) or the October 14
/// `portrait-hashes.txt` (one hash per line, all portraits).
fn parse_catalog(text: &str) -> (HashMap<u64, Source>, Vec<String>) {
    let mut catalog = HashMap::new();
    let mut names: Vec<String> = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') { continue; }
        let mut fields = line.split('\t');
        let Some(hash) = fields.next().and_then(|h| u64::from_str_radix(h.trim(), 16).ok()) else { continue };
        let (role, name) = match fields.next() {
            Some(role) => match Role::parse(role.trim()) {
                Some(role) => (role, fields.next().unwrap_or("").trim().to_owned()),
                None => continue,
            },
            None => (Role::Portrait, String::new()),
        };
        catalog.insert(hash, Source { role, name });
    }
    for source in catalog.values() { if !names.contains(&source.name) { names.push(source.name.clone()); } }
    (catalog, names)
}

fn state() -> Option<&'static Mutex<State>> {
    static STATE: OnceLock<Option<Mutex<State>>> = OnceLock::new();
    STATE.get_or_init(|| {
        let file = std::env::var_os("KIU_NATIVE_UI").or_else(|| std::env::var_os("KIU_NATIVE_DIALOGUE"))?;
        let text = std::fs::read_to_string(&file).ok()?;
        let (catalog, names) = parse_catalog(&text);
        if catalog.is_empty() { return None; }
        let count = |role| catalog.values().filter(|s| s.role == role).count();
        log::info!("Original PC interface layers: {} portrait, {} insert, {} HUD, {} menu, {} decor textures",
            count(Role::Portrait), count(Role::Insert), count(Role::Hud), count(Role::Menu), count(Role::Decor));
        let (jobs, done) = std::sync::mpsc::channel();
        crate::replacements::hud_pack_enabled(); // starts decoding the HD HUD atlases
        Some(Mutex::new(State { catalog, names, next: 1u64 << 61, census: census::Census::from_environment(),
            jobs: Some(jobs), done: Some(done), ..State::default() }))
    }).as_ref()
}

pub fn enabled() -> bool { state().is_some() }

/// Start of an emulated frame.
pub fn begin_frame() {
    let Some(state) = state() else { return };
    let Ok(mut s) = state.lock() else { return };
    s.pending.clear();
    s.bottom_draws = 0;
    s.frame += 1;
}

/// End of an emulated frame: a redrawn bottom screen replaces the shown one.
pub fn end_frame() -> BottomScene {
    let Some(state) = state() else { return BottomScene::default() };
    let Ok(mut s) = state.lock() else { return BottomScene::default() };
    let s = &mut *s;
    apply_hd_jobs(s);
    let fresh = s.bottom_draws > 0;
    if fresh {
        s.shown = std::mem::take(&mut s.pending);
        s.stale = 0;
    } else {
        s.pending.clear();
        s.stale += 1;
        if s.stale > STALE_FRAMES { s.shown.clear(); }
    }
    let frame = s.frame;
    for layer in &s.shown {
        if matches!(layer.role, Role::Portrait | Role::Insert) {
            let limit = if layer.role == Role::Portrait { PORTRAIT_LIMIT } else { PICTURE_LIMIT };
            let run = s.runs.entry(layer.name).or_insert((frame, frame, limit));
            run.1 = frame;
        }
    }
    s.runs.retain(|_, run| frame - run.1 <= 60);
    s.fades = s.runs.iter().map(|(&name, &(first, _, limit))| {
        let over = (frame - first).saturating_sub(limit);
        (name, 1.0 - (over as f32 / PICTURE_FADE as f32).min(1.0))
    }).collect();
    let names = &s.names;
    s.scene = scene::classify(s.frame, fresh, s.shown.iter().map(|l| scene::Evidence {
        role: l.role, atlas: &names[l.name], uv: l.uv, island: l.island.is_some(),
    }));
    if let Some(census) = &mut s.census { census.record(s.frame, fresh, &s.shown, names); }
    evict(s);
    s.scene
}

/// The last classified bottom screen.
pub fn scene() -> BottomScene {
    state().and_then(|s| s.lock().ok().map(|s| s.scene)).unwrap_or_default()
}

/// The touch point the game was given this frame, guest bottom-screen pixels.
pub fn set_touch(touch: Option<(u16, u16)>) {
    if let Some(Ok(mut s)) = state().map(Mutex::lock) { s.touch = touch.map(|(x, y)| [x as f32, y as f32]); }
}

/// Bounded host texture cache; textures still shown are never freed.
fn evict(s: &mut State) {
    if s.cache.len() < CACHE_LIMIT { return; }
    let live: HashSet<u64> = s.shown.iter().chain(&s.pending).map(|l| l.texture).collect();
    let mut freed = Vec::new();
    s.cache.retain(|_, (id, _)| if live.contains(id) { true } else { freed.push(*id); false });
    s.free.extend(freed);
}

/// Whether a census is being written (diagnostic paths may then do extra work).
pub(crate) fn census_enabled() -> bool {
    state().is_some_and(|s| s.lock().is_ok_and(|s| s.census.is_some()))
}

/// Census only: a lower-screen draw the capture did not take, and why. Each
/// distinct reason/texture/pipeline combination is written once.
pub(crate) fn note_rejected(reason: &'static str, detail: String) {
    if let Some(Ok(mut s)) = state().map(Mutex::lock) {
        let frame = s.frame;
        if let Some(census) = &mut s.census { census.rejected(frame, reason, detail); }
    }
}

/// A 2D draw reached the guest bottom screen (any texture).
pub(crate) fn note_bottom_draw() {
    if let Some(Ok(mut s)) = state().map(Mutex::lock) { s.bottom_draws += 1; }
}

/// The role of a lower-screen texture: catalogued, or `Unlisted` for any
/// other ordinary texture.
pub(crate) fn role(hash: Option<u64>) -> Option<Role> {
    let hash = hash?;
    Some(state()?.lock().ok()?.catalog.get(&hash).map_or(Role::Unlisted, |s| s.role))
}

/// Keeps one original draw. `xy` is in guest bottom-screen pixels.
#[allow(clippy::too_many_arguments)]
pub(crate) fn push(hash: u64, width: u32, height: u32, texels: &[[u8; 4]],
    registers: &[u32], primary: [f32; 4], xy: [[f32; 2]; 4], uv: [[f32; 2]; 4]) {
    let Some(state) = state() else { return };
    let Ok(mut guard) = state.lock() else { return };
    let s = &mut *guard;
    let (role, label) = match s.catalog.get(&hash) {
        Some(source) => (source.role, source.name.as_str()),
        None => (Role::Unlisted, "unlisted"),
    };
    let name = match s.names.iter().position(|n| n == label) {
        Some(index) => index,
        None => { s.names.push(label.to_owned()); s.names.len() - 1 }
    };
    if s.pending.len() >= MAX_LAYERS || texels.len() < (width * height) as usize { return; }
    // Text and other unlisted art goes with the layer it is written on: the
    // most recent picture panel or HUD piece under it (the Practice Range
    // weapon card's text with the card, a power name with its HUD bubble).
    let role = if role == Role::Unlisted {
        let c = layout::center(layout::bounds(&xy));
        let under = s.pending.iter().rev().find(|l| (l.role == Role::Insert || l.island.is_some()) && {
            let b = layout::bounds(&l.xy);
            c[0] >= b[0] && c[0] <= b[2] && c[1] >= b[1] && c[1] <= b[3]
        });
        match under { Some(l) if l.role == Role::Insert => Role::Insert, _ => role }
    } else { role };
    // Decide placement first: unplaced HUD/menu/decor draws need no texture.
    let hud_like = matches!(role, Role::Hud | Role::Unlisted);
    let island = if hud_like && !layout::is_touch_marker(&xy, s.touch) { layout::island_for(&xy) } else { None };
    // Text and other unlisted art elsewhere (menus, panels) is not kept, nor
    // procedural effects whose UVs leave the texture (the stylus ripple rings,
    // UV 0..2 x -1..1 in the October 15 census) — they are not HUD elements.
    let tiled = uv.iter().flatten().any(|v| !(-0.01..=1.01).contains(v));
    if role == Role::Unlisted && (island.is_none() || tiled) { return; }
    let needs_texture = matches!(role, Role::Portrait | Role::Insert) || island.is_some();
    let texture = if needs_texture {
        let texels = &texels[..(width * height) as usize];
        let hd = hd_for(s, hash, texels, width, height);
        let env = crate::tev::TexEnv::read(registers);
        let fade = bake::alpha_is_a_fade(&env, primary, texels);
        let baked_primary = if fade { [primary[0], primary[1], primary[2], 1.0] } else { primary };
        let mut key = vec![hash as u32, (hash >> 32) as u32, width, height];
        key.extend(baked_primary.map(f32::to_bits));
        for base in [0xc0, 0xc8, 0xd0, 0xd8, 0xf0, 0xf8] { key.extend_from_slice(&registers[base..base + 5]); }
        key.extend([registers[0xe0], registers[0xfd]]);
        let (id, is_hd) = match s.cache.get(&key) {
            Some(&entry) => entry,
            None => {
                let id = s.next;
                s.next += 1;
                s.uploads.push(OverlayTexture { id, offset: None, size: [width, height], pixels: bake::bake(&env, baked_primary, texels), linear: true });
                s.cache.insert(key.clone(), (id, false));
                (id, false)
            }
        };
        if let (false, Some(hd), Some(jobs)) = (is_hd, hd, &s.jobs) {
            if s.baking.insert(key.clone()) {
                let jobs = jobs.clone();
                std::thread::spawn(move || {
                    let pixels = bake::bake(&env, baked_primary, &hd.texels);
                    let _ = jobs.send(Done::Baked(key, [hd.width, hd.height], pixels));
                });
            }
        }
        if let Some(root) = crate::diagnostics::draw_capture_path() {
            capture_for_diagnostics(root, s.pending.len(), hash, &env, primary, texels, width, height, xy, uv);
        }
        Some((id, if fade { primary[3].clamp(0.0, 1.0) } else { 1.0 }))
    } else { None };
    let (texture, alpha) = texture.unwrap_or((0, 1.0));
    s.pending.push(Layer { role, name, texture, xy, uv, alpha, island });
}

/// The HD version of a catalogued texture, if the local pack has one and it
/// has finished loading. The first request starts the load in the background.
fn hd_for(s: &mut State, hash: u64, texels: &[[u8; 4]], width: u32, height: u32) -> Option<std::sync::Arc<Hd>> {
    match s.hd.get(&hash) {
        Some(HdState::Ready(hd)) => return Some(hd.clone()),
        Some(_) => return None,
        None => {}
    }
    let Some(jobs) = s.jobs.clone() else { return None };
    if !crate::replacements::hud_pack_enabled() {
        s.hd.insert(hash, HdState::Missing);
        return None;
    }
    s.hd.insert(hash, HdState::Loading);
    let texels = texels.to_vec();
    std::thread::spawn(move || {
        let hd = crate::replacements::load_hud(crate::raster::fingerprint(texels.as_flattened()), width, height, 1).map(|r| {
            let base = (r.width * r.height) as usize;
            std::sync::Arc::new(Hd { width: r.width, height: r.height, texels: r.texels[..base].to_vec() })
        });
        let _ = jobs.send(Done::Loaded(hash, hd));
    });
    None
}

/// Takes finished background loads and bakes. A finished bake replaces the
/// original-resolution texture in the cache and in the layers shown now.
fn apply_hd_jobs(s: &mut State) {
    let Some(done) = &s.done else { return };
    let finished: Vec<Done> = done.try_iter().collect();
    for job in finished {
        match job {
            Done::Loaded(hash, hd) => {
                s.hd.insert(hash, hd.map_or(HdState::Missing, HdState::Ready));
            }
            Done::Baked(key, size, pixels) => {
                s.baking.remove(&key);
                let Some(&(old, false)) = s.cache.get(&key) else { continue };
                let id = s.next;
                s.next += 1;
                s.uploads.push(OverlayTexture { id, offset: None, size, pixels, linear: true });
                s.cache.insert(key, (id, true));
                for layer in s.shown.iter_mut().chain(s.pending.iter_mut()) {
                    if layer.texture == old { layer.texture = id; }
                }
                s.free.push(old);
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn capture_for_diagnostics(root: &std::path::Path, index: usize, hash: u64, env: &crate::tev::TexEnv,
    primary: [f32; 4], texels: &[[u8; 4]], width: u32, height: u32, xy: [[f32; 2]; 4], uv: [[f32; 2]; 4]) {
    let _ = std::fs::create_dir_all(root);
    let mut rgba = Vec::with_capacity(texels.len() * 4);
    for pixel in texels {
        let mut textures = [[0.0; 4]; 4];
        textures[0] = pixel.map(|v| v as f32 / 255.0);
        rgba.extend(env.apply(primary, textures, None).map(|v| (v.clamp(0., 1.) * 255.).round() as u8));
    }
    let name = format!("ui-{index}-{hash:016X}");
    let _ = image::save_buffer(root.join(format!("{name}.png")), &rgba, width, height, image::ColorType::Rgba8);
    let _ = std::fs::write(root.join(format!("{name}.json")), format!("{{\"xy\":{xy:?},\"uv\":{uv:?},\"primary\":{primary:?}}}"));
}

/// PICA's V origin is opposite the top-down decoded texture rows, just as
/// raster.frag converts V before sampling. Host overlay shaders do not.
fn overlay_uv(uv: [f32; 2]) -> [f32; 2] { [uv[0], 1.0 - uv[1]] }

/// Lower-screen text the game draws into a buffer first (power names),
/// copied back from the GPU when it changes. Kept at twice the original
/// resolution: sharper than the 3DS, small enough to bake quickly.
pub(crate) struct Text {
    pub hash: u64,
    pub size: [u32; 2],
    pub texels: std::sync::Arc<Vec<[u8; 4]>>,
}

fn texts() -> &'static Mutex<HashMap<(u32, [u32; 2]), std::sync::Arc<Text>>> {
    static TEXTS: OnceLock<Mutex<HashMap<(u32, [u32; 2]), std::sync::Arc<Text>>>> = OnceLock::new();
    TEXTS.get_or_init(Default::default)
}

/// A finished copy of a text buffer: `native` is its 3DS size, `scaled`
/// the size of `rgba` (rows top first, as decoded textures have them).
pub(crate) fn set_text(addr: u32, native: [u32; 2], scaled: [u32; 2], rgba: &[u8]) {
    if !enabled() || native[0] == 0 || native[1] == 0 { return; }
    let target = [native[0] * 2, native[1] * 2];
    let (fx, fy) = (scaled[0] as f32 / target[0] as f32, scaled[1] as f32 / target[1] as f32);
    let mut texels = Vec::with_capacity((target[0] * target[1]) as usize);
    for y in 0..target[1] {
        let (y0, y1) = ((y as f32 * fy) as u32, (((y + 1) as f32 * fy).ceil() as u32).min(scaled[1]).max(1));
        for x in 0..target[0] {
            let (x0, x1) = ((x as f32 * fx) as u32, (((x + 1) as f32 * fx).ceil() as u32).min(scaled[0]).max(1));
            let mut sum = [0u32; 4];
            let mut count = 0;
            for sy in y0..y1.max(y0 + 1) {
                for sx in x0..x1.max(x0 + 1) {
                    let at = ((sy.min(scaled[1] - 1) * scaled[0] + sx.min(scaled[0] - 1)) * 4) as usize;
                    for c in 0..4 { sum[c] += rgba[at + c] as u32; }
                    count += 1;
                }
            }
            texels.push(sum.map(|v| (v / count.max(1)) as u8));
        }
    }
    let hash = crate::raster::fingerprint(texels.as_flattened()) | 1 << 63;
    if let Ok(mut map) = texts().lock() {
        map.insert((addr, native), std::sync::Arc::new(Text { hash, size: target, texels: std::sync::Arc::new(texels) }));
    }
}

pub(crate) fn text(addr: u32, native: [u32; 2]) -> Option<std::sync::Arc<Text>> {
    texts().lock().ok()?.get(&(addr, native)).cloned()
}

/// The relocated layers for this window, placed in the window rectangle.
pub fn overlay(width: u32, height: u32, visible: bool) -> Overlay {
    overlay_in(width, height, [0.0, 0.0, width as f32, height as f32], visible)
}

/// The relocated layers placed relative to the game's main view `[x, y, w, h]`
/// inside the window, so they sit on the picture and not in side bars.
/// `visible` is the presentation's decision (gameplay view, no panel or menu
/// over it). Texture uploads and frees are always handed over, so the host
/// cache stays consistent. Insert before runtime menus so they keep visual
/// and input precedence.
pub fn overlay_in(width: u32, height: u32, view: [f32; 4], visible: bool) -> Overlay {
    let Some(state) = state() else { return Overlay::default() };
    let Ok(mut s) = state.lock() else { return Overlay::default() };
    let mut overlay = Overlay { textures: std::mem::take(&mut s.uploads), free: std::mem::take(&mut s.free), ..Overlay::default() };
    let [vx, vy, w, h] = view;
    if !visible || width == 0 || height == 0 || !(w >= 1.0 && h >= 1.0) { return overlay; }
    let interface = config::get();
    for layer in &s.shown {
        let place: Box<dyn Fn([f32; 2]) -> [f32; 2]> = match (layer.role, layer.island) {
            (Role::Portrait, _) if interface.portraits => {
                let center = layer.xy.iter().map(|v| v[0]).sum::<f32>() / 4.0;
                let right = center >= 160.0;
                Box::new(move |p| layout::place_portrait(p, right, w, h))
            }
            (Role::Insert, _) if interface.inserts => Box::new(move |p| layout::place_insert(p, w, h)),
            (Role::Hud | Role::Unlisted, Some(island)) if interface.hud => {
                let scale = interface.hud_scale;
                let above = island == layout::ACTION && layout::above_action_row(layout::center(layout::bounds(&layer.xy))[1]);
                Box::new(move |p| layout::place_island_element(p, island, w, h, scale, above))
            }
            _ => continue,
        };
        let fade = s.fades.get(&layer.name).copied().unwrap_or(1.0);
        if fade <= 0.0 { continue; }
        let a = (layer.alpha * fade * 255.0).round() as u8;
        let vertices = (0..4).map(|i| {
            let [x, y] = place(layer.xy[i]);
            OverlayVertex { position: [vx + x, vy + y], uv: overlay_uv(layer.uv[i]), color: [a; 4] }
        }).collect();
        overlay.meshes.push(OverlayMesh { texture: layer.texture, clip: [0, 0, width, height], vertices, indices: vec![0, 1, 2, 1, 3, 2] });
    }
    overlay
}

/// Optional diagnostic census, `KIU_UI_CENSUS=file.csv`: one row per
/// catalogued bottom-screen draw whenever the set of draws changes. It is how
/// the remaining unknown roles (items, vehicle actions, gag art) are traced.
mod census {
    use std::io::Write;
    pub struct Census {
        file: std::fs::File,
        last: Vec<String>,
        rejected: Option<std::fs::File>,
        seen: std::collections::HashSet<String>,
    }
    impl Census {
        pub fn from_environment() -> Option<Census> {
            let path = std::path::PathBuf::from(std::env::var_os("KIU_UI_CENSUS")?);
            let mut file = std::fs::File::create(&path).ok()?;
            let _ = writeln!(file, "frame,fresh,role,atlas,x0,y0,x1,y1,u0,v0,u1,v1,alpha,island");
            let mut rejected = std::fs::File::create(path.with_file_name("lower-screen-rejected.csv")).ok();
            if let Some(f) = &mut rejected { let _ = writeln!(f, "first_frame,reason,detail"); }
            Some(Census { file, last: Vec::new(), rejected, seen: Default::default() })
        }
        pub(super) fn rejected(&mut self, frame: u64, reason: &str, detail: String) {
            let key = format!("{reason},{detail}");
            if self.seen.len() < 4096 && self.seen.insert(key.clone()) {
                if let Some(f) = &mut self.rejected { let _ = writeln!(f, "{frame},{key}"); }
            }
        }
        pub(super) fn record(&mut self, frame: u64, fresh: bool, layers: &[super::Layer], names: &[String]) {
            let rows: Vec<String> = layers.iter().map(|l| {
                let b = super::layout::bounds(&l.xy);
                let mut u = [f32::INFINITY, f32::INFINITY, f32::NEG_INFINITY, f32::NEG_INFINITY];
                for p in l.uv { u[0] = u[0].min(p[0]); u[1] = u[1].min(p[1]); u[2] = u[2].max(p[0]); u[3] = u[3].max(p[1]); }
                format!("{:?},{},{:.0},{:.0},{:.0},{:.0},{:.4},{:.4},{:.4},{:.4},{:.2},{}", l.role, names[l.name],
                    b[0], b[1], b[2], b[3], u[0], u[1], u[2], u[3], l.alpha, l.island.map_or("-", |i| i.name))
            }).collect();
            // geometry only; ignore pure alpha animation for the change test
            let key: Vec<String> = rows.iter().map(|r| r.rsplitn(3, ',').nth(2).unwrap_or(r).to_owned()).collect();
            if key == self.last { return; }
            self.last = key;
            for row in rows { let _ = writeln!(self.file, "{frame},{},{row}", fresh as u8); }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn catalog_accepts_roles_and_the_october_portrait_list() {
        let (c, names) = parse_catalog("# comment\n00000000000000AB\nCD\thud\tgc_00\nEF\tmenu\tgm_01\n12\tunknown\tx\n");
        assert_eq!(c[&0xAB].role, Role::Portrait);
        assert_eq!(c[&0xCD].role, Role::Hud);
        assert_eq!(c[&0xEF].name, "gm_01");
        assert!(!c.contains_key(&0x12));
        assert!(names.contains(&"gc_00".to_owned()));
    }
    #[test]
    fn original_portrait_uv_uses_top_down_host_texture_rows() {
        assert_eq!(overlay_uv([0., 1.]), [0., 0.]);
        assert_eq!(overlay_uv([1., 0.]), [1., 1.]);
    }
}
