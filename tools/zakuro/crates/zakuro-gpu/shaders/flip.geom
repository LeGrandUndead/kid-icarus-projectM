#version 450

// passes lit triangles through unchanged except for their quaternions. q and
// -q are the same orientation, but the rasterizer interpolating from one to
// the other goes through nothing like either, which shows as bands of wrong
// lighting across a surface (the PICA200 puts the three on one side first,
// as the software rasterizer does). only pipelines with fragment lighting on
// run it.

layout(triangles) in;
layout(triangle_strip, max_vertices = 3) out;

layout(location = 0) in vec4 in_color[];
layout(location = 1) in vec4 in_texcoords01[];
layout(location = 2) in vec2 in_texcoord2[];
layout(location = 3) noperspective in float in_depth[];
layout(location = 4) in vec4 in_quaternion[];
layout(location = 5) in vec3 in_view[];
layout(location = 6) in float in_texcoord0_w[];

layout(location = 0) out vec4 out_color;
layout(location = 1) out vec4 out_texcoords01;
layout(location = 2) out vec2 out_texcoord2;
layout(location = 3) noperspective out float out_depth;
layout(location = 4) out vec4 out_quaternion;
layout(location = 5) out vec3 out_view;
layout(location = 6) out float out_texcoord0_w;

void main() {
    vec4 first = in_quaternion[0];
    for (int i = 0; i < 3; i++) {
        gl_Position = gl_in[i].gl_Position;
        out_color = in_color[i];
        out_texcoords01 = in_texcoords01[i];
        out_texcoord2 = in_texcoord2[i];
        out_depth = in_depth[i];
        vec4 q = in_quaternion[i];
        out_quaternion = dot(q, first) < 0.0 ? -q : q;
        out_view = in_view[i];
        out_texcoord0_w = in_texcoord0_w[i];
        EmitVertex();
    }
    EndPrimitive();
}
