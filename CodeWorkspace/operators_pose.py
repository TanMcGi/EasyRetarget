# =====================================================================
# EasyRetarget - operators_pose.py
# Pose mode operators: pie menu, retarget space, adjust inversions,
# and open mapping popup for active bone.
# =====================================================================

import math
import bpy
from bpy.types import Operator, Menu
from bpy.props import BoolProperty, EnumProperty

from .constraint_utils import (
    find_rotation_constraint,
    find_location_constraint,
)
from .debug import log


# =====================================================================
# Inversion helpers — manipulate to_min/to_max directly
#
# Invert state is encoded as to_max < to_min in Blender's Transform
# constraint. To flip inversion while preserving offset and fine-tune:
#   Non-inverted → Inverted:  to_min += 2*half_range, to_max -= 2*half_range
#   Inverted → Non-inverted:  to_min -= 2*half_range, to_max += 2*half_range
# =====================================================================

_ROT_HALF_RANGE = math.pi   # 180° in radians
_LOC_HALF_RANGE = 100.0     # Blender units


def _is_axis_none(a, b):
    """Return True if the axis is mapped to NONE (both range ends are 0)."""
    return math.isclose(a, 0.0) and math.isclose(b, 0.0)


def _is_inverted(a, b):
    """Return True if the axis range is inverted (to_max < to_min)."""
    return b < a


def _set_axis_invert_rot(con, axis, target_inverted):
    """Set the invert state of one rotation axis without disturbing offset or fine-tune."""
    hr = _ROT_HALF_RANGE
    if axis == 'X':
        a, b = con.to_min_x_rot, con.to_max_x_rot
        if _is_axis_none(a, b) or _is_inverted(a, b) == target_inverted:
            return
        if target_inverted:
            con.to_min_x_rot = a + 2 * hr
            con.to_max_x_rot = b - 2 * hr
        else:
            con.to_min_x_rot = a - 2 * hr
            con.to_max_x_rot = b + 2 * hr
    elif axis == 'Y':
        a, b = con.to_min_y_rot, con.to_max_y_rot
        if _is_axis_none(a, b) or _is_inverted(a, b) == target_inverted:
            return
        if target_inverted:
            con.to_min_y_rot = a + 2 * hr
            con.to_max_y_rot = b - 2 * hr
        else:
            con.to_min_y_rot = a - 2 * hr
            con.to_max_y_rot = b + 2 * hr
    elif axis == 'Z':
        a, b = con.to_min_z_rot, con.to_max_z_rot
        if _is_axis_none(a, b) or _is_inverted(a, b) == target_inverted:
            return
        if target_inverted:
            con.to_min_z_rot = a + 2 * hr
            con.to_max_z_rot = b - 2 * hr
        else:
            con.to_min_z_rot = a - 2 * hr
            con.to_max_z_rot = b + 2 * hr


def _toggle_axis_invert_rot(con, axis):
    """Toggle the invert state of one rotation axis."""
    hr = _ROT_HALF_RANGE
    if axis == 'X':
        a, b = con.to_min_x_rot, con.to_max_x_rot
        if _is_axis_none(a, b):
            return
        if _is_inverted(a, b):
            con.to_min_x_rot = a - 2 * hr
            con.to_max_x_rot = b + 2 * hr
        else:
            con.to_min_x_rot = a + 2 * hr
            con.to_max_x_rot = b - 2 * hr
    elif axis == 'Y':
        a, b = con.to_min_y_rot, con.to_max_y_rot
        if _is_axis_none(a, b):
            return
        if _is_inverted(a, b):
            con.to_min_y_rot = a - 2 * hr
            con.to_max_y_rot = b + 2 * hr
        else:
            con.to_min_y_rot = a + 2 * hr
            con.to_max_y_rot = b - 2 * hr
    elif axis == 'Z':
        a, b = con.to_min_z_rot, con.to_max_z_rot
        if _is_axis_none(a, b):
            return
        if _is_inverted(a, b):
            con.to_min_z_rot = a - 2 * hr
            con.to_max_z_rot = b + 2 * hr
        else:
            con.to_min_z_rot = a + 2 * hr
            con.to_max_z_rot = b - 2 * hr


