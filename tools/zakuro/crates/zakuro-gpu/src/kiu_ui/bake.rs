//! Applies a draw's own texture combiner to its original texture once, so the
//! host overlay shows exactly what the game's combiner produced.
use crate::tev::TexEnv;

/// Combiner output for one texel.
fn texel(env: &TexEnv, primary: [f32; 4], pixel: [u8; 4]) -> [f32; 4] {
    let mut textures = [[0.0; 4]; 4];
    textures[0] = pixel.map(|v| v as f32 / 255.0);
    env.apply(primary, textures, None)
}

pub fn premultiply(c: [f32; 4]) -> [u8; 4] {
    let a = c[3].clamp(0.0, 1.0);
    [(c[0].clamp(0.0, 1.0) * a * 255.0).round() as u8,
     (c[1].clamp(0.0, 1.0) * a * 255.0).round() as u8,
     (c[2].clamp(0.0, 1.0) * a * 255.0).round() as u8, (a * 255.0).round() as u8]
}

/// Whether the vertex alpha only scales the result's alpha, the usual fade.
/// Then one baked texture serves every step of a fade, with the alpha given
/// to the host vertices, instead of a new texture per animation frame.
/// Checked on a sample of the draw's real texels with its real combiner.
pub fn alpha_is_a_fade(env: &TexEnv, primary: [f32; 4], texels: &[[u8; 4]]) -> bool {
    if texels.is_empty() { return false; }
    let opaque = [primary[0], primary[1], primary[2], 1.0];
    let half = [primary[0], primary[1], primary[2], 0.5];
    let step = (texels.len() / 61).max(1);
    texels.iter().step_by(step).take(64).all(|&pixel| {
        let (a, b) = (texel(env, opaque, pixel), texel(env, half, pixel));
        (b[3] - a[3].clamp(0.0, 1.0) * 0.5).abs() < 1.5 / 255.0
            && (0..3).all(|i| a[3] < 1.0 / 255.0 || (a[i].clamp(0.0, 1.0) - b[i].clamp(0.0, 1.0)).abs() < 1.5 / 255.0)
    })
}

/// Premultiplied RGBA8 for the host overlay.
pub fn bake(env: &TexEnv, primary: [f32; 4], texels: &[[u8; 4]]) -> Vec<u8> {
    let mut pixels = Vec::with_capacity(texels.len() * 4);
    for &pixel in texels { pixels.extend(premultiply(texel(env, primary, pixel))); }
    pixels
}

/// Area (box) resampling of premultiplied RGBA to a smaller size, so an HD
/// texture shown smaller than its texels stays clean (the overlay has no
/// mipmaps; plain bilinear minification would alias).
pub fn shrink(pixels: &[u8], w: u32, h: u32, tw: u32, th: u32) -> Vec<u8> {
    let (tw, th) = (tw.min(w).max(1), th.min(h).max(1));
    if tw == w && th == h { return pixels.to_vec(); }
    let (fx, fy) = (w as f32 / tw as f32, h as f32 / th as f32);
    // separable: rows first, then columns, with fractional pixel coverage
    let weights = |n: u32, f: f32, src: u32| -> Vec<Vec<(usize, f32)>> {
        (0..n).map(|i| {
            let (a, b) = (i as f32 * f, ((i + 1) as f32 * f).min(src as f32));
            let mut v = Vec::new();
            let mut x = a.floor();
            while x < b {
                let cover = (b.min(x + 1.0) - a.max(x)).max(0.0);
                if cover > 0.0 { v.push((x as usize, cover / f)); }
                x += 1.0;
            }
            v
        }).collect()
    };
    let (wx, wy) = (weights(tw, fx, w), weights(th, fy, h));
    let mut rows = vec![0f32; (tw * h * 4) as usize];
    for y in 0..h as usize {
        for (ox, taps) in wx.iter().enumerate() {
            for c in 0..4 {
                rows[(y * tw as usize + ox) * 4 + c] = taps.iter().map(|&(x, k)| pixels[(y * w as usize + x) * 4 + c] as f32 * k).sum();
            }
        }
    }
    let mut out = vec![0u8; (tw * th * 4) as usize];
    for (oy, taps) in wy.iter().enumerate() {
        for x in 0..tw as usize {
            for c in 0..4 {
                let v: f32 = taps.iter().map(|&(y, k)| rows[(y * tw as usize + x) * 4 + c] * k).sum();
                out[(oy * tw as usize + x) * 4 + c] = v.round().clamp(0.0, 255.0) as u8;
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn shrink_averages_by_area() {
        // 4x1 -> 2x1: pairs averaged; 3x1 -> 2x1: fractional coverage
        let px = [0u8, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 0];
        assert_eq!(super::shrink(&px, 4, 1, 2, 1), vec![128, 128, 128, 128, 128, 128, 128, 128]);
        let px3 = [255u8, 0, 0, 255, 0, 0, 0, 0, 255, 0, 0, 255];
        let r = super::shrink(&px3, 3, 1, 2, 1);
        assert_eq!(r[0], 170);
        assert_eq!(r[4], 170);
    }

    use super::*;
    #[test]
    fn transparency_is_premultiplied_without_opaque_background() {
        assert_eq!(premultiply([1.0, 0.5, 0.0, 0.0]), [0, 0, 0, 0]);
        assert_eq!(premultiply([1.0, 0.5, 0.0, 0.5]), [128, 64, 0, 128]);
    }

    fn registers(stage0_source: u32, stage0_combine: u32) -> Vec<u32> {
        // TEV stage 0 at 0xC0: sources, operands, combiners, color, scale
        let mut r = vec![0u32; 0x300];
        r[0xC0] = stage0_source;
        r[0xC1] = 0;
        r[0xC2] = stage0_combine;
        r[0xC3] = 0;
        r[0xC4] = 0;
        // stages 1-5 pass the previous result through: source previous (0xF)
        for base in [0xC8, 0xD0, 0xD8, 0xF0, 0xF8] { r[base] = 0x000F_000F; r[base + 2] = 0; }
        r
    }

    #[test]
    fn modulated_fade_is_recognized_and_replace_is_not() {
        // stage 0: color = texture0 * primary, alpha = texture0 * primary
        let modulate = registers(0x0003_0003 | (0x0000_0000), 0x0001_0001);
        // source1 must be primary (0); source0 texture0 (3)
        let env = TexEnv::read(&modulate);
        let texels = [[255, 128, 0, 255], [10, 20, 30, 128], [0, 0, 0, 0], [255, 255, 255, 255]];
        assert!(alpha_is_a_fade(&env, [1.0, 1.0, 1.0, 0.3], &texels));
        // alpha = primary only would still scale with primary... use a constant instead:
        // stage 0 replace with texture0: primary alpha has no effect, so a
        // half-alpha vertex must not be applied as a fade.
        let replace = registers(0x0003_0003, 0x0000_0000);
        let env = TexEnv::read(&replace);
        assert!(!alpha_is_a_fade(&env, [1.0, 1.0, 1.0, 0.3], &texels));
    }
}
