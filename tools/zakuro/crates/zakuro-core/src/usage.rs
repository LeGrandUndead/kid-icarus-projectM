//! what a title asks of the runtime while it runs: the services it calls,
//! the kernel calls it makes, the GPU commands it queues, and how long the
//! host took per frame. written next to the recompiled library as
//! <library>.usage.txt with the interpreted-code census, to know what a
//! title really depends on before replacing any of it.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::time::Duration;

/// frame times are counted in buckets of this many milliseconds, up to the
/// last bucket, which takes everything longer.
const BUCKET_MS: f64 = 1.0;
const BUCKETS: usize = 101;

pub struct Usage {
    path: PathBuf,
    probe: Option<crate::frame_probe::FrameProbe>,
    /// requests per service and command id.
    pub services: BTreeMap<(String, u16), u64>,
    /// supervisor calls per number.
    pub svcs: [u64; 256],
    /// GX commands per id: DMA, command list, fill, display transfer,
    /// texture copy, cache flush.
    pub gx: [u64; 8],
    /// buffer swaps the title queued, per screen.
    pub swaps: [u64; 2],
    /// guest frames (vertical blanks) since the start.
    pub frames: u64,
    /// host time per frame, emulating and showing, in buckets.
    emulating: Histogram,
    showing: Histogram,
    /// frames the host did not show to catch up.
    pub skipped: u64,
    /// host time the GPU commands (command lists, transfers, fills) took,
    /// per guest frame: the renderer's CPU side, inside "emulating".
    gpu_commands: Histogram,
    gx_this_frame: Duration,
    /// the frame being run: when it started and the renderer's counters
    /// then, to say where a slow one's time went.
    frame_start: Option<FrameStart>,
    /// slow frames logged so far, the log stops at SLOW_FRAMES_LOGGED.
    slow_logged: u32,
}

/// a frame over this is logged with its breakdown (zakuro::slow_frame).
const SLOW_FRAME: Duration = Duration::from_millis(25);
const SLOW_FRAMES_LOGGED: u32 = 2000;

