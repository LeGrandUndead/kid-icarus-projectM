//! Timing helpers, in frames at 60 a second: easing, keyed tracks, shake,
//! a small deterministic random generator and the handheld camera drift.

pub(super) fn clamp01(t: f32) -> f32 { t.clamp(0.0, 1.0) }
#[derive(Clone, Copy)]
pub(super) enum Ease { Out, In, InOut, OutBack }
pub(super) fn ease(e: Ease, t: f32) -> f32 {
    match e {
        Ease::Out => 1.0 - (1.0 - t).powi(4),
        Ease::In => t * t * t,
        Ease::InOut => if t < 0.5 { 4.0 * t * t * t } else { 1.0 - (-2.0 * t + 2.0).powi(3) / 2.0 },
        Ease::OutBack => { let (s, t) = (1.7, t - 1.0); t * t * ((s + 1.0) * t + s) + 1.0 }
    }
}
/// A value keyed at frames; each key says how it is reached.
pub(super) fn track(f: f32, keys: &[(f32, f32, Ease)]) -> f32 {
    if f <= keys[0].0 { return keys[0].1; }
    for w in keys.windows(2) {
        let (a, b) = (w[0], w[1]);
        if f <= b.0 { return a.1 + (b.1 - a.1) * ease(b.2, clamp01((f - a.0) / (b.0 - a.0).max(1e-6))); }
    }
    keys[keys.len() - 1].1
}
pub(super) fn k2(f0: f32, v0: f32, f1: f32, v1: f32, e: Ease, f: f32) -> f32 { track(f, &[(f0, v0, Ease::Out), (f1, v1, e)]) }
/// A decaying shake, alternating sides each frame.
pub(super) fn shake(f: f32, start: f32, frames: f32, amp: f32, seed: u32) -> f32 {
    let t = (f - start).floor();
    if t < 0.0 || t >= frames { return 0.0; }
    let a = amp * (1.0 - t / frames).powi(2);
    let s = if (t as i32) % 2 == 1 { -1.0 } else { 1.0 };
    a * s * (0.6 + 0.4 * hash01(seed * 1000 + t as u32))
}
pub(super) fn hash01(n: u32) -> f32 {
    let mut x = n.wrapping_mul(0x9E37_79B9) ^ 0x85EB_CA6B;
    x ^= x >> 15; x = x.wrapping_mul(0x2C1B_3C6D); x ^= x >> 12; x = x.wrapping_mul(0x297A_2D39); x ^= x >> 15;
    (x as f32) / (u32::MAX as f32)
}
/// A small deterministic random sequence.
pub(super) struct Rng(pub(super) u32);
impl Rng {
    pub(super) fn f(&mut self, a: f32, b: f32) -> f32 { self.0 = self.0.wrapping_add(1); a + (b - a) * hash01(self.0) }
}
/// The slow handheld camera.
pub(super) fn cam(v: f32) -> [f32; 2] {
    use std::f32::consts::TAU;
    [18.0 * (TAU * v / 240.0).sin() + 7.0 * (TAU * v / 97.0 + 1.0).sin(),
     9.0 * (TAU * v / 300.0 + 2.0).sin() + 4.0 * (TAU * v / 131.0).sin()]
}
