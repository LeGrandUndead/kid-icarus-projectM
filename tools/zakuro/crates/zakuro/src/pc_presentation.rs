//! Host presentation policy, decided in one place. Guest scene identity comes
//! only from verified evidence (`zakuro_gpu::kiu_ui::BottomScene`, built from
//! original ROM texture identity); it is never guessed from pixels.
use crate::settings::Screens;
use zakuro_gpu::kiu_ui::BottomScene;
use zakuro_gpu::{Recipe, ScreenLayout};
use zakuro_core::services::hid::{InputState, PadState};

#[derive(Debug, PartialEq, Eq)]
pub enum InputContext { GameplayCapture, PointerMenu, LegacyPointer, RuntimeModal }

/// What the player is shown.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PresentationMode {
    /// Not the KIU PC presentation (other titles, normal launcher).
    Original,
    /// One gameplay view; original portraits/HUD relocated over it.
    Gameplay,
    /// The original interactive lower screen as a panel over the view, opened
    /// with Tab or automatically for the game's own pause menu.
    LowerScreenPanel { automatic: bool },
    /// Development/regression comparison: both original screens.
    LegacyDualScreen,
    /// The game's out-of-stage menus on one screen, arranged as on the
    /// console (ScreenLayout::Menus), the lower picture clickable, while the
    /// game shows a menu screen.
    Menus,
}

/// Why the lower screen was opened without the player asking.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AutoPanel {
    /// the in-game pause menu: a panel over the frozen gameplay view
    Pause,
    /// an out-of-stage menu screen (save select, main menu, Solo...),
    /// both pictures composed as one scene
    Menus,
}

/// Change the panel because of what the game is showing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PanelRequest { Keep, Open, Close, Relayout }

/// Consecutive frames of gameplay HUD without any menu art before an
/// automatically opened pause panel closes again (a third of a second).
const CLOSE_AFTER: u32 = 20;
/// Frames without menu art before the menus' layout ends (a quarter of a
/// second: frames the game skips or fades through do not flicker it).
const MENUS_GONE: u32 = 15;
/// Frames a 3D upper picture counts for: rooms keep their layout through
/// a frame or two drawn without 3D.
const ROOM_FRAMES: u32 = 30;

#[derive(Default)]
pub struct PcPresentation {
    pub enabled: bool,
    pub legacy: bool,
    /// Previous host layout and captured aim, never guest gameplay state.
    pub access: Option<(Screens, Option<[f32; 2]>)>,
    pub boundary: bool,
    blocked_buttons: PadState,
    blocked_stick: bool,
    /// The panel was opened for a detected menu, not by the player.
    automatic: Option<AutoPanel>,
    /// The player closed an automatic panel; wait until that menu is gone.
    suppressed: bool,
    gameplay_frames: u32,
    /// Consecutive frames without menu art.
    away_frames: u32,
    /// Frames a 3D upper picture still counts for (ROOM_FRAMES after one).
    room_frames: u32,
    /// The menus' upper picture is a 3D room (decided from room_frames).
    room: bool,
    /// The menu shown has its own one-screen composition.
    recipe: Option<Recipe>,
}

impl PcPresentation {
    pub fn new(enabled: bool) -> Self { Self { enabled, ..Self::default() } }
    pub fn layout(&self, original: Screens, wide: bool) -> ScreenLayout {
        if self.enabled {
            if self.access.is_some() {
                return if self.automatic == Some(AutoPanel::Menus) {
                    match self.recipe {
                        Some(recipe) => ScreenLayout::Composed { wide, recipe },
                        None => ScreenLayout::Menus { wide, room: self.room },
                    }
                }
                    else { ScreenLayout::BottomOverlay { wide } };
            }
            if self.legacy { return if wide { ScreenLayout::StackedWide } else { ScreenLayout::Stacked }; }
            return if wide { ScreenLayout::TopWide } else { ScreenLayout::TopOnly };
        }
        if wide && original == Screens::TopOnly { ScreenLayout::TopWide }
        else { original.screens() }
    }

    pub fn mode(&self) -> PresentationMode {
        if !self.enabled { PresentationMode::Original }
        else if self.access.is_some() && self.automatic == Some(AutoPanel::Menus) { PresentationMode::Menus }
        else if self.access.is_some() { PresentationMode::LowerScreenPanel { automatic: self.automatic.is_some() } }
        else if self.legacy { PresentationMode::LegacyDualScreen }
        else { PresentationMode::Gameplay }
    }

    /// Relocated original layers are part of the gameplay view only.
    pub fn gameplay_layers_visible(&self, captured: bool, runtime_menu: bool) -> bool {
        self.mode() == PresentationMode::Gameplay && captured && !runtime_menu
    }

