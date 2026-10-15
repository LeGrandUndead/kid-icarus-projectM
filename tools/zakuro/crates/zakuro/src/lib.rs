//! Zakuro's frontend, a window showing the library of games or a game with
//! a menu over it, and the loop that drives the emulated console one frame
//! at a time.

mod audio;
mod cli;
mod gamepad;
mod gui;
mod input;
mod input_trace;
mod library;
mod menus;
mod present;
mod pc_presentation;
mod ram_snapshot;
mod kiu_jump;
mod recompile;
mod report;
mod settings;

use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use winit::application::ApplicationHandler;
use winit::event::{DeviceEvent, DeviceId, ElementState, KeyEvent, MouseButton, MouseScrollDelta, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{KeyCode, PhysicalKey};
use winit::window::{CursorGrabMode, Fullscreen, Window, WindowId};

use zakuro_common::Screen;
use zakuro_core::{loader, Config, FrameOutcome, System};
use zakuro_gpu::{layout, GpuScreen, Overlay, PresentError, RendererKind, ScreenImage};

use gui::Gui;
use input::Keyboard;
use library::Library;
use menus::{Action, Menus};
use present::Backend;
use recompile::{Job, Stage};
use settings::{Renderer, Screens, Settings};

pub use zakuro_core::recompiled::Linked;

/// runs the emulator as the command line says, on recompiled code linked
/// into the program when there is some.
pub fn run(linked: Option<Linked>) {
    report::init();

    let options = match cli::parse() {
        Ok(options) => options,
        Err(message) => {
            eprintln!("zakuro: {message}");
            std::process::exit(2);
        }
    };
    let mut settings = Settings::load();
    let pc_display = std::env::var("KIU_PC_DISPLAY").as_deref() == Ok("1080p");
    if pc_display { settings.layout = Screens::TopOnly; }
    // KIU's temporary PC-native control layer is opt-in so this frontend can
    // still run other titles unchanged. The KIU launcher enables it.
    let pc_controls = std::env::var_os("KIU_PC_CONTROLS").is_some();
    let mouse_sensitivity = std::env::var("KIU_MOUSE_SENSITIVITY")
        .ok()
        .and_then(|value| value.parse::<f32>().ok())
        .unwrap_or(0.55)
        .clamp(0.05, 4.0);
    let walk_strength = std::env::var("KIU_WALK_STRENGTH")
        .ok()
        .and_then(|value| value.parse::<f32>().ok())
        .unwrap_or(0.60)
        .clamp(0.51, 0.95);
    let mut keyboard = Keyboard::new(settings.keys.clone());
    keyboard.set_pc_mode(pc_controls, walk_strength);

    let data_dir = options.data.clone().map(PathBuf::from).or_else(default_data_dir);
    if let Some(dir) = &data_dir {
        report::to_file(dir);
        bring_saves(dir);
    }

    let mut app = App {
        keyboard,
        gamepads: gamepad::Gamepads::new(settings.pad.clone()),
        scale: options.scale.unwrap_or(settings.scale).max(1),
        layout: settings.layout,
        options,
        settings,
        linked,
        data_dir,
        game: None,
        library: Library::default(),
        menus: Menus::default(),
        jobs: Vec::new(),
        gui: None,
        backend: None,
        window: None,
        audio: None,
        mouse_down: false,
        tilting_from: None,
        cursor: (0.0, 0.0),
        pc_controls,
        mouse_captured: false,
        presentation: pc_presentation::PcPresentation::new(std::env::var_os("KIU_SINGLE_SCREEN").is_some()),
        pc_display,
        experimental_wide: std::env::var_os("KIU_EXPERIMENTAL_WIDE").is_some(),
        experimental_air: std::env::var_os("KIU_EXPERIMENTAL_AIR").is_some(),
        mouse_sensitivity,
        input_trace: input_trace::InputTrace::from_environment(),
        last_title_update: Instant::now(),
        next_frame: Instant::now(),
        skipped: 0,
        shown: 0,
        spent: Spent::default(),
        paused: false,
        stop: false,
        maximized_before_full_screen: false,
        resize_after_full_screen: false,
        land_publications: 0,
        land_seen: None,
        space_jump: kiu_jump::SpaceJump::default(),
    };

    if let Some(frames) = app.options.headless {
        app.start();
        if let Some(game) = &mut app.game {
            run_headless(&mut game.system, frames);
        }
        return;
    }

    if let Some(folder) = app.settings.games.clone() {
        app.library.scan(&folder);
    }
    app.audio = if app.options.mute {
        None
    } else {
        audio::Audio::open(zakuro_core::AUDIO_SAMPLE_RATE).inspect_err(|error| log::warn!("no sound, {error}")).ok()
    };
    app.apply_volume();

    let event_loop = EventLoop::new().expect("create an event loop");
    event_loop.set_control_flow(ControlFlow::Poll);
    if let Err(error) = event_loop.run_app(&mut app) {
        eprintln!("zakuro: {error}");
    }
}

/// the system's place for a program's data.
fn default_data_dir() -> Option<PathBuf> {
    let var = |name: &str| std::env::var_os(name).filter(|value| !value.is_empty()).map(PathBuf::from);
    let dir = if cfg!(windows) {
        var("APPDATA")
    } else if cfg!(target_os = "macos") {
        var("HOME").map(|home| home.join("Library/Application Support"))
    } else {
        var("XDG_DATA_HOME").or_else(|| var("HOME").map(|home| home.join(".local/share")))
    };
    dir.map(|dir| dir.join("zakuro"))
}

/// saves Zakuro kept in the working directory before it had a place for
/// them, copied there the first time. the old ones stay as they were.
fn bring_saves(data: &Path) {
    let (old, new) = (Path::new("user"), data.join("user"));
    if new.exists() || !old.is_dir() {
        return;
    }
    // a copy cut short is left under another name, and tried again
    let partial = data.join("user.copying");
    let copied = std::fs::remove_dir_all(&partial)
        .or_else(|error| if error.kind() == std::io::ErrorKind::NotFound { Ok(()) } else { Err(error) })
        .and_then(|()| copy_dir(old, &partial))
        .and_then(|()| std::fs::rename(&partial, &new));
    match copied {
        Ok(()) => log::info!("copied the saves in ./user to {}, the old ones stay as they were", new.display()),
        Err(error) => log::warn!("could not copy the saves in ./user to {}, {error}", new.display()),
    }
}

fn copy_dir(from: &Path, to: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(to)?;
    for entry in std::fs::read_dir(from)? {
        let entry = entry?;
        let target = to.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir(&entry.path(), &target)?;
        } else {
            std::fs::copy(entry.path(), target)?;
        }
    }
    Ok(())
}

