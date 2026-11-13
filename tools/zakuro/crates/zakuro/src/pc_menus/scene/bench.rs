
/// KIU_SCENE_PACK=... cargo test --release -p zakuro --lib pc_menus::scene::bench -- --nocapture --ignored
#[test]
#[ignore]
fn timings() {
    let Some(root) = super::pack() else { return };
    let t = std::time::Instant::now();
    let mut n = 0; let mut px = 0;
    for i in [100, 101, 102, 103, 104, 105, 106, 107] {
        let p = super::frames::load_frame(&root.join("char_2"), i, None).unwrap();
        n += 1; px += p.width * p.height;
    }
    let dt = t.elapsed().as_secs_f64() / n as f64;
    println!("char frame decode: {:.1} ms each ({:.2} Mpx)", dt * 1000.0, px as f64 / n as f64 / 1e6);
    let t = std::time::Instant::now();
    for f in ["paper_1.webp", "stage_1.webp", "rays_1.webp"] { let _ = crate::pc_menus::buttons::load(&root.join(f)).unwrap(); }
    println!("paper+stage+rays decode: {:.0} ms", t.elapsed().as_secs_f64() * 1000.0);
    // the menu as the game runs it: real time, never waiting for frames
    {
        let ctx = egui::Context::default();
        let screen = egui::Rect::from_min_size(egui::Pos2::ZERO, egui::vec2(super::W, super::H));
        let t0 = std::time::Instant::now();
        let mut scene = super::Scene::load(&ctx, &root).unwrap();
        println!("load (all at once, test only): {:.0} ms", t0.elapsed().as_secs_f64() * 1000.0);
        let start = std::time::Instant::now();
        let mut worst = 0.0f64; let mut total = 0.0f64; let mut n = 0;
        for f in 0..600usize {
            // 60 frames a second of wall time
            let due = start + std::time::Duration::from_micros(16_667 * f as u64);
            if let Some(wait) = due.checked_duration_since(std::time::Instant::now()) { std::thread::sleep(wait); }
            let t = std::time::Instant::now();
            let input = egui::RawInput { time: Some(start.elapsed().as_secs_f64()), screen_rect: Some(screen), ..Default::default() };
            let sel = [(0usize, 0usize), (130, 1), (230, 2), (320, 3), (420, 1), (470, 0), (520, 2)].iter().rev().find(|(at, _)| f >= *at).map(|x| x.1);
            let out = ctx.run_ui(input, |ui| {
                if f == 0 { scene.on_menu(ui.ctx()); }
                scene.select(sel);
                scene.show(ui.ctx(), screen);
            });
            // what gui.rs does with the textures, and the meshes
            let mut bytes = 0;
            for (_, ds) in &out.textures_delta.set { for d in ds { let egui::ImageData::Color(c) = &d.image; let mut b = vec![0u8; c.pixels.len() * 4]; for (o, p) in b.chunks_exact_mut(4).zip(&c.pixels) { o.copy_from_slice(&p.to_array()); } bytes += b.len(); } }
            let _ = ctx.tessellate(out.shapes, 1.0);
            let dt = t.elapsed().as_secs_f64() * 1000.0;
            if f > 5 { worst = worst.max(dt); total += dt; n += 1; }
            if dt > 12.0 { println!("  frame {f}: {dt:.1} ms ({} KB uploaded)", bytes >> 10); }
        }
        let st = scene.stream.stats;
        println!("real time: {:.1} ms a frame on average, worst {:.1} ms; character frames on time {}, late {} (at most {} behind)", total / n as f64, worst, st[0], st[1], st[2]);
    }
    let ctx = egui::Context::default();
    let t = std::time::Instant::now();
    let mut s = None;
    let _ = ctx.run_ui(egui::RawInput::default(), |_| { s = super::Scene::load(&_ui_ctx(), &root); });
    println!("Scene::load: {:.0} ms", t.elapsed().as_secs_f64() * 1000.0);
    fn _ui_ctx() -> egui::Context { egui::Context::default() }
}
