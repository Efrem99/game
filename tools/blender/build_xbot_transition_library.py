"""Build a compact XBot transition clip library from compatible FBX sources.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" --factory-startup -b -P tools/blender/build_xbot_transition_library.py
"""

from __future__ import annotations

import argparse
import json
import sys
from math import radians
from pathlib import Path

import bpy


# Preserve the ASCII junction project root during local builds.
# Using __file__.resolve() jumps to the underlying Cyrillic path and breaks
# downstream Windows/Panda tooling on this machine.
PROJECT_ROOT = Path.cwd()
DEFAULT_CLIP_SPECS = (
    ("idle", PROJECT_ROOT / "assets" / "models" / "xbot" / "idle.glb"),
    ("walk", PROJECT_ROOT / "assets" / "models" / "xbot" / "walk.glb"),
    ("run", PROJECT_ROOT / "assets" / "models" / "xbot" / "run.glb"),
    ("dodging", PROJECT_ROOT / "assets" / "anims" / "dodge_roll.fbx"),
    ("jumping", PROJECT_ROOT / "assets" / "anims" / "jump_takeoff.fbx"),
    ("falling", PROJECT_ROOT / "assets" / "anims" / "fall_air.fbx"),
    ("falling_hard", PROJECT_ROOT / "assets" / "anims" / "fall_air.fbx"),
    ("landing", PROJECT_ROOT / "assets" / "anims" / "land_recover.fbx"),
    ("run_blade", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "run_blade.fbx"),
    ("sliding", PROJECT_ROOT / "models" / "animations" / "GoAwayQuickly.fbx"),
    ("swim", PROJECT_ROOT / "assets" / "anims" / "swim_loop.fbx"),
    ("vaulting", PROJECT_ROOT / "assets" / "anims" / "vault_over.fbx"),
    ("climbing", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "climb_fast.fbx"),
    ("wallrun", PROJECT_ROOT / "assets" / "anims" / "wallrun_side.fbx"),
    ("flying", PROJECT_ROOT / "assets" / "anims" / "flying_loop.fbx"),
    ("flight_takeoff", PROJECT_ROOT / "assets" / "anims" / "jump_takeoff.fbx"),
    ("flight_hover", PROJECT_ROOT / "assets" / "anims" / "flying_loop.fbx"),
    ("flight_glide", PROJECT_ROOT / "assets" / "anims" / "flying_loop.fbx"),
    ("flight_airdash", PROJECT_ROOT / "assets" / "anims" / "flying_loop.fbx"),
    ("flight_dive", PROJECT_ROOT / "assets" / "anims" / "fall_air.fbx"),
    ("flight_land", PROJECT_ROOT / "assets" / "anims" / "land_recover.fbx"),
    ("attacking", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "attack_light_right.fbx"),
    ("attack_light_right", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "attack_light_right.fbx"),
    ("attack_thrust_right", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "attack_thrust_right.fbx"),
    ("blocking", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "blocking.fbx"),
    ("casting", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "cast_fast.fbx"),
    ("cast_prepare", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "cast_prepare.fbx"),
    ("cast_channel", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "cast_channel.fbx"),
    ("cast_release", PROJECT_ROOT / "assets" / "anims" / "mixamo" / "player" / "cast_release.fbx"),
    ("recovering", PROJECT_ROOT / "assets" / "anims" / "land_recover.fbx"),
)
DEFAULT_RUNTIME_CLIP_DIR = PROJECT_ROOT / "assets" / "models" / "xbot" / "runtime_clips"
ACTION_SELECTION_HINTS = {
    "idle": ("idle",),
    "walk": ("walk",),
    "run": ("run",),
    "dodging": ("dodge_roll", "dodging"),
    "jumping": ("jump_takeoff", "jumping"),
    "falling": ("fall_air", "falling"),
    "falling_hard": ("fall_air", "falling_hard", "falling"),
    "landing": ("land_recover", "landing"),
    "run_blade": ("run_blade", "run"),
    "sliding": ("goawayquickly", "sliding"),
    "swim": ("swim_loop", "swim"),
    "vaulting": ("vault_over", "vault_high", "vault_low", "vaulting"),
    "climbing": ("climb_fast", "climb_up", "climb_slow", "climbing"),
    "wallrun": ("wallrun_side", "wallrun_start", "wallrun_exit", "wallrun"),
    "flying": ("flying_loop", "flying"),
    "flight_takeoff": ("jump_takeoff", "flight_takeoff"),
    "flight_hover": ("flying_loop", "flight_hover", "flying"),
    "flight_glide": ("flying_loop", "flight_glide", "flying"),
    "flight_airdash": ("flying_loop", "flight_airdash", "flying"),
    "flight_dive": ("fall_air", "flight_dive", "falling"),
    "flight_land": ("land_recover", "flight_land", "landing"),
    "attacking": ("attack_light_right", "attacking"),
    "attack_light_right": ("attack_light_right",),
    "attack_thrust_right": ("attack_thrust_right", "attack_thrust"),
    "blocking": ("blocking", "block_guard"),
    "casting": ("cast_fast", "casting"),
    "cast_prepare": ("cast_prepare",),
    "cast_channel": ("cast_channel",),
    "cast_release": ("cast_release",),
    "recovering": ("land_recover", "recovering"),
}
WEAPON_TRANSITION_POSES = {
    "weapon_unsheathe": {
        1: {},
        8: {
            "mixamorig:Spine": (0.0, 0.0, -6.0),
            "mixamorig:Spine1": (0.0, 0.0, -8.0),
            "mixamorig:Spine2": (0.0, 0.0, -10.0),
            "mixamorig:RightShoulder": (0.0, 0.0, 12.0),
            "mixamorig:RightArm": (18.0, -4.0, 22.0),
            "mixamorig:RightForeArm": (42.0, 8.0, 26.0),
            "mixamorig:RightHand": (10.0, 0.0, 22.0),
            "mixamorig:LeftShoulder": (0.0, 0.0, -6.0),
            "mixamorig:LeftArm": (-8.0, 0.0, -14.0),
            "mixamorig:LeftForeArm": (-16.0, 0.0, -10.0),
        },
        16: {
            "mixamorig:Spine": (0.0, 0.0, 10.0),
            "mixamorig:Spine1": (0.0, 0.0, 16.0),
            "mixamorig:Spine2": (0.0, 0.0, 20.0),
            "mixamorig:RightShoulder": (0.0, 0.0, -10.0),
            "mixamorig:RightArm": (-34.0, 6.0, -22.0),
            "mixamorig:RightForeArm": (-58.0, 10.0, -6.0),
            "mixamorig:RightHand": (6.0, 0.0, -18.0),
            "mixamorig:LeftShoulder": (0.0, 0.0, 6.0),
            "mixamorig:LeftArm": (6.0, 0.0, 10.0),
            "mixamorig:LeftForeArm": (12.0, 0.0, 6.0),
        },
        24: {
            "mixamorig:Spine": (0.0, 0.0, 4.0),
            "mixamorig:Spine1": (0.0, 0.0, 6.0),
            "mixamorig:Spine2": (0.0, 0.0, 8.0),
            "mixamorig:RightArm": (-12.0, 0.0, -8.0),
            "mixamorig:RightForeArm": (-24.0, 0.0, -4.0),
            "mixamorig:RightHand": (2.0, 0.0, -6.0),
            "mixamorig:LeftArm": (2.0, 0.0, 4.0),
            "mixamorig:LeftForeArm": (6.0, 0.0, 2.0),
        },
    },
    "weapon_sheathe": {
        1: {
            "mixamorig:Spine": (0.0, 0.0, 4.0),
            "mixamorig:Spine1": (0.0, 0.0, 6.0),
            "mixamorig:Spine2": (0.0, 0.0, 8.0),
            "mixamorig:RightArm": (-12.0, 0.0, -8.0),
            "mixamorig:RightForeArm": (-24.0, 0.0, -4.0),
            "mixamorig:RightHand": (2.0, 0.0, -6.0),
            "mixamorig:LeftArm": (2.0, 0.0, 4.0),
            "mixamorig:LeftForeArm": (6.0, 0.0, 2.0),
        },
        10: {
            "mixamorig:Spine": (0.0, 0.0, -4.0),
            "mixamorig:Spine1": (0.0, 0.0, -10.0),
            "mixamorig:Spine2": (0.0, 0.0, -14.0),
            "mixamorig:RightShoulder": (0.0, 0.0, 8.0),
            "mixamorig:RightArm": (16.0, -2.0, 18.0),
            "mixamorig:RightForeArm": (34.0, 4.0, 20.0),
            "mixamorig:RightHand": (6.0, 0.0, 18.0),
            "mixamorig:LeftArm": (-6.0, 0.0, -10.0),
            "mixamorig:LeftForeArm": (-10.0, 0.0, -8.0),
        },
        18: {},
    },
}


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Build compact XBot transition library.")
    parser.add_argument(
        "--base-model",
        default=str(PROJECT_ROOT / "assets" / "models" / "xbot" / "Xbot.glb"),
        help="Base XBot model used as the export rig.",
    )
    parser.add_argument(
        "--output-glb",
        default=str(PROJECT_ROOT / "assets" / "models" / "xbot" / "xbot_transition_pack.glb"),
        help="Output GLB path.",
    )
    parser.add_argument(
        "--report-json",
        default=str(PROJECT_ROOT / "logs" / "xbot_transition_pack_report.json"),
        help="JSON report path.",
    )
    parser.add_argument(
        "--runtime-dir",
        default=str(DEFAULT_RUNTIME_CLIP_DIR),
        help="Directory for per-state single-clip GLBs.",
    )
    parser.add_argument(
        "--clip",
        action="append",
        default=None,
        help="Clip mapping in the form state=path/to/source.fbx (repeatable).",
    )
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)


