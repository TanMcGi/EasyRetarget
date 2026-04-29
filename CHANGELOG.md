# Changelog

All notable changes to EasyRetarget will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (major.minor.patch).

---

## [0.4.2] — 2026-04-21

### Added
- **Pose mode pie menu** (`Ctrl+Shift+E`) titled "Easy Retarget" with six options:
  Rotation - Use Local, Rotation - Use World, Location - Use Local, Location - Use World,
  Inversions, and Mapping. The four space options apply to all selected target rig bones
  that have the relevant constraint. Inversions opens the Adjust Inversions popup.
  Mapping opens the Constraint Mapping popup for the active bone.
- **Adjust Inversions popup** (`Ctrl+Shift+I`, also accessible from the pie menu).
  Displays rotation and/or location sections based on which constraint types exist on any
  selected target rig bone. Each axis shows a four-button switch: Current (no change),
  All On, All Off, and Toggle All. Changes apply in real time; Cancel reverts all
  affected constraints to their pre-invoke state via a range snapshot.
- **Mapping popup keybind** (`Alt+Shift+M`, also accessible from the pie menu). Opens
  the Constraint Mapping popup for the active bone only. If the active bone is not in
  the bone pair list, a warning is reported. If the bone is paired but has no constraints,
  the popup opens in blank-slate mode without auto-creating constraints.
- **`blank_slate` mode on `EASYRETARGET_OT_EditConstraint`**. When invoked with
  `blank_slate=True`, the popup skips automatic constraint creation on open even when
  the addon preferences have creation defaults enabled.
- **`operators_pose.py`** — new module containing `EASYRETARGET_OT_RetargetSpace`,
  `EASYRETARGET_OT_AdjustInversions`, `EASYRETARGET_OT_OpenMappingForActiveBone`,
  and `EASYRETARGET_MT_EasyRetargetPie`.
- All three new keybinds sync between the addon preferences hotkey panel and Blender's
  keymap preferences, following the same pattern as the existing Add Bone Pair from
  Selection keybind.

### Changed
- **Fine Tune sections in the Constraint Mapping popup are now collapsible**, with one
  independent section for Rotation and one for Location. Both default to collapsed.
  Expanded/collapsed state persists per bone pair in scene data via new
  `rot_fine_tune_expanded` and `loc_fine_tune_expanded` fields on
  `EASYRETARGET_BonePairItem`.

---

## [0.4.1] — 2026-04-21

### Added
- **`matching.py` — individual toe bone detection.**
  AutoPopulate now identifies and correctly matches individual toe bones across
  all common naming conventions:
  - **Named compound forms:** `BigToe`, `SecondToe`, `MiddleToe`, `FourthToe`,
    `SmallToe` / `LittleToe`, `RingToe`, `FirstToe`, `GrossToe`, and their
    `toe`-prefix variants (`ToeBig`, `ToeRing`, etc.).
  - **Standalone anatomical terms:** `Hallux` / `Halux` (always resolves to big toe).
  - **Numbered `toe1`–`toe5` style** (no separator before digit): the digit is
    treated as a toe identity number rather than a bone segment, so `DEF-toe1.L`
    resolves to big toe identity with no segment, matching `BigToe.L`.
  - **`toe.01` / `toe.001` style** (separator before digit): the digit is kept
    as a bone segment number; the bone falls through to the generic `toe`
    canonical name as before.
  - **Rigify `f_`-prefixed individual toes:** `DEF-f_bigtoe.01.L`,
    `DEF-f_smalltoe.02.R`, etc. The leading `f` is stripped before detection
    when the standard path produces no match.
  - Individual toes match on a `(toe_identity, segment)` compound key — the
    same scheme used for fingers — preventing cross-toe mismatches.

### Fixed
- **`_extract_segment()` return signature** updated from 2-tuple to 3-tuple
  `(text, segment, had_separator)`. All call sites updated to unpack three
  values. The `had_separator` flag drives the `toe1` vs. `toe.01`
  disambiguation described above.
- **AutoPopulate dialog descriptions** shortened for readability. All three
  rebuild mode descriptions are now single-line strings that fit comfortably
  within the dialog box without wrapping.
- **Status icon column overlap** in the bone pair list: replaced
  `column + scale_x=0.7` with `layout.split(factor=0.08)` so the icon strip
  occupies a fixed fractional width and no longer compresses the source bone
  field.

---

## [0.4.0] — 2026-04-21

### Added
- **`matching.py` — full bone matching algorithm for AutoPopulate.**
  A new module implements a multi-phase normalization and matching pipeline:
  - **Phase 1 — Normalization:** strips known rig prefixes (`DEF-`, `ORG-`,
    `MCH-`, `CTRL-`, `mixamorig:`, `Bip01_`, `CC_Base_`, `ValveBiped_`, `b_`)
    and suffixes (`_jnt`, `_jt`, `_bind`, `_bone`, `_def`); extracts and
    normalizes side tokens (`Left`/`Right`/`.L`/`.R`/`_L`/`_R` in prefix,
    suffix, or camelCase positions); extracts trailing segment numbers
    (`.01`, `_1`, `1`, etc.); splits camelCase and removes all separators
    to produce a compact lowercase token.
  - **Phase 2 — Finger detection:** resolves named fingers (`thumb`, `index`,
    `middle`, `ring`, `pinky`/`little`), Rigify `f_` prefixes (`f_thumb`,
    `f_index`, etc.), and numbered fingers (`Finger1`, `Finger2`, …). Numbered
    finger offset (whether `Finger1` is thumb or index) is determined
    automatically by detecting whether a separate thumb-named bone exists in
    the selection.
  - **Phase 3 — Synonym lookup:** maps normalized tokens to canonical
    anatomical names via a synonym table covering all major body segments.
    Bare `arm` and bare `leg` are treated as low-confidence synonyms for
    `upperarm` and `thigh` respectively and produce a WARNING status.
    Additional synonyms: `knee`↔`shin`, `elbow`/`lowerarm`↔`forearm`,
    `wrist`↔`hand`, `calf`/`lowerleg`↔`shin`, `ankle`↔`foot`,
    `clavicle`/`collar`/`collarbone`↔`shoulder`, `pelvis`/`hip`↔`hips`,
    and more.
  - **Phase 4 — Matching:** hard-filters by side, pole/aim status, and
    finger vs. non-finger category. Finger bones match on `(finger_identity,
    segment)` as a compound key. Regular bones match on canonical name.
    Pole/aim/target bones only match other pole/aim/target bones. A unique
    match produces `CONFIRMED`; a low-confidence or ambiguous match produces
    `WARNING`; no match produces `ERROR`.
- **Match status icon column** in the bone pair list. A new first column
  shows the match state for each pair:
  - Dot (`DECORATE`) — no match attempted or pair is empty.
  - Checkmark (`CHECKMARK`) — high-confidence match or manually verified.
  - Warning button (`ERROR`) — low-confidence match. Clicking the button
    opens a confirmation popup showing the match reason and promotes the
    pair to confirmed status.
  - X (`CANCEL`) — no match found; requires manual entry.
  Manual pairs (added via the `+` button, hotkey, or direct bone field edits)
  always display as confirmed once both bone fields are populated.
- **`EASYRETARGET_OT_ConfirmMatchWarning`** — operator invoked by clicking a
  warning icon in the list. Opens a popup displaying the source bone, target
  bone, and the reason for the low-confidence warning. Confirming sets
  `match_status = 'CONFIRMED'` and `is_manual = True`.
- **`EASYRETARGET_OT_ClearAllWarnings`** — bulk operator that confirms all
  WARNING-status pairs at once. Displayed as a "Clear Warnings" button in the
  Bone Pairs section, directly below Auto Populate. Greyed out when no
  warnings exist in the list.
- **`match_status` EnumProperty** (`NONE` / `CONFIRMED` / `WARNING` /
  `ERROR`) on `EASYRETARGET_BonePairItem`. Persists in scene data.
- **`match_reason` StringProperty** on `EASYRETARGET_BonePairItem`. Stores
  the human-readable reason for a WARNING status, displayed in the
  confirmation popup.
- **`is_manual` BoolProperty** on `EASYRETARGET_BonePairItem`. `True` when
  the pair was set by the user rather than the algorithm. Used by the
  Re-run Algorithm rebuild mode to determine which pairs to preserve.
- **AutoPopulate log** (`auto_populate/autopopulate_YYYY-MM-DD_HH-MM-SS.log`).
  A distinct log file, separate from the general session log, is created fresh
  on each AutoPopulate run. Written to the `auto_populate/` subdirectory inside
  the configured log directory. Records the rebuild mode, rig names, bone
  counts, per-bone match results with reasons for warnings and errors, and a
  final summary. Controlled by the same Debug Logging preference as the
  session log. New functions `reset_ap_log()`, `log_autopopulate()`, and
  `log_ap_section()` added to `debug.py`.

### Changed
- **AutoPopulate confirmation dialog redesigned.** The previous checkbox-based
  dialog is replaced with a three-option rebuild mode selector:
  - **Fill Gaps Only** — re-evaluates only unmatched, warning, and error pairs;
    all confirmed pairs are preserved regardless of `is_manual`.
  - **Re-run Algorithm** *(default)* — re-runs the matching algorithm on all
    bones; pairs with `is_manual = True` are preserved.
  - **Full Rebuild** — clears all existing pairs and rebuilds from scratch.
  A dynamic description below the selector updates to explain exactly what
  will happen for the chosen mode. The description box uses an alert style
  only for Full Rebuild.
- **AutoPopulate uses selected bones when in Pose Mode.** If bones are
  selected on both source and target rigs when the operator runs, only those
  bones are passed to the matching algorithm. Falls back to all armature bones
  when not in Pose Mode or when no valid selection is present on both rigs.
- **AutoPopulate result report** now includes per-category counts:
  confirmed, warnings, and errors.
- **`_on_target_bone_update`** in `properties.py` now sets `is_manual = True`
  and updates `match_status` to `'CONFIRMED'` (or `'NONE'` if the target field
  is cleared) whenever the user manually edits the target bone field.
- **`EASYRETARGET_OT_ConfirmTargetBoneChange.execute()`** now sets
  `is_manual = True` and `match_status = 'CONFIRMED'` after the user confirms
  changing a constrained target bone.
- **`EASYRETARGET_OT_AddBonePair`** initializes `match_status = 'NONE'` and
  `is_manual = True` on new blank pairs.
- **`EASYRETARGET_OT_AddBonePairFromSelection`** sets `match_status =
  'CONFIRMED'` and `is_manual = True` on pairs created from selection.

---

## [0.3.7] — 2026-04-21

