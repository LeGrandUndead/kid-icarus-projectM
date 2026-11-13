//! The game's menus redrawn on the PC screen with the game's own art.
//!
//! The lower screen is not shown at all. Each of the game's buttons is drawn
//! by us, from the button sheet the game itself uses (in the PC menu art
//! pack, `KIU_MENU_PACK`, rebuilt from the player's ROM at 4x), cut along
//! its own outline, at a place laid out for a 16:9 window
//! (doc/UI_DESIGN_RULES.md). A vine in the art's own style binds them
//! (menu_vine); they sway together in a slow breeze (menu_motion). Pointing
//! lights a button (by its own outline), clicking presses it, and, as in the
//! game, a deliberate drag pulls it about on its vine; it springs back.
//!
//! Moving the pointer onto a button selects it at once on the PC (the gold,
//! the PC scene's heading and character), while the game's own cursor
//! walks there out of sight with the D-pad (menu_motion::Nav); clicking it touches the game's real
//! button on its hidden lower screen (top_menus::Tap). The game still
//! decides what happens; keyboard and controller keep working, and light
//! the same buttons.
//!
//! Only coordinates and texture fingerprints live here; the art is read at
//! run time from the pack on the player's machine.

use crate::pc_menus::art::Art;
use crate::pc_menus::cursor::Nav;
use crate::pc_menus::motion::Motion;
use crate::pc_menus::screens::{back_touch, Screen, BACK_AT, BACK_SCALE};

/// A redrawn screen's moving state: its buttons' motion and the game's
/// cursor.
#[derive(Default)]
pub struct Live {
    pub motion: Motion,
    pub nav: Nav,
    /// the button pressed, where (units), and whether it became a drag
    press: Option<(usize, [f32; 2], bool)>,
    /// each button's eased hover (0 rest, 1 pointed) and gold (0 off, 1 lit)
    ease: Vec<[f32; 2]>,
    /// the button the pointer was on last frame
    last_pointed: Option<usize>,
}