/// builds a System with no title loaded and both screens filled with a
/// solid color, to check the presentation path (framebuffer config -> guest
/// memory -> window) in isolation from any title's boot logic.
fn paint_test_pattern(config: Config) -> System {
    use zakuro_core::memory::{MemoryRegion, MemoryState, Permission};

    let mut system = System::new(config);

    // ABGR in memory for format 0 (Rgba8), red = 00 00 00 FF?
    let paint = |system: &mut System, screen: Screen, rgba: [u8; 4]| {
        let width = screen.width();
        let height = screen.height();
        let stride = height * 4;
        let size = stride * width;

        let block = system
            .memory
            .phys
            .allocate(MemoryRegion::Base, size)
            .expect("allocate test pattern framebuffer");

        let vaddr = zakuro_core::services::gsp::physical_to_virtual(system, block.addr);
        system.memory.map(
            vaddr,
            block.addr,
            size,
            Permission::READ | Permission::WRITE,
            MemoryState::Shared,
        );

        let mut pixel = [0u8; 4];
        pixel[3] = rgba[0]; // r
        pixel[2] = rgba[1]; // g
        pixel[1] = rgba[2]; // b
        pixel[0] = rgba[3]; // a
        let mut data = Vec::with_capacity(size as usize);
        for _ in 0..(size / 4) {
            data.extend_from_slice(&pixel);
        }
        system.memory.write_physical(block.addr, &data);

        let index = match screen {
            Screen::Top => 0,
            Screen::Bottom => 1,
        };
        system.set_framebuffer(index, 0, block.addr, block.addr, stride, 0);
    };

    paint(&mut system, Screen::Top, [220, 40, 40, 255]); // red
    paint(&mut system, Screen::Bottom, [40, 90, 220, 255]); // blue
    system
}

fn run_headless(system: &mut System, frames: u64) {
    let start = Instant::now();
    let mut outcome = FrameOutcome::Completed;
    let mut ran = 0;
    for _ in 0..frames {
        outcome = system.run_frame();
        ran += 1;
        if outcome != FrameOutcome::Completed {
            break;
        }
    }
    let elapsed = start.elapsed();
    println!("{outcome:?} after {ran} frames in {elapsed:.2?}");
    println!(
        "{:.1} MIPS, {}",
        system.cpu.cycles as f64 / elapsed.as_secs_f64() / 1e6,
        system.status_line()
    );
    if !system.fatal_errors.is_empty() {
        println!("fatal errors: {}", system.fatal_errors.join("; "));
    }
    for (thread, pc, hits) in system.hot_spots(10) {
        println!("  hot {thread:<8} 0x{pc:08X} {hits}");
    }
}

/// a game being played.
struct Running {
    system: System,
    path: PathBuf,
    name: String,
    /// the inputs written down, ZAKURO_RECORD=file, for playing the run
    /// back.
    recorder: Option<zakuro_core::replay::Recorder>,
    /// the inputs a recording wrote down, ZAKURO_REPLAY=file, played back in
    /// place of the keyboard's and the controllers', and the frames run.
    replay: Option<zakuro_core::replay::Replay>,
    frame: u64,
    /// frames run since counting_since, for the frame rate.
    frames: u32,
    counting_since: Instant,
    fps: f32,
}

impl Running {
    fn new(system: System, path: PathBuf, name: String) -> Running {
        Running {
            system,
            path,
            name,
            recorder: None,
            replay: None,
            frame: 0,
            frames: 0,
            counting_since: Instant::now(),
            fps: 0.0,
        }
    }

    fn count_frame(&mut self) {
        self.frames += 1;
        let elapsed = self.counting_since.elapsed();
        if elapsed >= Duration::from_millis(500) {
            self.fps = self.frames as f32 / elapsed.as_secs_f32();
            self.frames = 0;
            self.counting_since = Instant::now();
        }
    }
}

struct App {
    options: cli::Options,
    settings: Settings,
    linked: Option<Linked>,
    data_dir: Option<PathBuf>,
    game: Option<Running>,
    library: Library,
    menus: Menus,
    jobs: Vec<Job>,
    gui: Option<Gui>,
    // backend must be declared (and therefore dropped) before window, Rust
    // drops struct fields in declaration order, and the GL surface's Drop
    // calls eglDestroySurface, which on Wayland does a protocol round-trip
    // against the window's wl_surface.
    backend: Option<Backend>,
    window: Option<Window>,
    keyboard: Keyboard,
    gamepads: gamepad::Gamepads,
    audio: Option<audio::Audio>,
    /// the window's size, times the console's.
    scale: u32,
    /// how the screens are arranged.
    layout: Screens,
    /// the left button is down, and where the pointer is, in window pixels.
    mouse_down: bool,
    /// where the pointer was when the right button went down, which tilts
    /// the console while held.
    tilting_from: Option<(f32, f32)>,
    cursor: (f32, f32),
    /// KIU-specific temporary PC control mode. The eventual project runtime
    /// will own this rather than exposing Zakuro's generic bindings.
    pc_controls: bool,
    mouse_captured: bool,
    /// Temporary bottom-screen access; never persists a layout change.
    presentation: pc_presentation::PcPresentation,
    pc_display: bool,
    experimental_wide: bool,
    experimental_air: bool,
    mouse_sensitivity: f32,
    input_trace: Option<input_trace::InputTrace>,
    last_title_update: Instant,
    /// when the next frame is due. frames run to a schedule rather than one
    /// after another, so that a slow one is made up by those after it and
    /// the sound, made as the console runs, keeps up.
    next_frame: Instant,
    /// frames in a row not shown while catching up.
    skipped: u32,
    /// frames shown since the title was last updated.
    shown: u32,
    /// how long emulating and showing frames took since the title was last
    /// updated, for the frame rate's log.
    spent: Spent,
    /// stopped with F1, without the menu.
    paused: bool,
    stop: bool,
    /// the window was maximized when it went full screen, which leaving
    /// full screen brings back.
    maximized_before_full_screen: bool,
    /// the layout or the scale changed while the window was full screen,
    /// which kept its size, so leaving full screen fits the window to them.
    resize_after_full_screen: bool,
    /// KIU land detection for wheel power selection: the land camera hook's
    /// counter and the last frame land gameplay (or the Power Palette) was seen.
    land_publications: u64,
    land_seen: Option<u64>,
    /// KIU: Space uses the equipped Sky Jump (kiu_jump.rs).
    space_jump: kiu_jump::SpaceJump,
}

