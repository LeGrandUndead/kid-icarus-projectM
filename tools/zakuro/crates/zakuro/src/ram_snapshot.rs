//! Research aid (KIU_RAM_SNAPSHOT=<folder>, F7): saves the game's mapped
//! memory so two moments can be compared offline (for example before and
//! after using a power) to locate game state such as the equipped powers.
//! Not user-facing; the files hold game memory and stay local.
//!
//! Format: b"KIURAM1\0", frame (u64 LE), then one record per non-zero
//! mapped page: address (u32 LE) followed by the 4096-byte page.
use std::io::Write;

use zakuro_core::memory::Memory;

const PAGE: u32 = 0x1000;
/// VRAM and the GPU/DSP windows hold pictures, not game state.
const SKIP: [(u32, u32); 2] = [(0x1F00_0000, 0x1F60_0000), (0x1FF0_0000, 0x2000_0000)];

/// Saves a snapshot into a folder named by the runtime itself.
pub fn save_in(memory: &mut Memory, frame: u64, folder: &std::path::Path) {
    let _ = std::fs::create_dir_all(folder);
    let path = folder.join(format!("ram-{frame:08}.bin"));
    match write(memory, frame, &path) {
        Ok(pages) => log::warn!("RAM snapshot: {} ({pages} pages)", path.display()),
        Err(error) => log::warn!("RAM snapshot failed: {error}"),
    }
}

pub fn save(memory: &mut Memory, frame: u64) {
    let Some(folder) = std::env::var_os("KIU_RAM_SNAPSHOT").map(std::path::PathBuf::from) else { return };
    let _ = std::fs::create_dir_all(&folder);
    let path = folder.join(format!("ram-{frame:08}.bin"));
    match write(memory, frame, &path) {
        Ok(pages) => log::warn!("RAM snapshot: {} ({pages} pages)", path.display()),
        Err(error) => log::warn!("RAM snapshot failed: {error}"),
    }
}

/// Saves pages kept earlier (address, page) as a snapshot of that frame.
pub fn save_pages<'a>(pages: impl Iterator<Item = (u32, &'a [u8])>, frame: u64, folder: &std::path::Path, name: &str) {
    let _ = std::fs::create_dir_all(folder);
    let path = folder.join(format!("{name}-{frame:08}.bin"));
    let result = (|| -> std::io::Result<usize> {
        let mut out = std::io::BufWriter::new(std::fs::File::create(&path)?);
        out.write_all(b"KIURAM1\0")?;
        out.write_all(&frame.to_le_bytes())?;
        let mut written = 0;
        for (address, page) in pages {
            out.write_all(&address.to_le_bytes())?;
            out.write_all(page)?;
            written += 1;
        }
        out.flush()?;
        Ok(written)
    })();
    match result {
        Ok(pages) => log::warn!("RAM snapshot: {} ({pages} pages)", path.display()),
        Err(error) => log::warn!("RAM snapshot failed: {error}"),
    }
}

/// Copies the game memory a few pages at a time, so a whole copy is always
/// at hand without stopping a frame for it: each call takes the next slice
/// of the address space; when a pass ends it is returned whole.
#[derive(Default)]
pub struct Rolling {
    cursor: u32,
    started: u64,
    pages: Vec<(u32, Box<[u8]>)>,
}

impl Rolling {
    /// One frame's share (a pass takes `frames` frames); Some(first frame of
    /// the pass, its pages) when a pass is complete.
    pub fn step(&mut self, memory: &mut Memory, frame: u64, frames: u32) -> Option<(u64, Vec<(u32, Box<[u8]>)>)> {
        if self.cursor == 0 && self.pages.is_empty() {
            self.started = frame;
        }
        let per_frame = (0x10_0000 / frames.max(1)).max(1);
        let mut page = vec![0u8; PAGE as usize];
        for _ in 0..per_frame {
            let address = self.cursor;
            let skipped = SKIP.iter().any(|&(lo, hi)| address >= lo && address < hi);
            if !skipped && memory.is_readable(address, PAGE) {
                memory.read_bytes(address, &mut page);
                if page.iter().any(|&b| b != 0) {
                    self.pages.push((address, page.clone().into_boxed_slice()));
                }
            }
            match address.checked_add(PAGE) {
                Some(next) => self.cursor = next,
                None => {
                    self.cursor = 0;
                    return Some((self.started, std::mem::take(&mut self.pages)));
                }
            }
        }
        None
    }
}

fn write(memory: &mut Memory, frame: u64, path: &std::path::Path) -> std::io::Result<usize> {
    let mut out = std::io::BufWriter::new(std::fs::File::create(path)?);
    out.write_all(b"KIURAM1\0")?;
    out.write_all(&frame.to_le_bytes())?;
    let mut page = vec![0u8; PAGE as usize];
    let mut written = 0;
    let mut address: u32 = 0;
    loop {
        let skipped = SKIP.iter().any(|&(lo, hi)| address >= lo && address < hi);
        if !skipped && memory.is_readable(address, PAGE) {
            memory.read_bytes(address, &mut page);
            if page.iter().any(|&b| b != 0) {
                out.write_all(&address.to_le_bytes())?;
                out.write_all(&page)?;
                written += 1;
            }
        }
        match address.checked_add(PAGE) {
            Some(next) => address = next,
            None => break,
        }
    }
    out.flush()?;
    Ok(written)
}
