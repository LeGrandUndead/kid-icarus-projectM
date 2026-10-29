//! Which float uniforms of a vertex program are transforms: the rows or
//! columns of the matrices it moves vertices, normals and texture
//! coordinates with.
//!
//! Frame interpolation (see raster/hardware/interpolate.rs) draws an
//! in-between frame by blending a draw's uniforms halfway towards the
//! previous frame's. That is right for a matrix, whose halfway point puts
//! the object halfway, and wrong for most other uniforms: an offset into a
//! texture atlas picking an animation cell or a digit would sample between
//! two cells, a flag or an index would take a value the game never gave
//! it. N64 renderers know which values are matrices because the display
//! list says so; a PICA shader is a program, so the program is read
//! instead.
//!
//! A uniform counts as a transform where the program uses it as a matrix:
//! - an operand of dp3, dp4 or dph, a row of a matrix applied to a vector;
//! - multiplied by one component of another vector repeated (`mul r0,
//!   c0, v0.xxxx`, `mad r0, v0.yyyy, c1, r0`), a column applied to one;
//! - added to such columns applied (`add r0, c3, r0` after the above), the
//!   column a vector's w of 1 would have picked, the translation, which
//!   compilers add on its own rather than multiply by 1. Followed through
//!   the temporary registers in program order.
//!
//! Read relative to an address register (`dp4 r0, c[a0.x + 20], v0`, the
//! bone palettes of skinned models), every uniform from the base on counts,
//! since the index is only known per vertex.
//!
//! A uniform used any other way anywhere in the program (added, compared,
//! moved, an index for mova, multiplied component by component) is left
//! alone even where it is also a transform: it holds something else too.
//! Only code the entry point can reach is read, as several programs share
//! the unit's memory.

use super::isa::{Instruction, OpCode, OperandDescriptor};
use super::{DESCRIPTOR_SIZE, FLOAT_UNIFORMS, PROGRAM_SIZE};

/// The first source register number that is a float uniform.
const UNIFORM_BASE: u32 = 0x20;

/// The float uniforms of a program that are transforms, bit i for uniform i.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Transforms {
    /// all of them, the ones to blend.
    pub all: u128,
    /// those the program reads by number rather than through an address
    /// register: always used, unlike the slots of a palette a model may
    /// leave holding another model's bones.
    pub direct: u128,
}

/// which float uniforms of the program running from entry are transforms,
/// see the module comment.
pub fn transform_uniforms(
    program: &[u32; PROGRAM_SIZE],
    descriptors: &[u32; DESCRIPTOR_SIZE],
    entry: u32,
) -> Transforms {
    let mut transform = 0u128;
    let mut direct = 0u128;
    let mut other = 0u128;
    // temporaries holding columns applied to a vector, bit per register
    let mut columns = 0u16;
    let temporary = |register: u32| (0x10..0x20).contains(&register).then(|| register - 0x10);
    let mut pcs = reachable(program, entry);
    pcs.sort_unstable();
    for pc in pcs {
        let instruction = Instruction(program[pc]);
        let op = instruction.opcode();
        let (uniform, relative, use_, written) = match op {
            OpCode::Mad | OpCode::MadI => {
                let (src1, src2, src3) = instruction.mad_sources();
                let descriptor = OperandDescriptor(
                    descriptors[instruction.mad_descriptor_index() as usize % DESCRIPTOR_SIZE],
                );
                let relative = instruction.mad_address_register_index() != 0;
                let written = (instruction.mad_destination(), false);
                if op == OpCode::Mad {
                    // src1 * src2 + src3, src2 the wide one: a column when
                    // the other factor is one component repeated
                    let broadcast = is_broadcast(descriptor.source(1).0);
                    if broadcast {
                        (src2, relative, Use::Transform, (written.0, src2 >= UNIFORM_BASE))
                    } else {
                        (src2, relative, Use::Other, written)
                    }
                } else {
                    // the wide one is what is added
                    let _ = src1;
                    (src3, relative, Use::Other, written)
                }
            }
            op if op.writes() || matches!(op, OpCode::Mova | OpCode::Cmp) => {
                let (src1, src2) = instruction.sources();
                let descriptor = OperandDescriptor(
                    descriptors[instruction.descriptor_index() as usize % DESCRIPTOR_SIZE],
                );
                let relative = instruction.address_register_index() != 0;
                let wide = if op.is_inverted() { src2 } else { src1 };
                let onto_columns = temporary(src2).is_some_and(|t| columns & 1 << t != 0);
                let (use_, column) = match op {
                    OpCode::Dp3 | OpCode::Dp4 | OpCode::Dph | OpCode::DphI => (Use::Transform, false),
                    // the narrow operand is the second source
                    OpCode::Mul if is_broadcast(descriptor.source(2).0) => (Use::Transform, wide >= UNIFORM_BASE),
                    // a translation added to columns applied, or two
                    // partial sums of them added together
                    OpCode::Add if onto_columns => {
                        let both = temporary(src1).is_some_and(|t| columns & 1 << t != 0);
                        (if wide >= UNIFORM_BASE { Use::Transform } else { Use::Other }, wide >= UNIFORM_BASE || both)
                    }
                    _ => (Use::Other, false),
                };
                let written = if op.writes() { instruction.destination() } else { u32::MAX };
                (wide, relative, use_, (written, column))
            }
            _ => continue,
        };
        let (destination, column) = written;
        if let Some(t) = temporary(destination) {
            if column {
                columns |= 1 << t;
            } else {
                columns &= !(1 << t);
            }
        }
        let Some(index) = uniform
            .checked_sub(UNIFORM_BASE)
            .filter(|&i| (i as usize) < FLOAT_UNIFORMS)
        else {
            continue;
        };
        let bits = if relative {
            from(index)
        } else {
            1u128 << index
        };
        match use_ {
            Use::Transform => {
                transform |= bits;
                if !relative {
                    direct |= bits;
                }
            }
            Use::Other => other |= bits,
        }
    }
    Transforms {
        all: transform & !other,
        direct: direct & !other,
    }
}

