//! Opt-in traces of the exact input passed to the guest after controller merging.
use std::fs::File;
use std::io::{BufWriter, Write};
use zakuro_core::services::hid::InputState;

pub struct InputTrace { writer: BufWriter<File>, failed: bool }
impl InputTrace {
    pub fn from_environment() -> Option<Self> {
        let path = std::env::var_os("KIU_INPUT_TRACE")?;
        match File::create(&path) {
            Ok(file) => {
                let mut writer = BufWriter::new(file);
                if writeln!(writer, "frame,mouse_dx,mouse_dy,captured,replay,touch_down,touch_x,touch_y,circle_x,circle_y,buttons,adapter").is_err() {
                    return None;
                }
                log::info!("input trace: {}", std::path::Path::new(&path).display());
                Some(Self { writer, failed: false })
            }
            Err(error) => { log::warn!("cannot create input trace: {error}"); None }
        }
    }
    pub fn sample(&mut self, frame: u64, raw: [f32; 2], captured: bool, input: InputState, replay: bool, _bounded: bool) {
        if self.failed { return; }
        let (x, y) = input.touch.unwrap_or_default();
        let result = writeln!(self.writer, "{frame},{},{},{captured},{replay},{},{x},{y},{},{},{},bounded",
            raw[0], raw[1], input.touch.is_some(), input.circle_x, input.circle_y, input.buttons.bits())
            .and_then(|_| if frame.is_multiple_of(60) { self.writer.flush() } else { Ok(()) });
        if let Err(error) = result {
            log::warn!("input trace disabled after write failure: {error}");
            self.failed = true;
        }
    }
}