/// how long each step of the loop took, its mean and its longest.
#[derive(Default)]
struct Spent {
    emulating: Times,
    showing: Times,
}

#[derive(Default)]
struct Times {
    total: Duration,
    longest: Duration,
    count: u32,
}

impl Times {
    fn add(&mut self, time: Duration) {
        self.total += time;
        self.longest = self.longest.max(time);
        self.count += 1;
    }
}

impl std::fmt::Display for Times {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mean = self.total.as_secs_f64() * 1e3 / self.count.max(1) as f64;
        write!(f, "{mean:.1} ms, at most {:.1}", self.longest.as_secs_f64() * 1e3)
    }
}

/// one 3DS frame, about 16.71 ms.
const FRAME_TIME: Duration =
    Duration::from_nanos(zakuro_core::CYCLES_PER_FRAME * 1_000_000_000 / zakuro_core::kernel::thread::CPU_CLOCK_HZ);
/// how far behind the schedule may fall before it starts over instead of
/// running fast to catch up, after a pause say.
const CATCH_UP_LIMIT: Duration = Duration::from_millis(200);
/// frames that may go unshown in a row while catching up.
const MAX_SKIPPED: u32 = 4;

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.window.is_some() {
            return;
        }

        let size = self.window_size();
        let attributes = Window::default_attributes().with_title("Zakuro").with_inner_size(size);
        let renderer = self.options.renderer.unwrap_or(match self.settings.renderer {
            Renderer::Vulkan => RendererKind::Vulkan,
            Renderer::OpenGl => RendererKind::OpenGl,
        });

        let backend = Backend::create(event_loop, attributes.clone(), renderer).or_else(|error| {
            if renderer != RendererKind::Vulkan {
                return Err(error);
            }
            // a machine without a working Vulkan driver still gets a window
            log::warn!("could not start the Vulkan backend, {error}, presenting with OpenGL instead");
            Backend::create(event_loop, attributes, RendererKind::OpenGl)
        });
        match backend {
            Ok((window, mut backend)) => {
                log::info!("presenting with the {} backend", backend.name());
                backend.set_layout(self.presentation.layout(self.layout, self.experimental_wide));
                self.gui = Some(Gui::new(&window));
                self.window = Some(window);
                self.backend = Some(backend);
                // the game the command line names starts on the device the
                // presenter may lend the renderer, once there is one
                self.start();
            }
            Err(error) => {
                eprintln!("zakuro: could not start the {renderer:?} backend: {error}");
                event_loop.exit();
            }
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let consumed = match (&mut self.gui, &self.window) {
            (Some(gui), Some(window)) => gui.event(window, &event),
            _ => false,
        };
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::Focused(false) => {
                self.presentation.focus_lost();
                self.set_mouse_capture(false);
                self.keyboard.release();
                self.mouse_down = false;
                self.tilting_from = None;
            }
            WindowEvent::Resized(size) => {
                if let Some(backend) = &mut self.backend {
                    backend.resize(size.width, size.height);
                }
            }
            WindowEvent::KeyboardInput { event, .. } => self.key(event, consumed),
            WindowEvent::MouseInput { state, button, .. } => {
                if button == MouseButton::Left {
                    let pressed = state == ElementState::Pressed;
                    if self.pc_controls && self.mouse_captured {
                        self.keyboard.pc_attack(pressed);
                    } else {
                        self.mouse_down = pressed && !self.pointer_taken(consumed);
                        self.touch();
                    }
                }
                if button == MouseButton::Right && !(self.pc_controls && self.mouse_captured) {
                    let pressed = state == ElementState::Pressed && !self.pointer_taken(consumed);
                    self.tilting_from = pressed.then_some(self.cursor);
                    self.tilt();
                }
            }
            WindowEvent::CursorMoved { position, .. } => {
                self.cursor = (position.x as f32, position.y as f32);
                if !self.mouse_captured {
                    self.touch();
                    self.tilt();
                }
            }
            WindowEvent::MouseWheel { delta, .. } => {
                let playing = self.game.is_some() && !self.menus.menu_open && !self.menus.settings_open;
                if self.pc_controls && self.mouse_captured && playing && self.settings.kiu_wheel_powers {
                    let up = match delta {
                        MouseScrollDelta::LineDelta(_, y) => y,
                        // touchpads and smooth wheels: about 40 px per notch
                        MouseScrollDelta::PixelDelta(position) => (position.y / 40.0) as f32,
                    };
                    // wheel down selects the next power unless reversed
                    self.keyboard.pc_wheel(if self.settings.kiu_wheel_reverse { up } else { -up });
                }
            }
            WindowEvent::RedrawRequested => self.step(event_loop),
            _ => {}
        }
    }

    fn device_event(&mut self, _event_loop: &ActiveEventLoop, _device_id: DeviceId, event: DeviceEvent) {
        if !(self.pc_controls && self.mouse_captured) {
            return;
        }
        if self.game.is_none() || self.menus.menu_open || self.menus.settings_open {
            return;
        }
        if let DeviceEvent::MouseMotion { delta: (dx, dy) } = event {
            self.keyboard.pc_mouse_motion(dx as f32, dy as f32);
        }
    }

    fn about_to_wait(&mut self, _event_loop: &ActiveEventLoop) {
        if let Some(window) = &self.window {
            window.request_redraw();
        }
    }
}

