//! Which frame of a character to show when: its entrance, then its hold
//! (looping, or back and forth with soft turns), never skipping a frame.

use super::manifest::Character;

/// Distance along a sweep of `len` frames, `t` frames in: at most one frame
/// per frame, easing in over the first `e` frames of distance and out over
/// the last (each ease takes 2e frames of time).
pub(super) fn sweep(t: f32, len: f32, e: f32) -> f32 {
    let e = e.min(len / 2.0).max(0.5);
    let total = len + 2.0 * e;
    let t = t.clamp(0.0, total);
    if t < 2.0 * e { t * t / (4.0 * e) }
    else if t > total - 2.0 * e { let u = total - t; len - u * u / (4.0 * e) }
    else { e + (t - 2.0 * e) }
}

/// Which character frame a mode shows `t` frames after it was selected.
pub(super) fn idle_index(c: &Character, t: f32) -> i32 {
    let mut t = t.max(0.0);
    if let Some(intro) = &c.intro {
        let len = (intro.range[1] - intro.range[0]) as f32;
        if t < len { return intro.range[0] + t as i32; }
        t -= len;
    }
    let [a, b] = c.idle.range;
    let len = (b - a).max(1) as f32;
    match c.idle.play.as_deref() {
        Some("pingpong") => {
            // back and forth: one rendered frame per frame (none skipped),
            // with a soft stop and start at each turn (a moving hold)
            let e = 12.0;
            let total = len + 2.0 * e;
            let p = t % (2.0 * total);
            let d = if p < total { sweep(p, len, e) } else { len - sweep(p - total, len, e) };
            a + (d.floor() as i32).clamp(0, b - a)
        }
        _ => a + (t as i32).rem_euclid(len as i32 + 1),
    }
}
