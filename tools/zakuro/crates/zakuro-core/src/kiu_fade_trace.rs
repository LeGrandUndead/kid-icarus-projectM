//! Diagnostic, temporary: what leaves the screen white after some warps in
//! the 60 FPS mode (chapter 9). Removed with the fix it leads to.
//!
//! The white is the game's own screen fader, left fading out at full white:
//! the fader singleton at `0x00D63620` keeps a fader per screen at `+0xB8`,
//! and `0x004641E0` starts a fade on one of its slots by writing the colour
//! (`+0x1C`), the starting amount (`+0x3C`) and the rate (`+0x4C`, negative
//! for a fade back in), at `layer * 0x48 + slot * 4`. Two memory snapshots of
//! a white that lasted 548 frames had the top screen's layer 0 slot 1 fading
//! out, white, at a rate of 1/16, with no fade back in.
//!
//! The warp controller (`0x00820B50`, a member at `+0x524` of the object that
//! updates it; state at `+0xB4`: 0 fade out, 1 hold, 2 move, 3 fade in,
//! 4 end, -1 idle; `+0xAC` set when a request found no destination, which
//! skips both fades) asks for that kind of fade through `0x00538B34`.
//!
//! Written to `build/diagnostics/fade-trace.log`, overwritten each run:
//! - every fade started on the top screen's fader: slot, colour, rate, and
//!   the return addresses on the stack, which name who asked;
//! - the warp controller, once a fade shows where it is: every write of its
//!   state and of its no-destination flag, with who wrote it;
//! - how long the fader stays at full white.
//!
//! `KIU_FADE_TRACE=0` turns it off. It only reads and logs; the game runs
//! as without it, a little slower on the two memory pages it watches.

use std::fs::File;
use std::io::{BufWriter, Write};

use zakuro_cpu::Bus;

use crate::memory::{Memory, WatchHit};

/// the fader singleton, and where its faders are.
const FADERS: u32 = 0x00D6_3620;
const FADER_LIST: u32 = 0xB8;
/// the fields of a fader 0x004641E0 writes, over every layer and slot.
const FADER_FIELDS: (u32, u32) = (0x1C, 0x4C + 0x48 * 3 + 4 * 4);
/// return addresses in the warp controller after each of its fades.
const WARP_FADE_OUT: u32 = 0x0082_0DEC;
const WARP_FADE_IN: u32 = 0x0082_10A4;
/// where a warp request (0x0082115C) returns to, in
/// anime_command::WarpControl (0x00AB5B0C).
const WARP_REQUEST: u32 = 0x00AB_5B74;
/// how far above a fade's return address 0x00538B34 saved the caller's r4.
const SAVED_R4: usize = 5;

pub struct FadeTrace {
    out: Option<BufWriter<File>>,
    fader: u32,
    warp: u32,
    white: Option<u64>,
}

fn code(word: u32) -> bool {
    (0x0010_0000..0x00C8_0000).contains(&word) && word & 1 == 0
}

impl FadeTrace {
    pub fn open() -> Option<FadeTrace> {
        if std::env::var("KIU_FADE_TRACE").is_ok_and(|v| v.trim() == "0") {
            return None;
        }
        let dir = std::path::Path::new("build/diagnostics");
        let out = std::fs::create_dir_all(dir).ok().and_then(|_| File::create(dir.join("fade-trace.log")).ok()).map(BufWriter::new);
        if out.is_some() {
            log::info!("fade trace on: build/diagnostics/fade-trace.log");
        }
        Some(FadeTrace { out, fader: 0, warp: 0, white: None })
    }

    fn line(&mut self, text: std::fmt::Arguments) {
        if let Some(out) = &mut self.out {
            let _ = writeln!(out, "{text}");
            let _ = out.flush();
        }
    }