struct FrameStart {
    at: std::time::Instant,
    phases: Vec<(&'static str, u64, u64)>,
    stats: [(&'static str, u64); zakuro_gpu::stats::COUNT],
}

#[derive(Clone)]
struct Histogram {
    buckets: [u64; BUCKETS],
    total: f64,
    count: u64,
    longest: f64,
}

impl Default for Histogram {
    fn default() -> Self {
        Histogram { buckets: [0; BUCKETS], total: 0.0, count: 0, longest: 0.0 }
    }
}

impl Histogram {
    fn add(&mut self, time: Duration) {
        let ms = time.as_secs_f64() * 1e3;
        self.buckets[((ms / BUCKET_MS) as usize).min(BUCKETS - 1)] += 1;
        self.total += ms;
        self.count += 1;
        self.longest = self.longest.max(ms);
    }

    /// the time under which a share of the frames took, to a bucket.
    fn percentile(&self, share: f64) -> f64 {
        let wanted = (self.count as f64 * share).ceil() as u64;
        let mut seen = 0;
        for (i, &n) in self.buckets.iter().enumerate() {
            seen += n;
            if seen >= wanted {
                return (i + 1) as f64 * BUCKET_MS;
            }
        }
        BUCKETS as f64 * BUCKET_MS
    }

    fn line(&self, name: &str) -> String {
        if self.count == 0 {
            return format!("{name:<10} no frames\n");
        }
        format!(
            "{name:<10} mean {:.2} ms, p50 <{:.0}, p95 <{:.0}, p99 <{:.0}, longest {:.1} ms, over 16.7 ms: {}\n",
            self.total / self.count as f64,
            self.percentile(0.50),
            self.percentile(0.95),
            self.percentile(0.99),
            self.longest,
            self.buckets[17..].iter().sum::<u64>(),
        )
    }
}

impl Usage {
    pub fn new(library: &Path) -> Usage {
        Usage {
            path: library.with_extension("usage.txt"),
            probe: crate::frame_probe::FrameProbe::from_environment(),
            services: BTreeMap::new(),
            svcs: [0; 256],
            gx: [0; 8],
            swaps: [0; 2],
            frames: 0,
            emulating: Histogram::default(),
            showing: Histogram::default(),
            skipped: 0,
            gpu_commands: Histogram::default(),
            gx_this_frame: Duration::ZERO,
            frame_start: None,
            slow_logged: 0,
        }
    }

    /// a frame starts running: its clock and counters, for end_frame.
    pub fn begin_frame(&mut self) {
        self.frame_start = Some(FrameStart {
            at: std::time::Instant::now(),
            phases: zakuro_gpu::profile::totals(),
            stats: zakuro_gpu::stats::all(),
        });
    }

    /// one line for a frame over SLOW_FRAME: the renderer phases and
    /// counters that moved, the rest being the title's code and the kernel.
    fn log_slow_frame(&mut self, start: FrameStart, took: Duration) {
        if took < SLOW_FRAME || self.slow_logged >= SLOW_FRAMES_LOGGED {
            return;
        }
        self.slow_logged += 1;
        let ms = |nanos: u64| nanos as f64 / 1e6;
        let mut parts = Vec::new();
        // top-level phases only (no leading spaces in their names), the
        // nested ones are inside them
        let mut renderer = 0;
        for ((name, nanos, _), (_, before, _)) in zakuro_gpu::profile::totals().iter().zip(&start.phases) {
            let spent = nanos - before;
            if !name.starts_with(' ') {
                renderer += spent;
            }
            if spent >= 1_000_000 {
                parts.push(format!("{}: {:.1}", name.trim(), ms(spent)));
            }
        }
        for ((name, now), (_, before)) in zakuro_gpu::stats::all().iter().zip(&start.stats) {
            let moved = now - before;
            if moved == 0 {
                continue;
            }
            parts.push(if name.ends_with(" ns") { format!("{}: {:.1} ms", name.trim_end_matches(" ns"), ms(moved)) } else { format!("{name}: {moved}") });
        }
        let total = took.as_nanos() as u64;
        // a warning, like the sound running dry: it is a stutter, and the
        // headless benches log warnings only
        log::warn!(
            target: "zakuro::slow_frame",
            "frame {} took {:.1} ms: renderer {:.1}, title and kernel {:.1} | {}",
            self.frames,
            ms(total),
            ms(renderer),
            ms(total.saturating_sub(renderer)),
            parts.join(", ")
        );
    }

    pub fn service(&mut self, name: &str, command: u16) {
        match self.services.get_mut(&(name.to_owned(), command)) {
            Some(count) => *count += 1,
            None => {
                self.services.insert((name.to_owned(), command), 1);
            }
        }
    }

    pub fn wait_site(&mut self, number: u32, pc: u32, lr: u32, regs: [u32; 5]) {
        if let Some(probe) = &mut self.probe { probe.wait_site(number, pc, lr, regs); }
    }

    pub fn svc(&mut self, number: u32) {
        self.svcs[(number & 0xFF) as usize] += 1;
    }

    pub fn gx(&mut self, id: u8, took: Duration) {
        self.gx[(id as usize).min(7)] += 1;
        self.gx_this_frame += took;
    }

    /// a guest frame ended: what its GPU commands cost the host goes into
    /// the histogram.
    pub fn end_frame(&mut self) {
        self.frames += 1;
        let gpu = std::mem::take(&mut self.gx_this_frame);
        self.gpu_commands.add(gpu);
        if let Some(start) = self.frame_start.take() {
            let took = start.at.elapsed();
            self.log_slow_frame(start, took);
        }
        if let Some(probe) = &mut self.probe { probe.frame(self.frames, self.swaps, gpu); }
    }

    /// what the host spent on one frame.
    pub fn host_frame(&mut self, emulating: Option<Duration>, showing: Option<Duration>) {
        if let Some(time) = emulating {
            self.emulating.add(time);
        }
        match showing {
            Some(time) => self.showing.add(time),
            None => self.skipped += 1,
        }
    }

    /// writes the report.
    pub fn save(&self) {
        let frames = self.frames.max(1) as f64;
        let mut out = format!("# what the title used, over {} frames ({:.0} s)\n\n", self.frames, self.frames as f64 / 59.83);
        out += "# host time per frame (a 3DS frame is 16.7 ms)\n";
        out += &self.emulating.line("emulating");
        out += &self.showing.line("showing");
        out += &format!("skipped    {} frames not shown to catch up\n", self.skipped);
        out += &self.gpu_commands.line("gpu cmds");
        let particles = zakuro_gpu::stats::get(&zakuro_gpu::stats::PARTICLE_PRIMITIVES);
        let particle_ms = zakuro_gpu::stats::get(&zakuro_gpu::stats::PARTICLE_NANOS) as f64 / 1e6;
        out += &format!(
            "particles  {particles} geometry-shader particle primitives, {particle_ms:.0} ms in all, {:.3} ms a frame\n",
            particle_ms / frames
        );

        out += "\n# renderer host time by phase (inclusive), ms per frame, ms per call, calls per frame\n";
        for (name, nanos, count) in zakuro_gpu::profile::totals() {
            let ms = nanos as f64 / 1e6;
            out += &format!(
                "{name:<30} {:>7.3} {:>8.4} {:>9.2}\n",
                ms / frames,
                ms / count.max(1) as f64,
                count as f64 / frames
            );
        }

        out += "\n# why GPU images came back to guest memory: event, count\n";
        for (what, count) in zakuro_gpu::profile::events().iter().take(40) {
            out += &format!("{count:>8}  {what}\n");
        }

        out += "\n# GPU work the title queued, per frame\n";
        for (id, name) in ["dma", "command list", "memory fill", "display transfer", "texture copy", "cache flush"]
            .iter()
            .enumerate()
        {
            out += &format!("{name:<17} {:>8.2}  ({})\n", self.gx[id] as f64 / frames, self.gx[id]);
        }
        out += &format!("buffer swaps      {:>8.2} top, {:.2} bottom\n", self.swaps[0] as f64 / frames, self.swaps[1] as f64 / frames);

        out += "\n# service requests: service, command, count, per frame\n";
        let mut services: Vec<_> = self.services.iter().collect();
        services.sort_by(|a, b| b.1.cmp(a.1));
        for ((name, command), count) in services {
            out += &format!("{name:<14} 0x{command:04X} {count:>12} {:>9.3}\n", *count as f64 / frames);
        }

        out += "\n# supervisor calls: number, name, count, per frame\n";
        let mut svcs: Vec<(usize, u64)> = self.svcs.iter().copied().enumerate().filter(|&(_, n)| n > 0).collect();
        svcs.sort_by(|a, b| b.1.cmp(&a.1));
        for (number, count) in svcs {
            out += &format!("0x{number:02X} {:<24} {count:>12} {:>9.2}\n", svc_name(number), count as f64 / frames);
        }
        if let Some(probe) = &self.probe {
            if let Err(error) = probe.save() { log::warn!("frame probe: {error}"); }
        }
        if let Err(error) = std::fs::write(&self.path, out) {
            log::warn!("could not write {}, {error}", self.path.display());
        }
    }
}

fn svc_name(number: usize) -> &'static str {
    match number {
        0x01 => "ControlMemory",
        0x02 => "QueryMemory",
        0x03 => "ExitProcess",
        0x08 => "CreateThread",
        0x09 => "ExitThread",
        0x0A => "SleepThread",
        0x0B => "GetThreadPriority",
        0x0C => "SetThreadPriority",
        0x11 => "GetCurrentProcessorNumber",
        0x13 => "CreateMutex",
        0x14 => "ReleaseMutex",
        0x15 => "CreateSemaphore",
        0x16 => "ReleaseSemaphore",
        0x17 => "CreateEvent",
        0x18 => "SignalEvent",
        0x19 => "ClearEvent",
        0x1A => "CreateTimer",
        0x1B => "SetTimer",
        0x1C => "CancelTimer",
        0x1D => "ClearTimer",
        0x1E => "CreateMemoryBlock",
        0x1F => "MapMemoryBlock",
        0x20 => "UnmapMemoryBlock",
        0x21 => "CreateAddressArbiter",
        0x22 => "ArbitrateAddress",
        0x23 => "CloseHandle",
        0x24 => "WaitSynchronization1",
        0x25 => "WaitSynchronizationN",
        0x27 => "DuplicateHandle",
        0x28 => "GetSystemTick",
        0x2A => "GetSystemInfo",
        0x2B => "GetProcessInfo",
        0x2D => "ConnectToPort",
        0x32 => "SendSyncRequest",
        0x35 => "GetProcessId",
        0x37 => "GetThreadId",
        0x38 => "GetResourceLimit",
        0x39 => "GetResourceLimitLimitValues",
        0x3A => "GetResourceLimitCurrentValues",
        0x3C => "Break",
        0x3D => "OutputDebugString",
        _ => "",
    }
}
