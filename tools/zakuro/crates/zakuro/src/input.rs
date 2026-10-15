//! keyboard to 3DS button mapping.

use winit::keyboard::{KeyCode, PhysicalKey};
use zakuro_core::services::hid::{InputState, PadState};

use crate::settings::Keys;

/// accumulates key state between frames.
#[derive(Default)]
pub struct Keyboard {
    keys: Keys,
    buttons: PadState,
    /// the circle pad keys held, up, down, left, right.
    circle: [bool; 4],

    /// KIU/PC mode keeps movement separate from Zakuro's stock bindings.
    pc_mode: bool,
    pc_circle: [bool; 4],
    /// Alt is a walk modifier. Normal WASD ramps to a full analog throw so
    /// running is the default without triggering KIU's flick/dash detector.
    pc_walk: bool,
    pc_walk_keys: [bool; 2],
    pc_attack_held: bool,
    /// Separate sources from the normal D-pad keys, so releasing either
    /// binding cannot cancel the other. Pending preserves taps between samples.
    pc_action_held: [bool; 3],
    pc_action_pending: [bool; 3],
    /// Mouse-wheel power selection: fractional notches (touchpads send small
    /// deltas), whole steps still to send (+ next, - previous), and whether
    /// the next sample must be a release so the game sees separate presses.
    pc_wheel_accum: f32,
    pc_wheel_steps: i32,
    /// Samples left in the current step: pressed first, then released.
    pc_wheel_phase: u8,
    pc_wheel_right: bool,
    /// Steps are only sent while the game is known to be in land gameplay;
    /// in flight the same D-pad presses would fire the air special.
    pc_wheel_allowed: bool,
    pc_dash_armed: bool,
    pc_walk_strength: f32,
    pc_run_ramp: u8,
    pc_last_direction: [f32; 2],
    /// Shift creates an explicit synthetic stick flick. Phase 2 emits one
    /// neutral HID sample, phase 1 emits the full-stick direction.
    pc_dash_phase: u8,
    pc_dash_direction: [f32; 2],
    /// Physical Shift state. A dash is generated only on the transition from
    /// no Shift key held to a Shift key held, never by keyboard auto-repeat.
    pc_dash_keys: [bool; 2],

    /// virtual stylus used while the mouse is captured. Coordinates are in
    /// the 3DS touch screen's 320x240 space.
    pc_aiming: bool,
    pc_resume_release: bool,
    pc_touch: [f32; 2],
    /// Raw motion accumulated until the next guest input sample.
    pc_mouse_delta: [f32; 2],
    /// New physical motion for diagnostics, separate from unconsumed gestures.
    pc_trace_delta: [f32; 2],
    touch: Option<(u16, u16)>,
    /// how the mouse tilts the console, see InputState::tilt.
    tilt: [f32; 2],
}

impl Keyboard {
    pub fn new(keys: Keys) -> Keyboard {
        Keyboard {
            keys,
            pc_walk_strength: 0.60,
            pc_touch: [160.0, 120.0],
            ..Keyboard::default()
        }
    }

    pub fn set_pc_mode(&mut self, enabled: bool, walk_strength: f32) {
        self.pc_mode = enabled;
        self.pc_walk_strength = walk_strength.clamp(0.51, 0.90);
        self.release();
    }

    pub fn set_keys(&mut self, keys: Keys) {
        self.keys = keys;
        self.release();
    }

    /// lets go of everything, when the game stops seeing the keyboard.
    pub fn release(&mut self) {
        self.buttons = PadState::default();
        self.circle = [false; 4];
        self.pc_circle = [false; 4];
        self.pc_walk = false;
        self.pc_walk_keys = [false; 2];
        self.pc_attack_held = false;
        self.pc_action_held = [false; 3];
        self.pc_action_pending = [false; 3];
        self.clear_wheel();
        self.pc_run_ramp = 0;
        self.pc_last_direction = [0.0; 2];
        self.pc_dash_phase = 0;
        self.pc_dash_direction = [0.0; 2];
        self.pc_dash_keys = [false; 2];
        self.pc_dash_armed = false;
        self.pc_aiming = false;
        self.pc_resume_release = false;
        self.pc_touch = [160.0, 120.0];
        self.pc_mouse_delta = [0.0; 2];
        self.pc_trace_delta = [0.0; 2];
        self.touch = None;
        self.tilt = [0.0; 2];
    }

