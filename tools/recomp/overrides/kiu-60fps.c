/* 60 FPS mode (zakuro-core/src/kiu_frame_rate.rs).
 *
 * In 60 fps mode the game updates every vertical blank with its update step
 * (the float at 0x00828E30) set to 1.0 instead of 2.0. Everything the game
 * scales by that step keeps its speed; a RAM comparison of the same replay
 * at 30 and 60 (doc/60FPS_ANALYSIS.md) found 1,694 timers that do and 50
 * counters that count updates instead. Most of those are the per-object
 * "updates alive" counters (+0xB0) that 0x00917618 increments for every
 * object in its manager's three lists, once a game update (its only
 * caller is 0x0092CD88).
 *
 * In 60 fps mode this runs that function every other update, so the
 * counters advance 30 times a second as on the console. At the original
 * rate nothing changes. No game code is reproduced here, only addresses.
 */
#include "overrides.h"

#define KIU_STEP 0x00828E30u /* the update step, 2.0 or 1.0 (60 fps mode) */

RECOMP_OVERRIDE(0x00917618) {
    static unsigned parity;
    if (mem_read32(ctx, KIU_STEP) == 0x3F800000u && (parity++ & 1u)) {
        RETURN_TO(ctx->r[14]);
    }
    CALL(RECOMP_ORIGINAL(0x00917618));
}