def import_base_model(path: Path):
    bpy.ops.import_scene.gltf(filepath=str(path))


def import_anim(path: Path):
    suffix = str(path.suffix or "").strip().lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
        return
    bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)


def find_armatures():
    return [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]


def parse_clip_specs(raw_specs):
    items = [f"{state_key}={clip_path}" for state_key, clip_path in DEFAULT_CLIP_SPECS]
    if raw_specs:
        items.extend(str(item or "").strip() for item in raw_specs if str(item or "").strip())

    deduped = {}
    ordered_keys = []
    for item in items:
        text = str(item or "").strip()
        if (not text) or ("=" not in text):
            continue
        key, raw_path = text.split("=", 1)
        state_key = str(key or "").strip().lower()
        clip_path = Path(str(raw_path or "").strip())
        if not clip_path.is_absolute():
            clip_path = PROJECT_ROOT / clip_path
        if state_key and clip_path.exists():
            if state_key not in deduped:
                ordered_keys.append(state_key)
            deduped[state_key] = clip_path
    return [(state_key, deduped[state_key]) for state_key in ordered_keys]


def attach_action_to_base(base_armature, action, state_key):
    action.name = state_key
    action.use_fake_user = True
    if base_armature.animation_data is None:
        base_armature.animation_data_create()
    track = base_armature.animation_data.nla_tracks.new()
    track.name = state_key
    start = int(action.frame_range[0]) if action.frame_range else 1
    track.strips.new(state_key, start, action)