    fn button_for(&self, key: KeyCode) -> Option<PadState> {
        let keys = &self.keys;
        [
            (keys.a, PadState::A),
            (keys.b, PadState::B),
            (keys.x, PadState::X),
            (keys.y, PadState::Y),
            (keys.l, PadState::L),
            (keys.r, PadState::R),
            (keys.start, PadState::START),
            (keys.select, PadState::SELECT),
            (keys.up, PadState::UP),
            (keys.down, PadState::DOWN),
            (keys.left, PadState::LEFT),
            (keys.right, PadState::RIGHT),
        ]
        .into_iter()
        .find(|&(bound, _)| bound == key)
        .map(|(_, button)| button)
    }

    pub fn key(&mut self, key: PhysicalKey, pressed: bool) {
        let PhysicalKey::Code(code) = key else {
            return;
        };
        if let Some(button) = self.button_for(code) {
            self.buttons.set(button, pressed);
        }
        let circle = [self.keys.circle_up, self.keys.circle_down, self.keys.circle_left, self.keys.circle_right];
        for (held, bound) in self.circle.iter_mut().zip(circle) {
            if bound == code {
                *held = pressed;
            }
        }
    }

    fn pc_direction(&self) -> [f32; 2] {
        let axis = |plus: bool, minus: bool| plus as i8 as f32 - minus as i8 as f32;
        let [up, down, left, right] = self.pc_circle;
        let (mut x, mut y) = (axis(right, left), axis(up, down));
        if x != 0.0 && y != 0.0 {
            const DIAGONAL: f32 = std::f32::consts::FRAC_1_SQRT_2;
            x *= DIAGONAL;
            y *= DIAGONAL;
        }
        [x, y]
    }

    /// Handles the PC-native movement keys. Returns true when the key belongs
    /// to this mapping so the stock Zakuro binding should not see it too.
    pub fn pc_key(&mut self, key: PhysicalKey, pressed: bool) -> bool {
        if !self.pc_mode {
            return false;
        }
        let PhysicalKey::Code(code) = key else { return false };
        if self.pc_aiming {
            let actions = [self.keys.pc_action, self.keys.pc_power_previous, self.keys.pc_power_next];
            if let Some(index) = actions.iter().position(|&bound| bound == code) {
                if pressed && !self.pc_action_held[index] {
                    self.pc_action_pending[index] = true;
                }
                self.pc_action_held[index] = pressed;
                return true;
            }
        }
        let index = match code {
            KeyCode::KeyW => Some(0),
            KeyCode::KeyS => Some(1),
            KeyCode::KeyA => Some(2),
            KeyCode::KeyD => Some(3),
            KeyCode::AltLeft | KeyCode::AltRight => {
                let was_walking = self.pc_walk;
                self.pc_walk_keys[usize::from(code == KeyCode::AltRight)] = pressed;
                self.pc_walk = self.pc_walk_keys.iter().any(|held| *held);
                if was_walking && !self.pc_walk {
                    // Returning from walking to running should accelerate over
                    // a few HID samples rather than creating a dash-like edge.
                    self.pc_run_ramp = 0;
                }
                return true;
            }
            KeyCode::ShiftLeft | KeyCode::ShiftRight => {
                let index = if code == KeyCode::ShiftRight { 1 } else { 0 };
                let was_held = self.pc_dash_keys[0] || self.pc_dash_keys[1];
                self.pc_dash_keys[index] = pressed;
                let now_held = self.pc_dash_keys[0] || self.pc_dash_keys[1];
                if !now_held { self.pc_dash_armed = false; }

                // Shift is an action, not a held state. Windows/winit can
                // deliver repeated Pressed events while a key is held; only
                // the real up -> down edge is allowed to start a new dash.
                if !was_held && now_held {
                    let current = self.pc_direction();
                    if current == [0.0, 0.0] {
                        self.pc_dash_armed = true;
                        return true;
                    }
                    let direction = if current != [0.0, 0.0] { current } else { self.pc_last_direction };
                    if direction != [0.0, 0.0] {
                        self.pc_dash_direction = direction;
                        self.pc_dash_phase = 2;
                    }
                }
                return true;
            }
            _ => None,
        };
        if let Some(index) = index {
            if self.pc_circle[index] != pressed {
                self.pc_circle[index] = pressed;
                // Every direction change restarts the short run ramp. This is
                // what prevents ordinary WASD turns from becoming KIU dashes.
                self.pc_run_ramp = 0;
                let direction = self.pc_direction();
                if direction != [0.0, 0.0] {
                    self.pc_last_direction = direction;
                    if self.pc_dash_armed {
                        self.pc_dash_armed = false;
                        self.pc_dash_direction = direction;
                        self.pc_dash_phase = 2;
                    }
                }
            }
            true
        } else {
            false
        }
    }

