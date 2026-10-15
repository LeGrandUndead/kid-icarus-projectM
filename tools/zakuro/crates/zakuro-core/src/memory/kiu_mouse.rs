//! Opt-in KIU USA camera experiment. HID and visible touch stay bounded.
//! Discover the active camera through native input consumers, then replace its
//! current-minus-previous movement immediately before the land calculation.
use super::Memory;
const INPUT_XY: u32 = 0x00EF_D4D4;
const SIGNATURE: [(u32, u32); 4] = [
    (0x0035_349C, 0x00EF_9ED0),
    (0x004D_BA08, 0xE590_7004),
    (0x007D_ABB8, 0xEC90_0A02),
    (0x007D_ABC0, 0xEE30_0A61),
];
#[derive(Default)]
pub(super) struct RelativeMouse {
    verified: Option<bool>,
    enabled: bool,
    pending: [f32; 2],
    frames: u8,
    ring: Option<u32>,
    camera: Option<u32>,
    published: u64,
    /// Times the land camera consumer ran (state byte 0x1c == 1), moving or
    /// not: the game is running land gameplay with the mouse captured.
    land_published: u64,
}
fn within(address: u32, base: u32, len: u32) -> bool {
    address.wrapping_sub(base) < len
}
impl Memory {
    pub fn queue_kiu_mouse(&mut self, delta: Option<[f32; 2]>) {
        let Some(delta) = delta.filter(|d| d.iter().all(|v| v.is_finite())) else {
            self.kiu_mouse.enabled = false;
            self.kiu_mouse.pending = [0.0; 2];
            self.kiu_mouse.frames = 0;
            self.kiu_mouse.ring = None;
            self.kiu_mouse.camera = None;
            return;
        };
        if self.kiu_mouse.verified.is_none() {
            let matches = SIGNATURE.iter().all(|&(address, expected)| {
                let mut bytes = [0; 4];
                self.read_bytes(address, &mut bytes);
                u32::from_le_bytes(bytes) == expected
            }) && self.is_readable(INPUT_XY, 8);
            self.kiu_mouse.verified = Some(matches);
            if !matches {
                log::warn!("KIU relative camera refused: executable/layout signature differs");
            }
        }
        if self.kiu_mouse.verified != Some(true) {
            return;
        }
        self.kiu_mouse.enabled = true;
        // Do not store seconds of motion while paused or outside land gameplay.
        if self.kiu_mouse.frames >= 3 {
            self.kiu_mouse.pending = [0.0; 2];
            self.kiu_mouse.frames = 0;
        }
        self.kiu_mouse.frames += 1;
        for (pending, motion) in self.kiu_mouse.pending.iter_mut().zip(delta) {
            *pending = (*pending + motion).clamp(-32767.0, 32767.0);
        }
        self.guard_cpu_reads(INPUT_XY, 8);
        if let Some(ring) = self.kiu_mouse.ring {
            self.guard_cpu_reads(ring + 4, 0x140);
        }
        if let Some(camera) = self.kiu_mouse.camera {
            self.guard_cpu_reads(camera + 0x38, 0x14);
        }
    }
    pub fn kiu_mouse_publications(&self) -> u64 {
        self.kiu_mouse.published
    }
    /// Counts frames in which the game's land camera consumed mouse input.
    /// It only advances during land gameplay, so a recent change means the
    /// player is on foot (powers can be selected) rather than in flight.
    pub fn kiu_land_publications(&self) -> u64 {
        self.kiu_mouse.land_published
    }
    pub(crate) fn kiu_native_read(&mut self, address: u32, pc: u32, r0: u32, r1: u32) {
        if !self.kiu_mouse.enabled {
            return;
        }
        if within(address, INPUT_XY, 8) {
            let ring = match pc {
                0x0061_0524 => Some(r0),
                0x0060_A094 => r0.checked_add(0x1c0),
                _ => None,
            };
            if let Some(ring) = ring.filter(|&p| p >= 0x0800_0000 && self.is_readable(p, 0x14c)) {
                if self.kiu_mouse.ring != Some(ring) {
                    self.kiu_mouse.camera = None;
                }
                self.kiu_mouse.ring = Some(ring);
                self.guard_cpu_reads(ring + 4, 0x140);
            }
        }
        if pc == 0x004D_B974
            && self.kiu_mouse.ring == Some(r1)
            && within(address, r1 + 4, 0x140)
            && r0 >= 0x0800_0000
            && self.is_readable(r0, 0x60)
        {
            self.kiu_mouse.camera = Some(r0);
            self.guard_cpu_reads(r0 + 0x38, 0x14);
        }
        let Some(camera) = self.kiu_mouse.camera else {
            return;
        };
        // Observed land sensitivity branch, after its final call. Producer
        // reads and other sensitivity branches do not modify the game state.
        static EXPERIMENTAL_AIR: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        let air = *EXPERIMENTAL_AIR.get_or_init(|| std::env::var_os("KIU_EXPERIMENTAL_AIR").is_some());
        if (pc != 0x007D_AB54 && !(air && pc == 0x007D_AB1C)) || !within(address, camera + 0x38, 0x14) || self.kiu_mouse.frames == 0
        {
            return;
        }
        let mut state = [0u8; 0x4c];
        self.read_bytes(camera, &mut state);
        let air_consumer = air && pc == 0x007D_AB1C && state[0x1c] == 0;
        // The land consumer runs every land frame, with or without motion.
        if pc == 0x007D_AB54 && state[0x1c] == 1 {
            self.kiu_mouse.land_published += 1;
        }
        if !(pc == 0x007D_AB54 && state[0x1c] == 1 || air_consumer) || state[0x34] == 0 {
            return;
        }
        let number = |offset| f32::from_le_bytes(state[offset..offset + 4].try_into().unwrap());
        let current = [number(0x3c), number(0x40)];
        if !current.iter().all(|v| v.is_finite()) {
            return;
        }
        let [dx, dy] = self.kiu_mouse.pending;
        self.write_bytes(camera + 0x44, &(current[0] - dx).to_le_bytes());
        self.write_bytes(camera + 0x48, &(current[1] - dy).to_le_bytes());
        let duration = self.kiu_mouse.frames as f32 / 60.0;
        self.write_bytes(camera + 0x38, &duration.to_le_bytes());
        // Otherwise the native history reuses an older nonzero swipe at rest.
        self.write_bytes(camera + 0x20, &[0; 0x14]);
        self.kiu_mouse.pending = [0.0; 2];
        self.kiu_mouse.frames = 0;
        self.kiu_mouse.published += 1;
    }
    pub(crate) fn rearm_kiu_mouse(&mut self, address: u32) {
        if !self.kiu_mouse.enabled {
            return;
        }
        if within(address, INPUT_XY, 8) {
            self.guard_cpu_reads(INPUT_XY, 8);
        }
        if let Some(ring) = self.kiu_mouse.ring {
            if within(address, ring + 4, 0x140) {
                self.guard_cpu_reads(ring + 4, 0x140);
            }
        }
        if let Some(camera) = self.kiu_mouse.camera {
            if within(address, camera + 0x38, 0x14) {
                self.guard_cpu_reads(camera + 0x38, 0x14);
            }
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn air_consumer_is_opt_in_and_zero_motion_ignores_touch_position() {
        let enabled = std::env::var_os("KIU_EXPERIMENTAL_AIR").is_some();
        let mut m = memory();
        m.write_bytes(CAMERA + 0x1c, &[0]);
        m.queue_kiu_mouse(Some([4.0, -2.0]));
        discover(&mut m);
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB1C, 0, 0);
        assert_eq!(m.kiu_mouse_publications(), u64::from(enabled));
        if !enabled { return; }
        assert_eq!(value(&mut m, 0x44), 315.0);
        assert_eq!(value(&mut m, 0x48), 122.0);
        for x in [0.0f32, 319.0, 160.0] {
            m.write_bytes(CAMERA + 0x3c, &x.to_le_bytes());
            m.queue_kiu_mouse(Some([0.0, 0.0]));
            m.kiu_native_read(CAMERA + 0x38, 0x007D_AB1C, 0, 0);
            assert_eq!(value(&mut m, 0x44), x);
            assert_eq!(value(&mut m, 0x48), 120.0);
        }
        let publications = m.kiu_mouse_publications();
        m.write_bytes(CAMERA + 0x1c, &[1]);
        m.queue_kiu_mouse(Some([4.0, 0.0]));
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB1C, 0, 0);
        assert_eq!(m.kiu_mouse_publications(), publications);
        m.write_bytes(CAMERA + 0x1c, &[0]);
        m.write_bytes(CAMERA + 0x34, &[0]);
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB1C, 0, 0);
        assert_eq!(m.kiu_mouse_publications(), publications);
    }
    use crate::memory::{MemoryRegion, MemoryState, Permission};
    const RING: u32 = 0x0800_1000;
    const CAMERA: u32 = 0x0800_2000;
    fn memory() -> Memory {
        let mut m = Memory::new(false, 0x0400_0000);
        for page in [
            0x0035_3000,
            0x004D_B000,
            0x007D_A000,
            0x00EF_D000,
            RING,
            CAMERA,
        ] {
            let block = m.phys.allocate(MemoryRegion::Application, 0x1000).unwrap();
            m.map(
                page,
                block.addr,
                0x1000,
                Permission::RW,
                MemoryState::Private,
            );
        }
        for (address, value) in SIGNATURE {
            m.write_bytes(address, &value.to_le_bytes());
        }
        m.write_bytes(CAMERA + 0x1c, &[1]);
        m.write_bytes(CAMERA + 0x34, &[1]);
        m.write_bytes(CAMERA + 0x3c, &319f32.to_le_bytes());
        m.write_bytes(CAMERA + 0x40, &120f32.to_le_bytes());
        m
    }
    fn discover(m: &mut Memory) {
        m.kiu_native_read(INPUT_XY, 0x0060_A094, RING - 0x1c0, 0);
        m.kiu_native_read(RING + 8, 0x004D_B974, CAMERA, RING);
    }
    fn value(m: &mut Memory, offset: u32) -> f32 {
        let mut b = [0; 4];
        m.read_bytes(CAMERA + offset, &mut b);
        f32::from_le_bytes(b)
    }
    #[test]
    fn changes_camera_difference_only_at_land_consumer() {
        let mut m = memory();
        m.queue_kiu_mouse(Some([8.0, -3.0]));
        discover(&mut m);
        m.kiu_native_read(CAMERA + 0x38, 0x004D_B974, CAMERA, RING);
        assert_eq!(m.kiu_mouse_publications(), 0);
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB54, 0, 0);
        assert_eq!(value(&mut m, 0x3c), 319.0);
        assert_eq!(value(&mut m, 0x40), 120.0);
        assert_eq!(value(&mut m, 0x44), 311.0);
        assert_eq!(value(&mut m, 0x48), 123.0);
        assert_eq!(m.kiu_mouse_publications(), 1);
        m.queue_kiu_mouse(Some([0.0, 0.0]));
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB54, 0, 0);
        assert_eq!(value(&mut m, 0x44), 319.0);
    }
    #[test]
    fn capture_loss_unknown_image_and_other_mode_do_not_patch() {
        let mut m = memory();
        m.write_bytes(SIGNATURE[0].0, &[0; 4]);
        m.queue_kiu_mouse(Some([12.0, 4.0]));
        discover(&mut m);
        assert!(!m.kiu_mouse.enabled);
        let mut m = memory();
        m.queue_kiu_mouse(Some([12.0, 4.0]));
        discover(&mut m);
        m.write_bytes(CAMERA + 0x1c, &[0]);
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB54, 0, 0);
        assert_eq!(m.kiu_mouse_publications(), 0);
        m.write_bytes(CAMERA + 0x1c, &[1]);
        m.queue_kiu_mouse(None);
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB54, 0, 0);
        assert_eq!(m.kiu_mouse_publications(), 0);
    }
    #[test]
    fn retains_fractional_motion_but_bounds_inactive_backlog() {
        let mut m = memory();
        m.queue_kiu_mouse(Some([0.25, 0.0]));
        discover(&mut m);
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB54, 0, 0);
        assert_eq!(value(&mut m, 0x44), 318.75);
        for _ in 0..600 {
            m.queue_kiu_mouse(Some([4.0, 0.0]));
        }
        m.kiu_native_read(CAMERA + 0x38, 0x007D_AB54, 0, 0);
        assert!(319.0 - value(&mut m, 0x44) <= 12.0);
        assert!(value(&mut m, 0x38) <= 3.0 / 60.0);
    }
}
