"""
app/preflight.py — Tool availability checks before each pipeline stage.
Returns missing tool names so the orchestrator can record them in run.json.
"""
from __future__ import annotations

import shutil

# Required tools per stage and source type.
# Outer key: stage name. Inner key: source type (or "*" for all types).
TOOL_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "ingest": {
        "youtube": ["yt-dlp", "python"],
        "web": ["defuddle", "python"],
        "pdf": ["python"],
        "local": ["python"],
        "*": ["python"],
    },
    "notebooklm": {
        "*": ["notebooklm", "python"],
    },
    "workspace": {
        "*": ["claude", "python"],
    },
    "rebuild": {
        "*": ["claude", "python"],
    },
    "fill-gaps": {
        "*": ["claude", "python"],
    },
    "vault": {
        "*": ["python"],
    },
}

# Optional tools whose absence generates a warning (not a hard block)
OPTIONAL_TOOLS: dict[str, list[str]] = {
    "ingest:youtube": ["ffmpeg", "buzz"],
    "ingest:pdf": ["pandoc"],
}


def check_tools(stage: str, source_type: str = "*") -> list[str]:
    """Return list of missing *required* tools for the given stage + source type."""
    stage_reqs = TOOL_REQUIREMENTS.get(stage, {})
    tools: list[str] = []
    # Add source-type-specific requirements
    tools.extend(stage_reqs.get(source_type, []))
    # Add universal requirements for this stage
    for t in stage_reqs.get("*", []):
        if t not in tools:
            tools.append(t)

    missing = [t for t in tools if not _which(t)]
    return missing


def check_optional_tools(stage: str, source_type: str = "*") -> list[str]:
    """Return list of missing *optional* tools (generates warnings only)."""
    key = f"{stage}:{source_type}"
    optional = OPTIONAL_TOOLS.get(key, [])
    return [t for t in optional if not _which(t)]


def require_tools(stage: str, source_type: str = "*") -> None:
    """Raise PreflightError if any required tools are missing."""
    missing = check_tools(stage, source_type)
    if missing:
        raise PreflightError(
            f"Stage '{stage}' requires tools that are not installed: {', '.join(missing)}"
        )


def _which(tool: str) -> bool:
    return shutil.which(tool) is not None


class PreflightError(RuntimeError):
    pass
