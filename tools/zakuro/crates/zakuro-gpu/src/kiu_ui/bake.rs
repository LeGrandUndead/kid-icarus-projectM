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

/// How much of a draw's vertex color can be left to the host vertices
/// instead of baked into the texture, so that one baked texture serves every
/// step of a color or alpha animation (a flashing score, a fading panel)
/// rather than a new bake and upload per animation frame.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Tint {
    /// the combiner does not use the vertex color: bake with white, no tint.
    Unused,
    /// the combiner multiplies the texture by the whole vertex color: bake
    /// with white, tint with the color.
    Color,
    /// only the alpha scales the result: bake with the color at full alpha,
    /// tint with the alpha.
    Alpha,
    /// the color takes part some other way: bake with it.
    Baked,
}

/// vertex colors a combiner is tried with: what it does with them tells
/// what it does with any color, the combiner being linear in it or not.
const PROBES: [[f32; 4]; 3] = [[0.3, 0.6, 0.9, 0.5], [0.8, 0.2, 0.4, 0.9], [0.05, 0.95, 0.5, 0.25]];

/// Which Tint a combiner allows with a texture, checked on a sample of its
/// real texels with a few colors: unused when the result never changes with
/// the color; a color tint when it is always the result with white times
/// the color; an alpha fade when the color's alpha only scales the alpha.
/// It does not depend on the draw's own color, so a texture and combiner
/// are classified once (the check costs ~200 combiner runs, a per-draw
/// check cost the boss defeat scene's many sprites 10-30 ms a frame).
pub fn classify(env: &TexEnv, texels: &[[u8; 4]]) -> Tint {
    if texels.is_empty() { return Tint::Baked; }
    let step = (texels.len() / 61).max(1);
    let sample = || texels.iter().step_by(step).take(64);
    let white = [1.0; 4];
    let unused = PROBES.iter().all(|&p| sample().all(|&pixel| texel(env, p, pixel) == texel(env, white, pixel)));
    if unused { return Tint::Unused; }
    let modulates = PROBES.iter().all(|&p| sample().all(|&pixel| {
        let (lit, plain) = (texel(env, p, pixel), texel(env, white, pixel));
        (0..4).all(|i| (lit[i].clamp(0.0, 1.0) - plain[i].clamp(0.0, 1.0) * p[i]).abs() < 1.5 / 255.0)
    }));
    if modulates { return Tint::Color; }
    if PROBES.iter().all(|&p| alpha_is_a_fade(env, p, texels)) { Tint::Alpha } else { Tint::Baked }
}

/// Premultiplied RGBA8 for the host overlay.
pub fn bake(env: &TexEnv, primary: [f32; 4], texels: &[[u8; 4]]) -> Vec<u8> {
    let mut pixels = Vec::with_capacity(texels.len() * 4);
    // runs of one texel (transparent space in atlases) are combined once
    let mut last = None;
    for &pixel in texels {
        let out = match last {
            Some((p, out)) if p == pixel => out,
            _ => { let out = premultiply(texel(env, primary, pixel)); last = Some((pixel, out)); out }
        };
        pixels.extend(out);
    }
    pixels
}

/// The combiner's results on a fixed sample of a texture's texels, clamped:
/// what `scale` compares two colors of the same texture and combiner by.
pub fn samples(env: &TexEnv, primary: [f32; 4], texels: &[[u8; 4]]) -> Vec<[f32; 4]> {
    // visible texels: a sample of only transparent ones (an atlas's empty
    // space) would match any color
    let step = (texels.len() / 1021).max(1);
    let mut picked: Vec<[u8; 4]> = texels.iter().step_by(step).filter(|p| p[3] > 0).copied().collect();
    if picked.len() > 64 { let keep = picked.len() / 64; picked = picked.into_iter().step_by(keep).take(64).collect(); }
    picked.extend(texels.iter().step_by((texels.len() / 15).max(1)).take(16));
    picked.into_iter().map(|p| texel(env, primary, p).map(|c| c.clamp(0.0, 1.0))).collect()
}