impl App {
    /// the console's settings for a game, from the command line and the
    /// settings.
    fn config(&self) -> Config {
        let interpret = self.options.interpreter || !self.settings.recompiled;
        Config {
            new3ds: self.options.new3ds,
            data_dir: self.data_dir.clone(),
            recompiled: self.options.recompiled.clone().filter(|_| !interpret).map(Into::into),
            linked: self.linked.filter(|_| !interpret),
            find_recompiled: !interpret,
            hardware_renderer: self.options.hardware_rasterizer.unwrap_or(self.settings.hardware_rasterizer),
            resolution: self.options.resolution.unwrap_or(self.settings.resolution),
            device: self.backend.as_ref().and_then(Backend::shared_device),
            ..Config::default()
        }
    }

    /// starts what the command line asks for, the test pattern or a game.
    fn start(&mut self) {
        if self.options.test_pattern {
            // the test pattern has no CPU program to run, paused keeps just
            // presenting what is there
            let system = paint_test_pattern(self.config());
            self.game = Some(Running::new(system, PathBuf::new(), "test pattern".to_owned()));
            self.paused = true;
        } else if let Some(rom) = self.options.rom.clone() {
            if let Err(error) = self.play(Path::new(&rom)) {
                eprintln!("zakuro: {error}");
                std::process::exit(1);
            }
        }
        if self.options.profile {
            if let Some(game) = &mut self.game {
                game.system.enable_profiler();
            }
        }
    }

    /// starts the game at path, in place of any other.
    fn play(&mut self, path: &Path) -> Result<(), String> {
        // the old game and what it holds on the GPU go first, its sound too
        self.game = None;
        if let Some(audio) = &self.audio {
            audio.clear();
        }
        let mut config = self.config();
        // a recording starts the clock at a known time, for playing it back
        let record = std::env::var_os("ZAKURO_RECORD").map(PathBuf::from);
        let clock = zakuro_core::memory::config::host_clock();
        if record.is_some() {
            config.clock = Some(clock);
        }
        // and plays back from the clock it was made at
        let replay = match std::env::var_os("ZAKURO_REPLAY").map(PathBuf::from) {
            Some(file) => {
                let replay = zakuro_core::replay::Replay::open(&file).map_err(|error| format!("could not read {}, {error}", file.display()))?;
                log::info!("playing back the inputs in {}", file.display());
                config.clock = Some(replay.clock());
                Some(replay)
            }
            None => None,
        };
        let system = loader::load(path, config).map_err(|error| format!("could not open {}, {error}", path.display()))?;
        let name = self
            .library
            .games
            .iter()
            .find(|game| game.path == path)
            .map(|game| game.name.clone())
            .or_else(|| path.file_stem().map(|stem| stem.to_string_lossy().into_owned()))
            .unwrap_or_default();
        let mut game = Running::new(system, path.to_owned(), name);
        game.replay = replay;
        if let Some(record) = record {
            match zakuro_core::replay::Recorder::create(&record, clock) {
                Ok(recorder) => {
                    log::info!("recording the inputs to {}", record.display());
                    game.recorder = Some(recorder);
                }
                Err(error) => log::warn!("could not record to {}, {error}", record.display()),
            }
        }
        self.game = Some(game);
        self.menus.menu_open = false;
        self.set_mouse_capture(false);
        self.keyboard.release();
        self.paused = false;
        self.next_frame = Instant::now();
        Ok(())
    }

    fn back_to_library(&mut self) {
        self.close_screen_access(false);
        self.game = None;
        if let Some(audio) = &self.audio {
            audio.clear();
        }
        self.menus.menu_open = false;
        self.set_mouse_capture(false);
        self.keyboard.release();
    }

    fn key(&mut self, event: KeyEvent, consumed: bool) {
        let pressed = event.state == ElementState::Pressed;
        let PhysicalKey::Code(code) = event.physical_key else { return };
        // Escape leaves a controller binding waiting for a button as it was
        if pressed && code == KeyCode::Escape && self.menus.rebinding_pad.take().is_some() {
            return;
        }
        // a binding waiting for a key takes it, Escape leaves it as it was
        if let (true, Some(index)) = (pressed, self.menus.rebinding) {
            self.menus.rebinding = None;
            if code != KeyCode::Escape {
                if let Some((_, key)) = self.settings.keys.all_mut().into_iter().nth(index) {
                    *key = code;
                }
                self.apply_settings();
            }
            return;
        }
        if pressed && !event.repeat {
            match code {
                KeyCode::Tab if self.pc_controls && self.game.is_some()
                    && !self.menus.menu_open && !self.menus.settings_open
                    && !self.gui.as_ref().is_some_and(Gui::wants_keyboard) => {
                    if self.presentation.access.is_some() { self.close_screen_access(true); }
                    else { self.open_screen_access(); }
                    return;
                }
                KeyCode::Escape | KeyCode::F2 if self.presentation.access.is_some() => {
                    self.close_screen_access(true);
                    return;
                }
                KeyCode::Escape if self.mouse_captured => {
                    // First Escape releases the mouse. A second one opens the
                    // runtime menu, like native PC games.
                    self.set_mouse_capture(false);
                    return;
                }
                KeyCode::Escape if self.game.is_some() => {
                    self.menus.menu_open = !self.menus.menu_open;
                    self.keyboard.release();
                    return;
                }
                KeyCode::F2 if self.pc_controls && self.game.is_some() => {
                    self.set_mouse_capture(!self.mouse_captured);
                    return;
                }
                KeyCode::F1 => {
                    self.paused = !self.paused;
                    log::info!("{}", if self.paused { "paused" } else { "resumed" });
                }
                KeyCode::F7 if std::env::var_os("KIU_RAM_SNAPSHOT").is_some() => {
                    if let Some(game) = &mut self.game {
                        ram_snapshot::save(&mut game.system.memory, game.frame);
                    }
                    return;
                }
                KeyCode::F8 if std::env::var_os("KIU_RENDER_CAPTURE").is_some() => {
                    zakuro_gpu::start_render_capture();
                    return;
                }
                KeyCode::F9 if self.presentation.enabled => {
                    self.close_screen_access(false);
                    self.presentation.boundary = true;
                    self.set_mouse_capture(false);
                    self.keyboard.release();
                    self.presentation.legacy = !self.presentation.legacy;
                    self.show_layout(self.layout);
                    return;
                }
                KeyCode::F10 if self.presentation.enabled => { return; }
                KeyCode::F9 => {
                    self.close_screen_access(false);
                    self.settings.layout = self.settings.layout.next();
                    self.settings.save();
                    self.apply_layout();
                }
                KeyCode::F10 if self.settings.layout.other_screen() != self.settings.layout => {
                    self.close_screen_access(false);
                    self.settings.layout = self.settings.layout.other_screen();
                    self.settings.save();
                    self.apply_layout();
                }
                KeyCode::F11 => self.toggle_fullscreen(),
                _ => {}
            }
        }
        let to_game = self.game.is_some()
            && !self.menus.menu_open
            && !self.menus.settings_open
            && !consumed
            && !self.gui.as_ref().is_some_and(Gui::wants_keyboard);
        // The KIU PC movement mapping consumes WASD/Shift so it does not
        // also hit Zakuro's stock A/Y and W/R bindings. Letting go still
        // gets through even if the menu opened meanwhile.
        let pointer_menu = self.presentation.enabled && self.presentation.context(self.mouse_captured, !to_game) == pc_presentation::InputContext::PointerMenu;
        if self.presentation.enabled && event.repeat { return; }
        if self.pc_controls && self.mouse_captured && to_game && code == self.settings.keys.pc_jump && self.settings.kiu_space_jump {
            if pressed && !event.repeat { self.space_jump.request(); }
            return;
        }
        let pc_key = self.pc_controls && !pointer_menu && (to_game || !pressed) && self.keyboard.pc_key(event.physical_key, pressed);
        if !pc_key && (to_game || !pressed) {
            self.keyboard.key(event.physical_key, pressed);
        }
    }

