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
    PcInterface,
    DrawCpu,
    WriteBack,
    Submit,
    WaitGpu,
    Sync,
    DisplayTransfer,
    MemoryFill,
    TextureCopy,
}

pub const NAMES: [&str; 16] = [
    "command lists",
    "  draws",
    "    shader prepare",
    "    textures (bind/decode)",
    "    hardware record",
    "      hw texture upload/lookup",
    "      hw pipeline lookup",
    "      pc interface capture",
    "    cpu shading/raster",
    "  write back (GPU->guest)",
    "  submit",
    "  wait for GPU",
    "sync for CPU access",
    "display transfer",
    "memory fill",
    "texture copy",
];

static NANOS: [AtomicU64; 16] = [const { AtomicU64::new(0) }; 16];
static COUNTS: [AtomicU64; 16] = [const { AtomicU64::new(0) }; 16];

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

/// why the renderer had to bring a GPU image back to guest memory, and
/// which buffers were involved, counted, for the usage report.
static EVENTS: std::sync::Mutex<Option<std::collections::BTreeMap<String, u64>>> = std::sync::Mutex::new(None);

pub fn event(what: impl FnOnce() -> String) {
    if let Ok(mut events) = EVENTS.lock() {
        let events = events.get_or_insert_with(Default::default);
        if events.len() < 512 {
            *events.entry(what()).or_insert(0) += 1;
        } else if let Some(count) = events.get_mut(&what()) {
            *count += 1;
        }
    }
}

pub fn events() -> Vec<(String, u64)> {
    let mut list: Vec<(String, u64)> = EVENTS
        .lock()
        .ok()
        .and_then(|events| events.as_ref().map(|e| e.iter().map(|(k, v)| (k.clone(), *v)).collect()))
        .unwrap_or_default();
    list.sort_by(|a, b| b.1.cmp(&a.1));
    list
}
