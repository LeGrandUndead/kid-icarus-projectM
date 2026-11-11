//! The game's menus redrawn on the PC screen with the game's own art.
//!
//! The lower screen is not shown at all. Each of the game's buttons is drawn
//! by us, from the button sheet the game itself uses (in the PC menu art
//! pack, `KIU_MENU_PACK`, rebuilt from the player's ROM at 4x), cut along
//! its own outline, at a place laid out for a 16:9 window
//! (doc/UI_DESIGN_RULES.md). A vine in the art's own style binds them
//! (menu_vine); they sway, can be dragged and pushed into each other, and
//! spring back to their place on it (menu_motion).
//!
//! Pointing at a button selects it in the game (menu_motion::Nav walks the
//! game's cursor there with the D-pad), so the game's heading, art, caption
//! and sounds follow the pointer; clicking it touches the game's real
//! button on its hidden lower screen (top_menus::Tap). The game still
//! decides what happens; keyboard and controller keep working, and light
//! the same buttons.
//!
//! Only coordinates and texture fingerprints live here; the art is read at
//! run time from the pack on the player's machine.

use std::path::{Path, PathBuf};

use crate::menu_motion::{Graph, Motion, Nav};

/// One button: where it is in the sheet and where it goes in the window.
pub struct Button {
    pub name: &'static str,
    /// the button in the game's sheet, in its own pixels (the sheet is
    /// `sheet_size` wide); the shapes whose middle lies inside are its own.
    pub sheet: [u32; 4],
    /// the sheet draws it on its side (turned a quarter left).
    pub turned: bool,
    /// top-left corner in window units (the window is 240 units tall).
    pub at: [f32; 2],
    /// units per sheet pixel.
    pub scale: f32,
    /// a slight tilt, degrees clockwise, so they hang like leaves.
    pub tilt: f32,
    /// where touching the 3DS lower screen presses it.
    pub touch: (u16, u16),
    /// its choice in the game's navigation map (`Screen::graph`).
    pub node: usize,
}

/// A screen redrawn this way.
pub struct Screen {
    /// the menu archive whose art identifies the screen.
    pub id: u16,
    /// the sheet's name in the pack: `<w>x<h>-<fingerprint>.png`.
    pub sheet: &'static str,
    pub sheet_size: u32,
    pub buttons: &'static [Button],
    /// the game's navigation map between its choices (its menu parameters:
    /// each choice's up, down, left and right neighbour).
    pub graph: Graph,
    /// for each choice of the map, the upper-screen art the game shows
    /// while it is selected (texture fingerprint, 0 unknown).
    pub selected_art: &'static [u64],
}

impl Screen {
    /// Whether choice `node` of the game's map is one of the shown buttons.
    pub fn shows(&self, node: usize) -> bool { self.buttons.iter().any(|b| b.node == node) }

    /// Whether the watched upper-screen art shows any choice's art.
    pub fn any_selected(&self, watched: u32) -> bool {
        (0..self.selected_art.len()).any(|i| self.selected_art[i] != 0 && watched & (1 << i) != 0)
    }

    /// The choice the game shows selected, from the watched upper-screen
    /// art drawn this frame (kiu_ui::watch_top, in `selected_art` order):
    /// one, or none while two cross-fade.
    pub fn selected(&self, watched: u32) -> Option<usize> {
        let known = (0..self.selected_art.len()).filter(|&i| self.selected_art[i] != 0 && watched & (1 << i) != 0);
        let mut it = known;
        let first = it.next()?;
        it.next().is_none().then_some(first)
    }
}

/// The game's Back arrow, the same on every menu screen.
pub const BACK_SHEET: &str = "64x32-230262A22CA913D6.png";
pub const BACK_AT: [f32; 2] = [12.0, 210.0];
pub const BACK_SCALE: f32 = 0.5;

