# =====================================================================
# EasyRetarget - operators_list.py
# Bone pair list management operators:
# Add, Remove, Move, AutoPopulate, AddBonePairFromSelection,
# ConfirmMatchWarning, ClearAllWarnings.
# =====================================================================

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, IntProperty

from .constraint_utils import (
    find_rotation_constraint,
    find_location_constraint,
    remove_rotation_constraint,
    remove_location_constraint,
)
from .utils import get_bone


class EASYRETARGET_OT_AddBonePair(Operator):
    """Add a new blank bone pair entry."""
    bl_idname = "easy_retarget.add_bone_pair"
    bl_label = "Add Bone Pair"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.easy_retarget
        item = props.bone_pairs.add()
        item.source_bone = ""
        item.target_bone = ""
        item.previous_target_bone = ""
        item.match_status = 'NONE'
        item.match_reason = ""
        item.is_manual = True
        props.bone_pairs_index = len(props.bone_pairs) - 1
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class EASYRETARGET_OT_RemoveBonePair(Operator):
    """Remove the currently selected bone pair entry."""
    bl_idname = "easy_retarget.remove_bone_pair"
    bl_label = "Remove Bone Pair"
    bl_options = {'REGISTER', 'UNDO'}

    _has_constraint: bool = False

    def invoke(self, context, event):
        props = context.scene.easy_retarget
        pairs = props.bone_pairs
        index = props.bone_pairs_index

        if not (pairs and 0 <= index < len(pairs)):
            return {'CANCELLED'}

        item = pairs[index]
        if props.target_rig and item.target_bone:
            pbone = get_bone(props.target_rig, item.target_bone)
            self._has_constraint = bool(
                pbone and (find_rotation_constraint(pbone) or find_location_constraint(pbone))
            )
        else:
            self._has_constraint = False

        if self._has_constraint:
            return context.window_manager.invoke_props_dialog(self, width=360)

        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        warn_box = layout.box()
        warn_box.alert = True
        col = warn_box.column(align=True)
        col.scale_y = 1.4
        col.label(text="This bone pair has EasyRetarget constraints.", icon='ERROR')
        col.label(text="Removing the pair will also remove all constraints from the target bone.")

    def execute(self, context):
        props = context.scene.easy_retarget
        pairs = props.bone_pairs
        index = props.bone_pairs_index

        if not (pairs and 0 <= index < len(pairs)):
            return {'CANCELLED'}

        item = pairs[index]

        # Remove all EasyRetarget constraints from the target bone.
        if props.target_rig and item.target_bone:
            pbone = get_bone(props.target_rig, item.target_bone)
            if pbone:
                remove_rotation_constraint(pbone)
                remove_location_constraint(pbone)

        pairs.remove(index)
        props.bone_pairs_index = max(0, index - 1)

        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class EASYRETARGET_OT_MoveBonePair(Operator):
    """Move a bone pair entry up or down in the list."""
    bl_idname = "easy_retarget.move_bone_pair"
    bl_label = "Move Bone Pair"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        items=[
            ('UP',   "Up",   "Move entry up"),
            ('DOWN', "Down", "Move entry down"),
        ]
    )

    def execute(self, context):
        props = context.scene.easy_retarget
        pairs = props.bone_pairs
        index = props.bone_pairs_index
        count = len(pairs)

        if self.direction == 'UP' and index > 0:
            pairs.move(index, index - 1)
            props.bone_pairs_index = index - 1
        elif self.direction == 'DOWN' and index < count - 1:
            pairs.move(index, index + 1)
            props.bone_pairs_index = index + 1

        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


# ── Dynamic description text used in AutoPopulate dialog ─────────────

_REBUILD_DESCRIPTIONS = {
    'FILL_GAPS':    "Re-evaluate unmatched, warning, and error pairs. Confirmed and manual pairs are unchanged.",
    'RERUN':        "Re-run matching on all bones. Confirmed and manual pairs are preserved.",
    'FULL_REBUILD': "Clear all pairs and rebuild from scratch. Nothing is preserved.",
}


