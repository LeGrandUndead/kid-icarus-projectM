//! The vine that binds a redrawn menu's buttons together (native_menu):
//! a black silhouette tendril in the style of the game's own menu art,
//! entering from the window's edge, passing by each button (wherever the
//! button is now, so it bends when one is dragged), with laurel leaves and
//! curls, ending in a spiral.
//!
//! Pure geometry: triangles in window units (the window is 240 units tall),
//! each vertex with a coverage (1 inside, 0 on the soft outer edge) so the
//! drawing is smooth without multisampling.

use std::f32::consts::PI;

pub type P = [f32; 2];

/// Triangles, three vertices each: position and coverage.
#[derive(Default)]
pub struct Shape {
    pub vertices: Vec<(P, f32)>,
}

impl Shape {
    fn tri(&mut self, a: (P, f32), b: (P, f32), c: (P, f32)) { self.vertices.extend([a, b, c]); }

    /// A stroke along `path` from width `w0` to `w1`, with a soft edge of
    /// `soft` units on each side.
    pub fn ribbon(&mut self, path: &[P], w0: f32, w1: f32, soft: f32) {
        if path.len() < 2 { return; }
        let mut length = vec![0.0f32];
        for w in path.windows(2) { length.push(length.last().unwrap() + dist(w[0], w[1])); }
        let total = length.last().copied().unwrap_or(1.0).max(1e-4);
        // across each point: outer left, inner left, inner right, outer right
        let rows: Vec<[(P, f32); 4]> = path.iter().enumerate().map(|(i, &p)| {
            let (a, b) = (path[i.saturating_sub(1)], path[(i + 1).min(path.len() - 1)]);
            let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
            let d = (dx * dx + dy * dy).sqrt().max(1e-6);
            let n = [-dy / d, dx / d];
            let half = (w0 + (w1 - w0) * length[i] / total) * 0.5;
            let at = |k: f32| [p[0] + n[0] * k, p[1] + n[1] * k];
            [(at(half + soft), 0.0), (at(half), 1.0), (at(-half), 1.0), (at(-half - soft), 0.0)]
        }).collect();
        for r in rows.windows(2) {
            for k in 0..3 {
                self.tri(r[0][k], r[0][k + 1], r[1][k]);
                self.tri(r[0][k + 1], r[1][k + 1], r[1][k]);
            }
        }
    }

    /// A pointed leaf from `at` along `angle`.
    pub fn leaf(&mut self, at: P, angle: f32, length: f32, width: f32, soft: f32) {
        const N: usize = 12;
        let (c, s) = (angle.cos(), angle.sin());
        let place = |x: f32, y: f32| [at[0] + x * c - y * s, at[1] + x * s + y * c];
        let half = |t: f32| (PI * t.powf(0.8)).sin().max(0.0).powf(1.2) * width * 0.5;
        // the midrib, with both halves fanned from it
        for side in [1.0f32, -1.0] {
            for k in 0..N {
                let (t0, t1) = (k as f32 / N as f32, (k + 1) as f32 / N as f32);
                let (m0, m1) = ((place(t0 * length, 0.0), 1.0), (place(t1 * length, 0.0), 1.0));
                let (e0, e1) = ((place(t0 * length, side * half(t0)), 1.0), (place(t1 * length, side * half(t1)), 1.0));
                let (o0, o1) = ((place(t0 * length, side * (half(t0) + soft)), 0.0), (place(t1 * length, side * (half(t1) + soft)), 0.0));
                self.tri(m0, e0, m1);
                self.tri(e0, e1, m1);
                self.tri(e0, o0, e1);
                self.tri(o0, o1, e1);
            }
        }
    }
}

pub fn dist(a: P, b: P) -> f32 { ((a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2)).sqrt() }

/// A smooth curve through `points` (Catmull-Rom), `steps` points a span.
pub fn curve(points: &[P], steps: usize) -> Vec<P> {
    if points.len() < 2 { return points.to_vec(); }
    let mut out = Vec::with_capacity((points.len() - 1) * steps + 1);
    let at = |i: isize| points[i.clamp(0, points.len() as isize - 1) as usize];
    for i in 0..points.len() as isize - 1 {
        let (p0, p1, p2, p3) = (at(i - 1), at(i), at(i + 1), at(i + 2));
        for k in 0..steps {
            let t = k as f32 / steps as f32;
            let (t2, t3) = (t * t, t * t * t);
            out.push(std::array::from_fn(|j| 0.5 * (2.0 * p1[j] + (-p0[j] + p2[j]) * t
                + (2.0 * p0[j] - 5.0 * p1[j] + 4.0 * p2[j] - p3[j]) * t2 + (-p0[j] + 3.0 * p1[j] - 3.0 * p2[j] + p3[j]) * t3)));
        }
    }
    out.push(*points.last().unwrap());
    out
}

