#version 330 core

// Textures: albedo (slot 0), normal map (slot 1), roughness (slot 2)
uniform sampler2D p3d_Texture0;
uniform sampler2D p3d_Texture1;
uniform sampler2D p3d_Texture2;

in vec3 v_normal;
in vec3 v_world_normal;
in vec2 v_texcoord;
in vec3 v_world_pos;
in float v_height;
in vec4 v_color;
out vec4 fragColor;

// --- Lighting ---
const vec3  SUN_DIR    = normalize(vec3(0.50, 0.45, 0.72));
const vec3  SUN_COLOR  = vec3(0.85, 0.78, 0.65); // Reduced from 1.10
const vec3  SKY_AMB    = vec3(0.10, 0.16, 0.28); // Reduced from 0.16
const vec3  GND_AMB    = vec3(0.08, 0.06, 0.05);
const vec3  FILL_DIR   = normalize(vec3(-0.4, -0.3, 0.25));
const vec3  FILL_COLOR = vec3(0.12, 0.16, 0.22);

// --- Fog ---
const vec3  FOG_COLOR  = vec3(0.55, 0.68, 0.88);
const float FOG_START  = 40.0;
const float FOG_END    = 150.0;

// --- Cursed State ---
uniform float cursed_blend;
const vec3 CURSED_FOG_COLOR = vec3(0.18, 0.02, 0.01);

vec3 gamma_correct(vec3 c) { return pow(clamp(c, 0.0, 1.0), vec3(1.0/2.2)); }

void main() {
    // Sample textures
    vec3  albedo   = texture(p3d_Texture0, v_texcoord).rgb;
    vec3  norm_map = texture(p3d_Texture1, v_texcoord).rgb;
    float rough    = texture(p3d_Texture2, v_texcoord).r;

    // Reconstruct normal from normal map (tangent-space approximation)
    vec3 map_n = normalize(norm_map * 2.0 - 1.0);
    // Blend normal map with geometric normal (simplified without full TBN)
    vec3 n = normalize(v_normal + map_n * 0.3);

    // Hemisphere ambient
    float h    = n.z * 0.5 + 0.5;
    vec3  amb  = mix(GND_AMB, SKY_AMB, h);

    // Main sun light (diffuse)
    float NdotL = max(dot(n, SUN_DIR), 0.0);
    // Wrap lighting for softer shadows
    float wrap  = max(dot(n, SUN_DIR) * 0.5 + 0.5, 0.0);
    vec3  sun   = SUN_COLOR * mix(NdotL, wrap, 0.3);

    // Fill light from opposite side
    float fill  = max(dot(n, FILL_DIR), 0.0) * 0.25;
    vec3  fills = FILL_COLOR * fill;

    // Simple specular highlight (Blinn-Phong approximation)
    vec3  view_dir = normalize(vec3(0.0, -1.0, 0.6));  // approximate camera direction
    vec3  half_vec = normalize(SUN_DIR + view_dir);
    float spec_pow = mix(8.0, 128.0, 1.0 - rough);
    float spec     = pow(max(dot(n, half_vec), 0.0), spec_pow) * (1.0 - rough) * 0.35;

    // Rim light (backlight glow)
    float rim_dot = 1.0 - max(dot(n, view_dir), 0.0);
    float rim     = pow(rim_dot, 3.0) * 0.15;

    // Height-based color variation (grass darkens in valleys, brightens on hills)
    float height_mod = clamp((v_height + 5.0) / 30.0, 0.0, 1.0) * 0.12 + 0.94;

    // Combine
    vec3 color = albedo * v_color.rgb * height_mod * (amb + sun + fills) + vec3(spec) + vec3(rim) * SUN_COLOR * 0.5;

    // Darken in cursed zone
    color *= (1.0 - cursed_blend * 0.45);

    // Distance fog
    float dist      = length(v_world_pos);
    vec3  f_col     = mix(FOG_COLOR, CURSED_FOG_COLOR, cursed_blend);
    float f_start   = mix(FOG_START, 20.0, cursed_blend);
    float f_end     = mix(FOG_END, 80.0, cursed_blend);
    float fog_fac   = clamp((dist - f_start) / (f_end - f_start), 0.0, 1.0);
    fog_fac         = fog_fac * fog_fac;
    color           = mix(color, f_col, fog_fac);

    fragColor = vec4(gamma_correct(color), 1.0);
}