def _normalize_token(value):
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def select_action_for_state(new_actions, state_key):
    if not new_actions:
        return None
    normalized_lookup = {}
    for action in new_actions:
        normalized_lookup[_normalize_token(action.name)] = action
    preferred = list(ACTION_SELECTION_HINTS.get(state_key, ()))
    preferred.insert(0, state_key)
    for token in preferred:
        match = normalized_lookup.get(_normalize_token(token))
        if match is not None:
            return match
    return new_actions[0]


def create_generated_weapon_transition(base_armature, state_key):
    pose_spec = WEAPON_TRANSITION_POSES.get(state_key)
    if not pose_spec:
        return None

    base_armature.animation_data_create()
    action = bpy.data.actions.new(state_key)
    base_armature.animation_data.action = action

    targeted_bones = set()
    for frame_rows in pose_spec.values():
        targeted_bones.update(frame_rows.keys())

    pose_bones = {
        bone_name: base_armature.pose.bones.get(bone_name)
        for bone_name in targeted_bones
        if base_armature.pose.bones.get(bone_name) is not None
    }
    if not pose_bones:
        return None

    scene = bpy.context.scene
    for pose_bone in pose_bones.values():
        pose_bone.rotation_mode = "XYZ"

    for frame in sorted(pose_spec):
        scene.frame_set(frame)
        for pose_bone in pose_bones.values():
            pose_bone.rotation_euler = (0.0, 0.0, 0.0)
        for bone_name, euler_deg in pose_spec[frame].items():
            pose_bone = pose_bones.get(bone_name)
            if pose_bone is None:
                continue
            pose_bone.rotation_euler = tuple(radians(value) for value in euler_deg)
        for pose_bone in pose_bones.values():
            pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame)

    attach_action_to_base(base_armature, action, state_key)
    return {
        "state": state_key,
        "source": "generated:weapon_transition",
        "frame_range": tuple(float(v) for v in getattr(action, "frame_range", (0.0, 0.0))),
    }


