//! What frame interpolation did with every draw of a few frames, for
//! working out offline why something on screen still moves at 30.
//!
//! With interpolation on, a run of three frames in a row is written every
//! fifteen seconds (the first after five), sixteen runs at most, to
//! `build/diagnostics/interpolation/` (emptied at the first run of a
//! session):
//! - `frames.bin`: each draw of those frames, what it was recognised by,
//!   whether it matched a draw of the frame before, jumped or blended, and
//!   all its float uniforms;
//! - `programs/<fingerprint>-<entry>.bin`: each vertex program those draws
//!   ran, once, its words and operand descriptors.
//!
//! Layout, little endian: the file starts with `KIUIP1\0\0`; a frame is
//! `FRAM`, u64 frame, u32 draws; a draw is u32 kind (0 shaded on the CPU, 1
//! on the GPU), u64 fingerprint, u32 entry point, u32 colour buffer, u32
//! depth buffer (0 for none), u32 vertex arrays (u32::MAX: decoded on the
//! CPU, then u32 vertices), that many u32 address and u32 length, 3 u64
//! textures (0 none), u64 key, u128 transforms, u128 read directly, u8
//! matched, u8 jumped, u8 blended, u8 0, 24 u32 output semantics, 96 x 4
//! f32 float uniforms, u32 indices. A draw shaded on the CPU has zeros
//! from the fingerprint to the semantics and no uniforms.
//!
//! It only reads what the renderer already has; nothing it does changes a
//! picture.

use std::collections::HashSet;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::PathBuf;

use super::interpolate::Outcome;
use super::{Draw, Geometry, Inputs};
use crate::shader::transforms::Transforms;

/// frames of interpolation before the first run, and between two.
const FIRST: u64 = 300;
const EVERY: u64 = 900;
/// frames in a run, and runs in a session.
const RUN: u64 = 3;
const RUNS: u32 = 16;

#[derive(Default)]
pub(super) struct Report {
    out: Option<BufWriter<File>>,
    /// the frame being written, its draws so far, and where its count goes.
    draws: u32,
    frame_bytes: Vec<u8>,
    frame: u64,
    runs: u32,
    programs: HashSet<(u64, u32)>,
    started: bool,
}

fn folder() -> PathBuf {
    PathBuf::from("build/diagnostics/interpolation")
}

impl Report {
    /// whether the draws of the frame going on are being written.
    pub(super) fn on(&self) -> bool {
        self.out.is_some()
    }

    /// a frame ended with interpolation on: writes it out if it was being
    /// written, and starts on the next when one is due.
    pub(super) fn end_frame(&mut self, frames: u64) {
        if let Some(out) = self.out.as_mut() {
            let mut head = Vec::with_capacity(16);
            head.extend_from_slice(b"FRAM");
            head.extend_from_slice(&self.frame.to_le_bytes());
            head.extend_from_slice(&self.draws.to_le_bytes());
            let written = out.write_all(&head).and_then(|_| out.write_all(&self.frame_bytes)).and_then(|_| out.flush());
            if let Err(error) = written {
                log::warn!("interpolation report stopped: {error}");
                self.out = None;
                self.runs = RUNS;
            }
        }
        self.frame_bytes.clear();
        self.draws = 0;
        self.frame = frames;
        // within a run, past its first frame, the next frame is written too
        let into_run = frames.checked_sub(FIRST).map(|n| n % EVERY);
        let writing = matches!(into_run, Some(n) if n < RUN) && self.runs < RUNS;
        if !writing {
            if self.out.take().is_some() {
                self.runs += 1;
                log::info!("interpolation report: run {} written to {}", self.runs, folder().display());
            }
            return;
        }
        if self.out.is_none() {
            self.out = self.open();
            if self.out.is_none() {
                self.runs = RUNS;
            }
        }
    }

