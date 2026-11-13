//! The PC menus while a game runs: one value the frontend keeps (`PcMenus`)
//! and drives with five calls, in this order each frame:
//!
//! 1. `set_screen`: the screen the game shows now, from its screen recipe
//!    (a redrawn screen, or none);
//! 2. `cursor_press`: when the frame's input is made, the D-pad press that
//!    walks the game's cursor to what the pointer points at;
//! 3. `observe`: after the game's frame, which choice its upper screen shows
//!    selected;
//! 4. `show`: when the interface is drawn, the main menu's scene and the
//!    screen's buttons, returning the touch a click asks for;
//! 5. `check_click`: after the touch is started, whether the game took the
//!    last click (it is given once more if not).

use std::sync::mpsc::{Receiver, TryRecvError};

use crate::pc_menus::art::{self, Art};
use crate::pc_menus::buttons::{self, Live};
use crate::pc_menus::cursor::Dir;
use crate::pc_menus::scene::{self, Scene, Upload};
use crate::pc_menus::screens::{Screen, MAIN_MENU, SCREENS};
use crate::top_menus::Tap;

/// A click on a redrawn button the game has not answered yet.
struct Click {
    /// the touch it gave
    at: (u16, u16),
    /// frames waited since the touch ended
    waited: u32,
    /// it was given a second time already
    again: bool,
}

/// Frames to wait for the game to leave a screen after a click before giving
/// the click again: 2 s, longer than any of the game's transitions takes to
/// begin (the slowest seen: 1.6 s), so a second touch never lands on the
/// next screen.
const CLICK_PATIENCE: u32 = 120;

pub struct PcMenus {
    /// the redrawn screen the game shows, if any
    screen: Option<&'static Screen>,
    /// its buttons' motion and the game's cursor
    live: Live,
    /// the upper-screen art watched last frame (for the log)
    watched: u32,
    click: Option<Click>,
    /// the screens' art: prepared on its own thread from start-up, uploaded
    /// once and kept
    art_coming: Option<Receiver<Vec<art::Prepared>>>,
    arts: Vec<Art>,
    /// the main menu's scene: its pack read on its own thread from start-up,
    /// uploaded a few layers a frame, then kept for every visit
    scene_coming: Option<Receiver<Option<scene::Prepared>>>,
    scene_upload: Option<Upload>,
    scene: Option<Scene>,
}

impl PcMenus {
    /// Starts reading the menus' art in the background (when the menu art
    /// pack is there).
    pub fn new() -> PcMenus {
        PcMenus {
            screen: None,
            live: Live::default(),
            watched: 0,
            click: None,
            art_coming: crate::pc_menus::menu_art_pack().map(|_| art::prepare()),
            arts: Vec::new(),
            scene_coming: scene::pack().map(scene::prepare),
            scene_upload: None,
            scene: None,
        }
    }

    /// The redrawn screen the game shows now (`None`: none), as its menu
    /// archive. A new screen starts fresh: its buttons at home, the game's
    /// cursor unknown, its selection art watched on the upper screen.
    pub fn set_screen(&mut self, id: Option<u16>) {
        let screen = id.and_then(|id| SCREENS.iter().copied().find(|s| s.id == id));
        if screen.map(|s| s.id) == self.screen.map(|s| s.id) { return; }
        log::info!("Redrawn menu: {}", screen.map_or("none".into(), |s| format!("screen {:03}", s.id)));
        self.screen = screen;
        self.live = Live::default();
        zakuro_gpu::kiu_ui::watch_top(screen.map_or(&[][..], |s| s.selected_art));
    }

    /// The D-pad press walking the game's cursor this frame. None during a
    /// click: a D-pad press held with the touch can make the game ignore it.
    pub fn cursor_press(&mut self) -> Option<Dir> {
        let screen = self.screen?;
        if self.click.is_some() { return None; }
        self.live.nav.pad(&screen.graph, |n| screen.shows(n))
    }

    /// After the game's frame: the upper-screen art it drew (`watched`, in
    /// the screen's `selected_art` order) says which choice is selected.
    /// Only frames whose upper screen was drawn say anything.
    pub fn observe(&mut self, watched: u32, fresh: bool, frame: u64) {
        let Some(screen) = self.screen else { return };
        if watched != self.watched {
            log::debug!("Redrawn menu: upper art {watched:#06b} (selected {:?}, cursor {:?})", screen.selected(watched), self.live.nav.current);
            self.watched = watched;
        }
        if watched != 0 || fresh {
            self.live.nav.observe(screen.selected(watched), screen.any_selected(watched));
        }
        if self.live.nav.current.is_none() && frame % 300 == 0 {
            log::debug!("Redrawn menu: the game's selection is not known yet (upper art {watched:#06b})");
        }
    }

