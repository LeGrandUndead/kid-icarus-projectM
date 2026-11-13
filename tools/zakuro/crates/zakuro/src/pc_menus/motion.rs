//! How a redrawn menu's buttons move: each hangs at its home on the vine
//! on a spring, all sway together in a slow breeze, a button can be dragged
//! (it pushes the others out of its way, never goes further than `TETHER`
//! from home) and springs back when let go.

/// How far a button may be pulled from home, in units.
pub const TETHER: f32 = 22.0;
/// Margin inside a button's rectangle that does not collide (its art's
/// transparent corners), in units.
const SHRINK: f32 = 3.0;
const SPRING: f32 = 70.0;
const DAMPING: f32 = 9.0;
const DRAG_SPRING: f32 = 500.0;
const DRAG_DAMPING: f32 = 40.0;

pub type V = [f32; 2];

#[derive(Default)]
pub struct Motion {
    offset: Vec<V>,
    velocity: Vec<V>,
    /// the button held, and where on it (units from its corner)
    held: Option<(usize, V)>,
    time: f32,
}

/// A slow breeze through the vine: one wave (5 s) running down it, mostly
/// sideways, each button a little after the one above, so they move as one.
fn sway(i: usize, t: f32) -> V {
    let a = std::f32::consts::TAU * t / 5.0 - i as f32 * 0.6;
    [a.sin() * 0.7, (a + 1.3).sin() * 0.3]
}

fn shift(r: [f32; 4], o: V) -> [f32; 4] { [r[0] + o[0], r[1] + o[1], r[2] + o[0], r[3] + o[1]] }

impl Motion {
    pub fn new(count: usize) -> Self {
        Self { offset: vec![[0.0; 2]; count], velocity: vec![[0.0; 2]; count], held: None, time: 0.0 }
    }

    /// Button `i`'s rectangle now, from its home.
    pub fn rect(&self, i: usize, home: [f32; 4]) -> [f32; 4] { shift(home, self.offset.get(i).copied().unwrap_or_default()) }

    pub fn held(&self) -> Option<usize> { self.held.map(|h| h.0) }

    /// Grabs button `i` at `pointer` (units).
    pub fn grab(&mut self, i: usize, pointer: V, home: [f32; 4]) {
        let r = self.rect(i, home);
        self.held = Some((i, [pointer[0] - r[0], pointer[1] - r[1]]));
    }

    pub fn release(&mut self) { self.held = None; }

    /// Advances `dt` seconds; `homes` are the buttons' home rectangles,
    /// `pointer` where the pointer is (units).
    pub fn step(&mut self, dt: f32, homes: &[[f32; 4]], pointer: Option<V>) {
        if self.offset.len() != homes.len() { *self = Self::new(homes.len()); }
        let dt = dt.clamp(0.0, 1.0 / 20.0);
        // small steps keep the springs steady at any frame rate
        let steps = (dt / (1.0 / 240.0)).ceil().max(1.0) as usize;
        let h = dt / steps as f32;
        for _ in 0..steps {
            self.time += h;
            for i in 0..homes.len() {
                let (target, k, c) = match (self.held, pointer) {
                    (Some((held, grip)), Some(p)) if held == i =>
                        ([p[0] - grip[0] - homes[i][0], p[1] - grip[1] - homes[i][1]], DRAG_SPRING, DRAG_DAMPING),
                    _ => (sway(i, self.time), SPRING, DAMPING),
                };
                for a in 0..2 {
                    let force = -k * (self.offset[i][a] - target[a]) - c * self.velocity[i][a];
                    self.velocity[i][a] += force * h;
                    self.offset[i][a] += self.velocity[i][a] * h;
                }
            }
            self.collide(homes);
            self.tether();
        }
    }

