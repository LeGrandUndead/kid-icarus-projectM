//! Drawing in the design's 1920x1080 pixels: textured and coloured
//! polygons, clipped by half-planes, gathered into egui meshes and mapped to
//! the window (cover-scaled).

use egui::{Color32, Mesh, Pos2, Rect, TextureHandle};

use super::anim::clamp01;
use super::frames::Shown;
use super::{H, W};

/// A point and its texture coordinate.
#[derive(Clone, Copy)]
pub(super) struct Vx { pub(super) p: [f32; 2], pub(super) uv: [f32; 2], pub(super) c: Color32 }
/// The half-plane a*x + b*y + c >= 0.
#[derive(Clone, Copy)]
pub(super) struct Half { pub(super) a: f32, pub(super) b: f32, pub(super) c: f32 }
impl Half {
    pub(super) fn at(&self, p: [f32; 2]) -> f32 { self.a * p[0] + self.b * p[1] + self.c }
    /// Right of the slanted line through x0 (at the top, y = -40) leaning `lean` to the bottom (y = H + 40).
    pub(super) fn right_of(x0: f32, lean: f32) -> Half { let k = lean / (H + 80.0); Half { a: 1.0, b: k, c: 40.0 * k - x0 } }
}
pub(super) fn lerp_vx(a: Vx, b: Vx, t: f32) -> Vx {
    let l = |x: f32, y: f32| x + (y - x) * t;
    let lc = |x: u8, y: u8| (x as f32 + (y as f32 - x as f32) * t).round() as u8;
    Vx { p: [l(a.p[0], b.p[0]), l(a.p[1], b.p[1])], uv: [l(a.uv[0], b.uv[0]), l(a.uv[1], b.uv[1])],
         c: Color32::from_rgba_premultiplied(lc(a.c.r(), b.c.r()), lc(a.c.g(), b.c.g()), lc(a.c.b(), b.c.b()), lc(a.c.a(), b.c.a())) }
}
/// Sutherland-Hodgman: the part of a convex polygon inside `h`.
pub(super) fn clip(poly: &[Vx], h: Half) -> Vec<Vx> {
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
pub(super) struct Canvas { pub(super) meshes: Vec<Mesh>, pub(super) clips: Vec<Half> }
impl Canvas {
    /// A convex polygon, clipped by the current clips.
    pub(super) fn poly(&mut self, tex: egui::TextureId, pts: &[Vx]) {
        let mut poly = pts.to_vec();
        for h in &self.clips { poly = clip(&poly, *h); if poly.len() < 3 { return; } }
        let mut m = Mesh::with_texture(tex);
        for v in &poly { m.vertices.push(egui::epaint::Vertex { pos: Pos2::new(v.p[0], v.p[1]), uv: Pos2::new(v.uv[0], v.uv[1]), color: v.c }); }
        for i in 1..poly.len() as u32 - 1 { m.add_triangle(0, i, i + 1); }
        self.meshes.push(m);
    }
    /// A picture over the rectangle (x, y, w, h), turned `deg` about `pivot`, tinted.
    pub(super) fn image(&mut self, tex: &TextureHandle, r: [f32; 4], deg: f32, pivot: [f32; 2], tint: Color32) {
        self.image_part(tex.id(), [1.0, 1.0], r, deg, pivot, tint);
    }
    /// The top-left `uv` part of a texture over the rectangle.
    pub(super) fn image_part(&mut self, tex: egui::TextureId, uv: [f32; 2], r: [f32; 4], deg: f32, pivot: [f32; 2], tint: Color32) {
        let (s, c) = deg.to_radians().sin_cos();
        let rot = |x: f32, y: f32| [pivot[0] + (x - pivot[0]) * c - (y - pivot[1]) * s, pivot[1] + (x - pivot[0]) * s + (y - pivot[1]) * c];
        let [x, y, w, h] = r;
        let pts = [Vx { p: rot(x, y), uv: [0.0, 0.0], c: tint }, Vx { p: rot(x + w, y), uv: [uv[0], 0.0], c: tint },
                   Vx { p: rot(x + w, y + h), uv: uv, c: tint }, Vx { p: rot(x, y + h), uv: [0.0, uv[1]], c: tint }];
        self.poly(tex, &pts);
    }
    /// A character frame over the rectangle.
    pub(super) fn frame(&mut self, f: &Shown, r: [f32; 4], tint: Color32) { self.image_part(f.tex.id(), f.uv, r, 0.0, [0.0, 0.0], tint); }
    pub(super) fn image_at(&mut self, tex: &TextureHandle, at: [f32; 2], tint: Color32) {
        let s = tex.size();
        self.image(tex, [at[0], at[1], s[0] as f32, s[1] as f32], 0.0, at, tint);
    }
    /// An untextured convex polygon, one colour per corner.
    pub(super) fn fill(&mut self, pts: &[([f32; 2], Color32)]) {
        let v: Vec<Vx> = pts.iter().map(|&(p, c)| Vx { p, uv: [0.0, 0.0], c }).collect();
        let mut v = v; for x in &mut v { x.uv = [egui::epaint::WHITE_UV.x, egui::epaint::WHITE_UV.y]; }
        self.poly(egui::TextureId::default(), &v);
    }
    /// Draws everything, mapped from design pixels to the window, at `opacity`.
    pub(super) fn emit(self, painter: &egui::Painter, map: &Map, opacity: f32) {
        let k = clamp01(opacity);
        for mut m in self.meshes {
            for v in &mut m.vertices {
                v.pos = map.pos([v.pos.x, v.pos.y]);
                if k < 1.0 { v.color = v.color.gamma_multiply(k); }
            }
            painter.add(egui::Shape::mesh(m));
        }
    }
}
/// Design pixels to window points: the 1920x1080 design covers the window.
pub(super) struct Map { pub(super) origin: Pos2, pub(super) scale: f32 }
impl Map {
    pub(super) fn new(window: Rect) -> Map {
        let scale = (window.width() / W).max(window.height() / H);
        let origin = Pos2::new(window.center().x - W * scale / 2.0, window.center().y - H * scale / 2.0);
        Map { origin, scale }
    }
    pub(super) fn pos(&self, p: [f32; 2]) -> Pos2 { Pos2::new(self.origin.x + p[0] * self.scale, self.origin.y + p[1] * self.scale) }
    pub(super) fn design(&self, p: Pos2) -> [f32; 2] { [(p.x - self.origin.x) / self.scale, (p.y - self.origin.y) / self.scale] }
}

pub(super) fn faded(a: f32) -> Color32 { let k = (clamp01(a) * 255.0) as u8; Color32::from_rgba_premultiplied(k, k, k, k) }
/// Tint for an added light (its texture holds the colour with alpha 0).
pub(super) fn light(a: f32) -> Color32 { let k = (clamp01(a) * 255.0) as u8; Color32::from_rgba_premultiplied(k, k, k, 0) }
pub(super) fn rgba(c: [u8; 3], a: f32) -> Color32 {
    let k = clamp01(a);
    Color32::from_rgba_premultiplied((c[0] as f32 * k) as u8, (c[1] as f32 * k) as u8, (c[2] as f32 * k) as u8, (k * 255.0) as u8)
}
pub(super) fn additive(c: [u8; 3], a: f32) -> Color32 {
    let k = clamp01(a);
    Color32::from_rgba_premultiplied((c[0] as f32 * k) as u8, (c[1] as f32 * k) as u8, (c[2] as f32 * k) as u8, 0)
}
pub(super) fn mix(a: [u8; 3], b: [u8; 3], k: f32) -> [u8; 3] {
    [0, 1, 2].map(|i| (a[i] as f32 + (b[i] as f32 - a[i] as f32) * k) as u8)
}