### Changed
- **Create Constraints popup now presents per-run constraint type selection.**
  The confirmation dialog for the Create Constraints button now includes
  Rotation and Location checkboxes above the warning text. Both checkboxes
  default to the values set in addon preferences (`Create Rotation Constraint
  by Default` and `Create Location Constraint by Default`), so the user's
  preferences are respected without requiring any changes to preferences for
  one-off overrides. The warning text below the checkboxes updates dynamically
  to name which constraint types will be affected. If neither checkbox is
  checked, the alert changes to an info message and the operator cancels
  without making any changes. The info report on completion now lists counts
  for each constraint type that was processed.

---

## [0.3.6] — 2026-04-21

### Fixed
- **`AttributeError: 'Bone' object has no attribute 'select'` when using Ctrl+Shift+P to add a bone pair from selection.** In Blender 5.0, `bpy.types.Bone.select` was removed from the API. The `EASY_RETARGET_OT_add_bone_pair_from_selection` operator now uses `context.selected_pose_bones` (the Blender 5.0-compatible approach) and filters results by `PoseBone.id_data` to identify which bones belong to the source rig and which to the target rig. Behavior is otherwise identical to previous versions.

---

## [0.3.5] — 2026-04-18

### Added
- **Per-axis fine-tune offsets (rotation and location)** — each rotation axis now exposes
  independent "Fine Min" and "Fine Max" float fields in the constraint popup, stacked on top
  of the existing overall offset. Fine-tune values are encoded directly into the constraint's
  `to_min`/`to_max` range, so no extra Blender data is needed. The overall offset is stored
  per axis on the bone pair item (`rot_offset_x/y/z`, `loc_offset_x/y/z`) so that fine-tune
  can be correctly recovered when the popup is re-opened. Pre-0.3.5 constraints are migrated
  lazily on first open.
- **Add/Remove buttons per constraint section** — each section (Rotation, Location) in the
  constraint popup now shows an **Add** button in its header when no constraint exists, rather
  than auto-creating one on expand. When a constraint is present, a **Remove** button appears
  at the bottom of the expanded section, followed by an inline confirmation row ("Remove? Yes /
  No") to prevent accidental deletion. Canceling the main popup fully restores the pre-invoke
  state, including re-creating any constraint removed during the session.
- **Addon preferences for default constraint creation** — a new "Constraint Defaults" section
  in EasyRetarget addon preferences lets the user choose which constraints are automatically
  created when the edit popup is opened for a bone pair with no constraints. Rotation defaults
  to enabled; Location defaults to disabled. Both settings can be toggled independently.

### Changed
- **Constraint popup no longer auto-creates the location constraint on expand** — location is
  only created when the user explicitly clicks Add, or when the "Create Location by Default"
  preference is enabled.
- **Export/Import JSON now includes fine-tune values** (`fine_min_x/y/z`, `fine_max_x/y/z`
  for both rotation and location). Files exported from earlier versions import correctly with
  fine-tune values defaulting to `0.0` (backward compatible).
- **Copy/Paste constraint settings now transfers fine-tune values** alongside the existing
  axis mapping, invert, offset, and space settings.

---

## [0.3.4] — 2026-04-18

### Added
- **Hotkey: Add Bone Pair from Selection** (`Shift+Ctrl+P` in Pose Mode) — with both
  rigs set, select exactly one bone on the source rig and one on the target rig, then
  press the hotkey to instantly add the pair to the list. The operator identifies which
  bone belongs to which rig by ownership, so selection order does not matter. Cancels
  with a clear warning if zero or more than one bone is selected on either rig.
- **`keymap.py`** — new module that handles addon keymap registration and unregistration.
  The keymap is scoped to the `'Pose'` context so it only fires in Pose Mode.
- **Configurable hotkey in addon preferences** — the hotkey widget is rendered in the
  EasyRetarget addon preferences panel using `rna_keymap_ui.draw_kmi`, the same widget
  shown in Blender's Keymap editor. Both locations reference the same underlying
  `KeyMapItem`, so editing in either place is automatically reflected in the other.

---

## [0.3.3] — 2026-04-18

### Added
- **"EasyRetarget Only" constraint toggle** — a fourth toggle mode that disables all
  non-EasyRetarget constraints on paired target bones and force-enables both
  `EasyRetarget_Rotation` and `EasyRetarget_Location`. Displayed as a full-width
  button on a second row beneath the existing All Off / All On / Custom row.
- **Other constraint snapshot** — when entering "EasyRetarget Only" mode, the previous
  enabled state of every non-EasyRetarget constraint on paired bones is saved to
  `other_constraint_snapshot`. When switching to any other mode those states are
  restored before the new mode is applied. The snapshot persists in scene data across
  Blender restarts via `_apply_toggle_state` in the `load_post` handler.
- **`EASYRETARGET_OtherConstraintState`** — new `PropertyGroup` (fields: `bone_name`,
  `constraint_name`, `enabled`) backing the other constraint snapshot collection.

---

## [0.3.2] — 2026-04-18

### Fixed
- **`AttributeError: '_RestrictData' object has no attribute 'scenes'` on install.**
  During addon installation Blender runs `register()` in a restricted data context
  where `bpy.data` does not expose `scenes`. The migration and toggle restoration
  loop in `register()` now checks `hasattr(bpy.data, 'scenes')` before iterating,
  so the loop is silently skipped during installation. The `on_load_post` handler
  covers the migration when an actual file is opened, so no functionality is lost.

---

## [0.3.1] — 2026-04-18

### Fixed
- **`on_load_post` not firing on file open.** The handler was missing the
  `@bpy.app.handlers.persistent` decorator. Without it, Blender removes
  non-persistent handlers before firing them during a file load, so the
  handler never ran. This caused two regressions introduced in 0.3.0:
  the legacy constraint name migration (`"EasyRetarget"` → `"EasyRetarget_Rotation"`)
  never executed, leaving existing bone pairs unable to find their constraints
  (all rows showing the `+` icon); and the constraint toggle state was not
  restored after opening a file. Both are now fixed.
- **Migration and toggle restoration not running on addon enable.** `register()`
  now calls `_migrate_constraint_names` and `_apply_toggle_state` for all
  current scenes immediately after registration, covering the case where a
  file is already open when the addon is enabled (since `load_post` does not
  fire in that scenario).

---

## [0.3.0] — 2026-04-17

### Added
- **Location mapping** — each bone pair now supports a second `EasyRetarget_Location`
  Transform constraint that maps source bone location to target bone location. Supports
  the same per-axis source selection (X, Y, Z, None), invert, and offset controls as
  rotation, with its own independent Local/World space toggle. Offsets are in Blender
  units. The from-range is fixed at ±100 units with `use_motion_extrapolate = True`,
  giving a 1:1 default mapping at any scale. `mix_mode` is set to `'REPLACE'` for
  World/World space and `'ADD'` for Local/Local.
- **Dual-section constraint popup** — `EASYRETARGET_OT_EditConstraint` now shows two
  collapsible sections: **Rotation** (expanded by default) and **Location** (collapsed
  by default). The location section auto-creates the location constraint with defaults
  when first expanded; cancelling the popup removes it if it was freshly created.
- **Per-bone-pair section memory** — `rotation_expanded` and `location_expanded`
  `BoolProperty` fields on `EASYRETARGET_BonePairItem` persist each pair's popup
  expanded/collapsed state across sessions in scene data.
- **`ensure_constraint_order`** in `constraint_utils.py` — enforces that
  `EasyRetarget_Location` always precedes `EasyRetarget_Rotation` in the constraint
  stack. Called automatically after every constraint creation or update.
- **`create_or_update_location_constraint`** and supporting find/remove helpers
  (`find_location_constraint`, `remove_location_constraint`) in `constraint_utils.py`.
- **`LOCATION_CONSTRAINT_NAME = "EasyRetarget_Location"`** constant in
  `constraint_utils.py`.
- **`LOCATION_AXIS_ITEMS`** enum items in `operators_constraint.py` for location axis
  dropdowns.

### Changed
- **Rotation constraint renamed** from `"EasyRetarget"` to `"EasyRetarget_Rotation"`.
  `CONSTRAINT_NAME` is replaced by `ROTATION_CONSTRAINT_NAME`. All existing functions
  (`find_retarget_constraint`, `remove_retarget_constraint`, `create_or_update_constraint`)
  are renamed to `find_rotation_constraint`, `remove_rotation_constraint`,
  `create_or_update_rotation_constraint` for symmetry with the new location equivalents.
- **`calculate_map_to_min_max`** now accepts a `half_range` parameter (default `180.0`
  for rotation; pass `100.0` for location). Signature change is backward-compatible via
  the default.
- **Constraint toggle system** (`_on_constraint_toggle_update`, `_apply_toggle_state`)
  now applies to both rotation and location constraints simultaneously. The snapshot
  stores one representative enabled state per bone (rotation takes precedence; falls
  back to location) and restores it to both constraints.
- **`_on_target_bone_update`** in `properties.py` now checks for either constraint
  (`find_rotation_constraint` or `find_location_constraint`) before invoking the
  confirmation dialog.
- **`EASYRETARGET_OT_ConfirmTargetBoneChange`** removes both constraints from the old
  bone on confirm.
- **`EASYRETARGET_OT_RemoveBonePair`** removes both constraints from the target bone.
  Confirmation dialog now fires if either constraint is present.
- **`EASYRETARGET_OT_RemoveConstraint`** (row remove button) removes both constraints.
- **`EASYRETARGET_OT_RemoveAllConstraints`** removes both constraints per pair. Count
  reflects total constraints removed (up to 2 per pair).
- **`EASYRETARGET_OT_CreateConstraints`** now creates only the rotation constraint
  (with defaults) for all populated pairs. Location is opt-in via the popup. Warning
  text updated accordingly.
- **`EASYRETARGET_OT_CopyConstraintSettings`** copies both rotation and location
  constraint settings into a structured clipboard (`{'rotation': ..., 'location': ...}`).
  `poll()` now passes if either constraint exists on the selected pair.
- **`EASYRETARGET_OT_PasteConstraintSettings`** pastes both rotation and location
  settings if present in the clipboard.
- **JSON export** keys renamed: `"constraint"` → `"rotation_constraint"`;
  `"location_constraint"` added. Both are `null` when absent.
- **JSON import** accepts both `"rotation_constraint"` (current) and legacy
  `"constraint"` (pre-0.3.0 files) as the rotation key. Creates both constraints
  and calls `ensure_constraint_order` per pair.
- **Constraint button icon** in the UIList now shows `CONSTRAINT_BONE` if either
  constraint exists on the target bone, `ADD` if neither does.
- **`EASYRETARGET_OT_EditConstraint`** `bl_label` changed to `"Constraint Mapping"`.
  `_created` instance variable renamed to `_rot_created`; `_loc_created` added.
  Snapshot variables extended for location and expanded states.

### Fixed
- **`load_post` migration** — `on_load_post` now calls `_migrate_constraint_names`
  before applying toggle state. Any constraint named `"EasyRetarget"` on a paired
  target bone is silently renamed to `"EasyRetarget_Rotation"`. Safe to run multiple
  times; no constraint properties are modified.

---

## [0.1.31] — 2026-04-06

### Added
- **`original_target_rotation_mode` field** (`StringProperty`, default `''`)
  on `EASYRETARGET_BonePairItem`. Records the target bone's rotation mode at
  the moment the target bone is selected, before any matching changes it.
  Persists until a new target bone is selected for the pair.
- **`_on_target_bone_update` callback** on the `target_bone` `StringProperty`
  in `EASYRETARGET_BonePairItem`. When a target bone is selected, reads its
  current rotation mode and writes it to `original_target_rotation_mode`.
  Falls back gracefully if the bone cannot be resolved.

### Fixed
- **Reset to Default** (`EASYRETARGET_OT_ResetOffsets`) now restores the
  target bone's `rotation_mode` to `original_target_rotation_mode` (the mode
  it had before any matching was applied) and sets `offset_rotation_mode` to
  match. If `original_target_rotation_mode` is unset, behavior is unchanged.
  `original_target_rotation_mode` is not cleared on reset — it persists until
  a new target bone is selected.