    /// Overlapping buttons push each other apart; the held one does not
    /// give way.
    fn collide(&mut self, homes: &[[f32; 4]]) {
        let held = self.held();
        for i in 0..homes.len() {
            for j in i + 1..homes.len() {
                let (a, b) = (self.rect(i, homes[i]), self.rect(j, homes[j]));
                let (a, b) = ([a[0] + SHRINK, a[1] + SHRINK, a[2] - SHRINK, a[3] - SHRINK], [b[0] + SHRINK, b[1] + SHRINK, b[2] - SHRINK, b[3] - SHRINK]);
                let ox = a[2].min(b[2]) - a[0].max(b[0]);
                let oy = a[3].min(b[3]) - a[1].max(b[1]);
                if ox <= 0.0 || oy <= 0.0 { continue; }
                // apart along the shallower overlap, away from each other
                let (axis, depth) = if ox < oy { (0, ox) } else { (1, oy) };
                let sign = if (a[axis] + a[axis + 2]) < (b[axis] + b[axis + 2]) { -1.0 } else { 1.0 };
                let (wi, wj) = match held { Some(x) if x == i => (0.0, 1.0), Some(x) if x == j => (1.0, 0.0), _ => (0.5, 0.5) };
                self.offset[i][axis] += sign * depth * wi;
                self.offset[j][axis] -= sign * depth * wj;
                // and they bounce a little
                let push = sign * depth * 6.0;
                self.velocity[i][axis] += push * wi;
                self.velocity[j][axis] -= push * wj;
            }
        }
    }

    fn tether(&mut self) {
        for (o, v) in self.offset.iter_mut().zip(&mut self.velocity) {
            let d = (o[0] * o[0] + o[1] * o[1]).sqrt();
            if d > TETHER {
                let k = TETHER / d;
                *o = [o[0] * k, o[1] * k];
                // what pulled outward is spent
                let n = [o[0] / TETHER, o[1] / TETHER];
                let out = v[0] * n[0] + v[1] * n[1];
                if out > 0.0 { *v = [v[0] - out * n[0], v[1] - out * n[1]]; }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const HOMES: [[f32; 4]; 2] = [[20.0, 20.0, 80.0, 50.0], [20.0, 60.0, 80.0, 90.0]];

    #[test]
    fn a_button_left_alone_stays_near_home() {
        let mut m = Motion::new(2);
        for _ in 0..600 { m.step(1.0 / 60.0, &HOMES, None); }
        for i in 0..2 {
            let r = m.rect(i, HOMES[i]);
            assert!((r[0] - HOMES[i][0]).abs() < 2.0 && (r[1] - HOMES[i][1]).abs() < 2.0, "sways a little");
        }
    }

    #[test]
    fn a_dragged_button_follows_within_its_tether_and_comes_back() {
        let mut m = Motion::new(2);
        m.grab(0, [30.0, 30.0], HOMES[0]);
        for _ in 0..120 { m.step(1.0 / 60.0, &HOMES, Some([45.0, 30.0])); }
        let r = m.rect(0, HOMES[0]);
        assert!((r[0] - 35.0).abs() < 1.5, "follows the pointer: {r:?}");
        for _ in 0..120 { m.step(1.0 / 60.0, &HOMES, Some([300.0, 30.0])); }
        let r = m.rect(0, HOMES[0]);
        let d = ((r[0] - HOMES[0][0]).powi(2) + (r[1] - HOMES[0][1]).powi(2)).sqrt();
        assert!(d <= TETHER + 0.01, "bound to its home: {d}");
        m.release();
        for _ in 0..300 { m.step(1.0 / 60.0, &HOMES, None); }
        let r = m.rect(0, HOMES[0]);
        assert!((r[0] - HOMES[0][0]).abs() < 2.0, "springs back");
    }

    #[test]
    fn a_dragged_button_pushes_the_other() {
        let mut m = Motion::new(2);
        m.grab(0, [30.0, 30.0], HOMES[0]);
        for _ in 0..60 { m.step(1.0 / 60.0, &HOMES, Some([30.0, 50.0])); }
        let (a, b) = (m.rect(0, HOMES[0]), m.rect(1, HOMES[1]));
        assert!(b[1] > HOMES[1][1] + 3.0, "pushed down: {b:?}");
        assert!(a[3] - SHRINK <= b[1] + SHRINK + 0.5, "they do not overlap");
    }

    // a ring of four, as a menu's navigation map
}
