//! Frame interpolation, the drawing half: the twin world.
//!
//! With interpolation on, every surface the game draws into has a twin, an
//! image of the same size that only the host uses. Each draw is recorded a
//! second time into the twins, the same in every way but for its transform
//! uniforms, blended halfway towards the previous frame (interpolate.rs),
//! and the textures it samples that were drawn this frame, which come from
//! the twins too. What else changes a surface happens to its twin as well:
//! a fill clears both, an upload from guest memory is copied across, a
//! display transfer runs again from twin to twin. The twin of the buffer a
//! screen shows then holds the frame as it was halfway between the previous
//! one and this, which is shown first (see System::gpu_screen).
//!
//! Nothing in the twin world is ever written to guest memory or read by the
//! CPU, so the game cannot tell it exists: its logic still runs at 30
//! frames a second exactly as on the console.
//!
//! The twin draws of a rendering are recorded when it ends, in a rendering
//! of their own (end_rendering), which keeps the order of everything that
//! reads and writes each twin the same as for the surface itself: the real
//! world's barriers order both.

use std::collections::HashMap;

use ash::vk;

use super::interpolate::{Interpolator, Outcome, Uniforms};
use super::report::Report;
use super::{
    Draw, DrawCommand, Geometry, Hardware, Image, Inputs, Kind, Shading, COLOR_FORMAT,
    DEPTH_FORMAT, SHADING_SIZE,
};
use crate::raster::DrawnTexture;
use crate::shader::transforms::Transforms;
use crate::shader::FLOAT_UNIFORMS;
use crate::ScreenRef;

#[derive(Default)]
pub(super) struct Twins {
    on: bool,
    /// by surface index; surfaces stay where they are until the end.
    surfaces: Vec<Option<Twin>>,
    /// textures copied from twins, as Hardware::copies from surfaces.
    copies: HashMap<DrawnTexture, TwinCopy>,
    /// the twin draws of the rendering going on.
    pending: Vec<DrawCommand>,
    pub(super) interpolator: Interpolator,
    /// frames ended with interpolation on.
    frames: u64,
    /// what the frames since the last log line came to.
    period: Period,
    /// every draw of a few frames written out, see report.rs.
    report: Report,
}

/// totals over the frames between two log lines.
#[derive(Default)]
struct Period {
    frames: u32,
    drawn: u32,
    matched: u32,
    jumped: u32,
    cuts: u32,
    /// twins overwritten by their surface, as guest memory changed under it:
    /// the in-between picture of that surface is the real one then.
    reloads: u32,
    /// in-between pictures asked for and shown, and why the rest were not:
    /// the screen's buffer has no surface or twin, its twin is of another
    /// transfer, or the frame was a cut.
    asked: u32,
    shown: u32,
    no_twin: u32,
    stale: u32,
    cut: u32,
}

struct Twin {
    image: Image,
    upright: Option<TwinUpright>,
}

/// a twin turned upright for the presenter, as Surface::upright.
struct TwinUpright {
    image: Image,
    batch: u64,
    /// the frame was not a cut, so this is worth showing.
    shown: bool,
}

struct TwinCopy {
    image: Image,
    surface: usize,
    generation: u64,
    used: u64,
}

impl Twins {
    pub(super) fn on(&self) -> bool {
        self.on
    }
}

impl Hardware {
    /// draws every frame a second time halfway towards the one before,
    /// from now on, or stops. only a presenter sharing the device can show
    /// the pictures.
    pub(crate) fn set_interpolation(&mut self, on: bool) {
        let on = on && self.direct;
        if on && !self.twins.on {
            // the twins and the previous frame are from before: start over
            self.twins.interpolator.forget();
            let surfaces = std::mem::take(&mut self.twins.surfaces);
            let copies = std::mem::take(&mut self.twins.copies);
            self.retire_twins(surfaces, copies);
        }
        self.twins.on = on;
    }

    pub(crate) fn interpolating(&self) -> bool {
        self.twins.on
    }

