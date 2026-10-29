//! Kid Icarus: Uprising: the white screen after some warps in the 60 FPS
//! mode (chapter 9, Pandora's warps).
//!
//! A warp pad plays a short animation script, chapter 9's
//! `YAK_G09_Warp_G05_00` for one:
//!
//! ```text
//! EventPlayerStop, PlaySE,
//! StartFade   out to white over 16 frames
//! WaitFrame   16
//! Warp        the player is sent to the destination
//! WaitFrame   4
//! StartFade   back in over 16 frames
//! EventPlayerStop, ...
//! ```
//!
//! In the 60 FPS mode the script is sometimes cut off after `Warp`, before
//! its fade back in, and the screen stays white until something else
//! clears the fader. Found October 29: a trace of every fade showed the
//! script's fade-out (`anime_command::StartFade`, `0x00AEAD80`) with no
//! fade-in after it for 660 frames, and memory snapshots of an earlier white
//! had the script's commands loaded but no script running them.
//!
//! This finishes the script's own fade. When a StartFade fades out and its
//! script goes on to a Warp and then a StartFade back in on the same screen
//! and layer, that fade-in is due once the waits in between have passed. If
//! the fader is still faded out a little after that, the fade-in is started
//! as the command would start it: same screen, layer and length (the colour
//! stays the fade-out's, as the command's does). A script that fades back in
//! on time is left alone, and so is every fade that is not part of such a
//! script.
//!
//! The screen fader (singleton `0x00D63620`, a fader per screen at `+0xB8`)
//! keeps per layer (`0x48` bytes) and slot (4 bytes) the colour at `+0x1C`,
//! the amount at `+0x2C`, the target at `+0x3C` and the change per frame at
//! `+0x4C` (`0x00390D64`); StartFade fades through slot 1 (`0x00538B34`,
//! `0x00461060`, `0x004641E0`).
//!
//! It sees a fade start by watching writes to the faders' targets and rates;
//! the stack then says whether StartFade asked for it, and which command.

use zakuro_cpu::Bus;

use crate::memory::{Memory, WatchHit};

const FADERS: u32 = 0x00D6_3620;
const FADER_LIST: u32 = 0xB8;
const SCREENS: u32 = 2;
/// a fader's per-slot fields, layer 0 slot 0 colour to layer 3 slot 3 rate.
const FIELDS: (u32, u32) = (0x1C, 0x4C + 0x48 * 3 + 4 * 4);
const LAYER: u32 = 0x48;
const SLOT: u32 = 1;
const TARGET: u32 = 0x3C;
const RATE: u32 = 0x4C;

/// anime_command vtables.
const START_FADE: u32 = 0x00D0_C8E0;
const WAIT_FRAME: u32 = 0x00D0_C9D0;
const WARP: u32 = 0x00D0_B864;
/// where StartFade's call of 0x00538B34 returns to, and how far below it on
/// the stack that function keeps its caller's r4, the command.
const START_FADE_RETURN: u32 = 0x00AE_AE18;
const SAVED_COMMAND: usize = 5;
/// commands looked through after a fade-out for the warp and the fade-in.
const LOOK_AHEAD: usize = 8;
/// how long past its due time a fade-in may be late before it is started,
/// in 60ths of a second.
const GRACE: u64 = 30;

/// a StartFade command as the script holds it.
#[derive(Debug, Clone, Copy, PartialEq)]
struct StartFade {
    layer: u32,
    screen: u32,
    frames: f32,
    fade_in: bool,
}

fn start_fade(read: &mut impl FnMut(u32) -> u32, command: u32) -> Option<StartFade> {
    if read(command) != START_FADE {
        return None;
    }
    let packed = read(command + 0x10);
    Some(StartFade {
        layer: (packed >> 8) & 0xFF,
        screen: (packed >> 16) & 0xFF,
        frames: f32::from_bits(read(command + 0x14)),
        fade_in: read(command + 0x18) & 0xFF != 0,
    })
}

/// the fade-in a fade-out's script makes after a warp, and how long after
/// the fade-out it is due, in 60ths of a second. commands are linked
/// through `+8`, which points 4 bytes into the next.
fn warp_fade_in(read: &mut impl FnMut(u32) -> u32, fade_out: u32) -> Option<(StartFade, f32)> {
    let out = start_fade(read, fade_out)?;
    if out.fade_in {
        return None;
    }
    let (mut command, mut due, mut warped) = (fade_out, 0.0, false);
    for _ in 0..LOOK_AHEAD {
        command = read(command + 8).checked_sub(4)?;
        match read(command) {
            WAIT_FRAME => due += f32::from_bits(read(command + 0x10)),
            WARP => warped = true,
            START_FADE => {
                let fade = start_fade(read, command)?;
                return (warped && fade.fade_in && fade.screen == out.screen && fade.layer == out.layer)
                    .then_some((fade, due));
            }
            _ => {}
        }
    }
    None
}

/// a warp's fade-in the script has yet to start.
#[derive(Debug)]
struct Pending {
    fader: u32,
    layer: u32,
    frames: f32,
    /// the frame it is started at, if the script has not by then.
    deadline: u64,
}

#[derive(Default)]
pub struct WarpFade {
    faders: [u32; SCREENS as usize],
    pending: Option<Pending>,
}

impl WarpFade {
    /// after each frame, with the frame's watched writes.
    pub fn frame(&mut self, memory: &mut Memory, frame: u64, hits: &[WatchHit]) {
        for hit in hits {
            self.hit(memory, frame, hit);
        }
        self.watch(memory);
        self.finish(memory, frame);
    }