def remove_objects(objects):
    for obj in objects:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            continue
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def export_single_runtime_clip(base_model: Path, runtime_dir: Path, state_key: str, clip_path: Path | None):
    clear_scene()
    import_base_model(base_model)
    armatures = find_armatures()
    if not armatures:
        raise RuntimeError(f"No armature found after importing base model: {base_model}")
    base_armature = armatures[0]
    base_armature_name = base_armature.name
    base_object_names = {obj.name for obj in bpy.data.objects}
    base_action_names = set(bpy.data.actions.keys())

    new_objects = []
    if clip_path is None:
        generated = create_generated_weapon_transition(base_armature, state_key)
        if generated is None:
            raise RuntimeError(f"Failed to synthesize runtime clip for generated state '{state_key}'")
        selected_action = bpy.data.actions.get(state_key)
        if selected_action is None:
            raise RuntimeError(f"Generated state '{state_key}' did not leave a named action behind")
    else:
        before_actions = set(bpy.data.actions.keys())
        before_names = {obj.name for obj in bpy.data.objects}
        import_anim(clip_path)
        new_actions = [bpy.data.actions[name] for name in (set(bpy.data.actions.keys()) - before_actions)]
        new_objects = [obj for obj in bpy.data.objects if obj.name not in before_names]
        selected_action = select_action_for_state(new_actions, state_key)
        if selected_action is None:
            remove_objects(new_objects)
            raise RuntimeError(f"No imported action found for state '{state_key}' from {clip_path}")

    for action in list(bpy.data.actions):
        if action == selected_action:
            continue
        if action.name in base_action_names or action.users == 0 or action.name != state_key:
            try:
                bpy.data.actions.remove(action)
            except Exception:
                continue

    if clip_path is not None:
        attach_action_to_base(base_armature, selected_action, state_key)
    remove_objects(new_objects)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.name in base_object_names:
            obj.select_set(True)

    output_path = runtime_dir / f"{state_key}.glb"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
    )
    return output_path


def main():
    args = parse_args()
    clip_specs = parse_clip_specs(args.clip)
    if not clip_specs:
        raise RuntimeError("No valid clip mappings were provided.")

    base_model = Path(args.base_model)
    if not base_model.is_absolute():
        base_model = PROJECT_ROOT / base_model
    if not base_model.exists():
        raise FileNotFoundError(f"Base model not found: {base_model}")

    clear_scene()
    import_base_model(base_model)
    armatures = find_armatures()
    if not armatures:
        raise RuntimeError(f"No armature found after importing base model: {base_model}")
    base_armature = armatures[0]
    base_armature_name = base_armature.name
    base_object_names = {obj.name for obj in bpy.data.objects}

    created = []
    for state_key, clip_path in clip_specs:
        before_actions = set(bpy.data.actions.keys())
        before_names = {obj.name for obj in bpy.data.objects}
        import_anim(clip_path)

        new_actions = [bpy.data.actions[name] for name in (set(bpy.data.actions.keys()) - before_actions)]
        new_objects = [obj for obj in bpy.data.objects if obj.name not in before_names]

        selected_action = select_action_for_state(new_actions, state_key)
        if selected_action is None:
            remove_objects(new_objects)
            continue

        attach_action_to_base(base_armature, selected_action, state_key)
        frame_range = tuple(float(v) for v in getattr(selected_action, "frame_range", (0.0, 0.0)))
        created.append(
            {
                "state": state_key,
                "source": clip_path.as_posix(),
                "frame_range": frame_range,
            }
        )
        remove_objects(new_objects)

    for generated_state in ("weapon_unsheathe", "weapon_sheathe"):
        generated = create_generated_weapon_transition(base_armature, generated_state)
        if generated:
            created.append(generated)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if obj.name in base_object_names:
            obj.select_set(True)

    output_glb = Path(args.output_glb)
    if not output_glb.is_absolute():
        output_glb = PROJECT_ROOT / output_glb
    runtime_dir = Path(args.runtime_dir)
    if not runtime_dir.is_absolute():
        runtime_dir = PROJECT_ROOT / runtime_dir
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_glb),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
    )

    runtime_exports = []
    runtime_specs = list(clip_specs) + [
        ("weapon_unsheathe", None),
        ("weapon_sheathe", None),
    ]
    for state_key, clip_path in runtime_specs:
        runtime_clip = export_single_runtime_clip(base_model, runtime_dir, state_key, clip_path)
        runtime_exports.append(
            {
                "state": state_key,
                "source": "generated:weapon_transition" if clip_path is None else clip_path.as_posix(),
                "output_glb": runtime_clip.as_posix(),
            }
        )

    report = {
        "base_model": base_model.as_posix(),
        "base_armature": base_armature_name,
        "created": created,
        "runtime_exports": runtime_exports,
        "output_glb": output_glb.as_posix(),
        "runtime_dir": runtime_dir.as_posix(),
    }
    report_path = Path(args.report_json)
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
