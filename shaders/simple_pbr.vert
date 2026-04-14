#version 330 core

uniform mat4 p3d_ProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ViewMatrix;
uniform mat3 p3d_NormalMatrix;

uniform int inf_count;
uniform vec4 inf_pos[16];
uniform vec4 inf_param[16];
uniform float bend_weight;


in vec4 p3d_Vertex;
in vec4 p3d_Color;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;

out vec3 v_normal;
out vec3 v_world_normal;
out vec2 v_texcoord;
out vec3 v_world_pos;
out float v_height;
out vec4 v_color;

void main() {
    vec4 world_pos  = p3d_ModelMatrix * p3d_Vertex;

    vec3 total_bend = vec3(0.0);
    if (bend_weight > 0.0) {
        float height_factor = clamp(p3d_Vertex.z * 0.3, 0.0, 1.0) * bend_weight;
        for(int i = 0; i < 16; i++) {
            if (i >= inf_count) break;
            vec3 diff = world_pos.xyz - inf_pos[i].xyz;
            float dist = length(diff);
            float rad = inf_pos[i].w;
            if (dist < rad && rad > 0.0) {
                float factor = smoothstep(0.0, 1.0, 1.0 - (dist / rad)) * height_factor;
                vec3 push_dir = normalize(vec3(diff.x, diff.y, diff.z + 0.1));
                float str = inf_param[i].x;
                total_bend += push_dir * (str * factor);

                if (inf_param[i].y <= 1.0) { // Wind / Fire shimmer
                    total_bend.x += sin(inf_param[i].z * 14.0 + world_pos.y) * 0.1 * factor * str;
                    total_bend.y += cos(inf_param[i].z * 13.0 + world_pos.x) * 0.1 * factor * str;
                }
            }
        }
    }

    world_pos.xyz += total_bend;

    v_world_pos     = world_pos.xyz;
    v_height        = world_pos.z;
    v_normal        = normalize(p3d_NormalMatrix * p3d_Normal);
    v_world_normal  = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_texcoord      = p3d_MultiTexCoord0;
    v_color         = p3d_Color;

    gl_Position = p3d_ProjectionMatrix * (p3d_ViewMatrix * world_pos);
}