enum Use {
    Transform,
    Other,
}

/// uniforms index and up.
fn from(index: u32) -> u128 {
    let all = (1u128 << FLOAT_UNIFORMS) - 1;
    all & !((1u128 << index) - 1)
}

/// one component in every lane, .xxxx and the like.
fn is_broadcast(swizzle: [u8; 4]) -> bool {
    swizzle.iter().all(|&c| c == swizzle[0])
}

/// the instructions running from entry can reach, in no order: straight
/// on until end, both ways at a conditional jump, and the bodies calls run.
fn reachable(program: &[u32; PROGRAM_SIZE], entry: u32) -> Vec<usize> {
    let mut seen = vec![false; PROGRAM_SIZE];
    let mut found = Vec::new();
    // where to start reading, and where a call's body ends
    let mut work = vec![(entry, None::<u32>)];
    while let Some((start, end)) = work.pop() {
        let mut pc = start;
        while (pc as usize) < PROGRAM_SIZE && end.is_none_or(|end| pc < end) && !seen[pc as usize] {
            seen[pc as usize] = true;
            found.push(pc as usize);
            let instruction = Instruction(program[pc as usize]);
            match instruction.opcode() {
                OpCode::End => break,
                OpCode::Call | OpCode::CallC | OpCode::CallU => {
                    let (destination, count) = instruction.flow_target();
                    work.push((destination, Some(destination + count)));
                }
                // if bodies and loops lie straight on, as does the else
                // block after an if's body
                OpCode::JmpC | OpCode::JmpU => work.push((instruction.flow_target().0, end)),
                _ => {}
            }
            pc += 1;
        }
    }
    found
}

#[cfg(test)]
mod tests {
    use super::*;

    const IDENTITY: u32 = 0x1B; // xyzw
    const XXXX: u32 = 0x00;
    const YYYY: u32 = 0x55;

    /// a descriptor with each source's swizzle, writing every component.
    fn descriptor(src1: u32, src2: u32, src3: u32) -> u32 {
        0xF | src1 << 5 | src2 << 14 | src3 << 23
    }

    /// op dst, src1 (wide), src2, descriptor index; address register for src1.
    fn regular(op: u32, dst: u32, src1: u32, src2: u32, desc: u32, address: u32) -> u32 {
        op << 26 | dst << 21 | address << 19 | src1 << 12 | src2 << 7 | desc
    }

    /// mad dst, src1, src2 (wide), src3.
    fn mad(dst: u32, src1: u32, src2: u32, src3: u32, desc: u32) -> u32 {
        0x38 << 26 | dst << 24 | src1 << 17 | src2 << 10 | src3 << 5 | desc
    }

    const END: u32 = 0x22 << 26;
    const DP4: u32 = 0x02;
    const ADD: u32 = 0x00;
    const MUL: u32 = 0x08;
    const MOVA: u32 = 0x12;
    const MOV: u32 = 0x13;
    const CALL: u32 = 0x24;

    fn c(index: u32) -> u32 {
        UNIFORM_BASE + index
    }

    fn run(code: &[u32], descriptors: &[u32]) -> u128 {
        analyse(code, descriptors).all
    }

