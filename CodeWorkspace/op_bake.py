# =====================================================================
# EasyRetarget - op_bake.py
# Bake operator — placeholder for animation bake logic.
# =====================================================================

from bpy.types import Operator


class EASYRETARGET_OT_Bake(Operator):
    """Bake the retargeted animation (placeholder)."""
    bl_idname = "easy_retarget.bake"
    bl_label = "Bake"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self.report({'INFO'}, "EasyRetarget: Bake called — logic not yet implemented.")
        return {'FINISHED'}
