# =====================================================================
# EasyRetarget - operators_list.py
# Bone pair list management operators: Add, Remove, Move, AutoPopulate.
# =====================================================================

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty

from . import handlers
from .utils import force_depsgraph_update


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
        item.offset_location = (0.0, 0.0, 0.0)
        item.offset_rotation = (0.0, 0.0, 0.0, 0.0)
        item.offset_scale = (1.0, 1.0, 1.0)
        props.bone_pairs_index = len(props.bone_pairs) - 1
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class EASYRETARGET_OT_RemoveBonePair(Operator):
    """Remove the currently selected bone pair entry."""
    bl_idname = "easy_retarget.remove_bone_pair"
    bl_label = "Remove Bone Pair"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.easy_retarget
        pairs = props.bone_pairs
        index = props.bone_pairs_index

        if pairs and 0 <= index < len(pairs):
            if props.target_rig:
                cache_key = (props.target_rig.name, pairs[index].target_bone)
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
            ('UP', "Up", "Move entry up"),
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


class EASYRETARGET_OT_AutoPopulate(Operator):
    """Clear the bone pairs list and rebuild it by matching bone names between rigs."""
    bl_idname = "easy_retarget.auto_populate"
    bl_label = "Auto Populate"
    bl_options = {'REGISTER', 'UNDO'}

    only_populate_matches: BoolProperty(
        name="Only Populate Matches",
        description="Only add entries where a matching bone name is found on the target rig",
        default=True,
    )

    def invoke(self, context, event):
        props = context.scene.easy_retarget

        if not props.source_rig:
            self.report({'WARNING'}, "EasyRetarget: No Source Rig selected.")
            return {'CANCELLED'}

        if not props.target_rig:
            self.report({'WARNING'}, "EasyRetarget: No Target Rig selected.")
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        warn_box = layout.box()
        warn_box.alert = True
        warn_col = warn_box.column(align=True)
        warn_col.scale_y = 1.4
        warn_col.label(text="This will clear and rebuild the bone pairs list.", icon='ERROR')
        layout.separator()
        layout.prop(self, "only_populate_matches")

    def execute(self, context):
        props = context.scene.easy_retarget
        source_rig = props.source_rig
        target_rig = props.target_rig

        target_bone_names = {b.name for b in target_rig.data.bones}

        props.bone_pairs.clear()
        props.bone_pairs_index = 0

        for bone in source_rig.data.bones:
            match_found = bone.name in target_bone_names

            if self.only_populate_matches and not match_found:
                continue

            item = props.bone_pairs.add()
            item.source_bone = bone.name
            item.target_bone = bone.name if match_found else ""
            item.offset_location = (0.0, 0.0, 0.0)
            item.offset_rotation = (0.0, 0.0, 0.0, 0.0)
            item.offset_scale = (1.0, 1.0, 1.0)

        props.bone_pairs_index = 0

        if context.area:
            context.area.tag_redraw()

        self.report({'INFO'}, f"EasyRetarget: Auto Populate complete. {len(props.bone_pairs)} entries added.")
        return {'FINISHED'}