    /// takes in the controllers' buttons, a binding waiting for one takes
    /// it, and Home opens and closes the menu over the game.
    fn poll_gamepads(&mut self) {
        for button in self.gamepads.poll() {
            if let Some(index) = self.menus.rebinding_pad.take() {
                if let Some((_, bound)) = self.settings.pad.all_mut().into_iter().nth(index) {
                    *bound = button;
                }
                self.apply_settings();
            } else if button == gilrs::Button::Mode && self.game.is_some() {
                self.menus.menu_open = !self.menus.menu_open;
                self.keyboard.release();
            }
        }
    }

    /// whether the pointer is busy with something other than the game.
    fn pointer_taken(&self, consumed: bool) -> bool {
        consumed || self.game.is_none() || self.menus.menu_open || self.gui.as_ref().is_some_and(Gui::wants_pointer)
    }

    /// touches the bottom screen while the button is down over it.
    fn touch(&mut self) {
        let Some(window) = &self.window else { return };
        let size = window.inner_size();
        let (_, bottom) = layout(size.width, size.height, self.presentation.layout(self.layout, self.experimental_wide));
        // with the top screen alone there is nothing to touch
        let Some(bottom) = bottom else {
            self.keyboard.touch(None);
            return;
        };
        let x = self.cursor.0 - bottom.x;
        let y = self.cursor.1 - bottom.y;
        let inside = x >= 0.0 && y >= 0.0 && x < bottom.width && y < bottom.height;
        self.keyboard.touch((self.mouse_down && inside).then(|| {
            ((x / bottom.width * 320.0) as u16, (y / bottom.height * 240.0) as u16)
        }));
    }

    /// tilts the console while the right button is held, toward where the
    /// pointer went and by how far, as Citra's motion emulation does,
    /// which titles were tried with. letting go stands it upright again.
    fn tilt(&mut self) {
        // radians a pixel, and the furthest it goes, a quarter turn
        const PER_PIXEL: f32 = 0.01;
        let tilt = match (self.tilting_from, &self.window) {
            (Some((x, y)), Some(window)) => {
                let scale = window.scale_factor() as f32;
                let (dx, dy) = ((self.cursor.0 - x) / scale, (self.cursor.1 - y) / scale);
                let distance = dx.hypot(dy);
                let angle = (distance * PER_PIXEL).min(std::f32::consts::FRAC_PI_2);
                if distance > 0.0 { [dx / distance * angle, dy / distance * angle] } else { [0.0; 2] }
            }
            _ => [0.0; 2],
        };
        self.keyboard.tilt(tilt);
    }

    fn show_layout(&mut self, screens: Screens) {
        self.layout = screens;
        if let Some(backend) = &mut self.backend { backend.set_layout(self.presentation.layout(screens, self.experimental_wide)); }
    }

    fn open_screen_access(&mut self) {
        self.presentation.boundary = true;
        let aim = self.mouse_captured.then(|| self.keyboard.aim_position());
        self.presentation.access = Some((self.layout, aim));
        self.set_mouse_capture(false);
        self.keyboard.release();
        self.mouse_down = false;
        self.tilting_from = None;
        self.show_layout(Screens::BottomOnly);
        if let Some(window) = &self.window {
            let size = window.inner_size();
            self.cursor = (size.width as f32 / 2.0, size.height as f32 / 2.0);
            let _ = window.set_cursor_position(winit::dpi::PhysicalPosition::new(self.cursor.0, self.cursor.1));
        }
        log::info!("Bottom screen: click to interact; Tab returns to gameplay");
    }

    fn close_screen_access(&mut self, resume: bool) { self.close_screen_access_by(resume, true); }

    fn close_screen_access_by(&mut self, resume: bool, by_player: bool) {
        let Some((layout, aim)) = self.presentation.access.take() else { return };
        self.presentation.panel_closed(by_player, zakuro_gpu::kiu_ui::scene());
        self.presentation.boundary = true;
        self.mouse_down = false;
        self.tilting_from = None;
        self.keyboard.release();
        self.show_layout(layout);
        if resume {
            if let Some(aim) = aim {
                self.set_mouse_capture(true);
                if self.mouse_captured { self.keyboard.restore_aim_position(aim); }
            }
        }
    }

