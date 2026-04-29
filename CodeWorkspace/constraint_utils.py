# =====================================================================
# EasyRetarget - constraint_utils.py
# Helpers for creating, finding, updating, and removing EasyRetarget
# Transform constraints on paired target bones.
# =====================================================================

ROTATION_CONSTRAINT_NAME = "EasyRetarget_Rotation"
LOCATION_CONSTRAINT_NAME = "EasyRetarget_Location"

AXIS_ENUM = {
    'X':    'X',
    'Y':    'Y',
    'Z':    'Z',
    'NONE': 'X',
}

# Location map-from half-range in Blender units. With use_motion_extrapolate=True
# the mapping slope is always 1:1 regardless of the chosen range value.
_LOCATION_HALF_RANGE = 100.0


# =====================================================================
# Find / Remove
# =====================================================================

def find_rotation_constraint(pbone):
    """Return the EasyRetarget_Rotation Transform constraint on pbone, or None."""
    return pbone.constraints.get(ROTATION_CONSTRAINT_NAME)


def find_location_constraint(pbone):
    """Return the EasyRetarget_Location Transform constraint on pbone, or None."""
    return pbone.constraints.get(LOCATION_CONSTRAINT_NAME)


def remove_rotation_constraint(pbone):
    """Remove the EasyRetarget_Rotation constraint from pbone if present."""
    con = find_rotation_constraint(pbone)
    if con:
        pbone.constraints.remove(con)


def remove_location_constraint(pbone):
    """Remove the EasyRetarget_Location constraint from pbone if present."""
    con = find_location_constraint(pbone)
    if con:
        pbone.constraints.remove(con)


# =====================================================================
# Constraint Stack Ordering
# =====================================================================

def ensure_constraint_order(pbone):
    """
    Ensure EasyRetarget_Location comes before EasyRetarget_Rotation in
    the constraint stack. No-op if either constraint is absent.
    """
    loc_con = find_location_constraint(pbone)
    rot_con = find_rotation_constraint(pbone)
    if loc_con is None or rot_con is None:
        return

    constraints = list(pbone.constraints)
    loc_idx = next((i for i, c in enumerate(constraints) if c.name == LOCATION_CONSTRAINT_NAME), -1)
    rot_idx = next((i for i, c in enumerate(constraints) if c.name == ROTATION_CONSTRAINT_NAME), -1)

    if loc_idx == -1 or rot_idx == -1:
        return

    if loc_idx > rot_idx:
        pbone.constraints.move(loc_idx, rot_idx)


# =====================================================================
# Min/Max Calculation
# =====================================================================

def calculate_map_to_min_max(invert, source_axis, offset=0.0, half_range=180.0,
                             fine_min=0.0, fine_max=0.0):
    """
    Calculate the Map To Min and Max values for one owner axis.

    For rotation: half_range=180.0, offset and fine values are in degrees.
    For location: half_range=100.0, offset and fine values are in Blender units.

    A 1:1 non-inverted mapping with no offset produces:
      to_min = -half_range, to_max = +half_range
    Inversion swaps the half_range signs. Offset shifts both ends linearly.
    fine_min and fine_max are independent per-end adjustments added on top
    of the centered offset range.
    When source_axis is 'NONE', both values are 0 (all adjustments ignored).

    Returns (to_min, to_max).
    """
    if source_axis == 'NONE':
        return (0.0, 0.0)

    if invert:
        return (half_range + offset + fine_min, -half_range + offset + fine_max)
    else:
        return (-half_range + offset + fine_min, half_range + offset + fine_max)


# =====================================================================
# Create / Update — Rotation
# =====================================================================

