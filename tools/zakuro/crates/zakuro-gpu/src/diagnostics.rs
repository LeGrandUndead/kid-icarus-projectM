//! Opt-in, bounded captures for investigating rendering errors.
//! Raw registers and encoded texture bytes stay local to the user's project.
use std::{collections::HashSet, fs::{self, File}, hash::{Hash, Hasher}, io::Write,
          path::PathBuf, sync::{Mutex, OnceLock}};
use crate::texture::TextureFormat;
use std::sync::atomic::{AtomicU64, Ordering};

static FRAME: AtomicU64 = AtomicU64::new(0);
pub fn diagnostic_frame(frame: u64) { FRAME.store(frame, Ordering::Relaxed); }
/// the first of the two frames F8 asked to be captured draw by draw.
static F8_FRAME: AtomicU64 = AtomicU64::new(u64::MAX);
pub(crate) fn draw_capture_path() -> Option<&'static PathBuf> {
    static REQUEST: OnceLock<Option<(u64, PathBuf)>> = OnceLock::new();
    let frame = FRAME.load(Ordering::Relaxed);
    if let Some((target, path)) = REQUEST.get_or_init(|| {
        Some((std::env::var("KIU_DRAW_FRAME").ok()?.parse().ok()?,
              PathBuf::from(std::env::var_os("KIU_DRAW_CAPTURE")?)))
    }).as_ref() {
        return (*target == frame).then_some(path);
    }
    // F8 in a live render capture: the picture after each draw of two
    // frames (the game may draw only every other one), with its registers
    static LIVE: OnceLock<Option<PathBuf>> = OnceLock::new();
    let path = LIVE.get_or_init(|| Some(PathBuf::from(std::env::var_os("KIU_RENDER_CAPTURE")?).join("frame"))).as_ref()?;
    let first = F8_FRAME.load(Ordering::Relaxed);
    (frame >= first && frame - first < 2).then_some(path)
}

/// Always on, bounded: each distinct top-screen HUD batch (the game's 2D
/// HUD program: health bar, score, and whatever else it draws there) once,
/// with its bounds, projection rows and the PC anchor it got, so a HUD piece
/// the PC layout misses (October 21: the health bar shrinking when Pit is
/// hit) can be read from any session log.
pub(crate) fn hud_batch(viewport: (f32, f32, f32, f32), bounds: [f32; 4], projection: [[f32; 4]; 2], anchor: f32) {
    if viewport.3 != 400.0 { return; } // the lower screen is kiu_ui's
    // menus and the title use the same program: start once gameplay has
    // drawn a health bar or score the PC layout knows
    static PLAYING: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
    if anchor != 0.0 { PLAYING.store(true, Ordering::Relaxed); }
    if !PLAYING.load(Ordering::Relaxed) { return; }
    static SEEN: OnceLock<Mutex<HashSet<[i32; 13]>>> = OnceLock::new();
    let key: [i32; 13] = std::array::from_fn(|i| match i {
        0..4 => (bounds[i] / 4.0).round() as i32,
        4..12 => (projection[(i - 4) / 4][(i - 4) % 4] * 1e4).round() as i32,
        _ => (anchor * 1e4).round() as i32,
    });
    let Ok(mut seen) = SEEN.get_or_init(Default::default).lock() else { return };
    if seen.len() >= 1500 || !seen.insert(key) { return; }
    log::info!(target: "zakuro::hud_batch", "frame {} bounds {:?} projection {:?} anchor {}",
        FRAME.load(Ordering::Relaxed), bounds, projection, anchor);
}

/// Offline isolation only; never enabled by the normal launcher.
pub(crate) fn ignore_depth_test() -> bool {
    static IGNORE: OnceLock<bool> = OnceLock::new();
    *IGNORE.get_or_init(|| std::env::var_os("KIU_DIAGNOSTIC_IGNORE_DEPTH").is_some())
        || LIVE_NO_DEPTH.load(Ordering::Relaxed)
}

