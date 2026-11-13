//! The game's own cursor, walked to where the pointer points: the game shows
//! its selected choice's art on its upper screen, the menu reads which
//! choice that is (`Nav::observe`), and presses the D-pad along the game's
//! own navigation map (`Graph`) until the cursor is there, out of sight, so
//! the game's state, sounds and keyboard or controller selection agree with
//! what the PC shows.

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
