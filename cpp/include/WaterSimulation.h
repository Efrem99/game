#pragma once
#include "PhysicsEngine.h"
#include <vector>
#include <cmath>

// ───────────────────────────────────────────────
// Water surface wave vertex (for GPU upload)
// ───────────────────────────────────────────────
struct WaveVertex {
    float x, y;        // grid position
    float height;      // displaced Z
    float nx, ny, nz;  // normal
};

// ───────────────────────────────────────────────
// Gerstner wave parameters
// ───────────────────────────────────────────────
struct GerstnerWave {
    Vec3  dir       {};
    float amplitude = 0.4f;
    float wavelength= 8.0f;
    float speed     = 2.0f;
    float steepness = 0.5f;
};

// ───────────────────────────────────────────────
// WaterSimulation
// Computes Gerstner waves on a grid; Python
// uploads vertex array to Geom each frame.
// ───────────────────────────────────────────────
class WaterSimulation {
public:
    // gridSize × gridSize vertices, worldSize × worldSize meters
    WaterSimulation(int gridSize = 64, float worldSize = 40.f);

    // Simulate one frame, fill _vertices
    void update(float time);

    // Query height at world XY (bilinear interp)
    float getHeightAt(float worldX, float worldY) const;

    // Query normal at world XY
    Vec3  getNormalAt(float worldX, float worldY) const;

    // Character <-> water interaction
    void applySwimForces(CharacterState& cs, float dt) const;

    // Splash effect trigger – returns position of ripple center
    Vec3 splash(const Vec3& pos, float strength);

    // Get flat vertex array (x,y,z,nx,ny,nz per vertex)
    // Ready to upload to Panda3D GeomVertexData
    const std::vector<float>& getVertexBuffer() const { return _vbo; }
    const std::vector<int>&   getIndexBuffer()  const { return _ibo; }
    int gridSize()  const { return _grid; }
    int vertCount() const { return _grid * _grid; }
    int indexCount()const { return (_grid-1)*(_grid-1)*6; }

private:
    int   _grid;
    float _world;
    float _cellSize;

    std::vector<WaveVertex> _verts;
    std::vector<float>      _vbo;
    std::vector<int>        _ibo;

    // 4 Gerstner waves summed together
    std::vector<GerstnerWave> _waves;

    // Splash ripples
    struct Ripple { float x, y, strength, elapsed; };
    std::vector<Ripple> _ripples;

    void buildIndexBuffer();
    void computeGerstner(WaveVertex& v, float time) const;
    void addRipple(WaveVertex& v, const Ripple& r) const;
    void rebuildVBO();
};
