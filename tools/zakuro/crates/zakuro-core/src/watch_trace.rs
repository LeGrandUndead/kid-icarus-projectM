//! Research: which code writes chosen memory, while the game runs.
//!
//! Off unless `build/diagnostics/watch.txt` (or `KIU_WATCH`) lists ranges,
//! one `address[:length]` in hex per line or comma, `#` starting a comment:
//!
//! ```text
//! E14600:1200   # the camera manager's cameras
//! ```
//!
//! Every distinct place that writes there (code address and return
//! address) is counted, with the offsets it wrote, a value it wrote, when
//! it was first seen and the return addresses on its stack, which name its
//! callers. `build/diagnostics/watch-trace.txt` is rewritten with the
//! summary every ten seconds and when the game ends. Watched pages are
//! written the slow way, so only watch what a question needs.

use std::collections::{BTreeSet, HashMap};
use std::io::Write;

use crate::memory::{Memory, WatchHit};

const SUMMARY_EVERY: u64 = 600;
const OUT: &str = "build/diagnostics/watch-trace.txt";

struct Writer {
    count: u64,
    first: u64,
    offsets: BTreeSet<u32>,
    value: u32,
    callers: Vec<u32>,
}

pub struct WatchTrace {
    ranges: Vec<(u32, u32)>,
    writers: HashMap<(u32, u32), Writer>,
    frame: u64,
}

fn parse(text: &str) -> Vec<(u32, u32)> {
    text.lines()
        .map(|line| line.split('#').next().unwrap_or(""))
        .flat_map(|line| line.split(','))
        .filter_map(|item| {
            let item = item.trim();
            if item.is_empty() {
                return None;
            }
            let (address, length) = item.split_once(':').unwrap_or((item, "4"));
            let hex = |t: &str| u32::from_str_radix(t.trim().trim_start_matches("0x"), 16).ok();
            Some((hex(address)?, hex(length)?))
        })
        .collect()
}

impl WatchTrace {
    /// the ranges asked for, or none.
    pub fn open() -> Option<WatchTrace> {
        let text = std::env::var("KIU_WATCH").ok().or_else(|| std::fs::read_to_string("build/diagnostics/watch.txt").ok())?;
        let ranges = parse(&text);
        if ranges.is_empty() {
            return None;
        }
        log::warn!("watching writes to {} ranges ({} or KIU_WATCH), results in {OUT}", ranges.len(), "build/diagnostics/watch.txt");
        Some(WatchTrace { ranges, writers: HashMap::new(), frame: 0 })
    }

    pub fn arm(&self, memory: &mut Memory) {
        for &(address, length) in &self.ranges {
            memory.watch_cpu_writes(address, length);
        }
    }

    /// this frame's writes.
    pub fn frame(&mut self, hits: &[WatchHit], frame: u64) {
        self.frame = frame;
        for hit in hits {
            let Some(&(base, _)) = self.ranges.iter().find(|(a, l)| hit.address.wrapping_sub(*a) < *l) else { continue };
            let writer = self.writers.entry((hit.pc, hit.lr)).or_insert_with(|| Writer {
                count: 0,
                first: frame,
                offsets: BTreeSet::new(),
                value: hit.value,
                callers: hit.stack.iter().copied().filter(|w| (0x0010_0000..0x00C9_6000).contains(w) && w & 1 == 0).take(8).collect(),
            });
            writer.count += 1;
            if writer.offsets.len() < 64 {
                writer.offsets.insert(hit.address - base);
            }
        }
        if frame % SUMMARY_EVERY == 0 {
            self.summary(frame);
        }
    }

    pub fn summary(&self, frame: u64) {
        if let Some(folder) = std::path::Path::new(OUT).parent() {
            let _ = std::fs::create_dir_all(folder);
        }
        let Ok(mut out) = std::fs::File::create(OUT) else { return };
        let _ = writeln!(out, "frame {frame}: {} writers to {:X?}", self.writers.len(), self.ranges);
        let mut writers: Vec<_> = self.writers.iter().collect();
        writers.sort_by_key(|(_, w)| std::cmp::Reverse(w.count));
        for ((pc, lr), w) in writers {
            let offsets: Vec<String> = w.offsets.iter().map(|o| format!("{o:X}")).collect();
            let callers: Vec<String> = w.callers.iter().map(|c| format!("{c:08X}")).collect();
            let _ = writeln!(
                out,
                "pc {pc:08X} lr {lr:08X}  {} writes from frame {}, e.g. {:08X} ({})  offsets {}  callers {}",
                w.count, w.first, w.value, f32::from_bits(w.value), offsets.join(" "), callers.join(" ")
            );
        }
    }
}

/// the summary once more as the game ends.
impl Drop for WatchTrace {
    fn drop(&mut self) {
        self.summary(self.frame);
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn ranges_by_line_or_comma_with_comments() {
        let ranges = super::parse("E14600:1200   # cameras\n00D63620, 0x00F2E4B0:10\n\n# nothing\n");
        assert_eq!(ranges, vec![(0xE14600, 0x1200), (0xD63620, 4), (0xF2E4B0, 0x10)]);
    }
}