    /// the game swapped the top screen's buffers: the frame drawn since the
    /// last swap is the one the next is blended with.
    pub(crate) fn end_frame(&mut self) {
        if self.twins.on {
            let counts = self.twins.interpolator.counts();
            let cut = self.twins.interpolator.cut();
            let period = &mut self.twins.period;
            period.frames += 1;
            period.drawn += counts.drawn;
            period.matched += counts.matched;
            period.jumped += counts.jumped;
            period.cuts += cut as u32;
            self.twins.frames += 1;
            if self.twins.frames % 600 == 0 {
                let p = std::mem::take(&mut self.twins.period);
                let per = |n: u32| n as f32 / p.frames.max(1) as f32;
                log::info!(
                    "in-between frames, last {}: {:.0} draws with transforms each, {:.0} blended, {:.1} jumped, {} cuts, {:.1} twins reloaded from memory; shown {} of {} asked ({} no twin, {} of another transfer, {} cuts)",
                    p.frames,
                    per(p.drawn),
                    per(p.matched - p.jumped),
                    per(p.jumped),
                    p.cuts,
                    per(p.reloads),
                    p.shown,
                    p.asked,
                    p.no_twin,
                    p.stale,
                    p.cut
                );
            }
            self.twins.interpolator.end_frame();
            let frames = self.twins.frames;
            self.twins.report.end_frame(frames);
        }
        let wanted = crate::interpolation::wanted();
        if wanted != self.twins.on {
            self.set_interpolation(wanted);
            log::info!(
                "in-between frames {}",
                if self.twins.on { "on (60 FPS)" } else { "off" }
            );
        }
    }

    fn twin(&self, index: usize) -> Option<&Twin> {
        self.twins.surfaces.get(index)?.as_ref()
    }

    /// a surface's twin, made as a copy of the surface when it has none,
    /// before what is about to change the surface. outside rendering.
    pub(super) fn twin_ensure(&mut self, index: usize) -> Result<(), String> {
        if self.twin(index).is_some() {
            return Ok(());
        }
        let surface = &self.surfaces[index];
        let (width, height, kind) = (
            surface.width * self.scale,
            surface.height * self.scale,
            surface.kind,
        );
        let (format, usage, aspect) = match kind {
            Kind::Color(_) => (
                COLOR_FORMAT,
                vk::ImageUsageFlags::COLOR_ATTACHMENT | vk::ImageUsageFlags::STORAGE,
                vk::ImageAspectFlags::COLOR,
            ),
            Kind::Depth(_) => (
                DEPTH_FORMAT,
                vk::ImageUsageFlags::DEPTH_STENCIL_ATTACHMENT,
                vk::ImageAspectFlags::DEPTH | vk::ImageAspectFlags::STENCIL,
            ),
        };
        let usage = usage | vk::ImageUsageFlags::TRANSFER_SRC | vk::ImageUsageFlags::TRANSFER_DST;
        let image = self.image(width, height, format, usage, aspect)?;
        if self.twins.surfaces.len() <= index {
            self.twins.surfaces.resize_with(index + 1, || None);
        }
        let target = image.image;
        self.twins.surfaces[index] = Some(Twin {
            image,
            upright: None,
        });
        self.copy_to_twin(index, target, (width, height), aspect);
        Ok(())
    }

    /// the surface's image as it is now into its twin, between barriers.
    fn copy_to_twin(
        &mut self,
        index: usize,
        twin: vk::Image,
        (width, height): (u32, u32),
        aspect: vk::ImageAspectFlags,
    ) {
        let layers = vk::ImageSubresourceLayers::default()
            .aspect_mask(aspect)
            .layer_count(1);
        let region = [vk::ImageCopy::default()
            .src_subresource(layers)
            .dst_subresource(layers)
            .extent(vk::Extent3D {
                width,
                height,
                depth: 1,
            })];
        self.unfenced = true;
        self.barrier();
        // SAFETY: recording, outside rendering, between two images of the
        // same format and size in the general layout made for transfers
        unsafe {
            self.device.cmd_copy_image(
                self.commands,
                self.surfaces[index].image.image,
                vk::ImageLayout::GENERAL,
                twin,
                vk::ImageLayout::GENERAL,
                &region,
            )
        };
        self.unfenced = true;
        self.barrier();
    }