- **Clear All** (`EASYRETARGET_OT_ClearAllOffsets`) applies the same
  per-pair rotation mode restoration as Reset to Default. Falls back to the
  source bone's rotation mode if `original_target_rotation_mode` is unset,
  and to `'QUATERNION'` if neither is available.

---

## [0.2.6] — 2026-04-07

### Added
- **JSON Export** (`EASYRETARGET_OT_ExportJSON`) — exports all bone pairs
  and their constraint settings to a `.json` file via Blender's native file
  browser. Default filename is blank. Constraint data (axis mapping, inversion,
  offsets, space) is included per pair only when an EasyRetarget constraint
  exists on the target bone. Pairs without a constraint export with
  `"constraint": null`.
- **JSON Import** (`EASYRETARGET_OT_ImportJSON`) — selects a `.json` file via
  Blender's native file browser, then opens a confirmation dialog with three
  options: Append (add imported pairs to the existing list), Replace (clear
  the list first), or Cancel. Constraints are created on the target bones if
  the source and target rigs are already set and the bones exist. If rigs are
  not set, bone pair names are imported without constraints.
- **`operators_io.py`** — new module containing the export, import, and import
  confirmation operators.
- **Red highlighting in the bone pair list** — source and target bone fields
  turn red when the corresponding rig is not selected or the bone name does not
  exist on the rig. Each field is checked independently.
- Export and Import JSON buttons added side-by-side in the Settings section of
  the N-panel under a "Bone Pairs Data" label.

---

## [0.2.5] — 2026-04-07

### Fixed
- **Bone selection sync was constantly overwriting manual list selection.**
  The `_sync_bone_pair_selection` draw handler now tracks the last active
  bone in a module-level `_last_active_bone` tuple `(bone_name, owner_name)`.
  On each redraw, if the active bone is unchanged from the previous redraw,
  the handler returns immediately without touching `bone_pairs_index`. The
  list is only synced when the active bone actually changes. `_last_active_bone`
  is reset to `(None, None)` on `unregister_handlers()` to avoid stale state
  across addon reloads.

---

## [0.2.4] — 2026-04-07

### Added
- **Copy Constraint Settings** (`EASYRETARGET_OT_CopyConstraintSettings`) —
  copies the selected bone pair's constraint settings (axis mapping, inversion,
  offsets, space) to a module-level clipboard. Greyed out when the selected
  pair has no constraint. Does not persist across Blender restarts.
- **Paste Constraint Settings** (`EASYRETARGET_OT_PasteConstraintSettings`) —
  pastes from the clipboard to the selected bone pair's constraint, creating it
  if it does not exist. Overwrites silently. Greyed out when clipboard is empty
  or no valid pair is selected.
- **Remove constraint column** in the bone pair list — a per-row remove button
  (with confirmation dialog) that is hidden by default. Toggled by a new button
  in the bottom row of the list using the `show_remove_constraint_column`
  `BoolProperty` on `EASYRETARGET_SceneProperties`.
- Copy, Paste, and remove column toggle buttons added to the bottom row of the
  bone pair list alongside the existing +/−/up/down buttons.

### Fixed
- **Cancelling the constraint popup did not restore the constraint** to its
  pre-invoke state. `EditConstraint.invoke()` now snapshots all operator
  property values after reading from the existing constraint.
  `EditConstraint.cancel()` restores the snapshot and calls
  `_write_to_constraint()` to rewrite the original settings.
- **Clicking the constraint button did not select the bone pair** in the list.
  `EditConstraint.invoke()` now sets `props.bone_pairs_index = self.pair_index`
  before opening the dialog.
- **Constraint toggle button order** corrected to All Off, All On, Custom.

### Changed
- **Space selection in the constraint popup** replaced with a two-option toggle
  button row (Local / World) using a single `space: EnumProperty`. Both target
  and owner space are always set together — Local/Local (Add mix mode) or
  World/World (Replace mix mode). Separate target/owner space dropdowns removed.
- **Offset header label** in the popup now reads "Offset (Local)" or
  "Offset (World)" based on the current space selection, clarifying that
  World/World offsets operate in world space.
- **`CreateConstraints`** now defaults to Local/Local space.
- **Remove Constraint** (`EASYRETARGET_OT_RemoveConstraint`) moved from the
  popup to the list row (hidden behind the remove column toggle). Now has a
  confirmation dialog.

---

## [0.2.3] — 2026-04-07

### Added
- **Reset Addon State operator** (`EASYRETARGET_OT_ResetAddonState`) in
  `debug.py`. Unregisters and re-registers all handlers and starts a fresh
  log file. Accessible via a button in the addon preferences panel. Use this
  when reloading the addon mid-session without restarting Blender to clear
  stale handler state from previous versions.

### Fixed
- **`map_from` and `map_to` are now only set when they differ from
  `'ROTATION'`** in `create_or_update_constraint`. Reassigning `map_to`
  resets `mix_mode_rot` back to `'ADD'`, so guarding the assignment prevents
  the mix mode from being overridden on every `check()` call when the popup
  is open.

### Changed
- **Comprehensive debug logging added** throughout `constraint_utils.py`,
  `operators_constraint.py`, and `handlers.py` to diagnose the mix mode and
  bone selection sync issues:
  - `create_or_update_constraint` logs constraint creation vs update,
    `map_from`/`map_to` changes, `mix_mode_rot` before and after assignment,
    and per-axis mapping/inversion/offset values.
  - `EditConstraint._write_to_constraint` logs expected vs actual
    `mix_mode_rot` after each write.
  - `EditConstraint._read_from_constraint` logs recovered mapping, inversion,
    offset, and space settings.
  - `EditConstraint.draw` logs each time it is called and when the Remove
    Constraint button is drawn.
  - `_sync_bone_pair_selection` logs the active bone, its owning rig, whether
    a matching pair is found, and any errors accessing context properties.

---

## [0.2.2] — 2026-04-07

### Added
- **Offset values are now functional** in the constraint settings popup.
  Each axis offset shifts the Map To Min and Max values linearly by the
  specified degree amount, which is equivalent to adding a fixed rotation
  on top of the mapped result across the full ±180° input range. For
  example a +10° X offset produces Map To Min=-170°, Max=190°. Offset is
  ignored for axes mapped to None. `calculate_map_to_min_max` in
  `constraint_utils.py` now accepts an `offset_degrees` parameter, and
  `create_or_update_constraint` accepts `offset_x`, `offset_y`, `offset_z`.
- **`_read_from_constraint`** in `operators_constraint.py` now correctly
  recovers the stored offset from the constraint's `to_min` values:
  `offset = to_min_degrees + 180` for non-inverted axes,
  `offset = to_min_degrees - 180` for inverted axes.

### Fixed
- **Bone selection no longer syncs to the N-panel list.** The
  `depsgraph_update_post` handler approach did not fire on bone selection
  changes since those do not trigger a depsgraph update. Replaced with a
  `SpaceView3D.draw_handler_add` callback using `'POST_PIXEL'` on the
  `'WINDOW'` region, which fires on every viewport redraw. When the active
  pose bone belongs to the source or target rig and a matching pair is
  found, `bone_pairs_index` is updated and all `UI` regions in `VIEW_3D`
  areas are tagged for redraw so the N-panel list updates immediately.
- **`con.map_to = 'ROTATION'` is now set before `con.mix_mode_rot`** in
  `create_or_update_constraint`, ensuring the rotation mix mode property
  is active when it is written.

---

## [0.2.1] — 2026-04-07

### Added
- **Selection sync handler** (`sync_bone_pair_selection` in `handlers.py`).
  A `depsgraph_update_post` handler that reads `bpy.context.active_pose_bone`
  and its owning object via `id_data`. If the owner is the source rig, finds
  the first bone pair whose `source_bone` matches and sets `bone_pairs_index`.
  If the owner is the target rig, matches against `target_bone`. If the owner
  is neither rig, does nothing. Registered at addon load alongside the
  `load_post` handler.
- **Remove Constraint button** at the bottom of the `EditConstraint` popup.
  Removes the EasyRetarget constraint from the target bone immediately without
  confirmation and closes the dialog. Implemented as
  `EASYRETARGET_OT_RemoveConstraint`.
- Handler registration consolidated into `register_handlers()` and
  `unregister_handlers()` in `handlers.py`, covering both `load_post` and
  `depsgraph_update_post` handlers.

### Fixed
- **Popup showed stale values from previous invocations** when opening the
  constraint settings for a bone that did not yet have a constraint. Operator
  properties are now explicitly reset to defaults at the start of `invoke()`
  before reading from an existing constraint.
- **Mix mode now correctly set to REPLACE for World-to-World space** and ADD
  for all other space combinations, in `constraint_utils.py`.

### Changed
- **Offset fields in the constraint popup are now explicitly placeholder UI**
  — they are visible but inert and not written to the constraint. A truly
  additive offset mechanism will be implemented in a future update.
  `calculate_map_to_min_max` no longer accepts or applies an offset parameter.

---

## [0.2.0] — 2026-04-07

