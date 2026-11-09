//! Reads the game library, then the ROM image, once, start to end, on a
//! background thread when a game starts.
//!
//! Both are mapped into memory and used on the emulation thread: the
//! library's code is paged in the first time each part runs, and the game's
//! file reads copy from the mapped ROM. What is not yet in the system's file
//! cache comes off the disk right there, during the frame.
//!
//! - October 28: on a cold cache, loading a new area stalled frames for
//!   100-300 ms (280 slow frames, all "title and kernel", around area
//!   loads; none on the next run, with the ROM cached).
//! - November 9: with only the ROM read ahead, a cold start still had 130
//!   frames over 100 ms in its first minute, all "title and kernel" and
//!   most after the ROM was done: the 425 MB library's code. And the boot
//!   took 22 s longer, the ROM's 20 s read competing for the disk with the
//!   pages the boot needed.
//!
//! So the library goes first, as fast as the disk gives it (a few seconds,
//! and what the boot needs), then the ROM at the system's background
//! priority, which lets the game's own reads go ahead of it. One sequential
//! pass is what a disk does fastest. It only reads; nothing is kept but the
//! system's own cache.

use std::io::Read;
use std::path::{Path, PathBuf};

pub fn start(library: Option<PathBuf>, rom: PathBuf) {
    let spawned = std::thread::Builder::new().name("prefetch".into()).spawn(move || {
        if let Some(library) = library {
            read("game library", &library);
        }
        background_priority();
        read("ROM", &rom);
    });
    if let Err(error) = spawned {
        log::warn!("prefetch not started: {error}");
    }
}

fn read(what: &str, path: &Path) {
    let started = std::time::Instant::now();
    let Ok(mut file) = std::fs::File::open(path) else { return };
    let mut buffer = vec![0u8; 1 << 20];
    let mut total = 0u64;
    loop {
        match file.read(&mut buffer) {
            Ok(0) => break,
            Ok(read) => total += read as u64,
            Err(error) => {
                log::warn!("{what} prefetch stopped: {error}");
                return;
            }
        }
    }
    log::info!("{what} prefetched: {} MiB in {:.1} s", total >> 20, started.elapsed().as_secs_f64());
}

/// from here on this thread's disk reads wait for everyone else's.
#[cfg(windows)]
fn background_priority() {
    #[link(name = "kernel32")]
    extern "system" {
        fn GetCurrentThread() -> isize;
        fn SetThreadPriority(thread: isize, priority: i32) -> i32;
    }
    const THREAD_MODE_BACKGROUND_BEGIN: i32 = 0x0001_0000;
    // SAFETY: both take and return plain values, for the calling thread.
    if unsafe { SetThreadPriority(GetCurrentThread(), THREAD_MODE_BACKGROUND_BEGIN) } == 0 {
        log::warn!("the ROM is prefetched at normal priority, background priority was refused");
    }
}

#[cfg(not(windows))]
fn background_priority() {}