    /// guest memory's bytes went up into a surface: its twin gets them too.
    pub(super) fn twin_uploaded(&mut self, index: usize) {
        let Some(twin) = self.twin(index) else { return };
        let target = twin.image.image;
        self.twins.period.reloads += 1;
        let surface = &self.surfaces[index];
        let size = (surface.width * self.scale, surface.height * self.scale);
        let aspect = match surface.kind {
            Kind::Color(_) => vk::ImageAspectFlags::COLOR,
            Kind::Depth(_) => vk::ImageAspectFlags::DEPTH | vk::ImageAspectFlags::STENCIL,
        };
        self.copy_to_twin(index, target, size, aspect);
    }

    /// the image a fill of a whole surface clears in its twin too.
    pub(super) fn twin_image(&self, index: usize) -> Option<vk::Image> {
        self.twin(index).map(|twin| twin.image.image)
    }

    /// the view a fill of a surface clears in its twin too.
    pub(super) fn twin_view(&self, index: usize) -> Option<vk::ImageView> {
        self.twin(index).map(|twin| twin.image.view)
    }

    /// a draw recorded into the surfaces, for the twins: its transforms
    /// blended, and drawn textures from the twins (views, from
    /// twin_texture). recorded once the rendering ends.
    pub(super) fn twin_draw(
        &mut self,
        draw: &Draw,
        mut command: DrawCommand,
        views: [Option<vk::ImageView>; 3],
    ) -> Result<(), String> {
        for (image, view) in command.images.iter_mut().zip(views) {
            if let Some(view) = view {
                image.image_view = view;
            }
        }
        let mut seen = (0, Transforms::default());
        if let (Geometry::Shaded(shading), Some(vertex)) = (draw.geometry, command.vertex.as_mut())
        {
            let transforms = self.twins.interpolator.transforms(shading.unit);
            let key = draw_key(draw, shading);
            seen = (key, transforms);
            if transforms.all != 0 {
                let mut blended: Uniforms = [[0.0; 4]; FLOAT_UNIFORMS];
                if self.twins.interpolator.blend(
                    key,
                    transforms,
                    &shading.unit.float_uniforms,
                    &mut blended,
                ) {
                    // the draw's block of what the vertex program reads, with
                    // the blended uniforms over the float uniforms it starts with
                    let real = vertex[1].offset;
                    let offset = self.stage(SHADING_SIZE, self.storage_alignment)?;
                    let block = self.ring(real, SHADING_SIZE).to_vec();
                    let staging = self.ring(offset, SHADING_SIZE);
                    staging.copy_from_slice(&block);
                    for (out, value) in staging
                        .as_chunks_mut::<4>()
                        .0
                        .iter_mut()
                        .zip(blended.iter().flatten())
                    {
                        *out = value.to_le_bytes();
                    }
                    vertex[1] = vertex[1].offset(offset);
                }
            }
        }
        if self.twins.report.on() {
            let outcome = if seen.1.all != 0 { self.twins.interpolator.outcome() } else { Outcome::default() };
            self.twins.report.draw(draw, seen.0, seen.1, outcome);
        }
        self.twins.pending.push(command);
        Ok(())
    }

    /// records the twin draws of the rendering that just ended into the
    /// twins of its surfaces, see the module comment.
    pub(super) fn twin_pass(&mut self, color: usize, depth: Option<usize>) {
        let mut pending = std::mem::take(&mut self.twins.pending);
        if pending.is_empty() {
            self.twins.pending = pending;
            return;
        }
        // both made as the rendering began, see begin_rendering
        let color_view = self.twin_view(color);
        let depth_view = depth.map(|d| self.twin_view(d));
        let views = match (color_view, depth_view) {
            (Some(color), None) => Some((color, None)),
            (Some(color), Some(Some(depth))) => Some((color, Some(depth))),
            _ => None,
        };
        if let Some((color_view, depth_view)) = views {
            let surface = &self.surfaces[color];
            let size = (surface.width * self.scale, surface.height * self.scale);
            self.render_into(size, color_view, depth_view);
            for command in &pending {
                self.issue(command);
            }
            // SAFETY: rendering was begun just above
            unsafe { self.device.cmd_end_rendering(self.commands) };
        }
        pending.clear();
        self.twins.pending = pending;
    }