### Changed
- **Major architecture overhaul.** The Live Offset depsgraph handler system
  has been replaced with Blender's native Transform constraint. Each paired
  target bone can now have an "EasyRetarget" Transform constraint created on
  it that handles live rotation mapping natively through Blender's own
  constraint evaluation pipeline, with no persistent depsgraph handler
  required.

- **Rotation Mapping constraint** (`constraint_utils.py`): a single
  Transform constraint named "EasyRetarget" is created per paired target
  bone. Settings include per-axis source mapping (X, Y, Z, or None),
  per-axis inversion, per-axis offset (±180°, linear shift), and
  target/owner space (World or Local). Map From range is always ±180°.
  Mix mode is always Add. Inversion and None mapping are encoded into
  the Map To Min/Max values; offsets shift the Map To range linearly.

- **Constraint button** replaces the offset button in each bone pair row.
  Uses `CONSTRAINT_BONE` icon when a constraint exists, `ADD` icon when
  it does not. Opens a popup showing axis mapping, inversion, offset, and
  space settings. Creates the constraint with defaults (X→X, Y→Y, Z→Z,
  no inversion, zero offset) if it does not yet exist. Cancelling after
  creation removes the constraint.

- **Create Constraints button** replaces Match All. Creates or resets the
  EasyRetarget constraint for all populated bone pairs with defaults.
  Confirmation dialog warns that existing settings will be overwritten.

- **Remove All Constraints button** replaces Clear All. Removes the
  EasyRetarget constraint from all paired target bones and resets the
  constraint toggle to Custom.

- **Constraint toggle** (All Off / Custom / All On) replaces the Live
  Offset toggle in the Settings section. All Off disables all EasyRetarget
  constraints on paired bones. All On enables them all. Custom respects
  individual constraint enabled states. Switching away from Custom
  snapshots the current enabled states in `constraint_state_snapshot`
  (persisted in scene data) so they can be restored when returning to
  Custom. Toggling between All Off and All On preserves the existing
  snapshot.

- **`load_post` handler** simplified — now only re-applies the constraint
  toggle state on file load. In Custom mode, restores enabled states from
  `constraint_state_snapshot` to handle files modified without the addon
  installed. The constraint data itself (target, mapping, offsets) persists
  natively in the .blend file.

- **Target bone change warning** — changing the target bone on a pair that
  already has an EasyRetarget constraint now shows a confirmation dialog.
  Confirming removes the constraint from the old bone. Cancelling reverts
  the target bone field. Implemented via `previous_target_bone`
  StringProperty on `EASYRETARGET_BonePairItem` and
  `EASYRETARGET_OT_ConfirmTargetBoneChange` operator.

- **Remove Bone Pair warning** — removing a pair that has an EasyRetarget
  constraint now shows a confirmation dialog before removing both the pair
  and the constraint.

### Added
- `constraint_utils.py` — new module containing `find_retarget_constraint`,
  `remove_retarget_constraint`, `create_or_update_constraint`, and
  `calculate_map_to_min_max` helpers.
- `operators_constraint.py` — new module containing
  `EASYRETARGET_OT_EditConstraint`, `EASYRETARGET_OT_CreateConstraints`,
  `EASYRETARGET_OT_RemoveAllConstraints`, and
  `EASYRETARGET_OT_ConfirmTargetBoneChange`.
- `EASYRETARGET_ConstraintState` PropertyGroup (`bone_name`, `enabled`)
  for the constraint state snapshot.
- `constraint_state_snapshot` CollectionProperty on
  `EASYRETARGET_SceneProperties`.
- `constraint_toggle` EnumProperty on `EASYRETARGET_SceneProperties`.
- `previous_target_bone` StringProperty on `EASYRETARGET_BonePairItem`.

### Removed
- `operators_offset.py` — entirely removed. All offset, matching, and
  Live Offset logic is superseded by the Transform constraint approach.
- Live Offset depsgraph handler (`apply_live_offsets`), pose snapshot
  system, disabled constraints system, and all related properties and
  PropertyGroups (`EASYRETARGET_BonePoseSnapshot`,
  `EASYRETARGET_DisabledConstraint`, `pose_snapshot`,
  `disabled_constraints`, `live_offset`).
- `offset_location`, `offset_rotation`, `offset_scale`,
  `offset_rotation_mode`, `original_target_rotation_mode`,
  `use_local_rotation` from `EASYRETARGET_BonePairItem`.
- Match All, Match Source, Clear All, Reset Offsets, Match Rotation Mode
  operators.
- `utils.py` stripped to `get_bone` and `force_depsgraph_update` — all
  rotation math helpers removed.

---

## [0.1.32] — 2026-04-06

### Added
- **`use_local_rotation` checkbox** (`BoolProperty`, default `False`) on
  `EASYRETARGET_BonePairItem`. When enabled, the Live Offset handler reads
  the source bone's current local rotation each update and writes it directly
  to the target bone in the target bone's rotation mode, with any manual
  rotation offset applied on top. Equivalent to a Copy Rotation constraint
  in Local to Local space. Location and scale offsets apply as normal.
  Displayed as a column in the bone pair list row before the offset button,
  using the `ORIENTATION_LOCAL` icon. Greyed out unless both bones are populated.
- **`use_local_rotation` initialized to `False`** in `AddBonePair` and
  `AutoPopulate`.
- **`get_pose_rotation_as_quat()`** restored to `utils.py` — required by the
  local rotation copy path in `apply_live_offsets`.

### Fixed
- **`apply_live_offsets` was changing the target bone's rotation mode** on every
  depsgraph update, causing silent rotation mode changes when manually editing
  offset values on a bone with a mismatched rotation mode. The handler no longer
  sets `pbone.rotation_mode` at all — rotation mode changes are now exclusively
  the responsibility of the match sequence operators and the Match Source Rotation
  Mode button.
- **Canceling the offset popup did not revert a rotation mode match** performed
  by clicking Match Source Rotation Mode inside the popup. `EditOffsets.invoke()`
  now also snapshots `offset_rotation_mode` and the target bone's current
  `rotation_mode`. `EditOffsets.cancel()` restores both.

### Changed
- **Match All and Match Source skip `use_local_rotation` pairs** entirely during
  the rotation delta calculation in `_run_match_sequence`. Rotation mode matching
  in step 3 also skips these pairs. Location and scale offsets are unaffected.

---

## [0.1.31] — 2026-04-06

### Added
- **`original_target_rotation_mode` field** (`StringProperty`, default `''`)
  on `EASYRETARGET_BonePairItem`. Records the target bone's rotation mode at
  the moment the target bone is selected, before any matching changes it.
  Persists until a new target bone is selected for the pair.
- **`_on_target_bone_update` callback** on the `target_bone` `StringProperty`
  in `EASYRETARGET_BonePairItem`. When a target bone is selected, reads its
  current rotation mode and writes it to `original_target_rotation_mode`.
  Falls back gracefully if the bone cannot be resolved.

### Fixed
- **Reset to Default** (`EASYRETARGET_OT_ResetOffsets`) now restores the
  target bone's `rotation_mode` to `original_target_rotation_mode` (the mode
  it had before any matching was applied) and sets `offset_rotation_mode` to
  match. If `original_target_rotation_mode` is unset, behavior is unchanged.
  `original_target_rotation_mode` is not cleared on reset — it persists until
  a new target bone is selected.
- **Clear All** (`EASYRETARGET_OT_ClearAllOffsets`) applies the same
  per-pair rotation mode restoration as Reset to Default. Falls back to the
  source bone's rotation mode if `original_target_rotation_mode` is unset,
  and to `'QUATERNION'` if neither is available.

---

## [0.1.30] — 2026-04-06

### Changed
- **Match All and Match Source completely rewritten** to use evaluated
  armature-space matrices instead of the Copy Rotation constraint + Visual
  Transform Apply pipeline. The new approach is designed for control bones
  with clean constraint stacks (Child Of only) and correctly accounts for
  Euler rotation order.

  New sequence for both operators:
  1. Snapshot entire target armature pose.
  2. Reset target bone channels to identity/zero (all bones for Match All;
     target bone and ancestors only for Match Source).
  3. Match each paired target bone's rotation mode to its source bone.
  4. Evaluate the depsgraph via `context.evaluated_depsgraph_get()`.
  5. For each paired bone, read the fully evaluated armature-space matrices
     from `source_rig.evaluated_get(depsgraph)` and
     `target_rig.evaluated_get(depsgraph)`.
  6. Compute the local-space rotation delta:
     `delta = tgt_eval_matrix.inverted() @ src_eval_matrix`
     where `tgt_eval_matrix` is the target bone's evaluated matrix at
     zeroed channels (includes Child Of constraint influence), and
     `src_eval_matrix` is the source bone's evaluated matrix.
  7. Decompose delta to the target bone's rotation mode:
     - Quaternion: stored as `(W, X, Y, Z)`.
     - Axis Angle: stored as `(angle, X, Y, Z)`.
     - Euler: decomposed with the correct order and a zero reference euler,
       stored as `(0.0, X, Y, Z)`.
  8. Store `offset_rotation_mode` from the matched rotation mode.
  9. Restore full armature snapshot.
  10. Evaluate depsgraph.

- **Removed** the Copy Rotation constraint pipeline from `_run_match_sequence`:
  no Pose Mode switching, no constraint adding/removing, no `uuid4` tagging,
  no `visual_transform_apply`, no `disable_paired_constraints` calls during
  matching. `disable_paired_constraints` and `restore_disabled_constraints`
  remain in `handlers.py` for use by the Live Offset toggle sequence.
- **Removed** `import uuid` from `operators_offset.py`.
- **Removed** `import BoolProperty` from `operators_offset.py` (no longer used).

---

## [0.1.29] — 2026-04-03

### Added
- **`offset_rotation_mode` field** (`StringProperty`, default `'QUATERNION'`) on
  `EASYRETARGET_BonePairItem`. Stores the rotation mode the offset was calculated
  in so it can be correctly reapplied by the Live Offset handler regardless of
  the target bone's current rotation mode setting.
- **`_on_source_bone_update` callback** on the `source_bone` `StringProperty` in
  `EASYRETARGET_BonePairItem`. When the source bone is changed, reads the new
  source bone's current rotation mode and writes it to `offset_rotation_mode`.
  Falls back to the existing value if the source bone cannot be resolved.
- **Clear All button** in the Bone Pairs section of the N-panel, below Match All.
  - Opens a confirmation dialog with an alert warning.
  - On confirm: resets `offset_location`, `offset_rotation`, and `offset_scale`
    to identity/zero defaults for every bone pair, and sets `offset_rotation_mode`
    from the current source bone's rotation mode (falls back to `'QUATERNION'`
    if unavailable).
  - Pauses the Live Offset handler during the reset and calls `apply_live_offsets`
    directly afterward for an immediate viewport update, consistent with Match All
    and Match Source behavior.