def create_or_update_rotation_constraint(
    target_rig,
    target_bone_name,
    source_rig,
    source_bone_name,
    map_x_from,
    map_y_from,
    map_z_from,
    invert_x,
    invert_y,
    invert_z,
    offset_x=0.0,
    offset_y=0.0,
    offset_z=0.0,
    fine_min_x=0.0, fine_max_x=0.0,
    fine_min_y=0.0, fine_max_y=0.0,
    fine_min_z=0.0, fine_max_z=0.0,
    target_space='LOCAL',
    owner_space='LOCAL',
    enabled=True,
):
    """
    Create or update the EasyRetarget_Rotation Transform constraint on the target bone.

    map_x/y/z_from: 'X', 'Y', 'Z', or 'NONE'
    invert_x/y/z: bool
    offset_x/y/z: float, degrees — shifts both range ends equally (center shift).
    fine_min/max_x/y/z: float, degrees — independent per-end adjustments on top of offset.
    target_space / owner_space: 'WORLD' or 'LOCAL'

    map_from and map_to are only assigned when they differ from 'ROTATION' to
    avoid resetting mix_mode_rot (which reverts to 'ADD' on reassignment).
    mix_mode_rot is set to 'REPLACE' for World/World, 'ADD' otherwise.

    Calls ensure_constraint_order after creation/update.

    Returns the constraint.
    """
    import math
    from .debug import log

    pbone = target_rig.pose.bones.get(target_bone_name)
    if not pbone:
        log(f"  create_or_update_rotation_constraint: bone not found: {target_bone_name}")
        return None

    con = find_rotation_constraint(pbone)
    if con is None:
        con = pbone.constraints.new('TRANSFORM')
        con.name = ROTATION_CONSTRAINT_NAME
        log(f"  create_or_update_rotation_constraint: created new on {target_bone_name}")
    else:
        log(f"  create_or_update_rotation_constraint: updating existing on {target_bone_name}")

    # ── Target ────────────────────────────────────────────────────────
    con.target = source_rig
    con.subtarget = source_bone_name
    con.target_space = target_space
    con.owner_space = owner_space
    con.use_motion_extrapolate = True

    # ── Map From ──────────────────────────────────────────────────────
    if con.map_from != 'ROTATION':
        log(f"  setting map_from to ROTATION (was {con.map_from})")
        con.map_from = 'ROTATION'

    con.from_min_x_rot = math.radians(-180.0)
    con.from_max_x_rot = math.radians(180.0)
    con.from_min_y_rot = math.radians(-180.0)
    con.from_max_y_rot = math.radians(180.0)
    con.from_min_z_rot = math.radians(-180.0)
    con.from_max_z_rot = math.radians(180.0)

    # ── Map To ────────────────────────────────────────────────────────
    # Only assign map_to when necessary — reassigning resets mix_mode_rot to 'ADD'.
    if con.map_to != 'ROTATION':
        log(f"  setting map_to to ROTATION (was {con.map_to})")
        con.map_to = 'ROTATION'

    # Set mix_mode_rot after map_to to ensure it takes effect.
    expected_mix = 'REPLACE' if (target_space == 'WORLD' and owner_space == 'WORLD') else 'ADD'
    log(f"  mix_mode_rot before set: {con.mix_mode_rot}, setting to: {expected_mix}")
    con.mix_mode_rot = expected_mix
    log(f"  mix_mode_rot after set:  {con.mix_mode_rot}")

    # ── Axis Mapping ──────────────────────────────────────────────────
    x_min, x_max = calculate_map_to_min_max(invert_x, map_x_from, offset_x, 180.0, fine_min_x, fine_max_x)
    con.map_to_x_from = AXIS_ENUM.get(map_x_from, 'X')
    con.to_min_x_rot = math.radians(x_min)
    con.to_max_x_rot = math.radians(x_max)

    y_min, y_max = calculate_map_to_min_max(invert_y, map_y_from, offset_y, 180.0, fine_min_y, fine_max_y)
    con.map_to_y_from = AXIS_ENUM.get(map_y_from, 'Y')
    con.to_min_y_rot = math.radians(y_min)
    con.to_max_y_rot = math.radians(y_max)

    z_min, z_max = calculate_map_to_min_max(invert_z, map_z_from, offset_z, 180.0, fine_min_z, fine_max_z)
    con.map_to_z_from = AXIS_ENUM.get(map_z_from, 'Z')
    con.to_min_z_rot = math.radians(z_min)
    con.to_max_z_rot = math.radians(z_max)

    log(f"  X: {map_x_from} inv={invert_x} off={offset_x:.2f} fine=[{fine_min_x:.2f},{fine_max_x:.2f}] → [{x_min:.1f}, {x_max:.1f}]")
    log(f"  Y: {map_y_from} inv={invert_y} off={offset_y:.2f} fine=[{fine_min_y:.2f},{fine_max_y:.2f}] → [{y_min:.1f}, {y_max:.1f}]")
    log(f"  Z: {map_z_from} inv={invert_z} off={offset_z:.2f} fine=[{fine_min_z:.2f},{fine_max_z:.2f}] → [{z_min:.1f}, {z_max:.1f}]")

    con.enabled = enabled

    ensure_constraint_order(pbone)

    return con


# =====================================================================
# Create / Update — Location
# =====================================================================

