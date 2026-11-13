//! The main menu's scene, drawn by the PC behind the redrawn buttons
//! (pc_menus::buttons): the "Ink & Paper" design.
//!
//! Everything is the game's own art, prepared once from the player's ROM into
//! a scene pack (tools/idols/menu_pack ->
//! build/texture-work/menu-pc/scene-040, local only): the striped paper and
//! the mode's emblem, the mode's stage in a slanted window with the mode's
//! character relit for it, ink ornaments, the ground band, the heading,
//! caption and controls. This module plays it live, following the game's
//! own selection:
//!
//! - entry: the paper wipes in from the left, the window pulls back and slams
//!   in, the character rides in after it, the band rises, heading, caption and
//!   controls arrive one after the other;
//! - holds never stop: a slow handheld camera drifts the stage, the character
//!   and the ink at different depths, the key light breathes, rays turn,
//!   particles drift, a soft light sweeps the paper;
//! - a change of selection: the modes stand in a column like their buttons;
//!   going down the list pans the window down to the next scene (going up,
//!   up), an ink gutter between them, characters travelling further than their
//!   stage and landing with a small overshoot; the paper's colour, the
//!   watermark, the heading and the caption all move the same way. It follows
//!   where the pointer is going, not each choice the game's cursor passes;
//! - confirm: the menu leaves, the character does its move (Together: the
//!   throw and the kick, with impact frames and hit-stop), then the window
//!   pushes in to fill the screen, as if going into that mode, and the scene
//!   fades into the game's next screen once the game shows it;
//! - Back: the menu leaves, the window slides away and the scene fades.
//!
//! Times are in frames at 60 per second, counted from real time, so it is
//! smooth at any refresh rate. Positions are in the design's 1920x1080
//! pixels, scaled to cover the window.
//!
//! Cost on the game's thread: the pack is read on its own thread from
//! start-up (`prepare`) and turned into textures a few per frame (`Upload`),
//! once, then kept for every visit. Character frames (JPEG colour + PNG
//! coverage, ~7 ms each) are decoded by 2-4 threads working from a to-do list
//! that is replaced every frame (what is needed now, then what comes next),
//! so they never fall behind for good; each mode's character is one texture,
//! updated in place.

use std::collections::HashMap;
use std::path::Path;

use egui::{Color32, Pos2, Rect, TextureHandle};

/// The design's size in pixels (scaled to cover the window).
const W: f32 = 1920.0;
const H: f32 = 1080.0;
const GOLD: [u8; 3] = [255, 208, 84];
const INK: [u8; 3] = [12, 8, 14];

mod anim;
mod canvas;
mod effects;
mod frames;
mod loading;
mod manifest;
mod timeline;
#[cfg(test)]
mod bench;
#[cfg(test)]
mod preview;

pub use loading::{prepare, Prepared, Upload};
pub use manifest::pack;

use anim::*;
use canvas::*;
use effects::*;
use frames::{Shown, Stream};
use loading::{Art, Tex};
use manifest::Manifest;
#[cfg(test)]
use manifest::{Character, Seq};
use timeline::idle_index;

/// What the scene is doing.
#[derive(Clone, Copy, PartialEq, Debug)]
enum Phase {
    Shown,
    /// the player confirmed this mode at this time (seconds)
    Confirming { mode: usize, at: f64 },
    /// the menu went away another way
    Leaving { at: f64 },
}

pub struct Scene {
    /// shown (between the menu appearing and the scene finishing)
    active: bool,
    /// for the log every 5 s: since when (real time), and how many times drawn
    report: (f64, u32),
    /// the real time last drawn: the scene's own clock (`time`) advances by
    /// at most 1/20 s a frame, so when the game stalls (loading its next
    /// screen) the animation pauses instead of jumping ahead
    real: f64,
    /// it finished while the game still showed the menu: it waits for the
    /// game to leave before it can start again
    rested_on_menu: bool,
    man: Manifest,
    art: Art,
    stream: Stream,
    /// when it appeared (seconds)
    start: f64,
    selected: usize,
    previous: usize,
    /// when the selection last changed
    changed: Option<f64>,
    /// when each mode became selected (its character's clock)
    chosen_at: [f64; 4],
    phase: Phase,
    /// when the game left the menu (the cut waits for it)
    game_left: Option<f64>,
    time: f64,
    /// where the pressed button was (design pixels)
    pressed_at: Option<[f32; 2]>,
    /// a selection waiting for the running change to finish
    pending: Option<usize>,
}

/// A change of selection: its length, and how long it is busy (a newer
/// selection waits until then).
const SWAP: f32 = 22.0;
const SWAP_BUSY: f32 = 12.0;
/// The ink gutter between two modes' scenes in the column.
const GUTTER: f32 = 70.0;
/// The confirm's push into the window.
const PUSH: f32 = 16.0;

impl Scene {
    fn build(ctx: &egui::Context, root: &Path, man: Manifest, made: &HashMap<String, TextureHandle>) -> Option<Scene> {
        let t = |f: &str| made.get(f).cloned();
        let mut modes = Vec::new();
        for m in &man.modes {
            modes.push(Tex { paper: t(&m.paper)?, stage: t(&m.stage)?, emblem: t(&m.emblem.file)?, rays: t(&m.rays)?,
                             heading: t(&m.heading.file)?, caption: t(&m.caption.file)?, glow: m.glow.as_deref().and_then(t) });
        }
        let s = &man.sprites;
        let art = Art { modes, band: t(&man.band.file)?, controls: t(&man.controls.file)?, swirl: t(&man.swirl.file)?, sprig: t(&man.sprig.file)?,
                        feather: t(&s.feather)?, spark: t(&s.spark)?,
                        leaves: s.leaves.iter().filter_map(|f| t(f)).collect(), flash: t(&s.flash)? };
        let stream = Stream::new(root, &man);
        let now = ctx.input(|i| i.time);
        log::info!("Main menu scene: the PC's ink and paper menu ({} character frames)", man.modes.iter().map(|m| m.character.frames.len()).sum::<usize>());
        Some(Scene { active: false, report: (now, 0), real: now, rested_on_menu: false, man, art, stream, start: now, selected: 0, previous: 0, changed: None,
                     chosen_at: [now; 4], phase: Phase::Shown, game_left: None, time: now, pressed_at: None, pending: None })
    }

