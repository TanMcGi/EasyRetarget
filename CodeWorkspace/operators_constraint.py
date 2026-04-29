# =====================================================================
# EasyRetarget - operators_constraint.py
# Constraint button operator (create/edit), Create Constraints,
# Remove All Constraints, Confirm Target Bone Change,
# Copy/Paste Constraint Settings.
# =====================================================================

import math
import bpy
from bpy.types import Operator
from bpy.props import IntProperty, StringProperty, BoolProperty, EnumProperty, FloatProperty

from .constraint_utils import (
    ROTATION_CONSTRAINT_NAME,
    LOCATION_CONSTRAINT_NAME,
    find_rotation_constraint,
    find_location_constraint,
    create_or_update_rotation_constraint,
    create_or_update_location_constraint,
    remove_rotation_constraint,
    remove_location_constraint,
)
from .utils import get_bone
from .debug import log, log_section


# =====================================================================
# Module-level clipboard for copy/paste constraint settings.
# Does not persist across Blender restarts.
# Structure: {'rotation': dict_or_None, 'location': dict_or_None}
# =====================================================================

_constraint_clipboard = None


# =====================================================================
# Axis mapping enum items
# =====================================================================

AXIS_ITEMS = [
    ('X',    "X",    "Copy the source bone's X rotation axis"),
    ('Y',    "Y",    "Copy the source bone's Y rotation axis"),
    ('Z',    "Z",    "Copy the source bone's Z rotation axis"),
    ('NONE', "None", "No rotation contribution from source on this axis"),
]

LOCATION_AXIS_ITEMS = [
    ('X',    "X",    "Copy the source bone's X location"),
    ('Y',    "Y",    "Copy the source bone's Y location"),
    ('Z',    "Z",    "Copy the source bone's Z location"),
    ('NONE', "None", "No location contribution from source on this axis"),
]


# =====================================================================
# Remove Constraint (row button with confirmation)
# =====================================================================

class EASYRETARGET_OT_RemoveConstraint(Operator):
    """Remove all EasyRetarget constraints from this bone pair's target bone."""
    bl_idname = "easy_retarget.remove_constraint"
    bl_label = "Remove Constraints"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pair_index: IntProperty(options={'SKIP_SAVE'})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        warn_box = layout.box()
        warn_box.alert = True
        col = warn_box.column(align=True)
        col.scale_y = 1.4
        col.label(text="Remove all EasyRetarget constraints from this bone?", icon='ERROR')
        col.label(text="This cannot be undone.")

    def execute(self, context):
        props = context.scene.easy_retarget
        if not (0 <= self.pair_index < len(props.bone_pairs)):
            return {'CANCELLED'}
        item = props.bone_pairs[self.pair_index]
        pbone = get_bone(props.target_rig, item.target_bone)
        if pbone:
            remove_rotation_constraint(pbone)
            remove_location_constraint(pbone)
            log(f"  RemoveConstraint: removed from {item.target_bone}")
        return {'FINISHED'}


# =====================================================================
# Edit Constraint operator (constraint button)
# =====================================================================