def _set_axis_invert_loc(con, axis, target_inverted):
    """Set the invert state of one location axis without disturbing offset or fine-tune."""
    hr = _LOC_HALF_RANGE
    if axis == 'X':
        a, b = con.to_min_x, con.to_max_x
        if _is_axis_none(a, b) or _is_inverted(a, b) == target_inverted:
            return
        if target_inverted:
            con.to_min_x = a + 2 * hr
            con.to_max_x = b - 2 * hr
        else:
            con.to_min_x = a - 2 * hr
            con.to_max_x = b + 2 * hr
    elif axis == 'Y':
        a, b = con.to_min_y, con.to_max_y
        if _is_axis_none(a, b) or _is_inverted(a, b) == target_inverted:
            return
        if target_inverted:
            con.to_min_y = a + 2 * hr
            con.to_max_y = b - 2 * hr
        else:
            con.to_min_y = a - 2 * hr
            con.to_max_y = b + 2 * hr
    elif axis == 'Z':
        a, b = con.to_min_z, con.to_max_z
        if _is_axis_none(a, b) or _is_inverted(a, b) == target_inverted:
            return
        if target_inverted:
            con.to_min_z = a + 2 * hr
            con.to_max_z = b - 2 * hr
        else:
            con.to_min_z = a - 2 * hr
            con.to_max_z = b + 2 * hr


def _toggle_axis_invert_loc(con, axis):
    """Toggle the invert state of one location axis."""
    hr = _LOC_HALF_RANGE
    if axis == 'X':
        a, b = con.to_min_x, con.to_max_x
        if _is_axis_none(a, b):
            return
        if _is_inverted(a, b):
            con.to_min_x = a - 2 * hr
            con.to_max_x = b + 2 * hr
        else:
            con.to_min_x = a + 2 * hr
            con.to_max_x = b - 2 * hr
    elif axis == 'Y':
        a, b = con.to_min_y, con.to_max_y
        if _is_axis_none(a, b):
            return
        if _is_inverted(a, b):
            con.to_min_y = a - 2 * hr
            con.to_max_y = b + 2 * hr
        else:
            con.to_min_y = a + 2 * hr
            con.to_max_y = b - 2 * hr
    elif axis == 'Z':
        a, b = con.to_min_z, con.to_max_z
        if _is_axis_none(a, b):
            return
        if _is_inverted(a, b):
            con.to_min_z = a - 2 * hr
            con.to_max_z = b + 2 * hr
        else:
            con.to_min_z = a + 2 * hr
            con.to_max_z = b - 2 * hr


# =====================================================================
# Snapshot storage for Adjust Inversions
# Stores to_min/to_max values captured at popup open for cancel revert.
# =====================================================================

_inv_rot_snap: dict = {}    # bone_name -> {to_min_x_rot, to_max_x_rot, ...}
_inv_loc_snap: dict = {}    # bone_name -> {to_min_x, to_max_x, ...}
_inv_has_rot: set = set()   # bone names that had a rotation constraint
_inv_has_loc: set = set()   # bone names that had a location constraint
_inv_target_bones: list = []  # ordered list of all affected bone names


# =====================================================================
# Retarget Space Operator
# =====================================================================

