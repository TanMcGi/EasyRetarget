# =====================================================================
# EasyRetarget - ui.py
# Panel and UIList definitions.
# =====================================================================

import bpy
from bpy.types import Panel, UIList

from .utils import has_non_default_offsets


class EASYRETARGET_UL_BonePairs(UIList):
    """Draws each bone pair entry in the list."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            row.prop(item, "source_bone", text="", icon='BONE_DATA')
            row.label(text="", icon='FORWARD')
            row.prop(item, "target_bone", text="", icon='BONE_DATA')

            has_offsets = has_non_default_offsets(item)
            both_populated = bool(item.source_bone and item.target_bone)
            offset_icon = 'DECORATE_KEYFRAME' if has_offsets else 'DECORATE_ANIMATE'

            sub = row.column()
            sub.enabled = both_populated
            offset_op = sub.operator(
                "easy_retarget.edit_offsets",
                text="",
                icon=offset_icon,
            )
            offset_op.pair_index = index

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='BONE_DATA')

    def draw_filter(self, context, layout):
        row = layout.row()
        row.prop(self, "filter_name", text="", icon='VIEWZOOM')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        filtered = []
        ordered = []

        if self.filter_name:
            filtered = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, items,
                "source_bone", reverse=self.use_filter_invert
            )

        return filtered, ordered


class EASYRETARGET_PT_MainPanel(Panel):
    """Main EasyRetarget panel in the N-panel."""
    bl_label = "EasyRetarget"
    bl_idname = "EASYRETARGET_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EasyRetarget"

    def draw(self, context):
        layout = self.layout
        props = context.scene.easy_retarget

        # ── Rig Pickers ──────────────────────────────────────────────
        col = layout.column(align=True)
        col.label(text="Rigs", icon='ARMATURE_DATA')
        col.prop(props, "source_rig", text="Source")
        col.prop(props, "target_rig", text="Target")

        layout.separator()

        # ── Bone Pairs ───────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.prop(
            props, "bone_pairs_expanded",
            icon='TRIA_DOWN' if props.bone_pairs_expanded else 'TRIA_RIGHT',
            icon_only=True,
            emboss=False,
        )
        row.label(text="Bone Pairs", icon='BONE_DATA')

        if props.bone_pairs_expanded:
            box.operator("easy_retarget.auto_populate", text="Auto Populate", icon='FILE_REFRESH')
            box.operator("easy_retarget.match_all_offsets", text="Match All", icon='SNAP_ON')

            box.template_list(
                "EASYRETARGET_UL_BonePairs",
                "",
                props,
                "bone_pairs",
                props,
                "bone_pairs_index",
                rows=4,
            )

            row = box.row(align=True)
            row.operator("easy_retarget.add_bone_pair", text="", icon='ADD')
            row.operator("easy_retarget.remove_bone_pair", text="", icon='REMOVE')
            row.separator()
            row.operator("easy_retarget.move_bone_pair", text="", icon='TRIA_UP').direction = 'UP'
            row.operator("easy_retarget.move_bone_pair", text="", icon='TRIA_DOWN').direction = 'DOWN'

        layout.separator()

        # ── Settings ─────────────────────────────────────────────────
        box = layout.box()
        row = box.row()
        row.prop(
            props, "settings_expanded",
            icon='TRIA_DOWN' if props.settings_expanded else 'TRIA_RIGHT',
            icon_only=True,
            emboss=False,
        )
        row.label(text="Settings", icon='SETTINGS')

        if props.settings_expanded:
            col = box.column(align=True)
            col.prop(props, "live_offset")
            col.separator()
            col.prop(props, "bake_keyed_frames_only")

            sub = col.column()
            sub.enabled = not props.bake_keyed_frames_only
            sub.prop(props, "keying_interval")

        layout.separator()

        # ── Bake Button ───────────────────────────────────────────────
        layout.operator("easy_retarget.bake", text="Bake", icon='RENDER_ANIMATION')