/// The main menu's choices in the game's map (MENUID_TOP's SelMenuParams):
/// 0 SinglePlay, 1 MultiPlay, 2 Collection, 3 Option, 4 Present
/// (StreetPass), 5 Return, 6 HowToPlay, 7 Pong. Up, down, left, right.
const MAIN_MENU_MAP: [[usize; 4]; 8] = [
    [5, 2, 4, 4], [4, 3, 2, 2], [0, 5, 1, 1], [1, 4, 5, 7],
    [3, 1, 0, 0], [2, 0, 6, 3], [1, 4, 7, 5], [1, 4, 3, 6],
];

/// The main menu: Solo, Together, Vault and Options hang from a vine on
/// the left of the section's art, clear of its heading and of the
/// caption's black ground. One scale for all four (the art's own
/// proportions keep Solo first), 10 units between them, inside the safe
/// margins. StreetPass and AR Cards (3DS only) are left out.
pub const MAIN_MENU: Screen = Screen { id: 40, sheet: "256x256-701C2B1F2A647930.png", sheet_size: 256,
    buttons: &[
        Button { name: "Solo", sheet: [1, 1, 193, 86], turned: false, at: [22.0, 22.0], scale: 0.34, tilt: -2.0, touch: (104, 52), node: 0 },
        Button { name: "Together", sheet: [1, 91, 184, 180], turned: false, at: [28.0, 60.9], scale: 0.34, tilt: 2.0, touch: (224, 128), node: 1 },
        Button { name: "Vault", sheet: [0, 182, 118, 255], turned: false, at: [22.0, 101.16], scale: 0.34, tilt: -1.5, touch: (64, 140), node: 2 },
        Button { name: "Options", sheet: [203, 1, 255, 174], turned: true, at: [28.0, 135.98], scale: 0.34, tilt: 1.5, touch: (142, 211), node: 3 },
    ],
    graph: Graph { edges: &MAIN_MENU_MAP },
    // menu040/MenCmnBgUp0007Sg, 0002Ml, 0007Cl, 0007Op: the section art
    selected_art: &[0xE6C4C19E3FFA6CBC, 0xB1AD9D130D2C0DCE, 0xA19D56343FECD3C8, 0xAD4E16B8C71A4066],
};

pub const SCREENS: [&Screen; 1] = [&MAIN_MENU];

/// The back arrow's touch on the lower screen, per screen.
pub fn back_touch(id: u16) -> (u16, u16) {
    match id { 40 => (26, 220), _ => (24, 218) }
}

/// An RGBA picture.
#[derive(Clone)]
pub struct Picture {
    pub width: usize,
    pub height: usize,
    pub rgba: Vec<u8>,
}

impl Picture {
    fn alpha(&self, x: usize, y: usize) -> u8 { self.rgba[(y * self.width + x) * 4 + 3] }

    /// The part `[x0, y0, x1, y1)`, keeping only the pixels of shapes for
    /// which `mine` holds.
    fn cut(&self, r: [usize; 4], shape: &[u32], mine: &[bool]) -> Picture {
        let (w, h) = (r[2] - r[0], r[3] - r[1]);
        let mut rgba = vec![0u8; w * h * 4];
        for y in 0..h {
            for x in 0..w {
                let (sx, sy) = (x + r[0], y + r[1]);
                let s = shape[sy * self.width + sx];
                if s != 0 && mine[s as usize] {
                    let from = (sy * self.width + sx) * 4;
                    rgba[(y * w + x) * 4..][..4].copy_from_slice(&self.rgba[from..from + 4]);
                }
            }
        }
        Picture { width: w, height: h, rgba }
    }

    /// Turned a quarter right (undoes a sheet's quarter left).
    fn turned_right(&self) -> Picture {
        let (w, h) = (self.height, self.width);
        let mut rgba = vec![0u8; w * h * 4];
        for y in 0..h {
            for x in 0..w {
                // new (x, y) comes from old (y, oldheight - 1 - x)
                let from = ((self.height - 1 - x) * self.width + y) * 4;
                rgba[(y * w + x) * 4..][..4].copy_from_slice(&self.rgba[from..from + 4]);
            }
        }
        Picture { width: w, height: h, rgba }
    }