    /// a texture drawn this frame, from the twin of the surface it is part
    /// of, copied the same way and as often as copy_texture copies it from
    /// the surface. none when the surface has no twin, the texture is the
    /// same in both worlds then.
    pub(super) fn twin_texture(
        &mut self,
        texture: &DrawnTexture,
    ) -> Result<Option<vk::ImageView>, String> {
        let Some((source, row)) = self.texture_source(texture) else {
            return Ok(None);
        };
        let Some(twin) = self.twin_view(source) else {
            return Ok(None);
        };
        let generation = self.surfaces[source].generation;
        let batch = self.batch;
        if let Some(copy) = self.twins.copies.get_mut(texture) {
            if copy.surface == source && copy.generation == generation {
                copy.used = batch;
                return Ok(Some(copy.image.view));
            }
        }
        let n = self.copy_scale(texture, source);
        if !self.twins.copies.contains_key(texture) {
            let usage = vk::ImageUsageFlags::SAMPLED | vk::ImageUsageFlags::STORAGE;
            let image = self.image(
                texture.width * n,
                texture.height * n,
                COLOR_FORMAT,
                usage,
                vk::ImageAspectFlags::COLOR,
            )?;
            self.twins.copies.insert(
                *texture,
                TwinCopy {
                    image,
                    surface: source,
                    generation,
                    used: batch,
                },
            );
        }
        let view = self.twins.copies[texture].image.view;
        let twin_image = self
            .twin(source)
            .map(|twin| twin.image.image)
            .ok_or("a twin went")?;
        self.copy_texture_from(source, (twin, twin_image), row, view, texture, n)?;
        if let Some(copy) = self.twins.copies.get_mut(texture) {
            copy.surface = source;
            copy.generation = generation;
            copy.used = batch;
        }
        Ok(Some(view))
    }

    /// a display transfer from a surface into a screen's buffer, again from
    /// the twin, into the twin, and that turned upright for the presenter.
    pub(super) fn twin_transfer(
        &mut self,
        source: usize,
        target: usize,
        constants: [i32; 11],
        size: (u32, u32),
    ) -> Result<(), String> {
        // made after the transfer, as the transfer writes all of it the copy
        // has that matters
        self.twin_ensure(target)?;
        let from = self
            .twin_view(source)
            .unwrap_or(self.surfaces[source].image.view);
        let into = self.twin_view(target).ok_or("a twin went")?;
        self.dispatch_transfer((from, into), constants, size)?;
        // a row of the surface is a column of the screen
        let (width, height) = (
            self.surfaces[target].height * self.scale,
            self.surfaces[target].width * self.scale,
        );
        if self.twin(target).is_some_and(|twin| twin.upright.is_none()) {
            let usage = vk::ImageUsageFlags::STORAGE | vk::ImageUsageFlags::SAMPLED;
            let image = self.image(
                width,
                height,
                COLOR_FORMAT,
                usage,
                vk::ImageAspectFlags::COLOR,
            )?;
            if let Some(Some(twin)) = self.twins.surfaces.get_mut(target) {
                twin.upright = Some(TwinUpright {
                    image,
                    batch: 0,
                    shown: false,
                });
            }
        }
        let shown = !self.twins.interpolator.cut();
        let batch = self.batch;
        let Some(Some(twin)) = self.twins.surfaces.get_mut(target) else {
            return Err("a twin went".into());
        };
        let Some(upright) = twin.upright.as_mut() else {
            return Err("a twin went".into());
        };
        upright.batch = batch;
        upright.shown = shown;
        let target_view = upright.image.view;
        self.record_upright(into, target_view, (width, height))
    }