    /// The automatic panel kind, if the panel is open because of the game.
    pub fn automatic(&self) -> Option<AutoPanel> { self.automatic.filter(|_| self.access.is_some()) }

    /// Follows the game's own pause menu and its out-of-stage menus.
    /// `allowed` is false while a runtime menu/modal owns input or the option
    /// is off. Menus are known by their own art on the lower screen, never
    /// beside gameplay HUD or the pause menu.
    pub fn observe(&mut self, scene: BottomScene, allowed: bool) -> PanelRequest {
        if !self.enabled || self.legacy { return PanelRequest::Keep; }
        let menus = (scene.menu_screen || scene.save_select) && scene.hud == 0 && !scene.pause_menu;
        if menus { self.away_frames = 0; } else { self.away_frames = self.away_frames.saturating_add(1); }
        self.room_frames = if scene.top_3d { ROOM_FRAMES } else { self.room_frames.saturating_sub(1) };
        let room = self.room_frames > 0;
        // menus recomposed as one picture so far: the save select
        let recipe = scene.save_select.then_some(Recipe::SaveSelect);
        match self.automatic() {
            Some(AutoPanel::Menus) => {
                if self.away_frames >= MENUS_GONE {
                    self.automatic = None;
                    return PanelRequest::Close;
                }
                // a skipped frame keeps the menu's composition
                let recipe = if menus { recipe } else { self.recipe };
                if room != self.room || recipe != self.recipe {
                    self.room = room;
                    self.recipe = recipe;
                    return PanelRequest::Relayout;
                }
                return PanelRequest::Keep;
            }
            // retreating from a stage: its pause panel leads into the menus
            Some(AutoPanel::Pause) if menus => {
                self.automatic = Some(AutoPanel::Menus);
                self.room = room;
                self.recipe = recipe;
                return PanelRequest::Relayout;
            }
            _ => {}
        }
        if menus {
            if self.access.is_none() && allowed && !self.suppressed {
                self.automatic = Some(AutoPanel::Menus);
                self.room = room;
                self.recipe = recipe;
                return PanelRequest::Open;
            }
            return PanelRequest::Keep;
        }
        if scene.pause_menu {
            self.gameplay_frames = 0;
            if allowed && self.access.is_none() && !self.suppressed {
                self.automatic = Some(AutoPanel::Pause);
                return PanelRequest::Open;
            }
            return PanelRequest::Keep;
        }
        if !scene.menu && !scene.menu_screen && !scene.save_select { self.suppressed = false; }
        if self.automatic() != Some(AutoPanel::Pause) { return PanelRequest::Keep; }
        // Closing needs positive evidence of gameplay, not just a missing
        // label: option sub-panels may draw other art.
        if scene.fresh {
            if !scene.menu && scene.hud > 0 { self.gameplay_frames += 1; } else { self.gameplay_frames = 0; }
        }
        if self.gameplay_frames >= CLOSE_AFTER {
            self.gameplay_frames = 0;
            self.automatic = None;
            return PanelRequest::Close;
        }
        PanelRequest::Keep
    }

    /// The panel closed for any reason. A player closing an automatic panel
    /// over a still-visible pause menu is respected until that menu ends.
    pub fn panel_closed(&mut self, by_player: bool, scene: BottomScene) {
        if self.automatic.is_some() && by_player && (scene.pause_menu || scene.menu || scene.menu_screen || scene.save_select) { self.suppressed = true; }
        self.automatic = None;
        self.gameplay_frames = 0;
    }

    pub fn context(&self, captured: bool, modal: bool) -> InputContext {
        if modal { InputContext::RuntimeModal }
        else if self.access.is_some() { InputContext::PointerMenu }
        else if captured { InputContext::GameplayCapture }
        else { InputContext::LegacyPointer }
    }

    pub fn focus_lost(&mut self) {
        if let Some((_, aim)) = &mut self.access { *aim = None; }
        self.boundary = true;
    }

