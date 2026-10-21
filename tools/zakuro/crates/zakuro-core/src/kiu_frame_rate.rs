//! Kid Icarus: Uprising at 60 frames a second (experimental).
//!
//! The game renders every second vertical blank: its display scheduler
//! (singleton at 0x00D63824) waits `interval` = 2 blanks per frame and hands
//! the update the 60 Hz ticks that passed. Its update step (the float 2.0 at
//! 0x00828E30, read by 0x00828D68 and turned into per-system deltas by
//! 0x00607A4C) is in 60ths of a second.
//!
//! The 60 fps mode, found by the October 18-19 research (see
//! doc/60FPS_ANALYSIS.md):
//! - interval 1, with the scheduler's even-tick carry cleared, so a frame is
//!   drawn every blank;
//! - the update step 1.0 instead of 2.0, so movement, flight paths and
//!   everything else the game scales by its step keeps normal speed;
//! - elapsed ticks reported as 1.
//!
//! Systems that count frames instead of using the step run at double speed;
//! `kiu_frame_locks` corrects the known ones. Turning the mode off puts the
//! original values back at the next frame. Saves are not involved.
//!
//! The setting is kept in `%APPDATA%/zakuro/kiu-60fps.txt` ("1" or "0");
//! `KIU_60FPS=1`/`0` overrides it for one run.
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::OnceLock;

use zakuro_cpu::Bus;

use crate::System;

const MANAGER: u32 = 0x00D63824;
const STEP: u32 = 0x00828E30;
const STEP_ORIGINAL: u32 = 0x4000_0000; // 2.0
const STEP_SIXTY: u32 = 0x3F80_0000; // 1.0

fn path() -> Option<std::path::PathBuf> {
    std::env::var_os("APPDATA").map(|p| std::path::PathBuf::from(p).join("zakuro/kiu-60fps.txt"))
}

fn setting() -> &'static AtomicBool {
    static VALUE: OnceLock<AtomicBool> = OnceLock::new();
    VALUE.get_or_init(|| {
        let saved = path().and_then(|p| std::fs::read_to_string(p).ok());
        let on = std::env::var("KIU_60FPS").ok().or(saved).map(|v| v.trim() == "1").unwrap_or(false);
        AtomicBool::new(on)
    })
}

/// whether the 60 fps mode is wanted.
pub fn enabled() -> bool {
    setting().load(Ordering::Relaxed)
}

/// turns the 60 fps mode on or off, from the next game frame, and keeps the
/// choice for the next start.
pub fn set_enabled(on: bool) {
    setting().store(on, Ordering::Relaxed);
    if let Some(path) = path() {
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Err(error) = std::fs::write(path, if on { "1\n" } else { "0\n" }) {
            log::warn!("Could not save the 60 fps setting: {error}");
        }
    }
}

/// fast-forward runs the game at its original 30 fps, half the drawing per
/// game step, whatever the 60 fps setting says.
static FAST_FORWARD: AtomicBool = AtomicBool::new(false);

/// while on, the 60 fps mode is set aside; the setting itself is kept.
pub fn set_fast_forward(on: bool) {
    FAST_FORWARD.store(on, Ordering::Relaxed);
}

/// what the game is doing now: 0 not known yet, 30 or 60.
static ACTIVE: AtomicU8 = AtomicU8::new(0);

/// the rate the game is drawing at, once the scheduler exists.
pub fn active_rate() -> u8 {
    ACTIVE.load(Ordering::Relaxed)
}

/// whether this is the USA release the addresses belong to.
fn signatures(system: &mut System) -> bool {
    system.kernel.program_id == 0x0004000000030100
        && system.memory.read32(0x00991164) == 0xEF000028
        && system.memory.read32(0x009911CC) == 0xEF000028
        && system.memory.read32(0x009911DC) == MANAGER
        && system.memory.read32(0x00828E10) == 0xED9F0A06
}

/// called at the two GetSystemTick calls around the scheduler's callback,
/// `pre` for the one before (0x00991164), else the one after (0x009911CC).
pub(crate) fn at_scheduler(system: &mut System, pre: bool) {
    static CHECKED: OnceLock<()> = OnceLock::new();
    static VALID: AtomicBool = AtomicBool::new(false);
    if CHECKED.get().is_none() {
        let valid = signatures(system);
        VALID.store(valid, Ordering::Relaxed);
        let _ = CHECKED.set(());
        if !valid {
            log::warn!("60 fps mode: not the expected executable, left off");
        }
    }
    if !VALID.load(Ordering::Relaxed) {
        return;
    }
    let manager = system.memory.read32(MANAGER);
    if manager & 3 != 0 || !(0x0010_0000..0x2000_0000).contains(&manager) {
        return;
    }
    if pre && system.cpu.regs[5] != manager {
        return;
    }
    let step = system.memory.read32(STEP);
    if !matches!(step, STEP_ORIGINAL | STEP_SIXTY) {
        return;
    }
    let interval = system.memory.read32(manager + 0x54);
    let want = enabled() && !FAST_FORWARD.load(Ordering::Relaxed);

    if !pre {
        // the display wait rounds elapsed ticks back to its even count:
        // keep the one tick the update is stepping by
        if want && interval == 1 && step == STEP_SIXTY {
            system.memory.write32(manager + 0xB0, 1);
        }
        return;
    }

    if want {
        if interval == 2 {
            system.memory.write32(manager + 0x54, 1);
            log::info!("60 fps mode on");
        } else if interval != 1 {
            return;
        }
        system.memory.write32(manager + 0xA8, 0);
        system.memory.write32(manager + 0xAC, 0);
        if step != STEP_SIXTY && !system.memory.write32_privileged(STEP, STEP_SIXTY) {
            // without the step change the game would run at double speed
            system.memory.write32(manager + 0x54, 2);
            return;
        }
        system.memory.write32(manager + 0xB0, 1);
        ACTIVE.store(60, Ordering::Relaxed);
    } else {
        if step == STEP_SIXTY {
            let _ = system.memory.write32_privileged(STEP, STEP_ORIGINAL);
            if interval == 1 {
                system.memory.write32(manager + 0x54, 2);
            }
            log::info!("60 fps mode off");
        }
        ACTIVE.store(30, Ordering::Relaxed);
    }
}
