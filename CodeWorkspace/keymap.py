# =====================================================================
# EasyRetarget - keymap.py
# Addon keymap registration and unregistration.
# Keymaps are registered under the 'Pose' context so they only fire
# while the user is in Pose Mode.
# =====================================================================

import bpy


# Module-level list of (KeyMap, KeyMapItem) tuples registered by this
# addon, used for clean removal on unregister.
addon_keymaps = []


def register_keymaps():
    """Register all EasyRetarget keymaps."""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    km = kc.keymaps.new(name='Pose', space_type='EMPTY')

    # Add Bone Pair from Selection
    kmi = km.keymap_items.new(
        'easy_retarget.add_bone_pair_from_selection',
        type='P',
        value='PRESS',
        shift=True,
        ctrl=True,
    )
    addon_keymaps.append((km, kmi))

    # Pie Menu
    kmi = km.keymap_items.new(
        'wm.call_menu_pie',
        type='E',
        value='PRESS',
        shift=True,
        ctrl=True,
    )
    kmi.properties.name = 'EASYRETARGET_MT_EasyRetargetPie'
    addon_keymaps.append((km, kmi))

    # Adjust Inversions popup (direct)
    kmi = km.keymap_items.new(
        'easy_retarget.adjust_inversions',
        type='I',
        value='PRESS',
        shift=True,
        ctrl=True,
    )
    addon_keymaps.append((km, kmi))

    # Open Mapping Popup for Active Bone
    kmi = km.keymap_items.new(
        'easy_retarget.open_mapping_for_active_bone',
        type='M',
        value='PRESS',
        shift=True,
        alt=True,
    )
    addon_keymaps.append((km, kmi))


def unregister_keymaps():
    """Unregister all EasyRetarget keymaps."""
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
