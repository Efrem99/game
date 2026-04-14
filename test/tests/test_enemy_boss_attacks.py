import random
import sys
import types
import unittest
from pathlib import Path

from panda3d.core import Vec3

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.boss_manager import EnemyUnit


class _QuatStub:
    def __init__(self, heading_deg):
        self.heading_deg = float(heading_deg)

    def getForward(self):
        import math

        rad = math.radians(self.heading_deg)
        return Vec3(math.sin(rad), math.cos(rad), 0.0)


class _RootStub:
    def __init__(self, pos=None, heading_deg=0.0):
        self._pos = Vec3(pos) if pos is not None else Vec3(0.0, 0.0, 0.0)
        self._heading_deg = float(heading_deg)

    def isEmpty(self):
        return False

    def getPos(self, render=None):
        del render
        return Vec3(self._pos)

    def setPos(self, *args):
        if len(args) == 1:
            self._pos = Vec3(args[0])
            return
        self._pos = Vec3(float(args[0]), float(args[1]), float(args[2]))

    def getH(self, render=None):
        del render
        return float(self._heading_deg)

    def setH(self, render_or_value, value=None):
        if value is None:
            self._heading_deg = float(render_or_value)
            return
        del render_or_value
        self._heading_deg = float(value)

    def getQuat(self, render=None):
        del render
        return _QuatStub(self._heading_deg)

    def setColorScale(self, *args):
        self._color = tuple(args)


class _NodeStub:
    def __init__(self):
        self.removed = False

    def isEmpty(self):
        return False

    def removeNode(self):
        self.removed = True

    def reparentTo(self, parent):
        self.parent = parent

    def setScale(self, *args):
        self.scale = tuple(float(v) for v in args)

    def setColorScale(self, *args):
        self.color = tuple(float(v) for v in args)


class _PlayerStub:
    def __init__(self, hp=100.0):
        self.cs = types.SimpleNamespace(health=float(hp), maxHealth=float(hp))
        self.damage_calls = []

    def take_damage(self, amount, damage_type="physical", source=None):
        self.damage_calls.append((float(amount), str(damage_type), source))
        self.cs.health = max(0.0, float(self.cs.health) - float(amount))


class _CameraDirectorStub:
    def __init__(self):
        self.calls = []

    def emit_impact(self, kind="hit", intensity=1.0, direction_deg=0.0):
        self.calls.append((str(kind), float(intensity), float(direction_deg)))


class _TimeFxStub:
    def __init__(self):
        self.calls = []

    def trigger(self, kind="combat", duration=None, scales=None):
        self.calls.append((str(kind), duration, dict(scales or {})))


class _LoaderStub:
    def __init__(self):
        self.loaded = []

    def loadModel(self, path):
        self.loaded.append(str(path))
        return _NodeStub()


class _WorldStub:
    def __init__(self, height=0.0):
        self.height = float(height)

    def _th(self, x, y):
        del x, y
        return float(self.height)