    /// A soft gold halo around the shape, `pad` pixels added on each side.
    pub fn glow(&self, pad: usize) -> Picture {
        let (w, h) = (self.width + 2 * pad, self.height + 2 * pad);
        let mut a = vec![0f32; w * h];
        for y in 0..self.height {
            for x in 0..self.width {
                a[(y + pad) * w + x + pad] = self.alpha(x, y) as f32 / 255.0;
            }
        }
        // grown, then blurred: three box blurs make a smooth falloff
        let grow = (pad / 2).max(1);
        a = spread(&a, w, h, grow, f32::max);
        for _ in 0..3 { a = spread(&a, w, h, (pad / 3).max(1), |s, v| s + v); }
        let peak = a.iter().cloned().fold(0.0, f32::max).max(1e-6);
        let mut rgba = vec![0u8; w * h * 4];
        for (i, v) in a.iter().enumerate() {
            let k = (v / peak).min(1.0);
            // premultiplied gold
            let c = [255.0, 208.0, 84.0].map(|c: f32| (c * k) as u8);
            rgba[i * 4..][..4].copy_from_slice(&[c[0], c[1], c[2], (255.0 * k) as u8]);
        }
        Picture { width: w, height: h, rgba }
    }
}

/// A box pass (both directions) combining a pixel's neighbours with `f`;
/// sums are averaged.
fn spread(a: &[f32], w: usize, h: usize, r: usize, f: fn(f32, f32) -> f32) -> Vec<f32> {
    let average = f(1.0, 1.0) == 2.0;
    let pass = |src: &[f32], horizontal: bool| -> Vec<f32> {
        let mut out = vec![0f32; w * h];
        for y in 0..h {
            for x in 0..w {
                let mut acc = 0.0;
                let mut n = 0.0;
                for d in -(r as isize)..=(r as isize) {
                    let (sx, sy) = if horizontal { (x as isize + d, y as isize) } else { (x as isize, y as isize + d) };
                    if sx < 0 || sy < 0 || sx >= w as isize || sy >= h as isize { continue; }
                    acc = f(acc, src[sy as usize * w + sx as usize]);
                    n += 1.0;
                }
                out[y * w + x] = if average { acc / n } else { acc };
            }
        }
        out
    };
    let once = pass(a, true);
    pass(&once, false)
}

/// The shapes of a picture (4-connected pixels with some alpha): each
/// pixel's shape number (0 none), and each shape's bounds (index = number).
pub fn shapes(p: &Picture) -> (Vec<u32>, Vec<[usize; 4]>) {
    let mut shape = vec![0u32; p.width * p.height];
    let mut bounds = vec![[0usize; 4]];
    let mut stack = Vec::new();
    for start in 0..shape.len() {
        if shape[start] != 0 || p.rgba[start * 4 + 3] <= 10 { continue; }
        let n = bounds.len() as u32;
        let mut b = [usize::MAX, usize::MAX, 0, 0];
        shape[start] = n;
        stack.push(start);
        while let Some(i) = stack.pop() {
            let (x, y) = (i % p.width, i / p.width);
            b = [b[0].min(x), b[1].min(y), b[2].max(x + 1), b[3].max(y + 1)];
            let mut visit = |j: usize| if shape[j] == 0 && p.rgba[j * 4 + 3] > 10 { shape[j] = n; stack.push(j); };
            if x > 0 { visit(i - 1); }
            if x + 1 < p.width { visit(i + 1); }
            if y > 0 { visit(i - p.width); }
            if y + 1 < p.height { visit(i + p.width); }
        }
        bounds.push(b);
    }
    (shape, bounds)
}