    /// Reads and uploads the whole pack at once (the preview test).
    #[cfg(test)]
    pub fn load(ctx: &egui::Context, root: &Path) -> Option<Scene> {
        let mut up = Upload::new(Prepared::read(root.to_path_buf())?);
        loop { if let Some(s) = up.step(ctx) { return Some(s); } if up.prepared.pictures.is_empty() { return None; } }
    }

    /// Whether the scene is being shown.
    pub fn active(&self) -> bool { self.active }

    /// Every 5 s while shown, how smooth it is, for the log: how often it
    /// was drawn, character frames shown on time or late, decoding time.
    fn report_now(&mut self) {
        self.report.1 += 1;
        let span = self.real - self.report.0;
        if span < 5.0 { return; }
        let st = std::mem::take(&mut self.stream.stats);
        let (n, ms) = std::mem::take(&mut self.stream.decoded);
        log::info!(
            "Main menu scene: drawn {:.0} times a second; character frames on time {}, late {} (at most {} behind); {} decoded, {:.1} ms each on {} threads",
            self.report.1 as f64 / span, st[0], st[1], st[2], n, if n > 0 { ms / n as f32 } else { 0.0 }, self.stream.threads
        );
        self.report = (self.real, 0);
    }

    /// The main menu is on screen: starts the scene from its entry, unless it
    /// is already showing this visit.
    pub fn on_menu(&mut self, ctx: &egui::Context) {
        if self.active && self.game_left.is_none() { return; }
        if !self.active && self.rested_on_menu { return; }
        self.real = ctx.input(|i| i.time);
        let now = self.time;
        self.active = true; self.start = now; self.report = (self.real, 0);
        self.selected = 0; self.previous = 0; self.changed = None; self.chosen_at = [now; 4];
        self.phase = Phase::Shown; self.game_left = None; self.pressed_at = None; self.pending = None;
    }

    /// The game's selected choice this frame (its node: 0 Solo .. 3 Options):
    /// where the selection is going. A change starts at once unless one is
    /// still running; then the newest waits for it (only the last one counts).
    pub fn select(&mut self, node: Option<usize>) {
        let Some(node) = node.filter(|&n| n < 4) else { return };
        if self.phase != Phase::Shown { return; }
        if node == self.selected { self.pending = None; return; }
        if self.changed.is_some_and(|t| self.frames_since(t) < SWAP_BUSY) { self.pending = Some(node); return; }
        self.change_to(node);
    }

    fn change_to(&mut self, node: usize) {
        self.previous = self.selected;
        self.selected = node;
        self.changed = Some(self.time);
        self.chosen_at[node] = self.time;
        self.pending = None;
    }

    /// The player confirmed choice `node` (a click on its button, at `at`).
    pub fn confirm(&mut self, node: usize, at: Option<Pos2>, window: Rect) {
        if node >= 4 || self.phase != Phase::Shown { return; }
        if node != self.selected { self.change_to(node); }
        self.pressed_at = at.map(|p| Map::new(window).design(p));
        self.phase = Phase::Confirming { mode: node, at: self.time };
    }

    /// The game has left the menu screen.
    pub fn game_left(&mut self) {
        if !self.active { self.rested_on_menu = false; return; }
        if self.game_left.is_none() { self.game_left = Some(self.time); }
        if self.phase == Phase::Shown { self.phase = Phase::Leaving { at: self.time }; }
    }

    /// The player is going back (the Back arrow).
    pub fn back(&mut self) { if self.phase == Phase::Shown { self.phase = Phase::Leaving { at: self.time }; } }

    /// Whether the menu's own pieces (buttons) take input.
    pub fn interactive(&self) -> bool { self.phase == Phase::Shown }

    fn frames_since(&self, t: f64) -> f32 { ((self.time - t) * 60.0) as f32 }

    /// Frames since the menu began to leave (confirm: after the press), if it is leaving.
    fn leaving_for(&self) -> Option<f32> {
        match self.phase {
            Phase::Shown => None,
            Phase::Confirming { at, .. } => Some(self.frames_since(at) - 4.0),
            Phase::Leaving { at } => Some(self.frames_since(at)),
        }
    }

    /// How far the menu's words have left (0 here .. 1 gone), for element
    /// `i` of the leaving order (0 heading, 3 caption, 4 controls).
    fn out_k(&self, i: usize) -> f32 {
        self.leaving_for().map_or(0.0, |c| k2(0.0, 0.0, 12.0, 1.0, Ease::In, c - 3.0 * i as f32))
    }

    /// Where button `i` is (a horizontal offset in window units of 240 per
    /// height) and how visible: it arrives from the left on entry, staggered,
    /// and leaves to the left.
    pub fn button_presence(&self, i: usize) -> (f32, f32) {
        let v = self.frames_since(self.start) - 28.0 - 3.0 * i as f32;
        let arrive = track(v, &[(0.0, 0.0, Ease::Out), (18.0, 1.0, Ease::OutBack)]);
        let alpha = k2(0.0, 0.0, 12.0, 1.0, Ease::Out, v);
        let leave = self.leaving_for().map_or(0.0, |c| k2(0.0, 0.0, 12.0, 1.0, Ease::In, c - 3.0 - 2.0 * i as f32));
        let dx_px = -560.0 * (1.0 - arrive) - 900.0 * leave;
        (dx_px / 4.5, alpha * (1.0 - leave))
    }