class EASYRETARGET_OT_EditConstraint(Operator):
    """
    Open the Constraint Mapping popup for a bone pair.

    Each section (Rotation, Location) shows an Add button when no constraint
    exists, or the full settings plus a Remove button when one does. Removal
    requires inline confirmation. Cancel restores the pre-invoke state,
    including re-creating any constraint that was removed during the session.

    Per-axis fine-tune min/max offsets are independent per-end adjustments
    stacked on top of the overall offset. The overall offset is stored on
    BonePairItem so fine-tune can be correctly recovered on subsequent opens.
    """
    bl_idname = "easy_retarget.edit_constraint"
    bl_label = "Constraint Mapping"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    pair_index: IntProperty(options={'SKIP_SAVE'})

    # ── Expanded section state ────────────────────────────────────────────
    rot_expanded: BoolProperty(default=True)
    loc_expanded: BoolProperty(default=False)
    rot_fine_tune_expanded: BoolProperty(default=False)
    loc_fine_tune_expanded: BoolProperty(default=False)

    # ── Blank-slate mode: skip auto-creating constraints on open ──────────
    blank_slate: BoolProperty(default=False, options={'SKIP_SAVE'})

    # ── Add / Remove flags (reset by check() after handling) ─────────────
    add_rotation_requested:  BoolProperty(default=False, options={'SKIP_SAVE'})
    add_location_requested:  BoolProperty(default=False, options={'SKIP_SAVE'})
    remove_rot_confirm:      BoolProperty(default=False, options={'SKIP_SAVE'})
    remove_loc_confirm:      BoolProperty(default=False, options={'SKIP_SAVE'})
    remove_rot_execute:      BoolProperty(default=False, options={'SKIP_SAVE'})
    remove_loc_execute:      BoolProperty(default=False, options={'SKIP_SAVE'})

    # ── Rotation properties ───────────────────────────────────────────────
    map_x_from: EnumProperty(name="X Source Axis", items=AXIS_ITEMS, default='X')
    map_y_from: EnumProperty(name="Y Source Axis", items=AXIS_ITEMS, default='Y')
    map_z_from: EnumProperty(name="Z Source Axis", items=AXIS_ITEMS, default='Z')

    invert_x: BoolProperty(name="Invert X", default=False)
    invert_y: BoolProperty(name="Invert Y", default=False)
    invert_z: BoolProperty(name="Invert Z", default=False)

    offset_x: FloatProperty(name="X Offset", default=0.0, min=-180.0, max=180.0,
                            subtype='ANGLE', unit='ROTATION')
    offset_y: FloatProperty(name="Y Offset", default=0.0, min=-180.0, max=180.0,
                            subtype='ANGLE', unit='ROTATION')
    offset_z: FloatProperty(name="Z Offset", default=0.0, min=-180.0, max=180.0,
                            subtype='ANGLE', unit='ROTATION')

    # Per-axis fine-tune: independent per-end adjustments on top of offset (degrees).
    fine_min_x: FloatProperty(name="X Fine Min", default=0.0, subtype='ANGLE', unit='ROTATION')
    fine_max_x: FloatProperty(name="X Fine Max", default=0.0, subtype='ANGLE', unit='ROTATION')
    fine_min_y: FloatProperty(name="Y Fine Min", default=0.0, subtype='ANGLE', unit='ROTATION')
    fine_max_y: FloatProperty(name="Y Fine Max", default=0.0, subtype='ANGLE', unit='ROTATION')
    fine_min_z: FloatProperty(name="Z Fine Min", default=0.0, subtype='ANGLE', unit='ROTATION')
    fine_max_z: FloatProperty(name="Z Fine Max", default=0.0, subtype='ANGLE', unit='ROTATION')

    space: EnumProperty(
        name="Rotation Space",
        description="Rotation space for both target and owner",
        items=[
            ('LOCAL', "Local", "Local to Local space — offset is in local space (Add mix mode)"),
            ('WORLD', "World", "World to World space — offset is in world space (Replace mix mode)"),
        ],
        default='LOCAL',
    )

    # ── Location properties ───────────────────────────────────────────────
    loc_map_x_from: EnumProperty(name="X Source Axis", items=LOCATION_AXIS_ITEMS, default='X')
    loc_map_y_from: EnumProperty(name="Y Source Axis", items=LOCATION_AXIS_ITEMS, default='Y')
    loc_map_z_from: EnumProperty(name="Z Source Axis", items=LOCATION_AXIS_ITEMS, default='Z')

    loc_invert_x: BoolProperty(name="Invert X", default=False)
    loc_invert_y: BoolProperty(name="Invert Y", default=False)
    loc_invert_z: BoolProperty(name="Invert Z", default=False)

    loc_offset_x: FloatProperty(name="X Offset", default=0.0)
    loc_offset_y: FloatProperty(name="Y Offset", default=0.0)
    loc_offset_z: FloatProperty(name="Z Offset", default=0.0)

    # Per-axis fine-tune for location (Blender units).
    loc_fine_min_x: FloatProperty(name="X Fine Min", default=0.0)
    loc_fine_max_x: FloatProperty(name="X Fine Max", default=0.0)
    loc_fine_min_y: FloatProperty(name="Y Fine Min", default=0.0)
    loc_fine_max_y: FloatProperty(name="Y Fine Max", default=0.0)
    loc_fine_min_z: FloatProperty(name="Z Fine Min", default=0.0)
    loc_fine_max_z: FloatProperty(name="Z Fine Max", default=0.0)

    loc_space: EnumProperty(
        name="Location Space",
        description="Location space for both target and owner",
        items=[
            ('LOCAL', "Local", "Local to Local space — offset is in local space (Add mix mode)"),
            ('WORLD', "World", "World to World space — offset is in world space (Replace mix mode)"),
        ],
        default='LOCAL',
    )

    # ── Instance-level state (set in invoke; not operator props) ─────────
    # Whether each constraint existed before this popup opened.
    # Used in cancel() to decide restore vs. remove.
    _had_rotation: bool = False
    _had_location: bool = False

    # Rotation snapshot for cancel restoration.
    _snap_map_x_from: str = 'X'
    _snap_map_y_from: str = 'Y'
    _snap_map_z_from: str = 'Z'
    _snap_invert_x: bool = False
    _snap_invert_y: bool = False
    _snap_invert_z: bool = False
    _snap_offset_x: float = 0.0
    _snap_offset_y: float = 0.0
    _snap_offset_z: float = 0.0
    _snap_fine_min_x: float = 0.0
    _snap_fine_max_x: float = 0.0
    _snap_fine_min_y: float = 0.0
    _snap_fine_max_y: float = 0.0
    _snap_fine_min_z: float = 0.0
    _snap_fine_max_z: float = 0.0
    _snap_space: str = 'LOCAL'
    _snap_rot_expanded: bool = True
    _snap_rot_fine_tune_expanded: bool = False

    # Location snapshot for cancel restoration.
    _snap_loc_map_x_from: str = 'X'
    _snap_loc_map_y_from: str = 'Y'
    _snap_loc_map_z_from: str = 'Z'
    _snap_loc_invert_x: bool = False
    _snap_loc_invert_y: bool = False
    _snap_loc_invert_z: bool = False
    _snap_loc_offset_x: float = 0.0
    _snap_loc_offset_y: float = 0.0
    _snap_loc_offset_z: float = 0.0
    _snap_loc_fine_min_x: float = 0.0
    _snap_loc_fine_max_x: float = 0.0
    _snap_loc_fine_min_y: float = 0.0
    _snap_loc_fine_max_y: float = 0.0
    _snap_loc_fine_min_z: float = 0.0
    _snap_loc_fine_max_z: float = 0.0
    _snap_loc_space: str = 'LOCAL'
    _snap_loc_expanded: bool = False
    _snap_loc_fine_tune_expanded: bool = False

    # ── Helpers ───────────────────────────────────────────────────────────

    def _reset_rotation_properties(self):
        self.map_x_from = 'X'
        self.map_y_from = 'Y'
        self.map_z_from = 'Z'
        self.invert_x = False
        self.invert_y = False
        self.invert_z = False
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        self.fine_min_x = 0.0
        self.fine_max_x = 0.0
        self.fine_min_y = 0.0
        self.fine_max_y = 0.0
        self.fine_min_z = 0.0
        self.fine_max_z = 0.0
        self.space = 'LOCAL'

    def _reset_location_properties(self):
        self.loc_map_x_from = 'X'
        self.loc_map_y_from = 'Y'
        self.loc_map_z_from = 'Z'
        self.loc_invert_x = False
        self.loc_invert_y = False
        self.loc_invert_z = False
        self.loc_offset_x = 0.0
        self.loc_offset_y = 0.0
        self.loc_offset_z = 0.0
        self.loc_fine_min_x = 0.0
        self.loc_fine_max_x = 0.0
        self.loc_fine_min_y = 0.0
        self.loc_fine_max_y = 0.0
        self.loc_fine_min_z = 0.0
        self.loc_fine_max_z = 0.0
        self.loc_space = 'LOCAL'

    def _snapshot_rotation_properties(self):
        self._snap_map_x_from = self.map_x_from
        self._snap_map_y_from = self.map_y_from
        self._snap_map_z_from = self.map_z_from
        self._snap_invert_x   = self.invert_x
        self._snap_invert_y   = self.invert_y
        self._snap_invert_z   = self.invert_z
        self._snap_offset_x   = self.offset_x
        self._snap_offset_y   = self.offset_y
        self._snap_offset_z   = self.offset_z
        self._snap_fine_min_x = self.fine_min_x
        self._snap_fine_max_x = self.fine_max_x
        self._snap_fine_min_y = self.fine_min_y
        self._snap_fine_max_y = self.fine_max_y
        self._snap_fine_min_z = self.fine_min_z
        self._snap_fine_max_z = self.fine_max_z
        self._snap_space                = self.space
        self._snap_rot_expanded         = self.rot_expanded
        self._snap_rot_fine_tune_expanded = self.rot_fine_tune_expanded

    def _snapshot_location_properties(self):
        self._snap_loc_map_x_from = self.loc_map_x_from
        self._snap_loc_map_y_from = self.loc_map_y_from
        self._snap_loc_map_z_from = self.loc_map_z_from
        self._snap_loc_invert_x   = self.loc_invert_x
        self._snap_loc_invert_y   = self.loc_invert_y
        self._snap_loc_invert_z   = self.loc_invert_z
        self._snap_loc_offset_x   = self.loc_offset_x
        self._snap_loc_offset_y   = self.loc_offset_y
        self._snap_loc_offset_z   = self.loc_offset_z
        self._snap_loc_fine_min_x = self.loc_fine_min_x
        self._snap_loc_fine_max_x = self.loc_fine_max_x
        self._snap_loc_fine_min_y = self.loc_fine_min_y
        self._snap_loc_fine_max_y = self.loc_fine_max_y
        self._snap_loc_fine_min_z = self.loc_fine_min_z
        self._snap_loc_fine_max_z = self.loc_fine_max_z
        self._snap_loc_space                = self.loc_space
        self._snap_loc_expanded             = self.loc_expanded
        self._snap_loc_fine_tune_expanded   = self.loc_fine_tune_expanded

    def _restore_rotation_snapshot(self):
        self.map_x_from = self._snap_map_x_from
        self.map_y_from = self._snap_map_y_from
        self.map_z_from = self._snap_map_z_from
        self.invert_x   = self._snap_invert_x
        self.invert_y   = self._snap_invert_y
        self.invert_z   = self._snap_invert_z
        self.offset_x   = self._snap_offset_x
        self.offset_y   = self._snap_offset_y
        self.offset_z   = self._snap_offset_z
        self.fine_min_x = self._snap_fine_min_x
        self.fine_max_x = self._snap_fine_max_x
        self.fine_min_y = self._snap_fine_min_y
        self.fine_max_y = self._snap_fine_max_y
        self.fine_min_z = self._snap_fine_min_z
        self.fine_max_z = self._snap_fine_max_z
        self.space                  = self._snap_space
        self.rot_expanded           = self._snap_rot_expanded
        self.rot_fine_tune_expanded = self._snap_rot_fine_tune_expanded

    def _restore_location_snapshot(self):
        self.loc_map_x_from = self._snap_loc_map_x_from
        self.loc_map_y_from = self._snap_loc_map_y_from
        self.loc_map_z_from = self._snap_loc_map_z_from
        self.loc_invert_x   = self._snap_loc_invert_x
        self.loc_invert_y   = self._snap_loc_invert_y
        self.loc_invert_z   = self._snap_loc_invert_z
        self.loc_offset_x   = self._snap_loc_offset_x
        self.loc_offset_y   = self._snap_loc_offset_y
        self.loc_offset_z   = self._snap_loc_offset_z
        self.loc_fine_min_x = self._snap_loc_fine_min_x
        self.loc_fine_max_x = self._snap_loc_fine_max_x
        self.loc_fine_min_y = self._snap_loc_fine_min_y
        self.loc_fine_max_y = self._snap_loc_fine_max_y
        self.loc_fine_min_z = self._snap_loc_fine_min_z
        self.loc_fine_max_z = self._snap_loc_fine_max_z
        self.loc_space              = self._snap_loc_space
        self.loc_expanded           = self._snap_loc_expanded
        self.loc_fine_tune_expanded = self._snap_loc_fine_tune_expanded

    def _get_item_and_bones(self, context):
        props = context.scene.easy_retarget
        item = props.bone_pairs[self.pair_index]
        tgt_pbone = get_bone(props.target_rig, item.target_bone)
        return props, item, tgt_pbone

    def _read_from_rotation_constraint(self, con, item):
        """
        Populate rotation operator properties from an existing constraint.

        Uses item.rot_offset_x/y/z as the stored overall offset for fine-tune
        recovery. If stored offset is 0.0, falls back to the pre-fine-tune
        recovery formula (to_min_deg + 180 for non-inverted) and stores the
        result — this handles migration from pre-0.3.5 data.

        NOTE: The lazy-migration check triggers whenever stored offset is 0.0.
        If offset is genuinely 0.0 but fine-tune is nonzero, fine-tune values
        will be mis-recovered on the first read after a Blender restart. This
        is a known limitation that will be addressed in a future patch.
        """
        log_section("EditConstraint._read_from_rotation_constraint")

        def _is_none(min_r, max_r):
            return math.isclose(min_r, 0.0) and math.isclose(max_r, 0.0)

        def _is_inverted(min_r, max_r):
            return max_r < min_r

        axis_map = {'X': 'X', 'Y': 'Y', 'Z': 'Z'}

        # ── X axis ───────────────────────────────────────────────────
        if _is_none(con.to_min_x_rot, con.to_max_x_rot):
            self.map_x_from = 'NONE'
            self.invert_x = False
        else:
            self.map_x_from = axis_map.get(con.map_to_x_from, 'X')
            self.invert_x = _is_inverted(con.to_min_x_rot, con.to_max_x_rot)

        to_min_x_deg = math.degrees(con.to_min_x_rot)
        to_max_x_deg = math.degrees(con.to_max_x_rot)

        if self.map_x_from != 'NONE':
            if item.rot_offset_x != 0.0:
                offset_x_deg = item.rot_offset_x
            else:
                # Lazy migration: recover offset from constraint (fine_min assumed 0)
                offset_x_deg = (to_min_x_deg - 180.0 if self.invert_x
                                else to_min_x_deg + 180.0)
                item.rot_offset_x = offset_x_deg

            if self.invert_x:
                fine_min_x_deg = to_min_x_deg - (180.0 + offset_x_deg)
                fine_max_x_deg = to_max_x_deg - (-180.0 + offset_x_deg)
            else:
                fine_min_x_deg = to_min_x_deg - (-180.0 + offset_x_deg)
                fine_max_x_deg = to_max_x_deg - (180.0 + offset_x_deg)
        else:
            offset_x_deg = 0.0
            fine_min_x_deg = 0.0
            fine_max_x_deg = 0.0

        self.offset_x   = math.radians(offset_x_deg)
        self.fine_min_x = math.radians(fine_min_x_deg)
        self.fine_max_x = math.radians(fine_max_x_deg)

        # ── Y axis ───────────────────────────────────────────────────
        if _is_none(con.to_min_y_rot, con.to_max_y_rot):
            self.map_y_from = 'NONE'
            self.invert_y = False
        else:
            self.map_y_from = axis_map.get(con.map_to_y_from, 'Y')
            self.invert_y = _is_inverted(con.to_min_y_rot, con.to_max_y_rot)

        to_min_y_deg = math.degrees(con.to_min_y_rot)
        to_max_y_deg = math.degrees(con.to_max_y_rot)

        if self.map_y_from != 'NONE':
            if item.rot_offset_y != 0.0:
                offset_y_deg = item.rot_offset_y
            else:
                offset_y_deg = (to_min_y_deg - 180.0 if self.invert_y
                                else to_min_y_deg + 180.0)
                item.rot_offset_y = offset_y_deg

            if self.invert_y:
                fine_min_y_deg = to_min_y_deg - (180.0 + offset_y_deg)
                fine_max_y_deg = to_max_y_deg - (-180.0 + offset_y_deg)
            else:
                fine_min_y_deg = to_min_y_deg - (-180.0 + offset_y_deg)
                fine_max_y_deg = to_max_y_deg - (180.0 + offset_y_deg)
        else:
            offset_y_deg = 0.0
            fine_min_y_deg = 0.0
            fine_max_y_deg = 0.0

        self.offset_y   = math.radians(offset_y_deg)
        self.fine_min_y = math.radians(fine_min_y_deg)
        self.fine_max_y = math.radians(fine_max_y_deg)

        # ── Z axis ───────────────────────────────────────────────────
        if _is_none(con.to_min_z_rot, con.to_max_z_rot):
            self.map_z_from = 'NONE'
            self.invert_z = False
        else:
            self.map_z_from = axis_map.get(con.map_to_z_from, 'Z')
            self.invert_z = _is_inverted(con.to_min_z_rot, con.to_max_z_rot)

        to_min_z_deg = math.degrees(con.to_min_z_rot)
        to_max_z_deg = math.degrees(con.to_max_z_rot)

        if self.map_z_from != 'NONE':
            if item.rot_offset_z != 0.0:
                offset_z_deg = item.rot_offset_z
            else:
                offset_z_deg = (to_min_z_deg - 180.0 if self.invert_z
                                else to_min_z_deg + 180.0)
                item.rot_offset_z = offset_z_deg

            if self.invert_z:
                fine_min_z_deg = to_min_z_deg - (180.0 + offset_z_deg)
                fine_max_z_deg = to_max_z_deg - (-180.0 + offset_z_deg)
            else:
                fine_min_z_deg = to_min_z_deg - (-180.0 + offset_z_deg)
                fine_max_z_deg = to_max_z_deg - (180.0 + offset_z_deg)
        else:
            offset_z_deg = 0.0
            fine_min_z_deg = 0.0
            fine_max_z_deg = 0.0

        self.offset_z   = math.radians(offset_z_deg)
        self.fine_min_z = math.radians(fine_min_z_deg)
        self.fine_max_z = math.radians(fine_max_z_deg)

        self.space = 'WORLD' if con.target_space == 'WORLD' else 'LOCAL'

        log(f"  rot map: X={self.map_x_from} Y={self.map_y_from} Z={self.map_z_from}")
        log(f"  rot invert: X={self.invert_x} Y={self.invert_y} Z={self.invert_z}")
        log(f"  rot space={self.space} mix_mode_rot={con.mix_mode_rot}")

    def _read_from_location_constraint(self, con, item):
        """
        Populate location operator properties from an existing constraint.
        Same lazy-migration pattern as rotation; units are Blender units (no
        radians conversion). Half-range for location is 100.
        """
        log_section("EditConstraint._read_from_location_constraint")

        def _is_none(min_v, max_v):
            return math.isclose(min_v, 0.0) and math.isclose(max_v, 0.0)

        def _is_inverted(min_v, max_v):
            return max_v < min_v

        axis_map = {'X': 'X', 'Y': 'Y', 'Z': 'Z'}
        half_range = 100.0

        # ── X axis ───────────────────────────────────────────────────
        if _is_none(con.to_min_x, con.to_max_x):
            self.loc_map_x_from = 'NONE'
            self.loc_invert_x = False
        else:
            self.loc_map_x_from = axis_map.get(con.map_to_x_from, 'X')
            self.loc_invert_x = _is_inverted(con.to_min_x, con.to_max_x)

        if self.loc_map_x_from != 'NONE':
            if item.loc_offset_x != 0.0:
                offset_x = item.loc_offset_x
            else:
                offset_x = (con.to_min_x - half_range if self.loc_invert_x
                            else con.to_min_x + half_range)
                item.loc_offset_x = offset_x

            if self.loc_invert_x:
                loc_fine_min_x = con.to_min_x - (half_range + offset_x)
                loc_fine_max_x = con.to_max_x - (-half_range + offset_x)
            else:
                loc_fine_min_x = con.to_min_x - (-half_range + offset_x)
                loc_fine_max_x = con.to_max_x - (half_range + offset_x)
        else:
            offset_x = 0.0
            loc_fine_min_x = 0.0
            loc_fine_max_x = 0.0

        self.loc_offset_x   = offset_x
        self.loc_fine_min_x = loc_fine_min_x
        self.loc_fine_max_x = loc_fine_max_x

        # ── Y axis ───────────────────────────────────────────────────
        if _is_none(con.to_min_y, con.to_max_y):
            self.loc_map_y_from = 'NONE'
            self.loc_invert_y = False
        else:
            self.loc_map_y_from = axis_map.get(con.map_to_y_from, 'Y')
            self.loc_invert_y = _is_inverted(con.to_min_y, con.to_max_y)

        if self.loc_map_y_from != 'NONE':
            if item.loc_offset_y != 0.0:
                offset_y = item.loc_offset_y
            else:
                offset_y = (con.to_min_y - half_range if self.loc_invert_y
                            else con.to_min_y + half_range)
                item.loc_offset_y = offset_y

            if self.loc_invert_y:
                loc_fine_min_y = con.to_min_y - (half_range + offset_y)
                loc_fine_max_y = con.to_max_y - (-half_range + offset_y)
            else:
                loc_fine_min_y = con.to_min_y - (-half_range + offset_y)
                loc_fine_max_y = con.to_max_y - (half_range + offset_y)
        else:
            offset_y = 0.0
            loc_fine_min_y = 0.0
            loc_fine_max_y = 0.0

        self.loc_offset_y   = offset_y
        self.loc_fine_min_y = loc_fine_min_y
        self.loc_fine_max_y = loc_fine_max_y

        # ── Z axis ───────────────────────────────────────────────────
        if _is_none(con.to_min_z, con.to_max_z):
            self.loc_map_z_from = 'NONE'
            self.loc_invert_z = False
        else:
            self.loc_map_z_from = axis_map.get(con.map_to_z_from, 'Z')
            self.loc_invert_z = _is_inverted(con.to_min_z, con.to_max_z)

        if self.loc_map_z_from != 'NONE':
            if item.loc_offset_z != 0.0:
                offset_z = item.loc_offset_z
            else:
                offset_z = (con.to_min_z - half_range if self.loc_invert_z
                            else con.to_min_z + half_range)
                item.loc_offset_z = offset_z

            if self.loc_invert_z:
                loc_fine_min_z = con.to_min_z - (half_range + offset_z)
                loc_fine_max_z = con.to_max_z - (-half_range + offset_z)
            else:
                loc_fine_min_z = con.to_min_z - (-half_range + offset_z)
                loc_fine_max_z = con.to_max_z - (half_range + offset_z)
        else:
            offset_z = 0.0
            loc_fine_min_z = 0.0
            loc_fine_max_z = 0.0

        self.loc_offset_z   = offset_z
        self.loc_fine_min_z = loc_fine_min_z
        self.loc_fine_max_z = loc_fine_max_z

        self.loc_space = 'WORLD' if con.target_space == 'WORLD' else 'LOCAL'

        log(f"  loc map: X={self.loc_map_x_from} Y={self.loc_map_y_from} Z={self.loc_map_z_from}")
        log(f"  loc invert: X={self.loc_invert_x} Y={self.loc_invert_y} Z={self.loc_invert_z}")
        log(f"  loc space={self.loc_space} mix_mode={con.mix_mode}")

    def _write_to_rotation_constraint(self, context):
        """
        Write current rotation operator properties back to the constraint.
        Stores the overall offset on item for fine-tune recovery on next open.
        Creates the constraint if it does not exist.
        """
        props, item, tgt_pbone = self._get_item_and_bones(context)
        if not tgt_pbone:
            return

        offset_x_deg   = math.degrees(self.offset_x)
        offset_y_deg   = math.degrees(self.offset_y)
        offset_z_deg   = math.degrees(self.offset_z)
        fine_min_x_deg = math.degrees(self.fine_min_x)
        fine_max_x_deg = math.degrees(self.fine_max_x)
        fine_min_y_deg = math.degrees(self.fine_min_y)
        fine_max_y_deg = math.degrees(self.fine_max_y)
        fine_min_z_deg = math.degrees(self.fine_min_z)
        fine_max_z_deg = math.degrees(self.fine_max_z)

        # Store overall offsets on item so fine-tune can be recovered next open.
        item.rot_offset_x = offset_x_deg
        item.rot_offset_y = offset_y_deg
        item.rot_offset_z = offset_z_deg

        toggle = props.constraint_toggle
        enabled = (toggle == 'ALL_ON') or (toggle == 'CUSTOM')
        space_str = 'WORLD' if self.space == 'WORLD' else 'LOCAL'

        create_or_update_rotation_constraint(
            props.target_rig,
            item.target_bone,
            props.source_rig,
            item.source_bone,
            map_x_from=self.map_x_from,
            map_y_from=self.map_y_from,
            map_z_from=self.map_z_from,
            invert_x=self.invert_x,
            invert_y=self.invert_y,
            invert_z=self.invert_z,
            offset_x=offset_x_deg,
            offset_y=offset_y_deg,
            offset_z=offset_z_deg,
            fine_min_x=fine_min_x_deg, fine_max_x=fine_max_x_deg,
            fine_min_y=fine_min_y_deg, fine_max_y=fine_max_y_deg,
            fine_min_z=fine_min_z_deg, fine_max_z=fine_max_z_deg,
            target_space=space_str,
            owner_space=space_str,
            enabled=enabled,
        )

    def _write_to_location_constraint(self, context):
        """
        Write current location operator properties back to the constraint.
        Stores the overall offset on item for fine-tune recovery on next open.
        Creates the constraint if it does not exist.
        """
        props, item, tgt_pbone = self._get_item_and_bones(context)
        if not tgt_pbone:
            return

        # Store overall offsets on item so fine-tune can be recovered next open.
        item.loc_offset_x = self.loc_offset_x
        item.loc_offset_y = self.loc_offset_y
        item.loc_offset_z = self.loc_offset_z

        toggle = props.constraint_toggle
        enabled = (toggle == 'ALL_ON') or (toggle == 'CUSTOM')
        space_str = 'WORLD' if self.loc_space == 'WORLD' else 'LOCAL'

        create_or_update_location_constraint(
            props.target_rig,
            item.target_bone,
            props.source_rig,
            item.source_bone,
            map_x_from=self.loc_map_x_from,
            map_y_from=self.loc_map_y_from,
            map_z_from=self.loc_map_z_from,
            invert_x=self.loc_invert_x,
            invert_y=self.loc_invert_y,
            invert_z=self.loc_invert_z,
            offset_x=self.loc_offset_x,
            offset_y=self.loc_offset_y,
            offset_z=self.loc_offset_z,
            fine_min_x=self.loc_fine_min_x, fine_max_x=self.loc_fine_max_x,
            fine_min_y=self.loc_fine_min_y, fine_max_y=self.loc_fine_max_y,
            fine_min_z=self.loc_fine_min_z, fine_max_z=self.loc_fine_max_z,
            target_space=space_str,
            owner_space=space_str,
            enabled=enabled,
        )

    # ── Operator interface ────────────────────────────────────────────────

    def invoke(self, context, event):
        props = context.scene.easy_retarget

        if not (0 <= self.pair_index < len(props.bone_pairs)):
            return {'CANCELLED'}
        if not props.source_rig or not props.target_rig:
            self.report({'WARNING'}, "EasyRetarget: Source and Target rigs required.")
            return {'CANCELLED'}

        # Select this pair in the list.
        props.bone_pairs_index = self.pair_index

        props, item, tgt_pbone = self._get_item_and_bones(context)
        if not tgt_pbone:
            self.report({'WARNING'}, "EasyRetarget: Target bone not found.")
            return {'CANCELLED'}

        # Restore per-pair expanded states.
        self.rot_expanded           = item.rotation_expanded
        self.loc_expanded           = item.location_expanded
        self.rot_fine_tune_expanded = item.rot_fine_tune_expanded
        self.loc_fine_tune_expanded = item.loc_fine_tune_expanded

        # Read addon preferences for default creation behaviour.
        addon_prefs = context.preferences.addons.get(__package__)
        if addon_prefs:
            create_rot_default = addon_prefs.preferences.create_rotation_by_default
            create_loc_default = addon_prefs.preferences.create_location_by_default
        else:
            create_rot_default = True
            create_loc_default = False

        toggle = props.constraint_toggle
        enabled = (toggle == 'ALL_ON') or (toggle == 'CUSTOM')

        # ── Rotation ─────────────────────────────────────────────────
        self._reset_rotation_properties()
        rot_con = find_rotation_constraint(tgt_pbone)
        if rot_con is not None:
            self._had_rotation = True
            self._read_from_rotation_constraint(rot_con, item)
            log(f"  EditConstraint.invoke: read existing rotation on {item.target_bone}")
        else:
            self._had_rotation = False
            if create_rot_default and not self.blank_slate:
                create_or_update_rotation_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from='X', map_y_from='Y', map_z_from='Z',
                    invert_x=False, invert_y=False, invert_z=False,
                    enabled=enabled,
                )
                log(f"  EditConstraint.invoke: auto-created rotation on {item.target_bone} (pref)")

        # ── Location ─────────────────────────────────────────────────
        self._reset_location_properties()
        loc_con = find_location_constraint(tgt_pbone)
        if loc_con is not None:
            self._had_location = True
            self._read_from_location_constraint(loc_con, item)
            log(f"  EditConstraint.invoke: read existing location on {item.target_bone}")
        else:
            self._had_location = False
            if create_loc_default and not self.blank_slate:
                create_or_update_location_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from='X', map_y_from='Y', map_z_from='Z',
                    invert_x=False, invert_y=False, invert_z=False,
                    enabled=enabled,
                )
                log(f"  EditConstraint.invoke: auto-created location on {item.target_bone} (pref)")

        # ── Snapshot for cancel ───────────────────────────────────────
        self._snapshot_rotation_properties()
        self._snapshot_location_properties()

        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout

        if not (0 <= self.pair_index < len(context.scene.easy_retarget.bone_pairs)):
            layout.label(text="Invalid bone pair index.", icon='ERROR')
            return

        props, item, tgt_pbone = self._get_item_and_bones(context)

        rot_con = find_rotation_constraint(tgt_pbone) if tgt_pbone else None
        loc_con = find_location_constraint(tgt_pbone) if tgt_pbone else None

        # ── Target bone label ─────────────────────────────────────────
        box = layout.box()
        box.label(text="Target")
        box.label(text=f"Bone: {item.source_bone}", icon='BONE_DATA')

        layout.separator()

        # ── Rotation section ──────────────────────────────────────────
        rot_box = layout.box()
        rot_header = rot_box.row()
        rot_header.prop(
            self, "rot_expanded",
            icon='TRIA_DOWN' if self.rot_expanded else 'TRIA_RIGHT',
            icon_only=True,
            emboss=False,
        )
        rot_header.label(text="Rotation", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        if rot_con is None:
            rot_header.prop(self, "add_rotation_requested",
                            text="Add", icon='ADD', toggle=True)

        if self.rot_expanded and rot_con is not None:
            row = rot_box.row(align=True)
            row.prop_enum(self, "space", 'LOCAL')
            row.prop_enum(self, "space", 'WORLD')

            rot_box.separator(factor=0.5)

            header = rot_box.row(align=True)
            header.label(text="Axis")
            header.label(text="Source")
            header.label(text="Invert")
            offset_label = "Offset (World)" if self.space == 'WORLD' else "Offset (Local)"
            header.label(text=offset_label)

            for axis, map_prop, inv_prop, off_prop in (
                ('X', 'map_x_from', 'invert_x', 'offset_x'),
                ('Y', 'map_y_from', 'invert_y', 'offset_y'),
                ('Z', 'map_z_from', 'invert_z', 'offset_z'),
            ):
                row = rot_box.row(align=True)
                row.label(text=axis)
                row.prop(self, map_prop, text="")
                sub = row.row(align=True)
                sub.enabled = getattr(self, map_prop) != 'NONE'
                sub.prop(self, inv_prop, text="", icon='ARROW_LEFTRIGHT')
                sub.prop(self, off_prop, text="")

            rot_box.separator(factor=0.5)
            ft_row = rot_box.row()
            ft_row.prop(
                self, "rot_fine_tune_expanded",
                icon='TRIA_DOWN' if self.rot_fine_tune_expanded else 'TRIA_RIGHT',
                icon_only=True,
                emboss=False,
            )
            ft_row.label(text="Fine Tune", icon='MODIFIER')

            if self.rot_fine_tune_expanded:
                ft_header = rot_box.row(align=True)
                ft_header.label(text="Axis")
                ft_header.label(text="Min")
                ft_header.label(text="Max")

                for axis, map_prop, min_prop, max_prop in (
                    ('X', 'map_x_from', 'fine_min_x', 'fine_max_x'),
                    ('Y', 'map_y_from', 'fine_min_y', 'fine_max_y'),
                    ('Z', 'map_z_from', 'fine_min_z', 'fine_max_z'),
                ):
                    row = rot_box.row(align=True)
                    row.label(text=axis)
                    sub = row.row(align=True)
                    sub.enabled = getattr(self, map_prop) != 'NONE'
                    sub.prop(self, min_prop, text="")
                    sub.prop(self, max_prop, text="")

            rot_box.separator(factor=0.5)
            if not self.remove_rot_confirm:
                rot_box.prop(self, "remove_rot_confirm",
                             text="Remove Rotation", icon='TRASH', toggle=True)
            else:
                confirm_row = rot_box.row(align=True)
                confirm_row.alert = True
                confirm_row.label(text="Remove rotation constraint?")
                confirm_row.prop(self, "remove_rot_execute",
                                 text="Yes", icon='CHECKMARK', toggle=True)
                confirm_row.prop(self, "remove_rot_confirm",
                                 text="No", icon='X', toggle=True)

        # ── Location section ──────────────────────────────────────────
        loc_box = layout.box()
        loc_header = loc_box.row()
        loc_header.prop(
            self, "loc_expanded",
            icon='TRIA_DOWN' if self.loc_expanded else 'TRIA_RIGHT',
            icon_only=True,
            emboss=False,
        )
        loc_header.label(text="Location", icon='CON_LOCLIMIT')
        if loc_con is None:
            loc_header.prop(self, "add_location_requested",
                            text="Add", icon='ADD', toggle=True)

        if self.loc_expanded and loc_con is not None:
            row = loc_box.row(align=True)
            row.prop_enum(self, "loc_space", 'LOCAL')
            row.prop_enum(self, "loc_space", 'WORLD')

            loc_box.separator(factor=0.5)

            header = loc_box.row(align=True)
            header.label(text="Axis")
            header.label(text="Source")
            header.label(text="Invert")
            loc_offset_label = "Offset (World)" if self.loc_space == 'WORLD' else "Offset (Local)"
            header.label(text=loc_offset_label)

            for axis, map_prop, inv_prop, off_prop in (
                ('X', 'loc_map_x_from', 'loc_invert_x', 'loc_offset_x'),
                ('Y', 'loc_map_y_from', 'loc_invert_y', 'loc_offset_y'),
                ('Z', 'loc_map_z_from', 'loc_invert_z', 'loc_offset_z'),
            ):
                row = loc_box.row(align=True)
                row.label(text=axis)
                row.prop(self, map_prop, text="")
                sub = row.row(align=True)
                sub.enabled = getattr(self, map_prop) != 'NONE'
                sub.prop(self, inv_prop, text="", icon='ARROW_LEFTRIGHT')
                sub.prop(self, off_prop, text="")

            loc_box.separator(factor=0.5)
            ft_row = loc_box.row()
            ft_row.prop(
                self, "loc_fine_tune_expanded",
                icon='TRIA_DOWN' if self.loc_fine_tune_expanded else 'TRIA_RIGHT',
                icon_only=True,
                emboss=False,
            )
            ft_row.label(text="Fine Tune", icon='MODIFIER')

            if self.loc_fine_tune_expanded:
                ft_header = loc_box.row(align=True)
                ft_header.label(text="Axis")
                ft_header.label(text="Min")
                ft_header.label(text="Max")

                for axis, map_prop, min_prop, max_prop in (
                    ('X', 'loc_map_x_from', 'loc_fine_min_x', 'loc_fine_max_x'),
                    ('Y', 'loc_map_y_from', 'loc_fine_min_y', 'loc_fine_max_y'),
                    ('Z', 'loc_map_z_from', 'loc_fine_min_z', 'loc_fine_max_z'),
                ):
                    row = loc_box.row(align=True)
                    row.label(text=axis)
                    sub = row.row(align=True)
                    sub.enabled = getattr(self, map_prop) != 'NONE'
                    sub.prop(self, min_prop, text="")
                    sub.prop(self, max_prop, text="")

            loc_box.separator(factor=0.5)
            if not self.remove_loc_confirm:
                loc_box.prop(self, "remove_loc_confirm",
                             text="Remove Location", icon='TRASH', toggle=True)
            else:
                confirm_row = loc_box.row(align=True)
                confirm_row.alert = True
                confirm_row.label(text="Remove location constraint?")
                confirm_row.prop(self, "remove_loc_execute",
                                 text="Yes", icon='CHECKMARK', toggle=True)
                confirm_row.prop(self, "remove_loc_confirm",
                                 text="No", icon='X', toggle=True)

    def check(self, context):
        """Called on every property change — handle add/remove, sync state, write constraints."""
        props, item, tgt_pbone = self._get_item_and_bones(context)
        if not tgt_pbone:
            return True

        toggle = props.constraint_toggle
        enabled = (toggle == 'ALL_ON') or (toggle == 'CUSTOM')

        # ── Handle add requests ───────────────────────────────────────
        if self.add_rotation_requested:
            self.add_rotation_requested = False
            if find_rotation_constraint(tgt_pbone) is None:
                create_or_update_rotation_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from='X', map_y_from='Y', map_z_from='Z',
                    invert_x=False, invert_y=False, invert_z=False,
                    enabled=enabled,
                )
                self._reset_rotation_properties()
                log(f"  EditConstraint.check: added rotation on {item.target_bone}")

        if self.add_location_requested:
            self.add_location_requested = False
            if find_location_constraint(tgt_pbone) is None:
                create_or_update_location_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from='X', map_y_from='Y', map_z_from='Z',
                    invert_x=False, invert_y=False, invert_z=False,
                    enabled=enabled,
                )
                self._reset_location_properties()
                log(f"  EditConstraint.check: added location on {item.target_bone}")

        # ── Handle remove executions ──────────────────────────────────
        if self.remove_rot_execute:
            self.remove_rot_execute = False
            self.remove_rot_confirm = False
            remove_rotation_constraint(tgt_pbone)
            log(f"  EditConstraint.check: removed rotation on {item.target_bone}")

        if self.remove_loc_execute:
            self.remove_loc_execute = False
            self.remove_loc_confirm = False
            remove_location_constraint(tgt_pbone)
            log(f"  EditConstraint.check: removed location on {item.target_bone}")

        # ── Sync expanded states to BonePairItem for persistence ──────
        item.rotation_expanded      = self.rot_expanded
        item.location_expanded      = self.loc_expanded
        item.rot_fine_tune_expanded = self.rot_fine_tune_expanded
        item.loc_fine_tune_expanded = self.loc_fine_tune_expanded

        # ── Write constraints (only if they exist) ────────────────────
        if find_rotation_constraint(tgt_pbone) is not None:
            self._write_to_rotation_constraint(context)

        if find_location_constraint(tgt_pbone) is not None:
            self._write_to_location_constraint(context)

        return True

    def execute(self, context):
        props, item, tgt_pbone = self._get_item_and_bones(context)
        if tgt_pbone:
            item.rotation_expanded      = self.rot_expanded
            item.location_expanded      = self.loc_expanded
            item.rot_fine_tune_expanded = self.rot_fine_tune_expanded
            item.loc_fine_tune_expanded = self.loc_fine_tune_expanded
            if find_rotation_constraint(tgt_pbone) is not None:
                self._write_to_rotation_constraint(context)
            if find_location_constraint(tgt_pbone) is not None:
                self._write_to_location_constraint(context)
        return {'FINISHED'}

    def cancel(self, context):
        """
        Restore all constraints to their pre-invoke state.

        If a constraint existed before the popup (_had_rotation/_had_location),
        it is removed (cleanup) and then recreated from the snapshot. If it did
        not exist before, any constraint created during the popup is removed.
        """
        props, item, tgt_pbone = self._get_item_and_bones(context)
        if not tgt_pbone:
            return

        # ── Rotation ─────────────────────────────────────────────────
        remove_rotation_constraint(tgt_pbone)
        if self._had_rotation:
            self._restore_rotation_snapshot()
            self._write_to_rotation_constraint(context)
            log("  EditConstraint.cancel: restored rotation to pre-invoke state")
        else:
            log(f"  EditConstraint.cancel: removed rotation created during popup on {item.target_bone}")

        # ── Location ─────────────────────────────────────────────────
        remove_location_constraint(tgt_pbone)
        if self._had_location:
            self._restore_location_snapshot()
            self._write_to_location_constraint(context)
            log("  EditConstraint.cancel: restored location to pre-invoke state")
        else:
            log(f"  EditConstraint.cancel: removed location created during popup on {item.target_bone}")

        # Restore expanded states in BonePairItem.
        item.rotation_expanded      = self._snap_rot_expanded
        item.location_expanded      = self._snap_loc_expanded
        item.rot_fine_tune_expanded = self._snap_rot_fine_tune_expanded
        item.loc_fine_tune_expanded = self._snap_loc_fine_tune_expanded


