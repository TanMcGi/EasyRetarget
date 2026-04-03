# =====================================================================
# EasyRetarget - __init__.py
# Add-on entry point: bl_info, registration, and unregistration.
#
# Creator: Lemur-Duck Studios
# Version: 0.1.25
# =====================================================================

bl_info = {
    "name": "EasyRetarget",
    "author": "Lemur-Duck Studios",
    "version": (0, 1, 25),
    "blender": (5, 0, 0),
    "location": "View3D > N-Panel > EasyRetarget",
    "description": "Simple UI for setting up character rig animation retargeting.",
    "category": "Animation",
}

import bpy
from bpy.props import PointerProperty

from .debug import EASYRETARGET_AddonPreferences
from .properties import (
    EASYRETARGET_BonePoseSnapshot,
    EASYRETARGET_DisabledConstraint,
    EASYRETARGET_BonePairItem,
    EASYRETARGET_SceneProperties,
)
from .ui import EASYRETARGET_UL_BonePairs, EASYRETARGET_PT_MainPanel
from .operators_list import (
    EASYRETARGET_OT_AddBonePair,
    EASYRETARGET_OT_RemoveBonePair,
    EASYRETARGET_OT_MoveBonePair,
    EASYRETARGET_OT_AutoPopulate,
)
from .operators_offset import (
    EASYRETARGET_OT_EditOffsets,
    EASYRETARGET_OT_MatchSourceOffsets,
    EASYRETARGET_OT_MatchAllOffsets,
    EASYRETARGET_OT_MatchRotationMode,
    EASYRETARGET_OT_ResetOffsets,
)
from .op_bake import EASYRETARGET_OT_Bake
from . import handlers


classes = (
    EASYRETARGET_AddonPreferences,
    EASYRETARGET_BonePoseSnapshot,
    EASYRETARGET_DisabledConstraint,
    EASYRETARGET_BonePairItem,
    EASYRETARGET_SceneProperties,
    EASYRETARGET_UL_BonePairs,
    EASYRETARGET_OT_EditOffsets,
    EASYRETARGET_OT_MatchSourceOffsets,
    EASYRETARGET_OT_MatchAllOffsets,
    EASYRETARGET_OT_MatchRotationMode,
    EASYRETARGET_OT_ResetOffsets,
    EASYRETARGET_OT_AddBonePair,
    EASYRETARGET_OT_RemoveBonePair,
    EASYRETARGET_OT_MoveBonePair,
    EASYRETARGET_OT_AutoPopulate,
    EASYRETARGET_OT_Bake,
    EASYRETARGET_PT_MainPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.easy_retarget = PointerProperty(type=EASYRETARGET_SceneProperties)
    # Handlers registered on demand when Live Offset is enabled.
    # Live Offset defaults to off so no handler registration at load.


def unregister():
    handlers.unregister_handlers()
    for scene in bpy.data.scenes:
        try:
            props = scene.easy_retarget
            if props.live_offset and props.target_rig:
                handlers.restore_user_intent(props.target_rig, props.bone_pairs)
        except Exception:
            pass
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.easy_retarget


if __name__ == "__main__":
    register()