    /// For a confirm of `mode`: playback speed of its move, when the move hits
    /// (Together's kick), and when the window starts pushing in to fill the screen.
    fn confirm_plan(&self, mode: usize) -> (f32, Option<f32>, f32) {
        let c = &self.man.modes[mode].character.confirm;
        let len = (c.range[1] - c.range[0]) as f32;
        let speed = if len > 70.0 { 1.5 } else { 1.0 };
        let hit = c.impact.map(|i| 4.0 + (i - c.range[0]) as f32 / speed);
        let push = match hit { Some(h) => h + 14.0, None => 14.0 };
        (speed, hit, push)
    }

    /// How visible the whole scene is. Confirm: it fades into the game's next
    /// screen once the push-in is done and the game shows that screen (at most
    /// 3 s later). Back: it fades as the window slides away.
    fn opacity(&self) -> f32 {
        match self.phase {
            Phase::Shown => 1.0,
            Phase::Confirming { mode, at } => {
                let (_, _, push) = self.confirm_plan(mode);
                let c = self.frames_since(at);
                let pushed = push + PUSH;
                let game = self.game_left.map_or(f32::INFINITY, |t| ((t - at) * 60.0) as f32);
                1.0 - clamp01((c - pushed.max(game)) / 16.0)
            }
            Phase::Leaving { at } => 1.0 - clamp01((self.frames_since(at) - 6.0) / 14.0),
        }
    }

    /// Draws the scene. Returns false once it has finished leaving (it then
    /// rests until the menu appears again).
    pub fn show(&mut self, ctx: &egui::Context, window: Rect) -> bool {
        if !self.active { return false; }
        let real = ctx.input(|i| i.time);
        self.time += (real - self.real).clamp(0.0, 1.0 / 20.0);
        self.real = real;
        self.stream.receive();
        // the game did not take the click (it is still on the menu long after
        // the push-in): the menu comes back rather than fading to the game's own
        if let Phase::Confirming { mode, at } = self.phase {
            let (_, _, push) = self.confirm_plan(mode);
            if self.game_left.is_none() && self.frames_since(at) > push + PUSH + 240.0 {
                log::warn!("Main menu scene: the game did not leave the menu after the click; showing the menu again");
                self.phase = Phase::Shown; self.pressed_at = None;
                self.chosen_at[self.selected] = self.time;
            }
        }
        self.report_now();
        if let Some(n) = self.pending {
            if self.changed.is_none_or(|t| self.frames_since(t) >= SWAP_BUSY) { self.change_to(n); }
        }
        // Enter or Space confirms the selection, as the game itself will
        if self.phase == Phase::Shown && ctx.input(|i| i.key_pressed(egui::Key::Enter) || i.key_pressed(egui::Key::Space)) {
            self.phase = Phase::Confirming { mode: self.selected, at: self.time };
        }
        let map = Map::new(window);
        let v = self.frames_since(self.start);
        let mut cv = Canvas::default();
        self.draw(ctx, &mut cv, v);
        let opacity = self.opacity();
        let painter = ctx.layer_painter(egui::LayerId::new(egui::Order::Background, egui::Id::new("kiu-menu-scene")));
        cv.emit(&painter, &map, opacity);
        self.stream.publish();
        ctx.request_repaint();
        if opacity <= 0.0 { self.active = false; self.rested_on_menu = self.game_left.is_none(); self.stream.publish(); }
        self.active
    }