def _build_unit(*, player=None):
    unit = EnemyUnit.__new__(EnemyUnit)
    unit.app = types.SimpleNamespace(
        player=player,
        camera_director=_CameraDirectorStub(),
        time_fx=_TimeFxStub(),
        world=None,
        audio=None,
    )
    unit.render = object()
    unit.loader = None
    unit.cfg = {
        "stats": {
            "max_hp": 2550.0,
            "armor": 25.0,
            "power": 44.0,
            "attack_range": 5.3,
        },
        "ai": {
            "melee_damage": 24.0,
            "melee_hit_time": 0.36,
            "melee_window_start": 0.31,
            "melee_window_end": 0.48,
            "jump_slam_range": 8.0,
            "jump_slam_cooldown": 5.0,
            "jump_slam_damage": 34.0,
            "jump_slam_radius": 8.5,
            "player_hit_collider_radius": 1.0,
            "earth_throw_range": 16.0,
            "earth_throw_cooldown": 4.0,
            "earth_throw_damage": 20.0,
            "earth_throw_radius": 3.4,
            "earth_throw_speed": 13.0,
            "earth_throw_vertical_boost": 4.4,
            "earth_throw_visual_scale": 0.92,
        },
    }
    unit._rng = random.Random(3)
    unit.id = "golem_titan"
    unit.kind = "golem"
    unit.name = "Titan Golem"
    unit.is_boss = True
    unit.root = _RootStub(Vec3(0.0, 0.0, 0.0))
    unit.actor = None
    unit.nodes = {}
    unit.fire_origin = None
    unit.proxy = types.SimpleNamespace(health=2550.0, armor=25.0, alive=True)
    unit._anim_map = {}
    unit._anim_active_clip = ""
    unit._anim_active_state = ""
    unit._damage_flash = 0.0
    unit._last_hp_seen = 2550.0
    unit.state = "idle"
    unit.state_time = 0.0
    unit.state_lock = 0.0
    unit.attack_cd = 0.0
    unit._attack_windup = 0.0
    unit._pending_hit_react = 0.0
    unit.engaged_until = 999.0
    unit._is_engaged = True
    unit.melee_applied = False
    unit.fire_particles = []
    unit.fire_emit_acc = 0.0
    unit.fire_tick_acc = 0.0
    unit.last_fire_sfx = -999.0
    unit.max_hp = 2550.0
    unit.hp = 2550.0
    unit.awareness = "alert"
    unit.stealth_meter = 1.0
    unit.last_known_player_pos = None
    unit.armor = 25.0
    unit._telegraph_fx = {}
    unit._phase_rules = []
    unit._phase_cursor = 0
    unit._phase_damage_mul = 1.0
    unit._phase_speed_mul = 1.0
    unit._phase_telegraph_mul = 1.0
    unit._phase_cooldown_mul = 1.0
    unit._phase_anim_rate_mul = 1.0
    unit._death_reported = False
    unit._loot_bag_dropped = False
    unit._loot_bag_anchor_id = ""
    unit._loot_bag_node = None
    unit._attack_variant = "melee"
    unit._jump_slam_cooldown = 0.0
    unit._earth_throw_cooldown = 0.0
    unit._jump_slam_phase = "idle"
    unit._jump_slam_vertical_velocity = 0.0
    unit._jump_slam_ground_z = 0.0
    unit._jump_slam_landed = False
    unit._earth_throw_done = False
    unit._earth_projectiles = []
    unit._sync_proxy_from_core = lambda: None
    unit._sync_proxy_to_core = lambda: None
    unit._check_phase_transitions = lambda: None
    unit._update_stealth = lambda dt, player_pos, stealth_state=None: None
    unit._sync_actor_animation = lambda: None
    unit._tick_fire_particles = lambda dt: None
    unit._animate = lambda: None
    unit._apply_visual_state = lambda dt: None
    return unit