    fn analyse(code: &[u32], descriptors: &[u32]) -> Transforms {
        let mut program = Box::new([0u32; PROGRAM_SIZE]);
        program[..code.len()].copy_from_slice(code);
        let mut table = Box::new([0u32; DESCRIPTOR_SIZE]);
        table[..descriptors.len()].copy_from_slice(descriptors);
        transform_uniforms(&program, &table, 0)
    }

    #[test]
    fn matrix_rows_are_transforms_and_an_atlas_offset_is_not() {
        let d = [descriptor(IDENTITY, IDENTITY, IDENTITY)];
        let code = [
            // the position through a 4x4 matrix in c0..c3
            regular(DP4, 0, c(0), 0, 0, 0),
            regular(DP4, 0, c(1), 0, 0, 0),
            regular(DP4, 0, c(2), 0, 0, 0),
            regular(DP4, 0, c(3), 0, 0, 0),
            // texture coordinates plus the cell an animation is on, c8
            regular(ADD, 2, c(8), 2, 0, 0),
            END,
        ];
        assert_eq!(run(&code, &d), 0b1111);
    }

    #[test]
    fn columns_times_a_repeated_component_are_transforms() {
        let d = [
            descriptor(IDENTITY, XXXX, IDENTITY),
            descriptor(YYYY, IDENTITY, IDENTITY),
            descriptor(IDENTITY, IDENTITY, IDENTITY),
        ];
        let code = [
            // mul r0, c4, v0.xxxx
            regular(MUL, 0x10, c(4), 0, 0, 0),
            // mad r0, v0.yyyy, c5, r0
            mad(0x10, 0, c(5), 0x10, 1),
            // mul r1, c6, v1: a color, component by component
            regular(MUL, 0x11, c(6), 1, 2, 0),
            END,
        ];
        assert_eq!(run(&code, &d), 1 << 4 | 1 << 5);
    }

    #[test]
    fn a_translation_added_to_columns_is_a_transform_and_an_offset_to_a_texcoord_is_not() {
        let d = [
            descriptor(IDENTITY, XXXX, IDENTITY),
            descriptor(YYYY, IDENTITY, IDENTITY),
            descriptor(IDENTITY, IDENTITY, IDENTITY),
        ];
        let code = [
            // r0 = c0 * v0.x + c1 * v0.y, then + c3: a 4x4 with w = 1
            regular(MUL, 0x10, c(0), 0, 0, 0),
            mad(0x10, 0, c(1), 0x10, 1),
            regular(ADD, 0x10, c(3), 0x10, 2, 0),
            regular(MOV, 0, 0x10, 0, 2, 0),
            // r1 = v2 + c8: an atlas cell offset on a raw texture coordinate
            regular(ADD, 0x11, c(8), 2, 2, 0),
            // r0 rewritten by something else: c9 added to it is no translation
            regular(MOV, 0x10, 1, 0, 2, 0),
            regular(ADD, 0x10, c(9), 0x10, 2, 0),
            END,
        ];
        assert_eq!(run(&code, &d), 1 << 0 | 1 << 1 | 1 << 3);
    }

    #[test]
    fn a_bone_palette_counts_from_its_base() {
        let d = [descriptor(IDENTITY, IDENTITY, IDENTITY)];
        let code = [
            // mova a0.x, v4 then dp4 r0, c[a0.x + 20], v0
            regular(MOVA, 0, 4, 0, 0, 0),
            regular(DP4, 0x10, c(20), 0, 0, 1),
            // c90 also an index for mova elsewhere
            regular(MOVA, 0, c(90), 0, 0, 0),
            END,
        ];
        let found = analyse(&code, &d);
        let mask = found.all;
        assert!(mask & (1 << 20) != 0 && mask & (1 << 89) != 0);
        assert!(mask & (1 << 19) == 0 && mask & (1 << 90) == 0);
        assert_eq!(found.direct, 0);
    }

    #[test]
    fn a_uniform_with_another_use_is_left_alone() {
        let d = [descriptor(IDENTITY, IDENTITY, IDENTITY)];
        let code = [
            regular(DP4, 0, c(0), 0, 0, 0),
            regular(MOV, 0x10, c(0), 0, 0, 0),
            END,
        ];
        assert_eq!(run(&code, &d), 0);
    }

    #[test]
    fn only_code_the_entry_reaches_counts() {
        let d = [descriptor(IDENTITY, IDENTITY, IDENTITY)];
        let call = |destination: u32, count: u32| CALL << 26 | destination << 10 | count;
        let code = [
            call(4, 2),
            END,
            // never run: another program's add of c0
            regular(ADD, 0, c(0), 0, 0, 0),
            END,
            // the subroutine
            regular(DP4, 0, c(0), 0, 0, 0),
            regular(DP4, 0, c(1), 0, 0, 0),
        ];
        assert_eq!(run(&code, &d), 0b11);
    }
}
