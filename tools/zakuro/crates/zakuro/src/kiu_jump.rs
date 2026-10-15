//! KIU Space jump (doc/PC_INTERFACE_DESIGN_DIRECTION.md, variant 2): Space
//! uses the equipped Sky Jump without the player selecting it.
//!
//! The game keeps the land Power Palette in memory (doc/POWER_STATE.md):
//! count, selected slot, then one `(slot << 16) | power id` entry per slot.
//! A Space jump only reads that list. It then presses the D-pad like a
//! player: steps to Sky Jump, the "use" press, and steps back to the power
//! that was selected. Writing the selection into memory does not work: the
//! palette's cursor lives elsewhere (October 15 test: the bubble showed Sky
//! Jump but another power was used). The game still decides whether a jump
//! is possible (on the ground, uses left, not in a scripted scene).
use zakuro_core::memory::Memory;
use zakuro_core::services::hid::PadState;

/// Power id of Sky Jump (October 15 snapshot: slot 0 showed Sky Jump).
const SKY_JUMP: u32 = 0x00;
/// Frames each press is held and released: the game does not read the
/// buttons on every land frame (same timing as the wheel in input.rs).
const HOLD: usize = 3;
const GAP: usize = 4;
/// Frames between the use press and stepping back, so the jump has started.
const SETTLE: usize = 12;
const MAX_SLOTS: u32 = 12;
const STRUCT_SIZE: usize = 0x80;
/// Where the live palette is: FCRAM (October 15: 0x14F3C968). The main
/// heap holds a look-alike copy (0x08048158, probably the saved equipment),
/// which the game does not read for the palette and must never be changed.
const REGIONS: [(u32, u32); 1] = [(0x1400_0000, 0x1C00_0000)];

#[derive(Default)]
pub struct SpaceJump {
    /// Address of the palette structure found earlier (re-checked each use).
    palette: Option<u32>,
    requested: bool,
    /// Buttons for the coming frames, front first: steps to Sky Jump, the
    /// use press, a pause while the jump starts, and the steps back.
    plan: std::collections::VecDeque<PadState>,
}

/// One validated palette: the selected slot and each slot's power id.
#[derive(Debug, PartialEq)]
pub struct Palette {
    pub selected: u32,
    pub ids: Vec<u32>,
}

fn word(bytes: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes(bytes[offset..offset + 4].try_into().unwrap())
}

/// Checks that `bytes` (at least STRUCT_SIZE long) hold a palette.
pub fn parse(bytes: &[u8]) -> Option<Palette> {
    let count = word(bytes, 0);
    let selected = word(bytes, 4);
    // At least two powers: one-entry look-alikes are common in memory, and
    // with a single power equipped no selection change is needed anyway.
    if !(2..=MAX_SLOTS).contains(&count) || selected >= count || word(bytes, 0x70) != count {
        return None;
    }
    let mut ids = Vec::new();
    for slot in 0..count {
        let entry = word(bytes, 0x0C + 8 * slot as usize);
        if entry >> 16 != slot || entry & 0xFFFF >= 0x100 {
            return None;
        }
        if ids.contains(&(entry & 0xFFFF)) {
            return None; // a power is equipped once
        }
        ids.push(entry & 0xFFFF);
    }
    // unused slots are empty
    if (count..MAX_SLOTS).any(|slot| word(bytes, 0x0C + 8 * slot as usize) != 0 || word(bytes, 0x10 + 8 * slot as usize) != 0) {
        return None;
    }
    // display order: every slot exactly once
    let mut seen = [false; MAX_SLOTS as usize];
    for &order in &bytes[0x74..0x74 + count as usize] {
        if order as u32 >= count || std::mem::replace(&mut seen[order as usize], true) {
            return None;
        }
    }
    Some(Palette { selected, ids })
}

fn read(memory: &mut Memory, address: u32) -> Option<Palette> {
    if !memory.is_readable(address, STRUCT_SIZE as u32) {
        return None;
    }
    let mut bytes = [0u8; STRUCT_SIZE];
    memory.read_bytes(address, &mut bytes);
    parse(&bytes)
}

/// Searches the heap once; afterwards the cached address is re-checked.
fn find(memory: &mut Memory) -> Option<u32> {
    let mut page = vec![0u8; 0x1000 + STRUCT_SIZE];
    for (start, end) in REGIONS {
        let mut address = start;
        while address < end {
            if memory.is_readable(address, 0x1000 + STRUCT_SIZE as u32) {
                memory.read_bytes(address, &mut page);
                for offset in (0..0x1000).step_by(4) {
                    // cheap filter first: small count, selection below it
                    let count = word(&page, offset);
                    if (2..=MAX_SLOTS).contains(&count) && word(&page, offset + 4) < count {
                        if parse(&page[offset..offset + STRUCT_SIZE]).is_some() {
                            return Some(address + offset as u32);
                        }
                    }
                }
            }
            address += 0x1000;
        }
    }
    None
}

/// Shortest D-pad route from one slot to another on the wrapping palette:
/// (steps, true = right/next).
pub fn route(from: u32, to: u32, count: u32) -> (u32, bool) {
    let right = (to + count - from) % count;
    let left = (from + count - to) % count;
    if right <= left { (right, true) } else { (left, false) }
}