    /// Takes in what the background threads made and uploads it, and starts
    /// or rests the main menu's scene with the game's screen. Before drawing.
    fn update(&mut self, ctx: &egui::Context, game_running: bool) {
        if let Some(rx) = &self.art_coming {
            match rx.try_recv() {
                Ok(prepared) => { self.arts = prepared.iter().filter_map(|p| p.upload(ctx)).collect(); self.art_coming = None; }
                Err(TryRecvError::Disconnected) => {
                    log::warn!("Redrawn menu: the menu art pack (KIU_MENU_PACK) is missing or unreadable; the game's own menus are shown");
                    self.art_coming = None;
                }
                Err(TryRecvError::Empty) => {}
            }
        }
        if let Some(rx) = &self.scene_coming {
            match rx.try_recv() {
                Ok(Some(prepared)) => { self.scene_upload = Some(Upload::new(prepared)); self.scene_coming = None; }
                Ok(None) | Err(TryRecvError::Disconnected) => {
                    log::warn!("Main menu scene: its pack (menu-pc/scene-040) is missing or unreadable; the game's own upper screen is shown");
                    self.scene_coming = None;
                }
                Err(TryRecvError::Empty) => {}
            }
        }
        if let Some(up) = &mut self.scene_upload {
            if let Some(scene) = up.step(ctx) { self.scene = Some(scene); self.scene_upload = None; }
        }
        // the scene starts when the main menu appears, and is told when the
        // game leaves it (it then plays its exit and rests)
        if let Some(scene) = &mut self.scene {
            if game_running && self.screen.is_some_and(|s| s.id == MAIN_MENU.id) { scene.on_menu(ctx); } else { scene.game_left(); }
        }
    }

    /// Draws the main menu's scene and the screen's buttons over `window`
    /// (egui points). `visible`: the game is running and no PC panel covers
    /// it. Returns the touch a click asks for.
    pub fn show(&mut self, ctx: &egui::Context, window: egui::Rect, game_running: bool, visible: bool) -> Option<(u16, u16)> {
        self.update(ctx, game_running);
        let scene = self.scene.as_mut().filter(|s| s.active());
        if let Some(scene) = scene {
            // where the selection is going, not each choice the cursor passes on the way
            scene.select(self.live.nav.heading());
            if !scene.show(ctx, window) { log::info!("Main menu scene: finished (kept for the next visit)"); }
        }
        let screen = self.screen.filter(|_| visible)?;
        let art = self.arts.iter().find(|a| a.id == screen.id)?;
        let scene = self.scene.as_ref().filter(|s| s.active());
        let presence: Vec<(f32, f32)> = (0..screen.buttons.len()).map(|i| scene.map_or((0.0, 1.0), |s| s.button_presence(i))).collect();
        let interactive = scene.is_none_or(|s| s.interactive());
        let out = buttons::show(ctx, screen, art, &mut self.live, window, &presence, interactive);
        self.live.nav.want(out.entered);
        if let Some(scene) = self.scene.as_mut().filter(|s| s.active()) {
            if let Some((node, at)) = out.clicked { scene.confirm(node, Some(at), window); }
            if out.back { scene.back(); }
        }
        if let Some(at) = out.touch { self.click = Some(Click { at, waited: 0, again: false }); }
        out.touch
    }

    /// Once a frame after the touches are started: a click the game has not
    /// taken (still on the screen `CLICK_PATIENCE` frames after its touch)
    /// is given once more; the scene comes back by itself if that fails too.
    pub fn check_click(&mut self, tap: &mut Tap) {
        let Some(click) = &mut self.click else { return };
        if self.screen.is_none() { self.click = None; return; }
        if tap.busy() { return; }
        click.waited += 1;
        if click.waited <= CLICK_PATIENCE { return; }
        if click.again { self.click = None; return; }
        log::warn!("Redrawn menu: the game did not take the click at {:?}; giving it again", click.at);
        tap.start(click.at);
        click.waited = 0;
        click.again = true;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_click_the_game_ignores_is_given_once_more_then_dropped() {
        let mut pc = PcMenus { art_coming: None, scene_coming: None, ..PcMenus::new() };
        pc.set_screen(Some(MAIN_MENU.id));
        let mut tap = Tap::default();
        pc.click = Some(Click { at: (104, 52), waited: 0, again: false });
        // no cursor walk while a click is in flight
        assert_eq!(pc.cursor_press(), None);
        for _ in 0..CLICK_PATIENCE { pc.check_click(&mut tap); }
        assert!(!tap.busy(), "patient for 2 s");
        pc.check_click(&mut tap);
        assert!(tap.busy(), "then the touch again");
        while tap.next().is_some() {}
        for _ in 0..=CLICK_PATIENCE { pc.check_click(&mut tap); }
        assert!(pc.click.is_none() && !tap.busy(), "not a third time");
    }

    #[test]
    fn leaving_the_screen_ends_the_wait() {
        let mut pc = PcMenus { art_coming: None, scene_coming: None, ..PcMenus::new() };
        pc.set_screen(Some(MAIN_MENU.id));
        pc.click = Some(Click { at: (104, 52), waited: 0, again: false });
        pc.set_screen(None);
        pc.check_click(&mut Tap::default());
        assert!(pc.click.is_none());
    }
}