# =====================================================================
# Create Constraints (all pairs)
# =====================================================================

class EASYRETARGET_OT_CreateConstraints(Operator):
    """
    Create or reset EasyRetarget constraints for all populated bone pairs with
    defaults (X→X, Y→Y, Z→Z, no inversion, Local space). The popup presents
    checkboxes for Rotation and Location that default to the addon preferences,
    allowing per-run overrides without changing preferences.
    """
    bl_idname = "easy_retarget.create_constraints"
    bl_label = "Create Constraints"
    bl_options = {'REGISTER', 'UNDO'}

    create_rotation: BoolProperty(
        name="Rotation",
        description="Create or reset the EasyRetarget_Rotation constraint on all populated bone pairs",
        default=True,
    )
    create_location: BoolProperty(
        name="Location",
        description="Create or reset the EasyRetarget_Location constraint on all populated bone pairs",
        default=False,
    )

    def invoke(self, context, event):
        # Seed checkboxes from addon preferences so they reflect the user's
        # defaults while still being adjustable per-run.
        addon_prefs = context.preferences.addons.get(__package__)
        if addon_prefs:
            self.create_rotation = addon_prefs.preferences.create_rotation_by_default
            self.create_location = addon_prefs.preferences.create_location_by_default
        else:
            self.create_rotation = True
            self.create_location = False
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout

        # Constraint type selection.
        layout.label(text="Constraint types to create or reset:")
        row = layout.row(align=True)
        row.prop(self, "create_rotation")
        row.prop(self, "create_location")
        layout.separator(factor=0.5)

        # Dynamic alert/info below the checkboxes.
        if self.create_rotation or self.create_location:
            types = []
            if self.create_rotation:
                types.append("Rotation")
            if self.create_location:
                types.append("Location")
            type_str = " and ".join(types)
            warn_box = layout.box()
            warn_box.alert = True
            col = warn_box.column(align=True)
            col.scale_y = 1.3
            col.label(
                text=f"This will create or reset {type_str} constraints for all bone pairs.",
                icon='ERROR',
            )
            col.label(text="Any existing matching constraint settings will be overwritten.")
        else:
            info_box = layout.box()
            col = info_box.column(align=True)
            col.scale_y = 1.3
            col.label(text="No constraint types selected — nothing will be created.", icon='INFO')

    def execute(self, context):
        props = context.scene.easy_retarget

        if not props.source_rig or not props.target_rig:
            self.report({'WARNING'}, "EasyRetarget: Source and Target rigs required.")
            return {'CANCELLED'}

        if not self.create_rotation and not self.create_location:
            self.report({'INFO'}, "EasyRetarget: No constraint types selected.")
            return {'CANCELLED'}

        toggle = props.constraint_toggle
        enabled = (toggle == 'ALL_ON') or (toggle == 'CUSTOM')

        rot_count = 0
        loc_count = 0
        for item in props.bone_pairs:
            if not item.source_bone or not item.target_bone:
                continue
            if self.create_rotation:
                con = create_or_update_rotation_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from='X', map_y_from='Y', map_z_from='Z',
                    invert_x=False, invert_y=False, invert_z=False,
                    target_space='LOCAL', owner_space='LOCAL',
                    enabled=enabled,
                )
                if con:
                    rot_count += 1
            if self.create_location:
                con = create_or_update_location_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from='X', map_y_from='Y', map_z_from='Z',
                    invert_x=False, invert_y=False, invert_z=False,
                    target_space='LOCAL', owner_space='LOCAL',
                    enabled=enabled,
                )
                if con:
                    loc_count += 1

        parts = []
        if self.create_rotation:
            parts.append(f"{rot_count} rotation")
        if self.create_location:
            parts.append(f"{loc_count} location")
        self.report(
            {'INFO'},
            f"EasyRetarget: Created/updated {' and '.join(parts)} constraints.",
        )
        return {'FINISHED'}


