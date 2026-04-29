# =====================================================================
# EasyRetarget - operators_io.py
# JSON export and import operators for bone pair and constraint data.
# =====================================================================

import json
import math
import bpy
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .constraint_utils import (
    find_rotation_constraint,
    find_location_constraint,
    create_or_update_rotation_constraint,
    create_or_update_location_constraint,
    ensure_constraint_order,
)
from .utils import get_bone
from .debug import log


# =====================================================================
# Export
# =====================================================================

class EASYRETARGET_OT_ExportJSON(Operator, ExportHelper):
    """Export bone pairs and constraint settings to a JSON file."""
    bl_idname = "easy_retarget.export_json"
    bl_label = "Export Bone Pairs"
    bl_options = {'REGISTER'}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    filepath: StringProperty(subtype='FILE_PATH', default="")

    def execute(self, context):
        props = context.scene.easy_retarget
        data = {'bone_pairs': []}

        def _is_none_rot(min_r, max_r):
            return math.isclose(min_r, 0.0) and math.isclose(max_r, 0.0)

        def _is_inverted(min_a, max_a):
            return max_a < min_a

        def _is_none_loc(min_v, max_v):
            return math.isclose(min_v, 0.0) and math.isclose(max_v, 0.0)

        axis_map = {'X': 'X', 'Y': 'Y', 'Z': 'Z'}

        def _get_rot_offset(stored, to_min_r, inverted):
            """Return offset in degrees; lazy migration if stored is 0.0."""
            if stored != 0.0:
                return stored
            d = math.degrees(to_min_r)
            return (d - 180.0) if inverted else (d + 180.0)

        def _rot_fine(to_min_r, to_max_r, offset_deg, inverted):
            """Return (fine_min_deg, fine_max_deg) from constraint values."""
            mn = math.degrees(to_min_r)
            mx = math.degrees(to_max_r)
            if inverted:
                return (mn - (180.0 + offset_deg), mx - (-180.0 + offset_deg))
            return (mn - (-180.0 + offset_deg), mx - (180.0 + offset_deg))

        def _get_loc_offset(stored, to_min_v, inverted, half_range=100.0):
            """Return offset in Blender units; lazy migration if stored is 0.0."""
            if stored != 0.0:
                return stored
            return (to_min_v - half_range) if inverted else (to_min_v + half_range)

        def _loc_fine(to_min_v, to_max_v, offset_v, inverted, half_range=100.0):
            """Return (fine_min, fine_max) in Blender units."""
            if inverted:
                return (to_min_v - (half_range + offset_v),
                        to_max_v - (-half_range + offset_v))
            return (to_min_v - (-half_range + offset_v),
                    to_max_v - (half_range + offset_v))

        for item in props.bone_pairs:
            entry = {
                'source_bone': item.source_bone,
                'target_bone': item.target_bone,
                'rotation_constraint': None,
                'location_constraint': None,
            }

            if props.target_rig and item.target_bone:
                pbone = get_bone(props.target_rig, item.target_bone)
                if pbone:
                    # ── Rotation ────────────────────────────────────────────
                    rot_con = find_rotation_constraint(pbone)
                    if rot_con:
                        map_x = 'NONE' if _is_none_rot(rot_con.to_min_x_rot, rot_con.to_max_x_rot) else axis_map.get(rot_con.map_to_x_from, 'X')
                        map_y = 'NONE' if _is_none_rot(rot_con.to_min_y_rot, rot_con.to_max_y_rot) else axis_map.get(rot_con.map_to_y_from, 'Y')
                        map_z = 'NONE' if _is_none_rot(rot_con.to_min_z_rot, rot_con.to_max_z_rot) else axis_map.get(rot_con.map_to_z_from, 'Z')
                        inv_x = _is_inverted(rot_con.to_min_x_rot, rot_con.to_max_x_rot)
                        inv_y = _is_inverted(rot_con.to_min_y_rot, rot_con.to_max_y_rot)
                        inv_z = _is_inverted(rot_con.to_min_z_rot, rot_con.to_max_z_rot)
                        off_x = _get_rot_offset(item.rot_offset_x, rot_con.to_min_x_rot, inv_x) if map_x != 'NONE' else 0.0
                        off_y = _get_rot_offset(item.rot_offset_y, rot_con.to_min_y_rot, inv_y) if map_y != 'NONE' else 0.0
                        off_z = _get_rot_offset(item.rot_offset_z, rot_con.to_min_z_rot, inv_z) if map_z != 'NONE' else 0.0
                        fm_x, fx_x = _rot_fine(rot_con.to_min_x_rot, rot_con.to_max_x_rot, off_x, inv_x) if map_x != 'NONE' else (0.0, 0.0)
                        fm_y, fx_y = _rot_fine(rot_con.to_min_y_rot, rot_con.to_max_y_rot, off_y, inv_y) if map_y != 'NONE' else (0.0, 0.0)
                        fm_z, fx_z = _rot_fine(rot_con.to_min_z_rot, rot_con.to_max_z_rot, off_z, inv_z) if map_z != 'NONE' else (0.0, 0.0)
                        entry['rotation_constraint'] = {
                            'map_x_from': map_x, 'map_y_from': map_y, 'map_z_from': map_z,
                            'invert_x': inv_x, 'invert_y': inv_y, 'invert_z': inv_z,
                            'offset_x': off_x, 'offset_y': off_y, 'offset_z': off_z,
                            'fine_min_x': fm_x, 'fine_max_x': fx_x,
                            'fine_min_y': fm_y, 'fine_max_y': fx_y,
                            'fine_min_z': fm_z, 'fine_max_z': fx_z,
                            'space': 'WORLD' if rot_con.target_space == 'WORLD' else 'LOCAL',
                        }

                    # ── Location ─────────────────────────────────────────────
                    loc_con = find_location_constraint(pbone)
                    if loc_con:
                        map_x = 'NONE' if _is_none_loc(loc_con.to_min_x, loc_con.to_max_x) else axis_map.get(loc_con.map_to_x_from, 'X')
                        map_y = 'NONE' if _is_none_loc(loc_con.to_min_y, loc_con.to_max_y) else axis_map.get(loc_con.map_to_y_from, 'Y')
                        map_z = 'NONE' if _is_none_loc(loc_con.to_min_z, loc_con.to_max_z) else axis_map.get(loc_con.map_to_z_from, 'Z')
                        inv_x = _is_inverted(loc_con.to_min_x, loc_con.to_max_x)
                        inv_y = _is_inverted(loc_con.to_min_y, loc_con.to_max_y)
                        inv_z = _is_inverted(loc_con.to_min_z, loc_con.to_max_z)
                        off_x = _get_loc_offset(item.loc_offset_x, loc_con.to_min_x, inv_x) if map_x != 'NONE' else 0.0
                        off_y = _get_loc_offset(item.loc_offset_y, loc_con.to_min_y, inv_y) if map_y != 'NONE' else 0.0
                        off_z = _get_loc_offset(item.loc_offset_z, loc_con.to_min_z, inv_z) if map_z != 'NONE' else 0.0
                        fm_x, fx_x = _loc_fine(loc_con.to_min_x, loc_con.to_max_x, off_x, inv_x) if map_x != 'NONE' else (0.0, 0.0)
                        fm_y, fx_y = _loc_fine(loc_con.to_min_y, loc_con.to_max_y, off_y, inv_y) if map_y != 'NONE' else (0.0, 0.0)
                        fm_z, fx_z = _loc_fine(loc_con.to_min_z, loc_con.to_max_z, off_z, inv_z) if map_z != 'NONE' else (0.0, 0.0)
                        entry['location_constraint'] = {
                            'map_x_from': map_x, 'map_y_from': map_y, 'map_z_from': map_z,
                            'invert_x': inv_x, 'invert_y': inv_y, 'invert_z': inv_z,
                            'offset_x': off_x, 'offset_y': off_y, 'offset_z': off_z,
                            'fine_min_x': fm_x, 'fine_max_x': fx_x,
                            'fine_min_y': fm_y, 'fine_max_y': fx_y,
                            'fine_min_z': fm_z, 'fine_max_z': fx_z,
                            'space': 'WORLD' if loc_con.target_space == 'WORLD' else 'LOCAL',
                        }

            data['bone_pairs'].append(entry)

        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.report({'ERROR'}, f"EasyRetarget: Export failed — {e}")
            return {'CANCELLED'}

        log(f"  ExportJSON: exported {len(data['bone_pairs'])} pairs to {self.filepath}")
        self.report({'INFO'}, f"EasyRetarget: Exported {len(data['bone_pairs'])} bone pairs.")
        return {'FINISHED'}