    /// Left mouse button becomes the 3DS L button while mouse look is active.
    pub fn pc_attack(&mut self, pressed: bool) {
        if self.pc_mode {
            self.pc_attack_held = pressed;
        }
    }

    pub fn aim_position(&self) -> [f32; 2] { self.pc_touch }

    /// Restore only the aim anchor after a UI visit, never old motion or buttons.
    pub fn restore_aim_position(&mut self, position: [f32; 2]) {
        self.pc_touch = position;
        self.pc_resume_release = true;
        self.pc_mouse_delta = [0.0; 2];
        self.pc_trace_delta = [0.0; 2];
    }

    pub fn pc_aim_active(&mut self, active: bool) {
        self.pc_aiming = self.pc_mode && active;
        self.pc_resume_release = false;
        self.pc_touch = [160.0, 120.0];
        self.pc_mouse_delta = [0.0; 2];
        self.pc_trace_delta = [0.0; 2];
        self.pc_action_held = [false; 3];
        self.pc_action_pending = [false; 3];
        self.clear_wheel();
        if !self.pc_aiming {
            self.pc_attack(false);
        }
    }

    /// Accumulates raw relative desktop mouse motion. It is converted into a
    /// stylus drag once per emulated frame in state(), keeping behavior stable
    /// across mice with different USB report rates.
    pub fn pc_mouse_motion(&mut self, dx: f32, dy: f32) {
        if !self.pc_aiming || !dx.is_finite() || !dy.is_finite() {
            return;
        }
        self.pc_mouse_delta[0] += dx;
        self.pc_mouse_delta[1] += dy;
        self.pc_trace_delta[0] += dx;
        self.pc_trace_delta[1] += dy;
    }

    fn clear_wheel(&mut self) {
        self.pc_wheel_accum = 0.0;
        self.pc_wheel_steps = 0;
        self.pc_wheel_phase = 0;
    }

    /// Mouse wheel while aiming: `notches` > 0 selects the next power, < 0 the
    /// previous one. Selecting never uses a power. Fractions accumulate, so a
    /// touchpad's many small deltas still step one power at a time.
    pub fn pc_wheel(&mut self, notches: f32) {
        if !self.pc_aiming || !self.pc_wheel_allowed || !notches.is_finite() {
            return;
        }
        // A reversal cancels what is still queued instead of adding to it.
        if notches.signum() != self.pc_wheel_accum.signum() && self.pc_wheel_accum != 0.0 {
            self.pc_wheel_accum = 0.0;
        }
        if (notches > 0.0) != (self.pc_wheel_steps > 0) && self.pc_wheel_steps != 0 {
            self.pc_wheel_steps = 0;
        }
        self.pc_wheel_accum += notches;
        let whole = self.pc_wheel_accum.trunc();
        self.pc_wheel_accum -= whole;
        // A fast flick queues at most a few powers, never a long replay.
        self.pc_wheel_steps = (self.pc_wheel_steps + whole as i32).clamp(-4, 4);
    }

    /// Whether wheel selection may reach the game now (land gameplay).
    pub fn set_wheel_allowed(&mut self, allowed: bool) {
        if self.pc_wheel_allowed != allowed {
            self.pc_wheel_allowed = allowed;
            if !allowed { self.clear_wheel(); }
        }
    }

    /// One queued wheel step: the D-pad press is held for WHEEL_HOLD samples,
    /// then released for WHEEL_GAP. On land the game reads the buttons only
    /// on some frames (October 15 play test: one-sample presses, from the
    /// wheel or a very quick key tap, were missed about half the time).
    fn wheel_state(&mut self) -> PadState {
        const WHEEL_HOLD: u8 = 3;
        const WHEEL_GAP: u8 = 4;
        if !self.pc_aiming || !self.pc_wheel_allowed {
            self.pc_wheel_phase = 0;
            return PadState::empty();
        }
        if self.pc_wheel_phase == 0 {
            if self.pc_wheel_steps == 0 { return PadState::empty(); }
            self.pc_wheel_phase = WHEEL_HOLD + WHEEL_GAP;
            self.pc_wheel_right = self.pc_wheel_steps > 0;
            self.pc_wheel_steps -= self.pc_wheel_steps.signum();
        }
        self.pc_wheel_phase -= 1;
        if self.pc_wheel_phase >= WHEEL_GAP {
            if self.pc_wheel_right { PadState::RIGHT } else { PadState::LEFT }
        } else {
            PadState::empty()
        }
    }

