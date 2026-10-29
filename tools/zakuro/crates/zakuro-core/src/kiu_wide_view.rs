//! Kid Icarus: Uprising: the PC wide view, made by the game's own camera.
//!
//! The 16:9 picture and the "Gameplay view" zoom used to be made only in
//! the renderer, by rescaling the projection the game's shaders receive
//! (`zakuro-gpu/src/raster.rs`, `kiu_wide_shader`). The game was not told,
//! so it still culled, aimed and placed markers for its original 5:3 view:
//! enemies popped in at the new edges and the mouse aim stayed inside the
//! original frame (doc/CULLING_AND_POP_IN.md).
//!
//! With the override `tools/recomp/overrides/kiu-wide-view.c` in the game
//! library, the game's camera functions (projection matrix `0x00B4F89C`,
//! culling frustum `0x00B4F948`, lens cache `0x0090DC70`) widen the top
//! screen's lens themselves. This writes, once a frame, the factors they
//! use to spare bytes past the end of the game's data:
//!
//! ```text
//! 0x00F35F00  "KIUW" when the factors are valid
//! 0x00F35F04  tan(fov/2) factor: 1/scale of the Gameplay view, 1 outside gameplay
//! 0x00F35F08  aspect factor: 16/15 for the 16:9 picture
//! 0x00F35F0C  count the library raises when it widens a projection
//! ```
//!
//! When that count moves, the library is doing it and the renderer stops
//! widening the picture (`kiu_ui::camera::set_game_view`); a library built
//! without the override never moves it, and the renderer goes on as before.
//!
//! The zoom is for gameplay, as the renderer's was: it follows the game's
//! world shaders (`kiu_ui::camera::take_world_seen`), and lets go half a
//! second after they stop, so a loading frame does not make the view jump.

use zakuro_cpu::Bus;

use crate::memory::Memory;

const VIEW: u32 = 0x00F3_5F00;
const MAGIC: u32 = u32::from_le_bytes(*b"KIUW");
const LENS: u32 = VIEW + 4;
const ASPECT: u32 = VIEW + 8;
const COUNT: u32 = VIEW + 0xC;
/// 5:3 to 16:9.
const WIDE: f32 = 16.0 / 15.0;
/// frames the zoom stays after the world shaders were last seen.
const ZOOM_GRACE: u32 = 30;

#[derive(Default)]
pub struct WideView {
    checked: bool,
    enabled: bool,
    count: u32,
    active: bool,
    since_world: u32,
}

impl WideView {
    /// after each frame: the factors for the next.
    pub fn frame(&mut self, memory: &mut Memory) {
        if !self.checked {
            self.checked = true;
            // the same switch as the renderer's 16:9 view (launch.py sets
            // it unless --original-aspect)
            self.enabled = std::env::var_os("KIU_EXPERIMENTAL_WIDE").is_some()
                && memory.is_readable(VIEW, 0x10);
        }
        if !self.enabled {
            return;
        }
        let count = memory.read32(COUNT);
        if count != self.count {
            self.count = count;
            if !self.active {
                self.active = true;
                zakuro_gpu::kiu_ui::camera::set_game_view(true);
                log::info!("wide view: the game's camera widens itself (kiu-wide-view.c); the renderer no longer rescales it");
            }
        }
        self.since_world = if zakuro_gpu::kiu_ui::camera::take_world_seen() { 0 } else { self.since_world.saturating_add(1) };
        let zoom = self.since_world <= ZOOM_GRACE;
        let lens = factors(zakuro_gpu::kiu_ui::camera::scale(), zoom).0;
        memory.write32(LENS, lens.to_bits());
        memory.write32(ASPECT, WIDE.to_bits());
        memory.write32(VIEW, MAGIC);
    }
}

/// the lens and aspect factors for a Gameplay view scale (1 original, 0.75
/// widest) while in gameplay or not.
fn factors(scale: f32, gameplay: bool) -> (f32, f32) {
    let lens = if gameplay && scale.is_finite() && scale > 0.0 { (1.0 / scale).clamp(1.0, 4.0 / 3.0) } else { 1.0 };
    (lens, WIDE)
}

#[cfg(test)]
mod tests {
    use super::factors;

    #[test]
    fn the_zoom_is_for_gameplay_and_the_aspect_always() {
        let (lens, wide) = factors(0.7518797, true);
        assert!((lens - 1.33).abs() < 0.001, "{lens}");
        assert!((wide - 16.0 / 15.0).abs() < 1e-6);
        assert_eq!(factors(0.7518797, false).0, 1.0);
        assert_eq!(factors(1.0, true).0, 1.0);
        assert_eq!(factors(f32::NAN, true).0, 1.0);
    }

    #[test]
    fn the_magic_spells_kiuw_as_the_override_reads_it() {
        assert_eq!(super::MAGIC, 0x5755494B);
    }
}