    /// Builds the picture.
    fn draw(&mut self, ctx: &egui::Context, cv: &mut Canvas, v: f32) {
        use std::f32::consts::TAU;
        let cur = self.selected;
        let prev = self.previous;
        let ts = self.changed.map_or(1e6, |t| self.frames_since(t));
        let swapping = ts < SWAP;
        // the modes stand in a column like their buttons: going down the list
        // pans the window down to the next one (its content rises), going up pans up
        let d: f32 = if cur > prev { 1.0 } else { -1.0 };
        let pan = ease(Ease::InOut, clamp01(ts / SWAP));
        let show = if pan >= 0.5 { cur } else { prev };
        let [cx, cy] = cam(v);
        let man = self.man.clone();
        let p0 = man.panel.x0; let lean = man.panel.lean;
        // the confirm: its move, its hit, the push into the window
        let (conf, conf_c) = match self.phase { Phase::Confirming { mode, at } => (Some(mode), self.frames_since(at)), _ => (None, 0.0) };
        let (speed, hit, push_at) = conf.map_or((1.0, None, 1e6), |m| self.confirm_plan(m));
        let hold = 10.0;
        let hitstop = hit.is_some_and(|h| conf_c >= h && conf_c < h + hold);
        let after_hit = hit.map(|h| conf_c - h);
        let push = if conf.is_some() { ease(Ease::In, clamp01((conf_c - push_at) / PUSH)) } else { 0.0 };
        let back = match self.phase { Phase::Leaving { at } => ease(Ease::In, clamp01(self.frames_since(at) / 14.0)), _ => 0.0 };

        // 1. paper: wipes in from the left; a new mode's colour is revealed by its
        //    edge moving the same way as the pan
        let px = k2(0.0, -W, 8.0, 0.0, Ease::Out, v);
        let paper = |cv: &mut Canvas, m: usize| {
            let t = &self.art.modes[m].paper;
            cv.poly(t.id(), &[Vx { p: [px, 0.0], uv: [0.0, 0.0], c: Color32::WHITE }, Vx { p: [W + px, 0.0], uv: [1.0, 0.0], c: Color32::WHITE },
                               Vx { p: [W + px, H], uv: [1.0, 1.0], c: Color32::WHITE }, Vx { p: [px, H], uv: [0.0, 1.0], c: Color32::WHITE }]);
        };
        if swapping {
            paper(cv, prev);
            let kp = ease(Ease::InOut, clamp01((ts - 2.0) / SWAP));
            // d > 0: the new colour rises from the bottom edge; d < 0: it comes down from the top
            let edge = if d > 0.0 { H - (H + 40.0) * kp } else { -40.0 + (H + 40.0) * kp };
            cv.clips.push(if d > 0.0 { Half { a: 0.0, b: 1.0, c: -edge } } else { Half { a: 0.0, b: -1.0, c: edge } });
            paper(cv, cur);
            cv.clips.pop();
        } else { paper(cv, cur); }
        // the window's light spilling on the paper, and a soft sweep across it
        if v >= 8.0 {
            let hi = man.modes[show].high;
            let (a, b) = (additive(hi, 0.16), additive(hi, 0.0));
            cv.fill(&[([p0 - 520.0, -40.0], b), ([p0, -40.0], a), ([p0 - lean, H + 40.0], a), ([p0 - 520.0 - lean, H + 40.0], b)]);
            let p = ((v % 300.0) / 300.0) * 2600.0 - 700.0;
            let (z, w) = (additive([255, 255, 255], 0.0), additive([255, 248, 235], 0.10));
            for (x0, x1, c0, c1) in [(p - 160.0, p, z, w), (p, p + 160.0, w, z)] {
                cv.fill(&[([x0, 0.0], c0), ([x1, 0.0], c1), ([x1 - 0.6 * H, H], c1), ([x0 - 0.6 * H, H], c0)]);
            }
        }
        // 2. the watermark: drifts with the pan, keeps breathing
        let breathe = 1.5 * (TAU * v / 420.0).sin();
        let emblem = |cv: &mut Canvas, m: usize, sc: f32, dy: f32, a: f32| {
            if a <= 0.01 { return; }
            let t = &self.art.modes[m].emblem; let at = man.modes[m].emblem.at; let s = t.size();
            let (w, h) = (s[0] as f32 * sc, s[1] as f32 * sc);
            let c = [at[0] + s[0] as f32 / 2.0 + 10.0 * (TAU * v / 360.0).sin(), at[1] + s[1] as f32 / 2.0 + 8.0 * (TAU * v / 290.0).sin() + dy];
            cv.image(t, [c[0] - w / 2.0, c[1] - h / 2.0, w, h], breathe, c, faded(a));
        };
        if self.changed.is_some() {
            if swapping { emblem(cv, prev, 1.0, -d * 140.0 * pan, 1.0 - k2(0.0, 0.0, 12.0, 1.0, Ease::In, ts)); }
            emblem(cv, cur, 1.0, d * 140.0 * (1.0 - ease(Ease::Out, clamp01((ts - 6.0) / 18.0))), k2(6.0, 0.0, 16.0, 1.0, Ease::Out, ts));
        } else {
            emblem(cv, cur, track(v, &[(10.0, 0.86, Ease::Out), (28.0, 1.0, Ease::OutBack)]), 0.0, k2(10.0, 0.0, 18.0, 1.0, Ease::Out, v));
        }

        // 3. the window: pulls back and slams in on entry; pushes in to fill the
        //    screen on confirm (its edge sweeps out to the left); slides away on Back
        let pdx = track(v, &[(0.0, 1500.0, Ease::Out), (6.0, 1500.0, Ease::Out), (20.0, 0.0, Ease::OutBack)]) - 1700.0 * push + 1600.0 * back;
        let sx_hit = hit.map_or(0.0, |h| shake(conf_c, h, hold + 10.0, 6.0, 2));
        let vx_hit = hit.map_or(0.0, |h| shake(conf_c, h, hold + 10.0, 20.0, 3));
        let kx = shake(v, 20.0, 8.0, 7.0, 1);
        let panel_clip = Half::right_of(p0 + pdx, lean);
        let impact_frame = hit.is_some_and(|h| conf_c >= h && conf_c < h + 2.0);
        let zoom_push = 1.0 + 0.07 * push;
        // the character's frame for a mode now
        let char_index = |s: &Scene, m: usize| -> (i32, Vec<i32>) {
            let c = &s.man.modes[m].character;
            if conf == Some(m) && conf_c >= 4.0 {
                let mut f = (conf_c - 4.0) * speed;
                if let Some(h) = hit {
                    let hit_f = (h - 4.0) * speed;
                    if f >= hit_f { f = if f < hit_f + hold { hit_f } else { f - hold }; }
                }
                let i = (c.confirm.range[0] + f as i32).min(c.confirm.range[1]);
                return (i, (1..5).map(|k| (i + k).min(c.confirm.range[1])).collect());
            }
            let t = s.frames_since(s.chosen_at[m]);
            let i = idle_index(c, t);
            let mut ahead: Vec<i32> = (1..6).map(|k| idle_index(c, t + k as f32)).collect();
            ahead.extend((0..3).map(|k| c.confirm.range[0] + k));      // a confirm may come any time
            (i, ahead)
        };
        // one mode's window content (stage, light, lines) moved by (dx, dy), and its character
        let content = |s: &mut Scene, cv: &mut Canvas, m: usize, slide: f32, dy_stage: f32, dy_char: f32| -> Option<(Shown, [f32; 4])> {
            let art = &s.art.modes[m]; let ma = &man.modes[m];
            let stage = &art.stage; let ss = stage.size(); let (sw, sh) = (ss[0] as f32, ss[1] as f32);
            let z = (1.03 + 0.02 * (TAU * v / 400.0).sin()) * zoom_push;
            let (cw, chh) = (W / z, H / z);
            let mut o = 60.0 + cx;
            if ma.stage_scroll > 0.0 { o = (v * ma.stage_scroll + cx).rem_euclid(W); }
            let o = o.clamp(0.0, sw - cw);
            let oy = (35.0 + cy - (chh - H) / 2.0).clamp(0.0, sh - chh);
            let (shx, shy) = (sx_hit + kx, dy_stage);
            let uv = |x: f32, y: f32| [(o + (x - shx) * cw / W) / sw, (oy + (y - shy) * chh / H) / sh];
            let corners = [[p0 + pdx - 2000.0, -40.0 + dy_stage], [W + 400.0, -40.0 + dy_stage], [W + 400.0, H + 40.0 + dy_stage], [p0 + pdx - 2000.0, H + 40.0 + dy_stage]];
            cv.clips.push(panel_clip);
            cv.poly(stage.id(), &corners.map(|p| Vx { p, uv: uv(p[0], p[1]), c: Color32::WHITE }));
            // the key light breathes; rays turn slowly about it
            let pulse = 0.88 + 0.12 * (TAU * v / 180.0).sin();
            if let Some(g) = &art.glow { cv.image(g, [0.0, dy_stage, W, H], 0.0, [0.0, 0.0], light(pulse)); }
            let ra = k2(16.0, 0.0, 38.0, 1.0, Ease::Out, v) * pulse;
            let ang = (v * 0.12).to_radians(); let c0 = [ma.rays_at[0], ma.rays_at[1] + dy_stage];
            let (s_, c_) = (-ang).sin_cos();
            let ruv = |x: f32, y: f32| { let (dx, dy) = (x - c0[0], y - c0[1]); [(ma.rays_at[0] + dx * c_ - dy * s_) / W, (ma.rays_at[1] + dx * s_ + dy * c_) / H] };
            cv.poly(art.rays.id(), &[[0.0, dy_stage], [W, dy_stage], [W, H + dy_stage], [0.0, H + dy_stage]].map(|p| Vx { p, uv: ruv(p[0], p[1]), c: light(ra) }));
            if v >= 20.0 {
                if m == 0 { wind_streaks(cv, v, dy_stage); }
                if m == 1 {
                    let strong = if v < 32.0 || hitstop { 1.0 } else { 0.21 };
                    speed_lines(cv, [man.impact[0], man.impact[1] + dy_stage], if hitstop { 999 } else { (v / 2.0) as u32 }, strong, mix(ma.color, [255, 255, 255], 0.6), 60);
                }
            }
            // the far particles, behind the character
            if v >= 14.0 { s.particles(cv, m, v, dy_stage, false); }
            cv.clips.pop();
            let (i, ahead) = char_index(s, m);
            let fr = s.stream.get(ctx, m, i, &ahead)?;
            let (at, sz) = (fr.at, fr.size);
            let mut r = [at[0] + slide + vx_hit + 1.7 * cx, at[1] + 1.7 * cy + dy_char, sz[0], sz[1]];
            // a slow breathing push-in on the held pose (key-art camera), and the
            // confirm's push-in brings the character closer too
            let breath = 1.0 + 0.025 * (0.5 - 0.5 * (TAU * s.frames_since(s.chosen_at[m]) / 240.0).cos());
            {
                let f = [r[0] + r[2] / 2.0, r[1] + r[3]];          // about the feet: they stay on the ground
                r = [f[0] + (r[0] - f[0]) * breath, f[1] + (r[1] - f[1]) * breath, r[2] * breath, r[3] * breath];
            }
            if zoom_push > 1.0 {
                // about the character's own middle, so nobody is pushed out of the picture
                let f = [r[0] + r[2] / 2.0, r[1] + r[3] * 0.55];
                r = [f[0] + (r[0] - f[0]) * zoom_push, f[1] + (r[1] - f[1]) * zoom_push, r[2] * zoom_push, r[3] * zoom_push];
            }
            if conf == Some(1) && m == 1 {
                if let Some(h) = hit {
                    let cz = track(conf_c, &[(h - 6.0, 1.0, Ease::Out), (h, 0.98, Ease::InOut), (h + 4.0, 1.06, Ease::Out), (h + 40.0, 1.03, Ease::Out)]);
                    let ip = man.impact;
                    r = [ip[0] + (r[0] - ip[0]) * cz, ip[1] + (r[1] - ip[1]) * cz, r[2] * cz, r[3] * cz];
                }
            }
            Some((fr, r))
        };
        let mut chars: Vec<(Shown, [f32; 4], Option<Half>, usize, f32)> = Vec::new();
        if !impact_frame {
            if self.changed.is_none() {
                let slide = track(v, &[(0.0, 1500.0, Ease::Out), (9.0, 1500.0, Ease::Out), (23.0, 0.0, Ease::OutBack)]);
                if let Some((t, r)) = content(self, cv, cur, slide, 0.0, 0.0) { chars.push((t, r, None, cur, 0.0)); }
            } else if swapping {
                // the column of scenes: one screen and an ink gutter apart
                let step = H + GUTTER;
                let old_dy = -d * step * pan;
                let new_dy = d * step * (1.0 - pan);
                // characters travel further than their stage (closer to the lens) and land with a small overshoot
                let char_k = ease(Ease::OutBack, clamp01((ts - 3.0) / (SWAP - 3.0)));
                let old_c = -d * step * 1.25 * pan;
                let new_c = d * step * 1.25 * (1.0 - char_k);
                // each scene keeps to its own part of the column
                let (old_side, new_side) = if d > 0.0 {
                    (Half { a: 0.0, b: -1.0, c: H + old_dy }, Half { a: 0.0, b: 1.0, c: -(new_dy) })
                } else {
                    (Half { a: 0.0, b: 1.0, c: -old_dy }, Half { a: 0.0, b: -1.0, c: H + new_dy })
                };
                cv.clips.push(old_side);
                if let Some((t, r)) = content(self, cv, prev, 0.0, old_dy, old_c) { chars.push((t, r, Some(old_side), prev, old_c)); }
                cv.clips.pop();
                cv.clips.push(new_side);
                if let Some((t, r)) = content(self, cv, cur, 0.0, new_dy, new_c) { chars.push((t, r, Some(new_side), cur, new_c)); }
                cv.clips.pop();
                // the ink gutter between them
                let gy = if d > 0.0 { H + old_dy } else { old_dy - GUTTER };
                cv.clips.push(panel_clip);
                ink_gutter(cv, gy, self.changed.map_or(0, |t| (t * 10.0) as u32));
                cv.clips.pop();
            } else {
                if let Some((t, r)) = content(self, cv, cur, 0.0, 0.0, 0.0) { chars.push((t, r, None, cur, 0.0)); }
            }
        }
        // the window's edge: ink, with the mode's colour inside it
        let edge_col = if swapping { mix(man.modes[prev].color, man.modes[cur].color, pan) } else { man.modes[cur].color };
        let e0 = p0 + pdx;
        cv.fill(&[([e0 - 12.0, -40.0], rgba(INK, 1.0)), ([e0 + 12.0, -40.0], rgba(INK, 1.0)), ([e0 + 12.0 - lean, H + 40.0], rgba(INK, 1.0)), ([e0 - 12.0 - lean, H + 40.0], rgba(INK, 1.0))]);
        cv.fill(&[([e0 + 10.0, -40.0], rgba(edge_col, 1.0)), ([e0 + 16.0, -40.0], rgba(edge_col, 1.0)), ([e0 + 16.0 - lean, H + 40.0], rgba(edge_col, 1.0)), ([e0 + 10.0 - lean, H + 40.0], rgba(edge_col, 1.0))]);
        if impact_frame {
            // the impact in KIU's own ink: black silhouettes and lines on bare paper
            let t = &self.art.modes[1].paper;
            cv.image(t, [0.0, 0.0, W, H], 0.0, [0.0, 0.0], Color32::WHITE);
            speed_lines(cv, man.impact, 1000 + conf_c as u32, 1.0, INK, 90);
            let (i, _) = char_index(self, 1);
            if let Some(fr) = self.stream.get(ctx, 1, i, &[]) {
                cv.frame(&fr, [fr.at[0] + vx_hit + 1.7 * cx, fr.at[1] + 1.7 * cy, fr.size[0], fr.size[1]], Color32::from_rgba_premultiplied(0, 0, 0, 255));
            }
        } else {
            for (t, r, side, m, dy) in &chars {
                if let Some(h) = side { cv.clips.push(*h); }
                cv.frame(t, *r, Color32::WHITE);
                if side.is_some() { cv.clips.pop(); }
                // the near particles, in front of the character, in the window
                if v >= 14.0 { cv.clips.push(panel_clip); self.particles(cv, *m, v, *dy, true); cv.clips.pop(); }
            }
            // the kick lands: flash, feathers, a white flash over everything
            if let Some(t) = after_hit.filter(|&t| t >= 2.0).map(|t| t - 2.0) {
                if t < 22.0 {
                    let sz = 400.0 + 1000.0 * ease(Ease::Out, clamp01(t / 6.0)); let fa = 1.0 - clamp01((t - 4.0) / 18.0);
                    let ip = man.impact;
                    cv.image(&self.art.flash.clone(), [ip[0] - sz / 2.0, ip[1] - sz / 2.0, sz, sz], 0.0, ip, additive([255, 220, 160], fa));
                }
                if t < 70.0 { self.feathers(cv, t); }
                if t < 8.0 { let a = 150.0 / 255.0 * (1.0 - t / 8.0); cv.fill(&[([0.0, 0.0], rgba([255, 244, 220], a)), ([W, 0.0], rgba([255, 244, 220], a)), ([W, H], rgba([255, 244, 220], a)), ([0.0, H], rgba([255, 244, 220], a))]); }
            }
        }
        // ink ornaments framing the window (they move the most), the ground band, the sprig;
        // the push-in carries them out of the picture
        let kick = if self.changed.is_some() { -d * track(ts, &[(4.0, 26.0, Ease::Out), (24.0, 0.0, Ease::OutBack)]) } else { 0.0 };
        let sw_at = man.swirl.at;
        cv.image_at(&self.art.swirl.clone(), [sw_at[0] + pdx.max(0.0) + 2.4 * cx, sw_at[1] + 2.4 * cy + kick - 260.0 * push], Color32::WHITE);
        let band_y = k2(6.0, 200.0, 20.0, 0.0, Ease::Out, v) + 360.0 * push;
        cv.image_at(&self.art.band.clone(), [man.band.at[0], man.band.at[1] + band_y], Color32::WHITE);
        {
            let t = self.art.sprig.clone(); let s = t.size(); let b = man.sprig.base;
            let sway = 2.5 * (TAU * v / 200.0).sin();
            let y = b[1] + k2(8.0, 260.0, 22.0, 0.0, Ease::Out, v) + 360.0 * push;
            let x = b[0] + 1.4 * cx;
            cv.image(&t, [x - s[0] as f32 / 2.0, y - s[1] as f32, s[0] as f32, s[1] as f32], sway, [x, y], Color32::WHITE);
        }
        vignette(cv);
        // 5. the menu's words: heading, caption, controls (they move with the pan)
        let ok0 = self.out_k(0);
        let head = |cv: &mut Canvas, m: usize, a: f32, s: f32, dy: f32, sq: [f32; 2]| {
            if a <= 0.01 { return; }
            let t = &self.art.modes[m].heading; let sz = t.size(); let b = man.modes[m].heading.base;
            let float = 4.0 * (TAU * v / 150.0).sin(); let r = 0.6 * (TAU * v / 210.0).sin();
            let (w, h) = (sz[0] as f32 * s * sq[0], sz[1] as f32 * s * sq[1]);
            let y1 = b[1] + dy + float;
            cv.image(t, [b[0] - w / 2.0, y1 - h, w, h], r, [b[0], y1 - h / 2.0], faded(a));
        };
        if self.changed.is_none() {
            head(cv, cur, k2(24.0, 0.0, 30.0, 1.0, Ease::Out, v) * (1.0 - ok0), track(v, &[(24.0, 0.6, Ease::Out), (38.0, 1.0, Ease::OutBack)]), -260.0 * ok0, [1.0, 1.0]);
        } else {
            if ts < 9.0 { let k = k2(0.0, 0.0, 8.0, 1.0, Ease::In, ts); head(cv, prev, 1.0 - k, 1.0, -d * 50.0 * k, [1.0, 1.0]); }
            if ts >= 7.0 {
                let arrive = track(ts, &[(7.0, d * 60.0, Ease::Out), (21.0, 0.0, Ease::OutBack)]);
                head(cv, cur, k2(7.0, 0.0, 11.0, 1.0, Ease::Out, ts) * (1.0 - ok0), 1.0, arrive - 260.0 * ok0, [1.0, 1.0]);
            }
        }
        let ok3 = self.out_k(3); let ok4 = self.out_k(4);
        let caption = |cv: &mut Canvas, m: usize, a: f32, dy: f32| {
            if a <= 0.01 { return; }
            let p = &man.modes[m].caption; cv.image_at(&self.art.modes[m].caption, [p.at[0], p.at[1] + dy], faded(a));
        };
        if self.changed.is_none() {
            caption(cv, cur, k2(40.0, 0.0, 56.0, 1.0, Ease::Out, v) * (1.0 - ok3), k2(40.0, 30.0, 56.0, 0.0, Ease::Out, v) + 160.0 * ok3);
        } else {
            if ts < 7.0 { caption(cv, prev, 1.0 - k2(0.0, 0.0, 6.0, 1.0, Ease::In, ts), -d * 16.0 * k2(0.0, 0.0, 6.0, 1.0, Ease::In, ts)); }
            if ts >= 10.0 { caption(cv, cur, k2(10.0, 0.0, 18.0, 1.0, Ease::Out, ts) * (1.0 - ok3), k2(10.0, d * 24.0, 22.0, 0.0, Ease::Out, ts) + 160.0 * ok3); }
        }
        cv.image_at(&self.art.controls.clone(), [man.controls.at[0], man.controls.at[1] + 160.0 * ok4], faded(k2(46.0, 0.0, 60.0, 1.0, Ease::Out, v) * (1.0 - ok4)));
        // the press: a gold ring from the button
        if let (Phase::Confirming { .. }, Some(p)) = (self.phase, self.pressed_at) {
            if conf_c < 18.0 { ring(cv, p, conf_c / 18.0); }
        }
    }