    /// after each frame.
    pub fn frame(&mut self, memory: &mut Memory, frame: u64, rate: u8) {
        let hits: Vec<WatchHit> = memory.watch_hits.drain(..).collect();
        for hit in &hits {
            self.hit(memory, frame, rate, hit);
        }

        let faders = memory.read32(FADERS);
        if faders == 0 {
            return;
        }
        let fader = memory.read32(faders + FADER_LIST);
        if fader != self.fader && fader != 0 {
            self.fader = fader;
            memory.watch_cpu_writes(fader + FADER_FIELDS.0, FADER_FIELDS.1 - FADER_FIELDS.0);
            self.line(format_args!("frame {frame}: top screen fader at {fader:08X}"));
        }
        if self.fader == 0 {
            return;
        }
        // layer 0 slot 1, the warp's
        let amount = f32::from_bits(memory.read32(self.fader + 0x3C + 4));
        let speed = f32::from_bits(memory.read32(self.fader + 0x4C + 4));
        let white = amount >= 0.999 && speed > 0.0;
        match (white, self.white) {
            (true, None) => self.white = Some(frame),
            (false, Some(since)) => {
                if frame - since > 30 {
                    self.line(format_args!("frame {frame}: white from frame {since} to {frame}, {} frames", frame - since));
                }
                self.white = None;
            }
            (true, Some(since)) if (frame - since) % 300 == 60 => {
                let state = if self.warp != 0 { memory.read32(self.warp + 0xB4) as i32 } else { -2 };
                self.line(format_args!("frame {frame}: white for {} frames (60 FPS {}), warp controller state {state}", frame - since, rate == 60));
            }
            _ => {}
        }
    }

    fn hit(&mut self, memory: &mut Memory, frame: u64, rate: u8, hit: &WatchHit) {
        let callers: Vec<String> = hit.stack.iter().filter(|&&w| code(w)).take(10).map(|w| format!("{w:08X}")).collect();
        let callers = callers.join(" ");
        if self.fader != 0 && hit.address.wrapping_sub(self.fader) < FADER_FIELDS.1 {
            let field = hit.address - self.fader;
            // a layer's fields, 0x48 bytes each: colours at +0x1C, amounts
            // at +0x3C (written every frame, left out), rates at +0x4C
            let layer = (field - FADER_FIELDS.0) / 0x48;
            let (slot, kind) = match field - 0x48 * layer {
                rel @ 0x1C..0x2C => ((rel - 0x1C) / 4, "colour"),
                rel @ 0x4C..0x5C => ((rel - 0x4C) / 4, "rate"),
                _ => return,
            };
            let value = if kind == "rate" { format!("{:.5}", f32::from_bits(hit.value)) } else { format!("{:08X}", hit.value) };
            self.line(format_args!(
                "frame {frame}: fader layer {layer} slot {slot} {kind} {value} (60 FPS {}) | pc {:08X} lr {:08X} | callers {callers}",
                rate == 60, hit.pc, hit.lr
            ));
            // a fade of the warp controller: where it is
            if kind == "rate" {
                if let Some(i) = hit.stack.iter().position(|&w| w == WARP_FADE_OUT || w == WARP_FADE_IN) {
                    if let Some(&warp) = i.checked_sub(SAVED_R4).and_then(|j| hit.stack.get(j)) {
                        if warp != self.warp && warp != 0 {
                            self.warp = warp;
                            memory.watch_cpu_writes(warp + 0xAC, 4);
                            memory.watch_cpu_writes(warp + 0xB4, 4);
                            self.line(format_args!("frame {frame}: warp controller at {warp:08X}"));
                        }
                    }
                }
            }
            return;
        }
        if self.warp != 0 && (hit.address == self.warp + 0xB4 || hit.address == self.warp + 0xAC) {
            let what = if hit.address == self.warp + 0xB4 { "state" } else { "no destination" };
            let request = if hit.stack.contains(&WARP_REQUEST) { " (a request)" } else { "" };
            let timer = f32::from_bits(memory.read32(self.warp + 0xB0));
            let fade = f32::from_bits(memory.read32(self.warp + 0xA4));
            let wait = f32::from_bits(memory.read32(self.warp + 0xA8));
            self.line(format_args!(
                "frame {frame}: warp {what} {}{request}, timer {timer:.4}, fade {fade:.4}, wait/2 {wait:.4} (60 FPS {}) | pc {:08X} lr {:08X} | callers {callers}",
                hit.value as i32, rate == 60, hit.pc, hit.lr
            ));
        }
    }
}
