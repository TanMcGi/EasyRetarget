# =====================================================================
# EasyRetarget - debug.py
# Addon preferences and debug logging utilities.
# =====================================================================

import bpy
import os
from datetime import datetime
from bpy.types import AddonPreferences, Operator
from bpy.props import BoolProperty, StringProperty


# Session log file path — set on first log() call, stable for the session.
_session_log_path: str = ""

# AutoPopulate log file path — reset and recreated on each AutoPopulate run.
_ap_log_path: str = ""


def _get_prefs():
    """Return the EasyRetarget addon preferences, or None if unavailable."""
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        return None


def _get_log_path():
    """
    Return the log file path for this session, creating it on first call.
    Filename format: easy_retarget_YYYY-MM-DD_HH-MM-SS.log
    """
    global _session_log_path
    if _session_log_path:
        return _session_log_path

    prefs = _get_prefs()
    if prefs and prefs.log_directory:
        directory = bpy.path.abspath(prefs.log_directory)
    else:
        directory = bpy.app.tempdir

    os.makedirs(directory, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"easy_retarget_{timestamp}.log"
    _session_log_path = os.path.join(directory, filename)
    return _session_log_path


def log(message: str):
    """
    Write a timestamped message to the session log file if debug logging
    is enabled in addon preferences.
    """
    prefs = _get_prefs()
    if not prefs or not prefs.debug_logging:
        return

    path = _get_log_path()
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {message}\n"

    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        print(f"EasyRetarget debug log error: {e}")


def log_section(title: str):
    """Write a section divider to the log."""
    log(f"{'─' * 60}")
    log(f"  {title}")
    log(f"{'─' * 60}")


def reset_session_log():
    """
    Reset the session log path so the next log() call starts a new file.
    Call this if you want a fresh log within the same Blender session.
    """
    global _session_log_path
    _session_log_path = ""


# =====================================================================
# AutoPopulate Log
# A separate log file created fresh on each AutoPopulate run.
# Written to log_directory/auto_populate/ (independent of the session log).
# =====================================================================

def _get_ap_log_path() -> str:
    """
    Create and return a new AutoPopulate log file path.
    Called at the start of each AutoPopulate run to produce a fresh file.
    Files go to: <log_directory>/auto_populate/autopopulate_YYYY-MM-DD_HH-MM-SS.log
    """
    global _ap_log_path

    prefs = _get_prefs()
    if prefs and prefs.log_directory:
        base_dir = bpy.path.abspath(prefs.log_directory)
    else:
        base_dir = bpy.app.tempdir

    ap_dir = os.path.join(base_dir, "auto_populate")
    os.makedirs(ap_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"autopopulate_{timestamp}.log"
    _ap_log_path = os.path.join(ap_dir, filename)
    return _ap_log_path


def reset_ap_log():
    """
    Force a new AutoPopulate log file on the next log_autopopulate() call.
    Call this at the start of each AutoPopulate run.
    """
    global _ap_log_path
    _ap_log_path = _get_ap_log_path()


def log_autopopulate(message: str):
    """
    Write a timestamped line to the AutoPopulate log file.
    Respects the same debug_logging preference as the session log.
    No-op if debug logging is disabled.
    """
    prefs = _get_prefs()
    if not prefs or not prefs.debug_logging:
        return

    if not _ap_log_path:
        return

    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {message}\n"

    try:
        with open(_ap_log_path, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        print(f"EasyRetarget AutoPopulate log error: {e}")


def log_ap_section(title: str):
    """Write a section divider to the AutoPopulate log."""
    log_autopopulate(f"{'─' * 60}")
    log_autopopulate(f"  {title}")
    log_autopopulate(f"{'─' * 60}")


# =====================================================================
# Reset Addon State Operator
# =====================================================================

class EASYRETARGET_OT_ResetAddonState(Operator):
    """
    Re-register all EasyRetarget handlers and start a fresh log file.
    Use this when reloading the addon mid-session without restarting
    Blender, to clear stale handler state from previous versions.
    """
    bl_idname = "easy_retarget.reset_addon_state"
    bl_label = "Reset Addon State"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from . import handlers
        # Unregister all handlers cleanly then re-register.
        handlers.unregister_handlers()
        handlers.register_handlers()
        # Start a fresh log file for this session.
        reset_session_log()
        self.report({'INFO'}, "EasyRetarget: Addon state reset. Fresh log started.")
        log("  ResetAddonState: handlers re-registered, new log started.")
        return {'FINISHED'}


# =====================================================================
# Addon Preferences
# =====================================================================

class EASYRETARGET_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    debug_logging: BoolProperty(
        name="Debug Logging",
        description="Write detailed debug information to a log file on each depsgraph update",
        default=True,
    )

    create_rotation_by_default: BoolProperty(
        name="Create Rotation Constraint by Default",
        description="Automatically create the rotation constraint when the edit popup is opened for a bone pair with no constraints",
        default=True,
    )

    create_location_by_default: BoolProperty(
        name="Create Location Constraint by Default",
        description="Automatically create the location constraint when the edit popup is opened for a bone pair with no constraints",
        default=False,
    )

    log_directory: StringProperty(
        name="Log Directory",
        description="Directory where debug log files will be written",
        subtype='DIR_PATH',
        default="C:\\Users\\ThatCasual\\OneDrive\\Projects\\WithClaude\\EasyRetarget\\logs\\",
    )

    def draw(self, context):
        layout = self.layout

        # ── Hotkeys ──────────────────────────────────────────────────
        col = layout.column(align=True)
        col.label(text="Hotkeys", icon='KEYINGSET')

        wm = context.window_manager
        kc = wm.keyconfigs.addon
        if kc:
            from . import keymap as er_keymap
            from rna_keymap_ui import draw_kmi
            for km, kmi in er_keymap.addon_keymaps:
                col2 = col.column()
                col2.context_pointer_set("keymap", km)
                draw_kmi([], kc, km, kmi, col2, 0)

        layout.separator()

        # ── Debug Logging ─────────────────────────────────────────────
        col = layout.column(align=True)
        col.prop(self, "debug_logging")

        row = col.row()
        row.enabled = self.debug_logging
        row.prop(self, "log_directory", text="Log Directory")

        if self.debug_logging:
            path = _get_log_path()
            col.separator()
            info_box = col.box()
            info_box.label(text=f"Current log: {path}", icon='TEXT')

        col.separator()
        col.operator("easy_retarget.reset_addon_state", icon='FILE_REFRESH')

        layout.separator()

        # ── Constraint Defaults ───────────────────────────────────────
        col = layout.column(align=True)
        col.label(text="Constraint Defaults", icon='CONSTRAINT_BONE')
        col.prop(self, "create_rotation_by_default")
        col.prop(self, "create_location_by_default")
