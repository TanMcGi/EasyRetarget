# =====================================================================
# EasyRetarget - utils.py
# Shared helper functions.
# =====================================================================


def get_bone(rig, bone_name):
    """Return a pose bone by name from an armature object, or None."""
    if rig and rig.type == 'ARMATURE' and bone_name:
        return rig.pose.bones.get(bone_name)
    return None


def force_depsgraph_update(context=None):
    """Force an immediate depsgraph update."""
    import bpy
    ctx = context if context is not None else bpy.context
    if ctx and ctx.scene:
        ctx.scene.frame_set(ctx.scene.frame_current)
