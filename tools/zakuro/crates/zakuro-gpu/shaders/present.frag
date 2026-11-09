#version 450
layout(location = 0) in vec2 uv;
layout(location = 0) out vec4 colour;
layout(set = 0, binding = 0) uniform sampler2D screen;
// where the part of the screen drawn lies in the image, its corner and size
// as texture coordinates, then its corners inset by half a texel, which
// samples keep within so filtering takes nothing from around it.
// then how far in from its left, top, right and bottom edges it fades into
// the window's background (zero: a solid edge, the usual case).
// mode.x: the picture carries coverage in its alpha, premultiplied (a menu's
// lower screen drawn for laying over the upper one); otherwise it is opaque.
// mode.y: how much of it shows (1; less while a menu layout fades out).
// the output is premultiplied either way, blended ONE, ONE_MINUS_SRC_ALPHA.
layout(push_constant) uniform Crop {
    vec4 area;
    vec4 bounds;
    vec4 feather;
    vec4 mode;
} crop;
float ramp(float d, float width) {
    return width <= 0.0 ? 1.0 : smoothstep(0.0, width, d);
}
float fade() {
    return ramp(uv.x, crop.feather.x) * ramp(uv.y, crop.feather.y)
        * ramp(1.0 - uv.x, crop.feather.z) * ramp(1.0 - uv.y, crop.feather.w);
}
vec4 finish(vec4 texel) {
    float f = fade() * crop.mode.y;
    return crop.mode.x > 0.5 ? texel * f : vec4(texel.rgb * f, f);
}
// a screen drawn bigger than the window shows it is averaged over every
// texel a window pixel covers, which smooths its edges the way drawing at a
// higher resolution should. one drawn smaller is filtered as usual.
void main() {
    vec2 at = crop.area.xy + uv * crop.area.zw;
    vec2 size = vec2(textureSize(screen, 0));
    vec2 covered = fwidth(at) * size;
    if (max(covered.x, covered.y) <= 1.0) {
        colour = finish(texture(screen, clamp(at, crop.bounds.xy, crop.bounds.zw)));
        return;
    }
    // each sample is bilinear, so it already averages its four texels
    ivec2 taps = ivec2(clamp(ceil(covered), 1.0, 4.0));
    vec4 sum = vec4(0.0);
    for (int y = 0; y < taps.y; y++) {
        for (int x = 0; x < taps.x; x++) {
            vec2 offset = ((vec2(x, y) + 0.5) / vec2(taps) - 0.5) * covered / size;
            sum += texture(screen, clamp(at + offset, crop.bounds.xy, crop.bounds.zw));
        }
    }
    colour = finish(sum / float(taps.x * taps.y));
}
