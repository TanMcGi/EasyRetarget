# =====================================================================
# EasyRetarget - ui.py
# Panel and UIList definitions.
# =====================================================================

import bpy
from bpy.types import Panel, UIList

from .constraint_utils import find_rotation_constraint, find_location_constraint
from .utils import get_bone


class EASYRETARGET_UL_BonePairs(UIList):
    """Draws each bone pair entry in the list."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            props = context.scene.easy_retarget

            # ── Status icon / button (fixed-width first column) ───────
            # NONE      → dot     (no match attempted)
            # CONFIRMED → check   (high confidence or manually verified)
            # WARNING   → button  (low confidence — click to confirm)
            # ERROR     → X       (no match found)
            status = item.match_status

            # A manual pair with both bones set always shows as confirmed.
            if item.is_manual and item.source_bone and item.target_bone:
                status = 'CONFIRMED'

            # Split gives the status icon a truly fixed width, preventing it
            # from compressing the source bone field that follows.
            split = layout.split(factor=0.08, align=True)
            status_col = split.column(align=True)
            row = split.row(align=True)

            if status == 'CONFIRMED':
                status_col.label(text="", icon='CHECKMARK')
            elif status == 'WARNING':
                warn_op = status_col.operator(
                    "easy_retarget.confirm_match_warning",
                    text="",
                    icon='ERROR',
                    emboss=True,
                )
                warn_op.pair_index = index
            elif status == 'ERROR':
                status_col.label(text="", icon='CANCEL')
            else:
                # NONE — neutral dot.
                status_col.label(text="", icon='DECORATE')

            # Source bone field — red if source rig not set or bone doesn't exist.
            source_valid = bool(
                props.source_rig and
                item.source_bone and
                props.source_rig.data.bones.get(item.source_bone)
            )
            src_col = row.column(align=True)
            src_col.alert = bool(item.source_bone and not source_valid)
            src_col.prop(item, "source_bone", text="", icon='BONE_DATA')

            row.label(text="", icon='FORWARD')

            # Target bone field — red if target rig not set or bone doesn't exist.
            target_valid = bool(
                props.target_rig and
                item.target_bone and
                props.target_rig.data.bones.get(item.target_bone)
            )
            tgt_col = row.column(align=True)
            tgt_col.alert = bool(item.target_bone and not target_valid)
            tgt_col.prop(item, "target_bone", text="", icon='BONE_DATA')

            both_populated = bool(item.source_bone and item.target_bone)

            # Constraint button — CONSTRAINT_BONE if either constraint exists, ADD otherwise.
            has_constraint = False
            if both_populated and props.target_rig:
                pbone = get_bone(props.target_rig, item.target_bone)
                has_constraint = bool(
                    pbone and (find_rotation_constraint(pbone) or find_location_constraint(pbone))
                )

            con_icon = 'CONSTRAINT_BONE' if has_constraint else 'ADD'

            sub = row.column()
            sub.enabled = both_populated
            con_op = sub.operator(
                "easy_retarget.edit_constraint",
                text="",
                icon=con_icon,
            )
            con_op.pair_index = index

            # Remove constraint button — only visible when column is shown.
            if props.show_remove_constraint_column:
                sub = row.column()
                sub.enabled = has_constraint
                rm_op = sub.operator(
                    "easy_retarget.remove_constraint",
                    text="",
                    icon='X',
                )
                rm_op.pair_index = index

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
            box.operator("easy_retarget.auto_populate",          text="Auto Populate",          icon='FILE_REFRESH')

            # Clear Warnings — greyed out when no warnings exist.
            has_warnings = any(
                item.match_status == 'WARNING' for item in props.bone_pairs
            )
            clear_row = box.row()
            clear_row.enabled = has_warnings
            clear_row.operator(
                "easy_retarget.clear_all_warnings",
                text="Clear Warnings",
                icon='CHECKMARK',
            )

            box.operator("easy_retarget.create_constraints",     text="Create Constraints",     icon='CONSTRAINT_BONE')
            box.operator("easy_retarget.remove_all_constraints", text="Remove All Constraints", icon='X')

            box.template_list(
                "EASYRETARGET_UL_BonePairs",
                "",
                props,
                "bone_pairs",
                props,
                "bone_pairs_index",
                rows=4,
            )

            # ── Bottom button row ─────────────────────────────────────
            row = box.row(align=True)
            row.operator("easy_retarget.add_bone_pair",    text="", icon='ADD')
            row.operator("easy_retarget.remove_bone_pair", text="", icon='REMOVE')
            row.separator()
            row.operator("easy_retarget.move_bone_pair",   text="", icon='TRIA_UP').direction   = 'UP'
            row.operator("easy_retarget.move_bone_pair",   text="", icon='TRIA_DOWN').direction = 'DOWN'
            row.separator()
            row.operator("easy_retarget.copy_constraint_settings",  text="", icon='COPYDOWN')
            row.operator("easy_retarget.paste_constraint_settings", text="", icon='PASTEDOWN')
            row.separator()
            # Toggle remove constraint column visibility.
            remove_col_icon = 'PANEL_CLOSE' if props.show_remove_constraint_column else 'X'
            row.prop(props, "show_remove_constraint_column", text="", icon=remove_col_icon, toggle=True)

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

            # ── Constraint Toggle ────────────────────────────────────
            col.label(text="Constraints")
            row = col.row(align=True)
            row.prop_enum(props, "constraint_toggle", 'ALL_OFF')
            row.prop_enum(props, "constraint_toggle", 'ALL_ON')
            row.prop_enum(props, "constraint_toggle", 'CUSTOM')
            row = col.row(align=True)
            row.prop_enum(props, "constraint_toggle", 'EASYRETARGET_ONLY')

            col.separator()
            col.prop(props, "bake_keyed_frames_only")

            sub = col.column()
            sub.enabled = not props.bake_keyed_frames_only
            sub.prop(props, "keying_interval")

            col.separator()
            col.label(text="Bone Pairs Data")
            row = col.row(align=True)
            row.operator("easy_retarget.export_json", text="Export JSON", icon='EXPORT')
            row.operator("easy_retarget.import_json", text="Import JSON", icon='IMPORT')

        layout.separator()

        # ── Bake Button ───────────────────────────────────────────────
        layout.operator("easy_retarget.bake", text="Bake", icon='RENDER_ANIMATION')
