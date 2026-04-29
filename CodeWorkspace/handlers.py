# =====================================================================
# EasyRetarget - handlers.py
# load_post handler — migrates legacy constraint names, then restores
# constraint toggle state after a file is loaded or Blender restarts.
# SpaceView3D draw handler — syncs bone selection in the viewport to
# the corresponding bone pair row in the N-panel.
# =====================================================================

import bpy
from .debug import log


# =====================================================================
# Selection Sync Draw Handler
# =====================================================================

# Module-level handle for the SpaceView3D draw handler so it can be
# removed on unregister.
_draw_handler = None


# Module-level tracking of the last active bone to avoid overwriting
# manual list selection on every redraw.
_last_active_bone: tuple = (None, None)  # (bone_name, owner_name)


def _sync_bone_pair_selection():
    """
    SpaceView3D POST_PIXEL draw callback.
    Fires on every viewport redraw. Only updates bone_pairs_index when
    the active pose bone has changed since the last redraw, so manual
    list selection is not constantly overwritten.
    """
    global _last_active_bone

    try:
        active_pose_bone = bpy.context.active_pose_bone
    except AttributeError as e:
        log(f"  sync_bone_pair_selection: AttributeError accessing active_pose_bone: {e}")
        return

    if active_pose_bone is None:
        return

    owner = active_pose_bone.id_data
    bone_name = active_pose_bone.name
    owner_name = owner.name if owner else None

    # Bail if the active bone hasn't changed since the last redraw.
    if (bone_name, owner_name) == _last_active_bone:
        return

    _last_active_bone = (bone_name, owner_name)

    try:
        scene = bpy.context.scene
        props = scene.easy_retarget
    except AttributeError as e:
        log(f"  sync_bone_pair_selection: AttributeError accessing scene props: {e}")
        return

    source_rig = props.source_rig
    target_rig = props.target_rig

    if owner == source_rig:
        field = 'source_bone'
    elif owner == target_rig:
        field = 'target_bone'
    else:
        log(f"  sync_bone_pair_selection: bone '{bone_name}' owner '{owner_name}' is neither source nor target rig")
        return

    log(f"  sync_bone_pair_selection: active bone changed to '{bone_name}' on {field} rig '{owner_name}'")

    for i, item in enumerate(props.bone_pairs):
        if getattr(item, field) == bone_name:
            if props.bone_pairs_index != i:
                props.bone_pairs_index = i
                log(f"  sync_bone_pair_selection: set bone_pairs_index to {i}")
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            for region in area.regions:
                                if region.type == 'UI':
                                    region.tag_redraw()
            return

    log(f"  sync_bone_pair_selection: no matching pair found for '{bone_name}'")


# =====================================================================
# Load Post Handler
# =====================================================================

@bpy.app.handlers.persistent
def on_load_post(filepath):
    """
    load_post handler. Decorated with @persistent so it survives file
    loads and fires on every file open for the lifetime of the session.
    Without @persistent, Blender removes the handler before firing it,
    meaning it would never run.

    1. Runs the legacy constraint name migration: renames any constraint
       named "EasyRetarget" to "EasyRetarget_Rotation" on all paired
       target bones (one-time, silent, non-destructive).

    2. Re-applies the constraint toggle state to all EasyRetarget
       constraints on paired bones:
         - ALL_OFF: ensures all constraints are disabled.
         - ALL_ON:  ensures all constraints are enabled.
         - CUSTOM:  restores individual enabled states from
                    constraint_state_snapshot.
    """
    for scene in bpy.data.scenes:
        try:
            props = scene.easy_retarget
            _migrate_constraint_names(props)
            _apply_toggle_state(props)
        except Exception as e:
            log(f"  on_load_post error for scene '{scene.name}': {e}")