/// The buttons of a sheet, each cut along its own shapes (a neighbour's
/// shape poking into its rectangle is left out), turned upright.
pub fn cut_buttons(sheet: &Picture, screen: &Screen) -> Vec<Picture> {
    let k = sheet.width as f32 / screen.sheet_size as f32;
    let (shape, bounds) = shapes(sheet);
    screen.buttons.iter().map(|b| {
        let r = b.sheet.map(|v| (v as f32 * k).round() as usize);
        let r = [r[0], r[1], r[2].min(sheet.width), r[3].min(sheet.height)];
        let mine: Vec<bool> = bounds.iter().enumerate().map(|(i, s)| {
            let (cx, cy) = ((s[0] + s[2]) / 2, (s[1] + s[3]) / 2);
            i != 0 && cx >= r[0] && cx < r[2] && cy >= r[1] && cy < r[3]
        }).collect();
        let cut = sheet.cut(r, &shape, &mine);
        if b.turned { cut.turned_right() } else { cut }
    }).collect()
}

pub fn load(path: &Path) -> Option<Picture> {
    let img = image::open(path).ok()?.to_rgba8();
    let (w, h) = img.dimensions();
    let mut rgba = img.into_raw();
    // premultiplied, as egui draws
    for px in rgba.chunks_exact_mut(4) {
        let a = px[3] as u32;
        for c in &mut px[..3] { *c = ((*c as u32 * a + 127) / 255) as u8; }
    }
    Some(Picture { width: w as usize, height: h as usize, rgba })
}

pub fn pack() -> Option<PathBuf> {
    std::env::var_os("KIU_MENU_PACK").map(PathBuf::from).filter(|p| p.is_dir())
}

/// The textures of one redrawn screen, ready to draw.
pub struct Art {
    pub id: u16,
    /// each button, and its glow (with the glow's padding in texture pixels)
    pub buttons: Vec<(egui::TextureHandle, egui::TextureHandle, f32)>,
    /// texture pixels per sheet pixel
    pub density: f32,
    pub back: Option<(egui::TextureHandle, egui::TextureHandle, f32, f32)>,
}

fn texture(ctx: &egui::Context, name: &str, p: &Picture) -> egui::TextureHandle {
    let image = egui::ColorImage::from_rgba_premultiplied([p.width, p.height], &p.rgba);
    ctx.load_texture(name, image, egui::TextureOptions::LINEAR)
}

impl Art {
    pub fn load(ctx: &egui::Context, screen: &Screen) -> Option<Art> {
        let pack = pack()?;
        let sheet = load(&pack.join(screen.sheet))?;
        let density = sheet.width as f32 / screen.sheet_size as f32;
        let buttons = cut_buttons(&sheet, screen).iter().zip(screen.buttons).map(|(p, b)| {
            let pad = (p.height.min(p.width) as f32 * 0.14) as usize;
            let glow = p.glow(pad);
            (texture(ctx, &format!("kiu-{}-{}", screen.id, b.name), p), texture(ctx, &format!("kiu-{}-{}-glow", screen.id, b.name), &glow), pad as f32)
        }).collect();
        let back = load(&pack.join(BACK_SHEET)).map(|p| {
            let k = p.width as f32 / 64.0;
            let pad = (p.height as f32 * 0.14) as usize;
            (texture(ctx, "kiu-back", &p), texture(ctx, "kiu-back-glow", &p.glow(pad)), pad as f32, k)
        });
        log::info!("Main menu redrawn from the menu art pack ({}x)", density);
        Some(Art { id: screen.id, buttons, density, back })
    }
}

/// A redrawn screen's moving state: its buttons' motion and the game's
/// cursor.
#[derive(Default)]
pub struct Live {
    pub motion: Motion,
    pub nav: Nav,
}

/// What the pointer did on a redrawn screen this frame.
#[derive(Default)]
pub struct Output {
    /// a click asked for this touch on the lower screen
    pub touch: Option<(u16, u16)>,
    /// the choice the pointer rests on (its node in the game's map)
    pub pointed: Option<usize>,
}

/// The buttons' home rectangles, in units.
fn homes(screen: &Screen, art: &Art) -> Vec<[f32; 4]> {
    screen.buttons.iter().zip(&art.buttons).map(|(b, (tex, _, _))| {
        let (w, h) = (tex.size()[0] as f32 / art.density * b.scale, tex.size()[1] as f32 / art.density * b.scale);
        [b.at[0], b.at[1], b.at[0] + w, b.at[1] + h]
    }).collect()
}