    /// the in-between picture of a screen, for a presenter sharing the
    /// device, when the frame that screen shows has one worth showing.
    pub(crate) fn twin_screen_image(
        &mut self,
        screen: ScreenRef,
    ) -> Result<Option<crate::GpuScreen>, String> {
        if !self.twins.on {
            return Ok(None);
        }
        self.twins.period.asked += 1;
        let upright = self
            .screen_surface(screen)
            .and_then(|index| self.twin(index))
            .and_then(|twin| twin.upright.as_ref());
        let Some(upright) = upright else {
            self.twins.period.no_twin += 1;
            return Ok(None);
        };
        if upright.batch != screen.batch {
            self.twins.period.stale += 1;
            return Ok(None);
        }
        if !upright.shown {
            self.twins.period.cut += 1;
            return Ok(None);
        }
        let view = upright.image.view;
        self.twins.period.shown += 1;
        if screen.batch >= self.batch {
            self.submit()?;
        }
        Ok(Some(self.screen_area(view, screen)))
    }

    /// the in-between picture of a screen read back, and its width.
    #[cfg(test)]
    pub(crate) fn twin_upright_pixels(
        &mut self,
        screen: ScreenRef,
    ) -> Result<(Vec<u8>, u32), String> {
        let index = self.screen_surface(screen).ok_or("no surface")?;
        let image = self
            .twin(index)
            .and_then(|twin| twin.upright.as_ref())
            .ok_or("nothing in between")?
            .image
            .image;
        self.upright_image_pixels(image, screen)
    }

    /// textures copied from twins nobody drew with for a while go, as
    /// submit does for those from surfaces.
    pub(super) fn retire_twin_copies(&mut self) {
        let batch = self.batch;
        let stale: Vec<DrawnTexture> = self
            .twins
            .copies
            .iter()
            .filter(|(_, c)| batch - c.used > 600)
            .map(|(&k, _)| k)
            .collect();
        for key in stale {
            if let Some(copy) = self.twins.copies.remove(&key) {
                self.destroy_image(&copy.image);
            }
        }
    }

    /// destroys the twins and their copies, once the GPU is done with them.
    fn retire_twins(
        &mut self,
        surfaces: Vec<Option<Twin>>,
        copies: HashMap<DrawnTexture, TwinCopy>,
    ) {
        if surfaces.iter().all(Option::is_none) && copies.is_empty() {
            return;
        }
        // SAFETY: waits for the GPU before the images go
        unsafe {
            let _ = self.device.device_wait_idle();
        }
        for twin in surfaces.into_iter().flatten() {
            self.destroy_image(&twin.image);
            if let Some(upright) = &twin.upright {
                self.destroy_image(&upright.image);
            }
        }
        for copy in copies.into_values() {
            self.destroy_image(&copy.image);
        }
    }

    /// everything the twin world holds, for Drop, the GPU idle already.
    pub(super) fn destroy_twins(&mut self) {
        let surfaces = std::mem::take(&mut self.twins.surfaces);
        let copies = std::mem::take(&mut self.twins.copies);
        for twin in surfaces.into_iter().flatten() {
            self.destroy_image(&twin.image);
            if let Some(upright) = &twin.upright {
                self.destroy_image(&upright.image);
            }
        }
        for copy in copies.into_values() {
            self.destroy_image(&copy.image);
        }
    }
}

/// what a draw draws, the same for the same draw from one frame to the
/// next: its program, its vertex arrays, its textures and the buffers it
/// draws into.
fn draw_key(draw: &Draw, shading: &Shading) -> u64 {
    let mix =
        |hash: u64, word: u64| (hash.rotate_left(5) ^ word).wrapping_mul(0x517C_C1B7_2722_0A95);
    let mut hash = mix(shading.unit.fingerprint(), shading.unit.entry_point as u64);
    hash = mix(hash, draw.target as u64);
    hash = mix(hash, draw.depth.map_or(0, |(addr, _)| addr as u64));
    match shading.inputs {
        Inputs::Raw(raw) => {
            for &(addr, len) in &raw.arrays {
                hash = mix(hash, (addr as u64) << 32 | len as u64);
            }
        }
        Inputs::Decoded(decoded) => hash = mix(hash, decoded.len() as u64),
    }
    for bound in draw.textures {
        // by where it is, not what it holds: an animated texture is still
        // the same object's
        let texture = bound.as_ref().map_or(0, |b| b.addr as u64 | 1 << 32);
        hash = mix(hash, texture);
    }
    hash
}
