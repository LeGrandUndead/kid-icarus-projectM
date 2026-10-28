//! The white screen after warps in chapter 9 (October 28 investigation).
//!
//! A render capture showed the game itself drawing its full-white fade
//! layer (zakuro_gpu::white_out) frame after frame while the CPU sat idle,
//! and it stays at 30 fps too: the game's own logic holds the white, waiting
//! on something. When the white lasts two seconds this writes, to
//! build/diagnostics/white-out.log, what every thread is doing and waiting
//! on, with the return addresses on its stack, again every five seconds
//! while it lasts and once when it ends, and saves a RAM snapshot at the
//! start and the end (build/diagnostics/white-out/).

use std::io::Write;

use zakuro_core::System;

/// Frames of full white before reporting (2 s at 60 fps).
const REPORT_FRAMES: u32 = 120;
/// Frames between reports while it lasts (5 s).
const REPORT_EVERY: u32 = 300;

#[derive(Default)]
pub struct WhiteWatch {
    /// game-drawn frames in a row with the full-white layer
    frames: u32,
}

impl WhiteWatch {
    /// After each emulated frame.
    pub fn frame(&mut self, system: &mut System, frame: u64) {
        let Some(full) = zakuro_gpu::white_out::take_full() else { return };
        if full {
            self.frames += 1;
            if self.frames == REPORT_FRAMES {
                log::warn!("white-out held {} frames (frame {frame}): see build/diagnostics/white-out.log", self.frames);
                crate::ram_snapshot::save_in(&mut system.memory, frame, &folder());
            }
            if self.frames >= REPORT_FRAMES && (self.frames - REPORT_FRAMES).is_multiple_of(REPORT_EVERY) {
                report(system, frame, &format!("white for {} frames", self.frames));
            }
        } else {
            if self.frames >= REPORT_FRAMES {
                log::warn!("white-out ended at frame {frame} after {} frames", self.frames);
                report(system, frame, &format!("white ended after {} frames", self.frames));
                crate::ram_snapshot::save_in(&mut system.memory, frame, &folder());
            } else if self.frames >= 30 {
                log::info!("white-out of {} frames", self.frames);
            }
            self.frames = 0;
        }
    }
}

fn folder() -> std::path::PathBuf {
    std::path::PathBuf::from("build/diagnostics/white-out")
}

/// The threads, and for each the code addresses on its stack (return
/// addresses, newest first), appended to the log.
fn report(system: &mut System, frame: u64, what: &str) {
    let tick = system.cpu.cycles;
    let mut text = format!("frame {frame}: {what}\n{}", system.kernel.report(tick));
    let threads: Vec<(u32, u32, u32)> = system.kernel.threads.iter()
        .filter(|t| t.status != zakuro_core::kernel::thread::ThreadStatus::Dead)
        .map(|t| {
            let current = Some(t.id) == system.kernel.current_thread;
            (t.id, if current { system.cpu.regs[13] } else { t.context.regs[13] }, t.stack_top)
        })
        .collect();
    for (id, sp, top) in threads {
        let mut calls = Vec::new();
        let mut at = sp & !3;
        while at < top && at < sp.saturating_add(0x800) && calls.len() < 16 {
            let mut bytes = [0u8; 4];
            system.memory.read_bytes(at, &mut bytes);
            let word = u32::from_le_bytes(bytes);
            // code addresses of the executable (ARM, or Thumb with the low bit)
            if (0x0010_0000..0x00D0_0000).contains(&(word & !1)) {
                calls.push(format!("{word:08X}"));
            }
            at += 4;
        }
        text += &format!("  t{id} stack: {}\n", calls.join(" "));
    }
    let _ = std::fs::create_dir_all("build/diagnostics");
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open("build/diagnostics/white-out.log") {
        let _ = writeln!(file, "{text}");
    }
}