/// A textured quad over `rect` (points), turned `degrees` about its centre.
fn quad(tex: egui::TextureId, rect: egui::Rect, degrees: f32, tint: egui::Color32) -> egui::Shape {
    let mut mesh = egui::Mesh::with_texture(tex);
    mesh.add_rect_with_uv(rect, egui::Rect::from_min_max(egui::pos2(0.0, 0.0), egui::pos2(1.0, 1.0)), tint);
    mesh.rotate(egui::emath::Rot2::from_angle(degrees.to_radians()), rect.center());
    egui::Shape::mesh(mesh)
}

/// The vine as a mesh: black, coverage as alpha, moved by `offset` points.
fn vine_mesh(shape: &crate::menu_vine::Shape, origin: egui::Pos2, unit: f32, offset: egui::Vec2, alpha: f32) -> egui::Shape {
    let mut mesh = egui::Mesh::default();
    for (i, (p, coverage)) in shape.vertices.iter().enumerate() {
        let pos = origin + egui::vec2(p[0], p[1]) * unit + offset;
        // the art's black, very slightly warm
        let a = (coverage * alpha * 255.0) as u8;
        let k = coverage * alpha;
        mesh.vertices.push(egui::epaint::Vertex { pos, uv: egui::epaint::WHITE_UV,
            color: egui::Color32::from_rgba_premultiplied((10.0 * k) as u8, (6.0 * k) as u8, (8.0 * k) as u8, a) });
        mesh.indices.push(i as u32);
    }
    egui::Shape::mesh(mesh)
}

