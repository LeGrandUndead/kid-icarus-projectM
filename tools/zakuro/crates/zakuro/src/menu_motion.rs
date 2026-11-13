//! How a redrawn menu's buttons move (native_menu), and how pointing at one
//! selects it in the game.
//!
//! Motion: each button hangs at its home on the vine on a spring. It sways
//! gently on its own, can be grabbed and dragged, pushes the others out of
//! its way, and springs back when let go, never further than `TETHER` from
//! home.
//!
//! Selection: the game keeps its own cursor, and shows the selected
//! choice's art on its upper screen. The menu reads which choice that is
//! (`observe`), and when the pointer rests on another one, presses the
//! D-pad along the game's own navigation map (`Graph`) until the game's
//! cursor is there, so the heading, art, caption and sounds all follow the
//! pointer, and keyboard or controller selection lights the same button.

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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Dir { Up, Down, Left, Right }

/// The game's navigation map: from each choice, where Up, Down, Left and
/// Right go (indices into the same list).
pub struct Graph { pub edges: &'static [[usize; 4]] }

impl Graph {
    /// The first press on the shortest way from `from` to `to`, passing only
    /// through choices for which `shown` holds (a hidden 3DS-only choice
    /// would leave the cursor where the pointer cannot follow it).
    pub fn first_step(&self, from: usize, to: usize, shown: impl Fn(usize) -> bool) -> Option<Dir> {
        if from == to || from >= self.edges.len() || to >= self.edges.len() { return None; }
        let mut first: Vec<Option<Dir>> = vec![None; self.edges.len()];
        let mut seen = vec![false; self.edges.len()];
        let mut queue = std::collections::VecDeque::from([from]);
        seen[from] = true;
        const DIRS: [Dir; 4] = [Dir::Up, Dir::Down, Dir::Left, Dir::Right];
        while let Some(n) = queue.pop_front() {
            for (k, &next) in self.edges[n].iter().enumerate() {
                if next >= self.edges.len() || seen[next] || !shown(next) { continue; }
                seen[next] = true;
                first[next] = first[n].or(Some(DIRS[k]));
                if next == to { return first[next]; }
                queue.push_back(next);
            }
        }
        None
    }
}

/// Frames a D-pad press is held, then frames to wait for the game's cursor.
const PRESS: u32 = 3;
const SETTLE: u32 = 10;
/// Presses tried for one target before giving up until the pointer moves.
const TRIES: u32 = 8;

/// Frames without any selection art before the cursor counts as unknown.
const UNSEEN: u32 = 20;

/// Moves the game's cursor to the choice the pointer rests on.
#[derive(Default)]
pub struct Nav {
    unseen: u32,
    /// the game's selected choice (index into the navigation map)
    pub current: Option<usize>,
    target: Option<usize>,
    pressing: Option<(Dir, u32)>,
    settle: u32,
    tries: u32,
}

impl Nav {
    /// What the game's upper screen shows selected this frame: `selected`
    /// when it is one choice; `any` whether it showed the art of any choice
    /// (two cross-fading still says the cursor is among them). A while with
    /// none means the cursor is on a choice the menu does not show.
    pub fn observe(&mut self, selected: Option<usize>, any: bool) {
        if selected.is_some() { self.current = selected; }
        self.unseen = if any { 0 } else { self.unseen + 1 };
        if self.unseen > UNSEEN { self.current = None; }
    }

    /// Where the cursor is going: the pointer's choice while the game's
    /// cursor walks there, otherwise where the cursor is.
    pub fn heading(&self) -> Option<usize> { self.target.filter(|_| self.tries < TRIES).or(self.current) }

    /// The choice the pointer has just moved onto (None: leave the game's
    /// cursor be). The walk carries on to it even if the pointer leaves.
    pub fn want(&mut self, target: Option<usize>) {
        if target.is_some() && target != self.target {
            self.target = target;
            self.tries = 0;
        }
    }

    /// Stops walking (a click went to the game's real button).
    pub fn stop(&mut self) { self.target = None; self.pressing = None; self.settle = 0; }

    /// The D-pad press to give the game this frame.
    pub fn pad(&mut self, graph: &Graph, shown: impl Fn(usize) -> bool) -> Option<Dir> {
        if let Some((dir, left)) = self.pressing {
            self.pressing = if left > 1 { Some((dir, left - 1)) } else { self.settle = SETTLE; None };
            return Some(dir);
        }
        if self.settle > 0 { self.settle -= 1; return None; }
        let (Some(from), Some(to)) = (self.current, self.target) else { return None };
        // there: the walk is done, keys and the pad are free again
        if from == to { self.target = None; return None; }
        if self.tries >= TRIES { return None; }
        let dir = graph.first_step(from, to, shown)?;
        self.tries += 1;
        self.pressing = Some((dir, PRESS - 1));
        Some(dir)
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
    const RING: Graph = Graph { edges: &[[3, 1, 0, 0], [0, 2, 1, 1], [1, 3, 2, 2], [2, 0, 3, 3]] };

    #[test]
    fn the_shortest_way_through_the_game_map() {
        assert_eq!(RING.first_step(0, 1, |_| true), Some(Dir::Down));
        assert_eq!(RING.first_step(0, 3, |_| true), Some(Dir::Up));
        assert_eq!(RING.first_step(2, 2, |_| true), None);
        assert_eq!(RING.first_step(0, 2, |n| n != 1), Some(Dir::Up), "around a hidden choice");
        assert_eq!(RING.first_step(0, 2, |n| n == 0 || n == 2), None, "no way without it");
    }

    #[test]
    fn the_cursor_is_walked_to_the_pointer_and_left_there() {
        let mut nav = Nav::default();
        nav.observe(Some(0), true);
        nav.want(Some(1));
        let presses: Vec<_> = (0..PRESS).map(|_| nav.pad(&RING, |_| true)).collect();
        assert!(presses.iter().all(|p| *p == Some(Dir::Down)));
        for _ in 0..SETTLE { assert_eq!(nav.pad(&RING, |_| true), None); }
        nav.observe(Some(1), true);
        assert_eq!(nav.pad(&RING, |_| true), None, "arrived");
        // a cursor on a choice the menu does not show is not known
        let mut lost = Nav::default();
        lost.observe(Some(3), true);
        for _ in 0..UNSEEN { lost.observe(None, false); }
        assert_eq!(lost.current, Some(3));
        lost.observe(None, false);
        assert_eq!(lost.current, None);
        // a cursor that does not move is not pushed forever
        nav.want(Some(0));
        let pressed = (0..200).filter(|_| nav.pad(&RING, |_| true).is_some()).count();
        assert_eq!(pressed as u32, TRIES * PRESS);
    }
}