- **`EASYRETARGET_OT_ClearAllOffsets`** operator registered in `__init__.py`.

### Changed
- **`apply_live_offsets`** in `handlers.py` now sets `pbone.rotation_mode` to
  `item.offset_rotation_mode` before writing offset values for each bone pair.
  This ensures the correct rotation mode is active on the target bone during the
  Live Offset session, which is important for baking and for keyed rotation mode
  channels on the target rig.
- **`_run_match_sequence`** in `operators_offset.py` now stores
  `item.offset_rotation_mode` from `tgt_pbone.rotation_mode` after the bake,
  for both Match All and Match Source.
- **`EASYRETARGET_OT_AutoPopulate`** now sets `offset_rotation_mode` from the
  source bone's current rotation mode for each pair where a source bone is found.
  Falls back to `'QUATERNION'` where no source bone match exists.
- **`EASYRETARGET_OT_AddBonePair`** initializes `offset_rotation_mode` to
  `'QUATERNION'`.

---

## [0.1.28] — 2026-04-03

### Fixed
- **Match All and Match Source now pause Live Offset during the match sequence.**
  If Live Offset is active when either operator runs, `unregister_handlers()` is
  called before `_run_match_sequence()` and `register_handlers()` is called
  immediately after. This prevents the depsgraph handler from forcing paired
  target bones back into their offset positions during the sequence, which
  requires those bones to be at rest for correct constraint evaluation. The
  `live_offset` property remains `True` throughout — only the handler
  registration is paused, so no snapshot or constraint state is disturbed.
  `apply_live_offsets()` is called directly after re-registering to apply the
  new offsets immediately.

---

## [0.1.27] — 2026-04-03

### Added
- **`load_post` handler** (`on_load_post` in `handlers.py`) that re-registers
  the depsgraph handler for any scene that has `live_offset` set to `True` after
  a file is loaded. This restores full Live Offset functionality when Blender is
  closed and reopened with Live Offset active. `pose_snapshot` and
  `disabled_constraints` persist in scene data across restarts, so no additional
  restoration is needed on load.
- `register_load_post_handler()` and `unregister_load_post_handler()` in
  `handlers.py` to manage the `load_post` handler lifecycle.

### Fixed
- **`unregister()` in `__init__.py` called the removed `handlers.restore_user_intent()`**
  function, which would raise an `AttributeError` when the add-on was disabled
  while Live Offset was active. `unregister()` now runs the full correct toggle-off
  sequence for each scene with `live_offset` enabled: re-enables disabled
  constraints, restores the pose snapshot, clears both collections, and sets
  `live_offset` to `False`.
- **Version number in `__init__.py` was not updated** when 0.1.26 was packaged.
  Corrected to `(0, 1, 27)`.
- **`offset_rotation` default W value was `0.0`**, which is not a valid identity
  quaternion. Changed to `(1.0, 0.0, 0.0, 0.0)` across `properties.py`,
  `operators_list.py` (Add Bone Pair and Auto Populate), and
  `operators_offset.py` (Reset to Default).
- **`has_non_default_offsets()` treated W=0 as the default** for `offset_rotation`,
  meaning a bone pair with identity rotation `(1, 0, 0, 0)` was incorrectly
  reported as having non-default offsets and processed by the Live Offset handler
  unnecessarily. Updated to treat `(1.0, 0.0, 0.0, 0.0)` as the default.
- **Canceling the Offset popup while Live Offset was enabled** did not immediately
  snap the bone back to its correct offset values — it waited for the next
  depsgraph update. `cancel()` in `EASYRETARGET_OT_EditOffsets` now directly
  calls `handlers.apply_live_offsets()` instead of relying on
  `force_depsgraph_update()`.
- **Clicking Match Source while Live Offset was enabled** did not immediately
  apply the new offset values to the bone — it waited for the next depsgraph
  update. `EASYRETARGET_OT_MatchSourceOffsets.execute()` now directly calls
  `handlers.apply_live_offsets()` after storing the new offset when
  `live_offset` is `True`.

### Changed
- **Match Source reset optimization.** `_run_match_sequence()` in
  `operators_offset.py` now only resets the target bone and its ancestors when
  called from Match Source (`pair_index_to_write` is not `None`), rather than
  resetting all bones on the target armature. Match All continues to reset all
  bones as before.
- **Removed unnecessary `view_layer.update()` at step 3** of `_run_match_sequence`.
  The update after the bone channel reset was a no-op because no constraints had
  been added yet at that point. The single update before `visual_transform_apply`
  (step 5) is sufficient.
- **`load_post` handler registered at add-on load** via `register_load_post_handler()`
  called from `register()` in `__init__.py`, and unregistered at add-on removal
  via `unregister_load_post_handler()`.

### Removed
- Six unused helper functions from `utils.py` that were superseded by the
  constraint-based match sequence introduced in 0.1.22 and were known to produce
  incorrect results: `get_armature_space_rest_rotation`,
  `get_parent_armature_space_rest_rotation`, `get_bone_rest_world_rotation`,
  `get_parent_bone_rest_world_rotation`, `get_parent_bone_posed_world_rotation`,
  and `get_pose_rotation_as_quat`.

---

## [0.1.26] — 2026-04-01

### Fixed
- **Live Offset now disables all bone constraints before writing offset values**
  and re-enables them immediately after. Prevents constraints from fighting or
  overriding the offset values written to the pose channels each handler update.

---

## [0.1.25] — 2026-04-01

### Fixed
- **Live Offset now properly disables constraints on paired target bones.**
  - On Live Offset toggle-on: all currently-enabled constraints on paired
    target bones are disabled and recorded in a new persistent
    `disabled_constraints` CollectionProperty on scene properties.
  - The handler writes offset values to clean channels with no constraints
    present to fight or override them.
  - On Live Offset toggle-off: constraints recorded in `disabled_constraints`
    are re-enabled before restoring the pose snapshot, then the collection
    is cleared.
  - Because `disabled_constraints` is a scene `CollectionProperty`, it
    persists across Blender restarts — if Live Offset is on when Blender
    closes and reopens, the addon still knows which constraints to restore
    when Live Offset is eventually turned off.

### Added
- `EASYRETARGET_DisabledConstraint` PropertyGroup in `properties.py`
  storing `bone_name` and `constraint_name`.
- `disabled_constraints` CollectionProperty on `EASYRETARGET_SceneProperties`.
- `disable_paired_constraints()` and `restore_disabled_constraints()` helpers
  in `handlers.py`.

---

## [0.1.24] — 2026-04-01

### Fixed
- `AttributeError: module 'easy_retarget.handlers' has no attribute 'pre_snapshot'`
  when clicking Auto Populate. Removed all stale references to the old
  `handlers.pre_snapshot` dict and `user_intent` fields from `operators_list.py`
  and `utils.py` that were left over from before the 0.1.22 refactor:
  - `handlers.pre_snapshot.clear()` and `handlers.pre_snapshot.pop()` removed
    from `operators_list.py`.
  - `item.user_intent_*` initializations removed from `operators_list.py`.
  - `user_intent_is_initialized()` and `init_user_intent_from_bone()` helper
    functions removed from `utils.py`.

---

## [0.1.23] — 2026-04-01

### Fixed
- `RuntimeError: name 'EASYRETARGET_BonePoseSnapshot' is not defined` on addon
  install. `EASYRETARGET_BonePoseSnapshot` was present in the `classes` tuple in
  `__init__.py` but missing from the `from .properties import ...` statement,
  so it was never imported into the module namespace before registration.

---

## [0.1.22] — 2026-04-01

### Changed
- **Live Offset simplified — user intent removed entirely.**
  - Handler now writes offset values directly to pose channels every update.
  - No change detection, no pre-snapshot, no intent tracking.
  - On Live Offset toggle-on: snapshots the entire target armature pose to
    `pose_snapshot` (a new `CollectionProperty` on scene properties), then
    registers the handler.
  - On Live Offset toggle-off: unregisters handler, restores the full pose
    from `pose_snapshot`, clears the snapshot.

- **Match All and Match Source now share a single `_run_match_sequence` helper**
  that performs the full correct sequence:
  1. Snapshot entire target armature (all bones, not just paired).
  2. Reset ALL bone channels to identity/zero.
  3. Force update.
  4. Disable all currently-enabled constraints on paired target bones; record which.
  5. Add `COPY_ROTATION` constraints with a unique `uuid4` name tag.
  6. Force update.
  7. Apply visual transform via `VIEW_3D` context override.
  8. Read baked channels; write offsets for all pairs (Match All) or one pair (Match Source).
  9. Clear paired bone channels.
  10. Remove only constraints matching the unique name tag.
  11. Re-enable only the constraints disabled in step 4.
  12. Restore full armature snapshot from step 1.
  13. Force update.

- **Match Source now uses the same sequence as Match All**, ensuring correct
  results for non-root bones regardless of the current pose state of parent bones.

### Added
- `EASYRETARGET_BonePoseSnapshot` PropertyGroup in `properties.py` storing
  per-bone: `bone_name`, `location`, `rotation_quaternion`, `rotation_euler`,
  `rotation_axis_angle`, `scale`, `rotation_mode`.
- `pose_snapshot` CollectionProperty on `EASYRETARGET_SceneProperties`.
- `snapshot_pose()` and `restore_pose_snapshot()` helpers in `handlers.py`.

### Removed
- `user_intent_location`, `user_intent_rotation`, `user_intent_scale` fields
  from `EASYRETARGET_BonePairItem`.
- All user intent tracking, change detection, `_last_written`, `_intent_written`,
  `pre_snapshot`, `restore_user_intent`, and `clear_intent_written` from `handlers.py`.

---

## [0.1.21] — 2026-04-01

### Changed
- Enhanced diagnostic logging in `apply_live_offsets` change detection:
  - Logs `pre_rot_q` and `last_rot_q` in both quaternion and native rotation
    mode (Euler XYZ values when in Euler mode) for easier channel-level diagnosis.
  - Logs `pre_loc`, `last_loc`, `pre_scale`, `last_scale` with 5 decimal places.
  - Detects and logs whether the pre-snapshot rotation is near identity
    (`pre_near_identity`) — the expected signature of an Alt+R reset.
  - Logs back-calculated intent quaternion before storing, labelled with whether
    it took the identity path or the back-calc path.
  - Logs final stored intent rotation after update.

---

## [0.1.20] — 2026-04-01

### Added
- **Debug Info section in Offset popup** — visible only when Debug Logging is
  enabled in addon preferences. Shows the currently stored `user_intent_location`,
  `user_intent_rotation`, and `user_intent_scale` values for the bone pair.

