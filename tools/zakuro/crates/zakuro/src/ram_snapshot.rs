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
