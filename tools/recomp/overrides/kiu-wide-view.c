/* PC wide view: the game's own top-screen camera, widened
 * (zakuro-core/src/kiu_wide_view.rs, doc/WIDE_VIEW.md).
 *
 * The game's cameras (Project Sora's psl library over Nintendo's graphics
 * library) keep their lens in a perspective "projection updater": near
 * +0x08, far +0x0C, field of view +0x10 (radians), aspect +0x14, 5:3 for
 * the top screen. Three functions turn that lens into what the rest of the
 * game uses:
 *
 *   0x00B4F89C  updater method 2: the projection matrix the shaders get
 *   0x00B4F948  updater method 3: the culling frustum's planes
 *   0x0090DC70  the camera's lens cache, tan(fov/2) +0x114, aspect +0x118,
 *               fov +0x11C, read by the game's screen/world conversions
 *
 * Each runs here as the game wrote it, on a widened lens when the runtime
 * asks for one: the tangent of half the field of view times a lens factor
 * (the "Gameplay view" zoom), the aspect times an aspect factor (16/15 for
 * the 16:9 picture). Drawing, culling, aiming and markers then all agree
 * on what is on screen. The game's own lens is never changed, so its
 * camera animations go on from the values they set.
 *
 * The runtime writes the factors to spare bytes past the end of the game's
 * data (the data and zeroed data end at 0x00F35D28; the page runs to
 * 0x00F36000 and nothing uses the rest) and sees from the count at +0xC
 * that this library widens the camera, so it stops widening the picture
 * itself. Without the runtime's word nothing changes. No game code is
 * reproduced here, only addresses and the layout of the lens.
 */
#include <math.h>
#include <string.h>
#include "overrides.h"

#define KIU_VIEW        0x00F35F00u /* written by the runtime */
#define KIU_VIEW_MAGIC  0x5755494Bu /* "KIUW": factors below are valid */
#define KIU_VIEW_LENS   (KIU_VIEW + 0x4) /* tan(fov/2) factor, 1 = original */
#define KIU_VIEW_ASPECT (KIU_VIEW + 0x8) /* aspect factor, 1 = original */
#define KIU_VIEW_COUNT  (KIU_VIEW + 0xC) /* projections widened, for the runtime */
#define KIU_VIEW_COPY   (KIU_VIEW + 0x40) /* the widened lens the methods read */

#define LENS_FOV    0x10u
#define LENS_ASPECT 0x14u
#define LENS_SIZE   0x18u

static float kiu_float(uint32_t bits) { float value; memcpy(&value, &bits, 4); return value; }
static uint32_t kiu_bits(float value) { uint32_t bits; memcpy(&bits, &value, 4); return bits; }

/* the factors for a lens of this aspect: only the top screen's (5:3; the
   game briefly uses 1.6656 in camera transitions), only when asked for. */
static int kiu_view(Context *ctx, float aspect, float *lens, float *wide) {
    if (mem_read32(ctx, KIU_VIEW) != KIU_VIEW_MAGIC) return 0;
    if (!(fabsf(aspect - 5.0f / 3.0f) < 0.01f)) return 0;
    *lens = kiu_float(mem_read32(ctx, KIU_VIEW_LENS));
    *wide = kiu_float(mem_read32(ctx, KIU_VIEW_ASPECT));
    if (!(*lens >= 1.0f && *lens <= 2.0f) || !(*wide >= 1.0f && *wide <= 1.5f)) return 0;
    return *lens != 1.0f || *wide != 1.0f;
}

/* points r1 (the updater) at a widened copy of its lens, for a method that
   reads only the lens. 1 when it did. */
static int kiu_widened_lens(Context *ctx) {
    uint32_t updater = ctx->r[1];
    float fov = kiu_float(mem_read32(ctx, updater + LENS_FOV));
    float aspect = kiu_float(mem_read32(ctx, updater + LENS_ASPECT));
    float lens, wide;
    if (!(fov > 0.0f && fov < 3.0f) || !kiu_view(ctx, aspect, &lens, &wide)) return 0;
    for (uint32_t offset = 0; offset < LENS_SIZE; offset += 4)
        mem_write32(ctx, KIU_VIEW_COPY + offset, mem_read32(ctx, updater + offset));
    mem_write32(ctx, KIU_VIEW_COPY + LENS_FOV, kiu_bits(2.0f * atanf(tanf(0.5f * fov) * lens)));
    mem_write32(ctx, KIU_VIEW_COPY + LENS_ASPECT, kiu_bits(aspect * wide));
    ctx->r[1] = KIU_VIEW_COPY;
    return 1;
}

/* the projection matrix (r0: where it goes, r1: the updater) */
RECOMP_OVERRIDE(0x00B4F89C) {
    if (kiu_widened_lens(ctx))
        mem_write32(ctx, KIU_VIEW_COUNT, mem_read32(ctx, KIU_VIEW_COUNT) + 1);
    CALL(RECOMP_ORIGINAL(0x00B4F89C));
}

/* the culling frustum (r0: where it goes, r1: the updater, s0: a margin) */
RECOMP_OVERRIDE(0x00B4F948) {
    kiu_widened_lens(ctx);
    CALL(RECOMP_ORIGINAL(0x00B4F948));
}

/* the camera's lens cache (r0: the camera, its updater at +4). Only a
   perspective updater's (type 1) is widened; the others are read from
   the projection matrix. */
RECOMP_OVERRIDE(0x0090DC70) {
    uint32_t camera = ctx->r[0];
    CALL(RECOMP_ORIGINAL(0x0090DC70));
    uint32_t updater = mem_read32(ctx, camera + 4);
    if (!updater || (mem_read8(ctx, updater + 4) & 0xFu) != 1u) RETURN();
    float aspect = kiu_float(mem_read32(ctx, camera + 0x118)), lens, wide;
    if (!kiu_view(ctx, aspect, &lens, &wide)) RETURN();
    float tangent = kiu_float(mem_read32(ctx, camera + 0x114)) * lens;
    mem_write32(ctx, camera + 0x114, kiu_bits(tangent));
    mem_write32(ctx, camera + 0x118, kiu_bits(aspect * wide));
    mem_write32(ctx, camera + 0x11C, kiu_bits(2.0f * atanf(tangent)));
    RETURN();
}