/// When every sample of `now` is the matching sample of `then` times one
/// factor per channel in [0, 1], those factors: the bake made for `then`
/// shown with them as the host tint gives the bake `now` would (a fade, a
/// darkening). Results are compared straight; the overlay applies the
/// alpha factor to the premultiplied color too.
pub fn scale(then: &[[f32; 4]], now: &[[f32; 4]]) -> Option<[f32; 4]> {
    if then.len() != now.len() || then.is_empty() { return None; }
    let mut k = [1.0f32; 4];
    for (c, k) in k.iter_mut().enumerate() {
        let (dot, norm) = then.iter().zip(now).fold((0.0, 0.0), |(d, n), (a, b)| (d + a[c] * b[c], n + a[c] * a[c]));
        if norm > 1e-6 { *k = dot / norm; }
        if !(-0.002..=1.002).contains(k) { return None; }
        *k = k.clamp(0.0, 1.0);
    }
    // straight color under zero alpha is invisible: compare premultiplied
    let fits = then.iter().zip(now).all(|(a, b)| {
        let pb = premultiply(*b);
        let scaled = [a[0] * k[0] * a[3] * k[3], a[1] * k[1] * a[3] * k[3], a[2] * k[2] * a[3] * k[3], a[3] * k[3]];
        (0..4).all(|i| (scaled[i] * 255.0 - pb[i] as f32).abs() <= 1.5)
    });
    fits.then_some(k)
}

/// The texels a quad samples: its guest UVs' rectangle in texels (left,
/// top, right, bottom, rows top-down as decoded), at least one texel each
/// way, and the UVs as host coordinates inside that rectangle. A quad drawn
/// from an atlas is baked from its own rectangle only, so the host's
/// filtering at the larger PC size never reaches the neighbouring sprite
/// (October 21: the white panel above the orb tray showed as lines over
/// the orbs).
pub fn crop(width: u32, height: u32, uv: &[[f32; 2]; 4]) -> ([u32; 4], [[f32; 2]; 4]) {
    let (w, h) = (width as f32, height as f32);
    let (mut lo, mut hi) = ([f32::INFINITY; 2], [f32::NEG_INFINITY; 2]);
    for p in uv {
        // texel space, rows top-down (PICA's V points up)
        let t = [p[0] * w, (1.0 - p[1]) * h];
        for i in 0..2 { lo[i] = lo[i].min(t[i]); hi[i] = hi[i].max(t[i]); }
    }
    let span = |lo: f32, hi: f32, size: u32| {
        // texel edges, give or take float error
        let a = ((lo + 0.01).floor().max(0.0) as u32).min(size - 1);
        let b = ((hi - 0.01).ceil().max(0.0) as u32).clamp(a + 1, size);
        (a, b)
    };
    let (x0, x1) = span(lo[0], hi[0], width);
    let (y0, y1) = span(lo[1], hi[1], height);
    let sample = uv.map(|p| [(p[0] * w - x0 as f32) / (x1 - x0) as f32, ((1.0 - p[1]) * h - y0 as f32) / (y1 - y0) as f32]);
    ([x0, y0, x1, y1], sample)
}