    /// Particles in the window, the mode's own, in depth: far ones (small,
    /// dim, slow) behind the character, near ones (big, faster) in front.
    fn particles(&self, cv: &mut Canvas, mode: usize, v: f32, dy: f32, near: bool) {
        let t = v / 60.0;
        let mut rnd = Rng([4, 1, 2, 3][mode] * 7919 + if near { 17 } else { 0 });
        let n = if near { 6 } else { 14 };
        let (x0, x1, y0, y1) = (self.man.panel.x0 - 200.0, W + 80.0, -80.0, self.man.band_y + 40.0);
        for k in 0..n {
            let z = if near { rnd.f(1.3, 1.8) } else { rnd.f(0.45, 0.9) };
            let ph = rnd.f(0.0, 1.0); let ph2 = rnd.f(0.0, 1.0); let spin = rnd.f(-1.0, 1.0); let sz = rnd.f(0.8, 1.2) * z;
            let alpha = if near { 0.85 } else { 0.35 + 0.35 * z };
            // each mode moves its own way, nearer ones faster (parallax)
            let (mut x, mut y, rot, tex, col, w, h) = match mode {
                0 => { // Solo: feathers streaming past Pit, down to the left
                    let sp = 520.0 * z; let len = (x1 - x0) + (y1 - y0);
                    let s = (t * sp / len + ph) % 1.0;
                    (x1 - s * (x1 - x0) + ph2 * 300.0, y0 + s * (y1 - y0) * 0.8 + ph2 * (y1 - y0) * 0.6 - 200.0, spin * 200.0 * t + 40.0, &self.art.feather, [255, 255, 255], 60.0 * sz, 30.0 * sz)
                }
                1 => { // Together: feathers knocked loose, drifting down
                    let sp = 60.0 * z; let s = (t * sp / (y1 - y0) + ph) % 1.0;
                    (x0 + ph2 * (x1 - x0) + (t * 1.3 + k as f32).sin() * 40.0, y0 + s * (y1 - y0), (t * 1.7 + k as f32).sin() * 50.0 + spin * 30.0, &self.art.feather, if k % 3 != 0 { [255, 255, 255] } else { [70, 60, 90] }, 56.0 * sz, 28.0 * sz)
                }
                2 => { // Vault: motes of light rising round her, twinkling
                    let sp = 40.0 * z; let s = (t * sp / (y1 - y0) + ph) % 1.0;
                    let tw = 0.55 + 0.45 * (t * 3.0 + k as f32 * 1.7).sin();
                    let d = 30.0 * sz * (0.6 + 0.6 * tw);
                    (1050.0 + ph2 * 760.0 + (t * 0.8 + k as f32).sin() * 30.0, y1 - s * (y1 - y0), 0.0, &self.art.spark, [210, 255, 235], d, d)
                }
                _ => { // Options: leaves blown across, fluttering
                    let sp = 110.0 * z; let s = (t * sp / (x1 - x0) + ph) % 1.0;
                    (x1 - s * (x1 - x0) * 1.2, y0 + ph2 * (y1 - y0) * 0.9 + s * 160.0 + (t * 2.2 + k as f32).sin() * 26.0, spin * 120.0 * t + (t * 3.0 + k as f32).sin() * 40.0,
                     &self.art.leaves[k % self.art.leaves.len().max(1)], if k % 2 != 0 { [255, 228, 240] } else { [255, 170, 210] }, 46.0 * sz, 46.0 * sz)
                }
            };
            y += dy; x += 0.0;
            let fade = clamp01((y1 - y) / 120.0) * clamp01((y - y0) / 120.0);
            if fade <= 0.0 { continue; }
            cv.image(tex, [x - w / 2.0, y - h / 2.0, w, h], rot, [x, y], rgba(col, alpha * fade));
        }
    }