def _migrate_constraint_names(props):
    """
    Rename legacy 'EasyRetarget' rotation constraints to 'EasyRetarget_Rotation'.
    Safe to run multiple times — no-op when no legacy constraints are present.
    """
    from .constraint_utils import ROTATION_CONSTRAINT_NAME
    from .utils import get_bone

    target_rig = props.target_rig
    if not target_rig:
        return

    for item in props.bone_pairs:
        if not item.target_bone:
            continue
        pbone = get_bone(target_rig, item.target_bone)
        if not pbone:
            continue
        legacy_con = pbone.constraints.get("EasyRetarget")
        if legacy_con:
            legacy_con.name = ROTATION_CONSTRAINT_NAME
            log(f"  migrate: renamed 'EasyRetarget' → '{ROTATION_CONSTRAINT_NAME}' on {item.target_bone}")


def _apply_toggle_state(props):
    """
    Apply the stored constraint_toggle state to all paired bones on file load.

    CUSTOM:            restores individual EasyRetarget enabled states from
                       constraint_state_snapshot.
    EASYRETARGET_ONLY: re-disables constraints listed in other_constraint_snapshot
                       and force-enables EasyRetarget constraints.
    ALL_OFF / ALL_ON:  sets all EasyRetarget constraints to disabled / enabled.
    """
    from .constraint_utils import (
        find_rotation_constraint, find_location_constraint,
        ROTATION_CONSTRAINT_NAME, LOCATION_CONSTRAINT_NAME,
    )
    from .utils import get_bone

    target_rig = props.target_rig
    if not target_rig:
        return

    toggle = props.constraint_toggle

    if toggle == 'CUSTOM':
        snapshot = {entry.bone_name: entry.enabled
                    for entry in props.constraint_state_snapshot}
        if snapshot:
            for item in props.bone_pairs:
                if not item.target_bone:
                    continue
                pbone = get_bone(target_rig, item.target_bone)
                if not pbone:
                    continue
                if item.target_bone in snapshot:
                    enabled = snapshot[item.target_bone]
                    rot_con = find_rotation_constraint(pbone)
                    loc_con = find_location_constraint(pbone)
                    if rot_con:
                        rot_con.enabled = enabled
                    if loc_con:
                        loc_con.enabled = enabled
        return

    if toggle == 'EASYRETARGET_ONLY':
        # Re-disable all constraints that were snapshotted before the switch.
        for entry in props.other_constraint_snapshot:
            pbone = get_bone(target_rig, entry.bone_name)
            if not pbone:
                continue
            con = pbone.constraints.get(entry.constraint_name)
            if con:
                con.enabled = False
                log(f"  on_load_post: {entry.bone_name} '{entry.constraint_name}' disabled (EASYRETARGET_ONLY)")
        # Force-enable EasyRetarget constraints on paired bones.
        for item in props.bone_pairs:
            if not item.target_bone:
                continue
            pbone = get_bone(target_rig, item.target_bone)
            if not pbone:
                continue
            rot_con = find_rotation_constraint(pbone)
            loc_con = find_location_constraint(pbone)
            if rot_con:
                rot_con.enabled = True
                log(f"  on_load_post: {item.target_bone} rotation constraint enabled=True (EASYRETARGET_ONLY)")
            if loc_con:
                loc_con.enabled = True
                log(f"  on_load_post: {item.target_bone} location constraint enabled=True (EASYRETARGET_ONLY)")
        return

    target_enabled = (toggle == 'ALL_ON')
    for item in props.bone_pairs:
        if not item.target_bone:
            continue
        pbone = get_bone(target_rig, item.target_bone)
        if not pbone:
            continue
        rot_con = find_rotation_constraint(pbone)
        loc_con = find_location_constraint(pbone)
        if rot_con:
            rot_con.enabled = target_enabled
            log(f"  on_load_post: {item.target_bone} rotation constraint enabled={target_enabled}")
        if loc_con:
            loc_con.enabled = target_enabled
            log(f"  on_load_post: {item.target_bone} location constraint enabled={target_enabled}")


# =====================================================================
# Handler Registration
# =====================================================================

def register_handlers():
    """Register all EasyRetarget handlers."""
    global _draw_handler

    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)

    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _sync_bone_pair_selection, (), 'WINDOW', 'POST_PIXEL'
        )


def unregister_handlers():
    """Unregister all EasyRetarget handlers."""
    global _draw_handler, _last_active_bone

    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)

    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None

    _last_active_bone = (None, None)
