# =====================================================================
# EasyRetarget - utils.py
# Shared helper functions.
# =====================================================================

from mathutils import Euler, Quaternion, Vector, Matrix


def get_bone(rig, bone_name):
    """Return a pose bone by name from an armature object, or None."""
    if rig and rig.type == 'ARMATURE' and bone_name:
        return rig.pose.bones.get(bone_name)
    return None


def get_armature_space_rest_rotation(rig, bone_name):
    """
    Return the accumulated rest rotation for a bone in armature space as a
    Quaternion, by multiplying only the rotation components of matrix_local
    up through the full parent chain.

    Using only the rotation component (stripping translation) avoids bone-length
    offsets contaminating the rotation extraction during delta decomposition,
    which would produce incorrect non-zero offsets even for identical bones.
    """
    bone = rig.data.bones.get(bone_name)
    if bone is None:
        return Quaternion()

    quats = []
    current = bone
    while current is not None:
        quats.append(current.matrix_local.to_quaternion().normalized())
        current = current.parent

    result = Quaternion()
    for q in reversed(quats):
        result = result @ q

    return result.normalized()


def get_parent_armature_space_rest_rotation(rig, bone_name):
    """
    Return the accumulated rest rotation of the parent of the given bone
    in armature space. Returns identity quaternion if the bone has no parent.
    """
    bone = rig.data.bones.get(bone_name)
    if bone is None or bone.parent is None:
        return Quaternion()
    return get_armature_space_rest_rotation(rig, bone.parent.name)


def has_non_default_offsets(item):
    """Return True if any offset value on a bone pair item is non-default."""
    for v in item.offset_location:
        if v != 0.0:
            return True
    for v in item.offset_rotation:
        if v != 0.0:
            return True
    for v in item.offset_scale:
        if v != 1.0:
            return True
    return False


def convert_rotation_offset(offset_rotation, from_mode, to_mode):
    """
    Convert a rotation offset stored as (W, X, Y, Z) from one rotation
    mode to another using mathutils. Returns a new 4-tuple (W, X, Y, Z).
    """
    w, x, y, z = offset_rotation

    if from_mode == 'QUATERNION':
        q = Quaternion((w, x, y, z))
    elif from_mode == 'AXIS_ANGLE':
        q = Quaternion((x, y, z), w)
    else:
        e = Euler((x, y, z), from_mode)
        q = e.to_quaternion()

    q.normalize()

    if to_mode == 'QUATERNION':
        return (q.w, q.x, q.y, q.z)
    elif to_mode == 'AXIS_ANGLE':
        axis, angle = q.to_axis_angle()
        return (angle, axis.x, axis.y, axis.z)
    else:
        e = q.to_euler(to_mode)
        return (0.0, e.x, e.y, e.z)


def offset_rotation_as_quat(offset_rotation, rot_mode):
    """Convert stored offset_rotation (W,X,Y,Z) to a Quaternion for the given mode."""
    w, x, y, z = offset_rotation
    if rot_mode == 'QUATERNION':
        q = Quaternion((w, x, y, z))
    elif rot_mode == 'AXIS_ANGLE':
        q = Quaternion((x, y, z), w)
    else:
        q = Euler((x, y, z), rot_mode).to_quaternion()
    q.normalize()
    return q


def get_pose_rotation_as_quat(pbone):
    """Read the current pose bone rotation as a Quaternion regardless of mode."""
    rot_mode = pbone.rotation_mode
    if rot_mode == 'QUATERNION':
        return pbone.rotation_quaternion.copy().normalized()
    elif rot_mode == 'AXIS_ANGLE':
        aa = pbone.rotation_axis_angle
        return Quaternion((aa[1], aa[2], aa[3]), aa[0]).normalized()
    else:
        return pbone.rotation_euler.to_quaternion().normalized()


def write_pose_rotation_from_quat(pbone, q):
    """Write a Quaternion back to the pose bone in its current rotation mode."""
    q = q.normalized()
    rot_mode = pbone.rotation_mode
    if rot_mode == 'QUATERNION':
        pbone.rotation_quaternion = q
    elif rot_mode == 'AXIS_ANGLE':
        axis, angle = q.to_axis_angle()
        pbone.rotation_axis_angle = (angle, axis.x, axis.y, axis.z)
    else:
        pbone.rotation_euler = q.to_euler(rot_mode, pbone.rotation_euler)



def force_depsgraph_update(context=None):
    """Force an immediate depsgraph update to trigger the live offset handler."""
    import bpy
    ctx = context if context is not None else bpy.context
    if ctx and ctx.scene:
        ctx.scene.frame_set(ctx.scene.frame_current)


def get_bone_rest_world_rotation(rig, bone_name):
    """
    Return the rest pose world-space rotation of a bone as a Quaternion.
    Combines the armature object's world rotation with the bone's
    armature-space rest rotation (rotation component only).
    Using world space lets Blender's own transform stack handle parent
    chain accumulation — no manual reconstruction needed.
    """
    bone = rig.data.bones.get(bone_name)
    if bone is None:
        return Quaternion()

    # Armature object world rotation
    arm_world_rot = rig.matrix_world.to_quaternion().normalized()

    # Bone's armature-space rest rotation (rotation only, no translation)
    bone_arm_rot = bone.matrix_local.to_quaternion().normalized()

    # Walk up parent chain accumulating rotations
    current = bone.parent
    while current is not None:
        bone_arm_rot = current.matrix_local.to_quaternion().normalized() @ bone_arm_rot
        current = current.parent

    return (arm_world_rot @ bone_arm_rot).normalized()


def get_parent_bone_rest_world_rotation(rig, bone_name):
    """
    Return the rest pose world-space rotation of the parent of the given bone.
    Returns the armature's world rotation if the bone has no parent.
    """
    bone = rig.data.bones.get(bone_name)
    if bone is None or bone.parent is None:
        return rig.matrix_world.to_quaternion().normalized()
    return get_bone_rest_world_rotation(rig, bone.parent.name)

def get_parent_bone_posed_world_rotation(rig, bone_name):
    """
    Return the current POSE world-space rotation of the parent of the given bone.
    Uses the evaluated pose matrix (target_pbone.parent.matrix) which reflects
    any offsets or animations already applied to the parent bone.
    Returns the armature's world rotation if the bone has no parent.

    This is needed for Match Source on child bones: the parent's pose rotation
    (not rest rotation) is the actual space the child's offset will be applied in.
    """
    pbone = rig.pose.bones.get(bone_name)
    if pbone is None or pbone.parent is None:
        return rig.matrix_world.to_quaternion().normalized()

    arm_world_rot = rig.matrix_world.to_quaternion().normalized()
    parent_pose_rot = pbone.parent.matrix.to_quaternion().normalized()
    return (arm_world_rot @ parent_pose_rot).normalized()