/// What the pointer did on a redrawn screen this frame.
#[derive(Default)]
pub struct Output {
    /// a button was clicked: its choice, and its centre (points)
    pub clicked: Option<(usize, egui::Pos2)>,
    /// the Back arrow was clicked
    pub back: bool,
    /// a click asked for this touch on the lower screen
    pub touch: Option<(u16, u16)>,
    /// the choice the pointer rests on (its node in the game's map)
    pub pointed: Option<usize>,
    /// the pointer has just moved onto this choice (select it)
    pub entered: Option<usize>,
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
fn vine_mesh(shape: &crate::pc_menus::vine::Shape, origin: egui::Pos2, unit: f32, offset: egui::Vec2, alpha: f32) -> egui::Shape {
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

/// The gold of the selection (the only thing in the menu that uses it).
const GOLD: egui::Color32 = egui::Color32::from_rgb(255, 208, 84);

/// Draws a redrawn screen over the window (`window`, in egui points).
/// The game's selected choice (`live.nav.current`) is lit with a gold glow,
/// the others step back. `presence(i)`: button i's horizontal offset in
/// units and its opacity (a scene's entrance and exit, menu_scene);
/// `interactive`: false while the scene is leaving.
pub fn show(ctx: &egui::Context, screen: &Screen, art: &Art, live: &mut Live, window: egui::Rect,
            presence: &[(f32, f32)], interactive: bool) -> Output {
    let unit = window.height() / 240.0;
    let mut out = Output::default();
    let (time, dt, pointer) = ctx.input(|i| (i.time as f32, i.stable_dt, i.pointer.latest_pos()));
    let pointer_units = pointer.map(|p| [(p.x - window.min.x) / unit, (p.y - window.min.y) / unit]);
    let homes = homes(screen, art);
    live.motion.step(dt, &homes, pointer_units);
    let (pressed, released, down) = ctx.input(|i| (i.pointer.primary_pressed(), i.pointer.primary_released(), i.pointer.primary_down()));
    let shown = presence.iter().map(|p| p.1).fold(0.0f32, f32::max).min(1.0);
    // which button is under the pointer: by its outline, the top one first
    // (later buttons and the held one are drawn on top)
    let placed: Vec<egui::Rect> = (0..homes.len()).map(|i| {
        let r = live.motion.rect(i, homes[i]); let dx = presence.get(i).map_or(0.0, |p| p.0);
        egui::Rect::from_min_max(window.min + egui::vec2(r[0] + dx, r[1]) * unit, window.min + egui::vec2(r[2] + dx, r[3]) * unit)
    }).collect();
    let hit = |i: usize, p: egui::Pos2| -> bool {
        let (b, (tex, _, pad)) = (&screen.buttons[i], &art.buttons[i]);
        let rect = placed[i];
        let glow = rect.expand(pad * rect.width() / tex.size()[0] as f32);
        // undo the button's tilt about its centre
        let local = rect.center() + egui::emath::Rot2::from_angle(-b.tilt.to_radians()) * (p - rect.center());
        art.masks[i].covers([(local.x - glow.min.x) / glow.width(), (local.y - glow.min.y) / glow.height()])
    };
    let mut top: Vec<usize> = (0..screen.buttons.len()).rev().collect();
    if let Some(h) = live.motion.held() { top.retain(|&i| i != h); top.insert(0, h); }
    let over = if shown > 0.5 && interactive { pointer.and_then(|p| top.iter().copied().find(|&i| presence.get(i).map_or(1.0, |q| q.1) > 0.5 && hit(i, p))) } else { None };
    // a click: pressed and released on the same button's own shape. As in
    // the game, a button can also be dragged about on its vine (it springs
    // back): only once the pointer has moved a clear 2.5 units (about 11
    // pixels at 1080p) while held, so a click never turns into a drag.
    if interactive {
        if pressed { live.press = over.zip(pointer_units).map(|(i, p)| (i, p, false)); }
        if let (Some((i, at, false)), Some(p), true) = (live.press, pointer_units, down) {
            if ((p[0] - at[0]).powi(2) + (p[1] - at[1]).powi(2)).sqrt() > 2.5 {
                live.motion.grab(i, at, homes[i]);
                live.press = Some((i, at, true));
            }
        }
        if released {
            if let Some((i, _, false)) = live.press {
                if over == Some(i) { out.touch = Some(screen.buttons[i].touch); out.clicked = Some((screen.buttons[i].node, placed[i].center())); }
            }
            live.press = None;
        }
    } else { live.press = None; }
    let pointing = live.motion.held().or(over);
    out.pointed = pointing.map(|i| screen.buttons[i].node);
    // only moving onto a button selects it, so keys and the pad keep
    // working while the pointer rests on one
    if pointing != live.last_pointed { out.entered = out.pointed; }
    live.last_pointed = pointing;
    // the selection shown: the pointer's at once, else where the game's
    // cursor is going (it catches up out of sight, menu_motion::Nav)
    let selected = out.entered.or(live.nav.heading());
    // hover and gold ease in and out (about 8 frames) rather than pop
    live.ease.resize(screen.buttons.len(), [0.0; 2]);
    let follow = 1.0 - (-dt.clamp(0.0, 0.1) * 22.0).exp();
    for (i, e) in live.ease.iter_mut().enumerate() {
        let want = [(pointing == Some(i)) as u8 as f32, (selected == Some(screen.buttons[i].node)) as u8 as f32];
        for k in 0..2 { e[k] += (want[k] - e[k]) * follow; }
    }
    egui::Area::new(egui::Id::new(("kiu-native-menu", screen.id))).order(egui::Order::Foreground).fixed_pos(window.min).show(ctx, |ui| {
        let painter = ui.painter().clone();
        let to_points = |r: [f32; 4]| egui::Rect::from_min_max(window.min + egui::vec2(r[0], r[1]) * unit, window.min + egui::vec2(r[2], r[3]) * unit);
        let now: Vec<[f32; 4]> = (0..homes.len()).map(|i| {
            let r = live.motion.rect(i, homes[i]); let dx = presence.get(i).map_or(0.0, |p| p.0);
            [r[0] + dx, r[1], r[2] + dx, r[3]]
        }).collect();
        if shown <= 0.01 { return; }
        // the vine, its soft shadow first
        let vine = crate::pc_menus::vine::vine(&now, 1.2 / unit);
        painter.add(vine_mesh(&vine, window.min, unit, egui::vec2(1.0, 1.6) * unit, 0.3 * shown));
        painter.add(vine_mesh(&vine, window.min, unit, egui::Vec2::ZERO, shown));
        // the buttons, the held one on top
        let mut order: Vec<usize> = (0..screen.buttons.len()).collect();
        if let Some(held) = live.motion.held() { order.retain(|&i| i != held); order.push(held); }
        for i in order {
            let (b, (tex, glow, pad)) = (&screen.buttons[i], &art.buttons[i]);
            let rect = to_points(now[i]);
            let alpha = presence.get(i).map_or(1.0, |p| p.1);
            if alpha <= 0.01 { continue; }
            // claims the pointer over the button (so the game's own pointer
            // handling stays out), the pressing is ours (above)
            let _ = ui.interact(rect, egui::Id::new(("kiu-native", screen.id, i)), egui::Sense::hover());
            let [hover, gold] = live.ease[i];
            let lit = gold > 0.02;
            let pressing = live.press.is_some_and(|(p, _, dragging)| p == i && !dragging) && over == Some(i);
            let grow = if pressing { 0.97 } else { 1.0 + 0.05 * hover };
            let rect = egui::Rect::from_center_size(rect.center(), rect.size() * grow);
            let px = rect.width() / tex.size()[0] as f32;
            let lift = if live.motion.held() == Some(i) { 2.0 } else { 1.0 };
            let shadow = rect.translate(egui::vec2(0.9, 1.4) * unit * lift).expand(pad * px * 0.6);
            let fade = |c: egui::Color32| c.gamma_multiply(alpha);
            painter.add(quad(glow.id(), shadow, b.tilt, fade(egui::Color32::from_black_alpha(110))));
            if lit {
                let pulse = 0.78 + 0.22 * (time * 3.5).sin();
                painter.add(quad(glow.id(), rect.expand(pad * px), b.tilt, fade(GOLD.gamma_multiply(pulse * gold))));
            }
            // the others step back a little
            let tint = if selected.is_none() { egui::Color32::WHITE } else { egui::Color32::from_gray((196.0 + 59.0 * gold) as u8) };
            painter.add(quad(tex.id(), rect, b.tilt, fade(tint)));
        }
        if let Some((tex, glow, pad, k)) = &art.back {
            let size = egui::vec2(tex.size()[0] as f32, tex.size()[1] as f32) / *k * BACK_SCALE * unit;
            let rect = egui::Rect::from_min_size(window.min + egui::vec2(BACK_AT[0], BACK_AT[1]) * unit, size);
            let sense = if interactive { egui::Sense::click() } else { egui::Sense::hover() };
            let response = ui.interact(rect, egui::Id::new(("kiu-native-back", screen.id)), sense);
            let grow = if response.is_pointer_button_down_on() { 0.97 } else if response.hovered() { 1.06 } else { 1.0 };
            let rect = egui::Rect::from_center_size(rect.center(), rect.size() * grow);
            if response.hovered() {
                let px = rect.width() / tex.size()[0] as f32;
                painter.add(quad(glow.id(), rect.expand(pad * px), 0.0, egui::Color32::from_white_alpha(230)));
            }
            painter.add(quad(tex.id(), rect, 0.0, egui::Color32::WHITE));
            if response.clicked() { out.touch = Some(back_touch(screen.id)); out.back = true; }
        }
    });
    if !ctx.input(|i| i.pointer.any_down()) { live.motion.release(); }
    if out.clicked.is_some() || out.back { live.nav.stop(); }
    out
}

#[cfg(test)]
mod pointer {
    use super::*;
    use crate::pc_menus::screens::MAIN_MENU;

    fn frame(ctx: &egui::Context, art: &Art, live: &mut Live, t: f64, events: Vec<egui::Event>) -> Output {
        let screen = egui::Rect::from_min_size(egui::Pos2::ZERO, egui::vec2(1920.0, 1080.0));
        let input = egui::RawInput { time: Some(t), screen_rect: Some(screen), events, ..Default::default() };
        let mut out = Output::default();
        let _ = ctx.run_ui(input, |ui| { out = show(ui.ctx(), &MAIN_MENU, art, live, screen, &[(0.0, 1.0); 4], true); });
        out
    }

    /// KIU_MENU_PACK=<menu-pc> cargo test -p zakuro --lib native_menu::pointer -- --ignored --nocapture
    #[test]
    #[ignore]
    fn pointing_and_clicking_follow_the_button_shapes() {
        let ctx = egui::Context::default();
        let mut art = None;
        let _ = ctx.run_ui(egui::RawInput::default(), |ui| art = Art::load(ui.ctx(), &MAIN_MENU));
        let Some(art) = art else { println!("no menu art pack"); return };
        let mut live = Live::default();
        let unit = 1080.0 / 240.0;
        let homes = homes(&MAIN_MENU, &art);
        let mut t = 0.0;
        let clock = std::time::Instant::now();
        for k in 0..120 { t += 1.0 / 60.0; let _ = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(egui::pos2(900.0, 100.0 + k as f32))]); }
        println!("buttons and vine: {:.2} ms a frame", clock.elapsed().as_secs_f64() * 1000.0 / 120.0);
        for (i, b) in MAIN_MENU.buttons.iter().enumerate() {
            // a point on the button's own art: the covered point nearest its middle
            let h = homes[i];
            let mut on = None;
            'find: for r in 0..40 {
                for (dx, dy) in [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r)] {
                    let p = egui::pos2(((h[0] + h[2]) / 2.0 + dx as f32) * unit, ((h[1] + h[3]) / 2.0 + dy as f32 * 0.3) * unit);
                    t += 1.0 / 60.0;
                    let out = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(p)]);
                    if out.pointed == Some(b.node) { on = Some((p, out)); break 'find; }
                }
            }
            let (p, out) = on.unwrap_or_else(|| panic!("{} never pointed at", b.name));
            println!("{}: pointed at {:?}, selected at once: {:?}", b.name, p, out.entered);
            // the next frame: still pointed, not entered again
            t += 1.0 / 60.0;
            let out = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(p)]);
            assert_eq!(out.pointed, Some(b.node));
            assert_eq!(out.entered, None);
            // press and release: a click on this button
            t += 1.0 / 60.0;
            let press = |pressed| egui::Event::PointerButton { pos: p, button: egui::PointerButton::Primary, pressed, modifiers: Default::default() };
            let _ = frame(&ctx, &art, &mut live, t, vec![press(true)]);
            t += 1.0 / 60.0;
            let out = frame(&ctx, &art, &mut live, t, vec![press(false)]);
            assert_eq!(out.clicked.map(|c| c.0), Some(b.node), "{} click", b.name);
            // a small wobble while pressed is still a click
            t += 1.0 / 60.0;
            let _ = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(p), press(true)]);
            t += 1.0 / 60.0;
            let _ = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(p + egui::vec2(4.0, 3.0))]);
            t += 1.0 / 60.0;
            let out = frame(&ctx, &art, &mut live, t, vec![egui::PointerButton::Primary].into_iter().map(|_| egui::Event::PointerButton { pos: p + egui::vec2(4.0, 3.0), button: egui::PointerButton::Primary, pressed: false, modifiers: Default::default() }).collect());
            assert_eq!(out.clicked.map(|c| c.0), Some(b.node), "{} click with a wobble", b.name);
            // a real drag pulls the button along and is not a click
            t += 1.0 / 60.0;
            let _ = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(p), press(true)]);
            let mut moved = egui::Pos2::ZERO;
            for k in 1..=20 {
                t += 1.0 / 60.0;
                moved = p + egui::vec2(6.0 * k as f32, 2.0 * k as f32);
                let _ = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(moved)]);
            }
            assert_eq!(live.motion.held(), Some(i), "{} held while dragged", b.name);
            t += 1.0 / 60.0;
            let out = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerButton { pos: moved, button: egui::PointerButton::Primary, pressed: false, modifiers: Default::default() }]);
            assert_eq!(out.clicked, None, "{}: a drag is not a click", b.name);
            for _ in 0..90 { t += 1.0 / 60.0; let _ = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(egui::pos2(1500.0, 500.0))]); }
            let r = live.motion.rect(i, homes[i]);
            println!("  dragged and let go: back within {:.1} units of home", ((r[0] - homes[i][0]).abs()).max((r[1] - homes[i][1]).abs()));
            // the empty top-left corner of its rectangle is not the button
            t += 1.0 / 60.0;
            let corner = egui::pos2(h[0] * unit + 2.0, h[1] * unit + 2.0);
            let out = frame(&ctx, &art, &mut live, t, vec![egui::Event::PointerMoved(corner)]);
            println!("  its rectangle's corner points at {:?}", out.pointed);
            assert_ne!(out.pointed, Some(b.node), "{}: the empty corner counts", b.name);
        }
    }
}