    /// A held controller action must not become a fresh action in a new UI.
    /// Outside transitions the original gamepad mapping passes through.
    pub fn controller(&mut self, mut input: InputState) -> InputState {
        if !self.enabled { return input; }
        if std::mem::take(&mut self.boundary) {
            self.blocked_buttons = input.buttons;
            self.blocked_stick = input.circle_x != 0.0 || input.circle_y != 0.0;
        }
        self.blocked_buttons &= input.buttons;
        input.buttons &= !self.blocked_buttons;
        if self.blocked_stick {
            self.blocked_stick = input.circle_x != 0.0 || input.circle_y != 0.0;
            input.circle_x=0.0; input.circle_y=0.0;
        }
        input
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fallback_and_overlay_preserve_aspect_policy() {
        let mut p=PcPresentation { enabled:true, ..Default::default() };
        assert_eq!(p.layout(Screens::BottomOnly,true),ScreenLayout::TopWide);
        p.legacy=true;
        assert_eq!(p.layout(Screens::TopOnly,true),ScreenLayout::StackedWide);
        p.access=Some((Screens::TopOnly,Some([319.0,120.0])));
        assert_eq!(p.layout(Screens::TopOnly,true),ScreenLayout::BottomOverlay { wide:true });
        assert_eq!(p.context(false,false),InputContext::PointerMenu);
        p.focus_lost();
        assert_eq!(p.access.unwrap().1,None);
        assert_eq!(p.context(false,true),InputContext::RuntimeModal);
    }
    fn scene(pause: bool, menu: bool, hud: u16) -> BottomScene {
        BottomScene { fresh: true, pause_menu: pause, menu: menu || pause, hud, ..BottomScene::default() }
    }

    #[test]
    fn pause_menu_opens_the_panel_and_gameplay_closes_it() {
        let mut p = PcPresentation::new(true);
        assert_eq!(p.mode(), PresentationMode::Gameplay);
        assert_eq!(p.observe(scene(false, false, 3), true), PanelRequest::Keep);
        assert_eq!(p.observe(scene(true, true, 3), true), PanelRequest::Open);
        p.access = Some((Screens::TopOnly, Some([10.0, 20.0])));
        assert_eq!(p.mode(), PresentationMode::LowerScreenPanel { automatic: true });
        assert!(!p.gameplay_layers_visible(true, false));
        // a sub-panel without the label and without HUD keeps it open
        for _ in 0..100 { assert_eq!(p.observe(scene(false, true, 0), true), PanelRequest::Keep); }
        for _ in 0..100 { assert_eq!(p.observe(scene(false, false, 0), true), PanelRequest::Keep); }
        // repeated (not fresh) summaries do not count
        for _ in 0..100 { assert_eq!(p.observe(BottomScene { hud: 3, ..BottomScene::default() }, true), PanelRequest::Keep); }
        for _ in 0..CLOSE_AFTER - 1 { assert_eq!(p.observe(scene(false, false, 3), true), PanelRequest::Keep); }
        assert_eq!(p.observe(scene(false, false, 3), true), PanelRequest::Close);
    }

    #[test]
    fn menus_get_the_console_arrangement_while_their_art_is_drawn() {
        let select = BottomScene { fresh: true, save_select: true, menu_screen: true, ..BottomScene::default() };
        let other = BottomScene { fresh: true, ..BottomScene::default() };
        let mut p = PcPresentation::new(true);
        assert_eq!(p.observe(select, true), PanelRequest::Open);
        p.access = Some((Screens::TopOnly, None));
        assert_eq!(p.mode(), PresentationMode::Menus);
        assert_eq!(p.layout(Screens::TopOnly, true), ScreenLayout::Composed { wide: true, recipe: Recipe::SaveSelect });
        assert_eq!(p.context(false, false), InputContext::PointerMenu);
        // leaving the save select for the main menu: the console arrangement
        let main = BottomScene { fresh: true, menu_screen: true, ..BottomScene::default() };
        assert_eq!(p.observe(main, true), PanelRequest::Relayout);
        assert_eq!(p.layout(Screens::TopOnly, true), ScreenLayout::Menus { wide: true, room: false });
        assert_eq!(p.observe(select, true), PanelRequest::Relayout);
        // a skipped frame does not lose the save select's composition
        assert_eq!(p.observe(other, true), PanelRequest::Keep);
        assert_eq!(p.layout(Screens::TopOnly, true), ScreenLayout::Composed { wide: true, recipe: Recipe::SaveSelect });
        assert_eq!(p.observe(select, true), PanelRequest::Keep);
        // a few frames without its art (skipped frames, fades) keep it
        for _ in 0..MENUS_GONE - 1 { assert_eq!(p.observe(other, true), PanelRequest::Keep); }
        assert_eq!(p.observe(select, true), PanelRequest::Keep);
        for _ in 0..MENUS_GONE - 1 { assert_eq!(p.observe(other, true), PanelRequest::Keep); }
        assert_eq!(p.observe(other, true), PanelRequest::Close);
        p.access = None;
        p.panel_closed(false, other);
        assert_eq!(p.mode(), PresentationMode::Gameplay);
        // the player leaving it with Tab is respected while it lasts
        assert_eq!(p.observe(select, true), PanelRequest::Open);
        p.access = Some((Screens::TopOnly, None));
        p.access = None;
        p.panel_closed(true, select);
        for _ in 0..30 { assert_eq!(p.observe(select, true), PanelRequest::Keep); }
        assert_eq!(p.observe(other, true), PanelRequest::Keep);
        assert_eq!(p.observe(select, true), PanelRequest::Open);
        // not while the runtime's own menus own the input
        let mut q = PcPresentation::new(true);
        assert_eq!(q.observe(select, false), PanelRequest::Keep);
        // menu art beside gameplay HUD is not a menu screen
        let mut h = PcPresentation::new(true);
        assert_eq!(h.observe(BottomScene { fresh: true, menu_screen: true, hud: 3, ..BottomScene::default() }, true), PanelRequest::Keep);
        // retreating from a stage: the pause panel becomes the menus' layout
        let mut r = PcPresentation::new(true);
        assert_eq!(r.observe(scene(true, true, 0), true), PanelRequest::Open);
        r.access = Some((Screens::TopOnly, None));
        let main = BottomScene { fresh: true, menu_screen: true, ..BottomScene::default() };
        assert_eq!(r.observe(main, true), PanelRequest::Relayout);
        assert_eq!(r.mode(), PresentationMode::Menus);
    }

    #[test]
    fn a_3d_room_above_the_menu_keeps_the_wide_view() {
        let room = BottomScene { fresh: true, menu_screen: true, top_3d: true, ..BottomScene::default() };
        let flat = BottomScene { fresh: true, menu_screen: true, ..BottomScene::default() };
        let mut p = PcPresentation::new(true);
        assert_eq!(p.observe(room, true), PanelRequest::Open);
        p.access = Some((Screens::TopOnly, None));
        assert_eq!(p.layout(Screens::TopOnly, true), ScreenLayout::Menus { wide: true, room: true });
        // a frame or two without 3D do not change it, a flat menu does
        for _ in 0..ROOM_FRAMES - 1 { assert_eq!(p.observe(flat, true), PanelRequest::Keep); }
        assert_eq!(p.observe(flat, true), PanelRequest::Relayout);
        assert_eq!(p.layout(Screens::TopOnly, true), ScreenLayout::Menus { wide: true, room: false });
        assert_eq!(p.observe(room, true), PanelRequest::Relayout);
    }

    #[test]
    fn player_choices_win_over_detection() {
        let mut p = PcPresentation::new(true);
        // not allowed (runtime menu/option off): no panel
        assert_eq!(p.observe(scene(true, true, 0), false), PanelRequest::Keep);
        assert_eq!(p.observe(scene(true, true, 0), true), PanelRequest::Open);
        p.access = Some((Screens::TopOnly, None));
        // player closes it over the pause menu: stays closed while it lasts
        p.access = None;
        p.panel_closed(true, scene(true, true, 0));
        for _ in 0..10 { assert_eq!(p.observe(scene(true, true, 0), true), PanelRequest::Keep); }
        // the next pause opens it again
        assert_eq!(p.observe(scene(false, false, 3), true), PanelRequest::Keep);
        assert_eq!(p.observe(scene(true, true, 3), true), PanelRequest::Open);
        // a panel the player opened with Tab is never closed automatically
        let mut q = PcPresentation::new(true);
        q.access = Some((Screens::TopOnly, None));
        for _ in 0..100 { assert_eq!(q.observe(scene(false, false, 3), true), PanelRequest::Keep); }
        // legacy and disabled modes never react
        q.access = None; q.legacy = true;
        assert_eq!(q.mode(), PresentationMode::LegacyDualScreen);
        assert_eq!(q.observe(scene(true, true, 0), true), PanelRequest::Keep);
        assert_eq!(PcPresentation::default().observe(scene(true, true, 0), true), PanelRequest::Keep);
        assert_eq!(PcPresentation::default().mode(), PresentationMode::Original);
    }

    #[test]
    fn disabled_policy_keeps_existing_layouts() {
        let p=PcPresentation::default();
        for view in Screens::ALL { assert_eq!(p.layout(view,false),view.screens()); }
    }
    #[test]
    fn held_controller_action_waits_for_release_across_menu_boundary() {
        let mut p=PcPresentation { enabled:true,boundary:true,..Default::default() };
        let held=InputState { buttons:PadState::L,circle_x:1.0,..Default::default() };
        for _ in 0..3 {
            let state=p.controller(held);
            assert!(state.buttons.is_empty()); assert_eq!(state.circle_x,0.0);
        }
        p.controller(InputState::default());
        let state=p.controller(held);
        assert_eq!(state.buttons,PadState::L); assert_eq!(state.circle_x,1.0);
    }
}
