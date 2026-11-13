//! Pictures: RGBA, premultiplied (as egui draws), read from the menu art
//! pack, and the few operations the redrawn menus need: cutting a sheet's
//! shapes apart, turning, a soft glow.

use std::path::Path;

/// An RGBA picture.
#[derive(Clone)]
pub struct Picture {
    pub width: usize,
    pub height: usize,
    pub rgba: Vec<u8>,
}

impl Picture {
    pub fn alpha(&self, x: usize, y: usize) -> u8 { self.rgba[(y * self.width + x) * 4 + 3] }

    /// The part `[x0, y0, x1, y1)`, keeping only the pixels of shapes for
    /// which `mine` holds.
    pub fn cut(&self, r: [usize; 4], shape: &[u32], mine: &[bool]) -> Picture {
        let (w, h) = (r[2] - r[0], r[3] - r[1]);
        let mut rgba = vec![0u8; w * h * 4];
        for y in 0..h {
            for x in 0..w {
                let (sx, sy) = (x + r[0], y + r[1]);
                let s = shape[sy * self.width + sx];
                if s != 0 && mine[s as usize] {
                    let from = (sy * self.width + sx) * 4;
                    rgba[(y * w + x) * 4..][..4].copy_from_slice(&self.rgba[from..from + 4]);
                }
            }
        }
        Picture { width: w, height: h, rgba }
    }

    /// Turned a quarter right (undoes a sheet's quarter left).
    pub fn turned_right(&self) -> Picture {
        let (w, h) = (self.height, self.width);
        let mut rgba = vec![0u8; w * h * 4];
        for y in 0..h {
            for x in 0..w {
                // new (x, y) comes from old (y, oldheight - 1 - x)
                let from = ((self.height - 1 - x) * self.width + y) * 4;
                rgba[(y * w + x) * 4..][..4].copy_from_slice(&self.rgba[from..from + 4]);
            }
        }
        Picture { width: w, height: h, rgba }
    }

    /// A soft gold halo around the shape, `pad` pixels added on each side.
    pub fn glow(&self, pad: usize) -> Picture {
        let (w, h) = (self.width + 2 * pad, self.height + 2 * pad);
        let mut a = vec![0f32; w * h];
        for y in 0..self.height {
            for x in 0..self.width {
                a[(y + pad) * w + x + pad] = self.alpha(x, y) as f32 / 255.0;
            }
        }
        // grown, then blurred: three box blurs make a smooth falloff
        let grow = (pad / 2).max(1);
        a = spread(&a, w, h, grow, f32::max);
        for _ in 0..3 { a = spread(&a, w, h, (pad / 3).max(1), |s, v| s + v); }
        let peak = a.iter().cloned().fold(0.0, f32::max).max(1e-6);
        let mut rgba = vec![0u8; w * h * 4];
        for (i, v) in a.iter().enumerate() {
            let k = (v / peak).min(1.0);
            // premultiplied gold
            let c = [255.0, 208.0, 84.0].map(|c: f32| (c * k) as u8);
            rgba[i * 4..][..4].copy_from_slice(&[c[0], c[1], c[2], (255.0 * k) as u8]);
        }
        Picture { width: w, height: h, rgba }
    }
}

/// A box pass (both directions) combining a pixel's neighbours with `f`;
/// sums are averaged.
fn spread(a: &[f32], w: usize, h: usize, r: usize, f: fn(f32, f32) -> f32) -> Vec<f32> {
    let average = f(1.0, 1.0) == 2.0;
    let pass = |src: &[f32], horizontal: bool| -> Vec<f32> {
        let mut out = vec![0f32; w * h];
        for y in 0..h {
            for x in 0..w {
                let mut acc = 0.0;
                let mut n = 0.0;
                for d in -(r as isize)..=(r as isize) {
                    let (sx, sy) = if horizontal { (x as isize + d, y as isize) } else { (x as isize, y as isize + d) };
                    if sx < 0 || sy < 0 || sx >= w as isize || sy >= h as isize { continue; }
                    acc = f(acc, src[sy as usize * w + sx as usize]);
                    n += 1.0;
                }
                out[y * w + x] = if average { acc / n } else { acc };
            }
        }
        out
    };
    let once = pass(a, true);
    pass(&once, false)
}