    /// records a click on the bottom screen, in screen pixels, or its release.
    pub fn touch(&mut self, position: Option<(u16, u16)>) {
        self.touch = position;
    }

    /// records the tilt the mouse gives the console.
    pub fn tilt(&mut self, tilt: [f32; 2]) {
        self.tilt = tilt;
    }

    fn pc_circle_state(&mut self) -> (f32, f32) {
        // An intentional Shift dash is a true synthetic flick: one neutral
        // sample followed by one full throw. This works even while already
        // running at full stick, where simply changing 1.0 -> 1.0 cannot dash.
        if self.pc_dash_phase == 2 {
            self.pc_dash_phase = 1;
            return (0.0, 0.0);
        }
        if self.pc_dash_phase == 1 {
            self.pc_dash_phase = 0;
            self.pc_run_ramp = 5;
            return (self.pc_dash_direction[0], self.pc_dash_direction[1]);
        }

        let [x, y] = self.pc_direction();
        if x == 0.0 && y == 0.0 {
            self.pc_run_ramp = 0;
            return (0.0, 0.0);
        }
        self.pc_last_direction = [x, y];

        if self.pc_walk {
            return (x * self.pc_walk_strength, y * self.pc_walk_strength);
        }

        // Normal movement should be running. The first ~80 ms ramps from the
        // known-safe partial throw to 1.0 so the game does not interpret the
        // keyboard's digital edge as a stylus-era analog flick/dash.
        const RAMP_FRAMES: u8 = 5;
        let t = (self.pc_run_ramp.min(RAMP_FRAMES) as f32) / RAMP_FRAMES as f32;
        let strength = self.pc_walk_strength + (1.0 - self.pc_walk_strength) * t;
        self.pc_run_ramp = self.pc_run_ramp.saturating_add(1).min(RAMP_FRAMES);
        (x * strength, y * strength)
    }

    fn pc_touch_state(&mut self, sensitivity: f32) -> Option<(u16, u16)> {
        if !self.pc_aiming { return self.touch; }
        // The game must see a touch-up between a menu click and resumed aim.
        if std::mem::take(&mut self.pc_resume_release) { return None; }
        let delta = std::mem::take(&mut self.pc_mouse_delta);
        let gain = sensitivity.clamp(0.05, 4.0);
        // Bounded aiming: no automatic lift, wrap, recenter, or overshoot debt.
        self.pc_touch[0] = (self.pc_touch[0] + delta[0] * gain).clamp(0.0, 319.0);
        self.pc_touch[1] = (self.pc_touch[1] + delta[1] * gain).clamp(0.0, 239.0);
        Some((self.pc_touch[0].round() as u16, self.pc_touch[1].round() as u16))
    }

    pub fn state(&mut self, mouse_sensitivity: f32) -> InputState {
        let (circle_x, circle_y) = if self.pc_mode {
            self.pc_circle_state()
        } else {
            let axis = |plus: bool, minus: bool| plus as i8 as f32 - minus as i8 as f32;
            let [up, down, left, right] = self.circle;
            (axis(right, left), axis(up, down))
        };

        let touch = self.pc_touch_state(mouse_sensitivity);
        let mut actions = PadState::empty();
        for (index, button) in [PadState::DOWN, PadState::LEFT, PadState::RIGHT].into_iter().enumerate() {
            let pending = std::mem::take(&mut self.pc_action_pending[index]);
            if self.pc_aiming && (self.pc_action_held[index] || pending) {
                actions |= button;
            }
        }
        // The wheel waits while a power key is held so the two never merge
        // into one long press.
        if !actions.intersects(PadState::LEFT | PadState::RIGHT) {
            actions |= self.wheel_state();
        }

        InputState {
            buttons: self.buttons | actions | if self.pc_attack_held { PadState::L } else { PadState::empty() },
            circle_x,
            circle_y,
            touch,
            tilt: self.tilt,
        }
    }