class EASYRETARGET_OT_AutoPopulate(Operator):
    """Clear and rebuild the bone pair list using the matching algorithm."""
    bl_idname = "easy_retarget.auto_populate"
    bl_label = "Auto Populate"
    bl_options = {'REGISTER', 'UNDO'}

    rebuild_mode: EnumProperty(
        name="Rebuild Mode",
        description="How to handle the existing bone pair list",
        items=[
            ('FILL_GAPS',    "Fill Gaps Only",    "Re-evaluate only unmatched, warning, and error pairs"),
            ('RERUN',        "Re-run Algorithm",  "Re-run the algorithm; preserve manual entries"),
            ('FULL_REBUILD', "Full Rebuild",       "Clear everything and rebuild from scratch"),
        ],
        default='RERUN',
    )

    def invoke(self, context, event):
        props = context.scene.easy_retarget

        if not props.source_rig:
            self.report({'WARNING'}, "EasyRetarget: No Source Rig selected.")
            return {'CANCELLED'}

        if not props.target_rig:
            self.report({'WARNING'}, "EasyRetarget: No Target Rig selected.")
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout

        layout.label(text="Rebuild Mode")
        col = layout.column(align=True)
        col.prop_enum(self, "rebuild_mode", 'FILL_GAPS')
        col.prop_enum(self, "rebuild_mode", 'RERUN')
        col.prop_enum(self, "rebuild_mode", 'FULL_REBUILD')

        layout.separator()

        # Dynamic description box — alert only for full rebuild.
        desc = _REBUILD_DESCRIPTIONS.get(self.rebuild_mode, "")
        box = layout.box()
        box.alert = (self.rebuild_mode == 'FULL_REBUILD')
        col = box.column(align=True)
        col.scale_y = 1.2
        icon = 'ERROR' if self.rebuild_mode == 'FULL_REBUILD' else 'INFO'
        col.label(text=desc, icon=icon)

    def execute(self, context):
        from .matching import match_bones
        from .debug import reset_ap_log, log_autopopulate, log_ap_section

        props       = context.scene.easy_retarget
        source_rig  = props.source_rig
        target_rig  = props.target_rig
        mode        = self.rebuild_mode

        # ── Start a fresh AutoPopulate log ────────────────────────────
        reset_ap_log()
        log_ap_section("EasyRetarget AutoPopulate")
        log_autopopulate(f"Mode:       {mode}")
        log_autopopulate(f"Source Rig: {source_rig.name}")
        log_autopopulate(f"Target Rig: {target_rig.name}")

        # ── Determine bone pools ──────────────────────────────────────
        # Use selected pose bones when in Pose Mode with a selection on
        # both rigs; otherwise fall back to all bones.
        src_pool = []
        tgt_pool = []

        if context.mode == 'POSE' and context.selected_pose_bones:
            selected = context.selected_pose_bones
            src_selected = [b.name for b in selected if b.id_data == source_rig]
            tgt_selected = [b.name for b in selected if b.id_data == target_rig]
            if src_selected and tgt_selected:
                src_pool = src_selected
                tgt_pool = tgt_selected
                log_autopopulate(
                    f"Using selected bones — "
                    f"source: {len(src_pool)}, target: {len(tgt_pool)}"
                )

        if not src_pool:
            src_pool = [b.name for b in source_rig.data.bones]
            tgt_pool = [b.name for b in target_rig.data.bones]
            log_autopopulate(
                f"Using all bones — "
                f"source: {len(src_pool)}, target: {len(tgt_pool)}"
            )

        # ── Collect pairs to preserve ─────────────────────────────────
        preserved: list[dict] = []   # list of attribute dicts for kept items

        if mode == 'FILL_GAPS':
            # Keep all CONFIRMED pairs (algorithm or manually confirmed).
            for item in props.bone_pairs:
                if item.match_status == 'CONFIRMED':
                    preserved.append(_snapshot_item(item))
                    log_autopopulate(
                        f"[PRESERVED] {item.source_bone} → {item.target_bone}"
                    )

        elif mode == 'RERUN':
            # Keep only is_manual=True pairs.
            for item in props.bone_pairs:
                if item.is_manual:
                    preserved.append(_snapshot_item(item))
                    log_autopopulate(
                        f"[PRESERVED] {item.source_bone} → {item.target_bone} (manual)"
                    )

        # FULL_REBUILD: nothing preserved.

        # ── Determine which source/target bones still need matching ───
        preserved_src = {p['source_bone'] for p in preserved}
        preserved_tgt = {p['target_bone']  for p in preserved}

        remaining_src = [n for n in src_pool if n not in preserved_src]
        remaining_tgt = [n for n in tgt_pool if n not in preserved_tgt]

        log_ap_section("Matching")
        log_autopopulate(
            f"Bones to match — source: {len(remaining_src)}, "
            f"target: {len(remaining_tgt)}"
        )

        # ── Run the matching algorithm ────────────────────────────────
        results = match_bones(remaining_src, remaining_tgt)

        # ── Log results ───────────────────────────────────────────────
        n_confirmed = sum(1 for r in results if r.status == 'CONFIRMED')
        n_warning   = sum(1 for r in results if r.status == 'WARNING')
        n_error     = sum(1 for r in results if r.status == 'ERROR')

        for r in results:
            tag = f"[{r.status:9s}]"
            tgt = r.target_name if r.target_name else "(no match)"
            log_autopopulate(f"{tag} {r.source_name} → {tgt}")
            if r.status in ('WARNING', 'ERROR'):
                log_autopopulate(f"           {r.reason}")

        log_ap_section("Summary")
        log_autopopulate(f"Preserved:  {len(preserved)}")
        log_autopopulate(f"Confirmed:  {n_confirmed}")
        log_autopopulate(f"Warnings:   {n_warning}")
        log_autopopulate(f"Errors:     {n_error}")

        # ── Rebuild the pair list ─────────────────────────────────────
        props.bone_pairs.clear()
        props.bone_pairs_index = 0

        # Write preserved pairs first (maintains their original relative order).
        for snap in preserved:
            item = props.bone_pairs.add()
            _restore_item(item, snap)

        # Write matched results (errors included so the user can see them).
        for r in results:
            item = props.bone_pairs.add()
            item.source_bone          = r.source_name
            item.target_bone          = r.target_name
            item.previous_target_bone = r.target_name
            item.match_status         = r.status
            item.match_reason         = r.reason if r.status == 'WARNING' else ""
            item.is_manual            = False

        props.bone_pairs_index = 0

        if context.area:
            context.area.tag_redraw()

        total = len(props.bone_pairs)
        self.report(
            {'INFO'},
            f"EasyRetarget: Auto Populate complete. "
            f"{total} pairs — {n_confirmed} matched, "
            f"{n_warning} warning(s), {n_error} error(s).",
        )
        return {'FINISHED'}