/// Draws a redrawn screen over the window (`window`, in egui points).
/// `selected`: the game's selected choice (its node), lit with a glow.
pub fn show(ctx: &egui::Context, screen: &Screen, art: &Art, live: &mut Live, window: egui::Rect) -> Output {
    let unit = window.height() / 240.0;
    let mut out = Output::default();
    let (time, dt, pointer) = ctx.input(|i| (i.time as f32, i.stable_dt, i.pointer.latest_pos()));
    let pointer_units = pointer.map(|p| [(p.x - window.min.x) / unit, (p.y - window.min.y) / unit]);
    let homes = homes(screen, art);
    live.motion.step(dt, &homes, pointer_units);
    let selected = live.nav.current;
    egui::Area::new(egui::Id::new(("kiu-native-menu", screen.id))).order(egui::Order::Foreground).fixed_pos(window.min).show(ctx, |ui| {
        let painter = ui.painter().clone();
        let to_points = |r: [f32; 4]| egui::Rect::from_min_max(window.min + egui::vec2(r[0], r[1]) * unit, window.min + egui::vec2(r[2], r[3]) * unit);
        let now: Vec<[f32; 4]> = (0..homes.len()).map(|i| live.motion.rect(i, homes[i])).collect();
        // the vine, its soft shadow first
        let vine = crate::menu_vine::vine(&now, 1.2 / unit);
        painter.add(vine_mesh(&vine, window.min, unit, egui::vec2(1.0, 1.6) * unit, 0.3));
        painter.add(vine_mesh(&vine, window.min, unit, egui::Vec2::ZERO, 1.0));
        // the buttons, the held one on top
        let mut order: Vec<usize> = (0..screen.buttons.len()).collect();
        if let Some(held) = live.motion.held() { order.retain(|&i| i != held); order.push(held); }
        for i in order {
            let (b, (tex, glow, pad)) = (&screen.buttons[i], &art.buttons[i]);
            let rect = to_points(now[i]);
            let response = ui.interact(rect, egui::Id::new(("kiu-native", screen.id, i)), egui::Sense::click_and_drag());
            if response.drag_started() { if let Some(p) = pointer_units { live.motion.grab(i, p, homes[i]); } }
            if response.drag_stopped() { live.motion.release(); }
            if response.clicked() { out.touch = Some(b.touch); }
            let pointed = response.hovered() || live.motion.held() == Some(i);
            if pointed { out.pointed = Some(b.node); }
            let lit = selected == Some(b.node);
            let grow = if response.is_pointer_button_down_on() && !response.dragged() { 0.97 } else if pointed { 1.05 } else { 1.0 };
            let rect = egui::Rect::from_center_size(rect.center(), rect.size() * grow);
            let px = rect.width() / tex.size()[0] as f32;
            let lift = if live.motion.held() == Some(i) { 2.0 } else { 1.0 };
            let shadow = rect.translate(egui::vec2(0.9, 1.4) * unit * lift).expand(pad * px * 0.6);
            painter.add(quad(glow.id(), shadow, b.tilt, egui::Color32::from_black_alpha(110)));
            if lit {
                let pulse = 0.78 + 0.22 * (time * 3.5).sin();
                painter.add(quad(glow.id(), rect.expand(pad * px), b.tilt, egui::Color32::from_white_alpha((255.0 * pulse) as u8)));
            }
            painter.add(quad(tex.id(), rect, b.tilt, egui::Color32::WHITE));
        }
        if let Some((tex, glow, pad, k)) = &art.back {
            let size = egui::vec2(tex.size()[0] as f32, tex.size()[1] as f32) / *k * BACK_SCALE * unit;
            let rect = egui::Rect::from_min_size(window.min + egui::vec2(BACK_AT[0], BACK_AT[1]) * unit, size);
            let response = ui.interact(rect, egui::Id::new(("kiu-native-back", screen.id)), egui::Sense::click());
            let grow = if response.is_pointer_button_down_on() { 0.97 } else if response.hovered() { 1.06 } else { 1.0 };
            let rect = egui::Rect::from_center_size(rect.center(), rect.size() * grow);
            if response.hovered() {
                let px = rect.width() / tex.size()[0] as f32;
                painter.add(quad(glow.id(), rect.expand(pad * px), 0.0, egui::Color32::from_white_alpha(230)));
            }
            painter.add(quad(tex.id(), rect, 0.0, egui::Color32::WHITE));
            if response.clicked() { out.touch = Some(back_touch(screen.id)); }
        }
    });
    if !ctx.input(|i| i.pointer.any_down()) { live.motion.release(); }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    fn picture(w: usize, h: usize, on: &[(usize, usize)]) -> Picture {
        let mut rgba = vec![0u8; w * h * 4];
        for &(x, y) in on { rgba[(y * w + x) * 4..][..4].copy_from_slice(&[x as u8, y as u8, 7, 255]); }
        Picture { width: w, height: h, rgba }
    }
    #[test]
    fn a_button_keeps_its_own_shapes_only() {
        // a 2x2 block (the button) and a single pixel poking into its
        // rectangle from a neighbour whose middle is outside it
        let p = picture(8, 4, &[(0, 0), (1, 0), (0, 1), (1, 1), (3, 1), (4, 1), (5, 1), (6, 1)]);
        let (_, bounds) = shapes(&p);
        assert_eq!(bounds.len(), 3);
        let screen = Screen { id: 0, sheet: "", sheet_size: 8, buttons: &[
            Button { name: "a", sheet: [0, 0, 4, 2], turned: false, at: [0.0; 2], scale: 1.0, tilt: 0.0, touch: (0, 0), node: 0 }],
            graph: Graph { edges: &[] }, selected_art: &[] };
        let cut = &cut_buttons(&p, &screen)[0];
        assert_eq!((cut.width, cut.height), (4, 2));
        assert_eq!(cut.alpha(1, 1), 255);
        assert_eq!(cut.alpha(3, 1), 0, "the neighbour's pixel is left out");
    }
    #[test]
    fn a_turned_button_stands_upright() {
        // a 1 wide, 3 tall strip read bottom to top becomes 3 wide left to right
        let p = picture(1, 3, &[(0, 0), (0, 1), (0, 2)]);
        let t = p.turned_right();
        assert_eq!((t.width, t.height), (3, 1));
        // the strip's bottom pixel (y 2) comes first
        assert_eq!(t.rgba[1], 2);
        assert_eq!(t.rgba[2 * 4 + 1], 0);
    }
    #[test]
    fn a_glow_surrounds_the_shape() {
        let p = picture(4, 4, &[(1, 1), (2, 1), (1, 2), (2, 2)]);
        let g = p.glow(4);
        assert_eq!((g.width, g.height), (12, 12));
        assert!(g.alpha(6, 6) > 200, "brightest at the shape");
        assert!(g.alpha(1, 6) < g.alpha(4, 6), "fading out");
        assert_eq!(g.alpha(0, 0), 0);
    }
    #[test]
    fn the_main_menu_stays_in_the_window_and_touches_its_screen() {
        for b in MAIN_MENU.buttons {
            let (w, h) = ((b.sheet[2] - b.sheet[0]) as f32, (b.sheet[3] - b.sheet[1]) as f32);
            let (w, h) = if b.turned { (h, w) } else { (w, h) };
            assert!(b.at[0] + w * b.scale < 426.0 && b.at[1] + h * b.scale <= 240.0, "{}", b.name);
            assert!(b.touch.0 < 320 && b.touch.1 < 240);
        }
        // the column does not reach the caption's black ground (from 165),
        // one scale, even gaps, inside the safe margin
        let mut bottom: Option<f32> = None;
        for b in MAIN_MENU.buttons {
            let h = if b.turned { b.sheet[2] - b.sheet[0] } else { b.sheet[3] - b.sheet[1] } as f32 * b.scale;
            if let Some(previous) = bottom { assert!((b.at[1] - previous - 10.0f32).abs() < 0.2, "{}", b.name); }
            bottom = Some(b.at[1] + h);
            assert_eq!(b.scale, MAIN_MENU.buttons[0].scale);
            assert!(b.at[0] >= 12.0 && b.at[1] >= 12.0);
        }
        assert!(bottom.unwrap() < 165.0);
        assert_eq!(MAIN_MENU.selected(0b0010), Some(1));
        assert_eq!(MAIN_MENU.selected(0b0110), None, "two cross-fading");
        assert_eq!(MAIN_MENU.selected(0b10000), None, "not one of the choices");
        assert_eq!(MAIN_MENU.graph.first_step(0, 2, |n| MAIN_MENU.shows(n)), Some(crate::menu_motion::Dir::Down), "Solo, then Vault below it");
        // Together to Solo goes by Vault, not by the hidden StreetPass
        assert_eq!(MAIN_MENU.graph.first_step(1, 0, |n| MAIN_MENU.shows(n)), Some(crate::menu_motion::Dir::Left));
        assert!(BACK_AT[0] >= 12.0 && BACK_AT[1] + 32.0 * BACK_SCALE <= 228.0);
    }
}

#[cfg(test)]
mod pack_check {
    /// With KIU_TEST_PACK (a menu art pack) and KIU_TEST_OUT: writes each
    /// cut button and glow of the main menu, to look at.
    #[test]
    fn cut_the_real_sheet() {
        let (Some(pack), Some(out)) = (std::env::var_os("KIU_TEST_PACK"), std::env::var_os("KIU_TEST_OUT")) else { return };
        let sheet = super::load(&std::path::Path::new(&pack).join(super::MAIN_MENU.sheet)).unwrap();
        for (p, b) in super::cut_buttons(&sheet, &super::MAIN_MENU).iter().zip(super::MAIN_MENU.buttons) {
            for (q, name) in [(p.clone(), b.name.to_string()), (p.glow((p.height.min(p.width) as f32 * 0.14) as usize), format!("{}-glow", b.name))] {
                image::RgbaImage::from_raw(q.width as u32, q.height as u32, q.rgba).unwrap()
                    .save(std::path::Path::new(&out).join(format!("{name}.png"))).unwrap();
            }
        }
    }
}