class EASYRETARGET_OT_RetargetSpace(Operator):
    """Set the retarget space for all selected target rig bones in Pose Mode."""
    bl_idname = "easy_retarget.retarget_space"
    bl_label = "Retarget Space"
    bl_options = {'REGISTER', 'UNDO'}

    constraint_type: EnumProperty(
        name="Constraint Type",
        items=[
            ('ROTATION', "Rotation", ""),
            ('LOCATION', "Location", ""),
        ],
        default='ROTATION',
    )
    space: EnumProperty(
        name="Space",
        items=[
            ('LOCAL', "Local", ""),
            ('WORLD', "World", ""),
        ],
        default='LOCAL',
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'POSE' and
            context.scene.easy_retarget.target_rig is not None
        )

    def execute(self, context):
        props = context.scene.easy_retarget
        target_rig = props.target_rig
        space_str = self.space

        selected_bones = [
            pb for pb in (context.selected_pose_bones or [])
            if pb.id_data == target_rig
        ]
        if not selected_bones:
            self.report({'WARNING'}, "EasyRetarget: No selected bones on the target rig.")
            return {'CANCELLED'}

        count = 0
        for pbone in selected_bones:
            if self.constraint_type == 'ROTATION':
                con = find_rotation_constraint(pbone)
                if con is None:
                    continue
                con.target_space = space_str
                con.owner_space  = space_str
                con.mix_mode_rot = 'REPLACE' if space_str == 'WORLD' else 'ADD'
                count += 1
                log(f"  RetargetSpace: {pbone.name} rotation → {space_str}")
            else:
                con = find_location_constraint(pbone)
                if con is None:
                    continue
                con.target_space = space_str
                con.owner_space  = space_str
                con.mix_mode     = 'REPLACE' if space_str == 'WORLD' else 'ADD'
                count += 1
                log(f"  RetargetSpace: {pbone.name} location → {space_str}")

        if count == 0:
            type_label = 'rotation' if self.constraint_type == 'ROTATION' else 'location'
            self.report(
                {'WARNING'},
                f"EasyRetarget: No selected bones had a {type_label} constraint.",
            )
        return {'FINISHED'}


# =====================================================================
# Adjust Inversions Popup
# =====================================================================

_INVERT_OP_ITEMS = [
    ('CURRENT',    "Current",    "Leave this axis unchanged"),
    ('ALL_ON',     "All On",     "Enable inversion for all selected bones with this constraint"),
    ('ALL_OFF',    "All Off",    "Disable inversion for all selected bones with this constraint"),
    ('TOGGLE_ALL', "Toggle All", "Flip inversion per bone independently"),
]