# =====================================================================
# Remove All Constraints
# =====================================================================

class EASYRETARGET_OT_RemoveAllConstraints(Operator):
    """Remove all EasyRetarget constraints (rotation and location) from all paired target bones."""
    bl_idname = "easy_retarget.remove_all_constraints"
    bl_label = "Remove All Constraints"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        warn_box = layout.box()
        warn_box.alert = True
        col = warn_box.column(align=True)
        col.scale_y = 1.4
        col.label(text="This will remove all EasyRetarget constraints (rotation and location).", icon='ERROR')
        col.label(text="This cannot be undone.")

    def execute(self, context):
        props = context.scene.easy_retarget

        if not props.target_rig:
            self.report({'WARNING'}, "EasyRetarget: No Target Rig selected.")
            return {'CANCELLED'}

        count = 0
        for item in props.bone_pairs:
            if not item.target_bone:
                continue
            pbone = get_bone(props.target_rig, item.target_bone)
            if pbone:
                rot_con = find_rotation_constraint(pbone)
                loc_con = find_location_constraint(pbone)
                if rot_con:
                    remove_rotation_constraint(pbone)
                    count += 1
                if loc_con:
                    remove_location_constraint(pbone)
                    count += 1

        props.constraint_toggle = 'CUSTOM'
        props.constraint_state_snapshot.clear()

        self.report({'INFO'}, f"EasyRetarget: Removed {count} constraints.")
        return {'FINISHED'}