    /// the faders' fields watched, again when a fader is made anew.
    fn watch(&mut self, memory: &mut Memory) {
        let faders = memory.read32(FADERS);
        if faders == 0 {
            return;
        }
        for screen in 0..SCREENS {
            let fader = memory.read32(faders + FADER_LIST + 4 * screen);
            if fader != 0 && fader != self.faders[screen as usize] {
                self.faders[screen as usize] = fader;
                memory.watch_cpu_writes(fader + FIELDS.0, FIELDS.1 - FIELDS.0);
            }
        }
    }

    fn hit(&mut self, memory: &mut Memory, frame: u64, hit: &WatchHit) {
        let Some(&fader) = self.faders.iter().find(|&&f| f != 0 && hit.address.wrapping_sub(f + FIELDS.0) < FIELDS.1 - FIELDS.0) else {
            return;
        };
        let field = hit.address - fader;
        let layer = (field - FIELDS.0) / LAYER;
        if field - layer * LAYER != RATE + 4 * SLOT {
            return;
        }
        // a fade started on this slot: StartFade's, or anything else's
        let command = hit.stack.iter().position(|&w| w == START_FADE_RETURN)
            .and_then(|i| i.checked_sub(SAVED_COMMAND))
            .map(|i| hit.stack[i]);
        let mut read = |addr: u32| memory.read32(addr);
        let fade = command.and_then(|c| start_fade(&mut read, c));
        if let Some(pending) = &self.pending {
            if pending.fader == fader && pending.layer == layer {
                // the script faded back in, or something else took the slot
                self.pending = None;
            }
        }
        let (Some(command), Some(fade)) = (command, fade) else { return };
        if fade.fade_in {
            return;
        }
        if let Some((fade_in, due)) = warp_fade_in(&mut read, command) {
            let deadline = frame + due.max(0.0).ceil() as u64 + GRACE;
            self.pending = Some(Pending { fader, layer, frames: fade_in.frames, deadline });
        }
    }

    /// a warp's fade-in its script did not start in time, started.
    fn finish(&mut self, memory: &mut Memory, frame: u64) {
        let Some(pending) = &self.pending else { return };
        if frame < pending.deadline {
            return;
        }
        let slot = pending.fader + pending.layer * LAYER + 4 * SLOT;
        let target = f32::from_bits(memory.read32(slot + TARGET));
        let rate = f32::from_bits(memory.read32(slot + RATE));
        if target >= 1.0 && rate > 0.0 && pending.frames > 0.0 {
            // as 0x004641E0 starts a fade back in: target 0, rate -1/frames
            memory.write32(slot + TARGET, 0f32.to_bits());
            memory.write32(slot + RATE, (-1.0 / pending.frames).to_bits());
            log::info!("warp fade: the script was cut off before its fade back in; faded in over {} frames (frame {frame})", pending.frames);
        }
        self.pending = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    /// chapter 9's warp script as the October 28 snapshot holds it, from its
    /// fade-out on.
    fn script(fade_in_layer: u32) -> HashMap<u32, u32> {
        let mut m = HashMap::new();
        let mut put = |addr: u32, words: &[u32]| {
            for (i, &w) in words.iter().enumerate() {
                m.insert(addr + 4 * i as u32, w);
            }
        };
        // StartFade out, white, layer 0, screen 0, 16 frames
        put(0x15AB5570, &[START_FADE, 0x15AB5570, 0x15AB55C4, 0, 0x0000_0000, 16f32.to_bits(), 0]);
        put(0x15AB55C0, &[WAIT_FRAME, 0x15AB55C0, 0x15AB55FC, 0, 16f32.to_bits()]);
        put(0x15AB55F8, &[WARP, 0x15AB55F8, 0x15AB5664, 0]);
        put(0x15AB5660, &[WAIT_FRAME, 0x15AB5660, 0x15AB569C, 0, 4f32.to_bits()]);
        put(0x15AB5698, &[START_FADE, 0x15AB5698, 0x15AB56EC, 0, fade_in_layer << 8, 16f32.to_bits(), 1]);
        put(0x15AB56E8, &[0x00D0_8E20, 0x15AB56E8, 0x15AB5724, 0]);
        put(0x15AB5720, &[0x00D1_F91C, 0x15AB5720, 0, 0]);
        m
    }

    fn reader(m: &HashMap<u32, u32>) -> impl FnMut(u32) -> u32 + '_ {
        move |addr| m.get(&addr).copied().unwrap_or(0)
    }

    #[test]
    fn a_warp_script_fades_back_in_twenty_frames_after_its_fade_out() {
        let m = script(0);
        let found = warp_fade_in(&mut reader(&m), 0x15AB5570);
        let fade_in = StartFade { layer: 0, screen: 0, frames: 16.0, fade_in: true };
        assert_eq!(found, Some((fade_in, 20.0)));
    }

    #[test]
    fn a_fade_in_is_not_a_fade_out_and_another_layer_is_another_fade() {
        let m = script(0);
        assert_eq!(warp_fade_in(&mut reader(&m), 0x15AB5698), None);
        let m = script(1);
        assert_eq!(warp_fade_in(&mut reader(&m), 0x15AB5570), None);
    }

    #[test]
    fn a_fade_out_without_a_warp_is_left_alone() {
        let mut m = script(0);
        // the Warp command replaced by another wait
        m.insert(0x15AB55F8, WAIT_FRAME);
        assert_eq!(warp_fade_in(&mut reader(&m), 0x15AB5570), None);
    }
}
