//! Menus answered from the top screen (October 24 experiment).
//!
//! While the game shows one of its out-of-stage menus, PC buttons are drawn
//! over the upper picture, and a click does what touching the 3DS lower
//! screen did there: a touch at that point, held a few frames. The lower
//! screen stays hidden (Tab still shows it). The game keeps its own
//! selection, sounds, animation and rules, and its keyboard and controller
//! controls keep working.
//!
//! A screen is known by the menu archive whose own art its lower screen
//! draws (kiu_ui: `BottomScene::shows_menu`). Touch points are the centres of
//! the game's own buttons on its lower screen, measured from captures.

use zakuro_gpu::kiu_ui::BottomScene;

/// One PC button: what it says, its colour (the game's own button's), and
/// where on the 3DS lower screen it touches.
pub struct TopButton {
    pub label: &'static str,
    pub colour: [u8; 3],
    pub touch: (u16, u16),
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Arrangement {
    /// side by side, low in the middle of the picture
    Row,
    /// stacked on the left of the picture
    Column,
}

pub struct TopMenu {
    /// the menu archive (`us/menu/NNN`) whose art identifies the screen
    pub id: u16,
    pub name: &'static str,
    pub arrangement: Arrangement,
    pub buttons: &'static [TopButton],
    /// the game's Back button on its lower screen
    pub back: (u16, u16),
}

/// The screens answered from the top so far.
pub const MENUS: [TopMenu; 2] = [
    // the save select: the three save books (the game's green, red and
    // blue), the bubble on the upper picture shows the chosen one
    TopMenu { id: 20, name: "save select", arrangement: Arrangement::Row, back: (24, 218), buttons: &[
        TopButton { label: "Book I", colour: [46, 125, 72], touch: (60, 96) },
        TopButton { label: "Book II", colour: [168, 38, 50], touch: (160, 98) },
        TopButton { label: "Book III", colour: [48, 70, 150], touch: (264, 98) },
    ] },
    // the main menu: Solo, Together, Vault, Options (StreetPass and AR are
    // 3DS-only and left out)
    TopMenu { id: 40, name: "main menu", arrangement: Arrangement::Column, back: (26, 220), buttons: &[
        TopButton { label: "Solo", colour: [205, 64, 58], touch: (104, 52) },
        TopButton { label: "Together", colour: [214, 140, 28], touch: (224, 128) },
        TopButton { label: "Vault", colour: [52, 140, 70], touch: (64, 140) },
        TopButton { label: "Options", colour: [110, 72, 168], touch: (142, 211) },
    ] },
];

/// The top-screen menu for what the lower screen shows, if there is one.
pub fn find(scene: &BottomScene) -> Option<&'static TopMenu> {
    MENUS.iter().find(|m| scene.shows_menu(m.id))
}

/// Frames a menu stays after its art was last seen: frames the game skips
/// or fades through do not make the buttons flicker.
const LINGER: u64 = 15;

/// The top-screen menu shown now.
#[derive(Default)]
pub struct Shown {
    menu: Option<&'static TopMenu>,
    seen: u64,
}

impl Shown {
    /// After each emulated frame (only fresh lower screens say anything).
    pub fn update(&mut self, scene: &BottomScene, frame: u64) {
        if !scene.fresh { return; }
        if let Some(menu) = find(scene) {
            if self.menu.map(|m| m.id) != Some(menu.id) { log::info!("Top-screen menu: {}", menu.name); }
            self.menu = Some(menu);
            self.seen = frame;
        } else if self.menu.is_some() && frame.saturating_sub(self.seen) > LINGER {
            self.menu = None;
        }
    }
    pub fn menu(&self) -> Option<&'static TopMenu> { self.menu }
}

/// Frames a tap holds its touch: the game reads the touch screen once a
/// frame, and its buttons answer a touch held and let go.
const TAP_FRAMES: u32 = 5;

/// A touch the PC buttons asked for.
#[derive(Default)]
pub struct Tap {
    at: Option<(u16, u16)>,
    frames: u32,
}

impl Tap {
    pub fn start(&mut self, at: (u16, u16)) {
        self.at = Some(at);
        self.frames = TAP_FRAMES + 1;
    }

    /// The touch to give the game this frame: Some(touch) while the tap
    /// lasts (its last frame lets go), None when there is no tap.
    pub fn next(&mut self) -> Option<Option<(u16, u16)>> {
        if self.frames == 0 { return None; }
        self.frames -= 1;
        Some(if self.frames == 0 { self.at.take(); None } else { self.at })
    }
}

