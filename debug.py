# =====================================================================
# EasyRetarget - debug.py
# Addon preferences and debug logging utilities.
# =====================================================================

import bpy
import os
from datetime import datetime
from bpy.types import AddonPreferences
from bpy.props import BoolProperty, StringProperty


# Session log file path — set on first log() call, stable for the session.
_session_log_path: str = ""


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
# Addon Preferences
# =====================================================================

class EASYRETARGET_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    debug_logging: BoolProperty(
        name="Debug Logging",
        description="Write detailed debug information to a log file on each depsgraph update",
        default=True,
    )

    log_directory: StringProperty(
        name="Log Directory",
        description="Directory where debug log files will be written",
        subtype='DIR_PATH',
        default="C:\\Users\\ThatCasual\\OneDrive\\Projects\\WithClaude\\EasyRetarget\\logs\\",
    )

    def draw(self, context):
        layout = self.layout
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
