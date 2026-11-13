//! A preview without the game: the scene's real drawing, through egui's own
//! tessellator, filled into pictures by a small software rasterizer.
//!   KIU_SCENE_PACK=<scene-040> KIU_SCENE_OUT=<folder> [KIU_SCENE_FRAMES=n] \
//!     cargo test --release -p zakuro --lib pc_menus::scene::preview -- --nocapture
//! The script: Solo shown, Together at 130, Vault at 230, Options at 320,
//! Together at 420, confirmed at 452, the game leaves at 500.

use super::*;
use std::path::PathBuf;

use egui::epaint::{ImageDelta, Primitive};
use egui::Mesh;

struct Img { w: usize, h: usize, px: Vec<[f32; 4]> }
fn apply(textures: &mut HashMap<egui::TextureId, Img>, id: egui::TextureId, d: &ImageDelta) {
    let egui::ImageData::Color(c) = &d.image;
    let conv = |p: &Color32| [p.r() as f32, p.g() as f32, p.b() as f32, p.a() as f32];
    match d.pos {
        None => { textures.insert(id, Img { w: c.size[0], h: c.size[1], px: c.pixels.iter().map(conv).collect() }); }
        Some([x0, y0]) => if let Some(t) = textures.get_mut(&id) {
            for y in 0..c.size[1] { for x in 0..c.size[0] { t.px[(y0 + y) * t.w + x0 + x] = conv(&c.pixels[y * c.size[0] + x]); } }
        },
    }
}
fn sample(t: &Img, u: f32, v: f32) -> [f32; 4] {
    let (x, y) = ((u * t.w as f32 - 0.5).clamp(0.0, t.w as f32 - 1.0), (v * t.h as f32 - 0.5).clamp(0.0, t.h as f32 - 1.0));
    let (x0, y0) = (x.floor() as usize, y.floor() as usize); let (x1, y1) = ((x0 + 1).min(t.w - 1), (y0 + 1).min(t.h - 1));
    let (fx, fy) = (x - x0 as f32, y - y0 as f32);
    let g = |xx: usize, yy: usize| t.px[yy * t.w + xx];
    let (a, b, c, d) = (g(x0, y0), g(x1, y0), g(x0, y1), g(x1, y1));
    [0, 1, 2, 3].map(|i| a[i] * (1.0 - fx) * (1.0 - fy) + b[i] * fx * (1.0 - fy) + c[i] * (1.0 - fx) * fy + d[i] * fx * fy)
}
fn raster(img: &mut [[f32; 3]], (w, h): (usize, usize), mesh: &Mesh, clip: Rect, ppp: f32, textures: &HashMap<egui::TextureId, Img>) {
    let tex = textures.get(&mesh.texture_id);
    for t in mesh.indices.chunks_exact(3) {
        let v = [mesh.vertices[t[0] as usize], mesh.vertices[t[1] as usize], mesh.vertices[t[2] as usize]];
        let p = v.map(|v| [v.pos.x * ppp, v.pos.y * ppp]);
        let area = (p[1][0] - p[0][0]) * (p[2][1] - p[0][1]) - (p[2][0] - p[0][0]) * (p[1][1] - p[0][1]);
        if area.abs() < 1e-6 { continue; }
        let minx = (p.iter().map(|q| q[0]).fold(f32::MAX, f32::min).max(clip.min.x * ppp).max(0.0)) as usize;
        let maxx = (p.iter().map(|q| q[0]).fold(f32::MIN, f32::max).min(clip.max.x * ppp).min(w as f32 - 1.0)).max(-1.0) as isize;
        let miny = (p.iter().map(|q| q[1]).fold(f32::MAX, f32::min).max(clip.min.y * ppp).max(0.0)) as usize;
        let maxy = (p.iter().map(|q| q[1]).fold(f32::MIN, f32::max).min(clip.max.y * ppp).min(h as f32 - 1.0)).max(-1.0) as isize;
        for y in miny as isize..=maxy { for x in minx as isize..=maxx {
            let (fx, fy) = (x as f32 + 0.5, y as f32 + 0.5);
            let w0 = ((p[1][0] - fx) * (p[2][1] - fy) - (p[2][0] - fx) * (p[1][1] - fy)) / area;
            let w1 = ((p[2][0] - fx) * (p[0][1] - fy) - (p[0][0] - fx) * (p[2][1] - fy)) / area;
            let w2 = 1.0 - w0 - w1;
            if w0 < -1e-4 || w1 < -1e-4 || w2 < -1e-4 { continue; }
            let col = |i: usize| [v[i].color.r() as f32, v[i].color.g() as f32, v[i].color.b() as f32, v[i].color.a() as f32];
            let (c0, c1, c2) = (col(0), col(1), col(2));
            let vc = [0, 1, 2, 3].map(|k| (c0[k] * w0 + c1[k] * w1 + c2[k] * w2) / 255.0);
            let (u, vv) = (v[0].uv.x * w0 + v[1].uv.x * w1 + v[2].uv.x * w2, v[0].uv.y * w0 + v[1].uv.y * w1 + v[2].uv.y * w2);
            let s = tex.map_or([255.0; 4], |t| sample(t, u, vv));
            let src = [0, 1, 2, 3].map(|k| s[k] * vc[k]);
            let d = &mut img[y as usize * w + x as usize];
            let a = src[3] / 255.0;
            for k in 0..3 { d[k] = (src[k] + d[k] * (1.0 - a)).min(255.0); }
        } }
    }
}

