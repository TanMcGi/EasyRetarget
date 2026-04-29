# EasyRetarget — Full Project Documentation

**Creator:** Lemur-Duck Studios
**Current Version:** 0.2.6
**Target Platform:** Blender 5.0+
**Language:** Python
**Document Purpose:** Comprehensive technical and user-facing reference for ongoing development, intended to onboard a new Claude instance continuing work in a Cowork project.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Development Conventions](#2-development-conventions)
3. [File Structure](#3-file-structure)
4. [Architecture Overview](#4-architecture-overview)
5. [Module Reference](#5-module-reference)
6. [UI Reference](#6-ui-reference)
7. [Key Systems — Technical Deep Dive](#7-key-systems--technical-deep-dive)
8. [Blender 5.0 API Notes and Gotchas](#8-blender-50-api-notes-and-gotchas)
9. [User Guide](#9-user-guide)
10. [Development History — The Road So Far](#10-development-history--the-road-so-far)
11. [Known Limitations and Future Work](#11-known-limitations-and-future-work)
12. [1.0 Release Checklist](#12-10-release-checklist)

---

## 1. Project Overview

EasyRetarget is a Blender addon that provides a simple, artist-friendly UI for setting up animation retargeting between two character rigs. The core workflow is:

1. The user selects a **Source Rig** (the rig that has animation) and a **Target Rig** (the rig that should receive it).
2. The user defines a list of **bone pairs**, mapping each source bone to a corresponding target bone.
3. For each pair, the user creates an **EasyRetarget Transform constraint** on the target bone that live-maps the source bone's rotation to the target bone. This is done through Blender's native Transform constraint system, meaning the retargeting is live, non-destructive, and baked into the `.blend` file with no persistent addon handler required during playback.
4. Eventually (not yet implemented), the user **bakes** the result to keyframes on the target rig.

The addon is designed primarily for control rigs with clean constraint stacks — specifically rigs using Child Of constraints as their primary hierarchy mechanism, with World Space support for root or COG bones.

---

## 2. Development Conventions

These conventions must be followed in all future development sessions.

- **Versioning:** Semantic versioning — `major.minor.patch`. The developer prompts when to move to the next major or minor version. All bug fixes and new features default to incrementing the patch version unless instructed otherwise.
- **Changelog:** Every version gets an entry in `CHANGELOG.md` following Keep a Changelog conventions. Changes are documented at the time the code is generated, not retroactively.
- **Output format:** Multi-file Blender package, distributed as a versioned `.zip` (e.g., `easy_retarget_0_2_6.zip`). The version number must always be in the zip filename.
- **Language:** United States English in all documents and code comments.
- **Code generation rule:** Never generate code or documents without being explicitly prompted. Explain reasoning and options first; wait for confirmation.
- **Clarification rule:** Always ask for clarification before choosing an implementation path. Number clarification question lists for easy reference. Getting it right the first time is the priority — reworking the same code repeatedly is far more costly than spending time on clarification upfront.
- **Multi-option rule:** If there are multiple valid implementation approaches, present all of them with their trade-offs and wait for the developer to choose.

---

## 3. File Structure

```
easy_retarget/
├── __init__.py              # bl_info, class registration/unregistration
├── properties.py            # PropertyGroup definitions, update callbacks, search callbacks
├── handlers.py              # load_post and SpaceView3D draw handlers
├── utils.py                 # Shared helper functions (get_bone, force_depsgraph_update)
├── constraint_utils.py      # Transform constraint helpers (create, find, remove, update)
├── operators_list.py        # Add, Remove, Move, AutoPopulate operators
├── operators_constraint.py  # EditConstraint, CreateConstraints, RemoveAllConstraints,
│                            # CopyConstraintSettings, PasteConstraintSettings,
│                            # RemoveConstraint, ConfirmTargetBoneChange
├── operators_io.py          # ExportJSON, ImportJSON, ImportJSONConfirm operators
├── op_bake.py               # Bake operator (placeholder — not yet implemented)
├── ui.py                    # UIList, N-Panel
└── debug.py                 # AddonPreferences, logging utilities, ResetAddonState
```

The package is distributed as `easy_retarget_X_Y_Z.zip` where X, Y, Z are the version numbers. The zip extracts to the `easy_retarget/` directory, which Blender installs as the addon package.

---

## 4. Architecture Overview

### The Core Idea: Constraints as the Runtime Layer

The most important architectural decision in EasyRetarget is that **the addon does not run any persistent logic during animation playback or pose evaluation**. Instead, it configures Blender's native **Transform constraint** on each target bone, and Blender's own constraint evaluation pipeline does all the live work. This means:

- The addon's constraint data (axis mapping, offsets, space) is stored directly in the `.blend` file as part of the constraint's own properties. No separate addon-side storage is needed for runtime values.
- The addon can be disabled after setup and the constraints continue to work.
- Performance during playback is determined by Blender's constraint evaluation, not by Python handler overhead.

The addon's role is to **configure** those constraints through a clean UI, and to manage their state (enabled/disabled) via a toggle system.

### What the Addon Does at Runtime

The only persistent runtime component is a **SpaceView3D draw handler** (`_sync_bone_pair_selection` in `handlers.py`) that fires on every viewport redraw. Its sole purpose is to sync the active pose bone in the viewport to the corresponding row in the N-panel bone pair list — a UI convenience that requires no constraint logic at all. This handler is extremely lightweight.

A **load_post handler** (`on_load_post` in `handlers.py`) fires once after a file is loaded and re-applies the constraint toggle state (All Off / All On / Custom) to ensure consistency if the file was saved or modified without the addon installed.

### Data Flow for a Retargeting Setup

```
User selects Source Rig + Target Rig
        ↓
User populates bone pairs (manually or via Auto Populate)
        ↓
User clicks constraint button on a bone pair row
        ↓
EditConstraint popup opens, reads/writes directly to the
Transform constraint on the target bone
        ↓
Blender evaluates the constraint stack on every frame —
source bone rotation is live-mapped to target bone
        ↓
(Future) User bakes result to keyframes on target rig
```

---

## 5. Module Reference

### `__init__.py`

Entry point for the addon. Contains `bl_info`, the `classes` tuple (in correct registration order — dependencies before dependents), `register()`, and `unregister()`.

`register()` registers all classes, attaches `EASYRETARGET_SceneProperties` to `bpy.types.Scene.easy_retarget`, then calls `handlers.register_handlers()`.

`unregister()` calls `handlers.unregister_handlers()` first, then unregisters all classes in reverse order, then deletes the scene property.

**When adding new operators or property groups:** add the class to the `classes` tuple and the corresponding import. Order matters — `PropertyGroup` subclasses must be registered before any class that references them (e.g., `EASYRETARGET_ConstraintState` before `EASYRETARGET_SceneProperties`).

---

### `properties.py`

Defines all `PropertyGroup` classes and their properties, plus search callbacks and update callbacks.

**`EASYRETARGET_ConstraintState`**
Stores the enabled state of one bone's EasyRetarget constraint. Used in the `constraint_state_snapshot` collection to remember per-bone states when the constraint toggle moves to All Off or All On.

Fields: `bone_name` (StringProperty), `enabled` (BoolProperty).

**`EASYRETARGET_BonePairItem`**
Represents one source-to-target bone mapping. The primary data unit of the addon.

Fields:
- `source_bone` — StringProperty with `_source_bone_search` callback. The bone name on the source rig.
- `target_bone` — StringProperty with `_target_bone_search` callback and `_on_target_bone_update` update callback.
- `previous_target_bone` — StringProperty (hidden). Stores the last confirmed target bone name for change detection in `_on_target_bone_update`.

**`EASYRETARGET_SceneProperties`**
Top-level scene property group, attached at `bpy.types.Scene.easy_retarget`. Contains all addon state.

| Property | Type | Purpose |
|---|---|---|
| `source_rig` | PointerProperty (Object, ARMATURE) | The source armature |
| `target_rig` | PointerProperty (Object, ARMATURE) | The target armature |
| `bone_pairs` | CollectionProperty (BonePairItem) | The list of bone mappings |
| `bone_pairs_index` | IntProperty | Active UIList selection index |
| `constraint_toggle` | EnumProperty | ALL_OFF / ALL_ON / CUSTOM |
| `constraint_state_snapshot` | CollectionProperty (ConstraintState) | Per-bone enabled state snapshot |
| `bone_pairs_expanded` | BoolProperty | UI expand/collapse state |
| `settings_expanded` | BoolProperty | UI expand/collapse state |
| `show_remove_constraint_column` | BoolProperty | Toggles remove column in the list |
| `bake_keyed_frames_only` | BoolProperty | Bake setting (unused in placeholder) |
| `keying_interval` | IntProperty | Bake setting (unused in placeholder) |

**Key callbacks:**

`_on_target_bone_update` — fires when `target_bone` changes on a `BonePairItem`. If the previous target bone had an EasyRetarget constraint, it invokes `EASYRETARGET_OT_ConfirmTargetBoneChange` via `INVOKE_DEFAULT` to ask the user before removing the old constraint. If no constraint existed, it silently updates `previous_target_bone`.

`_on_constraint_toggle_update` — fires when `constraint_toggle` changes. Implements the snapshot/restore logic: moving to ALL_OFF or ALL_ON snapshots current constraint enabled states (if no snapshot already exists), then sets all constraints on/off. Moving to CUSTOM restores from the snapshot and clears it.

---

### `handlers.py`

Contains the two persistent handlers and their registration/unregistration functions.

**`_sync_bone_pair_selection()`**
A `SpaceView3D` draw callback registered with `'POST_PIXEL'` on the `'WINDOW'` region. Fires on every viewport redraw.

Logic: reads `bpy.context.active_pose_bone`. Compares `(bone_name, owner_name)` against `_last_active_bone` — if unchanged, returns immediately (this is the key guard that prevents the handler from overwriting manual list selection on every redraw). If changed, updates `_last_active_bone`, searches `bone_pairs` for a matching `source_bone` or `target_bone`, updates `bone_pairs_index` if a match is found, and tags all VIEW_3D UI regions for redraw.

`_draw_handler` — module-level variable holding the draw handler reference so it can be removed on unregister.

`_last_active_bone` — module-level `tuple` of `(bone_name, owner_name)`, reset to `(None, None)` on `unregister_handlers()`.

**`on_load_post(filepath)`**
A `bpy.app.handlers.load_post` callback. Iterates all scenes, reads `constraint_toggle`, and calls `_apply_toggle_state()` for each scene.

**`_apply_toggle_state(props)`**
Internal helper. For CUSTOM mode: restores per-bone enabled states from `constraint_state_snapshot` (handles the case where the file was modified without the addon). For ALL_OFF/ALL_ON: sets all constraints enabled or disabled accordingly.

**`register_handlers()` / `unregister_handlers()`**
Register and unregister both handlers. `unregister_handlers()` also resets `_last_active_bone`.

---

### `utils.py`

Minimal shared helpers, deliberately kept small.

`get_bone(rig, bone_name)` — returns `rig.pose.bones.get(bone_name)` with null checks.

`force_depsgraph_update(context=None)` — calls `scene.frame_set(frame_current)` to force a depsgraph re-evaluation. Used primarily by rig picker update callbacks.

---

### `constraint_utils.py`

All logic for creating, finding, updating, and removing the EasyRetarget Transform constraint.

`CONSTRAINT_NAME = "EasyRetarget"` — the fixed name used for all constraints created by the addon.

`AXIS_ENUM` — dict mapping `'X'`, `'Y'`, `'Z'`, `'NONE'` to valid Blender axis enum values (`'NONE'` maps to `'X'` since Blender has no None axis, but Min/Max both being 0 in Add mode effectively zeroes the contribution).

**`find_retarget_constraint(pbone)`** — returns `pbone.constraints.get(CONSTRAINT_NAME)` or None.

**`remove_retarget_constraint(pbone)`** — removes the constraint if it exists.

**`calculate_map_to_min_max(invert, source_axis, offset_degrees=0.0)`**
Calculates the `to_min` and `to_max` degree values for one owner axis of the Transform constraint.

The Map From range is always ±180°. For a non-inverted 1:1 mapping with zero offset: `to_min = -180`, `to_max = 180`. For inverted: `to_min = 180`, `to_max = -180`. The offset shifts both ends linearly. For a `'NONE'` source axis: both are 0 (zeroes the axis contribution in Add mode).

Returns `(to_min, to_max)` in degrees. Caller converts to radians.

**`create_or_update_constraint(...)`**
The main workhorse function. Creates the constraint if it doesn't exist, then configures all fields. Parameters:

- `target_rig`, `target_bone_name` — the bone receiving the constraint
- `source_rig`, `source_bone_name` — the constraint target
- `map_x_from`, `map_y_from`, `map_z_from` — `'X'`, `'Y'`, `'Z'`, or `'NONE'`
- `invert_x`, `invert_y`, `invert_z` — bool
- `offset_x`, `offset_y`, `offset_z` — float, degrees
- `target_space`, `owner_space` — `'WORLD'` or `'LOCAL'`
- `enabled` — bool

**Critical implementation note:** `map_from` and `map_to` are only assigned when they differ from `'ROTATION'`. This is because reassigning `map_to` resets `mix_mode_rot` back to `'ADD'`, overriding any previous setting. The mix mode is set to `'REPLACE'` for World/World space and `'ADD'` for all other combinations. `mix_mode_rot` is always set after `map_to` is confirmed to be `'ROTATION'` to ensure it takes effect.

---

### `operators_constraint.py`

Contains all operators related to creating, editing, copying, pasting, and removing constraints.

**`EASYRETARGET_OT_EditConstraint`** (`easy_retarget.edit_constraint`)
The main constraint configuration popup. `pair_index` IntProperty identifies which bone pair it was invoked for.

`invoke()`: Sets `bone_pairs_index = pair_index` (so clicking the constraint button also selects the row). Creates the constraint with defaults if it doesn't exist. Reads all current constraint values into operator properties via `_read_from_constraint()`. Snapshots those values. Opens a `invoke_props_dialog`.

`draw()`: Draws the popup UI — space toggle, then per-axis rows with source axis dropdown, invert toggle, and offset field.

`execute()`: Calls `_write_to_constraint()` to write operator properties back to the constraint.

`cancel()`: Restores the snapshot by calling `_write_to_constraint()` with the snapshotted values. If the constraint was newly created (no pre-existing constraint), removes it entirely.

`_read_from_constraint(con)`: Reads all constraint fields into operator properties. Recovers offset from `to_min` values: for non-inverted axes `offset = degrees(to_min) + 180`; for inverted `offset = degrees(to_min) - 180`.

`_write_to_constraint()`: Calls `create_or_update_constraint()` with the current operator property values.

**`EASYRETARGET_OT_CreateConstraints`** (`easy_retarget.create_constraints`)
Creates or resets the EasyRetarget constraint on all populated bone pairs to defaults (X→X, Y→Y, Z→Z, no inversion, zero offset, Local/Local). Confirmation dialog warns that existing settings will be overwritten.

**`EASYRETARGET_OT_RemoveAllConstraints`** (`easy_retarget.remove_all_constraints`)
Removes the EasyRetarget constraint from all paired target bones. Confirmation dialog. Also resets `constraint_toggle` to CUSTOM.

**`EASYRETARGET_OT_CopyConstraintSettings`** (`easy_retarget.copy_constraint_settings`)
Copies the selected pair's constraint settings to the module-level `_constraint_clipboard` dict. Greyed out when the selected pair has no constraint.

**`EASYRETARGET_OT_PasteConstraintSettings`** (`easy_retarget.paste_constraint_settings`)
Pastes from `_constraint_clipboard` to the selected pair's constraint, creating it if needed. Greyed out when clipboard is empty or no valid pair is selected.

**`EASYRETARGET_OT_RemoveConstraint`** (`easy_retarget.remove_constraint`)
Removes the EasyRetarget constraint from a specific bone pair's target bone. `pair_index` IntProperty. Confirmation dialog. Called from the optional remove column in the bone pair list.

**`EASYRETARGET_OT_ConfirmTargetBoneChange`** (`easy_retarget.confirm_target_bone_change`)
Invoked from `_on_target_bone_update` when changing a target bone that already has a constraint. `pair_index`, `old_bone_name`, `new_bone_name` IntProperty/StringProperty. On confirm: removes the constraint from the old bone and updates `previous_target_bone`. On cancel: reverts `target_bone` back to `old_bone_name`.

**Module-level `_constraint_clipboard`** — dict or None. Holds copied constraint settings between copy and paste operations. Does not persist across Blender restarts.

---

### `operators_list.py`

List management operators.

**`EASYRETARGET_OT_AddBonePair`** — adds a blank entry, sets `bone_pairs_index` to the new item.

**`EASYRETARGET_OT_RemoveBonePair`** — checks if the selected pair has a constraint; if so, invokes a confirmation dialog. On confirm (or if no constraint), removes the constraint from the target bone and then removes the pair.

**`EASYRETARGET_OT_MoveBonePair`** — moves the selected entry up or down. `direction` EnumProperty (`'UP'`/`'DOWN'`).

**`EASYRETARGET_OT_AutoPopulate`** — clears and rebuilds the bone pairs list by iterating source rig bones and matching names against the target rig. `only_populate_matches` BoolProperty (default True) controls whether unmatched source bones get blank entries. Confirmation dialog with the option displayed. Note: Auto Populate does **not** create constraints — it only populates the list.

---

### `operators_io.py`

JSON export and import operators. Uses `ExportHelper` and `ImportHelper` from `bpy_extras.io_utils` to open Blender's native file browser.

**`EASYRETARGET_OT_ExportJSON`** (`easy_retarget.export_json`)
Iterates `bone_pairs`, reads constraint field values directly from each target bone's constraint, and writes a JSON file. Constraint data is included per pair only when an EasyRetarget constraint exists. Pairs without a constraint export with `"constraint": null`.

JSON structure:
```json
{
  "bone_pairs": [
    {
      "source_bone": "Hips",
      "target_bone": "pelvis",
      "constraint": {
        "map_x_from": "X",
        "map_y_from": "Y",
        "map_z_from": "Z",
        "invert_x": false,
        "invert_y": false,
        "invert_z": false,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "offset_z": 0.0,
        "space": "LOCAL"
      }
    }
  ]
}
```

**`EASYRETARGET_OT_ImportJSON`** (`easy_retarget.import_json`)
Reads a JSON file and stores it in module-level `_import_data`, then immediately invokes `EASYRETARGET_OT_ImportJSONConfirm` via `INVOKE_DEFAULT`.

**`EASYRETARGET_OT_ImportJSONConfirm`** (`easy_retarget.import_json_confirm`)
Confirmation dialog with three options: Append, Replace, Cancel. On Append or Replace: creates bone pairs from `_import_data`, creates constraints if both rigs are set and bones exist. Sets the initial constraint enabled state based on the current `constraint_toggle`. Clears `_import_data` after execution.

**Module-level `_import_data`** — dict or None. Holds parsed JSON between `ImportJSON.execute()` and `ImportJSONConfirm.execute()`.

---

### `op_bake.py`

Placeholder. `EASYRETARGET_OT_Bake` (`easy_retarget.bake`) reports an info message and returns `FINISHED`. No actual bake logic is implemented yet.

---

### `ui.py`

**`EASYRETARGET_UL_BonePairs`**
UIList subclass. `draw_item()` renders each bone pair row: source bone field (with red alert if invalid), forward arrow label, target bone field (with red alert if invalid), constraint button (CONSTRAINT_BONE icon if exists, ADD icon if not), and optional remove constraint button. The constraint button is greyed out unless both bones are populated.

Red highlighting logic: `source_valid = bool(props.source_rig and item.source_bone and props.source_rig.data.bones.get(item.source_bone))`. Same pattern for target. Alert is set only when the field has a non-empty value that doesn't resolve — empty fields are not highlighted red.

`draw_filter()` and `filter_items()` implement name-based list filtering using the built-in `filter_name` UIList property and `UI_UL_list.filter_items_by_name`.

**`EASYRETARGET_PT_MainPanel`**
The main N-panel. Draws in order: Rig pickers → Bone Pairs expandable section → Settings expandable section → Bake button.

The Bone Pairs section contains: Auto Populate, Create Constraints, Remove All Constraints buttons, the UIList, and the bottom button row (+/−/up/down/copy/paste/remove column toggle).

The Settings section contains: constraint toggle row (All Off / All On / Custom), bake settings, and the Export/Import JSON button pair.

---

### `debug.py`

**`EASYRETARGET_AddonPreferences`** (`bl_idname = __package__`)
Addon preferences panel. Contains:
- `debug_logging` BoolProperty — currently `True` by default. **Must be set to `False` before 1.0 release.**
- `log_directory` StringProperty — currently defaults to a developer-specific path. **Must be cleared before 1.0 release.**

The preferences panel draws the debug checkbox, log directory field, current log path, and the Reset Addon State button.

**`log(message)`** — writes a timestamped line to the session log file if debug logging is enabled.

**`log_section(title)`** — writes a section divider line to the log.

**`reset_session_log()`** — clears `_session_log_path` so the next `log()` call starts a new file.

**`EASYRETARGET_OT_ResetAddonState`** (`easy_retarget.reset_addon_state`)
Unregisters and re-registers all handlers, then starts a fresh log file. Accessible from addon preferences. Use this when reloading the addon mid-session in Blender without a full restart, to clear stale handler state.

**`_session_log_path`** — module-level string. Stable for the lifetime of a Blender session (or until `reset_session_log()` is called). Filename format: `easy_retarget_YYYY-MM-DD_HH-MM-SS.log`.

---

## 6. UI Reference

### N-Panel: EasyRetarget Tab

**Rigs section**
- Source Rig — object picker filtered to armatures only
- Target Rig — object picker filtered to armatures only

---

**Bone Pairs section** (expandable, default open)

- **Auto Populate** — clears and rebuilds the list from source rig bones. Confirmation dialog with "Only Populate Matches" checkbox. Does not create constraints.
- **Create Constraints** — creates EasyRetarget constraints on all populated pairs with default settings (X→X, Y→Y, Z→Z, Local/Local). Confirmation dialog warns settings will be overwritten.
- **Remove All Constraints** — removes EasyRetarget constraints from all paired target bones. Confirmation dialog.

Bone pair UIList. Each row:
- Source bone field (red if invalid/unresolvable)
- → arrow
- Target bone field (red if invalid/unresolvable)
- Constraint button — `CONSTRAINT_BONE` icon when constraint exists, `ADD` icon when it does not. Greyed out unless both bones are populated. Opens the Rotation Mapping popup. Also selects that row in the list.
- Remove constraint button (optional, hidden by default) — `X` icon, confirmation dialog.

Bottom row: + (Add) | − (Remove) | ↑ (Move Up) | ↓ (Move Down) | Copy Constraint | Paste Constraint | Remove Column toggle

---

**Settings section** (expandable, default closed)

- **Constraints toggle** — All Off / All On / Custom (default). Controls the enabled state of all EasyRetarget constraints on paired bones.
- **Bake Keyed Frames Only** checkbox (default on)
- **Keying Interval** integer field (greyed out when Bake Keyed Frames Only is on)
- **Bone Pairs Data** — Export JSON / Import JSON buttons side by side

---

**Bake button** — full width, outside all sections

---

### Rotation Mapping Popup

Opened by clicking the constraint button on a bone pair row.

- Target bone label at top
- **Space toggle** — Local / World. Controls both `target_space` and `owner_space` simultaneously. Local = Local/Local (Add mix mode). World = World/World (Replace mix mode).
- **Mapping section** — three rows, one per owner axis (X, Y, Z):
  - Axis label
  - Source axis dropdown — X, Y, Z, None
  - Invert toggle (greyed out when source axis is None)
  - Offset field in degrees ±180 (greyed out when source axis is None)
- Header label reads "Offset (Local)" or "Offset (World)" based on space selection

Cancel behavior:
- If the constraint existed before the popup was opened: restores all constraint fields to their pre-invoke state.
- If the constraint was newly created by opening this popup: removes it entirely.

---

## 7. Key Systems — Technical Deep Dive

### 7.1 The Transform Constraint and Offset Encoding

The EasyRetarget Transform constraint uses Blender's `TRANSFORM` constraint type with the following fixed configuration:

- `map_from = 'ROTATION'`
- Map From range: ±180° on all axes
- `map_to = 'ROTATION'`
- `use_motion_extrapolate = True`
- `mix_mode_rot = 'ADD'` for Local/Local, `'REPLACE'` for World/World

Per-axis mapping is encoded entirely in the `to_min` and `to_max` values:

| Scenario | to_min | to_max |
|---|---|---|
| Non-inverted, zero offset | -180° | +180° |
| Inverted, zero offset | +180° | -180° |
| Non-inverted, +10° offset | -170° | +190° |
| Inverted, +10° offset | +190° | -170° |
| None (axis zeroed) | 0° | 0° |

The `map_to_x_from`, `map_to_y_from`, `map_to_z_from` fields select which source rotation axis feeds each owner axis.

**Recovering offset from the constraint:** When reading back from an existing constraint, the offset is recovered from `to_min`:
- Non-inverted: `offset = degrees(to_min) + 180`
- Inverted: `offset = degrees(to_min) - 180`

**Why `map_from` and `map_to` are guarded before assignment:** Assigning `con.map_to = 'ROTATION'` unconditionally resets `con.mix_mode_rot` back to `'ADD'` every time it is called. Since `mix_mode_rot` must be `'REPLACE'` for World/World space, this guard is essential — without it, every `check()` call in an open popup would silently reset the mix mode.

### 7.2 Constraint Toggle System

The `constraint_toggle` EnumProperty on `EASYRETARGET_SceneProperties` has three states:

- **CUSTOM (default):** Individual constraint enabled states are respected as-is. This is the normal working state.
- **ALL_OFF:** All EasyRetarget constraints on paired bones are disabled. The current per-bone enabled states are snapshotted into `constraint_state_snapshot` before disabling (only if the snapshot is currently empty — preserves the snapshot when toggling between ALL_OFF and ALL_ON).
- **ALL_ON:** All constraints are enabled. Same snapshot logic as ALL_OFF.

Returning to CUSTOM from ALL_OFF or ALL_ON restores the per-bone states from the snapshot and clears it.

The snapshot persists in scene data across Blender restarts via `constraint_state_snapshot` CollectionProperty. The `load_post` handler re-applies the toggle state on file load.

### 7.3 Bone Selection Sync

`_sync_bone_pair_selection()` in `handlers.py` is a SpaceView3D draw callback that keeps the N-panel list selection in sync with the active pose bone in the viewport.

The key design challenge: a draw callback fires on every single viewport redraw — potentially dozens of times per second. Without a guard, it would overwrite manual list selection constantly. The `_last_active_bone` module-level tuple solves this: the handler does nothing unless `(bone_name, owner_name)` has changed since the last redraw. The guard makes the sync event-driven in practice even though the underlying mechanism is poll-based.

When a sync does occur, it iterates `bone_pairs` to find the first matching pair and updates `bone_pairs_index`. It then tags all VIEW_3D UI regions for redraw so the N-panel list updates immediately (necessary because the N-panel is in the same area but a different region than the viewport).

### 7.4 Target Bone Change Confirmation

When a user changes the `target_bone` field on a pair that already has an EasyRetarget constraint, `_on_target_bone_update` detects this via `previous_target_bone` and invokes `EASYRETARGET_OT_ConfirmTargetBoneChange`. The operator:

- On confirm: removes the constraint from the old target bone, updates `previous_target_bone` to the new bone name.
- On cancel: reverts `target_bone` back to `old_bone_name` (without triggering another update, since it's the same value as `previous_target_bone`).

This prevents silent constraint orphaning when the user accidentally changes a target bone that was already configured.

### 7.5 JSON Export/Import

The JSON format records all bone pair names and, when present, the full constraint configuration. The constraint data is recovered from the live constraint fields at export time (rather than from any addon-side duplicate storage), since the constraint is the single source of truth.

Import uses a two-step operator pattern — `ImportJSON.execute()` reads the file and stores it in the module-level `_import_data`, then immediately invokes `ImportJSONConfirm` via `INVOKE_DEFAULT`. This is necessary because Blender's `ExportHelper`/`ImportHelper` operators run their `execute()` in a non-interactive context (the file browser operator completes and then calls `execute()`), and `invoke_props_dialog` cannot be called from inside that execution context directly chained. The module-level variable bridges the two operators.

### 7.6 Copy/Paste Constraint Settings

`_constraint_clipboard` in `operators_constraint.py` is a module-level dict (or None) holding the most recently copied constraint settings. It does not persist across Blender restarts. The copy operator reads the current constraint fields and stores them in the clipboard dict. The paste operator reads from the dict and calls `create_or_update_constraint()`. Both operators use `poll()` to grey out when appropriate.

---

## 8. Blender 5.0 API Notes and Gotchas

These are hard-won findings from development. Each one cost real debugging time.

**`pbone.bone.select` is not settable.**
In Blender 5.0, `Bone.select` cannot be set from Python directly. Use `bpy.ops.pose.select_all(action='SELECT')` to select all bones instead.

**`bpy.ops.pose.visual_transform_apply()` requires a VIEW_3D context.**
This operator fails silently with a RuntimeError if no 3D viewport context is available. It must be called inside `context.temp_override()` with a valid `VIEW_3D` area and `WINDOW` region. (No longer used in the current architecture but critical to know for any future bake work.)

**Custom constraint subclassing is not supported.**
`bpy.types.Constraint` cannot be subclassed and registered via `bpy.utils.register_class()`. The Transform constraint is used instead of a custom constraint type.

**`TransformConstraint.mix_mode_rot` is reset by assigning `map_to`.**
Any assignment to `con.map_to` (even to the same value it already holds) resets `mix_mode_rot` to `'ADD'`. Always guard: `if con.map_to != 'ROTATION': con.map_to = 'ROTATION'`. Always set `mix_mode_rot` after any `map_to` assignment.

**Valid `mix_mode_rot` values:** `'REPLACE'`, `'ADD'`, `'BEFORE'`, `'AFTER'`. Only `'REPLACE'` and `'ADD'` are used by this addon.

**`bpy.context.active_pose_bone` behavior.**
Returns the active pose bone regardless of which object is active. Works in any mode where a pose bone is active (Pose Mode on any armature). `id_data` on the returned bone gives the owning armature object — this is how the sync handler determines which rig the active bone belongs to.

**SpaceView3D draw callbacks as a sync mechanism.**
`SpaceView3D.draw_handler_add(func, (), 'WINDOW', 'POST_PIXEL')` fires on every viewport redraw. This is the correct mechanism for polling Blender state that doesn't trigger a depsgraph update (like bone selection changes). `depsgraph_update_post` does NOT fire on bone selection changes, which is why the draw handler approach is used.

**Bone search in `StringProperty`.**
Use the `search` callback parameter on `StringProperty`, not a separate search operator. The callback should yield bone names matching `edit_text`. Set `search_options={'SORT'}` for alphabetical ordering.

**`CollectionProperty.add()` returns the new item.**
This is safe to use directly: `item = props.bone_pairs.add()`.

**`bpy.app.handlers.load_post` function signature.**
Handlers added to `load_post` must accept a single argument (`filepath` in Blender 5.0+).

---

## 9. User Guide

### Basic Setup

1. Install and enable the EasyRetarget addon in Blender Preferences.
2. In the 3D Viewport, open the N-panel and go to the EasyRetarget tab.
3. Set **Source Rig** to the armature that has the animation you want to retarget.
4. Set **Target Rig** to the armature that should receive the retargeted animation.

### Populating Bone Pairs

**Auto Populate** is the fastest way to get started. Click it and Blender will match bone names between the two rigs. With "Only Populate Matches" checked (default), only bones with matching names on both rigs are added. Uncheck it to add every source bone, leaving the target bone blank for non-matching ones.

You can also add pairs manually with the **+** button, or remove them with **−**. Reorder with the **↑** and **↓** buttons.

Source and target bone fields turn **red** if the rig is not set or the bone name doesn't exist on the rig. This is a validation indicator, not an error — you can still save the file.

### Creating Constraints

Once bone pairs are populated, click **Create Constraints** to create an EasyRetarget Transform constraint on every paired target bone with default settings (X maps to X, Y to Y, Z to Z, Local space, no inversion, no offset). A confirmation dialog warns that any existing settings will be overwritten.

Alternatively, click the **constraint button** (the ADD icon) on an individual bone pair row to create and configure a constraint for just that pair.

### Configuring a Constraint

Click the **constraint button** on any row (CONSTRAINT_BONE icon when a constraint exists, ADD icon when it doesn't). The **Rotation Mapping popup** opens.

- **Space:** Local or World. Local is appropriate for most control bones. World is appropriate for root or COG bones that need to copy world-space rotation directly.
- **Axis mapping:** For each target bone axis (X, Y, Z), choose which source axis to map from. Set to None to zero out that axis (the target bone won't rotate on that axis based on the source).
- **Invert:** Reverses the mapping direction for that axis.
- **Offset:** Shifts the mapped rotation by a fixed degree amount. Useful for correcting a rest pose difference between source and target bones.

Closing with **OK** applies the settings. Closing with **Cancel** restores the constraint to what it was before you opened the popup (or removes it entirely if it was just created).

### Constraint Toggle

In the Settings section, the **Constraints** toggle row controls all EasyRetarget constraints at once:

- **All Off:** Disables all constraints — the target rig returns to its native pose. The individual enabled states are remembered.
- **All On:** Enables all constraints.
- **Custom (default):** Respects each constraint's individual enabled state, which can be toggled from Blender's standard constraint properties.

This is useful for quickly previewing the target rig with and without the retargeting applied.

### Saving and Sharing Setups

Use **Export JSON** to save the current bone pair list and all constraint settings to a `.json` file. Use **Import JSON** on another file (or the same file after reworking) to bring them back. Import offers Append (add to existing list) or Replace (clear then import).

You can also **Copy** and **Paste** constraint settings between individual bone pairs using the buttons in the bottom row of the list.

### Baking

The **Bake** button is present in the UI but is not yet implemented. It will eventually bake the retargeted animation to keyframes on the target rig.

---

## 10. Development History — The Road So Far

This section documents not just what was built, but why decisions were made, what was tried, and what failed. This context is essential for understanding why the current architecture is the way it is and for avoiding re-investigating dead ends.

### Phase 1 — Single File Scaffold (0.0.0–0.0.9)

The addon began as a single `.py` file with a basic UI: rig pickers, a bone pair list, and a Live Offset handler. The core idea at the time was a `depsgraph_update_post` handler that would run every frame and write the source bone's rotation (plus a stored offset) directly to the target bone's pose channels.

The first major challenge was the **offset handler cache**. Writing to pose channels every depsgraph update is straightforward, but detecting when the user has manually adjusted a bone (as opposed to the handler writing it) proved very difficult. The problem: how do you know if the current channel value was put there by the handler or by the user? Several strategies were tried:

- **Storing the "applied" value and subtracting it next frame** — this would accumulate floating point errors and break completely if the user made multiple changes before the handler ran.
- **Pre/post snapshot strategy** — a `depsgraph_update_pre` handler captured the bone's state before the post handler wrote to it. The difference between pre and the previous written value indicated user intent. This was architecturally cleaner but still fragile.
- **Persistent user intent storage** — intent stored in scene properties so it survived addon reloads. Better, but still produced wrong results on single-channel drags (dragging X rotation alone would corrupt Y and Z intent) and on Alt+R bone resets.

By 0.0.9, the handler was roughly working but remained fragile. The key lesson: **tracking user intent through a poll-based handler is fundamentally difficult** because you can't distinguish the user's change from the handler's own previous write without careful bookkeeping that itself introduces bugs.

### Phase 2 — Multi-File Refactor (0.1.0)

The addon was refactored into a proper multi-file Blender package to support growing complexity. This was a clean structural change with no feature additions.

### Phase 3 — Match All / Match Source and the Quaternion Math Struggle (0.1.1–0.1.18)

With the Live Offset handler established, the next need was an operator to compute the correct **rotation offset** between a source and target bone — the delta that would make the target bone align with the source when the Live Offset was applied. This became the longest and most difficult part of the project.

The idea was: at rest, compute the world-space rotation of both the source and target bones, and find the local-space delta that the handler should apply to make them match.

**Why this is hard:**
- Blender bones have a non-identity rest orientation. Every bone points along +Y by default, but the bone's `matrix_local` encodes its actual orientation in its parent's space. You can't treat a bone's local rest as identity.
- For a bone in a hierarchy, the relevant "local rest" must be expressed relative to the parent's current orientation, not the parent's rest orientation. At the time the handler applies its offset, the parent has already been offset itself — so the parent's posed orientation is the correct reference frame, not its rest orientation.
- Parent-chain accumulation across multiple bones in Match All meant that each bone's computation depended on what the previous bone in the chain ended up at, but those values weren't in the depsgraph yet.
- Quaternion hemisphere issues caused sign flips at certain orientations.

Over versions 0.1.3 through 0.1.12, numerous approaches were tried:
- Using `matrix_local.to_quaternion()` directly — incorrect for parented bones due to bone-length translation contamination.
- Accumulating rotation up the parent chain manually — produced nonsensical results for child bones.
- World-space delta approach — better, but mixing rest and posed spaces caused incorrect results at depth.
- Rest-to-rest world-space approach with hemisphere normalization — mathematically cleaner but still produced wrong results when applied parent-first because the parent's depsgraph state was stale.

**The breakthrough (0.1.13–0.1.18):** Rather than computing the rotation math manually, the team pivoted to using **Blender's own constraint evaluation pipeline**. The sequence was:
1. Set both rigs to REST position.
2. Add a temporary `COPY_ROTATION` constraint (World/World, Replace) on the target bone.
3. Force a depsgraph update.
4. Use `bpy.ops.pose.visual_transform_apply()` to bake the constraint result into the pose channels.
5. Read the baked channels — those ARE the correct offset values.
6. Remove the temporary constraint and restore the rigs.

This completely sidestepped the quaternion math problem by letting Blender compute it. The main implementation challenge was that `visual_transform_apply()` requires a valid `VIEW_3D` area context — it fails silently without one, and the context override mechanism (`context.temp_override()`) was necessary.

### Phase 4 — Simplification and Stabilization (0.1.19–0.1.31)

After the constraint-pipeline match sequence was working, attention returned to the Live Offset handler's user intent system. Versions 0.1.19–0.1.21 added detailed diagnostic logging and attempted to improve intent tracking, but the fundamental problem remained — single-channel drags and Alt+R resets still caused corruption in some cases.

**0.1.22 made the decisive simplification:** user intent was removed entirely. The Live Offset handler simply locked the target bone's pose channels to `offset values` on every update. If the user moved the bone manually, the handler would immediately override it. This is less flexible — you can't pose on top of an offset while Live Offset is active — but it's completely correct and never produces corrupt intent state. A single `_run_match_sequence()` helper unified Match All and Match Source, and a full armature snapshot/restore system ensured the target rig was always returned to its previous state after matching.

Subsequent patches added:
- `load_post` handler for restart persistence (0.1.27)
- Constraint disable/restore system — all constraints on target bones were disabled during a Live Offset session and re-enabled on toggle-off (0.1.25). This was necessary because existing constraints on the target bones would fight the handler's writes.
- A per-bone `use_local_rotation` option (0.1.32, later removed in 0.2.0)
- Rotation mode tracking to handle bones that use Euler, Quaternion, or Axis Angle (0.1.29–0.1.31)

### Phase 5 — The Architecture Pivot to Native Constraints (0.2.0)

By 0.1.32, the Live Offset system was working but remained architecturally complex. The key insight that drove the 0.2.0 pivot was: **if the retargeting is essentially a Copy Rotation with some axis remapping, Blender already has a constraint that does exactly that — the Transform constraint**. Using it natively means:

- No persistent depsgraph handler required during playback.
- The constraint data is stored in the `.blend` file natively — no addon-side duplicate storage needed.
- The constraint can be disabled per-bone without removing it, enabling easy comparison.
- The addon can be disabled after setup and the constraints continue to work.

The trade-off was that the offset is now a **linear shift of the Map To range** (a static baked value at constraint creation time), not a truly additive offset in the sense that it doesn't update if the user adjusts it in real time. But for the primary use case — correcting a fixed rest pose difference between two rigs — a static linear shift is sufficient.

The entire `operators_offset.py` module was removed, along with all the Live Offset handler logic, the user intent system, the pose snapshot system, and the constraint disable/restore system. The addon became significantly simpler.

### Phase 6 — Post-Pivot Features (0.2.1–0.2.6)

After the architecture pivot, several features were added to make the constraint-based system complete and production-ready:

- **Bone selection sync** (0.2.1–0.2.2, 0.2.5): A draw handler syncs the active viewport bone to the N-panel list. First implemented as a `depsgraph_update_post` handler (which doesn't fire on bone selection) then correctly reimplemented as a `SpaceView3D.draw_handler_add` callback. The sync was initially overwriting manual list selection on every redraw (fixed in 0.2.5 by tracking `_last_active_bone`).

- **Constraint popup improvements** (0.2.2–0.2.4): The offset values were made functional (0.2.2). Canceling the popup was fixed to correctly restore the pre-invoke constraint state — the initial implementation failed to snapshot the state before opening (0.2.4). The space selection was changed from separate target/owner dropdowns to a single Local/World toggle because both spaces must always be set together for the mix mode to be correct.

- **Copy/Paste constraint settings** (0.2.4): Module-level clipboard. The remove constraint column was moved from the popup to the list rows behind a toggle (0.2.4).

- **JSON Export/Import** (0.2.6): Full round-trip save/load of bone pairs and constraint settings.

- **Red highlighting** (0.2.6): Bone pair fields turn red when the bone name is invalid.

- **Reset Addon State** (0.2.3): Utility for mid-session addon reloads without a full Blender restart.

---

## 11. Known Limitations and Future Work

### Not Yet Implemented

**Bake operator:** `op_bake.py` is a placeholder. The bake system needs to: iterate all frames (or only keyed frames), evaluate the depsgraph at each frame, read the target bone's resulting world/local pose (with the EasyRetarget constraint contributing), write that as a keyframe, then disable the constraint. The "Bake Keyed Frames Only" and "Keying Interval" settings in the UI are wired to properties but not yet used.

### Known Limitations

**Linear shift offset only:** The current offset mechanism is a linear shift of the Transform constraint's Map To range. This means:
- The offset is a fixed degree amount baked into the constraint at configuration time.
- It is not "additive on top of whatever the bone is doing" in a general sense — it's specifically a shift of the ±180° mapping range.
- For World/World space, the offset operates in world space, which may not be what the user expects (they may want a local-space correction on top of a world-space mapping).
- A truly additive local-space offset on top of a World/World Replace mode constraint would require a second constraint (e.g., a Copy Rotation in Local/Local space on top of the Transform constraint). This is documented as a future option if the need arises.

**Driver-controlled constraint enabled states:** If a target bone's constraint has its enabled state controlled by a driver, the constraint toggle system and `load_post` handler may conflict with that driver. Noted as a potential edge case for rigs with driver-controlled constraint stacks.

**Location and scale:** The current system only addresses rotation mapping. Location and scale retargeting are not implemented. The addon is designed for control rigs where location is typically handled by the rig hierarchy, but some workflows may need location mapping.

**Complex constraint stacks:** The addon is explicitly designed for target rigs with clean constraint stacks (Child Of only). Rigs with complex constraint hierarchies (IK chains, stretch-to, etc.) may not behave correctly with a Transform constraint added on top.

**No per-pair enabled state in the UI:** The individual constraint enabled state is not surfaced in the N-panel (it's accessible through Blender's standard bone properties). The remove column provides removal but not per-row toggling.

---

## 12. 1.0 Release Checklist

- [ ] Implement Bake operator (`op_bake.py` is currently a placeholder)
- [ ] Set `debug_logging` default to `False` in `debug.py`
- [ ] Clear `log_directory` default in `debug.py` (currently hardcoded to a developer path)
- [ ] Full testing across a variety of real character rig pairs
- [ ] Review and finalize changelog
- [ ] Verify all UI labels and operator tooltips are clear and consistent
- [ ] Confirm all confirmation dialogs are present where destructive actions occur