/// live A/B switches for a render capture session (F5, F6).
static LIVE_NO_DEPTH: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
static LIVE_CPU_SHADING: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
/// F5 in a render capture: depth testing off, to see what hides what.
pub fn toggle_no_depth() { LIVE_NO_DEPTH.fetch_xor(true, Ordering::Relaxed); }
/// F6 in a render capture: vertex shaders run on the CPU (the reference)
/// instead of the GPU, to tell a shader translation fault from the rest.
pub fn toggle_cpu_shading() { LIVE_CPU_SHADING.fetch_xor(true, Ordering::Relaxed); }
/// the live switches that are on, for the screen and the log, empty when
/// none is.
pub fn live_switches() -> String {
    let mut on = Vec::new();
    if LIVE_NO_DEPTH.load(Ordering::Relaxed) { on.push("F5 depth test OFF"); }
    if LIVE_CPU_SHADING.load(Ordering::Relaxed) { on.push("F6 CPU vertex shading ON"); }
    on.join("  |  ")
}
/// the CPU shades during a draw-by-draw capture too, so each draw's
/// vertices can be written out.
pub(crate) fn cpu_shading() -> bool { LIVE_CPU_SHADING.load(Ordering::Relaxed) || draw_capture_path().is_some() }

struct Capture {
    root: PathBuf,
    draws: File,
    textures: File,
    states: HashSet<Vec<u32>>,
    images: HashSet<(u32, u32, u32, TextureFormat, u64)>,
    bytes: usize,
    draw: u64,
    active: bool,
}

fn capture() -> Option<&'static Mutex<Capture>> {
    static CAPTURE: OnceLock<Option<Mutex<Capture>>> = OnceLock::new();
    CAPTURE.get_or_init(|| {
        let root = PathBuf::from(std::env::var_os("KIU_RENDER_CAPTURE")?);
        let open = || -> std::io::Result<Capture> {
            fs::create_dir_all(&root)?;
            let mut draws = File::create(root.join("draw-states.csv"))?;
            writeln!(draws, "id,first_draw,texture_config,proctex_enabled,proctex_config,depth_mask,depth_format")?;
            let mut textures = File::create(root.join("textures.csv"))?;
            writeln!(textures, "id,address,width,height,format,encoded_bytes")?;
            Ok(Capture { root: root.clone(), draws, textures, states: HashSet::new(),
                         images: HashSet::new(), bytes: 0, draw: 0,
                         active: std::env::var_os("KIU_RENDER_CAPTURE_WAIT").is_none() })
        };
        match open() {
            Ok(c) => Some(Mutex::new(c)),
            Err(e) => { log::warn!("render capture unavailable: {e}"); None }
        }
    }).as_ref()
}

/// Start the opt-in capture at the problematic scene, avoiding boot/menu data.
pub fn start_render_capture() {
    let Some(c) = capture() else { return };
    if let Ok(mut c) = c.lock() {
        c.active = true;
        log::info!("render capture started: {}", c.root.display());
    }
    // half a second later, so the key press itself is long gone
    F8_FRAME.store(FRAME.load(Ordering::Relaxed) + 30, Ordering::Relaxed);
}

pub(crate) fn draw(registers: &[u32]) {
    let Some(c) = capture() else { return };
    let Ok(mut c) = c.lock() else { return };
    if !c.active { return; }
    c.draw += 1;
    // Fragment state only: avoid collecting changing vertex-array pointers.
    let state: Vec<u32> = [0x80, 0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD,
        0xC0, 0xC2, 0xC8, 0xCA, 0xD0, 0xD2, 0xD8, 0xDA, 0xF0, 0xF2, 0xF8, 0xFA,
        0x107, 0x116, 0x85, 0x95, 0x9D].iter().map(|&i| registers[i]).collect();
    if c.states.len() >= 2048 || !c.states.insert(state.clone()) { return; }
    let id = c.states.len();
    let draw = c.draw;
    let bytes: Vec<u8> = registers[..0x200].iter().flat_map(|v| v.to_le_bytes()).collect();
    let result = fs::write(c.root.join(format!("draw-{id:04}.bin")), bytes).and_then(|_| {
        writeln!(c.draws, "{id},{draw},0x{:08X},{},0x{:08X},0x{:08X},0x{:08X}",
                 registers[0x80], (registers[0x80] >> 10) & 1,
                 registers[0xA8], registers[0x107], registers[0x116])
    });
    if let Err(e) = result { log::warn!("render state capture failed: {e}"); }
}

