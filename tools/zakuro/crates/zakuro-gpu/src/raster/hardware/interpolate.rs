//! Frame interpolation, the matching half: which draw of the previous frame
//! a draw is, and its transforms halfway between the two.
//!
//! The game keeps its own 30 frames a second; nothing here changes what it
//! runs or what reaches guest memory. Each frame is drawn a second time in
//! host-only images (twin.rs) with each draw's transform uniforms blended
//! halfway back towards that draw's in the frame before, and that picture
//! is shown first, a display refresh before the real one.
//!
//! A draw is known again by what it draws: its vertex program, the vertex
//! arrays, the textures and the buffer it draws into (`key`). Draws with the
//! same key (one model drawn several times) are told apart by the
//! transforms themselves: each takes the closest of the previous frame's
//! not yet taken. Only the uniforms the program uses as matrices blend
//! (shader/transforms.rs); everything else keeps the new frame's values.
//!
//! Where a draw has no match (it just appeared) or one of its matrices
//! turned further than a cut would between two frames, it is drawn as in
//! the new frame. A frame where many did is a cut, and is not shown
//! in-between at all (`cut`).

use std::collections::HashMap;

use crate::shader::transforms::{transform_uniforms, Transforms};
use crate::shader::{ShaderUnit, Vec4, FLOAT_UNIFORMS};

pub(super) type Uniforms = [Vec4; FLOAT_UNIFORMS];

/// how far between the previous frame and the new one the in-between
/// picture is.
const HALFWAY: f32 = 0.5;
/// a row or column of a matrix turning further than this between two
/// frames (cos 60°) is a camera cut or a teleport, not motion.
const TURN_COS: f32 = 0.5;
/// the previous frame's draws with a key looked through for the closest.
const CANDIDATES: usize = 32;

#[derive(Default)]
pub(super) struct Interpolator {
    /// by program fingerprint and entry point.
    transforms: HashMap<(u64, u32), Transforms>,
    previous: HashMap<u64, Vec<Entry>>,
    current: HashMap<u64, Vec<Entry>>,
    /// uniform blocks to reuse.
    spare: Vec<Box<Uniforms>>,
    frame: Counts,
}

struct Entry {
    uniforms: Box<Uniforms>,
    taken: bool,
}

/// the draws of a frame with transforms, those matched in the previous
/// one, and of those the ones that jumped.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub(super) struct Counts {
    pub(super) drawn: u32,
    pub(super) matched: u32,
    pub(super) jumped: u32,
}

impl Interpolator {
    /// the transform uniforms of the program a unit runs.
    pub(super) fn transforms(&mut self, unit: &ShaderUnit) -> Transforms {
        *self
            .transforms
            .entry((unit.fingerprint(), unit.entry_point))
            .or_insert_with(|| {
                transform_uniforms(&unit.program, &unit.descriptors, unit.entry_point)
            })
    }

    /// a draw of the new frame: kept for the next, and its uniforms for the
    /// in-between picture into blended, when there is anything to blend.
    pub(super) fn blend(
        &mut self,
        key: u64,
        transforms: Transforms,
        uniforms: &Uniforms,
        blended: &mut Uniforms,
    ) -> bool {
        if transforms.all == 0 {
            return false;
        }
        self.frame.drawn += 1;
        let mut kept = self
            .spare
            .pop()
            .unwrap_or_else(|| Box::new([[0.0; 4]; FLOAT_UNIFORMS]));
        kept.copy_from_slice(uniforms);
        self.current.entry(key).or_default().push(Entry {
            uniforms: kept,
            taken: false,
        });

        let Some(candidates) = self.previous.get_mut(&key) else {
            return false;
        };
        let closest = candidates
            .iter_mut()
            .filter(|entry| !entry.taken)
            .take(CANDIDATES)
            .min_by(|a, b| {
                distance(transforms.all, &a.uniforms, uniforms).total_cmp(&distance(
                    transforms.all,
                    &b.uniforms,
                    uniforms,
                ))
            });
        let Some(before) = closest else { return false };
        before.taken = true;
        self.frame.matched += 1;
        if jumped(transforms.direct, &before.uniforms, uniforms) {
            self.frame.jumped += 1;
            return false;
        }
        blended.copy_from_slice(uniforms);
        let mut changed = false;
        for i in bits(transforms.all) {
            for c in 0..4 {
                let (from, to) = (before.uniforms[i][c], uniforms[i][c]);
                if from != to {
                    blended[i][c] = from + (to - from) * HALFWAY;
                    changed = true;
                }
            }
        }
        changed
    }

    /// whether so many draws of the frame so far jumped that it is a cut.
    pub(super) fn cut(&self) -> bool {
        let Counts {
            matched, jumped, ..
        } = self.frame;
        jumped > 2 && jumped * 4 > matched
    }

    /// the frame so far.
    pub(super) fn counts(&self) -> Counts {
        self.frame
    }