def create_or_update_location_constraint(
    target_rig,
    target_bone_name,
    source_rig,
    source_bone_name,
    map_x_from,
    map_y_from,
    map_z_from,
    invert_x,
    invert_y,
    invert_z,
    offset_x=0.0,
    offset_y=0.0,
    offset_z=0.0,
    fine_min_x=0.0, fine_max_x=0.0,
    fine_min_y=0.0, fine_max_y=0.0,
    fine_min_z=0.0, fine_max_z=0.0,
    target_space='LOCAL',
    owner_space='LOCAL',
    enabled=True,
):
    """
    Create or update the EasyRetarget_Location Transform constraint on the target bone.

    map_x/y/z_from: 'X', 'Y', 'Z', or 'NONE'
    invert_x/y/z: bool
    offset_x/y/z: float, Blender units — shifts both range ends equally (center shift).
    fine_min/max_x/y/z: float, Blender units — independent per-end adjustments on top of offset.
    target_space / owner_space: 'WORLD' or 'LOCAL'

    Uses a fixed ±100 unit from-range with use_motion_extrapolate=True, giving a
    1:1 default mapping for any reasonable bone distance. mix_mode is set to
    'REPLACE' for World/World, 'ADD' otherwise.

    map_to is guarded before assignment to avoid resetting mix_mode (same pattern
    as the rotation constraint).

    Calls ensure_constraint_order after creation/update.

    Returns the constraint.
    """
    from .debug import log

    pbone = target_rig.pose.bones.get(target_bone_name)
    if not pbone:
        log(f"  create_or_update_location_constraint: bone not found: {target_bone_name}")
        return None

    con = find_location_constraint(pbone)
    if con is None:
        con = pbone.constraints.new('TRANSFORM')
        con.name = LOCATION_CONSTRAINT_NAME
        log(f"  create_or_update_location_constraint: created new on {target_bone_name}")
    else:
        log(f"  create_or_update_location_constraint: updating existing on {target_bone_name}")

    # ── Target ────────────────────────────────────────────────────────
    con.target = source_rig
    con.subtarget = source_bone_name
    con.target_space = target_space
    con.owner_space = owner_space
    con.use_motion_extrapolate = True

    # ── Map From ──────────────────────────────────────────────────────
    if con.map_from != 'LOCATION':
        log(f"  setting map_from to LOCATION (was {con.map_from})")
        con.map_from = 'LOCATION'

    con.from_min_x = -_LOCATION_HALF_RANGE
    con.from_max_x =  _LOCATION_HALF_RANGE
    con.from_min_y = -_LOCATION_HALF_RANGE
    con.from_max_y =  _LOCATION_HALF_RANGE
    con.from_min_z = -_LOCATION_HALF_RANGE
    con.from_max_z =  _LOCATION_HALF_RANGE

    # ── Map To ────────────────────────────────────────────────────────
    # Guard map_to assignment to avoid resetting mix_mode.
    if con.map_to != 'LOCATION':
        log(f"  setting map_to to LOCATION (was {con.map_to})")
        con.map_to = 'LOCATION'

    expected_mix = 'REPLACE' if (target_space == 'WORLD' and owner_space == 'WORLD') else 'ADD'
    log(f"  mix_mode before set: {con.mix_mode}, setting to: {expected_mix}")
    con.mix_mode = expected_mix
    log(f"  mix_mode after set:  {con.mix_mode}")

    # ── Axis Mapping ──────────────────────────────────────────────────
    x_min, x_max = calculate_map_to_min_max(invert_x, map_x_from, offset_x, _LOCATION_HALF_RANGE, fine_min_x, fine_max_x)
    con.map_to_x_from = AXIS_ENUM.get(map_x_from, 'X')
    con.to_min_x = x_min
    con.to_max_x = x_max

    y_min, y_max = calculate_map_to_min_max(invert_y, map_y_from, offset_y, _LOCATION_HALF_RANGE, fine_min_y, fine_max_y)
    con.map_to_y_from = AXIS_ENUM.get(map_y_from, 'Y')
    con.to_min_y = y_min
    con.to_max_y = y_max

    z_min, z_max = calculate_map_to_min_max(invert_z, map_z_from, offset_z, _LOCATION_HALF_RANGE, fine_min_z, fine_max_z)
    con.map_to_z_from = AXIS_ENUM.get(map_z_from, 'Z')
    con.to_min_z = z_min
    con.to_max_z = z_max

    log(f"  X: {map_x_from} inv={invert_x} off={offset_x:.4f} fine=[{fine_min_x:.4f},{fine_max_x:.4f}] → [{x_min:.4f}, {x_max:.4f}]")
    log(f"  Y: {map_y_from} inv={invert_y} off={offset_y:.4f} fine=[{fine_min_y:.4f},{fine_max_y:.4f}] → [{y_min:.4f}, {y_max:.4f}]")
    log(f"  Z: {map_z_from} inv={invert_z} off={offset_z:.4f} fine=[{fine_min_z:.4f},{fine_max_z:.4f}] → [{z_min:.4f}, {z_max:.4f}]")

    con.enabled = enabled

    ensure_constraint_order(pbone)

    return con
