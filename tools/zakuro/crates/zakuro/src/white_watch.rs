//! The white screen after warps in chapter 9 (October 28 investigation).
//!
//! A render capture showed the game itself drawing its full-white fade
//! layer (zakuro_gpu::white_out) frame after frame while the CPU sat idle:
//! the game's own fade logic holds the white. The 60 fps mode changes how
//! the game counts time, so when the white lasts over two seconds at 60 fps
//! this sets the game back to 30 fps until the white ends, logs both
//! moments, and saves a RAM snapshot at each (build/diagnostics/white-out)
//! to find the state the fade waits on. If the white then ends at once, the
//! 60 fps mode is the cause and this is also the workaround.

use zakuro_core::memory::Memory;

/// Frames of full white at 60 fps before stepping in (2 s).
const HOLD_FRAMES: u32 = 120;

#[derive(Default)]
pub struct WhiteWatch {
    /// frames in a row the full-white layer was drawn
    frames: u32,
    /// the frame the 30 fps hold began, while it lasts
    held_since: Option<u64>,
}

impl WhiteWatch {
    /// After each emulated frame.
    pub fn frame(&mut self, memory: &mut Memory, frame: u64) {
        if zakuro_gpu::white_out::take_full() {
            self.frames += 1;
            if self.frames == HOLD_FRAMES && self.held_since.is_none()
                && zakuro_core::kiu_frame_rate::active_rate() == 60
            {
                log::warn!("white-out held {} frames at 60 fps (frame {frame}): game set to 30 fps until it ends", self.frames);
                crate::ram_snapshot::save_in(memory, frame, &folder());
                zakuro_core::kiu_frame_rate::set_held_at_30(true);
                self.held_since = Some(frame);
            }
        } else {
            if let Some(since) = self.held_since.take() {
                log::warn!("white-out ended at frame {frame}, {} frames after going to 30 fps", frame - since);
                crate::ram_snapshot::save_in(memory, frame, &folder());
                zakuro_core::kiu_frame_rate::set_held_at_30(false);
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
