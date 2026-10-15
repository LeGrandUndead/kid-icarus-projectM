//! Optional, content-addressed PNG replacements. Guest textures and render
//! targets remain untouched; only the Vulkan upload receives larger pixels.
use std::{collections::HashSet, path::PathBuf, sync::OnceLock};

struct Pack { root: PathBuf, names: HashSet<String> }

fn pack() -> Option<&'static Pack> {
    static PACK: OnceLock<Option<Pack>> = OnceLock::new();
    PACK.get_or_init(|| {
        let root = PathBuf::from(std::env::var_os("KIU_TEXTURE_PACK")?);
        let names = std::fs::read_dir(&root).ok()?.filter_map(Result::ok)
            .filter(|e| e.file_type().is_ok_and(|t| t.is_file()))
            .filter_map(|e| e.file_name().into_string().ok()).collect();
        Some(Pack { root, names })
    }).as_ref()
}

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
    let pack = pack()?;
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