# =====================================================================
# Import — file selection then confirmation dialog
# =====================================================================

# Module-level storage for the parsed import data, passed from the
# file selector to the confirmation dialog.
_import_data = None


class EASYRETARGET_OT_ImportJSONConfirm(Operator):
    """
    Confirmation dialog shown after selecting a JSON file to import.
    Offers Append (add to existing list), Replace (clear then import),
    or Cancel.
    """
    bl_idname = "easy_retarget.import_json_confirm"
    bl_label = "Import Bone Pairs"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    action: EnumProperty(
        items=[
            ('APPEND',  "Append",  "Add imported pairs to the existing list"),
            ('REPLACE', "Replace", "Clear the existing list then import"),
            ('CANCEL',  "Cancel",  "Do not import"),
        ],
        default='APPEND',
        options={'SKIP_SAVE'},
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        global _import_data
        count = len(_import_data['bone_pairs']) if _import_data else 0
        layout.label(text=f"Importing {count} bone pair(s).", icon='INFO')
        layout.separator()
        layout.label(text="How should existing bone pairs be handled?")
        row = layout.row(align=True)
        row.prop_enum(self, "action", 'APPEND')
        row.prop_enum(self, "action", 'REPLACE')
        row.prop_enum(self, "action", 'CANCEL')

    def execute(self, context):
        global _import_data

        if self.action == 'CANCEL' or _import_data is None:
            return {'CANCELLED'}

        props = context.scene.easy_retarget

        if self.action == 'REPLACE':
            props.bone_pairs.clear()
            props.bone_pairs_index = 0

        toggle = props.constraint_toggle
        enabled = (toggle == 'ALL_ON') or (toggle == 'CUSTOM')

        added = 0
        for entry in _import_data.get('bone_pairs', []):
            item = props.bone_pairs.add()
            item.source_bone = entry.get('source_bone', '')
            item.target_bone = entry.get('target_bone', '')
            item.previous_target_bone = item.target_bone

            has_rigs = bool(
                props.target_rig and item.target_bone and
                props.source_rig and item.source_bone
            )

            # ── Rotation ────────────────────────────────────────────────
            # Accept both 'rotation_constraint' (current) and legacy 'constraint' key.
            rot_data = entry.get('rotation_constraint') or entry.get('constraint')
            if rot_data and has_rigs:
                space = rot_data.get('space', 'LOCAL')
                off_x = rot_data.get('offset_x', 0.0)
                off_y = rot_data.get('offset_y', 0.0)
                off_z = rot_data.get('offset_z', 0.0)
                create_or_update_rotation_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from=rot_data.get('map_x_from', 'X'),
                    map_y_from=rot_data.get('map_y_from', 'Y'),
                    map_z_from=rot_data.get('map_z_from', 'Z'),
                    invert_x=rot_data.get('invert_x', False),
                    invert_y=rot_data.get('invert_y', False),
                    invert_z=rot_data.get('invert_z', False),
                    offset_x=off_x, offset_y=off_y, offset_z=off_z,
                    fine_min_x=rot_data.get('fine_min_x', 0.0),
                    fine_max_x=rot_data.get('fine_max_x', 0.0),
                    fine_min_y=rot_data.get('fine_min_y', 0.0),
                    fine_max_y=rot_data.get('fine_max_y', 0.0),
                    fine_min_z=rot_data.get('fine_min_z', 0.0),
                    fine_max_z=rot_data.get('fine_max_z', 0.0),
                    target_space=space, owner_space=space,
                    enabled=enabled,
                )
                # Store offsets on item for fine-tune recovery.
                item.rot_offset_x = off_x
                item.rot_offset_y = off_y
                item.rot_offset_z = off_z

            # ── Location ─────────────────────────────────────────────────
            loc_data = entry.get('location_constraint')
            if loc_data and has_rigs:
                space = loc_data.get('space', 'LOCAL')
                off_x = loc_data.get('offset_x', 0.0)
                off_y = loc_data.get('offset_y', 0.0)
                off_z = loc_data.get('offset_z', 0.0)
                create_or_update_location_constraint(
                    props.target_rig, item.target_bone,
                    props.source_rig, item.source_bone,
                    map_x_from=loc_data.get('map_x_from', 'X'),
                    map_y_from=loc_data.get('map_y_from', 'Y'),
                    map_z_from=loc_data.get('map_z_from', 'Z'),
                    invert_x=loc_data.get('invert_x', False),
                    invert_y=loc_data.get('invert_y', False),
                    invert_z=loc_data.get('invert_z', False),
                    offset_x=off_x, offset_y=off_y, offset_z=off_z,
                    fine_min_x=loc_data.get('fine_min_x', 0.0),
                    fine_max_x=loc_data.get('fine_max_x', 0.0),
                    fine_min_y=loc_data.get('fine_min_y', 0.0),
                    fine_max_y=loc_data.get('fine_max_y', 0.0),
                    fine_min_z=loc_data.get('fine_min_z', 0.0),
                    fine_max_z=loc_data.get('fine_max_z', 0.0),
                    target_space=space, owner_space=space,
                    enabled=enabled,
                )
                # Store offsets on item for fine-tune recovery.
                item.loc_offset_x = off_x
                item.loc_offset_y = off_y
                item.loc_offset_z = off_z

            # Enforce stack order after both constraints are created.
            if has_rigs:
                pbone = get_bone(props.target_rig, item.target_bone)
                if pbone:
                    ensure_constraint_order(pbone)

            added += 1

        props.bone_pairs_index = max(0, len(props.bone_pairs) - 1)
        _import_data = None

        log(f"  ImportJSONConfirm: {self.action} — added {added} pairs")
        self.report({'INFO'}, f"EasyRetarget: Imported {added} bone pairs.")
        return {'FINISHED'}


class EASYRETARGET_OT_ImportJSON(Operator, ImportHelper):
    """Import bone pairs and constraint settings from a JSON file."""
    bl_idname = "easy_retarget.import_json"
    bl_label = "Import Bone Pairs"
    bl_options = {'REGISTER'}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    filepath: StringProperty(subtype='FILE_PATH', default="")

    def execute(self, context):
        global _import_data

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                _import_data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"EasyRetarget: Import failed — {e}")
            return {'CANCELLED'}

        if 'bone_pairs' not in _import_data:
            self.report({'ERROR'}, "EasyRetarget: Invalid file — no 'bone_pairs' key found.")
            _import_data = None
            return {'CANCELLED'}

        log(f"  ImportJSON: loaded {len(_import_data['bone_pairs'])} pairs from {self.filepath}")

        bpy.ops.easy_retarget.import_json_confirm('INVOKE_DEFAULT')
        return {'FINISHED'}
