//! Where the emulated CPU's time goes, once a second, to
//! `build/diagnostics/thread-time.log` (overwritten each run). For stalls
//! that depend on another thread getting through its work, such as the
//! white flash that sometimes lasts long after a warp: a loading thread
//! that hardly runs shows here. F4 writes a marker line ("noticed here").

use std::io::Write;

use crate::kernel::thread::ThreadId;

/// frames per line, about a second
const PERIOD: u64 = 60;

pub struct ThreadTime {
    file: Option<std::fs::File>,
    /// cycles per thread id since the last line, and while nothing ran
    cycles: Vec<u64>,
    idle: u64,
    frames: u64,
}

impl ThreadTime {
    pub fn open() -> Self {
        let dir = std::path::Path::new("build/diagnostics");
        let file = std::fs::create_dir_all(dir).ok().and_then(|_| std::fs::File::create(dir.join("thread-time.log")).ok());
        Self { file, cycles: Vec::new(), idle: 0, frames: 0 }
    }

    pub fn add(&mut self, thread: Option<ThreadId>, cycles: u64) {
        match thread {
            Some(id) => {
                let id = id as usize;
                if self.cycles.len() <= id { self.cycles.resize(id + 1, 0); }
                self.cycles[id] += cycles;
            }
            None => self.idle += cycles,
        }
    }

    pub fn mark(&mut self, frame: u64, what: &str) {
        if let Some(file) = &mut self.file { let _ = writeln!(file, "frame {frame}: --- {what} ---"); let _ = file.flush(); }
    }

    /// After every emulated frame: a line each period.
    pub fn end_frame(&mut self, frame: u64, threads: &[crate::kernel::thread::Thread]) {
        self.frames += 1;
        if self.frames < PERIOD { return; }
        self.frames = 0;
        let total = (self.cycles.iter().sum::<u64>() + self.idle).max(1) as f64;
        let mut line = format!("frame {frame}: idle {:.0}%", self.idle as f64 * 100.0 / total);
        for (id, &cycles) in self.cycles.iter().enumerate() {
            let share = cycles as f64 * 100.0 / total;
            if share < 0.5 { continue; }
            let (priority, core, entry) = threads.get(id).map_or((0, 0, 0), |t| (t.priority, t.processor_id, t.entry));
            line += &format!(" | t{id} p{priority:#04X} core{core} @{entry:08X} {share:.0}%");
        }
        // threads ready to run that did not run at all this period
        let starved: Vec<String> = threads.iter().filter(|t| t.is_runnable() && self.cycles.get(t.id as usize).copied().unwrap_or(0) == 0)
            .map(|t| format!("t{}", t.id)).collect();
        if !starved.is_empty() { line += &format!(" | ready but did not run: {}", starved.join(",")); }
        if let Some(file) = &mut self.file { let _ = writeln!(file, "{line}"); let _ = file.flush(); }
        self.cycles.iter_mut().for_each(|c| *c = 0);
        self.idle = 0;
    }
}