class EnemyBossAttackTests(unittest.TestCase):
    def test_enemy_unit_take_damage_can_kill_golem_boss_and_sync_proxy(self):
        unit = _build_unit()
        unit.hp = 32.0
        unit.proxy.health = 32.0

        hit = EnemyUnit.take_damage(unit, 120.0, "physical", source="hero")

        self.assertTrue(hit)
        self.assertLessEqual(float(unit.hp), 0.0)
        self.assertLessEqual(float(unit.proxy.health), 0.0)
        self.assertGreater(float(unit._damage_flash), 0.0)

    def test_boss_melee_damage_routes_through_player_once(self):
        player = _PlayerStub(hp=100.0)
        unit = _build_unit(player=player)
        unit.state = "attack"
        unit.state_time = 0.35
        unit.state_lock = 0.40

        EnemyUnit.update(unit, 0.01, Vec3(0.0, 2.0, 0.0))

        self.assertEqual(1, len(player.damage_calls))
        self.assertAlmostEqual(76.0, float(player.cs.health), places=3)

    def test_select_attack_variant_prefers_jump_slam_for_nearby_player(self):
        unit = _build_unit()

        variant = EnemyUnit._select_attack_variant(unit, 5.0)

        self.assertEqual("jump_slam", variant)

    def test_select_attack_variant_prefers_earth_throw_at_mid_range(self):
        unit = _build_unit()
        unit._jump_slam_cooldown = 4.0

        variant = EnemyUnit._select_attack_variant(unit, 13.0)

        self.assertEqual("earth_throw", variant)

    def test_jump_slam_impact_deals_damage_and_triggers_screen_feedback(self):
        player = _PlayerStub(hp=120.0)
        unit = _build_unit(player=player)

        hit = EnemyUnit._trigger_jump_slam_impact(unit, Vec3(0.0, 4.0, 0.0))

        self.assertTrue(hit)
        self.assertEqual(1, len(player.damage_calls))
        self.assertEqual("heavy", unit.app.camera_director.calls[-1][0])
        self.assertEqual("danger_focus", unit.app.time_fx.calls[-1][0])

    def test_jump_slam_impact_respects_player_collider_padding_near_edge(self):
        player = _PlayerStub(hp=120.0)
        unit = _build_unit(player=player)

        hit = EnemyUnit._trigger_jump_slam_impact(unit, Vec3(0.0, 9.1, 0.0))

        self.assertTrue(hit)
        self.assertEqual(1, len(player.damage_calls))

    def test_earth_projectile_impact_deals_damage_and_cleans_up_chunk(self):
        player = _PlayerStub(hp=120.0)
        unit = _build_unit(player=player)
        node = _NodeStub()
        unit._earth_projectiles = [
            {
                "node": node,
                "pos": Vec3(0.0, 1.0, 0.2),
                "vel": Vec3(0.0, 0.0, -0.1),
                "life": 0.8,
                "radius": 3.5,
                "damage": 22.0,
            }
        ]

        EnemyUnit._tick_earth_projectiles(unit, 0.10, Vec3(0.0, 1.2, 0.0))

        self.assertEqual(1, len(player.damage_calls))
        self.assertEqual([], unit._earth_projectiles)
        self.assertTrue(node.removed)

    def test_earth_projectile_impact_respects_player_collider_padding_near_edge(self):
        player = _PlayerStub(hp=120.0)
        unit = _build_unit(player=player)
        node = _NodeStub()
        unit._earth_projectiles = [
            {
                "node": node,
                "pos": Vec3(0.0, 0.0, 1.1),
                "vel": Vec3(0.0, 0.0, -0.2),
                "life": 0.8,
                "radius": 3.4,
                "damage": 22.0,
            }
        ]

        EnemyUnit._tick_earth_projectiles(unit, 0.10, Vec3(0.0, 4.15, 0.0))

        self.assertEqual(1, len(player.damage_calls))
        self.assertEqual([], unit._earth_projectiles)
        self.assertTrue(node.removed)

    def test_earth_projectile_node_uses_larger_boss_rock_scale(self):
        unit = _build_unit()
        unit.loader = _LoaderStub()

        node = EnemyUnit._create_earth_projectile_node(unit)

        self.assertIsNotNone(node)
        self.assertGreater(node.scale[0], 0.80)
        self.assertGreater(node.scale[2], 0.60)

    def test_update_reanchors_ground_boss_to_terrain_when_below_surface(self):
        unit = _build_unit()
        unit.app.world = _WorldStub(height=3.0)
        unit.root.setPos(0.0, 0.0, 0.25)
        unit.state = "idle"
        unit._is_engaged = False
        unit.engaged_until = 0.0

        EnemyUnit.update(unit, 0.10, Vec3(18.0, 18.0, 0.0))

        self.assertAlmostEqual(4.2, float(unit.root.getPos().z), places=3)

    def test_update_reanchors_ground_boss_to_terrain_when_floating_without_cause(self):
        unit = _build_unit()
        unit.app.world = _WorldStub(height=3.0)
        unit.root.setPos(0.0, 0.0, 9.5)
        unit.state = "idle"
        unit._is_engaged = False
        unit.engaged_until = 0.0

        EnemyUnit.update(unit, 0.10, Vec3(18.0, 18.0, 0.0))

        self.assertAlmostEqual(4.2, float(unit.root.getPos().z), places=3)


if __name__ == "__main__":
    unittest.main()
