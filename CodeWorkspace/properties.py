# =====================================================================
# EasyRetarget - properties.py
# PropertyGroup definitions for bone pairs and scene-level settings.
# =====================================================================

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


# =====================================================================
# Search Callbacks
# =====================================================================

def _source_bone_search(self, context, edit_text):
    props = context.scene.easy_retarget
    if props.source_rig and props.source_rig.type == 'ARMATURE':
        for bone in props.source_rig.data.bones:
            if edit_text.lower() in bone.name.lower():
                yield bone.name


def _target_bone_search(self, context, edit_text):
    props = context.scene.easy_retarget
    if props.target_rig and props.target_rig.type == 'ARMATURE':
        for bone in props.target_rig.data.bones:
            if edit_text.lower() in bone.name.lower():
                yield bone.name


# =====================================================================
# Update Callbacks
# =====================================================================

def _on_rig_update(self, context):
    from .utils import force_depsgraph_update
    force_depsgraph_update(context=context)


def _on_target_bone_update(self, context):
    """
    When the target bone changes, check whether the previous target bone
    has any EasyRetarget constraints. If so, invoke a confirmation dialog
    before removing them. On confirmation the constraints are removed and
    previous_target_bone is updated. On cancellation the target bone
    field is reverted.
    """
    from .constraint_utils import find_rotation_constraint, find_location_constraint
    from .utils import get_bone

    props = context.scene.easy_retarget
    new_bone = self.target_bone
    old_bone = self.previous_target_bone

    # Find this item's index for the confirmation operator.
    pair_index = -1
    for i, item in enumerate(props.bone_pairs):
        if item == self:
            pair_index = i
            break

    if old_bone and old_bone != new_bone and props.target_rig:
        pbone = get_bone(props.target_rig, old_bone)
        if pbone and (find_rotation_constraint(pbone) or find_location_constraint(pbone)):
            # Invoke confirmation — the operator will handle removal or revert.
            bpy.ops.easy_retarget.confirm_target_bone_change(
                'INVOKE_DEFAULT',
                pair_index=pair_index,
                old_bone_name=old_bone,
                new_bone_name=new_bone,
            )
            return

    # No constraints on old bone — update previous_target_bone and mark manual.
    self.previous_target_bone = new_bone
    self.is_manual = True
    self.match_reason = ""
    if self.source_bone and new_bone:
        self.match_status = 'CONFIRMED'
    elif not new_bone:
        self.match_status = 'NONE'


def _on_constraint_toggle_update(self, context):
    """
    When the constraint toggle changes, enable or disable EasyRetarget
    constraints (both rotation and location) on paired target bones.

    ALL_OFF:           snapshot EasyRetarget states (if coming from CUSTOM),
                       then disable all EasyRetarget constraints.
    ALL_ON:            snapshot EasyRetarget states (if coming from CUSTOM),
                       then enable all EasyRetarget constraints.
    CUSTOM:            restore EasyRetarget enabled states from snapshot,
                       then clear snapshot.
    EASYRETARGET_ONLY: snapshot all non-EasyRetarget constraints on paired
                       bones into other_constraint_snapshot, disable them,
                       then force-enable both EasyRetarget constraints.

    When leaving EASYRETARGET_ONLY, other_constraint_snapshot is restored
    first before the new mode is applied, so non-EasyRetarget constraints
    return to the state they had before the switch.
    """
    from .constraint_utils import (
        find_rotation_constraint, find_location_constraint,
        ROTATION_CONSTRAINT_NAME, LOCATION_CONSTRAINT_NAME,
    )
    from .utils import get_bone

    props = self
    target_rig = props.target_rig
    if not target_rig:
        return

    toggle = props.constraint_toggle

    # ── Step 1: If leaving EASYRETARGET_ONLY, restore non-EasyRetarget
    #            constraints from the other_constraint_snapshot first. ──
    if len(props.other_constraint_snapshot) > 0:
        for entry in props.other_constraint_snapshot:
            pbone = get_bone(target_rig, entry.bone_name)
            if not pbone:
                continue
            con = pbone.constraints.get(entry.constraint_name)
            if con:
                con.enabled = entry.enabled
        props.other_constraint_snapshot.clear()

    # ── Step 2: Apply new mode. ──────────────────────────────────────────

    if toggle == 'CUSTOM':
        # Restore EasyRetarget constraint states from snapshot.
        snapshot = {entry.bone_name: entry.enabled
                    for entry in props.constraint_state_snapshot}
        for item in props.bone_pairs:
            if not item.target_bone:
                continue
            pbone = get_bone(target_rig, item.target_bone)
            if not pbone:
                continue
            enabled = snapshot.get(item.target_bone, True)
            rot_con = find_rotation_constraint(pbone)
            loc_con = find_location_constraint(pbone)
            if rot_con:
                rot_con.enabled = enabled
            if loc_con:
                loc_con.enabled = enabled
        props.constraint_state_snapshot.clear()
        return

    if toggle == 'EASYRETARGET_ONLY':
        # Snapshot all non-EasyRetarget constraints on paired bones, then
        # disable them and force-enable the EasyRetarget constraints.
        er_names = {ROTATION_CONSTRAINT_NAME, LOCATION_CONSTRAINT_NAME}
        for item in props.bone_pairs:
            if not item.target_bone:
                continue
            pbone = get_bone(target_rig, item.target_bone)
            if not pbone:
                continue
            for con in pbone.constraints:
                if con.name in er_names:
                    continue
                entry = props.other_constraint_snapshot.add()
                entry.bone_name = item.target_bone
                entry.constraint_name = con.name
                entry.enabled = con.enabled
                con.enabled = False
            rot_con = find_rotation_constraint(pbone)
            loc_con = find_location_constraint(pbone)
            if rot_con:
                rot_con.enabled = True
            if loc_con:
                loc_con.enabled = True
        return

    # ALL_OFF and ALL_ON: snapshot EasyRetarget states only if the snapshot
    # is currently empty (i.e. coming from CUSTOM — preserve existing
    # snapshot when toggling between ALL_OFF and ALL_ON).
    if len(props.constraint_state_snapshot) == 0:
        for item in props.bone_pairs:
            if not item.target_bone:
                continue
            pbone = get_bone(target_rig, item.target_bone)
            if not pbone:
                continue
            rot_con = find_rotation_constraint(pbone)
            loc_con = find_location_constraint(pbone)
            if rot_con or loc_con:
                entry = props.constraint_state_snapshot.add()
                entry.bone_name = item.target_bone
                # Use rotation constraint as representative; fall back to location.
                entry.enabled = rot_con.enabled if rot_con else loc_con.enabled

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
        if loc_con:
            loc_con.enabled = target_enabled


