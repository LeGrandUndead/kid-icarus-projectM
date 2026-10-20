//! Opt-in frame-rate investigation. Observes original scheduling; never changes it.
//! KIU_FRAME_PROBE=<directory> emits per-vblank swaps and bounded wait-site summaries.
use std::{collections::BTreeMap, path::PathBuf, time::Duration};

const MAX_FRAMES: usize = 120_000;
const MAX_SITES: usize = 4096;
#[derive(Default)]
struct Site { count: u64, min: u64, max: u64 }
pub struct FrameProbe {
    root: PathBuf,
    previous: [u64; 2],
    rows: Vec<(u64, [u64; 2], f64)>,
    sites: BTreeMap<(u32, u32, u32), Site>,
}
impl FrameProbe {
    pub fn from_environment() -> Option<Self> {
        let root = PathBuf::from(std::env::var_os("KIU_FRAME_PROBE")?);
        std::fs::create_dir_all(&root).ok()?;
        Some(Self { root, previous: [0; 2], rows: Vec::with_capacity(MAX_FRAMES), sites: BTreeMap::new() })
    }
    pub fn frame(&mut self, frame: u64, swaps: [u64; 2], gpu: Duration) {
        let delta = [swaps[0].saturating_sub(self.previous[0]), swaps[1].saturating_sub(self.previous[1])];
        self.previous = swaps;
        if self.rows.len() < MAX_FRAMES { self.rows.push((frame, delta, gpu.as_secs_f64()*1000.0)); }
    }
    pub fn wait_site(&mut self, svc: u32, pc: u32, lr: u32, regs: [u32; 5]) {
        // All tick queries are recorded too: a game may busy-wait rather than sleep.
        let value = match svc {
            0x0A => regs[0] as u64 | ((regs[1] as u64)<<32),
            0x24 => regs[2] as u64 | ((regs[3] as u64)<<32),
            0x25 => regs[0] as u64 | ((regs[4] as u64)<<32),
            0x28 => 0,
            _ => return,
        };
        let key = (svc, pc, lr);
        if self.sites.len() >= MAX_SITES && !self.sites.contains_key(&key) { return; }
        let site = self.sites.entry(key).or_default();
        if site.count == 0 { site.min = value; }
        site.count += 1; site.min = site.min.min(value); site.max = site.max.max(value);
    }
    pub fn save(&self) -> std::io::Result<()> {
        use std::io::Write;
        let mut f = std::io::BufWriter::new(std::fs::File::create(self.root.join("frames.csv"))?);
        writeln!(f,"vblank,top_swaps,bottom_swaps,gpu_command_cpu_ms")?;
        for (frame, swaps, gpu) in &self.rows { writeln!(f,"{frame},{},{},{gpu:.4}",swaps[0],swaps[1])?; }
        f.flush()?;
        let mut f = std::io::BufWriter::new(std::fs::File::create(self.root.join("wait-sites.csv"))?);
        writeln!(f,"svc,pc,lr,calls,min_timeout_ns,max_timeout_ns")?;
        for ((svc,pc,lr),s) in &self.sites { writeln!(f,"{svc:02X},{pc:08X},{lr:08X},{},{},{}",s.count,s.min,s.max)?; }
        f.flush()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn swap_counts_are_deltas_and_wait_sites_keep_original_timeouts() {
        let mut p=FrameProbe { root:PathBuf::new(),previous:[0;2],rows:Vec::new(),sites:BTreeMap::new() };
        p.frame(1,[1,1],Duration::ZERO); p.frame(2,[1,1],Duration::ZERO); p.frame(3,[2,2],Duration::ZERO);
        assert_eq!(p.rows.iter().map(|r|r.1[0]).collect::<Vec<_>>(),vec![1,0,1]);
        p.wait_site(0x0A,0x100,0x200,[33_333_333,0,0,0,0]);
        p.wait_site(0x0A,0x100,0x200,[16_666_667,0,0,0,0]);
        let s=&p.sites[&(0x0A,0x100,0x200)];
        assert_eq!((s.count,s.min,s.max),(2,16_666_667,33_333_333));
        p.wait_site(0x32,0,0,[0;5]); assert_eq!(p.sites.len(),1);
    }
}
