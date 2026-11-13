//! A redrawn screen's art: its buttons cut from the game's sheet along their
//! own outlines, each with its glow and the mask that says where it can be
//! pointed at. Prepared on its own thread from start-up (`prepare`), then
//! uploaded once (`Prepared::upload`).

use crate::pc_menus::menu_art_pack;
use crate::pc_menus::picture::{load, shapes, Picture};
use crate::pc_menus::screens::{Screen, BACK_SHEET, SCREENS};

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

/// The textures of one redrawn screen, ready to draw.
pub struct Art {
    pub id: u16,
    /// each button, and its glow (with the glow's padding in texture pixels)
    pub buttons: Vec<(egui::TextureHandle, egui::TextureHandle, f32)>,
    /// each button's outline for pointing: its glow's coverage (the shape
    /// grown by a few pixels), so a button answers only over its own art,
    /// not the empty corners of its rectangle
    pub masks: Vec<Mask>,
    /// texture pixels per sheet pixel
    pub density: f32,
    pub back: Option<(egui::TextureHandle, egui::TextureHandle, f32, f32)>,
}

/// Where a button can be pointed at: coverage, one byte per glow pixel.
pub struct Mask { pub width: usize, pub height: usize, pub coverage: Vec<u8> }

impl Mask {
    fn of(p: &Picture) -> Mask {
        Mask { width: p.width, height: p.height, coverage: (0..p.width * p.height).map(|i| p.rgba[i * 4 + 3]).collect() }
    }
    /// Whether `uv` (0..1 across the glow's rectangle) is on the button.
    pub fn covers(&self, uv: [f32; 2]) -> bool {
        if !(0.0..1.0).contains(&uv[0]) || !(0.0..1.0).contains(&uv[1]) { return false; }
        let (x, y) = ((uv[0] * self.width as f32) as usize, (uv[1] * self.height as f32) as usize);
        self.coverage[y * self.width + x] > 90
    }
}

fn texture(ctx: &egui::Context, name: &str, p: &Picture) -> egui::TextureHandle {
    let image = egui::ColorImage::from_rgba_premultiplied([p.width, p.height], &p.rgba);
    ctx.load_texture(name, image, egui::TextureOptions::LINEAR)
}

/// A screen's button pictures, cut and glowed (the slow part), ready to
/// become textures; made on its own thread (`prepare`).
pub struct Prepared {
    id: u16,
    buttons: Vec<(Picture, Picture, f32)>,
    density: f32,
    back: Option<(Picture, Picture, f32, f32)>,
}

/// Cuts and glows every redrawn screen's buttons on its own thread (at
/// start-up), so showing a screen costs only its upload.
pub fn prepare() -> std::sync::mpsc::Receiver<Vec<Prepared>> {
    let (tx, rx) = std::sync::mpsc::channel();
    let _ = std::thread::Builder::new().name("native-menu-art".into()).spawn(move || {
        let _ = tx.send(SCREENS.iter().filter_map(|s| Prepared::make(s)).collect());
    });
    rx
}

impl Prepared {
    fn make(screen: &Screen) -> Option<Prepared> {
        let start = std::time::Instant::now();
        let pack = menu_art_pack()?;
        let sheet = load(&pack.join(screen.sheet))?;
        let density = sheet.width as f32 / screen.sheet_size as f32;
        let buttons = cut_buttons(&sheet, screen).into_iter().map(|p| {
            let pad = (p.height.min(p.width) as f32 * 0.14) as usize;
            let glow = p.glow(pad);
            (p, glow, pad as f32)
        }).collect();
        let back = load(&pack.join(BACK_SHEET)).map(|p| {
            let k = p.width as f32 / 64.0;
            let pad = (p.height as f32 * 0.14) as usize;
            let glow = p.glow(pad);
            (p, glow, pad as f32, k)
        });
        log::info!("Menu {:03} redrawn from the menu art pack ({}x), prepared in {} ms", screen.id, density, start.elapsed().as_millis());
        Some(Prepared { id: screen.id, buttons, density, back })
    }

    /// The textures (quick: the pictures are ready).
    pub fn upload(&self, ctx: &egui::Context) -> Option<Art> {
        let screen = SCREENS.iter().find(|s| s.id == self.id)?;
        let buttons = self.buttons.iter().zip(screen.buttons).map(|((p, glow, pad), b)| {
            (texture(ctx, &format!("kiu-{}-{}", screen.id, b.name), p), texture(ctx, &format!("kiu-{}-{}-glow", screen.id, b.name), glow), *pad)
        }).collect();
        let masks = self.buttons.iter().map(|(_, glow, _)| Mask::of(glow)).collect();
        let back = self.back.as_ref().map(|(p, glow, pad, k)| (texture(ctx, "kiu-back", p), texture(ctx, "kiu-back-glow", glow), *pad, *k));
        Some(Art { id: self.id, buttons, masks, density: self.density, back })
    }
}

impl Art {
    /// Cuts, glows and uploads at once (the preview test).
    #[cfg(test)]
    pub fn load(ctx: &egui::Context, screen: &Screen) -> Option<Art> { Prepared::make(screen)?.upload(ctx) }
}

#[cfg(test)]
mod pack_check {
    /// With KIU_TEST_PACK (a menu art pack) and KIU_TEST_OUT: writes each
    /// cut button and glow of the main menu, to look at.
    #[test]
    fn cut_the_real_sheet() {
        let (Some(pack), Some(out)) = (std::env::var_os("KIU_TEST_PACK"), std::env::var_os("KIU_TEST_OUT")) else { return };
        let sheet = crate::pc_menus::picture::load(&std::path::Path::new(&pack).join(crate::pc_menus::screens::MAIN_MENU.sheet)).unwrap();
        for (p, b) in super::cut_buttons(&sheet, &crate::pc_menus::screens::MAIN_MENU).iter().zip(crate::pc_menus::screens::MAIN_MENU.buttons) {
            for (q, name) in [(p.clone(), b.name.to_string()), (p.glow((p.height.min(p.width) as f32 * 0.14) as usize), format!("{}-glow", b.name))] {
                image::RgbaImage::from_raw(q.width as u32, q.height as u32, q.rgba).unwrap()
                    .save(std::path::Path::new(&out).join(format!("{name}.png"))).unwrap();
            }
        }
    }
}

