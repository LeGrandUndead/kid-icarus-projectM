//! counters the runtime's usage report reads: work the renderer does on the
//! CPU that is worth knowing the cost of.

use std::sync::atomic::{AtomicU64, Ordering};

/// geometry shader runs in fixed-size primitive (particle) mode, and the
/// nanoseconds they took.
pub static PARTICLE_PRIMITIVES: AtomicU64 = AtomicU64::new(0);
pub static PARTICLE_NANOS: AtomicU64 = AtomicU64::new(0);

/// textures decoded from guest memory on the CPU (a new or changed one),
/// and the nanoseconds it took.
pub static TEXTURE_DECODES: AtomicU64 = AtomicU64::new(0);
pub static TEXTURE_DECODE_NANOS: AtomicU64 = AtomicU64::new(0);
/// pipelines made on the drawing thread, compiled or taken from the
/// driver's cache, which the draw waits for, and the nanoseconds.
pub static PIPELINES_MADE: AtomicU64 = AtomicU64::new(0);
pub static PIPELINE_NANOS: AtomicU64 = AtomicU64::new(0);

/// every counter, named, for a frame's breakdown.
pub fn all() -> [(&'static str, u64); 6] {
    [
        ("particle primitives", get(&PARTICLE_PRIMITIVES)),
        ("particle ns", get(&PARTICLE_NANOS)),
        ("texture decodes", get(&TEXTURE_DECODES)),
        ("texture decode ns", get(&TEXTURE_DECODE_NANOS)),
        ("pipelines made", get(&PIPELINES_MADE)),
        ("pipeline ns", get(&PIPELINE_NANOS)),
    ]
}

pub fn add(counter: &AtomicU64, value: u64) {
    counter.fetch_add(value, Ordering::Relaxed);
}

pub fn get(counter: &AtomicU64) -> u64 {
    counter.load(Ordering::Relaxed)
}
