"""
app/config.py — Re-exports from scripts.run_state for use by the app package.
Single import point so modules don't need to know the scripts.* path themselves.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on sys.path so `scripts` namespace package resolves
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.run_state import (  # noqa: E402
    ROOT,
    SETTINGS_PATH,
    DEFAULT_WORKSPACE_FILES,
    load_settings,
    vault_root,
    source_dir,
    workspace_dir,
    state_path,
    load_state,
    save_state,
    default_state,
    infer_next_step,
    validate_state,
    normalize_state,
    atomic_write_json,
    update_timestamp,
)

__all__ = [
    "ROOT",
    "SETTINGS_PATH",
    "DEFAULT_WORKSPACE_FILES",
    "load_settings",
    "vault_root",
    "source_dir",
    "workspace_dir",
    "state_path",
    "load_state",
    "save_state",
    "default_state",
    "infer_next_step",
    "validate_state",
    "normalize_state",
    "atomic_write_json",
    "update_timestamp",
]