/// Draws the menu's buttons over the upper picture (`view`, in egui points)
/// and returns the touch a click asked for.
pub fn show(ctx: &egui::Context, menu: &TopMenu, view: egui::Rect) -> Option<(u16, u16)> {
    let mut clicked = None;
    let (w, h) = (view.width(), view.height());
    // where each button goes, as rectangles in the picture
    let mut rects: Vec<(egui::Rect, &TopButton)> = Vec::new();
    match menu.arrangement {
        Arrangement::Row => {
            let (bw, bh, gap) = (w * 0.17, h * 0.12, w * 0.025);
            let total = bw * menu.buttons.len() as f32 + gap * (menu.buttons.len() as f32 - 1.0);
            let mut x = view.center().x - total * 0.5;
            let y = view.bottom() - h * 0.19;
            for b in menu.buttons {
                rects.push((egui::Rect::from_min_size(egui::pos2(x, y), egui::vec2(bw, bh)), b));
                x += bw + gap;
            }
        }
        Arrangement::Column => {
            let (bw, bh, gap) = (w * 0.24, h * 0.115, h * 0.03);
            let mut y = view.top() + h * 0.2;
            for b in menu.buttons {
                rects.push((egui::Rect::from_min_size(egui::pos2(view.left() + w * 0.045, y), egui::vec2(bw, bh)), b));
                y += bh + gap;
            }
        }
    }
    egui::Area::new(egui::Id::new(("top-menu", menu.id))).order(egui::Order::Foreground).fixed_pos(view.min).show(ctx, |ui| {
        let painter = ui.painter().clone();
        for (i, (rect, b)) in rects.iter().enumerate() {
            let response = ui.interact(*rect, egui::Id::new(("top-button", menu.id, i)), egui::Sense::click());
            if button(&painter, *rect, b.label, b.colour, response.hovered(), response.is_pointer_button_down_on()) {
                // drawn
            }
            if response.clicked() { clicked = Some(b.touch); }
        }
        // the game's Back, small, bottom left of the picture
        let back = egui::Rect::from_min_size(egui::pos2(view.left() + w * 0.02, view.bottom() - h * 0.1), egui::vec2(w * 0.09, h * 0.075));
        let response = ui.interact(back, egui::Id::new(("top-back", menu.id)), egui::Sense::click());
        button(&painter, back, "Back", [43, 43, 58], response.hovered(), response.is_pointer_button_down_on());
        if response.clicked() { clicked = Some(menu.back); }
    });
    clicked
}

/// One button in the game's manner: a bold rounded plate with a dark rim,
/// lit and rimmed in gold under the pointer.
fn button(painter: &egui::Painter, rect: egui::Rect, label: &str, colour: [u8; 3], hovered: bool, pressed: bool) -> bool {
    let lift = |c: u8| if hovered { c.saturating_add(28) } else { c };
    let fill = egui::Color32::from_rgb(lift(colour[0]), lift(colour[1]), lift(colour[2]));
    let rim = if hovered { egui::Color32::from_rgb(242, 193, 78) } else { egui::Color32::from_rgb(20, 18, 30) };
    let rect = if pressed { rect.shrink(rect.height() * 0.04) } else { rect };
    let radius = rect.height() * 0.32;
    // a soft shadow under the plate
    painter.rect_filled(rect.translate(egui::vec2(0.0, rect.height() * 0.06)), radius, egui::Color32::from_black_alpha(110));
    painter.rect(rect, radius, fill, egui::Stroke::new((rect.height() * 0.06).max(2.0), rim), egui::StrokeKind::Inside);
    let size = rect.height() * 0.42;
    let font = egui::FontId::proportional(size);
    painter.text(rect.center() + egui::vec2(size * 0.06, size * 0.08), egui::Align2::CENTER_CENTER, label, font.clone(), egui::Color32::from_black_alpha(160));
    painter.text(rect.center(), egui::Align2::CENTER_CENTER, label, font, egui::Color32::WHITE);
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    fn scene(ids: &[u16]) -> BottomScene {
        let mut s = BottomScene { fresh: true, ..BottomScene::default() };
        for &id in ids { s.menus[id as usize / 64] |= 1 << (id % 64); }
        s
    }
    #[test]
    fn menus_are_known_by_their_art_and_linger_briefly() {
        assert_eq!(find(&scene(&[20])).map(|m| m.name), Some("save select"));
        assert_eq!(find(&scene(&[40])).map(|m| m.name), Some("main menu"));
        assert!(find(&scene(&[30])).is_none());
        let mut shown = Shown::default();
        shown.update(&scene(&[20]), 100);
        assert_eq!(shown.menu().map(|m| m.id), Some(20));
        // a skipped lower screen says nothing; a few frames without the art keep it
        shown.update(&BottomScene::default(), 101);
        shown.update(&scene(&[]), 110);
        assert!(shown.menu().is_some());
        shown.update(&scene(&[]), 100 + LINGER + 1);
        assert!(shown.menu().is_none());
    }
    #[test]
    fn a_tap_holds_its_touch_then_lets_go() {
        let mut tap = Tap::default();
        assert_eq!(tap.next(), None);
        tap.start((60, 96));
        for _ in 0..TAP_FRAMES { assert_eq!(tap.next(), Some(Some((60, 96)))); }
        assert_eq!(tap.next(), Some(None));
        assert_eq!(tap.next(), None);
    }
    #[test]
    fn touch_points_lie_on_the_lower_screen() {
        for menu in &MENUS {
            for (x, y) in menu.buttons.iter().map(|b| b.touch).chain([menu.back]) {
                assert!(x < 320 && y < 240, "{} {x},{y}", menu.name);
            }
        }
    }
}