class EASYRETARGET_OT_AdjustInversions(Operator):
    """
    Adjust inversion for all selected target rig bones that have EasyRetarget
    constraints. Changes apply in real time; Cancel reverts to the pre-invoke state.
    """
    bl_idname = "easy_retarget.adjust_inversions"
    bl_label = "Adjust Inversions"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    # Whether each constraint type exists on any selected bone.
    has_rotation: BoolProperty(default=False, options={'SKIP_SAVE'})
    has_location: BoolProperty(default=False, options={'SKIP_SAVE'})

    # Per-axis 4-button switches.
    rot_x_op: EnumProperty(name="Rotation X", items=_INVERT_OP_ITEMS, default='CURRENT')
    rot_y_op: EnumProperty(name="Rotation Y", items=_INVERT_OP_ITEMS, default='CURRENT')
    rot_z_op: EnumProperty(name="Rotation Z", items=_INVERT_OP_ITEMS, default='CURRENT')
    loc_x_op: EnumProperty(name="Location X", items=_INVERT_OP_ITEMS, default='CURRENT')
    loc_y_op: EnumProperty(name="Location Y", items=_INVERT_OP_ITEMS, default='CURRENT')
    loc_z_op: EnumProperty(name="Location Z", items=_INVERT_OP_ITEMS, default='CURRENT')

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'POSE' and
            context.scene.easy_retarget.target_rig is not None
        )

    def _selected_target_bones(self, context):
        target_rig = context.scene.easy_retarget.target_rig
        return [
            pb for pb in (context.selected_pose_bones or [])
            if pb.id_data == target_rig
        ]

    def invoke(self, context, event):
        global _inv_rot_snap, _inv_loc_snap, _inv_has_rot, _inv_has_loc, _inv_target_bones

        _inv_rot_snap.clear()
        _inv_loc_snap.clear()
        _inv_has_rot = set()
        _inv_has_loc = set()
        _inv_target_bones = []

        selected = self._selected_target_bones(context)
        if not selected:
            self.report({'WARNING'}, "EasyRetarget: No selected bones on the target rig.")
            return {'CANCELLED'}

        for pbone in selected:
            _inv_target_bones.append(pbone.name)

            rot_con = find_rotation_constraint(pbone)
            if rot_con is not None:
                _inv_has_rot.add(pbone.name)
                _inv_rot_snap[pbone.name] = {
                    'to_min_x_rot': rot_con.to_min_x_rot,
                    'to_max_x_rot': rot_con.to_max_x_rot,
                    'to_min_y_rot': rot_con.to_min_y_rot,
                    'to_max_y_rot': rot_con.to_max_y_rot,
                    'to_min_z_rot': rot_con.to_min_z_rot,
                    'to_max_z_rot': rot_con.to_max_z_rot,
                }

            loc_con = find_location_constraint(pbone)
            if loc_con is not None:
                _inv_has_loc.add(pbone.name)
                _inv_loc_snap[pbone.name] = {
                    'to_min_x': loc_con.to_min_x, 'to_max_x': loc_con.to_max_x,
                    'to_min_y': loc_con.to_min_y, 'to_max_y': loc_con.to_max_y,
                    'to_min_z': loc_con.to_min_z, 'to_max_z': loc_con.to_max_z,
                }

        self.has_rotation = bool(_inv_has_rot)
        self.has_location = bool(_inv_has_loc)

        if not self.has_rotation and not self.has_location:
            self.report(
                {'WARNING'},
                "EasyRetarget: No selected bones have EasyRetarget constraints.",
            )
            return {'CANCELLED'}

        # Reset all switches to CURRENT before opening.
        self.rot_x_op = self.rot_y_op = self.rot_z_op = 'CURRENT'
        self.loc_x_op = self.loc_y_op = self.loc_z_op = 'CURRENT'

        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout

        if self.has_rotation:
            rot_box = layout.box()
            rot_box.label(text="Rotation", icon='DRIVER_ROTATIONAL_DIFFERENCE')
            for axis_label, prop_name in (
                ('X', 'rot_x_op'),
                ('Y', 'rot_y_op'),
                ('Z', 'rot_z_op'),
            ):
                row = rot_box.row(align=True)
                row.label(text=axis_label)
                row.prop(self, prop_name, expand=True)

        if self.has_location:
            loc_box = layout.box()
            loc_box.label(text="Location", icon='CON_LOCLIMIT')
            for axis_label, prop_name in (
                ('X', 'loc_x_op'),
                ('Y', 'loc_y_op'),
                ('Z', 'loc_z_op'),
            ):
                row = loc_box.row(align=True)
                row.label(text=axis_label)
                row.prop(self, prop_name, expand=True)

    def _apply_op(self, context, constraint_type, axis, op):
        """Apply one inversion operation to all affected bones for a single axis."""
        target_rig = context.scene.easy_retarget.target_rig
        for bone_name in _inv_target_bones:
            pbone = target_rig.pose.bones.get(bone_name)
            if pbone is None:
                continue
            if constraint_type == 'ROTATION':
                if bone_name not in _inv_has_rot:
                    continue
                con = find_rotation_constraint(pbone)
                if con is None:
                    continue
                if op == 'ALL_ON':
                    _set_axis_invert_rot(con, axis, True)
                elif op == 'ALL_OFF':
                    _set_axis_invert_rot(con, axis, False)
                elif op == 'TOGGLE_ALL':
                    _toggle_axis_invert_rot(con, axis)
            else:
                if bone_name not in _inv_has_loc:
                    continue
                con = find_location_constraint(pbone)
                if con is None:
                    continue
                if op == 'ALL_ON':
                    _set_axis_invert_loc(con, axis, True)
                elif op == 'ALL_OFF':
                    _set_axis_invert_loc(con, axis, False)
                elif op == 'TOGGLE_ALL':
                    _toggle_axis_invert_loc(con, axis)

    def check(self, context):
        changed = False

        for axis, prop in (('X', 'rot_x_op'), ('Y', 'rot_y_op'), ('Z', 'rot_z_op')):
            op = getattr(self, prop)
            if op != 'CURRENT':
                self._apply_op(context, 'ROTATION', axis, op)
                setattr(self, prop, 'CURRENT')
                changed = True

        for axis, prop in (('X', 'loc_x_op'), ('Y', 'loc_y_op'), ('Z', 'loc_z_op')):
            op = getattr(self, prop)
            if op != 'CURRENT':
                self._apply_op(context, 'LOCATION', axis, op)
                setattr(self, prop, 'CURRENT')
                changed = True

        return changed

    def execute(self, context):
        return {'FINISHED'}

    def cancel(self, context):
        """Restore all constraint ranges to their pre-invoke state."""
        target_rig = context.scene.easy_retarget.target_rig
        if not target_rig:
            return

        for bone_name, snap in _inv_rot_snap.items():
            pbone = target_rig.pose.bones.get(bone_name)
            if pbone is None:
                continue
            con = find_rotation_constraint(pbone)
            if con is None:
                continue
            con.to_min_x_rot = snap['to_min_x_rot']
            con.to_max_x_rot = snap['to_max_x_rot']
            con.to_min_y_rot = snap['to_min_y_rot']
            con.to_max_y_rot = snap['to_max_y_rot']
            con.to_min_z_rot = snap['to_min_z_rot']
            con.to_max_z_rot = snap['to_max_z_rot']

        for bone_name, snap in _inv_loc_snap.items():
            pbone = target_rig.pose.bones.get(bone_name)
            if pbone is None:
                continue
            con = find_location_constraint(pbone)
            if con is None:
                continue
            con.to_min_x = snap['to_min_x']
            con.to_max_x = snap['to_max_x']
            con.to_min_y = snap['to_min_y']
            con.to_max_y = snap['to_max_y']
            con.to_min_z = snap['to_min_z']
            con.to_max_z = snap['to_max_z']

        log("  AdjustInversions.cancel: restored pre-invoke inversion state")