### Fixed
- **Single-channel drag changing all rotation values** and **Alt+R not reinjecting
  offset**: change detection now compares the pre-snapshot against `_last_written`
  (what the handler actually wrote last frame) rather than recomputing
  `intent + offset` fresh each time.
  - Added `_last_written` dict to `handlers.py`. After each successful write, the
    handler caches the exact values written (`location`, `rotation_quat`, `scale`).
  - On the next update, change detection compares the pre-snapshot against
    `_last_written`. If different, the user changed the channels — back-calculate
    new intent from pre-snapshot by removing the offset.
  - `clear_intent_written()` now also clears `_last_written`.

---

## [0.1.19] — 2026-04-01

### Added
- **User intent tracking restored to Live Offset handler.**
  - On first handler run for a bone (uninitialized intent), intent is set to
    identity/zero — not read from bone channels, which may be dirty.
  - Change detection compares pre-snapshot against `intent + offset`. If different,
    back-calculates new intent from the pre-snapshot by removing the offset, stores
    it persistently, then writes `intent + offset` to channels.
  - Toggle-off restores stored user intent to channels (offset-free).
  - `_intent_written` set gates change detection — only runs after the first
    successful write, preventing stale reads on the first handler update.

### Changed
- **Match All** now initializes `user_intent_location`, `user_intent_rotation`,
  and `user_intent_scale` to identity/zero for all processed pairs after storing
  offsets, then calls `handlers.clear_intent_written()` so the handler starts fresh.
- **Match Source** likewise initializes user intent to identity and calls
  `handlers.clear_intent_written()` after storing the offset.
- Handler user intent initialization changed from reading bone channels to setting
  identity/zero directly — eliminates dirty channel reads on first update.

---

## [0.1.18] — 2026-04-01

### Changed
- **Match All reworked to stay in POSE position throughout** — no REST switching.
  - Added confirmation dialog warning that paired target bone pose channels will
    be reset and any unkeyed adjustments will be lost.
  - Sequence: match rotation modes → reset all paired target bone channels to
    identity/zero → add Copy Rotation constraints → enter Pose Mode → select all →
    update → apply visual transform via context override → read baked channels →
    store as offsets → clear channels → remove constraints → return to Object Mode.
  - Source rotation bone channel reset: location `(0,0,0)`, quaternion `(1,0,0,0)`,
    euler `(0,0,0)`, axis-angle `(0,0,1,0)`, scale `(1,1,1)`.

---

## [0.1.17] — 2026-04-01

### Fixed
- Match All: replaced direct `pbone.matrix` reading with a proper context
  override for `bpy.ops.pose.visual_transform_apply()`.
  - Switches target rig to Pose Mode, selects all bones.
  - Finds a `VIEW_3D` area and its `WINDOW` region in the current screen.
  - Calls `visual_transform_apply` inside `context.temp_override()` with the
    correct area, region, and active object.
  - Falls back with a log warning if no `VIEW_3D` area is available.
  - Reads baked pose channel values after apply, stores as offsets, clears channels.
  - Returns to Object Mode and restores active object after completion.

---

## [0.1.16] — 2026-04-01

### Fixed
- Match All: replaced `bpy.ops.pose.visual_transform_apply()` with direct
  reading of `pbone.matrix` after constraint evaluation.
  - `visual_transform_apply` was silently failing due to missing 3D viewport
    context, resulting in identity rotations being stored as offsets.
  - After `context.view_layer.update()`, `pbone.matrix` already contains the
    constraint-evaluated armature-space matrix. The local rotation is extracted
    by factoring out the parent bone's matrix:
    `tgt_mat_local = inv(tgt_pbone.parent.matrix) @ tgt_pbone.matrix`
  - Removed mode switching and active object manipulation — no longer needed.

---

## [0.1.15] — 2026-04-01

### Fixed
- `AttributeError: 'Bone' object has no attribute 'select'` when clicking Match All.
  `tgt_pbone.bone.select` is not a valid settable attribute in Blender 5.0.
  Replaced per-bone selection with `bpy.ops.pose.select_all(action='SELECT')`
  since all target bones with constraints need visual transform applied anyway.

---

## [0.1.14] — 2026-04-01

### Changed
- **Match All completely rewritten** to use Blender's Copy Rotation constraint
  system and Visual Transform Apply instead of manual rotation math.
  - Sets both rigs to `REST` position and forces a view layer update.
  - Matches target bone rotation mode to source bone rotation mode for each pair.
  - Adds a temporary `COPY_ROTATION` constraint (World/World space, Replace mix)
    to each target bone targeting its paired source bone.
  - Forces another view layer update so constraints are evaluated.
  - Enters Pose Mode on the target rig, selects the paired bones, and calls
    `bpy.ops.pose.visual_transform_apply()` to bake constraint results into
    pose channels.
  - Reads the baked pose channel values and stores them as `offset_rotation`
    on each bone pair.
  - Clears pose channels back to zero/identity.
  - Removes all temporary constraints.
  - Restores both rigs to their original `pose_position`.
  - No manual quaternion math — Blender handles all rotation and parent chain
    resolution through its own constraint evaluation pipeline.

---

## [0.1.13] — 2026-04-01

### Changed
- **Match All completely rewritten** to use Blender's own evaluated rest pose
  matrices instead of manual world rotation reconstruction.
  - Temporarily sets both source and target armatures to `REST` position.
  - Calls `context.view_layer.update()` to force Blender to evaluate all
    `pbone.matrix` values in rest pose — all parent chain math handled natively.
  - Computes rotation delta as `(inv(tgt_pbone.matrix) @ src_pbone.matrix).to_quaternion()`
    directly in armature space. No manual quaternion chaining, no rest world
    rotation helpers, no hemisphere normalization hacks.
  - Restores both armatures to their original `pose_position` after calculation.
  - Processes pairs in parent-first order (unchanged).
  - No user-visible change — rigs are restored before the function returns.

---

## [0.1.12] — 2026-04-01

### Fixed
- **Match Source / Match All now work entirely in rest-pose world space**,
  eliminating the mixing of rest and posed spaces that caused incorrect
  results for chained bones.
  - Root cause: `tgt_bone_local_rest = inv(tgt_parent_posed_rot) @ tgt_rest_world_rot`
    was mixing a posed parent rotation with a rest bone rotation, producing a
    nonsensical local rest for child bones (large negative-W quaternions).
  - New approach: both `tgt_bone_local` and `src_bone_in_tgt_parent` are expressed
    in the same space — the target parent's **rest** world rotation. The delta
    `inv(tgt_bone_local) @ src_bone_in_tgt_parent` is a clean rest-to-rest
    comparison with no posed matrices involved.
  - Added hemisphere normalization: if the dot product of `tgt_bone_local` and
    `src_bone_in_tgt_parent` is negative, one is negated before multiplication
    to avoid sign-flip artifacts.
  - `_compute_match_rotation` now accepts `src_parent_world_rot` and
    `tgt_parent_world_rot` parameters and returns
    `(delta_rot, this_src_world_rot, this_tgt_world_rot)`.
  - Match All caches computed world rotations for both source and target bones
    and passes them down the chain, ensuring correct parent spaces at each depth.

---

## [0.1.11] — 2026-04-01

### Fixed
- **Match All now correctly chains parent world rotations** without relying on
  stale pose matrices.
  - Root cause: `pbone.parent.matrix` is only updated after the depsgraph
    re-evaluates. When Match All processes Bone1 and then Bone2 in the same
    operator call, Bone1's offset has been written to `item.offset_rotation`
    but not yet evaluated into the pose — so `pbone.parent.matrix` for Bone2
    still reflects Bone1's pre-offset state.
  - Fix: `_compute_match_rotation` now also returns `this_bone_world_rot` —
    the bone's computed world rotation after its delta is applied, derived
    analytically as `parent_world_rot @ local_rest @ delta`.
  - `EASYRETARGET_OT_MatchAllOffsets` maintains a `computed_world_rots` dict
    keyed by bone name. After each bone is processed, its computed world rotation
    is cached. Children look up their parent's cached rotation instead of reading
    the stale pose matrix, ensuring correct chained results.
  - Single Match Source calls are unaffected — they continue to use the live
    pose matrix fallback which is correct when only one bone is being processed.

---

## [0.1.10] — 2026-04-01

### Fixed
- **Match Source / Match All now correctly handle chained bones** (e.g. Bone → Bone1 → Bone2).
  - Root cause: `tgt_parent_world_rot` was using the parent's **rest** world rotation.
    For Bone2, this meant using Bone1's rest orientation — but at apply time, Bone1
    has already been rotated by its offset, so Bone2's offset was computed in the
    wrong parent space.
  - Fix: replaced `get_parent_bone_rest_world_rotation` with a new
    `get_parent_bone_posed_world_rotation` helper in `utils.py` that reads
    `pbone.parent.matrix` (the evaluated pose matrix) combined with the armature's
    world rotation. This reflects the parent's actual orientation after its own
    offset has been applied.
  - `_compute_match_rotation` updated to use `tgt_parent_posed_rot` throughout.
  - `EASYRETARGET_OT_MatchSourceOffsets` now delegates its rotation delta to
    `_compute_match_rotation` for consistency.
  - Location offset calculation in Match Source also updated to use posed parent
    rotation.

---

## [0.1.9] — 2026-04-01

### Added
- **Match All button** in the Bone Pairs section, below Auto Populate.
  - Applies the Match Source rotation calculation to all populated bone pairs
    in a single operation.
  - Processes pairs in parent-first order (sorted by hierarchy depth) to ensure
    parent rotations are resolved before children.
  - Rotation only — does not affect location or scale offsets.
  - Does not reinitialize user intent, preserving any manual channel adjustments.
  - Clears `pre_snapshot` so the handler applies new offsets on the next update.
  - Reports count of updated pairs on completion.
- **Debug logging added to Match Source operator** (`EASYRETARGET_OT_MatchSourceOffsets`
  and `_compute_match_rotation` shared helper):
  - Logs `src_rest_world_rot`, `tgt_rest_world_rot`, `tgt_parent_world_rot`,
    `tgt_bone_local_rest`, `src_in_tgt_parent`, and `delta_rot` for each pair.

### Changed
- Match Source and Match All share a `_compute_match_rotation` module-level
  helper function to avoid duplicating the rotation delta logic.

---

## [0.1.8] — 2026-04-01