/// The texels of a rectangle from `crop`, `scale` times larger when the
/// texels are an enlarged version of the cropped texture.
pub fn crop_texels(texels: &[[u8; 4]], width: u32, rect: [u32; 4], scale: u32) -> Vec<[u8; 4]> {
    let [x0, y0, x1, y1] = rect.map(|v| v * scale);
    let stride = (width * scale) as usize;
    (y0..y1).flat_map(|y| texels[y as usize * stride + x0 as usize..y as usize * stride + x1 as usize].iter().copied()).collect()
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

    /// a combiner multiplying the texture by the vertex color lets the
    /// host apply any color, so a color animation needs one bake; a replace
    /// ignores the color and must keep it baked (it changes nothing there).
    #[test]
    fn a_fade_reuses_the_bake_and_a_new_hue_does_not() {
        let then = vec![[1.0, 0.5, 0.2, 1.0], [0.3, 0.3, 0.3, 0.5], [0.0, 0.0, 0.0, 0.0]];
        let faded: Vec<[f32; 4]> = then.iter().map(|c| [c[0], c[1], c[2], c[3] * 0.4]).collect();
        let k = scale(&then, &faded).unwrap();
        assert!((k[3] - 0.4).abs() < 0.01 && (k[0] - 1.0).abs() < 0.01);
        let red: Vec<[f32; 4]> = then.iter().map(|c| [1.0, c[1], c[2], c[3]]).collect();
        assert_eq!(scale(&then, &red), None);
        let brighter: Vec<[f32; 4]> = then.iter().map(|c| [c[0] * 0.5, c[1] * 0.5, c[2] * 0.5, c[3]]).collect();
        assert_eq!(scale(&brighter, &then), None);
    }

    #[test]
    fn a_quad_bakes_only_the_texels_it_samples() {
        // the orb tray: u 0.3398-0.5273, v 0.0117-0.1992 of a 256x256 atlas
        let [l, r, b, t] = [87.0 / 256.0, 135.0 / 256.0, 3.0 / 256.0, 51.0 / 256.0];
        let uv = [[l, t], [r, t], [l, b], [r, b]];
        let (rect, sample) = crop(256, 256, &uv);
        assert_eq!(rect, [87, 205, 135, 253]);
        assert_eq!(sample, [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]);
        assert!(sample.iter().flatten().all(|v| (-0.02..=1.02).contains(v)));
        // a one-column strip stretched across a panel keeps one texel
        let strip = [[0.537_109_4, 0.412_109_4]; 4];
        let (rect, _) = crop(256, 256, &strip);
        assert_eq!((rect[2] - rect[0], rect[3] - rect[1]), (1, 1));
        let texels: Vec<[u8; 4]> = (0..16u8).map(|i| [i, 0, 0, 255]).collect();
        assert_eq!(crop_texels(&texels, 4, [1, 2, 3, 4], 1), vec![[9, 0, 0, 255], [10, 0, 0, 255], [13, 0, 0, 255], [14, 0, 0, 255]]);
    }

    #[test]
    fn runs_of_one_texel_bake_like_single_texels() {
        let env = TexEnv::read(&registers(0x0003_0003, 0x0000_0000));
        let texels = vec![[10, 20, 30, 200], [10, 20, 30, 200], [0, 0, 0, 0], [0, 0, 0, 0], [255, 0, 0, 255]];
        let one_by_one: Vec<u8> = texels.iter().flat_map(|&p| premultiply(texel(&env, [0.5; 4], p))).collect();
        assert_eq!(bake(&env, [0.5; 4], &texels), one_by_one);
    }

    #[test]
    fn modulated_color_is_a_host_tint() {
        let texels = [[255, 128, 0, 255], [10, 20, 30, 128], [0, 0, 0, 0], [255, 255, 255, 255]];
        let env = TexEnv::read(&registers(0x0003_0003, 0x0001_0001));
        let flash = [1.0, 0.4, 0.2, 0.7];
        assert_eq!(classify(&env, &texels), Tint::Color);
        // what the host draws: bake with white, times the color
        for &pixel in &texels {
            let (lit, plain) = (texel(&env, flash, pixel), texel(&env, [1.0; 4], pixel));
            for i in 0..4 { assert!((lit[i] - plain[i] * flash[i]).abs() < 1e-5); }
        }
        let env = TexEnv::read(&registers(0x0003_0003, 0x0000_0000));
        assert_eq!(classify(&env, &texels), Tint::Unused);
    }
}