    fn set_mouse_capture(&mut self, capture: bool) {
        let capture = capture && self.pc_controls && self.game.is_some() && !self.menus.menu_open && !self.menus.settings_open;
        let Some(window) = &self.window else {
            self.mouse_captured = false;
            self.keyboard.pc_aim_active(false);
            return;
        };
        if capture {
            let grabbed = window
                .set_cursor_grab(CursorGrabMode::Locked)
                .or_else(|_| window.set_cursor_grab(CursorGrabMode::Confined));
            match grabbed {
                Ok(()) => {
                    window.set_cursor_visible(false);
                    self.mouse_captured = true;
                    self.mouse_down = false;
                    self.tilting_from = None;
                    self.keyboard.pc_aim_active(true);
                    log::info!("PC mouse aim captured (F2 or Escape releases it)");
                }
                Err(error) => {
                    self.mouse_captured = false;
                    self.keyboard.pc_aim_active(false);
                    log::warn!("could not capture the mouse: {error}");
                }
            }
        } else {
            let _ = window.set_cursor_grab(CursorGrabMode::None);
            window.set_cursor_visible(true);
            self.mouse_captured = false;
            self.keyboard.pc_aim_active(false);
        }
    }

    fn toggle_fullscreen(&mut self) {
        if let Some(window) = &self.window {
            let full = window.fullscreen().is_some();
            if !full {
                self.maximized_before_full_screen = window.is_maximized();
                self.resize_after_full_screen = false;
            }
            window.set_fullscreen((!full).then_some(Fullscreen::Borderless(None)));
            // the layout may have changed meanwhile, which full screen kept
            // the window's size through. a window maximized before comes
            // back maximized, resizing it would take it out of that
            if full && self.resize_after_full_screen && !self.maximized_before_full_screen {
                let _ = window.request_inner_size(self.window_size());
            }
        }
    }

    fn apply_volume(&self) {
        if let Some(audio) = &self.audio {
            audio.set_volume(if self.settings.mute { 0.0 } else { self.settings.volume });
        }
    }

    /// saves the settings and puts to use what can change right away.
    fn apply_settings(&mut self) {
        self.close_screen_access(false);
        self.set_mouse_capture(false);
        self.settings.save();
        self.keyboard.set_keys(self.settings.keys.clone());
        self.gamepads.set_buttons(self.settings.pad.clone());
        self.apply_volume();
        self.apply_layout();
    }

    /// puts the screens' arrangement and the window scale to use, sizing
    /// the window to them.
    fn apply_layout(&mut self) {
        let scale = if self.options.scale.is_none() { self.settings.scale.max(1) } else { self.scale };
        if scale != self.scale || self.settings.layout != self.layout {
            self.scale = scale;
            self.layout = self.settings.layout;
            if let Some(backend) = &mut self.backend {
                backend.set_layout(self.presentation.layout(self.layout, self.experimental_wide));
            }
            // a full screen or maximized window keeps its size, resizing
            // it would take it out of that, full screen fits it on leaving
            match &self.window {
                Some(window) if window.fullscreen().is_some() => self.resize_after_full_screen = true,
                Some(window) if !window.is_maximized() => {
                    let _ = window.request_inner_size(self.window_size());
                }
                _ => {}
            }
        }
    }

    /// the window size that fits the screens at the chosen scale.
    fn window_size(&self) -> winit::dpi::Size {
        if self.pc_display { return winit::dpi::PhysicalSize::new(1920, 1080).into(); }
        let (width, height) = self.layout.screens().size();
        winit::dpi::LogicalSize::new(width * self.scale, height * self.scale).into()
    }

    fn recompile(&mut self, index: usize) {
        let Some(game) = self.library.games.get(index) else { return };
        self.jobs.retain(|job| job.program_id != game.program_id || !job.stage().finished());
        if self.jobs.iter().any(|job| job.program_id == game.program_id) {
            return;
        }
        self.jobs.push(Job::start(&game.path, game.program_id, &game.name));
    }

    /// tells about recompiles as they finish.
    fn poll_jobs(&mut self) {
        let mut finished = Vec::new();
        for job in &mut self.jobs {
            if !job.announced && job.stage().finished() {
                job.announced = true;
                finished.push((job.program_id, job.name.clone(), job.stage()));
            }
        }
        for (program_id, name, stage) in finished {
            match stage {
                Stage::Done => {
                    self.library.refresh_recompiled();
                    let playing = self.game.as_ref().is_some_and(|game| game.system.title.as_ref().is_some_and(|title| title.program_id() == program_id));
                    if playing {
                        self.menus.message = Some(format!("{name} is recompiled. Reset it from the menu, Esc, to run it on the new code."));
                    }
                }
                Stage::Failed(error) if error != "cancelled" => {
                    self.menus.message = Some(format!("Recompiling {name} failed, {error}"));
                }
                _ => {}
            }
        }
    }

    fn act(&mut self, action: Action, event_loop: &ActiveEventLoop) {
        match action {
            Action::Play(path) => {
                if let Err(error) = self.play(&path) {
                    self.menus.message = Some(error);
                }
            }
            Action::Recompile(index) => self.recompile(index),
            Action::CancelRecompile(program_id) => {
                for job in self.jobs.iter().filter(|job| job.program_id == program_id) {
                    job.cancel();
                }
            }
            Action::ChooseFolder => {
                if let Some(folder) = rfd::FileDialog::new().set_title("Where your games are").pick_folder() {
                    self.settings.games = Some(folder.clone());
                    self.settings.save();
                    self.library.scan(&folder);
                }
            }
            Action::ChooseBackground => {
                let picked = rfd::FileDialog::new()
                    .set_title("A picture for the library")
                    .add_filter("Pictures", &["png", "jpg", "jpeg", "webp", "bmp"])
                    .pick_file();
                if let Some(file) = picked {
                    self.settings.background = Some(file);
                    self.settings.save();
                }
            }
            Action::Rescan => {
                if let Some(folder) = self.settings.games.clone() {
                    self.library.scan(&folder);
                }
            }
            Action::Resume => {
                self.menus.menu_open = false;
                self.keyboard.release();
            }
            Action::Reset => {
                if let Some(path) = self.game.as_ref().map(|game| game.path.clone()) {
                    if let Err(error) = self.play(&path) {
                        self.menus.message = Some(error);
                    }
                }
            }
            Action::Library => self.back_to_library(),
            Action::Fullscreen => self.toggle_fullscreen(),
            Action::CopyReport => {
                if let (Some(game), Some(gui)) = (&self.game, &self.gui) {
                    gui.ctx.copy_text(report::text(&game.name, &game.system));
                    self.menus.message = Some("The game's details and the end of the log are copied. Paste them in your report and fill in what happens.".into());
                }
            }
            Action::Quit => event_loop.exit(),
            Action::Settings => self.apply_settings(),
            Action::Keyboard(text, button) => {
                if let Some(game) = &mut self.game {
                    game.system.answer_keyboard(&text, button);
                }
            }
        }
    }