    pub fn raw_mouse_delta(&mut self) -> [f32; 2] { std::mem::take(&mut self.pc_trace_delta) }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(keyboard: &mut Keyboard) -> InputState {
        keyboard.state(0.55)
    }

    #[test]
    fn captured_actions_preserve_aim_and_movement() {
        for (code, button) in [(KeyCode::KeyE, PadState::DOWN), (KeyCode::Digit1, PadState::LEFT), (KeyCode::Digit3, PadState::RIGHT)] {
            let mut keyboard = Keyboard::new(Keys::default());
            keyboard.set_pc_mode(true, 0.60);
            assert!(!keyboard.pc_key(PhysicalKey::Code(code), true));
            keyboard.pc_aim_active(true);
            keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyD), true);
            keyboard.pc_mouse_motion(40.0, -20.0);
            assert!(keyboard.pc_key(PhysicalKey::Code(code), true));
            let sample = keyboard.state(1.0);
            assert_eq!(sample.buttons, button);
            assert_eq!(sample.touch, Some((200, 100)));
            assert!(sample.circle_x > 0.0);
            keyboard.pc_key(PhysicalKey::Code(code), false);
            let sample = keyboard.state(1.0);
            assert!(sample.buttons.is_empty());
            assert_eq!(sample.touch, Some((200, 100)));
        }
    }

    fn land_wheel() -> Keyboard {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_aim_active(true);
        keyboard.set_wheel_allowed(true);
        keyboard
    }

    #[test]
    fn wheel_notches_become_separate_single_presses() {
        let mut keyboard = land_wheel();
        keyboard.pc_mouse_motion(10.0, 0.0);
        keyboard.pc_wheel(2.0);
        let samples: Vec<bool> = (0..16).map(|_| state(&mut keyboard).buttons == PadState::RIGHT).collect();
        let r = true; let o = false;
        assert_eq!(samples, [r, r, r, o, o, o, o, r, r, r, o, o, o, o, o, o]);
        keyboard.pc_wheel(-1.0);
        let samples: Vec<PadState> = (0..7).map(|_| state(&mut keyboard).buttons).collect();
        assert_eq!(&samples[..3], &[PadState::LEFT; 3]);
        assert!(samples[3..].iter().all(|b| b.is_empty()));
    }

    #[test]
    fn touchpad_fractions_accumulate_and_reversal_cancels() {
        let mut keyboard = land_wheel();
        for _ in 0..3 { keyboard.pc_wheel(0.3); }
        assert!(state(&mut keyboard).buttons.is_empty(), "0.9 of a notch is not a step yet");
        keyboard.pc_wheel(0.3);
        assert_eq!(state(&mut keyboard).buttons, PadState::RIGHT);
        for _ in 0..6 { state(&mut keyboard); }
        keyboard.pc_wheel(3.0);
        keyboard.pc_wheel(-1.0);
        assert_eq!(state(&mut keyboard).buttons, PadState::LEFT, "reversal drops the queued next steps");
        for _ in 0..6 { state(&mut keyboard); }
        assert!((0..10).all(|_| state(&mut keyboard).buttons.is_empty()));
    }

    #[test]
    fn wheel_does_nothing_in_flight_menus_or_uncaptured() {
        let mut keyboard = land_wheel();
        keyboard.set_wheel_allowed(false);
        keyboard.pc_wheel(1.0);
        assert!(state(&mut keyboard).buttons.is_empty(), "flight: would fire the special");
        keyboard.set_wheel_allowed(true);
        keyboard.pc_wheel(4.0);
        keyboard.set_wheel_allowed(false);
        keyboard.set_wheel_allowed(true);
        assert!(state(&mut keyboard).buttons.is_empty(), "queue dropped when leaving land");
        keyboard.pc_aim_active(false);
        keyboard.pc_wheel(1.0);
        assert!(state(&mut keyboard).buttons.is_empty());
        let mut flood = land_wheel();
        flood.pc_wheel(40.0);
        let pressed = (0..60).filter(|_| !state(&mut flood).buttons.is_empty()).count();
        assert_eq!(pressed, 4 * 3, "a flick is capped at four steps");
    }

    #[test]
    fn quick_action_tap_is_sampled_once_and_arrow_sources_are_independent() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_aim_active(true);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyE), true);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyE), false);
        assert_eq!(state(&mut keyboard).buttons, PadState::DOWN);
        assert!(state(&mut keyboard).buttons.is_empty());
        keyboard.key(PhysicalKey::Code(KeyCode::ArrowDown), true);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyE), true);
        state(&mut keyboard);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyE), false);
        assert_eq!(state(&mut keyboard).buttons, PadState::DOWN);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyE), true);
        keyboard.key(PhysicalKey::Code(KeyCode::ArrowDown), false);
        assert_eq!(state(&mut keyboard).buttons, PadState::DOWN);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyE), false);
        assert!(state(&mut keyboard).buttons.is_empty());
    }

    #[test]
    fn capture_and_focus_loss_clear_actions_and_rebinding_works() {
        let mut keyboard = Keyboard::new(Keys { pc_action: KeyCode::KeyR, ..Keys::default() });
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_aim_active(true);
        assert!(!keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyE), true));
        assert!(keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyR), true));
        keyboard.pc_aim_active(false);
        keyboard.pc_aim_active(true);
        assert!(state(&mut keyboard).buttons.is_empty());
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyR), true);
        keyboard.release();
        assert!(state(&mut keyboard).buttons.is_empty());
        keyboard.set_pc_mode(false, 0.60);
        assert!(!keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyR), true));
    }

    #[test]
    fn screen_visit_restores_aim_without_clicks_or_stale_motion() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_aim_active(true);
        keyboard.pc_mouse_motion(110.0, -30.0);
        assert_eq!(keyboard.state(1.0).touch, Some((270, 90)));
        let anchor = keyboard.aim_position();
        keyboard.pc_attack(true);
        keyboard.release();
        keyboard.touch(Some((12, 34)));
        assert_eq!(keyboard.state(1.0).touch, Some((12, 34)));
        assert!(state(&mut keyboard).buttons.is_empty());
        keyboard.release();
        keyboard.pc_aim_active(true);
        keyboard.restore_aim_position(anchor);
        assert_eq!(keyboard.state(1.0).touch, None);
        let sample = keyboard.state(1.0);
        assert_eq!(sample.touch, Some((270, 90)));
        assert!(sample.buttons.is_empty());
        assert_eq!(keyboard.raw_mouse_delta(), [0.0, 0.0]);
    }

    #[test]
    fn keys_press_the_buttons_they_are_bound_to() {
        let mut keyboard = Keyboard::new(Keys { a: KeyCode::KeyP, ..Keys::default() });
        keyboard.key(PhysicalKey::Code(KeyCode::KeyP), true);
        assert!(state(&mut keyboard).buttons.contains(PadState::A));
        keyboard.key(PhysicalKey::Code(KeyCode::KeyX), true);
        assert!(!state(&mut keyboard).buttons.contains(PadState::B), "X is no longer bound to anything");
    }

    #[test]
    fn opposite_circle_keys_cancel_out() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.key(PhysicalKey::Code(KeyCode::KeyJ), true);
        assert_eq!(state(&mut keyboard).circle_x, -1.0);
        keyboard.key(PhysicalKey::Code(KeyCode::KeyL), true);
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
        keyboard.release();
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
    }

    #[test]
    fn pc_wasd_ramps_to_running_and_alt_walks() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        assert!(keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyD), true));
        assert!((state(&mut keyboard).circle_x - 0.60).abs() < 0.001);
        for _ in 0..5 {
            state(&mut keyboard);
        }
        assert!((state(&mut keyboard).circle_x - 1.0).abs() < 0.001);
        assert!(keyboard.pc_key(PhysicalKey::Code(KeyCode::AltLeft), true));
        assert!((state(&mut keyboard).circle_x - 0.60).abs() < 0.001);
    }

    #[test]
    fn shift_generates_neutral_then_full_dash_flick() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyD), true);
        for _ in 0..7 {
            state(&mut keyboard);
        }
        assert!(keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), true));
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
        assert!((state(&mut keyboard).circle_x - 1.0).abs() < 0.001);
    }


    #[test]
    fn holding_shift_does_not_repeat_dash() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyD), true);
        for _ in 0..7 {
            state(&mut keyboard);
        }

        keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), true);
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
        assert!((state(&mut keyboard).circle_x - 1.0).abs() < 0.001);

        // Simulate a winit/Windows auto-repeat Pressed event while Shift is
        // still physically held. It must not generate another neutral/full
        // flick pair.
        keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), true);
        assert!(state(&mut keyboard).circle_x > 0.5);

        keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), false);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), true);
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
    }

    #[test]
    fn pc_mouse_attack_is_the_l_button() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_attack(true);
        assert!(state(&mut keyboard).buttons.contains(PadState::L));
        keyboard.pc_attack(false);
        assert!(!state(&mut keyboard).buttons.contains(PadState::L));
    }

    #[test]
    fn mouse_release_does_not_release_keyboard_attack() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.key(PhysicalKey::Code(KeyCode::KeyQ), true);
        keyboard.pc_attack(true);
        keyboard.pc_attack(false);
        assert!(state(&mut keyboard).buttons.contains(PadState::L));
        keyboard.release();
        assert!(state(&mut keyboard).buttons.is_empty());
    }

    #[test]
    fn releasing_one_alt_keeps_other_alt_walking() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyD), true);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::AltLeft), true);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::AltRight), true);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::AltLeft), false);
        for _ in 0..10 { assert_eq!(state(&mut keyboard).circle_x, 0.60); }
    }

    #[test]
    fn raw_event_partition_does_not_change_linear_touch() {
        let mut samples = Vec::new();
        for packets in [1, 8, 100] {
            let mut keyboard = Keyboard::new(Keys::default());
            keyboard.set_pc_mode(true, 0.60);
            keyboard.pc_aim_active(true);
            for _ in 0..packets { keyboard.pc_mouse_motion(40.0 / packets as f32, -20.0 / packets as f32); }
            samples.push(keyboard.state(1.0).touch);
        }
        assert!(samples.iter().all(|sample| *sample == Some((200, 100))));
    }

    #[test]
    fn trace_counts_physical_motion_once_even_when_gesture_defers_it() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_aim_active(true);
        keyboard.pc_mouse_motion(50.0, 10.0);
        assert_eq!(keyboard.raw_mouse_delta(), [50.0, 10.0]);
        keyboard.state(1.0);
        assert_eq!(keyboard.raw_mouse_delta(), [0.0, 0.0]);
        keyboard.pc_mouse_motion(f32::NAN, 1.0);
        assert_eq!(keyboard.raw_mouse_delta(), [0.0, 0.0]);
    }

    #[test]
    fn edges_never_lift_or_recenter_and_reverse_without_overshoot_debt() {
        for (dx, dy, edge, reverse) in [
            (10000.0, 0.0, (319,120), (318,120)),
            (-10000.0, 0.0, (0,120), (1,120)),
            (0.0, 10000.0, (160,239), (160,238)),
            (0.0, -10000.0, (160,0), (160,1)),
        ] {
            let mut keyboard = Keyboard::new(Keys::default());
            keyboard.set_pc_mode(true, 0.60);
            keyboard.pc_aim_active(true);
            assert_eq!(keyboard.state(1.0).touch, Some((160,120)));
            keyboard.pc_mouse_motion(dx, dy);
            assert_eq!(keyboard.state(1.0).touch, Some(edge));
            for _ in 0..120 { assert_eq!(keyboard.state(1.0).touch, Some(edge)); }
            keyboard.pc_mouse_motion(if dx == 0.0 { 0.0 } else { -dx.signum() },
                                     if dy == 0.0 { 0.0 } else { -dy.signum() });
            assert_eq!(keyboard.state(1.0).touch, Some(reverse));
            keyboard.pc_aim_active(false);
            assert_eq!(keyboard.state(1.0).touch, None);
        }
    }

    #[test]
    fn dash_is_one_directional_impulse_even_if_shift_pressed_first() {
        let mut keyboard = Keyboard::new(Keys::default());
        keyboard.set_pc_mode(true, 0.60);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), true);
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyD), true);
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
        assert_eq!(state(&mut keyboard).circle_x, 1.0);
        for _ in 0..30 {
            keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), true);
            assert_eq!(state(&mut keyboard).circle_x, 1.0);
        }
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyD), false);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::KeyA), true);
        assert!(state(&mut keyboard).circle_x < 0.0);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), false);
        keyboard.pc_key(PhysicalKey::Code(KeyCode::ShiftLeft), true);
        assert_eq!(state(&mut keyboard).circle_x, 0.0);
        assert_eq!(state(&mut keyboard).circle_x, -1.0);
    }
}
