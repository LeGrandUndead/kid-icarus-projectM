//! counters the runtime's usage report reads: work the renderer does on the
//! CPU that is worth knowing the cost of.

use std::sync::atomic::{AtomicU64, Ordering};

/// geometry shader runs in fixed-size primitive (particle) mode, and the
/// nanoseconds they took.
pub static PARTICLE_PRIMITIVES: AtomicU64 = AtomicU64::new(0);
pub static PARTICLE_NANOS: AtomicU64 = AtomicU64::new(0);

pub fn add(counter: &AtomicU64, value: u64) {
    counter.fetch_add(value, Ordering::Relaxed);
}

pub fn get(counter: &AtomicU64) -> u64 {
    counter.load(Ordering::Relaxed)
}