    fn step(&mut self, event_loop: &ActiveEventLoop) {
        if self.stop {
            event_loop.exit();
            return;
        }
        let now = Instant::now();
        if now > self.next_frame + CATCH_UP_LIMIT {
            self.next_frame = now;
        }
        self.library.poll();
        self.poll_jobs();
        self.poll_gamepads();

        // a game waiting on its keyboard waits for the user, not running
        let typing = self.game.as_ref().is_some_and(|game| game.system.keyboard_request().is_some());
        let playing =
            self.game.is_some() && !self.paused && !self.menus.menu_open && !self.menus.settings_open && !typing;
        if !playing && self.mouse_captured {
            self.set_mouse_capture(false);
            self.keyboard.release();
        }
        if playing {
            let start = Instant::now();
            self.emulate();
            self.spent.emulating.add(start.elapsed());
        } else if let Some(audio) = &self.audio {
            // the sound stops with the game, which is not falling behind
            audio.hold();
        }

        self.next_frame += FRAME_TIME;
        // behind the schedule, showing the frame would wait on the display,
        // so it goes unshown, a few at most
        let behind = Instant::now() > self.next_frame;
        if playing && behind && self.skipped < MAX_SKIPPED {
            self.skipped += 1;
        } else {
            self.skipped = 0;
            let start = Instant::now();
            self.present(event_loop);
            self.spent.showing.add(start.elapsed());
            self.shown += 1;
        }

        if self.last_title_update.elapsed() >= Duration::from_millis(500) {
            let shown = self.shown as f32 / self.last_title_update.elapsed().as_secs_f32();
            self.shown = 0;
            self.last_title_update = Instant::now();
            if let Some(game) = &self.game {
                let Spent { emulating, showing } = std::mem::take(&mut self.spent);
                log::debug!(
                    target: "zakuro::fps",
                    "{:.1} frames emulated and {shown:.1} shown a second, emulating took {emulating}, showing {showing}",
                    game.fps
                );
            }
            if let Some(window) = &self.window {
                let title = match &self.game {
                    Some(game) => format!("Zakuro - {} - {}{}", game.name, game.system.status_line(),
                        if self.pc_controls {
                            " - PC controls (F2 mouse)"
                        } else { "" }),
                    None => "Zakuro".to_owned(),
                };
                window.set_title(&title);
            }
            let underruns = self.audio.as_ref().map_or(0, |audio| audio.take_underruns());
            if underruns > 0 && playing {
                log::warn!("the sound ran dry {underruns} times, the emulation is falling behind");
            }
        }

        let now = Instant::now();
        if now < self.next_frame {
            std::thread::sleep(self.next_frame - now);
        }
    }

    /// runs one frame of the game.
    fn emulate(&mut self) {
        let Some(game) = &mut self.game else { return };
        let raw_mouse = self.keyboard.raw_mouse_delta();
        // Land gameplay was seen within the last third of a second.
        const LAND_GRACE: u64 = 20;
        let on_land = self.land_seen.is_some_and(|seen| game.frame.saturating_sub(seen) <= LAND_GRACE);
        self.keyboard.set_wheel_allowed(self.settings.kiu_wheel_powers && on_land);
        let mut input = match &mut game.replay {
            Some(replay) => replay.input(game.frame),
            None => {
                let mut keyboard = self.keyboard.state(self.mouse_sensitivity);
                if self.presentation.enabled {
                    let pad=self.presentation.controller(self.gamepads.apply(Default::default()));
                    keyboard.buttons |= pad.buttons;
                    if pad.circle_x != 0.0 || pad.circle_y != 0.0 {
                        keyboard.circle_x=pad.circle_x; keyboard.circle_y=pad.circle_y;
                    }
                    keyboard
                } else { self.gamepads.apply(keyboard) }
            }
        };
        if game.replay.is_none() {
            // While a Space jump steps through the palette, its D-pad presses
            // replace the player's power keys and wheel for those frames.
            let was_active = self.space_jump.active();
            let jump = self.space_jump.step(&mut game.system.memory, self.mouse_captured && on_land);
            if was_active || self.space_jump.active() || !jump.is_empty() {
                { use zakuro_core::services::hid::PadState; input.buttons = (input.buttons - (PadState::LEFT | PadState::RIGHT | PadState::DOWN)) | jump; }
            }
        }
        if let Some(trace) = &mut self.input_trace {
            trace.sample(game.frame, raw_mouse, self.mouse_captured, input, game.replay.is_some(), true);
        }
        game.frame += 1;
        if let Some(recorder) = &mut game.recorder {
            recorder.record(input);
        }
        game.system.set_input(input);
        static RELATIVE_CAMERA: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        let relative = *RELATIVE_CAMERA.get_or_init(|| std::env::var_os("KIU_RELATIVE_CAMERA").is_some());
        let pointer_visit = self.presentation.access.is_some() && self.experimental_air;
        let motion = if pointer_visit { Some([0.0; 2]) } else {
            (relative && self.mouse_captured && input.touch.is_some() && game.replay.is_none())
                .then(|| raw_mouse.map(|v| v * self.mouse_sensitivity))
        };
        game.system.memory.queue_kiu_mouse(motion);
        zakuro_gpu::kiu_ui::set_touch(input.touch);
        zakuro_gpu::kiu_ui::begin_frame();
        let outcome = game.system.run_frame();
        let scene = zakuro_gpu::kiu_ui::end_frame();
        let land = game.system.memory.kiu_land_publications();
        if land != self.land_publications || scene.palette {
            self.land_publications = land;
            self.land_seen = Some(game.frame);
        }
        game.count_frame();
        let sound = game.system.take_audio();
        if let Some(audio) = &self.audio {
            audio.push(&sound);
        }
        match outcome {
            FrameOutcome::Completed => {}
            FrameOutcome::Exited => {
                log::info!("the title exited");
                self.back_to_library();
            }
            FrameOutcome::Faulted => {
                log::error!("the title stopped on a fault");
                let errors = game.system.fatal_errors.join("; ");
                if !errors.is_empty() {
                    log::error!("{errors}");
                }
                let message = format!("The game stopped on a fault. {errors}");
                self.menus.report = Some((message.clone(), report::text(&game.name, &game.system)));
                self.menus.message = Some(message);
                self.back_to_library();
                return;
            }
        }
        self.follow_scene(scene);
    }

