"""
app/notebooklm.py — NotebookLM CLI wrappers.

Wraps the unofficial `notebooklm` CLI with:
- Auth failure detection (raises NotebookLMAuthError with actionable message)
- Session/network error detection
- Notebook reuse when notebook_id.txt already exists
- State updates via load_state/save_state
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app.config import load_state, save_state, source_dir


# ---------------------------------------------------------------------------
# Auth / error keywords
# ---------------------------------------------------------------------------

_AUTH_KEYWORDS = frozenset(["login", "auth", "unauthorized", "401", "session", "credentials", "expired"])
_TIMEOUT_KEYWORDS = frozenset(["timeout", "timed out", "connection refused", "network"])


def _classify_error(stderr: str, returncode: int) -> None:
    """Raise a typed error based on stderr content."""
    low = stderr.lower()
    if any(kw in low for kw in _AUTH_KEYWORDS):
        raise NotebookLMAuthError(
            "NotebookLM authentication failed. "
            "Open a separate terminal and run: notebooklm login\n"
            f"CLI output: {stderr[:300]}"
        )
    if any(kw in low for kw in _TIMEOUT_KEYWORDS):
        raise NotebookLMNetworkError(
            f"NotebookLM network/timeout error (exit {returncode}):\n{stderr[:300]}"
        )
    raise NotebookLMError(
        f"notebooklm command failed (exit {returncode}):\n{stderr[:400]}"
    )


def _run_nlm(cmd: list[str], timeout: int = 600) -> str:
    """Run a notebooklm CLI command. Returns stdout. Raises typed errors on failure."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise NotebookLMNetworkError(
            f"notebooklm command timed out after {timeout}s: {' '.join(cmd)}"
        )
    except FileNotFoundError:
        raise NotebookLMError(
            "notebooklm is not installed or not in PATH. "
            "Install it and run: notebooklm login"
        )
    if result.returncode != 0:
        _classify_error(result.stderr, result.returncode)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Notebook operations
# ---------------------------------------------------------------------------

def create_notebook(title: str) -> str:
    """
    Create a new NotebookLM notebook. Returns the notebook_id string.
    The CLI is expected to print the notebook_id to stdout.
    """
    output = _run_nlm(["notebooklm", "create", "--title", f"Learn: {title}"])
    # Expect output to be just the notebook_id (UUID-like string)
    notebook_id = output.strip()
    if not notebook_id:
        raise NotebookLMError("notebooklm create returned empty notebook_id")
    return notebook_id


def add_source(notebook_id: str, source_file: Path) -> None:
    """Add a source file to an existing notebook."""
    if not source_file.exists():
        raise NotebookLMError(f"Source file does not exist: {source_file}")
    _run_nlm([
        "notebooklm", "add-source",
        "--notebook-id", notebook_id,
        "--file", str(source_file),
    ])


def generate_deliverable(notebook_id: str, deliverable: str, output_path: Path) -> None:
    """
    Generate a NotebookLM deliverable and write it to output_path.
    Tries --instructions flag; ignores if not supported by CLI version.
    """
    instructions = (
        "Identify hidden assumptions, unstated prerequisites, implicit biases, "
        "and conclusions that lack direct evidence."
    )
    # Try with --instructions first
    cmd_with = [
        "notebooklm", "generate",
        "--notebook-id", notebook_id,
        "--type", deliverable,
        "--instructions", instructions,
        "--output", str(output_path),
    ]
    try:
        _run_nlm(cmd_with, timeout=900)
        return
    except NotebookLMError as exc:
        # If the error message suggests --instructions is not supported, retry without
        msg = str(exc).lower()
        if "instructions" not in msg and "unrecognized" not in msg:
            raise

    # Retry without --instructions
    cmd_plain = [
        "notebooklm", "generate",
        "--notebook-id", notebook_id,
        "--type", deliverable,
        "--output", str(output_path),
    ]
    _run_nlm(cmd_plain, timeout=900)


# ---------------------------------------------------------------------------
# Full stage runner
# ---------------------------------------------------------------------------

def run_notebooklm_stage(slug: str, deliverable: str = "study_guide") -> None:
    """
    Orchestrate the full NotebookLM stage for a slug:
    1. Reuse existing notebook_id or create a new notebook
    2. Add primary source file(s)
    3. Generate the requested deliverable
    4. Update run.json state

    Raises NotebookLMAuthError / NotebookLMError on failure.
    """
    sdir = source_dir(slug)
    state = load_state(slug)

    state["notebooklm"]["status"] = "in_progress"
    save_state(slug, state)

    # --- Resolve notebook_id ---
    notebook_id_file = sdir / "notebook_id.txt"
    existing_id = state["notebooklm"].get("notebook_id")

    if notebook_id_file.exists():
        notebook_id = notebook_id_file.read_text(encoding="utf-8").strip()
    elif existing_id:
        notebook_id = existing_id
    else:
        title = state["source"].get("title", slug)
        notebook_id = create_notebook(title)

    # Persist notebook_id.txt + state
    notebook_id_file.write_text(notebook_id, encoding="utf-8")
    state = load_state(slug)
    state["notebooklm"]["notebook_id"] = notebook_id
    save_state(slug, state)

    # --- Add primary source file ---
    source_file = _find_primary_source(sdir, state["source"]["type"])
    if source_file is None:
        raise NotebookLMError(
            f"No primary source file found in sources/{slug}/ to add to NotebookLM. "
            "Expected: transcript .txt, content.md, or .pdf"
        )
    add_source(notebook_id, source_file)

    # --- Generate deliverable ---
    artifact_name = f"nlm-{deliverable}.md"
    output_path = sdir / artifact_name
    generate_deliverable(notebook_id, deliverable, output_path)

    if not output_path.exists():
        raise NotebookLMError(
            f"notebooklm generate completed but output file not found: {output_path}"
        )

    # --- Update state ---
    state = load_state(slug)
    if deliverable not in state["notebooklm"]["deliverables"]:
        state["notebooklm"]["deliverables"].append(deliverable)
    if artifact_name not in state["notebooklm"]["artifacts"]:
        state["notebooklm"]["artifacts"].append(artifact_name)
    state["notebooklm"]["status"] = "done"
    state["workspace"]["status"] = "in_progress"
    state["next_recommended_step"] = "workspace"
    save_state(slug, state)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRIMARY_SOURCE_CANDIDATES: dict[str, list[str]] = {
    "youtube": ["*.txt", "*.srt"],
    "web": ["content.md", "content.txt"],
    "pdf": ["content.md", "*.pdf"],
    "local": ["*.md", "*.txt"],
}


def _find_primary_source(sdir: Path, source_type: str) -> Path | None:
    """Find the best primary source file to upload to NotebookLM."""
    patterns = _PRIMARY_SOURCE_CANDIDATES.get(source_type, ["*.md", "*.txt"])
    for pattern in patterns:
        if "*" in pattern:
            # Glob — prefer shortest name (most likely the transcript)
            matches = [
                f for f in sdir.glob(pattern)
                if f.name not in ("metadata.tsv", "ingest.log")
                and "extra_context" not in f.name
            ]
            if matches:
                return min(matches, key=lambda f: len(f.name))
        else:
            candidate = sdir / pattern
            if candidate.exists():
                return candidate
    return None


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class NotebookLMError(RuntimeError):
    pass


class NotebookLMAuthError(NotebookLMError):
    """Raised when the notebooklm CLI indicates auth/session failure."""
    pass


class NotebookLMNetworkError(NotebookLMError):
    pass