# =====================================================================
# Copy Constraint Settings
# =====================================================================

class EASYRETARGET_OT_CopyConstraintSettings(Operator):
    """Copy the EasyRetarget constraint settings from the selected bone pair."""
    bl_idname = "easy_retarget.copy_constraint_settings"
    bl_label = "Copy Constraint Settings"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        props = context.scene.easy_retarget
        if not props.target_rig:
            return False
        if not (0 <= props.bone_pairs_index < len(props.bone_pairs)):
            return False
        item = props.bone_pairs[props.bone_pairs_index]
        pbone = get_bone(props.target_rig, item.target_bone)
        return bool(pbone and (find_rotation_constraint(pbone) or find_location_constraint(pbone)))

    def execute(self, context):
        global _constraint_clipboard
        props = context.scene.easy_retarget
        item = props.bone_pairs[props.bone_pairs_index]
        pbone = get_bone(props.target_rig, item.target_bone)

        def _is_none_rot(min_r, max_r):
            return math.isclose(min_r, 0.0) and math.isclose(max_r, 0.0)

        def _is_inverted(min_a, max_a):
            return max_a < min_a

        def _is_none_loc(min_v, max_v):
            return math.isclose(min_v, 0.0) and math.isclose(max_v, 0.0)

        axis_map = {'X': 'X', 'Y': 'Y', 'Z': 'Z'}

        # ── Rotation ─────────────────────────────────────────────────
        rot_data = None
        rot_con = find_rotation_constraint(pbone)
        if rot_con:
            map_x = 'NONE' if _is_none_rot(rot_con.to_min_x_rot, rot_con.to_max_x_rot) else axis_map.get(rot_con.map_to_x_from, 'X')
            map_y = 'NONE' if _is_none_rot(rot_con.to_min_y_rot, rot_con.to_max_y_rot) else axis_map.get(rot_con.map_to_y_from, 'Y')
            map_z = 'NONE' if _is_none_rot(rot_con.to_min_z_rot, rot_con.to_max_z_rot) else axis_map.get(rot_con.map_to_z_from, 'Z')
            inv_x = _is_inverted(rot_con.to_min_x_rot, rot_con.to_max_x_rot)
            inv_y = _is_inverted(rot_con.to_min_y_rot, rot_con.to_max_y_rot)
            inv_z = _is_inverted(rot_con.to_min_z_rot, rot_con.to_max_z_rot)

            # Use stored offset from item (lazy migration if 0.0).
            def _get_rot_offset(stored, to_min_r, inverted):
                if stored != 0.0:
                    return stored
                d = math.degrees(to_min_r)
                return (d - 180.0) if inverted else (d + 180.0)

            off_x = _get_rot_offset(item.rot_offset_x, rot_con.to_min_x_rot, inv_x) if map_x != 'NONE' else 0.0
            off_y = _get_rot_offset(item.rot_offset_y, rot_con.to_min_y_rot, inv_y) if map_y != 'NONE' else 0.0
            off_z = _get_rot_offset(item.rot_offset_z, rot_con.to_min_z_rot, inv_z) if map_z != 'NONE' else 0.0

            def _rot_fine(to_min_d, to_max_d, offset_d, inverted):
                if inverted:
                    return (to_min_d - (180.0 + offset_d),
                            to_max_d - (-180.0 + offset_d))
                return (to_min_d - (-180.0 + offset_d),
                        to_max_d - (180.0 + offset_d))

            fm_x, fx_x = _rot_fine(math.degrees(rot_con.to_min_x_rot), math.degrees(rot_con.to_max_x_rot), off_x, inv_x) if map_x != 'NONE' else (0.0, 0.0)
            fm_y, fx_y = _rot_fine(math.degrees(rot_con.to_min_y_rot), math.degrees(rot_con.to_max_y_rot), off_y, inv_y) if map_y != 'NONE' else (0.0, 0.0)
            fm_z, fx_z = _rot_fine(math.degrees(rot_con.to_min_z_rot), math.degrees(rot_con.to_max_z_rot), off_z, inv_z) if map_z != 'NONE' else (0.0, 0.0)

            rot_data = {
                'map_x_from': map_x, 'map_y_from': map_y, 'map_z_from': map_z,
                'invert_x': inv_x, 'invert_y': inv_y, 'invert_z': inv_z,
                'offset_x': off_x, 'offset_y': off_y, 'offset_z': off_z,
                'fine_min_x': fm_x, 'fine_max_x': fx_x,
                'fine_min_y': fm_y, 'fine_max_y': fx_y,
                'fine_min_z': fm_z, 'fine_max_z': fx_z,
                'space': 'WORLD' if rot_con.target_space == 'WORLD' else 'LOCAL',
            }

        # ── Location ─────────────────────────────────────────────────
        loc_data = None
        loc_con = find_location_constraint(pbone)
        if loc_con:
            map_x = 'NONE' if _is_none_loc(loc_con.to_min_x, loc_con.to_max_x) else axis_map.get(loc_con.map_to_x_from, 'X')
            map_y = 'NONE' if _is_none_loc(loc_con.to_min_y, loc_con.to_max_y) else axis_map.get(loc_con.map_to_y_from, 'Y')
            map_z = 'NONE' if _is_none_loc(loc_con.to_min_z, loc_con.to_max_z) else axis_map.get(loc_con.map_to_z_from, 'Z')
            inv_x = _is_inverted(loc_con.to_min_x, loc_con.to_max_x)
            inv_y = _is_inverted(loc_con.to_min_y, loc_con.to_max_y)
            inv_z = _is_inverted(loc_con.to_min_z, loc_con.to_max_z)

            half_range = 100.0

            def _get_loc_offset(stored, to_min_v, inverted):
                if stored != 0.0:
                    return stored
                return (to_min_v - half_range) if inverted else (to_min_v + half_range)

            off_x = _get_loc_offset(item.loc_offset_x, loc_con.to_min_x, inv_x) if map_x != 'NONE' else 0.0
            off_y = _get_loc_offset(item.loc_offset_y, loc_con.to_min_y, inv_y) if map_y != 'NONE' else 0.0
            off_z = _get_loc_offset(item.loc_offset_z, loc_con.to_min_z, inv_z) if map_z != 'NONE' else 0.0

            def _loc_fine(to_min_v, to_max_v, offset_v, inverted):
                if inverted:
                    return (to_min_v - (half_range + offset_v),
                            to_max_v - (-half_range + offset_v))
                return (to_min_v - (-half_range + offset_v),
                        to_max_v - (half_range + offset_v))

            fm_x, fx_x = _loc_fine(loc_con.to_min_x, loc_con.to_max_x, off_x, inv_x) if map_x != 'NONE' else (0.0, 0.0)
            fm_y, fx_y = _loc_fine(loc_con.to_min_y, loc_con.to_max_y, off_y, inv_y) if map_y != 'NONE' else (0.0, 0.0)
            fm_z, fx_z = _loc_fine(loc_con.to_min_z, loc_con.to_max_z, off_z, inv_z) if map_z != 'NONE' else (0.0, 0.0)

            loc_data = {
                'map_x_from': map_x, 'map_y_from': map_y, 'map_z_from': map_z,
                'invert_x': inv_x, 'invert_y': inv_y, 'invert_z': inv_z,
                'offset_x': off_x, 'offset_y': off_y, 'offset_z': off_z,
                'fine_min_x': fm_x, 'fine_max_x': fx_x,
                'fine_min_y': fm_y, 'fine_max_y': fx_y,
                'fine_min_z': fm_z, 'fine_max_z': fx_z,
                'space': 'WORLD' if loc_con.target_space == 'WORLD' else 'LOCAL',
            }

        _constraint_clipboard = {'rotation': rot_data, 'location': loc_data}

        log(f"  CopyConstraintSettings: copied from {item.target_bone} (rot={rot_data is not None}, loc={loc_data is not None})")
        self.report({'INFO'}, "EasyRetarget: Constraint settings copied.")
        return {'FINISHED'}


