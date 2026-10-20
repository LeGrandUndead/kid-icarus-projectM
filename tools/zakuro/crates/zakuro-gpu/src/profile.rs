//! inclusive host time spent in the renderer's main phases, for the usage
//! report: always on, a clock read at the start and end of each phase.

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

#[derive(Clone, Copy)]
pub enum Phase {
    CommandList,
    Draw,
    ShaderPrepare,
    DrawTextures,
    DrawHardware,
    HardwareTexture,
    HardwarePipeline,
    DrawCpu,
    WriteBack,
    Submit,
    WaitGpu,
    Sync,
    DisplayTransfer,
    MemoryFill,
    TextureCopy,
}

pub const NAMES: [&str; 15] = [
    "command lists",
    "  draws",
    "    shader prepare",
    "    textures (bind/decode)",
    "    hardware record",
    "      hw texture upload/lookup",
    "      hw pipeline lookup",
    "    cpu shading/raster",
    "  write back (GPU->guest)",
    "  submit",
    "  wait for GPU",
    "sync for CPU access",
    "display transfer",
    "memory fill",
    "texture copy",
];

static NANOS: [AtomicU64; 15] = [const { AtomicU64::new(0) }; 15];
static COUNTS: [AtomicU64; 15] = [const { AtomicU64::new(0) }; 15];

pub struct Scope {
    phase: Phase,
    start: Instant,
}

impl Drop for Scope {
    fn drop(&mut self) {
        let index = self.phase as usize;
        NANOS[index].fetch_add(self.start.elapsed().as_nanos() as u64, Ordering::Relaxed);
        COUNTS[index].fetch_add(1, Ordering::Relaxed);
    }
}

pub fn scope(phase: Phase) -> Scope {
    Scope { phase, start: Instant::now() }
}

/// (name, total nanoseconds, times entered) for each phase.
pub fn totals() -> Vec<(&'static str, u64, u64)> {
    (0..NAMES.len())
        .map(|i| (NAMES[i], NANOS[i].load(Ordering::Relaxed), COUNTS[i].load(Ordering::Relaxed)))
        .collect()
}
