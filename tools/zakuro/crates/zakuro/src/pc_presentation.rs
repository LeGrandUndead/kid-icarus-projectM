//! Host presentation policy, decided in one place. Guest scene identity comes
//! only from verified evidence (`zakuro_gpu::kiu_ui::BottomScene`, built from
//! original ROM texture identity); it is never guessed from pixels.
use crate::settings::Screens;
use zakuro_gpu::kiu_ui::BottomScene;
use zakuro_gpu::ScreenLayout;
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
    /// An out-of-stage menu (title, Solo, chapter select...): both of the
    /// game's pictures side by side on the one PC screen, the lower one
    /// clickable, shown automatically while the game shows a menu screen.
    MenuScreen,
}

/// Change the panel because of what the game is showing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PanelRequest { Keep, Open, Close, Relayout }

/// Why the lower screen was opened without the player asking.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AutoPanel {
    /// the in-game pause menu: a panel over the frozen gameplay view
    Pause,
    /// an out-of-stage menu screen: MenuScreen
    MenuScreen,
}

/// Consecutive frames of gameplay HUD without any menu art before an
/// automatically opened pause panel closes again (a third of a second).
const CLOSE_AFTER: u32 = 20;

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
}

impl PcPresentation {
    pub fn new(enabled: bool) -> Self { Self { enabled, ..Self::default() } }
    pub fn layout(&self, original: Screens, wide: bool) -> ScreenLayout {
        if self.enabled {
            if self.access.is_some() {
                return if self.automatic == Some(AutoPanel::MenuScreen) { ScreenLayout::MenuScreen { wide } }
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
        else if self.access.is_some() && self.automatic == Some(AutoPanel::MenuScreen) { PresentationMode::MenuScreen }
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

    /// Follows the game's own pause menu and its out-of-stage menu screens.
    /// `allowed` is false while a runtime menu/modal owns input or the option
    /// is off. Opening needs the menu's own art; closing needs positive
    /// evidence of gameplay, never just missing art (loading, sub-panels).
    pub fn observe(&mut self, scene: BottomScene, allowed: bool) -> PanelRequest {
        if !self.enabled || self.legacy { return PanelRequest::Keep; }
        // menu art beside gameplay HUD is not a menu screen
        let want = if scene.menu_screen && !scene.pause_menu && scene.hud == 0 { Some(AutoPanel::MenuScreen) }
            else if scene.pause_menu { Some(AutoPanel::Pause) } else { None };
        if let Some(kind) = want {
            self.gameplay_frames = 0;
            if self.access.is_none() {
                if allowed && !self.suppressed {
                    self.automatic = Some(kind);
                    return PanelRequest::Open;
                }
                return PanelRequest::Keep;
            }
            // retreating from a pause menu leads into the menus (and a
            // menu screen never turns into a pause panel)
            if self.automatic == Some(AutoPanel::Pause) && kind == AutoPanel::MenuScreen {
                self.automatic = Some(kind);
                return PanelRequest::Relayout;
            }
            return PanelRequest::Keep;
        }
        if !scene.menu && !scene.menu_screen { self.suppressed = false; }
        let Some(kind) = self.automatic() else { return PanelRequest::Keep };
        if scene.fresh {
            let gameplay = !scene.menu && !scene.menu_screen
                && (scene.hud > 0 || (kind == AutoPanel::MenuScreen && scene.portraits > 0));
            if gameplay { self.gameplay_frames += 1; } else { self.gameplay_frames = 0; }
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
        if self.automatic.is_some() && by_player && (scene.pause_menu || scene.menu || scene.menu_screen) { self.suppressed = true; }
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
    fn menu_screens_show_both_pictures_until_gameplay_starts() {
        let menu = BottomScene { fresh: true, menu_screen: true, ..BottomScene::default() };
        let loading = BottomScene { fresh: true, ..BottomScene::default() };
        let dialogue = BottomScene { fresh: true, portraits: 2, ..BottomScene::default() };
        let mut p = PcPresentation::new(true);
        assert_eq!(p.observe(menu, true), PanelRequest::Open);
        p.access = Some((Screens::TopOnly, None));
        assert_eq!(p.mode(), PresentationMode::MenuScreen);
        assert_eq!(p.layout(Screens::TopOnly, true), ScreenLayout::MenuScreen { wide: true });
        assert_eq!(p.context(false, false), InputContext::PointerMenu);
        // loading between the menus and a stage keeps the menu layout
        for _ in 0..200 { assert_eq!(p.observe(loading, true), PanelRequest::Keep); }
        // the stage's opening dialogue (portraits, no HUD yet) is gameplay
        for _ in 0..CLOSE_AFTER - 1 { assert_eq!(p.observe(dialogue, true), PanelRequest::Keep); }
        assert_eq!(p.observe(dialogue, true), PanelRequest::Close);
        // a pause panel that leads into the menus becomes a menu screen
        let mut q = PcPresentation::new(true);
        assert_eq!(q.observe(scene(true, true, 0), true), PanelRequest::Open);
        q.access = Some((Screens::TopOnly, None));
        assert_eq!(q.observe(menu, true), PanelRequest::Relayout);
        assert_eq!(q.mode(), PresentationMode::MenuScreen);
        // portraits alone do not close a pause panel
        let mut r = PcPresentation::new(true);
        r.observe(scene(true, true, 0), true);
        r.access = Some((Screens::TopOnly, None));
        for _ in 0..100 { assert_eq!(r.observe(dialogue, true), PanelRequest::Keep); }
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