# =====================================================================
# Paste Constraint Settings
# =====================================================================

class EASYRETARGET_OT_PasteConstraintSettings(Operator):
    """Paste copied constraint settings to the selected bone pair's constraints."""
    bl_idname = "easy_retarget.paste_constraint_settings"
    bl_label = "Paste Constraint Settings"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if _constraint_clipboard is None:
            return False
        props = context.scene.easy_retarget
        if not props.source_rig or not props.target_rig:
            return False
        if not (0 <= props.bone_pairs_index < len(props.bone_pairs)):
            return False
        item = props.bone_pairs[props.bone_pairs_index]
        return bool(item.source_bone and item.target_bone)

    def execute(self, context):
        if _constraint_clipboard is None:
            return {'CANCELLED'}

        props = context.scene.easy_retarget
        item = props.bone_pairs[props.bone_pairs_index]

        toggle = props.constraint_toggle
        enabled = (toggle == 'ALL_ON') or (toggle == 'CUSTOM')

        # ── Rotation ─────────────────────────────────────────────────
        rot_data = _constraint_clipboard.get('rotation')
        if rot_data:
            space = rot_data['space']
            create_or_update_rotation_constraint(
                props.target_rig, item.target_bone,
                props.source_rig, item.source_bone,
                map_x_from=rot_data['map_x_from'],
                map_y_from=rot_data['map_y_from'],
                map_z_from=rot_data['map_z_from'],
                invert_x=rot_data['invert_x'],
                invert_y=rot_data['invert_y'],
                invert_z=rot_data['invert_z'],
                offset_x=rot_data['offset_x'],
                offset_y=rot_data['offset_y'],
                offset_z=rot_data['offset_z'],
                fine_min_x=rot_data.get('fine_min_x', 0.0),
                fine_max_x=rot_data.get('fine_max_x', 0.0),
                fine_min_y=rot_data.get('fine_min_y', 0.0),
                fine_max_y=rot_data.get('fine_max_y', 0.0),
                fine_min_z=rot_data.get('fine_min_z', 0.0),
                fine_max_z=rot_data.get('fine_max_z', 0.0),
                target_space=space,
                owner_space=space,
                enabled=enabled,
            )
            item.rot_offset_x = rot_data['offset_x']
            item.rot_offset_y = rot_data['offset_y']
            item.rot_offset_z = rot_data['offset_z']

        # ── Location ─────────────────────────────────────────────────
        loc_data = _constraint_clipboard.get('location')
        if loc_data:
            space = loc_data['space']
            create_or_update_location_constraint(
                props.target_rig, item.target_bone,
                props.source_rig, item.source_bone,
                map_x_from=loc_data['map_x_from'],
                map_y_from=loc_data['map_y_from'],
                map_z_from=loc_data['map_z_from'],
                invert_x=loc_data['invert_x'],
                invert_y=loc_data['invert_y'],
                invert_z=loc_data['invert_z'],
                offset_x=loc_data['offset_x'],
                offset_y=loc_data['offset_y'],
                offset_z=loc_data['offset_z'],
                fine_min_x=loc_data.get('fine_min_x', 0.0),
                fine_max_x=loc_data.get('fine_max_x', 0.0),
                fine_min_y=loc_data.get('fine_min_y', 0.0),
                fine_max_y=loc_data.get('fine_max_y', 0.0),
                fine_min_z=loc_data.get('fine_min_z', 0.0),
                fine_max_z=loc_data.get('fine_max_z', 0.0),
                target_space=space,
                owner_space=space,
                enabled=enabled,
            )
            item.loc_offset_x = loc_data['offset_x']
            item.loc_offset_y = loc_data['offset_y']
            item.loc_offset_z = loc_data['offset_z']

        log(f"  PasteConstraintSettings: pasted to {item.target_bone}")
        self.report({'INFO'}, "EasyRetarget: Constraint settings pasted.")
        return {'FINISHED'}