def _snapshot_item(item) -> dict:
    """Capture all relevant fields from a BonePairItem into a plain dict."""
    return {
        'source_bone':          item.source_bone,
        'target_bone':          item.target_bone,
        'previous_target_bone': item.previous_target_bone,
        'match_status':         item.match_status,
        'match_reason':         item.match_reason,
        'is_manual':            item.is_manual,
        'rotation_expanded':    item.rotation_expanded,
        'location_expanded':    item.location_expanded,
        'rot_offset_x':         item.rot_offset_x,
        'rot_offset_y':         item.rot_offset_y,
        'rot_offset_z':         item.rot_offset_z,
        'loc_offset_x':         item.loc_offset_x,
        'loc_offset_y':         item.loc_offset_y,
        'loc_offset_z':         item.loc_offset_z,
    }


def _restore_item(item, snap: dict):
    """Write a snapshot dict back to a BonePairItem."""
    item.source_bone          = snap['source_bone']
    item.target_bone          = snap['target_bone']
    item.previous_target_bone = snap['previous_target_bone']
    item.match_status         = snap['match_status']
    item.match_reason         = snap['match_reason']
    item.is_manual            = snap['is_manual']
    item.rotation_expanded    = snap['rotation_expanded']
    item.location_expanded    = snap['location_expanded']
    item.rot_offset_x         = snap['rot_offset_x']
    item.rot_offset_y         = snap['rot_offset_y']
    item.rot_offset_z         = snap['rot_offset_z']
    item.loc_offset_x         = snap['loc_offset_x']
    item.loc_offset_y         = snap['loc_offset_y']
    item.loc_offset_z         = snap['loc_offset_z']