#[test]
fn render() {
    let (Some(pack), Some(out)) = (std::env::var_os("KIU_SCENE_PACK"), std::env::var_os("KIU_SCENE_OUT")) else { return };
    let out = PathBuf::from(out); std::fs::create_dir_all(&out).unwrap();
    let n: usize = std::env::var("KIU_SCENE_FRAMES").ok().and_then(|s| s.parse().ok()).unwrap_or(600);
    let only: Option<Vec<usize>> = std::env::var("KIU_SCENE_ONLY").ok().map(|s| s.split(',').filter_map(|x| x.parse().ok()).collect());
    let ctx = egui::Context::default();
    let (w, h, ppp) = (960usize, 540usize, 0.5f32);
    let screen = Rect::from_min_size(Pos2::ZERO, egui::vec2(W, H));
    let mut textures: HashMap<egui::TextureId, Img> = HashMap::new();
    let mut scene: Option<Scene> = None;
    // the buttons and their vine too, when KIU_MENU_PACK points at the menu art pack
    let menu = &crate::pc_menus::buttons::MAIN_MENU;
    let mut art: Option<Option<crate::pc_menus::buttons::Art>> = None;
    let mut live = crate::pc_menus::buttons::Live::default();
    for f in 0..n {
        let t = f as f64 / 60.0;
        let input = egui::RawInput { time: Some(t), screen_rect: Some(screen), ..Default::default() };
        let output = ctx.run_ui(input, |ui| {
            let ctx = ui.ctx().clone();
            if scene.is_none() { scene = Scene::load(&ctx, std::path::Path::new(&pack)); }
            let s = scene.as_mut().unwrap();
            if f == 0 { s.on_menu(&ctx); }
            let sel = [(0usize, 0usize), (130, 1), (230, 2), (320, 3), (420, 1)].iter().rev().find(|(at, _)| f >= *at).map(|x| x.1);
            // wait for the frames the character needs (the game would show the previous one)
            for _ in 0..200 { s.stream.receive(); if !s.stream.pending() { break; } std::thread::sleep(std::time::Duration::from_millis(5)); }
            if f < 452 { s.select(sel); }
            if f == 452 { s.confirm(1, Some(Pos2::new(281.0, 520.0)), screen); }
            if f >= 500 { s.game_left(); }
            s.show(&ctx, screen);
            let art = art.get_or_insert_with(|| crate::pc_menus::buttons::Art::load(&ctx, &crate::pc_menus::buttons::MAIN_MENU));
            if let Some(art) = art {
                live.nav.observe(sel, true);
                let presence: Vec<(f32, f32)> = (0..4).map(|i| s.button_presence(i)).collect();
                let _ = crate::pc_menus::buttons::show(&ctx, menu, art, &mut live, screen, &presence, s.interactive());
            }
        });
        for (id, ds) in &output.textures_delta.set { for d in ds.iter() { apply(&mut textures, *id, d); } }
        if only.as_ref().is_some_and(|o| !o.contains(&f)) { continue; }
        let prims = ctx.tessellate(output.shapes, 1.0);
        let mut img = vec![[0.0f32; 3]; w * h];
        for p in &prims { if let Primitive::Mesh(m) = &p.primitive { raster(&mut img, (w, h), m, p.clip_rect, ppp, &textures); } }
        let bytes: Vec<u8> = img.iter().flat_map(|c| c.map(|x| x as u8)).collect();
        image::RgbImage::from_raw(w as u32, h as u32, bytes).unwrap().save(out.join(format!("{f:04}.png"))).unwrap();
    }
}