    /// Feathers bursting from the kick.
    fn feathers(&self, cv: &mut Canvas, t: f32) {
        let mut rnd = Rng(8 * 7919); let ip = self.man.impact;
        for n in 0..30 {
            let an = rnd.f(0.0, std::f32::consts::TAU); let sp = rnd.f(10.0, 26.0);
            let d = 100.0 + sp * 14.0 * ease(Ease::Out, clamp01(t / 14.0)) + sp * (t - 14.0).max(0.0) * 0.6;
            let col = if n % 3 != 0 { [255, 255, 255] } else { [120, 90, 170] };
            let p = [ip[0] + an.cos() * d, ip[1] + an.sin() * d + 0.12 * t * t];
            cv.image(&self.art.feather, [p[0] - 42.0, p[1] - 21.0, 84.0, 42.0], -an.to_degrees() + t * 6.0, p, rgba(col, 1.0 - clamp01((t - 40.0) / 30.0)));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn tracks_reach_their_keys() {
        let k = [(0.0, 10.0, Ease::Out), (10.0, 20.0, Ease::OutBack), (20.0, 0.0, Ease::In)];
        assert_eq!(track(-5.0, &k), 10.0);
        assert!((track(10.0, &k) - 20.0).abs() < 1e-4);
        assert!(track(8.0, &k) > 20.0, "overshoots on the way in");
        assert_eq!(track(30.0, &k), 0.0);
    }
    #[test]
    fn clipping_keeps_one_side() {
        let sq = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]].map(|p| Vx { p, uv: [p[0] / 10.0, p[1] / 10.0], c: Color32::WHITE });
        let half = clip(&sq, Half { a: 1.0, b: 0.0, c: -4.0 });     // x >= 4
        assert!(half.iter().all(|v| v.p[0] >= 4.0 - 1e-4));
        assert!(half.iter().any(|v| (v.uv[0] - 0.4).abs() < 1e-4), "texture coordinates follow the cut");
        assert!(clip(&sq, Half { a: 1.0, b: 0.0, c: -20.0 }).is_empty());
    }
    #[test]
    fn idle_loops_and_turns_back() {
        let c = Character { dir: String::new(), frames: vec![], intro: Some(Seq { range: [150, 195], play: None, impact: None }),
            idle: Seq { range: [195, 225], play: Some("pingpong".into()), impact: None }, confirm: Seq { range: [225, 259], play: None, impact: None } };
        assert_eq!(idle_index(&c, 0.0), 150);
        assert_eq!(idle_index(&c, 45.0), 195);
        // 30 frames of sweep with a 12-frame soft turn at each end: 54 frames each way
        assert_eq!(idle_index(&c, 45.0 + 54.0), 225, "the far end");
        assert_eq!(idle_index(&c, 45.0 + 108.0), 195, "and back");
        let steps: Vec<i32> = (0..108).map(|t| idle_index(&c, 45.0 + t as f32 + 1.0) - idle_index(&c, 45.0 + t as f32)).collect();
        assert!(steps.iter().all(|d| d.abs() <= 1), "never skips a frame: {steps:?}");
        let l = Character { intro: None, idle: Seq { range: [0, 359], play: Some("loop".into()), impact: None }, ..c };
        assert_eq!(idle_index(&l, 360.0), 0);
        assert_eq!(idle_index(&l, 361.0), 1);
    }
    #[test]
    fn the_brush_leaves_the_window_edge_alone() {
        let r = Half::right_of(900.0, 330.0);
        assert!(r.at([901.0, -40.0]) > 0.0 && r.at([899.0, -40.0]) < 0.0);
        assert!(r.at([900.0 - 330.0 + 1.0, H + 40.0]) > 0.0, "the edge leans left toward the bottom");
    }
}

