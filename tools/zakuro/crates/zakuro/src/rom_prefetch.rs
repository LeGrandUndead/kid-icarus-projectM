//! Reads the ROM image once, start to end, on a background thread when a
//! game starts.
//!
//! The runtime maps the ROM file into memory and the game's file reads copy
//! from that mapping on the emulation thread. Pages not yet in the system's
//! file cache are read from disk right there, during the frame: on a cold
//! cache (the first run after a rebuild, which pushes the ROM out of memory)
//! loading a new area stalled frames for 100-300 ms (October 28 log: 280
//! slow frames, all "title and kernel", around area loads; the next run,
//! with the file cached, had none). One sequential pass up front, which a
//! disk does fastest, puts the whole image in the cache before the game
//! asks for it. It only reads; nothing is kept but the system's own cache.

use std::io::Read;
use std::path::PathBuf;

pub fn start(path: PathBuf) {
    let spawned = std::thread::Builder::new().name("rom prefetch".into()).spawn(move || {
        let started = std::time::Instant::now();
        let Ok(mut file) = std::fs::File::open(&path) else { return };
        let mut buffer = vec![0u8; 8 << 20];
        let mut total = 0u64;
        loop {
            match file.read(&mut buffer) {
                Ok(0) => break,
                Ok(read) => total += read as u64,
                Err(error) => {
                    log::warn!("ROM prefetch stopped: {error}");
                    return;
                }
            }
        }
        log::info!("ROM prefetched: {} MiB in {:.1} s", total >> 20, started.elapsed().as_secs_f64());
    });
    if let Err(error) = spawned {
        log::warn!("ROM prefetch not started: {error}");
    }
}
