# =====================================================================
# EasyRetarget - __init__.py
# Add-on entry point: bl_info, registration, and unregistration.
#
# Creator: Lemur-Duck Studios
# Version: 0.4.2
# =====================================================================

bl_info = {
    "name": "EasyRetarget",
    "author": "Lemur-Duck Studios",
    "version": (0, 4, 2),
    "blender": (5, 0, 0),
    "location": "View3D > N-Panel > EasyRetarget",
    "description": "Simple UI for setting up character rig animation retargeting.",
    "category": "Animation",
}

import bpy
from bpy.props import PointerProperty

from .debug import EASYRETARGET_AddonPreferences, EASYRETARGET_OT_ResetAddonState
from .properties import (
    EASYRETARGET_ConstraintState,
    EASYRETARGET_OtherConstraintState,
    EASYRETARGET_BonePairItem,
    EASYRETARGET_SceneProperties,
)
from .ui import EASYRETARGET_UL_BonePairs, EASYRETARGET_PT_MainPanel
from .operators_list import (
    EASYRETARGET_OT_AddBonePair,
    EASYRETARGET_OT_RemoveBonePair,
    EASYRETARGET_OT_MoveBonePair,
    EASYRETARGET_OT_AutoPopulate,
    EASYRETARGET_OT_ConfirmMatchWarning,
    EASYRETARGET_OT_ClearAllWarnings,
    EASYRETARGET_OT_AddBonePairFromSelection,
)
from .operators_constraint import (
    EASYRETARGET_OT_RemoveConstraint,
    EASYRETARGET_OT_EditConstraint,
    EASYRETARGET_OT_CreateConstraints,
    EASYRETARGET_OT_RemoveAllConstraints,
    EASYRETARGET_OT_CopyConstraintSettings,
    EASYRETARGET_OT_PasteConstraintSettings,
    EASYRETARGET_OT_ConfirmTargetBoneChange,
)
from .op_bake import EASYRETARGET_OT_Bake
from .operators_io import (
    EASYRETARGET_OT_ExportJSON,
    EASYRETARGET_OT_ImportJSON,
    EASYRETARGET_OT_ImportJSONConfirm,
)
from .operators_pose import (
    EASYRETARGET_OT_RetargetSpace,
    EASYRETARGET_OT_AdjustInversions,
    EASYRETARGET_OT_OpenMappingForActiveBone,
    EASYRETARGET_MT_EasyRetargetPie,
)
from . import handlers, keymap


classes = (
    EASYRETARGET_AddonPreferences,
    EASYRETARGET_OT_ResetAddonState,
    EASYRETARGET_ConstraintState,
    EASYRETARGET_OtherConstraintState,
    EASYRETARGET_BonePairItem,
    EASYRETARGET_SceneProperties,
    EASYRETARGET_UL_BonePairs,
    EASYRETARGET_OT_RemoveConstraint,
    EASYRETARGET_OT_EditConstraint,
    EASYRETARGET_OT_CreateConstraints,
    EASYRETARGET_OT_RemoveAllConstraints,
    EASYRETARGET_OT_CopyConstraintSettings,
    EASYRETARGET_OT_PasteConstraintSettings,
    EASYRETARGET_OT_ConfirmTargetBoneChange,
    EASYRETARGET_OT_AddBonePair,
    EASYRETARGET_OT_RemoveBonePair,
    EASYRETARGET_OT_MoveBonePair,
    EASYRETARGET_OT_AutoPopulate,
    EASYRETARGET_OT_ConfirmMatchWarning,
    EASYRETARGET_OT_ClearAllWarnings,
    EASYRETARGET_OT_AddBonePairFromSelection,
    EASYRETARGET_OT_Bake,
    EASYRETARGET_OT_ExportJSON,
    EASYRETARGET_OT_ImportJSON,
    EASYRETARGET_OT_ImportJSONConfirm,
    EASYRETARGET_OT_RetargetSpace,
    EASYRETARGET_OT_AdjustInversions,
    EASYRETARGET_OT_OpenMappingForActiveBone,
    EASYRETARGET_MT_EasyRetargetPie,
    EASYRETARGET_PT_MainPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.easy_retarget = PointerProperty(type=EASYRETARGET_SceneProperties)
    handlers.register_handlers()
    keymap.register_keymaps()
    # Run migration and toggle restoration for any file already open when
    # the addon is enabled, since load_post won't fire in that case.
    # Guard with hasattr: during installation bpy.data is a _RestrictData
    # object that does not expose 'scenes', so the loop must be skipped.
    if hasattr(bpy.data, 'scenes'):
        for scene in bpy.data.scenes:
            try:
                handlers._migrate_constraint_names(scene.easy_retarget)
                handlers._apply_toggle_state(scene.easy_retarget)
            except Exception:
                pass


def unregister():
    keymap.unregister_keymaps()
    handlers.unregister_handlers()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.easy_retarget


if __name__ == "__main__":
    register()
