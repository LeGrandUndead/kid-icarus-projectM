//! Optional, content-addressed PNG replacements. Guest textures and render
//! targets remain untouched; only the Vulkan upload receives larger pixels.
use std::{collections::HashSet, path::PathBuf, sync::OnceLock};

struct Pack { root: PathBuf, names: HashSet<String> }

fn pack() -> Option<&'static Pack> {
    static PACK: OnceLock<Option<Pack>> = OnceLock::new();
    PACK.get_or_init(|| open("KIU_TEXTURE_PACK")).as_ref()
}

/// The HD HUD pack (KIU_HUD_PACK), used only by the relocated PC HUD layers.
fn hud_pack() -> Option<&'static Pack> {
    static PACK: OnceLock<Option<Pack>> = OnceLock::new();
    PACK.get_or_init(|| {
        let pack = open("KIU_HUD_PACK")?;
        // Decode the few HUD atlases once, in the background, at start-up:
        // the first HUD frame then needs no PNG decoding (no audio hitch).
        let names: Vec<String> = pack.names.iter().filter(|n| n.ends_with(".png")).cloned().collect();
        std::thread::spawn(|| {
            for name in names {
                let Some(pack) = hud_pack() else { return };
                let Some((size, hash)) = name.trim_end_matches(".png").split_once('-') else { continue };
                let Some((w, h)) = size.split_once('x') else { continue };
                let (Ok(w), Ok(h), Ok(hash)) = (w.parse(), h.parse(), u64::from_str_radix(hash, 16)) else { continue };
                if let Some(image) = decode(pack, hash, w, h, 1) {
                    if let Ok(mut cache) = decoded().lock() { cache.insert((name, 1), image); }
                }
            }
        });
        Some(pack)
    }).as_ref()
}

fn decoded() -> &'static std::sync::Mutex<std::collections::HashMap<(String, u8), Replacement>> {
    static CACHE: OnceLock<std::sync::Mutex<std::collections::HashMap<(String, u8), Replacement>>> = OnceLock::new();
    CACHE.get_or_init(Default::default)
}

fn open(variable: &str) -> Option<Pack> {
    {
        let root = PathBuf::from(std::env::var_os(variable)?);
        let names = std::fs::read_dir(&root).ok()?.filter_map(Result::ok)
            .filter(|e| e.file_type().is_ok_and(|t| t.is_file()))
            .filter_map(|e| e.file_name().into_string().ok()).collect();
        Some(Pack { root, names })
    }
}

#[derive(Clone)]
pub(crate) struct Replacement {
    pub width: u32,
    pub height: u32,
    pub levels: u8,
    pub extra_levels: u8,
    pub texels: Vec<[u8; 4]>,
}

fn scale(width: u32, height: u32, w: u32, h: u32) -> Option<u32> {
    if width == 0 || height == 0 || w > 4096 || h > 4096 || u64::from(w) * u64::from(h) > 1024 * 1024 { return None; }
    let scale = w / width;
    (matches!(scale, 2 | 4 | 8) && w == width * scale && h == height * scale).then_some(scale)
}

pub(crate) fn load(hash: u64, width: u32, height: u32, levels: u8) -> Option<Replacement> {
    load_from(pack()?, hash, width, height, levels)
}

pub(crate) fn load_hud(hash: u64, width: u32, height: u32, levels: u8) -> Option<Replacement> {
    let pack = hud_pack()?;
    let name = format!("{width}x{height}-{hash:016X}.png");
    if let Some(image) = decoded().lock().ok().and_then(|cache| cache.get(&(name, levels)).cloned()) {
        return Some(image);
    }
    load_from(pack, hash, width, height, levels)
}

pub(crate) fn hud_pack_enabled() -> bool { hud_pack().is_some() }

/// The PC menu art pack (KIU_MENU_PACK, tools/recomp/build_menu_pc_pack.py):
/// the menu screens' textures reconstructed from the user's ROM, named by
/// the fingerprint of their encoded ROM bytes (the UI catalog's identity),
/// `<w>x<h>-<fingerprint>.png`. Used for every draw of those textures.
fn menu_pack() -> Option<&'static Pack> {
    static PACK: OnceLock<Option<Pack>> = OnceLock::new();
    PACK.get_or_init(|| {
        let pack = open("KIU_MENU_PACK")?;
        log::info!("PC menu art: {} textures in {}", pack.names.len(), pack.root.display());
        Some(pack)
    }).as_ref()
}

pub(crate) fn menu_pack_enabled() -> bool { menu_pack().is_some() }

/// Where a menu texture's PC version is.
pub(crate) enum Menu {
    /// not in the pack: the original is used
    Missing,
    /// being decoded off the drawing thread: show the original meanwhile
    Pending,
    Ready(std::sync::Arc<Replacement>),
}

type MenuSlot = Option<std::sync::Arc<Replacement>>;

