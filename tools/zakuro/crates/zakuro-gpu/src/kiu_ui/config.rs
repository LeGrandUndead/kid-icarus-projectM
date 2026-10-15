//! PC interface options. Host settings in the preview profile
//! (`roaming/zakuro/kiu-interface.txt`), never the game's save data.
use std::sync::{Mutex, OnceLock};

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Interface {
    /// Original dialogue portraits over gameplay.
    pub portraits: bool,
    /// Lower-screen picture inserts (gags, cutaways, title cards).
    pub inserts: bool,
    /// Original special gauges / Power Palette / counters over gameplay.
    pub hud: bool,
    /// Size of the relocated HUD, 0.5 to 2.
    pub hud_scale: f32,
    /// Show the original pause panel automatically when the game pauses.
    pub auto_pause_panel: bool,
}

impl Default for Interface {
    fn default() -> Self { Self { portraits: true, inserts: true, hud: true, hud_scale: 1.0, auto_pause_panel: true } }
}

impl Interface {
    pub fn parse(text: &str) -> Self {
        let mut s = Self::default();
        for line in text.lines() {
            let Some((key, value)) = line.split_once('=') else { continue };
            let (key, value) = (key.trim(), value.trim());
            let flag = matches!(value, "1" | "true" | "on");
            match key {
                "portraits" => s.portraits = flag,
                "inserts" => s.inserts = flag,
                "hud" => s.hud = flag,
                "hud_scale" => if let Ok(v) = value.parse::<f32>() { if v.is_finite() { s.hud_scale = v.clamp(0.5, 2.0); } },
                "auto_pause_panel" => s.auto_pause_panel = flag,
                _ => {}
            }
        }
        s
    }
    pub fn text(&self) -> String {
        format!("portraits={}\ninserts={}\nhud={}\nhud_scale={}\nauto_pause_panel={}\n",
            self.portraits as u8, self.inserts as u8, self.hud as u8, self.hud_scale, self.auto_pause_panel as u8)
    }
}

fn path() -> Option<std::path::PathBuf> {
    std::env::var_os("APPDATA").map(|p| std::path::PathBuf::from(p).join("zakuro/kiu-interface.txt"))
}

fn cell() -> &'static Mutex<Interface> {
    static CELL: OnceLock<Mutex<Interface>> = OnceLock::new();
    CELL.get_or_init(|| {
        let mut value = path().and_then(|p| std::fs::read_to_string(p).ok()).map(|t| Interface::parse(&t)).unwrap_or_default();
        // A launcher switch can disable the relocated HUD for comparison.
        if std::env::var("KIU_NATIVE_HUD").as_deref() == Ok("0") { value.hud = false; }
        Mutex::new(value)
    })
}

pub fn get() -> Interface { cell().lock().map(|v| *v).unwrap_or_default() }

pub fn set(value: Interface) {
    if let Ok(mut v) = cell().lock() { *v = value; }
    if let Some(path) = path() {
        if let Some(parent) = path.parent() { let _ = std::fs::create_dir_all(parent); }
        if let Err(error) = std::fs::write(path, value.text()) { log::warn!("Could not save PC interface settings: {error}"); }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn round_trips_and_clamps() {
        let v = Interface { portraits: false, inserts: false, hud: true, hud_scale: 1.25, auto_pause_panel: false };
        assert_eq!(Interface::parse(&v.text()), v);
        assert_eq!(Interface::parse("hud_scale=9\nunknown=1").hud_scale, 2.0);
        assert_eq!(Interface::parse("hud_scale=NaN"), Interface::default());
        assert_eq!(Interface::parse(""), Interface::default());
    }
}
