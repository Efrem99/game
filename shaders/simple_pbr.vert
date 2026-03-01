#version 330 core

uniform mat4 p3d_ProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat3 p3d_NormalMatrix;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;

out vec3 v_normal;
out vec3 v_world_normal;
out vec2 v_texcoord;
out vec3 v_world_pos;
out float v_height;

void main() {
    vec4 world_pos  = p3d_ModelMatrix * p3d_Vertex;
    v_world_pos     = world_pos.xyz;
    v_height        = world_pos.z;
    v_normal        = normalize(p3d_NormalMatrix * p3d_Normal);
    v_world_normal  = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_texcoord      = p3d_MultiTexCoord0;
    gl_Position     = p3d_ProjectionMatrix * (p3d_ModelViewMatrix * p3d_Vertex);
}