    /// the new frame is done: it is the one the next is blended with.
    pub(super) fn end_frame(&mut self) {
        for (_, entries) in self.previous.drain() {
            self.spare
                .extend(entries.into_iter().map(|entry| entry.uniforms));
        }
        std::mem::swap(&mut self.previous, &mut self.current);
        self.frame = Counts::default();
    }

    /// nothing to blend with: the next frame starts afresh.
    pub(super) fn forget(&mut self) {
        self.end_frame();
        self.end_frame();
    }
}

/// the bits set in a mask, lowest first.
fn bits(mut mask: u128) -> impl Iterator<Item = usize> {
    std::iter::from_fn(move || {
        (mask != 0).then(|| {
            let bit = mask.trailing_zeros() as usize;
            mask &= mask - 1;
            bit
        })
    })
}

fn distance(mask: u128, a: &Uniforms, b: &Uniforms) -> f32 {
    bits(mask)
        .map(|i| (0..4).map(|c| (a[i][c] - b[i][c]).powi(2)).sum::<f32>())
        .sum()
}

/// whether a matrix row or column the program always reads turned too far
/// between the two frames for motion.
fn jumped(direct: u128, before: &Uniforms, now: &Uniforms) -> bool {
    bits(direct).any(|i| {
        let (a, b) = (&before[i], &now[i]);
        let dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
        let lengths = ((a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
            * (b[0] * b[0] + b[1] * b[1] + b[2] * b[2]))
            .sqrt();
        lengths > 1e-12 && dot < TURN_COS * lengths
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn uniforms(rows: &[(usize, Vec4)]) -> Box<Uniforms> {
        let mut u = Box::new([[0.0; 4]; FLOAT_UNIFORMS]);
        for &(i, v) in rows {
            u[i] = v;
        }
        u
    }

    const MATRIX: Transforms = Transforms {
        all: 0b1111,
        direct: 0b1111,
    };

    /// a model matrix at x, and an atlas cell in c8 that must not blend.
    fn model(x: f32, cell: f32) -> Box<Uniforms> {
        uniforms(&[
            (0, [1.0, 0.0, 0.0, x]),
            (1, [0.0, 1.0, 0.0, 0.0]),
            (2, [0.0, 0.0, 1.0, 0.0]),
            (3, [0.0, 0.0, 0.0, 1.0]),
            (8, [cell, 0.0, 0.0, 0.0]),
        ])
    }

    #[test]
    fn a_moving_model_is_drawn_halfway_and_its_cell_is_not_blended() {
        let mut lerp = Interpolator::default();
        let mut out = model(0.0, 0.0);
        assert!(
            !lerp.blend(7, MATRIX, &model(0.0, 0.0), &mut out),
            "nothing before the first frame"
        );
        lerp.end_frame();
        assert!(lerp.blend(7, MATRIX, &model(4.0, 3.0), &mut out));
        assert_eq!(out[0], [1.0, 0.0, 0.0, 2.0]);
        assert_eq!(out[8], [3.0, 0.0, 0.0, 0.0]);
        assert_eq!(
            lerp.counts(),
            Counts {
                drawn: 1,
                matched: 1,
                jumped: 0
            }
        );
    }

    #[test]
    fn copies_of_a_model_each_blend_with_their_own() {
        let mut lerp = Interpolator::default();
        let mut out = model(0.0, 0.0);
        lerp.blend(7, MATRIX, &model(0.0, 0.0), &mut out);
        lerp.blend(7, MATRIX, &model(100.0, 0.0), &mut out);
        lerp.end_frame();
        // drawn the other way round this time
        lerp.blend(7, MATRIX, &model(102.0, 0.0), &mut out);
        assert_eq!(out[0][3], 101.0);
        lerp.blend(7, MATRIX, &model(2.0, 0.0), &mut out);
        assert_eq!(out[0][3], 1.0);
    }

    #[test]
    fn a_camera_cut_is_not_blended() {
        let mut lerp = Interpolator::default();
        let mut out = model(0.0, 0.0);
        let turned = uniforms(&[
            (0, [0.0, 0.0, 1.0, 0.0]),
            (1, [0.0, 1.0, 0.0, 0.0]),
            (2, [-1.0, 0.0, 0.0, 0.0]),
            (3, [0.0, 0.0, 0.0, 1.0]),
        ]);
        for key in 0..4 {
            lerp.blend(key, MATRIX, &model(0.0, 0.0), &mut out);
        }
        lerp.end_frame();
        for key in 0..4 {
            assert!(!lerp.blend(key, MATRIX, &turned, &mut out));
        }
        assert!(lerp.cut());
    }

    #[test]
    fn a_draw_without_transforms_is_left_out() {
        let mut lerp = Interpolator::default();
        let mut out = model(0.0, 0.0);
        assert!(!lerp.blend(1, Transforms::default(), &model(1.0, 0.0), &mut out));
        assert_eq!(lerp.counts().drawn, 0);
    }
}