# =====================================================================
# Property Groups
# =====================================================================

class EASYRETARGET_ConstraintState(PropertyGroup):
    """Records the enabled state of a single bone's EasyRetarget constraints."""
    bone_name: StringProperty(options={'HIDDEN'})
    enabled: BoolProperty(default=True, options={'HIDDEN'})


class EASYRETARGET_OtherConstraintState(PropertyGroup):
    """
    Records the pre-EASYRETARGET_ONLY enabled state of a single
    non-EasyRetarget constraint on a paired bone, so it can be
    restored when leaving EASYRETARGET_ONLY mode.
    """
    bone_name: StringProperty(options={'HIDDEN'})
    constraint_name: StringProperty(options={'HIDDEN'})
    enabled: BoolProperty(default=True, options={'HIDDEN'})


class EASYRETARGET_BonePairItem(PropertyGroup):
    """Represents a single source-to-target bone mapping entry."""

    source_bone: StringProperty(
        name="Source Bone",
        description="Bone on the source rig",
        default="",
        search=_source_bone_search,
        search_options={'SORT'},
    )

    target_bone: StringProperty(
        name="Target Bone",
        description="Bone on the target rig",
        default="",
        search=_target_bone_search,
        search_options={'SORT'},
        update=_on_target_bone_update,
    )

    previous_target_bone: StringProperty(
        name="Previous Target Bone",
        description="Stores the last confirmed target bone name for change detection",
        default="",
        options={'HIDDEN'},
    )

    match_status: EnumProperty(
        name="Match Status",
        description="Result status of the last AutoPopulate match for this pair",
        items=[
            ('NONE',      "None",      "No match attempted or pair is empty"),
            ('CONFIRMED', "Confirmed", "High-confidence match or manually confirmed"),
            ('WARNING',   "Warning",   "Low-confidence or ambiguous match — needs review"),
            ('ERROR',     "Error",     "No match found — requires manual entry"),
        ],
        default='NONE',
        options={'HIDDEN'},
    )

    match_reason: StringProperty(
        name="Match Reason",
        description="Description of why this pair received a warning status",
        default="",
        options={'HIDDEN'},
    )

    is_manual: BoolProperty(
        name="Manual Entry",
        description="True when this pair was set by the user, not by the algorithm",
        default=False,
        options={'HIDDEN'},
    )

    rotation_expanded: BoolProperty(
        name="Rotation",
        description="Show rotation mapping settings in the constraint popup",
        default=True,
        options={'HIDDEN'},
    )

    location_expanded: BoolProperty(
        name="Location",
        description="Show location mapping settings in the constraint popup",
        default=False,
        options={'HIDDEN'},
    )

    rot_fine_tune_expanded: BoolProperty(
        name="Rotation Fine Tune",
        description="Show rotation fine tune settings in the constraint popup",
        default=False,
        options={'HIDDEN'},
    )

    loc_fine_tune_expanded: BoolProperty(
        name="Location Fine Tune",
        description="Show location fine tune settings in the constraint popup",
        default=False,
        options={'HIDDEN'},
    )

    # Stored overall offsets per axis — used to recover fine-tune deltas when
    # reading back from an existing constraint. Set whenever an offset is written.
    rot_offset_x: FloatProperty(
        name="Rotation X Stored Offset",
        description="Stored overall offset for rotation X axis (degrees), used for fine-tune recovery",
        default=0.0,
        options={'HIDDEN'},
    )
    rot_offset_y: FloatProperty(
        name="Rotation Y Stored Offset",
        description="Stored overall offset for rotation Y axis (degrees), used for fine-tune recovery",
        default=0.0,
        options={'HIDDEN'},
    )
    rot_offset_z: FloatProperty(
        name="Rotation Z Stored Offset",
        description="Stored overall offset for rotation Z axis (degrees), used for fine-tune recovery",
        default=0.0,
        options={'HIDDEN'},
    )
    loc_offset_x: FloatProperty(
        name="Location X Stored Offset",
        description="Stored overall offset for location X axis (Blender units), used for fine-tune recovery",
        default=0.0,
        options={'HIDDEN'},
    )
    loc_offset_y: FloatProperty(
        name="Location Y Stored Offset",
        description="Stored overall offset for location Y axis (Blender units), used for fine-tune recovery",
        default=0.0,
        options={'HIDDEN'},
    )
    loc_offset_z: FloatProperty(
        name="Location Z Stored Offset",
        description="Stored overall offset for location Z axis (Blender units), used for fine-tune recovery",
        default=0.0,
        options={'HIDDEN'},
    )