### Fixed
- **Match Source rotation delta corrected for parented bones.**
  - `tgt_bone_own_rest_rot` was previously derived from `bone.matrix_local.to_quaternion()`
    directly. For parented bones, `matrix_local` is relative to the parent's tail
    position which contaminates the rotation extraction, causing incorrect results
    for Bone2 and deeper bones.
  - `tgt_bone_local_rest` is now derived from world rotations:
    `inv(tgt_parent_world_rot) @ tgt_bone_world_rot`. This correctly expresses the
    bone's local rest orientation in its parent's space for both root and parented
    bones, with no bone-length contamination.

---

## [0.1.7] — 2026-04-01

### Changed
- **Debug logging enabled by default** for testing (to be reverted before 1.0 release).
- **Default log directory** set to `C:\Users\ThatCasual\OneDrive\Projects\WithClaude\EasyRetarget\logs\` (to be cleared before 1.0 release).

---

## [0.1.6] — 2026-04-01

### Fixed
- **Match Source rotation delta corrected** to account for the target bone's
  own inherent rest orientation.
  - Even freshly created Blender bones have a non-identity `matrix_local`
    because bones point along the Y axis by default. The previous approach
    stored the full world rotation as the offset, treating the target bone's
    local rest as identity — which is incorrect.
  - New formula: `inv(tgt_bone_own_rest_rot) @ inv(tgt_parent_world_rot) @ src_world_rot`
    where `tgt_bone_own_rest_rot` is the single bone's `matrix_local` rotation
    (no parent chain) and corrects for the bone's inherent rest orientation.
  - Identical bones now produce a zero offset. Bones with different orientations
    produce the correct additive delta regardless of hierarchy depth.

---

## [0.1.5] — 2026-04-01

### Fixed
- **Match Source rotation calculation simplified and corrected.**
  - Previous approach attempted to compute a delta between source and target
    world-space rest rotations, which was overcomplicated and incorrect.
  - New approach mirrors Blender's Copy Rotation constraint: take the source
    bone's world-space rest rotation and express it directly in the target bone's
    parent space. Since the offset is applied additively on top of the target
    bone's rest pose (which is identity in local space), this expressed rotation
    IS the offset — no delta computation needed.
  - Identical bones now correctly produce a zero offset (identity quaternion).
  - Bones with different orientations now correctly produce the local rotation
    needed to match the source regardless of hierarchy depth.

---

## [0.1.4] — 2026-04-01

### Fixed
- **Match Source rotation delta now computed in world space** rather than
  accumulated armature space, completely bypassing the manual parent chain
  reconstruction that was producing incorrect results.
  - New `get_bone_rest_world_rotation(rig, bone_name)` helper in `utils.py`
    returns the rest pose world-space rotation of a bone as a Quaternion by
    combining the armature object's world rotation with the bone's rotation
    accumulated up the parent chain — letting Blender's own transform stack
    handle hierarchy naturally.
  - New `get_parent_bone_rest_world_rotation(rig, bone_name)` returns the
    parent bone's rest world rotation, or the armature world rotation if
    the bone has no parent.
  - `EASYRETARGET_OT_MatchSourceOffsets` updated to compute the rotation
    delta in world space (`inv(tgt_world_rot) @ src_world_rot`) then express
    it in the target bone's local space by factoring out the target parent's
    world rotation.
  - Location and scale offset calculations updated consistently.
- Removed `get_armature_space_rest_rotation` and
  `get_parent_armature_space_rest_rotation` from `utils.py` as they are
  superseded by the world-space helpers.

---

## [0.1.3] — 2026-03-31

### Fixed
- **Match Source producing incorrect offsets** due to bone-length translation
  contaminating rotation extraction during matrix decomposition.
  - `get_armature_space_rest_matrix` and `get_parent_armature_space_rest_matrix`
    replaced in `utils.py` with `get_armature_space_rest_rotation` and
    `get_parent_armature_space_rest_rotation`, which accumulate only the rotation
    component of each bone's `matrix_local` up the parent chain (stripping
    translation entirely).
  - `EASYRETARGET_OT_MatchSourceOffsets` updated to use the new rotation-only
    helpers. The delta is now computed purely in quaternion space, eliminating
    the spurious non-zero offsets that appeared on identical or unrotated bones.
  - Location offset calculation updated to use `head_local` bone positions
    expressed in target parent rotation space.
  - Scale offset calculation updated to use bone length ratio as a proxy for
    scale difference.

---

## [0.1.2] — 2026-03-31

### Fixed
- Child bones in a hierarchy were having their written pose channel values
  overridden by Blender's pose re-evaluation after the parent bone was written
  in the same depsgraph update. The handler now processes bone pairs in
  **parent-first order** (sorted by hierarchy depth) so all parent writes are
  resolved before child bones are written within the same update cycle.
- `restore_user_intent` also updated to use parent-first ordering for consistency.

---

## [0.1.1] — 2026-03-31

### Added
- **Debug logging system** (`debug.py`).
  - New `EASYRETARGET_AddonPreferences` class adds an EasyRetarget entry in
    Blender's Add-on Preferences panel.
  - **Debug Logging** checkbox (off by default).
  - **Log Directory** path field (defaults to Blender's temp directory when blank).
  - Log filenames include the session start timestamp:
    `easy_retarget_YYYY-MM-DD_HH-MM-SS.log`. Each Blender session generates a
    new file; old logs accumulate in the chosen directory.
  - `log()` and `log_section()` utility functions used throughout `handlers.py`
    to record per-bone, per-update state at all key decision points.
  - Current log file path displayed in the preferences panel when debug is enabled.

### Changed
- **Live Offset handler intent initialization fix.**
  - Added `_intent_written` set in `handlers.py` to track which bones have had
    at least one successful write this session.
  - Change detection is now skipped until after the first write, preventing the
    handler from reading dirty (already-offset) bone channels as the new user
    intent on the very first update after Match Source or a fresh enable.
  - `clear_intent_written()` resets both `_intent_written` and `pre_snapshot`,
    called on Live Offset toggle and rig picker changes.
- `properties.py` updated to call `handlers.clear_intent_written()` on Live
  Offset toggle and rig picker changes.

---

## [0.1.0] — 2026-03-31

### Added
- Multi-file package structure. The add-on is now a proper Blender package
  installable as a `.zip` file, split into the following modules:
  - `__init__.py` — bl_info, class registration, unregistration.
  - `properties.py` — `EASYRETARGET_BonePairItem`, `EASYRETARGET_SceneProperties`,
    search callbacks, and property update callbacks.
  - `handlers.py` — `capture_pre_snapshot`, `apply_live_offsets`,
    `restore_user_intent`, handler registration/unregistration, and the
    `pre_snapshot` runtime dict.
  - `utils.py` — all shared helper functions.
  - `operators_list.py` — Add, Remove, Move, AutoPopulate operators.
  - `operators_offset.py` — EditOffsets, MatchSourceOffsets, MatchRotationMode,
    ResetOffsets operators.
  - `op_bake.py` — Bake operator (placeholder).
  - `ui.py` — `EASYRETARGET_UL_BonePairs`, `EASYRETARGET_PT_MainPanel`.

### Changed
- **Live Offset now defaults to off.** Users enable it explicitly once rigs
  and bone pairs are configured.
- Handlers are no longer registered at add-on load. They are registered on
  demand when Live Offset is toggled on, and unregistered when toggled off
  or the add-on is unregistered.

### Fixed
- Match Source offsets not being applied to pose channels after calculation:
  the `apply_live_offsets` handler now unconditionally writes `user_intent +
  offset` to channels when offsets are non-default, even when `pre_snapshot`
  was just cleared. Previously clearing the snapshot caused the write to be
  skipped on the next update.

---

## [0.0.10] — 2026-03-31

### Changed
- **Live Offset handler redesigned with persistent user intent storage.**
  - Each `EASYRETARGET_BonePairItem` now stores three hidden `FloatVectorProperty`
    fields: `user_intent_location`, `user_intent_rotation` (W,X,Y,Z quaternion),
    and `user_intent_scale`. These persist with the scene and represent what the
    bone's channels would be with Live Offset disabled.
  - `user_intent_scale` uses `(0,0,0)` as a sentinel for "uninitialized." On first
    handler run for a bone, intent is initialized from the bone's current channels.
  - Added `depsgraph_update_pre` handler (`_capture_pre_snapshot`) that reads
    current pose channel values before the post handler writes anything, giving a
    clean read of whatever is in the channels at that moment.
  - `depsgraph_update_post` handler (`_apply_live_offsets`) compares the
    pre-snapshot against stored user intent + offset. If they differ, an external
    change occurred — the new intent is back-calculated by removing the offset from
    the pre-snapshot, stored persistently, then intent + offset is written back.
  - Toggle-off restores stored user intent values directly to pose channels.
  - Toggle-on re-initializes intent from current bone state before enabling.
  - Module-level `_pre_snapshot` dict holds only the single-frame read; no
    long-lived stale state that could persist across add-on reloads.
- `_pre_snapshot` cleared on rig changes, Auto Populate, Match Source, Match
  Rotation Mode, Reset Offsets, and pair removal.
- `unregister()` now wraps intent restoration in a try/except to avoid errors
  during partial unregistration.

### Fixed
- Wrong transforms after add-on reload: user intent is now stored in scene
  properties rather than a module-level cache, so reloading the add-on mid-session
  no longer poisons the initial state with stale cached values.
- Offset not reinjected after manual pose channel changes: the pre/post handler
  pair correctly detects external changes and updates user intent before
  reapplying the offset.

---

## [0.0.9] — 2026-03-31

### Changed
- **Live Offset handler reworked with pre-offset snapshot strategy.**
  - Replaced the applied-offset cache with a `_pre_offset_cache` that stores each
    target bone's pose channel values as the user last intended them (before offset).
  - On every depsgraph update the handler compares current channel values against
    what it expects (snapshot + offset). If they differ, the user changed the pose
    directly — the handler back-calculates their new intended base value, updates
    the snapshot, then re-applies the offset on top. This means resetting a bone
    to rest pose (0, 0, 0) in pose mode will correctly result in rest + offset
    in the viewport without requiring Live Offset to be toggled.
  - Toggle-off now restores the cached pre-offset user values to the pose channels
    rather than subtracting the offset from current values, making it reliable
    regardless of how the channels were last changed.
  - Cache is cleared on rig picker changes, Auto Populate, and when individual
    pairs are removed, ensuring stale state never persists.
- **Match Source Offsets delta now computed in target bone local space.**
  - Previously the delta was computed purely in armature space, which did not
    account for parent chain rotations on bones deeper in the hierarchy.
  - The delta is now expressed relative to the target bone's own local space by
    factoring out the target parent's armature-space rest matrix, producing correct
    offsets for bones at any depth in the hierarchy.
- Cache is also cleared in `EASYRETARGET_OT_MatchRotationMode` and
  `EASYRETARGET_OT_ResetOffsets` so the handler re-evaluates cleanly after those
  operations.

---

## [0.0.9] — 2026-03-31

### Fixed
- Live Offset handler now correctly absorbs manual pose edits made in pose mode.
  Previously, editing a bone's channels directly while Live Offset was active would
  corrupt the offset calculation because the cache held stale "what was applied last
  time" data. The handler now reverses the previous offset from the current channel
  values on every update to recover the user's clean intended value, then re-applies
  the offset on top of that — so resetting a bone to rest (0,0,0) immediately
  re-applies the offset as expected without requiring a Live Offset toggle cycle.
- `Match Source` delta calculation now correctly re-expresses the armature-space
  delta in the target bone's local (parent) space by sandwiching the delta through
  the inverse of the target parent's armature-space rest matrix. Previously, child
  bones further down the hierarchy received incorrect offsets because the parent
  chain's rotation contribution was not factored out of the delta.

### Changed
- Live Offset cache renamed from `_applied_cache` to `_pre_offset_cache` and
  restructured to store the applied offset components rather than a snapshot of
  pre-offset values, clarifying the intent of the cache.
- `_read_pose_channels()` and `_write_pose_channels()` helpers extracted to
  centralize pose channel I/O and normalize all rotations to/from Quaternion
  internally.
- `_get_parent_armature_space_rest_matrix()` helper added to support correct
  local-space delta calculation in Match Source.

---

## [0.0.8] — 2026-03-31

### Changed
- **Live Offset handler completely reworked.** No longer writes to
  `target_pbone.matrix`. Instead reads and writes pose channel values directly:
  - `target_pbone.location` — offset added additively as a `Vector`.
  - `target_pbone.rotation_euler` / `rotation_quaternion` / `rotation_axis_angle`
    — offset applied via quaternion multiplication onto the current pose rotation,
    written back in the bone's active rotation mode.
  - `target_pbone.scale` — offset applied multiplicatively component-wise.
- Applied offset values are stored in a module-level `_applied_cache` dict keyed
  by `(target_rig_name, bone_name)`.
- On each handler invocation, the previously cached offset is subtracted before
  the current offset is re-applied, preventing accumulation across updates.
- Toggling Live Offset off now subtracts the cached offset from each affected bone's
  pose channels to restore their original values, rather than resetting to rest pose.
- Stale cache entries (bone pairs that have been removed) are cleaned up at the
  start of each handler invocation.
- `unregister()` now removes all applied offsets from all scenes before
  unregistering classes.

---

## [0.0.7] — 2026-03-31

### Fixed
- Live Offset handler now correctly computes the target bone's true armature-space
  rest matrix by accumulating `matrix_local` up through the full parent chain via
  the new `_get_armature_space_rest_matrix()` helper. Previously, `bone.matrix_local`
  was used directly, which is only parent-relative and caused bones to snap to an
  incorrect position as soon as any offset value was adjusted.
- `_on_live_offset_update()` now uses `_get_armature_space_rest_matrix()` when
  restoring bones to rest pose on Live Offset toggle-off, consistent with the
  corrected handler behavior.
- `EASYRETARGET_OT_MatchSourceOffsets` updated to use
  `_get_armature_space_rest_matrix()` for both source and target rest pose matrices,
  ensuring the calculated delta is correct for bones at any depth in the hierarchy.

---

## [0.0.6] — 2026-03-31

### Fixed
- Live Offset handler now skips bone pairs where all offset values are at their
  defaults (location 0, rotation 0, scale 1) via an early-out check using
  `_has_non_default_offsets()`. Previously the handler was constructing and applying
  a combined matrix to every target bone regardless of offset values, causing
  unintended pose changes even with no offsets set.

---

## [0.0.5] — 2026-03-31

### Added
- **Live Offset** checkbox in the Settings section (default: on).
  - When enabled, a `depsgraph_update_post` handler applies rest pose + additive
    location/rotation offset + multiplicative scale offset to each configured target
    bone on every depsgraph update.
  - Handler is registered on add-on load and when Live Offset is toggled on;
    unregistered when toggled off or the add-on is unregistered.
  - Toggling off restores all target rig bones to their unmodified rest pose.
  - `update` callbacks on all three `FloatVectorProperty` offset fields call
    `_force_depsgraph_update()` on every keystroke or drag for immediate viewport
    feedback.
  - `update` callbacks on `source_rig` and `target_rig` force an immediate
    depsgraph update when either rig picker changes.
- **Match Source** button in the Offset popup (above Reset to Default).
  - Opens a dialog with checkboxes for Location (off), Rotation (on), and Scale (off).
  - On confirm, calculates the delta between source and target bone rest pose matrices
    via `mathutils.Matrix.decompose()` and writes the result to the offset fields for
    each checked channel.
  - Rotation result is expressed in the target bone's current rotation mode.

### Fixed
- Cancel button on the Offset popup now correctly discards changes. Offset values are
  snapshotted in `invoke()` and restored via `cancel()` when the user dismisses the
  popup with Cancel.

### Changed
- **Live Offset** setting added to the Settings expandable section above
  Bake Keyed Frames Only.
- Handler registered at add-on load in `register()` and cleanly removed in
  `unregister()`.

---

## [0.0.4] — 2026-03-31

### Added
- **Offset Editor popup** (`EASYRETARGET_OT_EditOffsets`) accessible via a button on each bone
  pair row.
  - **Location** section: X, Y, Z float fields.
  - **Rotation** section: fields adapt to the target bone's rotation mode.
    - Euler (any order): X, Y, Z.
    - Quaternion: W, X, Y, Z.
    - Axis Angle: Angle, X, Y, Z.
  - **Scale** section: X, Y, Z float fields.
  - **Rotation Mode Mismatch Warning**: displayed when source and target bone rotation modes
    differ; includes a "Match Source Rotation Mode" button.
  - **Reset to Default** button at the bottom of the popup zeroes all offset values.
- **Match Rotation Mode operator** (`EASYRETARGET_OT_MatchRotationMode`): sets the target
  bone's rotation mode to match the source and converts stored rotation offset values
  mathematically via `mathutils`.
- **Reset Offsets operator** (`EASYRETARGET_OT_ResetOffsets`): resets all offset values on
  a bone pair to defaults (location 0, rotation 0, scale 1).
- Offset button on each bone pair row uses `DECORATE_KEYFRAME` icon when any offset is
  non-default, and `DECORATE_ANIMATE` icon otherwise.
- Offset button is greyed out unless both Source Bone and Target Bone are populated.

### Changed
- Single `offset` float field on `EASYRETARGET_BonePairItem` replaced with three
  `FloatVectorProperty` fields: `offset_location` (size 3), `offset_rotation` (size 4,
  W/X/Y/Z), and `offset_scale` (size 3).
- Auto Populate warning text now displays in an `alert` box with increased `scale_y` for
  a larger, red appearance.

### Removed
- Single `offset` FloatProperty removed from `EASYRETARGET_BonePairItem`.

---

## [0.0.3] — 2026-03-31

### Fixed
- Search popup returning no results for Source Bone and Target Bone fields: replaced
  `invoke_search_popup()` operator approach with `StringProperty` `search` keyword callback,
  which is the stable Blender 5.0 API path for inline searchable string fields.
- N-panel not refreshing after Auto Populate, Add, Remove, and Move operations: added
  `context.area.tag_redraw()` to all relevant operator `execute()` methods.

### Changed
- Bone search callbacks (`_source_bone_search`, `_target_bone_search`) moved to module-level
  functions and registered directly on the `StringProperty` definitions in `EASYRETARGET_BonePairItem`.
- `EASYRETARGET_OT_SearchSourceBone` and `EASYRETARGET_OT_SearchTargetBone` operators removed;
  bone fields now use `layout.prop()` directly, relying on the `search` callback for popup behavior.
- Search results are case-insensitive substring matches and sorted alphabetically via `search_options={'SORT'}`.

---

## [0.0.2] — 2026-03-31

### Changed
- Source Bone and Target Bone fields in each bone pair list entry replaced with `StringProperty`-backed
  searchable picker operators (`invoke_search_popup()`), matching the native Blender bone constraint
  UI behavior.
- Bone fields display the currently stored bone name inline in the list row, or "-- Select Bone --"
  if no bone has been selected yet.
- Bone name filtering in the search popup is case-insensitive substring matching.

### Removed
- `EnumProperty` bone selectors removed from `EASYRETARGET_BonePairItem` in favor of `StringProperty`.

---

## [0.0.1] — 2026-03-31

### Added
- **Auto Populate** button at the top of the Bone Pairs section.
  - Opens a confirmation dialog before clearing and rebuilding the list.
  - **Only Populate Matches** checkbox in the dialog (transient operator property, default: checked).
    - When checked: only adds entries where a matching bone name exists on the target rig.
    - When unchecked: adds an entry for every source rig bone; leaves Target Bone blank where no match is found.
  - Reports a warning if Source Rig or Target Rig is not set.
  - Reports a completion message with the count of entries added.

### Changed
- **+ button** now adds a single blank entry with no auto-match attempt.
- **Bake Keyed Frames Only** now defaults to `True`.
- Python filename convention updated to include version number (e.g. `easy_retarget_0_0_1.py`).

### Fixed
- `TypeError` when adding a blank bone pair entry: `EnumProperty` for Source Bone and Target Bone
  now uses `"NONE"` as the default sentinel token instead of `""`, resolving the invalid enum
  assignment when no bone match is found.

---

## [0.0.0] — 2026-03-31

### Added
- Initial add-on scaffold targeting Blender 5.0+.
- `bl_info` metadata block with name, author (Lemur-Duck Studios), version, and category.
- **EasyRetarget** N-panel tab in the 3D Viewport.
- Source Rig and Target Rig armature object pickers, filtered to armature objects only.
- **Bone Pairs** expandable section containing:
  - `UIList`-based bone pair list with per-entry Source Bone, Target Bone (filtered `EnumProperty` dropdowns populated from the selected rigs), and Offset (float).
  - Individual entry selection via standard `UIList` active index.
  - Add (`+`) operator that attempts automatic bone name matching between rigs; defaults to blank if no match is found.
  - Remove (`−`) operator that removes the currently selected entry.
  - Up/Down move operators providing drag-style reordering via Blender's `CollectionProperty.move()`.
- **Settings** expandable section containing:
  - "Bake Keyed Frames Only" checkbox (`BoolProperty`).
  - "Keying Interval" positive integer field (default: 1), disabled when "Bake Keyed Frames Only" is checked.
- **Bake** button (full-width, outside Settings) wired to a placeholder operator.
- Full `register()` / `unregister()` lifecycle with `PointerProperty` scene integration.
