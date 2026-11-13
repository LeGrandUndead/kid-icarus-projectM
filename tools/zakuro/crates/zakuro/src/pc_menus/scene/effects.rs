//! Effects drawn procedurally: speed lines, the ink gutter between scenes,
//! wind streaks, the click ring, the vignette.

use super::anim::{ease, Ease, Rng};
use super::canvas::{additive, rgba, Canvas};
use super::{GOLD, GUTTER, H, INK, W};

/// Speed lines fanning out from `c` (thin wedges).
pub(super) fn speed_lines(cv: &mut Canvas, c: [f32; 2], seed: u32, strength: f32, col: [u8; 3], n: usize) {
    let mut rnd = Rng(seed.wrapping_mul(2654435761));
    for _ in 0..n {
        let a = rnd.f(0.0, std::f32::consts::TAU); let r0 = rnd.f(300.0, 460.0); let r1 = r0 + rnd.f(500.0, 1400.0); let w = rnd.f(0.003, 0.010);
        let alpha = rnd.f(60.0, 150.0) / 255.0 * strength;
        let colr = rgba(col, alpha);
        cv.fill(&[([c[0] + a.cos() * r0, c[1] + a.sin() * r0], colr), ([c[0] + (a - w).cos() * r1, c[1] + (a - w).sin() * r1], colr),
                  ([c[0] + (a + w).cos() * r1, c[1] + (a + w).sin() * r1], colr)]);
    }
}

/// The ink gutter between two scenes of the column: a ragged black band
/// from `y` down, GUTTER tall, with a dry edge.
pub(super) fn ink_gutter(cv: &mut Canvas, y: f32, seed: u32) {
    let mut rnd = Rng(seed.wrapping_mul(40503) ^ 0x5bd1e995);
    let ink = rgba(INK, 1.0);
    let cols = 24;
    let (mut top, mut bottom) = (Vec::new(), Vec::new());
    for k in 0..=cols {
        let x = -400.0 + k as f32 * (W + 800.0) / cols as f32;
        top.push([x, y + rnd.f(-10.0, 8.0)]); bottom.push([x, y + GUTTER + rnd.f(-8.0, 12.0)]);
    }
    for k in 0..cols { cv.fill(&[(top[k], ink), (top[k + 1], ink), (bottom[k + 1], ink), (bottom[k], ink)]); }
    for _ in 0..18 {
        let x = rnd.f(-200.0, W + 200.0); let side = if rnd.f(0.0, 1.0) < 0.5 { -1.0 } else { 1.0 };
        let y0 = if side < 0.0 { y } else { y + GUTTER };
        let (a, b) = ([x, y0], [x + rnd.f(40.0, 220.0), y0 + side * rnd.f(4.0, 16.0)]);
        let w = rnd.f(2.0, 7.0) / 2.0; let col = rgba(INK, rnd.f(0.5, 1.0));
        cv.fill(&[([a[0], a[1] - w], col), ([b[0], b[1] - w], col), ([b[0], b[1] + w], col), ([a[0], a[1] + w], col)]);
    }
}

/// Wind streaking past Pit: long thin lines of light sliding down to the left.
pub(super) fn wind_streaks(cv: &mut Canvas, v: f32, dy: f32) {
    let mut rnd = Rng(0x2545F491);
    for _ in 0..16 {
        let ph = rnd.f(0.0, 1.0); let y0 = rnd.f(-100.0, H); let len = rnd.f(180.0, 520.0); let sp = rnd.f(22.0, 40.0); let w = rnd.f(1.0, 2.6);
        let s = ((v * sp / 2600.0) + ph) % 1.0;
        let x = W + 300.0 - s * 2600.0; let y = y0 + s * 900.0 + dy;
        let (ux, uy) = (-0.94f32, 0.34f32);
        let a = [x, y]; let b = [x - ux * len, y - uy * len];
        let fade = (1.0 - (2.0 * s - 1.0).abs()) * 0.35;
        let (c0, c1) = (additive([255, 250, 245], fade), additive([255, 250, 245], 0.0));
        cv.fill(&[([a[0], a[1] - w], c0), ([b[0], b[1] - w], c1), ([b[0], b[1] + w], c1), ([a[0], a[1] + w], c0)]);
    }
}

/// A gold ring opening from the pressed button.
pub(super) fn ring(cv: &mut Canvas, p: [f32; 2], t: f32) {
    let r = 60.0 + 340.0 * ease(Ease::Out, t); let w = 10.0 * (1.0 - t) + 2.0; let a = 1.0 - t;
    let col = rgba(GOLD, a);
    let n = 48;
    for i in 0..n {
        let (a0, a1) = (i as f32 / n as f32 * std::f32::consts::TAU, (i + 1) as f32 / n as f32 * std::f32::consts::TAU);
        let pt = |a: f32, rr: f32| [p[0] + a.cos() * rr, p[1] + a.sin() * rr * 0.55];
        cv.fill(&[(pt(a0, r - w / 2.0), col), (pt(a1, r - w / 2.0), col), (pt(a1, r + w / 2.0), col), (pt(a0, r + w / 2.0), col)]);
    }
}

/// Darker corners, very gently.
pub(super) fn vignette(cv: &mut Canvas) {
    let (clear, dark) = (rgba(INK, 0.0), rgba(INK, 0.16));
    cv.fill(&[([0.0, 0.0], dark), ([W, 0.0], dark), ([W, 140.0], clear), ([0.0, 140.0], clear)]);
    cv.fill(&[([0.0, H - 140.0], clear), ([W, H - 140.0], clear), ([W, H], dark), ([0.0, H], dark)]);
    cv.fill(&[([0.0, 0.0], dark), ([220.0, 0.0], clear), ([220.0, H], clear), ([0.0, H], dark)]);
    cv.fill(&[([W - 220.0, 0.0], clear), ([W, 0.0], dark), ([W, H], dark), ([W - 220.0, H], clear)]);
}