# =====================================================================
# Open Mapping Popup for Active Bone
# =====================================================================

class EASYRETARGET_OT_OpenMappingForActiveBone(Operator):
    """Open the Constraint Mapping popup for the active bone in Pose Mode."""
    bl_idname = "easy_retarget.open_mapping_for_active_bone"
    bl_label = "Retarget Mapping"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        props = context.scene.easy_retarget
        return (
            context.mode == 'POSE' and
            context.active_pose_bone is not None and
            props.target_rig is not None
        )

    def execute(self, context):
        props = context.scene.easy_retarget
        target_rig = props.target_rig
        active_pbone = context.active_pose_bone

        if active_pbone is None:
            self.report({'WARNING'}, "EasyRetarget: No active bone.")
            return {'CANCELLED'}

        if active_pbone.id_data != target_rig:
            self.report(
                {'WARNING'},
                "EasyRetarget: Active bone is not on the target rig.",
            )
            return {'CANCELLED'}

        bone_name = active_pbone.name
        pair_index = -1
        for i, item in enumerate(props.bone_pairs):
            if item.target_bone == bone_name:
                pair_index = i
                break

        if pair_index == -1:
            self.report(
                {'WARNING'},
                f"EasyRetarget: '{bone_name}' is not in the bone pair list.",
            )
            return {'CANCELLED'}

        bpy.ops.easy_retarget.edit_constraint(
            'INVOKE_DEFAULT',
            pair_index=pair_index,
            blank_slate=True,
        )
        return {'FINISHED'}


# =====================================================================
# Pie Menu
# =====================================================================

class EASYRETARGET_MT_EasyRetargetPie(Menu):
    bl_label = "Easy Retarget"
    bl_idname = "EASYRETARGET_MT_EasyRetargetPie"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        # West (slot 0)
        op = pie.operator("easy_retarget.retarget_space", text="Rotation - Use Local")
        op.constraint_type = 'ROTATION'
        op.space = 'LOCAL'

        # East (slot 1)
        op = pie.operator("easy_retarget.retarget_space", text="Rotation - Use World")
        op.constraint_type = 'ROTATION'
        op.space = 'WORLD'

        # South (slot 2)
        op = pie.operator("easy_retarget.retarget_space", text="Location - Use Local")
        op.constraint_type = 'LOCATION'
        op.space = 'LOCAL'

        # North (slot 3)
        op = pie.operator("easy_retarget.retarget_space", text="Location - Use World")
        op.constraint_type = 'LOCATION'
        op.space = 'WORLD'

        # North-West (slot 4)
        pie.operator("easy_retarget.adjust_inversions", text="Inversions")

        # North-East (slot 5)
        pie.operator("easy_retarget.open_mapping_for_active_bone", text="Mapping")