/// The frame-by-frame buttons for one Space jump.
pub fn plan(selected: u32, jump: u32, count: u32) -> Vec<PadState> {
    let mut frames = Vec::new();
    let mut press = |button: PadState, frames: &mut Vec<PadState>| {
        frames.extend(std::iter::repeat(button).take(HOLD));
        frames.extend(std::iter::repeat(PadState::empty()).take(GAP));
    };
    let (steps, right) = route(selected, jump, count);
    let (there, back) = if right { (PadState::RIGHT, PadState::LEFT) } else { (PadState::LEFT, PadState::RIGHT) };
    for _ in 0..steps { press(there, &mut frames); }
    press(PadState::DOWN, &mut frames);
    frames.extend(std::iter::repeat(PadState::empty()).take(SETTLE));
    for _ in 0..steps { press(back, &mut frames); }
    frames
}

impl SpaceJump {
    pub fn request(&mut self) {
        if self.plan.is_empty() {
            self.requested = true;
        }
    }

    /// True while a Space jump is pressing the D-pad (other power input waits).
    pub fn active(&self) -> bool { !self.plan.is_empty() }

    /// Runs once per frame before the game does. Returns the D-pad buttons
    /// for this frame (only meaningful while active()).
    pub fn step(&mut self, memory: &mut Memory, on_land: bool) -> PadState {
        if let Some(buttons) = self.plan.pop_front() {
            return buttons;
        }
        if !std::mem::take(&mut self.requested) || !on_land {
            return PadState::empty();
        }
        let address = match self.palette.filter(|&a| read(memory, a).is_some()) {
            Some(address) => address,
            None => match find(memory) {
                Some(address) => {
                    log::info!("KIU Space jump: power palette at {address:#010x}");
                    self.palette = Some(address);
                    address
                }
                None => {
                    log::info!("KIU Space jump: no power palette found");
                    return PadState::empty();
                }
            },
        };
        let Some(palette) = read(memory, address) else { return PadState::empty() };
        let Some(slot) = palette.ids.iter().position(|&id| id == SKY_JUMP) else {
            return PadState::empty(); // Jump not equipped: Space does nothing
        };
        self.plan = plan(palette.selected, slot as u32, palette.ids.len() as u32).into();
        self.plan.pop_front().unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The October 15 Practice Range palette, selection at slot 1.
    fn sample() -> Vec<u8> {
        let mut b = vec![0u8; STRUCT_SIZE];
        let put = |b: &mut Vec<u8>, o: usize, v: u32| b[o..o + 4].copy_from_slice(&v.to_le_bytes());
        put(&mut b, 0, 7);
        put(&mut b, 4, 1);
        put(&mut b, 8, 0x0069_1304);
        let entries = [(0x00, 0x0004_070a), (0x06, 0x0022_0302), (0x0F, 0x0029_2a02), (0x11, 0x0095_2f03),
            (0x32, 0x00a6_0501), (0x33, 0x00a4_1605), (0x3B, 0)];
        for (slot, (id, info)) in entries.iter().enumerate() {
            put(&mut b, 0x0C + 8 * slot, ((slot as u32) << 16) | id);
            put(&mut b, 0x10 + 8 * slot, *info);
        }
        put(&mut b, 0x70, 7);
        b[0x74..0x7B].copy_from_slice(&[0, 1, 2, 3, 4, 5, 6]);
        b
    }

    #[test]
    fn parses_the_recorded_palette() {
        let p = parse(&sample()).unwrap();
        assert_eq!(p.selected, 1);
        assert_eq!(p.ids, [0x00, 0x06, 0x0F, 0x11, 0x32, 0x33, 0x3B]);
    }

    #[test]
    fn routes_take_the_short_way_round() {
        assert_eq!(route(1, 0, 7), (1, false));
        assert_eq!(route(0, 0, 7), (0, true));
        assert_eq!(route(6, 0, 7), (1, true), "wraps past the end");
        assert_eq!(route(2, 5, 7), (3, true));
        assert_eq!(route(5, 1, 7), (3, true));
    }

    #[test]
    fn plan_steps_to_jump_uses_it_and_steps_back() {
        let p = plan(1, 0, 7);
        let presses: Vec<PadState> = p.iter().copied().filter(|b| !b.is_empty()).collect();
        assert_eq!(presses, [[PadState::LEFT; 3], [PadState::DOWN; 3], [PadState::RIGHT; 3]].concat());
        assert_eq!(p.len(), 7 + 7 + 12 + 7);
        // already on Sky Jump: just the use press
        assert_eq!(plan(0, 0, 7).iter().filter(|b| !b.is_empty()).count(), 3);
    }

    #[test]
    fn rejects_lookalikes() {
        let mut b = sample();
        b[4] = 7; // selection outside the list
        assert!(parse(&b).is_none());
        let mut b = sample();
        b[0x0C + 8 * 2 + 2] = 5; // slot numbers out of sequence
        assert!(parse(&b).is_none());
        let mut b = sample();
        b[0x75] = 0; // display order repeats a slot
        assert!(parse(&b).is_none());
        let mut b = sample();
        b[0x70] = 6; // trailing count disagrees
        assert!(parse(&b).is_none());
        let mut b = sample();
        b[0x0C + 8 * 3] = 0x06; // the same power twice
        assert!(parse(&b).is_none());
        let mut b = sample();
        b[0x0C + 8 * 8] = 1; // something in an unused slot
        assert!(parse(&b).is_none());
        // a one-entry list (very common pattern in memory) is not a palette
        let mut one = vec![0u8; STRUCT_SIZE];
        one[0] = 1;
        one[0x70] = 1;
        assert!(parse(&one).is_none());
    }
}
