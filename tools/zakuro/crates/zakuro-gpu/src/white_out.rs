//! Kid Icarus's white-out: the game fades to white by drawing a whole-screen
//! quad of constant white over the frame, `src * 1 + dst * src_alpha`, the
//! constant's alpha going from 1 (nothing) to 0 (all white). A render
//! capture in chapter 9 (October 28) found it held at alpha 0 frame after
//! frame while the screen stayed white: the game itself asks for the white,
//! the renderer draws what it is told. This counts the frames that draw it
//! fully white, so the runtime can tell a white-out that lasts.

use std::sync::atomic::{AtomicU32, Ordering};

static FULL: AtomicU32 = AtomicU32::new(0);
/// draws of any kind, to tell a frame the game did not draw at all (at
/// 30 fps every other one) from one without the white
static DRAWS: AtomicU32 = AtomicU32::new(0);

const REG_TEV0_SOURCES: usize = 0x0C0;
const REG_TEV0_CONSTANT: usize = 0x0C3;
const REG_BLEND: usize = 0x101;

/// Each draw: the full-white fade layer, constant white with alpha 0,
/// blended over the frame by its alpha.
pub(crate) fn draw(registers: &[u32]) {
    DRAWS.fetch_add(1, Ordering::Relaxed);
    if registers[REG_TEV0_SOURCES] == 0x0EEE_0EEE
        && registers[REG_TEV0_CONSTANT] == 0x00FF_FFFF
        && registers[REG_BLEND] == 0x1061_0000
    {
        FULL.fetch_add(1, Ordering::Relaxed);
    }
}

/// Since the last call: None when nothing was drawn, else whether the
/// full-white fade layer was.
pub fn take_full() -> Option<bool> {
    let full = FULL.swap(0, Ordering::Relaxed) > 0;
    (DRAWS.swap(0, Ordering::Relaxed) > 0).then_some(full)
}
