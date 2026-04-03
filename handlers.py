# =====================================================================
# EasyRetarget - handlers.py
# Depsgraph pre/post handlers for Live Offset functionality.
# =====================================================================

import bpy
from mathutils import Quaternion, Vector

from .utils import (
    get_bone,
    has_non_default_offsets,
    offset_rotation_as_quat,
    write_pose_rotation_from_quat,
)
from .debug import log, log_section


# =====================================================================
# Handlers
# =====================================================================

def apply_live_offsets(scene, depsgraph=None):
    """
    depsgraph_update_post handler.
    Writes offset values directly to pose channels. No user intent
    tracking — channels are locked to offset values while Live Offset
    is on. The user's original pose is stored in pose_snapshot and
    restored when Live Offset is turned off.
    """
    props = scene.easy_retarget

    if not props.live_offset:
        return

    target_rig = props.target_rig
    source_rig = props.source_rig

    if not target_rig or not source_rig:
        return

    log_section(f"apply_live_offsets — {target_rig.name}")

    # Sort pairs parent-first
    def _depth(bone_name):
        bone = target_rig.data.bones.get(bone_name)
        if bone is None:
            return 0
        depth = 0
        current = bone.parent
        while current is not None:
            depth += 1
            current = current.parent
        return depth

    sorted_pairs = sorted(
        [item for item in props.bone_pairs if item.source_bone and item.target_bone],
        key=lambda item: _depth(item.target_bone)
    )
    log(f"  processing order: {[item.target_bone for item in sorted_pairs]}")

    for item in sorted_pairs:
        if not has_non_default_offsets(item):
            log(f"  [{item.target_bone}] SKIP — no non-default offsets")
            continue

        pbone = get_bone(target_rig, item.target_bone)
        if not pbone:
            log(f"  [{item.target_bone}] SKIP — pose bone not found")
            continue

        rot_mode = pbone.rotation_mode
        offset_quat = offset_rotation_as_quat(item.offset_rotation, rot_mode)
        sx, sy, sz = item.offset_scale

        pbone.location = Vector(item.offset_location)
        write_pose_rotation_from_quat(pbone, offset_quat)
        pbone.scale = Vector((sx, sy, sz))

        log(f"  [{item.target_bone}] WROTE offset_loc={tuple(item.offset_location)}")
        log(f"  [{item.target_bone}] WROTE offset_rot=({offset_quat.w:.4f},{offset_quat.x:.4f},{offset_quat.y:.4f},{offset_quat.z:.4f})")

    if bpy.context.screen:
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()



# =====================================================================
# Constraint Management
# =====================================================================

def disable_paired_constraints(target_rig, bone_pairs, disabled_collection):
    """
    Disable all currently-enabled constraints on paired target bones.
    Records each disabled constraint in disabled_collection so they can
    be restored later, even across Blender restarts.
    """
    if not target_rig or target_rig.type != 'ARMATURE':
        return

    disabled_collection.clear()

    for item in bone_pairs:
        if not item.target_bone:
            continue
        pbone = target_rig.pose.bones.get(item.target_bone)
        if not pbone:
            continue
        for con in pbone.constraints:
            if con.enabled:
                con.enabled = False
                entry = disabled_collection.add()
                entry.bone_name = item.target_bone
                entry.constraint_name = con.name
                log(f"  disabled constraint: [{item.target_bone}] {con.name}")


def restore_disabled_constraints(target_rig, disabled_collection):
    """
    Re-enable all constraints recorded in disabled_collection.
    Only re-enables constraints that still exist on the bone.
    """
    if not target_rig or target_rig.type != 'ARMATURE':
        return

    for entry in disabled_collection:
        pbone = target_rig.pose.bones.get(entry.bone_name)
        if not pbone:
            continue
        con = pbone.constraints.get(entry.constraint_name)
        if con:
            con.enabled = True
            log(f"  restored constraint: [{entry.bone_name}] {entry.constraint_name}")


# =====================================================================
# Pose Snapshot Utilities
# =====================================================================

def snapshot_pose(target_rig, snapshot_collection):
    """
    Store all bone pose channel values from target_rig into
    snapshot_collection (a CollectionProperty of BonePoseSnapshot).
    Covers all bones so unpaired bones are preserved too.
    """
    if not target_rig or target_rig.type != 'ARMATURE':
        return

    snapshot_collection.clear()

    for pbone in target_rig.pose.bones:
        entry = snapshot_collection.add()
        entry.bone_name = pbone.name
        entry.location = tuple(pbone.location)
        entry.rotation_quaternion = tuple(pbone.rotation_quaternion)
        entry.rotation_euler = (pbone.rotation_euler.x, pbone.rotation_euler.y, pbone.rotation_euler.z)
        entry.rotation_axis_angle = tuple(pbone.rotation_axis_angle)
        entry.scale = tuple(pbone.scale)
        entry.rotation_mode = pbone.rotation_mode

    log(f"  snapshot_pose: stored {len(snapshot_collection)} bones from {target_rig.name}")


def restore_pose_snapshot(target_rig, snapshot_collection):
    """
    Restore all bone pose channel values from snapshot_collection
    back to target_rig's pose bones.
    """
    if not target_rig or target_rig.type != 'ARMATURE':
        return

    for entry in snapshot_collection:
        pbone = target_rig.pose.bones.get(entry.bone_name)
        if not pbone:
            continue
        pbone.rotation_mode = entry.rotation_mode
        pbone.location = Vector(entry.location)
        pbone.rotation_quaternion = Quaternion(entry.rotation_quaternion)
        pbone.rotation_euler = Vector(entry.rotation_euler)
        pbone.rotation_axis_angle = tuple(entry.rotation_axis_angle)
        pbone.scale = Vector(entry.scale)

    log(f"  restore_pose_snapshot: restored {len(snapshot_collection)} bones to {target_rig.name}")


# =====================================================================
# Handler Registration
# =====================================================================

def register_handlers():
    """Register post depsgraph handler if not already registered."""
    if apply_live_offsets not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(apply_live_offsets)


def unregister_handlers():
    """Unregister post depsgraph handler if registered."""
    if apply_live_offsets in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(apply_live_offsets)
