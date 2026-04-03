# =====================================================================
# EasyRetarget - properties.py
# PropertyGroup definitions for bone pairs and scene-level settings.
# =====================================================================

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


# =====================================================================
# Search Callbacks
# =====================================================================

def _source_bone_search(self, context, edit_text):
    props = context.scene.easy_retarget
    if props.source_rig and props.source_rig.type == 'ARMATURE':
        for bone in props.source_rig.data.bones:
            if edit_text.lower() in bone.name.lower():
                yield bone.name


def _target_bone_search(self, context, edit_text):
    props = context.scene.easy_retarget
    if props.target_rig and props.target_rig.type == 'ARMATURE':
        for bone in props.target_rig.data.bones:
            if edit_text.lower() in bone.name.lower():
                yield bone.name


# =====================================================================
# Update Callbacks
# =====================================================================

def _on_live_offset_update(self, context):
    from . import handlers
    from .utils import force_depsgraph_update
    if self.live_offset:
        # Snapshot current pose before overwriting with offsets
        handlers.snapshot_pose(self.target_rig, self.pose_snapshot)
        # Disable all enabled constraints on paired target bones and
        # record them so they can be restored when Live Offset is turned off.
        handlers.disable_paired_constraints(
            self.target_rig, self.bone_pairs, self.disabled_constraints
        )
        handlers.register_handlers()
    else:
        handlers.unregister_handlers()
        # Re-enable constraints that were disabled on toggle-on
        handlers.restore_disabled_constraints(
            self.target_rig, self.disabled_constraints
        )
        self.disabled_constraints.clear()
        # Restore the snapshotted pose
        handlers.restore_pose_snapshot(self.target_rig, self.pose_snapshot)
        self.pose_snapshot.clear()
    force_depsgraph_update(context=context)


def _on_rig_update(self, context):
    from . import handlers
    from .utils import force_depsgraph_update
    if self.live_offset:
        # Re-snapshot and re-disable constraints for the new rig
        self.pose_snapshot.clear()
        self.disabled_constraints.clear()
        handlers.snapshot_pose(self.target_rig, self.pose_snapshot)
        handlers.disable_paired_constraints(
            self.target_rig, self.bone_pairs, self.disabled_constraints
        )
    force_depsgraph_update(context=context)


def _on_offset_update(self, context):
    from .utils import force_depsgraph_update
    force_depsgraph_update(context=context)


# =====================================================================
# Property Groups
# =====================================================================

class EASYRETARGET_BonePoseSnapshot(PropertyGroup):
    """Stores the pose channel values for a single bone."""
    bone_name: StringProperty(options={'HIDDEN'})
    location: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0), options={'HIDDEN'})
    rotation_quaternion: FloatVectorProperty(size=4, default=(1.0, 0.0, 0.0, 0.0), options={'HIDDEN'})
    rotation_euler: FloatVectorProperty(size=3, default=(0.0, 0.0, 0.0), options={'HIDDEN'})
    rotation_axis_angle: FloatVectorProperty(size=4, default=(0.0, 0.0, 1.0, 0.0), options={'HIDDEN'})
    scale: FloatVectorProperty(size=3, default=(1.0, 1.0, 1.0), options={'HIDDEN'})
    rotation_mode: StringProperty(default='QUATERNION', options={'HIDDEN'})


class EASYRETARGET_DisabledConstraint(PropertyGroup):
    """Records a single constraint that was disabled when Live Offset was enabled."""
    bone_name: StringProperty(options={'HIDDEN'})
    constraint_name: StringProperty(options={'HIDDEN'})


class EASYRETARGET_BonePairItem(PropertyGroup):
    """Represents a single source-to-target bone mapping entry."""

    source_bone: StringProperty(
        name="Source Bone",
        description="Bone on the source rig",
        default="",
        search=_source_bone_search,
        search_options={'SORT'},
    )

    target_bone: StringProperty(
        name="Target Bone",
        description="Bone on the target rig",
        default="",
        search=_target_bone_search,
        search_options={'SORT'},
    )

    offset_location: FloatVectorProperty(
        name="Location Offset",
        description="Per-axis location offset applied to the target bone (additive)",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype='TRANSLATION',
        update=_on_offset_update,
    )

    offset_rotation: FloatVectorProperty(
        name="Rotation Offset",
        description="Rotation offset stored as (W, X, Y, Z); W unused for Euler modes (additive)",
        size=4,
        default=(0.0, 0.0, 0.0, 0.0),
        update=_on_offset_update,
    )

    offset_scale: FloatVectorProperty(
        name="Scale Offset",
        description="Per-axis scale offset applied to the target bone (multiplicative)",
        size=3,
        default=(1.0, 1.0, 1.0),
        update=_on_offset_update,
    )


class EASYRETARGET_SceneProperties(PropertyGroup):
    """Top-level scene properties for EasyRetarget."""

    source_rig: PointerProperty(
        name="Source Rig",
        description="The armature whose animation will be retargeted",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        update=_on_rig_update,
    )

    target_rig: PointerProperty(
        name="Target Rig",
        description="The armature that will receive the retargeted animation",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        update=_on_rig_update,
    )

    bone_pairs: CollectionProperty(
        name="Bone Pairs",
        type=EASYRETARGET_BonePairItem,
    )

    bone_pairs_index: IntProperty(
        name="Active Bone Pair Index",
        default=0,
    )

    # Full armature pose snapshot taken when Live Offset is enabled.
    # Restored when Live Offset is disabled.
    pose_snapshot: CollectionProperty(
        name="Pose Snapshot",
        type=EASYRETARGET_BonePoseSnapshot,
        options={'HIDDEN'},
    )

    # Records constraints disabled on paired target bones when Live Offset
    # is enabled, so they can be restored when Live Offset is turned off.
    # Persists in scene data so it survives Blender restarts.
    disabled_constraints: CollectionProperty(
        name="Disabled Constraints",
        type=EASYRETARGET_DisabledConstraint,
        options={'HIDDEN'},
    )

    bone_pairs_expanded: BoolProperty(
        name="Bone Pairs",
        default=True,
    )

    settings_expanded: BoolProperty(
        name="Settings",
        default=False,
    )

    bake_keyed_frames_only: BoolProperty(
        name="Bake Keyed Frames Only",
        description="Only bake frames that already have keyframes on the source rig",
        default=True,
    )

    keying_interval: IntProperty(
        name="Keying Interval",
        description="Interval (in frames) between baked keyframes",
        default=1,
        min=1,
    )

    live_offset: BoolProperty(
        name="Live Offset",
        description="Apply bone offsets live in the viewport via a depsgraph handler",
        default=False,
        update=_on_live_offset_update,
    )