class EASYRETARGET_OT_ConfirmMatchWarning(Operator):
    """
    Confirm a low-confidence AutoPopulate match, promoting it to a
    manually confirmed pair and clearing the warning status.
    """
    bl_idname = "easy_retarget.confirm_match_warning"
    bl_label = "Confirm Match"
    bl_options = {'REGISTER', 'UNDO'}

    pair_index: IntProperty(default=0, options={'HIDDEN'})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        props = context.scene.easy_retarget
        layout = self.layout

        pairs = props.bone_pairs
        if not (0 <= self.pair_index < len(pairs)):
            layout.label(text="Invalid pair index.", icon='ERROR')
            return

        item = pairs[self.pair_index]

        info_box = layout.box()
        col = info_box.column(align=True)
        col.label(
            text=f"Source:  {item.source_bone}",
            icon='BONE_DATA',
        )
        col.label(
            text=f"Target:  {item.target_bone}",
            icon='BONE_DATA',
        )

        layout.separator()

        warn_box = layout.box()
        warn_box.alert = True
        warn_col = warn_box.column(align=True)
        warn_col.scale_y = 1.2
        warn_col.label(text=item.match_reason, icon='ERROR')

        layout.separator()
        layout.label(text="Confirm this pairing? It will be marked as manually verified.")

    def execute(self, context):
        props = context.scene.easy_retarget
        pairs = props.bone_pairs

        if not (0 <= self.pair_index < len(pairs)):
            self.report({'WARNING'}, "EasyRetarget: Invalid pair index.")
            return {'CANCELLED'}

        item = pairs[self.pair_index]
        item.match_status = 'CONFIRMED'
        item.match_reason = ""
        item.is_manual    = True

        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class EASYRETARGET_OT_ClearAllWarnings(Operator):
    """Confirm all low-confidence matches, clearing all warning statuses at once."""
    bl_idname = "easy_retarget.clear_all_warnings"
    bl_label = "Clear Warnings"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.easy_retarget
        return any(item.match_status == 'WARNING' for item in props.bone_pairs)

    def execute(self, context):
        props = context.scene.easy_retarget
        count = 0
        for item in props.bone_pairs:
            if item.match_status == 'WARNING':
                item.match_status = 'CONFIRMED'
                item.match_reason = ""
                item.is_manual    = True
                count += 1

        if context.area:
            context.area.tag_redraw()

        self.report({'INFO'}, f"EasyRetarget: {count} warning(s) confirmed.")
        return {'FINISHED'}


class EASYRETARGET_OT_AddBonePairFromSelection(Operator):
    """
    Add a bone pair from the currently selected pose bones.
    Select exactly one bone on the source rig and one on the target rig,
    then press the hotkey (default: Shift+Ctrl+P) to create the pair.
    Both rigs must already be set in the EasyRetarget panel.
    """
    bl_idname = "easy_retarget.add_bone_pair_from_selection"
    bl_label = "Add Bone Pair from Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE':
            return False
        props = context.scene.easy_retarget
        return bool(props.source_rig and props.target_rig)

    def execute(self, context):
        props = context.scene.easy_retarget
        source_rig = props.source_rig
        target_rig = props.target_rig

        # Collect selected pose bones from each rig via context.selected_pose_bones,
        # which is compatible with Blender 5.0+ (Bone.select was removed).
        # id_data on a PoseBone returns the owning Object.
        selected = context.selected_pose_bones or []
        source_bones = [b for b in selected if b.id_data == source_rig]
        target_bones = [b for b in selected if b.id_data == target_rig]

        if len(source_bones) != 1:
            self.report(
                {'WARNING'},
                f"EasyRetarget: Select exactly one bone on the source rig "
                f"('{source_rig.name}'). Found {len(source_bones)}.",
            )
            return {'CANCELLED'}

        if len(target_bones) != 1:
            self.report(
                {'WARNING'},
                f"EasyRetarget: Select exactly one bone on the target rig "
                f"('{target_rig.name}'). Found {len(target_bones)}.",
            )
            return {'CANCELLED'}

        item = props.bone_pairs.add()
        item.source_bone          = source_bones[0].name
        item.target_bone          = target_bones[0].name
        item.previous_target_bone = item.target_bone
        item.match_status         = 'CONFIRMED'
        item.match_reason         = ""
        item.is_manual            = True
        props.bone_pairs_index = len(props.bone_pairs) - 1

        if context.area:
            context.area.tag_redraw()

        self.report(
            {'INFO'},
            f"EasyRetarget: Added pair '{item.source_bone}' → '{item.target_bone}'.",
        )
        return {'FINISHED'}