# =====================================================================
# Confirm Target Bone Change
# =====================================================================

class EASYRETARGET_OT_ConfirmTargetBoneChange(Operator):
    """
    Confirmation dialog shown when a target bone is changed on a pair
    that already has EasyRetarget constraints. Removes all constraints
    from the old bone on confirm, or reverts the target bone field on cancel.
    """
    bl_idname = "easy_retarget.confirm_target_bone_change"
    bl_label = "Confirm Target Bone Change"
    bl_options = {'INTERNAL'}

    pair_index:    IntProperty(options={'SKIP_SAVE'})
    old_bone_name: StringProperty(options={'SKIP_SAVE'})
    new_bone_name: StringProperty(options={'SKIP_SAVE'})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        warn_box = layout.box()
        warn_box.alert = True
        col = warn_box.column(align=True)
        col.scale_y = 1.4
        col.label(text=f"'{self.old_bone_name}' has EasyRetarget constraints.", icon='ERROR')
        col.label(text="Changing the target bone will remove them.")
        col.label(text="Press OK to confirm or Cancel to revert.")

    def execute(self, context):
        props = context.scene.easy_retarget
        if props.target_rig:
            pbone = get_bone(props.target_rig, self.old_bone_name)
            if pbone:
                remove_rotation_constraint(pbone)
                remove_location_constraint(pbone)
        if 0 <= self.pair_index < len(props.bone_pairs):
            item = props.bone_pairs[self.pair_index]
            item.previous_target_bone = self.new_bone_name
            # Mark as manually confirmed since the user explicitly chose a new bone.
            item.is_manual    = True
            item.match_reason = ""
            if item.source_bone and self.new_bone_name:
                item.match_status = 'CONFIRMED'
        return {'FINISHED'}

    def cancel(self, context):
        props = context.scene.easy_retarget
        if 0 <= self.pair_index < len(props.bone_pairs):
            item = props.bone_pairs[self.pair_index]
            item.target_bone = self.old_bone_name
            item.previous_target_bone = self.old_bone_name