pub(crate) fn texture(address: u32, format: TextureFormat, width: u32, height: u32, data: &[u8]) {
    let Some(c) = capture() else { return };
    let Ok(mut c) = c.lock() else { return };
    if !c.active { return; }
    let bytes = data.len() + width as usize * height as usize * 7 + 64;
    if c.images.len() >= 256 || c.bytes + bytes > 128 * 1024 * 1024 { return; }
    let mut hash = std::collections::hash_map::DefaultHasher::new();
    data.hash(&mut hash);
    if !c.images.insert((address, width, height, format, hash.finish())) { return; }
    c.bytes += bytes;
    let id = c.images.len();
    let mut ppm = format!("P6\n{width} {height}\n255\n").into_bytes();
    let mut rgba = Vec::with_capacity(width as usize * height as usize * 4);
    for y in 0..height {
        for x in 0..width {
            let pixel = crate::texture::sample_texel(data, format, width, x, y);
            ppm.extend_from_slice(&pixel[..3]);
            rgba.extend_from_slice(&pixel);
        }
    }
    let result = fs::write(c.root.join(format!("texture-{id:04}.bin")), data)
        .and_then(|_| fs::write(c.root.join(format!("texture-{id:04}.ppm")), ppm))
        .and_then(|_| fs::write(c.root.join(format!("texture-{id:04}.rgba")), rgba))
        .and_then(|_| writeln!(c.textures, "{id},0x{address:08X},{width},{height},{format:?},{}", data.len()));
    if let Err(e) = result { log::warn!("texture capture failed: {e}"); }
}

/// Bounded projection audit across a replay, including scripted cameras.
pub(crate) fn projection(unit: &crate::shader::ShaderUnit, width: f32, height: f32) {
    static AUDIT: OnceLock<Option<Mutex<(File, HashSet<Vec<u32>>)>>> = OnceLock::new();
    let Some(audit) = AUDIT.get_or_init(|| {
        let path = std::env::var_os("KIU_PROJECTION_TRACE")?;
        let mut file = File::create(path).ok()?;
        writeln!(file, "frame,program,linear_key,width,height,row0,row1,row86,row87,row88,row89").ok()?;
        Some(Mutex::new((file, HashSet::new())))
    }) else { return };
    let Ok(mut audit) = audit.lock() else { return };
    let id = unit.fingerprint();
    // Capture code once per identity, including programs used by the CPU
    // vertex path (the per-draw Vulkan capture cannot see those).
    static PROGRAMS: OnceLock<Mutex<HashSet<u64>>> = OnceLock::new();
    if let Ok(mut seen) = PROGRAMS.get_or_init(Default::default).lock() {
        if seen.len() < 128 && seen.insert(id) {
            let root = PathBuf::from(std::env::var_os("KIU_PROJECTION_TRACE").unwrap()).with_extension("shaders");
            let _ = fs::create_dir_all(&root);
            let bytes: Vec<u8> = unit.program.iter().chain(unit.descriptors.iter()).flat_map(|v| v.to_le_bytes()).collect();
            let _ = fs::write(root.join(format!("{id:016X}.bin")), bytes);
            #[cfg(feature = "vulkan")]
            {
                let mut shader = unit.clone(); shader.prepare();
                if let Some(program) = shader.prepared() {
                    if let Ok(source) = crate::shader::glsl::translate(&program, unit.entry_point, &std::array::from_fn(|i| i as u32)) {
                        let _ = fs::write(root.join(format!("{id:016X}.vert")), source);
                    }
                }
            }
        }
    }
    let rows = [0,1,86,87,88,89];
    let mut key = vec![id as u32, (id >> 32) as u32, width.to_bits(), height.to_bits()];
    for row in rows { key.extend(unit.float_uniforms[row].map(f32::to_bits)); }
    if audit.1.len() >= 16384 || !audit.1.insert(key) { return; }
    let _ = write!(audit.0, "{},{id:016X},{:?},{width},{height}", FRAME.load(Ordering::Relaxed), crate::raster::kiu_linear_shader_key(unit));
    for row in rows { let _ = write!(audit.0, ",\"{:?}\"", unit.float_uniforms[row]); }
    let _ = writeln!(audit.0);
}
