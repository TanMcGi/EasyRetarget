# =====================================================================
# EasyRetarget - operators_offset.py
# Offset editing operators: EditOffsets, MatchSourceOffsets,
# MatchAllOffsets, MatchRotationMode, ResetOffsets.
# =====================================================================

import uuid
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, IntProperty
from mathutils import Quaternion, Vector

from . import handlers
from .debug import log, log_section, _get_prefs
from .utils import (
    get_bone,
    has_non_default_offsets,
    convert_rotation_offset,
    force_depsgraph_update,
)


# =====================================================================
# Shared matching helper
# =====================================================================

def _run_match_sequence(context, target_rig, source_rig, valid_pairs, pair_index_to_write=None):
    """
    Core matching sequence shared by Match All and Match Source.

    Steps:
    1. Snapshot entire target armature pose.
    2. Reset ALL target armature bone channels to identity/zero.
    3. Force update.
    4. Disable all currently-enabled constraints on paired target bones.
    5. Add Copy Rotation constraints with a unique name tag.
    6. Force update.
    7. Enter Pose Mode, select all, apply visual transform via VIEW_3D override.
    8. Read baked channels — store as offset for:
         - All pairs if pair_index_to_write is None (Match All)
         - Only the pair at pair_index_to_write (Match Source)
    9. Clear paired bone channels back to identity.
    10. Remove only constraints matching our unique name tag.
    11. Re-enable constraints that were disabled in step 4.
    12. Restore full armature snapshot from step 1.
    13. Force update.

    Returns count of bone pairs updated.
    """
    import bpy

    # ── Step 1: Snapshot entire target armature ───────────────────────
    # Use a local dict rather than the scene CollectionProperty since
    # this is a temporary working snapshot only needed within this call.
    local_snapshot = {}
    for pbone in target_rig.pose.bones:
        local_snapshot[pbone.name] = {
            'rotation_mode': pbone.rotation_mode,
            'location': pbone.location.copy(),
            'rotation_quaternion': pbone.rotation_quaternion.copy(),
            'rotation_euler': pbone.rotation_euler.copy(),
            'rotation_axis_angle': tuple(pbone.rotation_axis_angle),
            'scale': pbone.scale.copy(),
        }
    log(f"  snapshot taken: {len(local_snapshot)} bones")

    # ── Step 2: Reset ALL bone channels on the target armature ────────
    for pbone in target_rig.pose.bones:
        pbone.location = (0.0, 0.0, 0.0)
        pbone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pbone.rotation_euler = (0.0, 0.0, 0.0)
        pbone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        pbone.scale = (1.0, 1.0, 1.0)

    # ── Step 3: Force update ──────────────────────────────────────────
    context.view_layer.update()

    # ── Step 4: Disable existing constraints on paired target bones ───
    constraint_tag = f"EasyRetarget_{uuid.uuid4().hex}"
    disabled_constraints = []  # (pbone, constraint) that we disabled

    for item in valid_pairs:
        tgt_pbone = get_bone(target_rig, item.target_bone)
        if not tgt_pbone:
            continue
        for con in tgt_pbone.constraints:
            if con.enabled:
                con.enabled = False
                disabled_constraints.append((tgt_pbone, con))

    # ── Step 5: Add Copy Rotation constraints ─────────────────────────
    added_constraints = []  # (pbone, constraint) we added

    for item in valid_pairs:
        src_pbone = get_bone(source_rig, item.source_bone)
        tgt_pbone = get_bone(target_rig, item.target_bone)
        if not src_pbone or not tgt_pbone:
            continue

        # Match rotation mode
        tgt_pbone.rotation_mode = src_pbone.rotation_mode

        con = tgt_pbone.constraints.new('COPY_ROTATION')
        con.name = constraint_tag
        con.target = source_rig
        con.subtarget = item.source_bone
        con.target_space = 'WORLD'
        con.owner_space = 'WORLD'
        con.mix_mode = 'REPLACE'
        added_constraints.append((tgt_pbone, con))

        log_section(f"  constraint added: {item.target_bone} <- {item.source_bone}")

    # ── Step 6: Force update ──────────────────────────────────────────
    context.view_layer.update()

    # ── Step 7: Apply visual transform via VIEW_3D context override ───
    prev_active = context.view_layer.objects.active
    context.view_layer.objects.active = target_rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')

    view3d_area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)
    if view3d_area:
        view3d_region = next((r for r in view3d_area.regions if r.type == 'WINDOW'), None)
        if view3d_region:
            with context.temp_override(
                area=view3d_area,
                region=view3d_region,
                active_object=target_rig,
            ):
                bpy.ops.pose.visual_transform_apply()
            log("  visual_transform_apply succeeded")
        else:
            log("  WARNING: No WINDOW region in VIEW_3D")
    else:
        log("  WARNING: No VIEW_3D area found")

    # ── Step 8 & 9: Read baked channels, store offsets, clear channels ─
    count = 0
    for i, item in enumerate(valid_pairs):
        tgt_pbone = get_bone(target_rig, item.target_bone)
        if not tgt_pbone:
            continue

        rot_mode = tgt_pbone.rotation_mode

        # Only write offset if this is the target pair (Match Source)
        # or if we're writing all pairs (Match All)
        should_write = (pair_index_to_write is None) or (i == pair_index_to_write)

        if should_write:
            log_section(f"  baked — tgt={item.target_bone} rot_mode={rot_mode}")
            if rot_mode == 'QUATERNION':
                q = tgt_pbone.rotation_quaternion.normalized()
                item.offset_rotation = (q.w, q.x, q.y, q.z)
                log(f"  baked_quat=({q.w:.4f},{q.x:.4f},{q.y:.4f},{q.z:.4f})")
            elif rot_mode == 'AXIS_ANGLE':
                aa = tgt_pbone.rotation_axis_angle
                item.offset_rotation = (aa[0], aa[1], aa[2], aa[3])
                log(f"  baked_axis_angle={tuple(aa)}")
            else:
                e = tgt_pbone.rotation_euler
                item.offset_rotation = (0.0, e.x, e.y, e.z)
                log(f"  baked_euler=({e.x:.4f},{e.y:.4f},{e.z:.4f})")
            count += 1

        # Clear paired bone channels regardless (cleanup)
        tgt_pbone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        tgt_pbone.rotation_euler = (0.0, 0.0, 0.0)
        tgt_pbone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)

    # ── Step 10: Remove only our constraints ──────────────────────────
    for pbone, con in added_constraints:
        pbone.constraints.remove(con)

    # ── Step 11: Re-enable previously disabled constraints ────────────
    for pbone, con in disabled_constraints:
        con.enabled = True

    # ── Step 12: Restore full armature snapshot ───────────────────────
    for pbone in target_rig.pose.bones:
        snap = local_snapshot.get(pbone.name)
        if not snap:
            continue
        pbone.rotation_mode = snap['rotation_mode']
        pbone.location = snap['location']
        pbone.rotation_quaternion = snap['rotation_quaternion']
        pbone.rotation_euler = snap['rotation_euler']
        pbone.rotation_axis_angle = snap['rotation_axis_angle']
        pbone.scale = snap['scale']

    # Return to Object Mode and restore active object
    bpy.ops.object.mode_set(mode='OBJECT')
    context.view_layer.objects.active = prev_active

    # ── Step 13: Force update ─────────────────────────────────────────
    context.view_layer.update()

    return count


