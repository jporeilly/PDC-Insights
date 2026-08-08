"""Where the app's mutable state lives.

Both writes this app ever makes — a saved dashboard spec and the Settings
page's ``.env`` persist — used to land beside the code. That is correct for a
source checkout and fatal for a packaged install: ``C:\\Program Files`` is not
writable, so the first save fails and the app looks broken rather than
mis-installed. (The pattern, and most of this file, comes from the Glossary
Generator's ``core/paths.py``, which learned it the hard way.)

This module is the single place that answers "which directory". Resolution,
in order:

  1. ``$INSIGHTS_STATE_DIR``, if set. Explicit always wins — this is what the
     Windows desktop shell sets, so the packaged app never has to infer
     anything.
  2. The repo root, if it is writable. Unchanged behaviour for checkouts,
     run.ps1/run.sh and Docker — ``.env`` stays at the root, saved dashboards
     stay in ``app/dashboards/``, nobody's existing state moves.
  3. The per-user data directory (``%APPDATA%\\PDC-Insights`` on Windows,
     ``$XDG_DATA_HOME`` or ``~/.local/share/pdc-insights`` elsewhere). Only
     reached when the repo root is read-only, i.e. a packaged install that
     did not set the variable.

Writability is PROBED, not asked: ``os.access(W_OK)`` reports the read-only
attribute on Windows and ignores ACLs, so it happily says yes for a directory
under Program Files that then refuses the write.

Saved dashboards overlay the shipped built-ins: reads check the state
directory first, then ``app/dashboards/``. In a checkout both are the same
place, so behaviour is exactly as before.
"""
from __future__ import annotations

import os
import sys
import tempfile

# app/ — the package directory; the shipped built-in dashboards live below it.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
# The repo root — where .env, frontend/ and ui/ live.
ROOT_DIR = os.path.dirname(APP_DIR)

# The read-only dashboards that ship with the app (3 per Analytics section).
BUILTIN_DASH_DIR = os.path.join(APP_DIR, "dashboards")

_STATE_DIR: str | None = None
_STATE_SOURCE: str | None = None       # why we chose it — for diagnostics


def _is_writable(path: str) -> bool:
    """Probe by actually creating a file. See the module docstring."""
    if not os.path.isdir(path):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            return False
    try:
        fd, probe = tempfile.mkstemp(prefix=".writeprobe-", dir=path)
        os.close(fd)
        os.unlink(probe)
        return True
    except OSError:
        return False


def _user_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "PDC-Insights")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/PDC-Insights")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "pdc-insights")


def state_dir() -> str:
    """The directory holding mutable state. Created if missing. Cached."""
    global _STATE_DIR, _STATE_SOURCE
    if _STATE_DIR is not None:
        return _STATE_DIR

    explicit = os.environ.get("INSIGHTS_STATE_DIR")
    if explicit:
        _STATE_DIR, _STATE_SOURCE = os.path.abspath(explicit), "INSIGHTS_STATE_DIR"
    elif _is_writable(ROOT_DIR):
        _STATE_DIR, _STATE_SOURCE = ROOT_DIR, "repo root (writable checkout)"
    else:
        _STATE_DIR, _STATE_SOURCE = _user_data_dir(), "per-user (install is read-only)"

    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
    except OSError:
        # A read-only state dir is not recoverable, but failing at import time
        # would take the whole app down with a stack trace. Let the individual
        # writes fail with their own messages instead.
        pass
    return _STATE_DIR


def state_source() -> str:
    """Human-readable reason for the current state_dir(). For diagnostics."""
    state_dir()
    return _STATE_SOURCE or "unresolved"


def env_file() -> str:
    """The .env the Settings page persists to (and the entrypoints load).

    In a checkout ``state_dir()`` is the repo root, so this is the same
    ``.env`` the app has always used."""
    return os.path.join(state_dir(), ".env")


def saved_dash_dir() -> str:
    """Where dashboard SAVES go. Never the install directory.

    In a checkout the state dir is the repo root and saves land in
    ``app/dashboards/`` exactly as before. Anywhere else (packaged install,
    or an explicit ``INSIGHTS_STATE_DIR``) they land in a ``dashboards/``
    folder inside the state directory."""
    if state_dir() == ROOT_DIR:
        return BUILTIN_DASH_DIR
    return os.path.join(state_dir(), "dashboards")


def dash_read_dirs() -> list[str]:
    """Directories to READ a dashboard from, saved-first.

    A user-saved spec must win over a shipped built-in of the same id, or
    duplicating-and-tweaking a standard dashboard would appear to do nothing."""
    dirs = [saved_dash_dir(), BUILTIN_DASH_DIR]
    return list(dict.fromkeys(dirs))            # dedupe, order preserved


def find_dashboard(section: str, filename: str) -> str | None:
    """Absolute path of ``<section>/<filename>`` in the first read dir that has
    it, or None. The one lookup rule shared by the web routes and the MCP
    server, so the two front doors cannot disagree about which file is live."""
    for d in dash_read_dirs():
        p = os.path.join(d, section, filename)
        if os.path.isfile(p):
            return p
    return None


def reset_cache() -> None:
    """Forget the resolved directory. Tests only — the environment is read once
    per process otherwise."""
    global _STATE_DIR, _STATE_SOURCE
    _STATE_DIR = _STATE_SOURCE = None