    /// Lets the presentation follow what the game's own lower screen shows.
    fn follow_scene(&mut self, scene: zakuro_gpu::kiu_ui::BottomScene) {
        if self.game.is_none() || !self.pc_controls { return; }
        let allowed = zakuro_gpu::kiu_ui::config::get().auto_pause_panel
            && !self.menus.menu_open && !self.menus.settings_open
            && !self.gui.as_ref().is_some_and(Gui::wants_keyboard);
        match self.presentation.observe(scene, allowed) {
            pc_presentation::PanelRequest::Open => {
                log::info!("Game pause menu shown: opening the lower-screen panel (Tab or Esc returns)");
                self.open_screen_access();
            }
            pc_presentation::PanelRequest::Close => {
                log::info!("Gameplay resumed: closing the pause panel");
                self.close_screen_access_by(true, false);
            }
            pc_presentation::PanelRequest::Keep => {}
        }
    }

    /// the menus, and the actions they asked for, done.
    fn interface(&mut self, event_loop: &ActiveEventLoop) -> Overlay {
        let (Some(gui), Some(window)) = (&mut self.gui, &self.window) else { return Overlay::default() };
        let show_fps = self.settings.show_fps;
        let game = self.game.as_ref().map(|game| (game.name.clone(), game.fps, game.system.recompiled.is_some()));
        let keyboard = self.game.as_ref().and_then(|game| game.system.keyboard_request().cloned());
        let (menus, library, settings, jobs) = (&mut self.menus, &self.library, &mut self.settings, &self.jobs);
        let mut actions = Vec::new();
        let overlay = gui.frame(window, |ui| {
            match &game {
                Some((name, fps, recompiled)) => {
                    actions.extend(menus.game(ui, name, show_fps.then_some(*fps), *recompiled, jobs))
                }
                None => actions.extend(menus.library(ui, library, settings, jobs)),
            }
            actions.extend(menus.settings(ui.ctx(), settings));
            if let Some(request) = &keyboard {
                actions.extend(menus.keyboard(ui.ctx(), request));
            }
            menus.message(ui.ctx());
        });
        self.library.changed = false;
        for action in actions {
            self.act(action, event_loop);
        }
        overlay
    }

    fn present(&mut self, event_loop: &ActiveEventLoop) {
        let mut overlay = self.interface(event_loop);
        if let Some(window)=&self.window {
            let size=window.inner_size();
            let visible=self.game.is_some()
                && self.presentation.gameplay_layers_visible(self.mouse_captured, self.menus.menu_open || self.menus.settings_open);
            let view=layout(size.width,size.height,self.presentation.layout(self.layout,self.experimental_wide)).0
                .map_or([0.0,0.0,size.width as f32,size.height as f32],|v|[v.x,v.y,v.width,v.height]);
            let mut dialogue=zakuro_gpu::kiu_ui::overlay_in(size.width,size.height,view,visible);
            dialogue.meshes.append(&mut overlay.meshes);
            dialogue.textures.append(&mut overlay.textures);
            dialogue.free.append(&mut overlay.free);
            overlay=dialogue;
        }
        let blank = |screen: Screen| ((std::sync::Arc::new(Vec::new()), screen.width(), screen.height()), None);
        let show_bottom = !self.presentation.enabled || self.presentation.access.is_some() || self.presentation.legacy;
        let (top, bottom) = match &mut self.game {
            Some(game) => (shown(&mut game.system, Screen::Top),
                if show_bottom { shown(&mut game.system, Screen::Bottom) } else { blank(Screen::Bottom) }),
            None => (blank(Screen::Top), blank(Screen::Bottom)),
        };
        let Some(backend) = &mut self.backend else { return };
        let (((top, top_width, top_height), top_gpu), ((bottom, bottom_width, bottom_height), bottom_gpu)) = (top, bottom);
        let result = backend.present(
            ScreenImage { width: top_width, height: top_height, pixels: &top, gpu: top_gpu },
            ScreenImage { width: bottom_width, height: bottom_height, pixels: &bottom, gpu: bottom_gpu },
            &overlay,
        );
        match result {
            Ok(()) | Err(PresentError::OutOfDate) => {}
            Err(error) => {
                log::error!("presentation failed: {error}");
                event_loop.exit();
            }
        }
    }
}

/// a screen as the presenter takes it, straight from the GPU when it shares
/// the renderer's device and the GPU drew what the screen shows, else its
/// pixels.
fn shown(system: &mut System, screen: Screen) -> (zakuro_core::Screen, Option<GpuScreen>) {
    if let Some(gpu) = system.gpu_screen(screen) {
        let scale = system.gpu.scale();
        return ((std::sync::Arc::new(Vec::new()), screen.width() * scale, screen.height() * scale), Some(gpu));
    }
    (system.read_screen_scaled(screen), None)
}

/// keeps the renderer kind referenced even when a backend feature is off.
const _: RendererKind = RendererKind::Software;