    fn open(&mut self) -> Option<BufWriter<File>> {
        let folder = folder();
        let fresh = !self.started;
        self.started = true;
        if fresh {
            let _ = std::fs::remove_dir_all(&folder);
        }
        std::fs::create_dir_all(folder.join("programs")).ok()?;
        let path = folder.join("frames.bin");
        let file = std::fs::OpenOptions::new().create(true).append(true).open(&path);
        match file {
            Ok(file) => {
                let mut out = BufWriter::new(file);
                if fresh && out.write_all(b"KIUIP1\0\0").is_err() {
                    return None;
                }
                Some(out)
            }
            Err(error) => {
                log::warn!("interpolation report not written, {}: {error}", path.display());
                None
            }
        }
    }

    /// one draw of the frame being written.
    pub(super) fn draw(&mut self, draw: &Draw, key: u64, transforms: Transforms, outcome: Outcome) {
        let b = &mut self.frame_bytes;
        let u32_ = |b: &mut Vec<u8>, v: u32| b.extend_from_slice(&v.to_le_bytes());
        self.draws += 1;
        match draw.geometry {
            Geometry::Placed { indices, .. } => {
                u32_(b, 0);
                b.extend_from_slice(&0u64.to_le_bytes());
                u32_(b, 0);
                u32_(b, draw.target);
                u32_(b, draw.depth.map_or(0, |(addr, _)| addr));
                u32_(b, 0);
                for unit_index in 0..3 {
                    b.extend_from_slice(&texture(draw, unit_index).to_le_bytes());
                }
                b.extend_from_slice(&0u64.to_le_bytes());
                b.extend_from_slice(&0u128.to_le_bytes());
                b.extend_from_slice(&0u128.to_le_bytes());
                b.extend_from_slice(&[0; 4]);
                for _ in 0..24 {
                    u32_(b, 0);
                }
                u32_(b, indices.len() as u32);
            }
            Geometry::Shaded(shading) => {
                let unit = shading.unit;
                let fingerprint = unit.fingerprint();
                u32_(b, 1);
                b.extend_from_slice(&fingerprint.to_le_bytes());
                u32_(b, unit.entry_point);
                u32_(b, draw.target);
                u32_(b, draw.depth.map_or(0, |(addr, _)| addr));
                match shading.inputs {
                    Inputs::Raw(raw) => {
                        u32_(b, raw.arrays.len() as u32);
                        for &(addr, len) in &raw.arrays {
                            u32_(b, addr);
                            u32_(b, len);
                        }
                    }
                    Inputs::Decoded(decoded) => {
                        u32_(b, u32::MAX);
                        u32_(b, decoded.len() as u32);
                    }
                }
                for unit_index in 0..3 {
                    b.extend_from_slice(&texture(draw, unit_index).to_le_bytes());
                }
                b.extend_from_slice(&key.to_le_bytes());
                b.extend_from_slice(&transforms.all.to_le_bytes());
                b.extend_from_slice(&transforms.direct.to_le_bytes());
                b.extend_from_slice(&[outcome.matched as u8, outcome.jumped as u8, outcome.blended as u8, 0]);
                for &semantic in &shading.semantics {
                    u32_(b, semantic);
                }
                for value in unit.float_uniforms.iter().flatten() {
                    b.extend_from_slice(&value.to_le_bytes());
                }
                u32_(b, shading.indices.len() as u32);
                if self.programs.insert((fingerprint, unit.entry_point)) {
                    let mut words = Vec::with_capacity((unit.program.len() + unit.descriptors.len() + 1) * 4);
                    for &word in unit.program.iter().chain(unit.descriptors.iter()) {
                        words.extend_from_slice(&word.to_le_bytes());
                    }
                    words.extend_from_slice(&unit.entry_point.to_le_bytes());
                    let path = folder().join("programs").join(format!("{fingerprint:016X}-{}.bin", unit.entry_point));
                    if let Err(error) = std::fs::write(&path, words) {
                        log::warn!("interpolation report: {} not written, {error}", path.display());
                    }
                }
            }
        }
    }
}

/// what a texture unit samples, as the matching sees it, 0 for nothing.
fn texture(draw: &Draw, unit: usize) -> u64 {
    match draw.textures.get(unit) {
        Some(Some(bound)) => bound.addr as u64 | 1 << 32,
        _ => 0,
    }
}