fn menu_cache() -> &'static std::sync::Mutex<std::collections::HashMap<(u64, u8), Option<MenuSlot>>> {
    static CACHE: OnceLock<std::sync::Mutex<std::collections::HashMap<(u64, u8), Option<MenuSlot>>>> = OnceLock::new();
    CACHE.get_or_init(Default::default)
}

/// The PC version of a menu texture. The first request starts decoding it in
/// the background (PNG decoding on the drawing thread made menus hitch).
pub(crate) fn menu(hash: u64, width: u32, height: u32, levels: u8) -> Menu {
    let Some(pack) = menu_pack() else { return Menu::Missing };
    if !pack.names.contains(&format!("{width}x{height}-{hash:016X}.png")) { return Menu::Missing; }
    let Ok(mut cache) = menu_cache().lock() else { return Menu::Missing };
    match cache.get(&(hash, levels)) {
        Some(Some(Some(image))) => return Menu::Ready(image.clone()),
        Some(Some(None)) => return Menu::Missing,
        Some(None) => return Menu::Pending,
        None => {}
    }
    cache.insert((hash, levels), None);
    std::thread::spawn(move || {
        let image = menu_pack().and_then(|pack| decode(pack, hash, width, height, levels)).map(std::sync::Arc::new);
        if let Ok(mut cache) = menu_cache().lock() { cache.insert((hash, levels), Some(image)); }
    });
    Menu::Pending
}

/// The GPU has its copy: the decoded pixels are not kept (a later upload
/// decodes them again).
pub(crate) fn menu_uploaded(hash: u64, levels: u8) {
    if let Ok(mut cache) = menu_cache().lock() {
        if matches!(cache.get(&(hash, levels)), Some(Some(Some(_)))) { cache.remove(&(hash, levels)); }
    }
}

fn load_from(pack: &Pack, hash: u64, width: u32, height: u32, levels: u8) -> Option<Replacement> {
    decode(pack, hash, width, height, levels)
}

fn decode(pack: &Pack, hash: u64, width: u32, height: u32, levels: u8) -> Option<Replacement> {
    let name = format!("{width}x{height}-{hash:016X}.png");
    if !pack.names.contains(&name) { return None; }
    let result = (|| -> Result<Replacement, String> {
        let mut reader = image::ImageReader::open(pack.root.join(&name)).map_err(|e| e.to_string())?;
        reader.set_format(image::ImageFormat::Png);
        let mut limits = image::Limits::default();
        limits.max_image_width = Some(4096);
        limits.max_image_height = Some(4096);
        limits.max_alloc = Some(80 * 1024 * 1024);
        reader.limits(limits);
        let image = reader.decode().map_err(|e| e.to_string())?.into_rgba8();
        let (w, h) = image.dimensions();
        let factor = scale(width, height, w, h).ok_or("expected matching 2x, 4x or 8x dimensions (maximum 4096 per side and 1 megapixel)")?;
        let extra_levels = factor.ilog2() as u8;
        let count = (levels + extra_levels).min(w.max(h).ilog2() as u8 + 1);
        let mut pixels: Vec<[u8; 4]> = image.into_raw().as_chunks::<4>().0.to_vec();
        let mut start = 0;
        let (mut mw, mut mh) = (w as usize, h as usize);
        for _ in 1..count {
            let next = pixels.len();
            for y in 0..(mh / 2).max(1) {
                for x in 0..(mw / 2).max(1) {
                    let samples = [pixels[start + (y*2).min(mh-1)*mw + (x*2).min(mw-1)],
                        pixels[start + (y*2).min(mh-1)*mw + (x*2+1).min(mw-1)],
                        pixels[start + (y*2+1).min(mh-1)*mw + (x*2).min(mw-1)],
                        pixels[start + (y*2+1).min(mh-1)*mw + (x*2+1).min(mw-1)]];
                    let alpha: u32 = samples.iter().map(|p| p[3] as u32).sum();
                    let mut pixel = [0, 0, 0, ((alpha + 2) / 4) as u8];
                    if alpha > 0 { for c in 0..3 {
                        pixel[c] = ((samples.iter().map(|p| p[c] as u32 * p[3] as u32).sum::<u32>() + alpha/2) / alpha) as u8;
                    } }
                    pixels.push(pixel);
                }
            }
            start = next; mw = (mw/2).max(1); mh = (mh/2).max(1);
        }
        Ok(Replacement { width: w, height: h, levels: count, extra_levels, texels: pixels })
    })();
    match result {
        Ok(image) => { log::info!("HD texture: {name} -> {}x{}", image.width, image.height); Some(image) }
        Err(error) => { log::warn!("Ignoring texture replacement {name}: {error}"); None }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn replacement_dimensions_preserve_atlas_coordinates() {
        assert_eq!(scale(256,128,1024,512), Some(4));
        for (w,h) in [(1024,1024),(256,128),(768,384),(8192,4096),(0,0)] {
            assert_eq!(scale(256,128,w,h), None);
        }
    }
}
