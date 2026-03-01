#include "WaterSimulation.h"
#include <cmath>
#include <algorithm>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

WaterSimulation::WaterSimulation(int gridSize, float worldSize)
    : _grid(gridSize), _world(worldSize),
      _cellSize(worldSize / float(gridSize - 1))
{
    _verts.resize(_grid * _grid);
    _vbo.resize(_grid * _grid * 6);

    // Init grid positions
    for (int y = 0; y < _grid; y++)
        for (int x = 0; x < _grid; x++) {
            auto& v = _verts[y * _grid + x];
            v.x = -_world * 0.5f + x * _cellSize;
            v.y = -_world * 0.5f + y * _cellSize;
        }

    // 4 Gerstner waves with different directions and params
    _waves = {
        { {1.f, 0.2f, 0}, 0.35f, 9.f,  1.5f, 0.5f },
        { {0.3f,1.f, 0},  0.25f, 6.f,  2.2f, 0.4f },
        { {-0.5f,0.7f,0}, 0.15f, 4.f,  3.0f, 0.3f },
        { {0.8f,-0.3f,0}, 0.10f, 12.f, 1.0f, 0.6f },
    };

    buildIndexBuffer();
}

void WaterSimulation::buildIndexBuffer() {
    _ibo.clear();
    for (int y = 0; y < _grid - 1; y++) {
        for (int x = 0; x < _grid - 1; x++) {
            int tl = y * _grid + x;
            int tr = tl + 1;
            int bl = tl + _grid;
            int br = bl + 1;
            _ibo.insert(_ibo.end(), {tl, bl, tr, tr, bl, br});
        }
    }
}

void WaterSimulation::computeGerstner(WaveVertex& v, float time) const {
    // Accumulate displacements from all waves
    float dx = 0, dy = 0, dz = 0;
    float nx = 0, ny = 0, nz = 1.f;

    for (auto& w : _waves) {
        Vec3  dir   = Vec3{w.dir.x, w.dir.y, 0}.normalized();
        float k     = 2.f * float(M_PI) / w.wavelength;
        float omega = std::sqrt(9.81f * k);
        float phase = k * (dir.x * v.x + dir.y * v.y) - omega * time + w.speed;

        float s = std::sin(phase);
        float c = std::cos(phase);

        // Gerstner displacement
        dx += w.steepness * w.amplitude * dir.x * c;
        dy += w.steepness * w.amplitude * dir.y * c;
        dz += w.amplitude * s;

        // Normal
        nx -= w.amplitude * k * dir.x * c;
        ny -= w.amplitude * k * dir.y * c;
        nz -= w.steepness * w.amplitude * k * s;
    }

    v.height = dz;
    // Normal (approximate, normalize later)
    float nlen = std::sqrt(nx*nx + ny*ny + nz*nz);
    v.nx = nx / nlen;
    v.ny = ny / nlen;
    v.nz = nz / nlen;
}

void WaterSimulation::addRipple(WaveVertex& v, const Ripple& r) const {
    float dist = std::sqrt((v.x - r.x)*(v.x - r.x) + (v.y - r.y)*(v.y - r.y));
    float speed= 5.f;
    float wave = r.strength * std::sin(dist * 2.f - r.elapsed * speed)
               * std::exp(-dist * 0.5f - r.elapsed * 2.f);
    v.height += wave;
}

void WaterSimulation::update(float time) {
    for (auto& v : _verts) {
        computeGerstner(v, time);
        for (auto& r : _ripples)
            addRipple(v, r);
    }

    // Advance ripples
    for (auto& r : _ripples) r.elapsed += 0.016f;
    _ripples.erase(std::remove_if(_ripples.begin(), _ripples.end(),
        [](const Ripple& r){ return r.elapsed > 2.5f; }), _ripples.end());

    rebuildVBO();
}

void WaterSimulation::rebuildVBO() {
    // Layout: x y (height) nx ny nz  per vertex
    for (int i = 0; i < _grid * _grid; i++) {
        const auto& v = _verts[i];
        int base = i * 6;
        _vbo[base+0] = v.x;
        _vbo[base+1] = v.y;
        _vbo[base+2] = v.height;
        _vbo[base+3] = v.nx;
        _vbo[base+4] = v.ny;
        _vbo[base+5] = v.nz;
    }
}

float WaterSimulation::getHeightAt(float wx, float wy) const {
    // Grid lookup + bilinear interpolation
    float gx = (wx + _world * 0.5f) / _cellSize;
    float gy = (wy + _world * 0.5f) / _cellSize;
    int ix = std::max(0, std::min(_grid-2, int(gx)));
    int iy = std::max(0, std::min(_grid-2, int(gy)));
    float fx = gx - ix;
    float fy = gy - iy;

    float h00 = _verts[ iy    * _grid + ix   ].height;
    float h10 = _verts[ iy    * _grid + ix+1 ].height;
    float h01 = _verts[(iy+1) * _grid + ix   ].height;
    float h11 = _verts[(iy+1) * _grid + ix+1 ].height;

    return h00*(1-fx)*(1-fy) + h10*fx*(1-fy) + h01*(1-fx)*fy + h11*fx*fy;
}

Vec3 WaterSimulation::getNormalAt(float wx, float wy) const {
    float gx = (wx + _world * 0.5f) / _cellSize;
    float gy = (wy + _world * 0.5f) / _cellSize;
    int ix = std::max(0, std::min(_grid-2, int(gx)));
    int iy = std::max(0, std::min(_grid-2, int(gy)));
    const auto& v = _verts[iy * _grid + ix];
    return {v.nx, v.ny, v.nz};
}

void WaterSimulation::applySwimForces(CharacterState& cs, float dt) const {
    if (!cs.inWater) return;
    // Buoyancy relative to actual wave height
    float wh = getHeightAt(cs.position.x, cs.position.y);
    float depth = wh - cs.position.z;
    float buoy  = std::clamp(depth / 2.f, 0.f, 1.f) * 18.f;
    cs.velocity.z += (buoy - 24.f) * dt;

    // Water drag
    float drag = std::pow(0.82f, dt * 60.f);
    cs.velocity.x *= drag;
    cs.velocity.y *= drag;
    cs.velocity.z *= std::pow(0.88f, dt * 60.f);
}

Vec3 WaterSimulation::splash(const Vec3& pos, float strength) {
    _ripples.push_back({pos.x, pos.y, strength, 0.f});
    return {pos.x, pos.y, getHeightAt(pos.x, pos.y)};
}