/// The shapes of a picture (4-connected pixels with some alpha): each
/// pixel's shape number (0 none), and each shape's bounds (index = number).
pub fn shapes(p: &Picture) -> (Vec<u32>, Vec<[usize; 4]>) {
    let mut shape = vec![0u32; p.width * p.height];
    let mut bounds = vec![[0usize; 4]];
    let mut stack = Vec::new();
    for start in 0..shape.len() {
        if shape[start] != 0 || p.rgba[start * 4 + 3] <= 10 { continue; }
        let n = bounds.len() as u32;
        let mut b = [usize::MAX, usize::MAX, 0, 0];
        shape[start] = n;
        stack.push(start);
        while let Some(i) = stack.pop() {
            let (x, y) = (i % p.width, i / p.width);
            b = [b[0].min(x), b[1].min(y), b[2].max(x + 1), b[3].max(y + 1)];
            let mut visit = |j: usize| if shape[j] == 0 && p.rgba[j * 4 + 3] > 10 { shape[j] = n; stack.push(j); };
            if x > 0 { visit(i - 1); }
            if x + 1 < p.width { visit(i + 1); }
            if y > 0 { visit(i - p.width); }
            if y + 1 < p.height { visit(i + p.width); }
        }
        bounds.push(b);
    }
    (shape, bounds)
}

/// Reads a picture file, premultiplied.
pub fn load(path: &Path) -> Option<Picture> {
    let img = image::open(path).ok()?.to_rgba8();
    let (w, h) = img.dimensions();
    let mut rgba = img.into_raw();
    // premultiplied, as egui draws
    for px in rgba.chunks_exact_mut(4) {
        let a = px[3] as u32;
        for c in &mut px[..3] { *c = ((*c as u32 * a + 127) / 255) as u8; }
    }
    Some(Picture { width: w as usize, height: h as usize, rgba })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pc_menus::art::cut_buttons;
    use crate::pc_menus::cursor::Graph;
    use crate::pc_menus::screens::{Button, Screen};
    fn picture(w: usize, h: usize, on: &[(usize, usize)]) -> Picture {
        let mut rgba = vec![0u8; w * h * 4];
        for &(x, y) in on { rgba[(y * w + x) * 4..][..4].copy_from_slice(&[x as u8, y as u8, 7, 255]); }
        Picture { width: w, height: h, rgba }
    }
    #[test]
    fn a_button_keeps_its_own_shapes_only() {
        // a 2x2 block (the button) and a single pixel poking into its
        // rectangle from a neighbour whose middle is outside it
        let p = picture(8, 4, &[(0, 0), (1, 0), (0, 1), (1, 1), (3, 1), (4, 1), (5, 1), (6, 1)]);
        let (_, bounds) = shapes(&p);
        assert_eq!(bounds.len(), 3);
        let screen = Screen { id: 0, sheet: "", sheet_size: 8, buttons: &[
            Button { name: "a", sheet: [0, 0, 4, 2], turned: false, at: [0.0; 2], scale: 1.0, tilt: 0.0, touch: (0, 0), node: 0 }],
            graph: Graph { edges: &[] }, selected_art: &[] };
        let cut = &cut_buttons(&p, &screen)[0];
        assert_eq!((cut.width, cut.height), (4, 2));
        assert_eq!(cut.alpha(1, 1), 255);
        assert_eq!(cut.alpha(3, 1), 0, "the neighbour's pixel is left out");
    }
    #[test]
    fn a_turned_button_stands_upright() {
        // a 1 wide, 3 tall strip read bottom to top becomes 3 wide left to right
        let p = picture(1, 3, &[(0, 0), (0, 1), (0, 2)]);
        let t = p.turned_right();
        assert_eq!((t.width, t.height), (3, 1));
        // the strip's bottom pixel (y 2) comes first
        assert_eq!(t.rgba[1], 2);
        assert_eq!(t.rgba[2 * 4 + 1], 0);
    }
    #[test]
    fn a_glow_surrounds_the_shape() {
        let p = picture(4, 4, &[(1, 1), (2, 1), (1, 2), (2, 2)]);
        let g = p.glow(4);
        assert_eq!((g.width, g.height), (12, 12));
        assert!(g.alpha(6, 6) > 200, "brightest at the shape");
        assert!(g.alpha(1, 6) < g.alpha(4, 6), "fading out");
        assert_eq!(g.alpha(0, 0), 0);
    }
}