/// A spiral winding in from radius `r` around `centre`, `turns` times,
/// starting at angle `start`, clockwise when `sign` is 1.
pub fn spiral(centre: P, r: f32, turns: f32, start: f32, sign: f32) -> Vec<P> {
    const N: usize = 40;
    (0..=N).map(|k| {
        let t = k as f32 / N as f32;
        let a = start + sign * t * turns * 2.0 * PI;
        let radius = r * (1.0 - t * 0.85);
        [centre[0] + radius * a.cos(), centre[1] + radius * a.sin()]
    }).collect()
}

/// The vine for buttons at these places (left, top, right, bottom in
/// units, top to bottom). `soft`: the soft edge, in units.
pub fn vine(buttons: &[[f32; 4]], soft: f32) -> Shape {
    let mut shape = Shape::default();
    let Some(last) = buttons.last() else { return shape };
    // whole inside the window: from a curl just above the first button to a
    // curl under the last, clear of the heading above and the ground band below
    let first = buttons[0];
    let top = [first[0] - 4.0, first[1] - 7.0];
    let mut spine: Vec<P> = vec![top];
    for (i, b) in buttons.iter().enumerate() {
        let x = b[0] - 1.0 + if i % 2 == 1 { 3.0 } else { -2.0 };
        spine.push([x, (b[1] + b[3]) * 0.5]);
    }
    spine.push([last[0] + 1.0, last[3] + 2.0]);
    spine.push([last[0] + 8.0, last[3] + 5.0]);
    let path = curve(&spine, 16);
    // fine at both ends, fullest a third of the way down
    let k = path.len() / 3;
    shape.ribbon(&path[..=k], 2.4, 6.0, soft);
    shape.ribbon(&path[k..], 6.0, 2.4, soft);
    shape.ribbon(&spiral([top[0], top[1] - 4.5], 4.5, 1.25, PI / 2.0, 1.0), 2.4, 0.8, soft);
    let end = *path.last().unwrap();
    shape.ribbon(&spiral([end[0] + 1.0, end[1] - 5.0], 5.0, 1.25, PI / 2.0, -1.0), 2.4, 0.8, soft);
    // laurel leaves in pairs along the spine, pointing down it
    let mut run = 0.0;
    for w in path.windows(2) {
        run += dist(w[0], w[1]);
        if run > 11.0 {
            run = 0.0;
            let angle = (w[1][1] - w[0][1]).atan2(w[1][0] - w[0][0]);
            for side in [1.0f32, -1.0] { shape.leaf(w[0], angle + side * 0.75, 9.0, 3.8, soft); }
        }
    }
    // a curl hanging between each pair of buttons, on the window's side
    for pair in buttons.windows(2) {
        let (x, y) = (pair[0][0].min(pair[1][0]) - 1.0, (pair[0][3] + pair[1][1]) * 0.5);
        let mut tendril = vec![[x, y]];
        tendril.extend(spiral([x - 4.5, y + 0.5], 4.2, 1.1, 0.0, 1.0));
        shape.ribbon(&tendril, 2.4, 0.7, soft);
    }
    shape
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn a_curve_passes_through_its_points() {
        let pts = [[0.0, 0.0], [10.0, 5.0], [20.0, 0.0]];
        let c = curve(&pts, 8);
        assert_eq!(c.len(), 17);
        assert_eq!(c[0], pts[0]);
        assert!(dist(c[8], pts[1]) < 1e-4);
        assert_eq!(*c.last().unwrap(), pts[2]);
    }
    #[test]
    fn a_ribbon_tapers_and_has_a_soft_edge() {
        let mut s = Shape::default();
        s.ribbon(&[[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]], 4.0, 2.0, 0.5);
        assert_eq!(s.vertices.len() % 3, 0);
        let (inside, edge): (Vec<_>, Vec<_>) = s.vertices.iter().partition(|v| v.1 == 1.0);
        let width = |x: f32, set: &[&(P, f32)]| set.iter().filter(|v| (v.0[0] - x).abs() < 1e-3).map(|v| v.0[1].abs()).fold(0.0, f32::max);
        assert!((width(0.0, &inside) - 2.0).abs() < 1e-3 && (width(20.0, &inside) - 1.0).abs() < 1e-3);
        assert!((width(0.0, &edge) - 2.5).abs() < 1e-3);
    }
    #[test]
    fn the_vine_follows_its_buttons() {
        let buttons = [[22.0, 22.0, 85.0, 51.0], [28.0, 61.0, 90.0, 91.0]];
        let v = vine(&buttons, 0.4);
        assert!(!v.vertices.is_empty() && v.vertices.len() % 3 == 0);
        assert!(v.vertices.iter().all(|(p, c)| p[0].is_finite() && p[1].is_finite() && (0.0..=1.0).contains(c)));
        // it stays at the buttons' left, and reaches below the last one
        let max_y = v.vertices.iter().map(|v| v.0[1]).fold(f32::MIN, f32::max);
        assert!(max_y > 91.0);
        let moved = vine(&[[22.0, 22.0, 85.0, 51.0], [48.0, 71.0, 110.0, 101.0]], 0.4);
        let max_moved = moved.vertices.iter().map(|v| v.0[1]).fold(f32::MIN, f32::max);
        assert!(max_moved > max_y + 5.0, "it bends to a moved button");
    }
}