class EASYRETARGET_SceneProperties(PropertyGroup):
    """Top-level scene properties for EasyRetarget."""

    source_rig: PointerProperty(
        name="Source Rig",
        description="The armature whose animation will be retargeted",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        update=_on_rig_update,
    )

    target_rig: PointerProperty(
        name="Target Rig",
        description="The armature that will receive the retargeted animation",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        update=_on_rig_update,
    )

    bone_pairs: CollectionProperty(
        name="Bone Pairs",
        type=EASYRETARGET_BonePairItem,
    )

    bone_pairs_index: IntProperty(
        name="Active Bone Pair Index",
        default=0,
    )

    constraint_toggle: EnumProperty(
        name="Constraint Toggle",
        description="Control the enabled state of all EasyRetarget constraints on paired bones",
        items=[
            ('ALL_OFF',           "All Off",
             "Disable all EasyRetarget constraints on paired bones"),
            ('ALL_ON',            "All On",
             "Enable all EasyRetarget constraints on paired bones"),
            ('CUSTOM',            "Custom",
             "Respect individual constraint enabled states as set by the user"),
            ('EASYRETARGET_ONLY', "EasyRetarget Only",
             "Disable all non-EasyRetarget constraints on paired bones and force-enable EasyRetarget constraints"),
        ],
        default='CUSTOM',
        update=_on_constraint_toggle_update,
        options={'HIDDEN'},
    )

    # Stores per-bone EasyRetarget constraint enabled states when the toggle
    # is ALL_OFF or ALL_ON, so they can be restored when returning to CUSTOM.
    # Persists in scene data across Blender restarts.
    constraint_state_snapshot: CollectionProperty(
        name="Constraint State Snapshot",
        type=EASYRETARGET_ConstraintState,
        options={'HIDDEN'},
    )

    # Stores per-bone, per-constraint enabled states of non-EasyRetarget
    # constraints when in EASYRETARGET_ONLY mode, so they can be restored
    # when leaving that mode. Persists in scene data across Blender restarts.
    other_constraint_snapshot: CollectionProperty(
        name="Other Constraint State Snapshot",
        type=EASYRETARGET_OtherConstraintState,
        options={'HIDDEN'},
    )

    bone_pairs_expanded: BoolProperty(
        name="Bone Pairs",
        default=True,
    )

    settings_expanded: BoolProperty(
        name="Settings",
        default=False,
    )

    show_remove_constraint_column: BoolProperty(
        name="Show Remove Column",
        description="Show the remove constraint button column in the bone pair list",
        default=False,
    )

    bake_keyed_frames_only: BoolProperty(
        name="Bake Keyed Frames Only",
        description="Only bake frames that already have keyframes on the source rig",
        default=True,
    )

    keying_interval: IntProperty(
        name="Keying Interval",
        description="Interval (in frames) between baked keyframes",
        default=1,
        min=1,
    )