# =====================================================================
# Operators
# =====================================================================

class EASYRETARGET_OT_EditOffsets(Operator):
    """Open the offset editor popup for a bone pair."""
    bl_idname = "easy_retarget.edit_offsets"
    bl_label = "Edit Bone Offsets"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pair_index: IntProperty(options={'SKIP_SAVE'})

    _snapshot_location: tuple = (0.0, 0.0, 0.0)
    _snapshot_rotation: tuple = (0.0, 0.0, 0.0, 0.0)
    _snapshot_scale: tuple = (1.0, 1.0, 1.0)

    def invoke(self, context, event):
        props = context.scene.easy_retarget
        if not (0 <= self.pair_index < len(props.bone_pairs)):
            return {'CANCELLED'}

        item = props.bone_pairs[self.pair_index]
        self._snapshot_location = tuple(item.offset_location)
        self._snapshot_rotation = tuple(item.offset_rotation)
        self._snapshot_scale = tuple(item.offset_scale)

        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        props = context.scene.easy_retarget

        if not (0 <= self.pair_index < len(props.bone_pairs)):
            layout.label(text="Invalid bone pair index.", icon='ERROR')
            return

        item = props.bone_pairs[self.pair_index]
        source_bone = get_bone(props.source_rig, item.source_bone)
        target_bone = get_bone(props.target_rig, item.target_bone)

        # ── Rotation Mode Mismatch Warning ───────────────────────────
        if source_bone and target_bone:
            src_mode = source_bone.rotation_mode
            tgt_mode = target_bone.rotation_mode
            if src_mode != tgt_mode:
                warn_box = layout.box()
                warn_box.alert = True
                col = warn_box.column(align=True)
                col.label(text="Rotation mode mismatch!", icon='ERROR')
                col.label(text=f"Source: {src_mode}   Target: {tgt_mode}")
                col.separator()
                match_op = col.operator(
                    "easy_retarget.match_rotation_mode",
                    text="Match Source Rotation Mode",
                    icon='DRIVER_ROTATIONAL_DIFFERENCE',
                )
                match_op.pair_index = self.pair_index
                layout.separator()

        # ── Location ─────────────────────────────────────────────────
        loc_box = layout.box()
        loc_box.label(text="Location", icon='OBJECT_ORIGIN')
        col = loc_box.column(align=True)
        col.prop(item, "offset_location", index=0, text="X")
        col.prop(item, "offset_location", index=1, text="Y")
        col.prop(item, "offset_location", index=2, text="Z")

        # ── Rotation ─────────────────────────────────────────────────
        rot_box = layout.box()
        rot_box.label(text="Rotation", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        col = rot_box.column(align=True)

        rot_mode = target_bone.rotation_mode if target_bone else 'XYZ'

        if rot_mode == 'QUATERNION':
            col.prop(item, "offset_rotation", index=0, text="W")
            col.prop(item, "offset_rotation", index=1, text="X")
            col.prop(item, "offset_rotation", index=2, text="Y")
            col.prop(item, "offset_rotation", index=3, text="Z")
        elif rot_mode == 'AXIS_ANGLE':
            col.prop(item, "offset_rotation", index=0, text="Angle")
            col.prop(item, "offset_rotation", index=1, text="X")
            col.prop(item, "offset_rotation", index=2, text="Y")
            col.prop(item, "offset_rotation", index=3, text="Z")
        else:
            col.prop(item, "offset_rotation", index=1, text="X")
            col.prop(item, "offset_rotation", index=2, text="Y")
            col.prop(item, "offset_rotation", index=3, text="Z")

        # ── Scale ─────────────────────────────────────────────────────
        scale_box = layout.box()
        scale_box.label(text="Scale", icon='FULLSCREEN_ENTER')
        col = scale_box.column(align=True)
        col.prop(item, "offset_scale", index=0, text="X")
        col.prop(item, "offset_scale", index=1, text="Y")
        col.prop(item, "offset_scale", index=2, text="Z")

        layout.separator()

        # ── Match Source Button ───────────────────────────────────────
        match_src_op = layout.operator(
            "easy_retarget.match_source_offsets",
            text="Match Source",
            icon='SNAP_ON',
        )
        match_src_op.pair_index = self.pair_index

        # ── Reset Button ──────────────────────────────────────────────
        reset_op = layout.operator(
            "easy_retarget.reset_offsets",
            text="Reset to Default",
            icon='LOOP_BACK',
        )
        reset_op.pair_index = self.pair_index

    def execute(self, context):
        return {'FINISHED'}

    def cancel(self, context):
        """Restore offset values to their pre-invoke snapshot."""
        props = context.scene.easy_retarget
        if 0 <= self.pair_index < len(props.bone_pairs):
            item = props.bone_pairs[self.pair_index]
            item.offset_location = self._snapshot_location
            item.offset_rotation = self._snapshot_rotation
            item.offset_scale = self._snapshot_scale
        force_depsgraph_update(context=context)


class EASYRETARGET_OT_MatchSourceOffsets(Operator):
    """
    Calculate and apply the rotation offset for a single bone pair.
    Snapshots the full armature, resets all bones, applies constraint,
    reads result, then restores the snapshot — same as Match All but
    only writes the offset for this one pair.
    """
    bl_idname = "easy_retarget.match_source_offsets"
    bl_label = "Match Source"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pair_index: IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        props = context.scene.easy_retarget

        if not (0 <= self.pair_index < len(props.bone_pairs)):
            return {'CANCELLED'}
        if not props.source_rig or not props.target_rig:
            self.report({'WARNING'}, "EasyRetarget: Source and Target rigs required.")
            return {'CANCELLED'}

        source_rig = props.source_rig
        target_rig = props.target_rig

        # Build valid pairs list (all populated pairs needed for full reset)
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

        valid_pairs = [
            item for item in props.bone_pairs
            if item.source_bone and item.target_bone
        ]
        valid_pairs.sort(key=lambda item: _depth(item.target_bone))

        if not valid_pairs:
            self.report({'WARNING'}, "EasyRetarget: No populated bone pairs found.")
            return {'CANCELLED'}

        # Find the index of our target pair within valid_pairs
        target_item = props.bone_pairs[self.pair_index]
        try:
            write_index = next(
                i for i, item in enumerate(valid_pairs)
                if item.source_bone == target_item.source_bone
                and item.target_bone == target_item.target_bone
            )
        except StopIteration:
            self.report({'WARNING'}, "EasyRetarget: Bone pair not found in populated pairs.")
            return {'CANCELLED'}

        log_section(f"MatchSourceOffsets — pair {self.pair_index} ({target_item.source_bone} -> {target_item.target_bone})")

        count = _run_match_sequence(
            context, target_rig, source_rig,
            valid_pairs,
            pair_index_to_write=write_index,
        )

        force_depsgraph_update(context=context)
        self.report({'INFO'}, f"EasyRetarget: Match Source complete.")
        return {'FINISHED'}


class EASYRETARGET_OT_MatchAllOffsets(Operator):
    """
    Calculate and apply rotation offsets for all bone pairs.
    Snapshots the full armature, resets all bones, applies constraints,
    reads results, then restores the snapshot.
    """
    bl_idname = "easy_retarget.match_all_offsets"
    bl_label = "Match All"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        warn_box = layout.box()
        warn_box.alert = True
        col = warn_box.column(align=True)
        col.scale_y = 1.4
        col.label(text="This will reset and recalculate all rotation offsets.", icon='ERROR')
        col.label(text="Any manually set offset values will be overwritten.")

    def execute(self, context):
        props = context.scene.easy_retarget

        if not props.source_rig:
            self.report({'WARNING'}, "EasyRetarget: No Source Rig selected.")
            return {'CANCELLED'}
        if not props.target_rig:
            self.report({'WARNING'}, "EasyRetarget: No Target Rig selected.")
            return {'CANCELLED'}

        source_rig = props.source_rig
        target_rig = props.target_rig

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

        valid_pairs = [
            item for item in props.bone_pairs
            if item.source_bone and item.target_bone
        ]
        valid_pairs.sort(key=lambda item: _depth(item.target_bone))

        if not valid_pairs:
            self.report({'INFO'}, "EasyRetarget: No populated bone pairs to process.")
            return {'CANCELLED'}

        log_section("MatchAllOffsets")

        count = _run_match_sequence(
            context, target_rig, source_rig,
            valid_pairs,
            pair_index_to_write=None,
        )

        force_depsgraph_update(context=context)
        self.report({'INFO'}, f"EasyRetarget: Match All complete. {count} bone pairs updated.")
        return {'FINISHED'}


class EASYRETARGET_OT_MatchRotationMode(Operator):
    """Set the target bone rotation mode to match the source bone and convert offset values."""
    bl_idname = "easy_retarget.match_rotation_mode"
    bl_label = "Match Source Rotation Mode"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pair_index: IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        props = context.scene.easy_retarget

        if not (0 <= self.pair_index < len(props.bone_pairs)):
            return {'CANCELLED'}

        item = props.bone_pairs[self.pair_index]
        source_bone = get_bone(props.source_rig, item.source_bone)
        target_bone = get_bone(props.target_rig, item.target_bone)

        if not source_bone or not target_bone:
            self.report({'WARNING'}, "EasyRetarget: Could not find source or target bone.")
            return {'CANCELLED'}

        from_mode = target_bone.rotation_mode
        to_mode = source_bone.rotation_mode

        if from_mode == to_mode:
            return {'FINISHED'}

        converted = convert_rotation_offset(item.offset_rotation, from_mode, to_mode)
        item.offset_rotation = converted
        target_bone.rotation_mode = to_mode

        if context.area:
            context.area.tag_redraw()

        return {'FINISHED'}


class EASYRETARGET_OT_ResetOffsets(Operator):
    """Reset all offset values on a bone pair to their defaults."""
    bl_idname = "easy_retarget.reset_offsets"
    bl_label = "Reset Offsets to Default"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pair_index: IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        props = context.scene.easy_retarget

        if not (0 <= self.pair_index < len(props.bone_pairs)):
            return {'CANCELLED'}

        item = props.bone_pairs[self.pair_index]
        item.offset_location = (0.0, 0.0, 0.0)
        item.offset_rotation = (0.0, 0.0, 0.0, 0.0)
        item.offset_scale = (1.0, 1.0, 1.0)

        force_depsgraph_update(context=context)
        return {'FINISHED'}
