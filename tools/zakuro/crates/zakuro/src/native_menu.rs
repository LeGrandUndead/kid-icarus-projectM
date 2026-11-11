//! The game's menus redrawn on the PC screen with the game's own art.
//!
//! The lower screen is not shown at all. Each of the game's buttons is drawn
//! by us, from the button sheet the game itself uses (in the PC menu art
//! pack, `KIU_MENU_PACK`, rebuilt from the player's ROM at 4x), cut along
//! its own outline, at a place laid out for a 16:9 window. Pointing at one
//! lights it; clicking it touches the game's real button on its hidden lower
//! screen (top_menus::Tap), so the game still decides what happens, with its
//! own sounds, transitions and rules. Keyboard and controller keep working
//! as they always did.
//!
//! Only coordinates live here; the art is read at run time from the pack on
//! the player's machine.

use std::path::{Path, PathBuf};

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
    /// where touching the 3DS lower screen presses it.
    pub touch: (u16, u16),
}

/// A screen redrawn this way.
pub struct Screen {
    /// the menu archive whose art identifies the screen.
    pub id: u16,
    /// the sheet's name in the pack: `<w>x<h>-<fingerprint>.png`.
    pub sheet: &'static str,
    pub sheet_size: u32,
    pub buttons: &'static [Button],
}

/// The game's Back arrow, the same on every menu screen.
pub const BACK_SHEET: &str = "64x32-230262A22CA913D6.png";
pub const BACK_AT: [f32; 2] = [12.0, 210.0];
pub const BACK_SCALE: f32 = 0.5;

/// The main menu: Solo, Together, Vault and Options in one column on the
/// left of the section's art, clear of its heading and of the caption's
/// black ground. One scale for all four (the art's own proportions keep
/// Solo first), 10 units between them, inside the safe margins
/// (doc/UI_DESIGN_RULES.md). StreetPass and AR Cards (3DS only) are left out.
pub const MAIN_MENU: Screen = Screen { id: 40, sheet: "256x256-701C2B1F2A647930.png", sheet_size: 256, buttons: &[
    Button { name: "Solo", sheet: [1, 1, 193, 86], turned: false, at: [14.0, 24.0], scale: 0.34, touch: (104, 52) },
    Button { name: "Together", sheet: [1, 91, 184, 180], turned: false, at: [14.0, 62.9], scale: 0.34, touch: (224, 128) },
    Button { name: "Vault", sheet: [0, 182, 118, 255], turned: false, at: [14.0, 103.2], scale: 0.34, touch: (64, 140) },
    Button { name: "Options", sheet: [203, 1, 255, 174], turned: true, at: [14.0, 138.0], scale: 0.34, touch: (142, 211) },
] };

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

/// Draws a redrawn screen over the window (`window`, in egui points) and
/// returns the touch a click asked for.
pub fn show(ctx: &egui::Context, screen: &Screen, art: &Art, window: egui::Rect) -> Option<(u16, u16)> {
    let unit = window.height() / 240.0;
    let mut clicked = None;
    let time = ctx.input(|i| i.time) as f32;
    egui::Area::new(egui::Id::new(("kiu-native-menu", screen.id))).order(egui::Order::Foreground).fixed_pos(window.min).show(ctx, |ui| {
        let painter = ui.painter().clone();
        let draw = |id: egui::Id, tex: &egui::TextureHandle, glow: &egui::TextureHandle, pad: f32, at: [f32; 2], size: egui::Vec2| -> bool {
            let rect = egui::Rect::from_min_size(window.min + egui::vec2(at[0], at[1]) * unit, size);
            let response = ui.interact(rect, id, egui::Sense::click());
            let lit = response.hovered();
            let grow = if response.is_pointer_button_down_on() { 0.97 } else if lit { 1.06 } else { 1.0 };
            let rect = egui::Rect::from_center_size(rect.center(), rect.size() * grow);
            let uv = egui::Rect::from_min_max(egui::pos2(0.0, 0.0), egui::pos2(1.0, 1.0));
            let px = rect.width() / tex.size()[0] as f32;
            // a soft shadow under it
            let shadow = rect.translate(egui::vec2(rect.height() * 0.03, rect.height() * 0.05)).expand(pad * px * 0.6);
            painter.image(glow.id(), shadow, uv, egui::Color32::from_black_alpha(120));
            if lit {
                let pulse = 0.8 + 0.2 * (time * 4.0).sin();
                painter.image(glow.id(), rect.expand(pad * px), uv, egui::Color32::from_white_alpha((255.0 * pulse) as u8));
            }
            painter.image(tex.id(), rect, uv, egui::Color32::WHITE);
            response.clicked()
        };
        for (i, (b, (tex, glow, pad))) in screen.buttons.iter().zip(&art.buttons).enumerate() {
            let size = egui::vec2(tex.size()[0] as f32, tex.size()[1] as f32) / art.density * b.scale * unit;
            if draw(egui::Id::new(("kiu-native", screen.id, i)), tex, glow, *pad, b.at, size) { clicked = Some(b.touch); }
        }
        if let Some((tex, glow, pad, k)) = &art.back {
            let size = egui::vec2(tex.size()[0] as f32, tex.size()[1] as f32) / *k * BACK_SCALE * unit;
            if draw(egui::Id::new(("kiu-native-back", screen.id)), tex, glow, *pad, BACK_AT, size) { clicked = Some(back_touch(screen.id)); }
        }
    });
    clicked
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
            Button { name: "a", sheet: [0, 0, 4, 2], turned: false, at: [0.0; 2], scale: 1.0, touch: (0, 0) }] };
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
