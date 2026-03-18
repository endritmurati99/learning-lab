"""
app/orchestrator.py — Central pipeline stage runner.

Python is the boss here. This module owns the control flow.
Claude is called only for cognitive subroutines (workspace structuring,
logic check, rebuild design, vault note generation).

Usage: imported by lab.py. Do not run directly.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import (
    ROOT,
    default_state,
    infer_next_step,
    load_state,
    save_state,
    source_dir,
    state_path,
    atomic_write_json,
)
from app.ingest import IngestError, detect_source_type, derive_slug, run_ingest
from app.notebooklm import NotebookLMAuthError, NotebookLMError, run_notebooklm_stage
from app.cognitive import CognitiveError, generate_vault_note, run_logic_check, structure_workspace
from app.preflight import PreflightError, check_optional_tools, check_tools


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorConfig:
    slug: str
    source_input: str              # original URL / path / slug string
    source_type: str               # youtube | web | pdf | local
    deliverable: str = "study_guide"
    topic: str | None = None
    include_rebuild: bool = False
    include_fill_gaps: bool = False
    include_vault: bool = False
    full_pipeline: bool = False
    auto_mode: bool = False
    force_reingest: bool = False
    verbose: bool = False
    dry_run: bool = False
    specific_stage: str | None = None
    title: str | None = None       # human-readable title (optional)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(config: OrchestratorConfig) -> int:
    """Main pipeline entry. Returns 0 on success, non-zero on error."""
    # Ensure sources dir exists
    source_dir(config.slug).mkdir(parents=True, exist_ok=True)

    # Load or initialize state
    state = _init_or_resume(config)

    # Set auto_mode in run.json when --auto is passed
    if config.auto_mode:
        state["auto_mode"] = True
        save_state(config.slug, state)

    # Single-stage mode
    if config.specific_stage:
        return _run_single_stage(config.specific_stage, config, state)

    # Full pipeline loop
    return _run_pipeline(config, state)


# ---------------------------------------------------------------------------
# Pipeline loop
# ---------------------------------------------------------------------------

def _run_pipeline(config: OrchestratorConfig, state: dict[str, Any]) -> int:
    while True:
        next_step = infer_next_step(state)
        _log(config, f"Next step: {next_step}")

        if next_step == "complete":
            _report_complete(config, state)
            return 0

        if not _should_run_stage(next_step, config):
            _report_boundary(next_step, config)
            return 0

        if config.dry_run:
            print(f"[lab] (dry-run) Would run stage: {next_step}")
            # Peek at what would follow by simulating stage completion
            state = _peek_next(next_step, state)
            if infer_next_step(state) == next_step:
                # Prevent infinite loop in dry-run
                break
            continue

        exit_code = _run_stage(next_step, config, state)
        if exit_code != 0:
            return exit_code

        # Reload state from disk after each stage (stages mutate run.json)
        state = load_state(config.slug)


def _should_run_stage(stage: str, config: OrchestratorConfig) -> bool:
    if stage in ("ingest", "notebooklm", "workspace"):
        return True
    if stage == "rebuild-project":
        return config.include_rebuild or config.full_pipeline
    if stage == "fill-gaps":
        return config.include_fill_gaps or config.full_pipeline
    if stage == "save-to-vault":
        return config.include_vault or config.full_pipeline
    return False


def _run_stage(stage: str, config: OrchestratorConfig, state: dict[str, Any]) -> int:
    try:
        if stage == "ingest":
            return _stage_ingest(config, state)
        if stage == "notebooklm":
            return _stage_notebooklm(config, state)
        if stage == "workspace":
            return _stage_workspace(config, state)
        if stage == "rebuild-project":
            return _stage_rebuild(config, state)
        if stage == "fill-gaps":
            return _stage_fill_gaps(config, state)
        if stage == "save-to-vault":
            return _stage_vault(config, state)
        print(f"[lab] ERROR: Unknown stage: {stage}", file=sys.stderr)
        return 1
    except (IngestError, NotebookLMAuthError, NotebookLMError, CognitiveError, PreflightError) as exc:
        _fail_stage(stage, config.slug, exc)
        return 1


def _run_single_stage(stage: str, config: OrchestratorConfig, state: dict[str, Any]) -> int:
    _log(config, f"Running single stage: {stage}")
    if config.dry_run:
        print(f"[lab] (dry-run) Would run stage: {stage}")
        return 0
    return _run_stage(stage, config, state)


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

def _stage_ingest(config: OrchestratorConfig, state: dict[str, Any]) -> int:
    if state["ingest"]["status"] == "done" and not config.force_reingest:
        _log(config, "Ingest already done — skipping")
        return 0

    missing = check_tools("ingest", config.source_type)
    if missing:
        _block_stage("ingest", config.slug, f"Missing tools: {', '.join(missing)}")
        return 1

    optional_missing = check_optional_tools("ingest", config.source_type)
    if optional_missing:
        _warn(f"Optional tools missing (non-blocking): {', '.join(optional_missing)}")

    _log(config, f"Ingesting {config.source_type} source: {config.source_input}")
    run_ingest(config.slug, config.source_input, config.title)
    _log(config, "Ingest complete")
    return 0


def _stage_notebooklm(config: OrchestratorConfig, state: dict[str, Any]) -> int:
    if state["notebooklm"]["status"] == "done":
        _log(config, "NotebookLM already done — skipping")
        return 0

    missing = check_tools("notebooklm", "*")
    if missing:
        _block_stage("notebooklm", config.slug, f"Missing tools: {', '.join(missing)}")
        return 1

    _log(config, f"Generating NotebookLM deliverable: {config.deliverable}")
    try:
        run_notebooklm_stage(config.slug, config.deliverable)
    except NotebookLMAuthError as exc:
        # Auth errors get a special message — not just "blocked"
        print(f"[lab] AUTH ERROR: {exc}", file=sys.stderr)
        _fail_stage("notebooklm", config.slug, exc)
        return 1
    _log(config, "NotebookLM complete")
    return 0


def _stage_workspace(config: OrchestratorConfig, state: dict[str, Any]) -> int:
    if state["workspace"]["status"] == "done" and state["workspace"].get("files_complete"):
        _log(config, "Workspace already complete — skipping")
        return 0

    missing = check_tools("workspace", "*")
    if missing:
        _block_stage("workspace", config.slug, f"Missing tools: {', '.join(missing)}")
        return 1

    _log(config, "Structuring workspace (calling Claude for cognitive work)")
    structure_workspace(config.slug)
    _log(config, "Workspace structuring complete")
    return 0


def _stage_rebuild(config: OrchestratorConfig, state: dict[str, Any]) -> int:
    rebuild_state = state.get("rebuild", {})
    if rebuild_state.get("status") in ("done", "skipped"):
        _log(config, f"Rebuild already {rebuild_state['status']} — skipping")
        return 0

    if not state["workspace"].get("is_tutorial", False):
        _log(config, "Source is not a tutorial — marking rebuild as skipped")
        state = load_state(config.slug)
        state["rebuild"]["status"] = "skipped"
        state["rebuild"]["reason"] = "not_applicable"
        state["next_recommended_step"] = "fill-gaps"
        save_state(config.slug, state)
        return 0

    # Rebuild is a cognitive task — delegate to the existing rebuild-project skill
    # via Claude (the skill has the actual code-writing logic).
    # For now we signal this as a boundary the user must cross manually,
    # unless a rebuild cognitive function is added to cognitive.py later.
    _log(config, "Rebuild stage: invoke 'rebuild-project' skill in Claude Code for code writing")
    print(
        "[lab] Rebuild requires Claude to write real project code.\n"
        "      Run the rebuild-project skill interactively, then resume with:\n"
        f"      python lab.py {config.slug} --fill-gaps --vault",
        file=sys.stderr,
    )
    return 0


def _stage_fill_gaps(config: OrchestratorConfig, state: dict[str, Any]) -> int:
    if state["fill_gaps"]["status"] == "done":
        _log(config, "Fill-gaps already done — skipping")
        return 0

    # fill-gaps cognitive work is handled by the fill-gaps skill in Claude.
    # auto_mode is already set in run.json, so the skill will skip confirmations.
    auto = state.get("auto_mode", False)
    if auto:
        _log(config, "fill-gaps: auto_mode=true — skill will run non-interactively")
    else:
        print(
            "[lab] fill-gaps stage reached. Run the fill-gaps skill in Claude Code:\n"
            f"      Trigger: 'fill gaps {config.slug}'\n"
            "      auto_mode is set in run.json — confirmations will be skipped.",
            file=sys.stderr,
        )
    # Mark as in_progress so state reflects we've reached this stage
    state = load_state(config.slug)
    if state["fill_gaps"]["status"] == "not_started":
        state["fill_gaps"]["status"] = "in_progress"
        save_state(config.slug, state)
    return 0


def _stage_vault(config: OrchestratorConfig, state: dict[str, Any]) -> int:
    vault_status = state.get("vault", {}).get("status", "not_started")
    if vault_status == "done":
        _log(config, "Vault already done — skipping")
        return 0

    # Import vault_sync here (heavy import, only needed for this stage)
    try:
        import sys as _sys
        _sys.path.insert(0, str(ROOT))
        from scripts import vault_sync  # type: ignore[import]
    except ImportError as exc:
        _fail_stage("vault", config.slug, exc)
        return 1

    _log(config, "Generating English vault note (calling Claude)")
    note_body = generate_vault_note(config.slug)

    # Write note body to temp file for vault_sync
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(note_body)
        tmp_path = Path(tmp.name)

    try:
        # Derive note title from workspace summary
        state = load_state(config.slug)
        title = state["vault"].get("draft_title") or state["source"].get("title", config.slug)
        main_insight = _extract_main_insight(note_body)

        _log(config, f"Exporting draft to Vault: {title}")
        result = vault_sync.export_draft(
            slug=config.slug,
            note_title=title,
            note_body_file=tmp_path,
            main_insight=main_insight,
        )

        # Update run.json with ExportResult
        state = load_state(config.slug)
        state["vault"]["note_path"] = result.note_path
        state["vault"]["bundle_path"] = result.bundle_path
        state["vault"]["project_bundle_path"] = result.project_bundle_path
        state["vault"]["daily_note_path"] = result.daily_note_path
        state["vault"]["draft_title"] = result.draft_title
        state["vault"]["export_identity"] = result.export_identity
        state["vault"]["last_exported_at"] = result.last_exported_at

        auto = state.get("auto_mode", False)
        if auto:
            state["vault"]["status"] = "done"
            state["next_recommended_step"] = "complete"
            _log(config, "Vault export complete (auto_mode)")
        else:
            state["vault"]["status"] = "awaiting_confirmation"
            print(
                f"[lab] Vault draft prepared at: {result.note_path}\n"
                "      Review and confirm by running: python lab.py " +
                config.slug + " --stage vault --auto",
                file=sys.stderr,
            )

        save_state(config.slug, state)
    finally:
        tmp_path.unlink(missing_ok=True)

    return 0


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _init_or_resume(config: OrchestratorConfig) -> dict[str, Any]:
    """Load existing run.json or initialize a new one."""
    path = state_path(config.slug)
    if path.exists():
        state = load_state(config.slug)
        _log(config, f"Resuming run (next: {state.get('next_recommended_step', '?')})")
        return state

    _log(config, f"Initializing new run for slug: {config.slug}")
    state = default_state(config.source_type, config.source_input, config.slug, config.title)
    source_dir(config.slug).mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, state)
    return state


def _fail_stage(stage: str, slug: str, exc: Exception) -> None:
    print(f"[lab] FAILED stage '{stage}': {exc}", file=sys.stderr)
    try:
        state = load_state(slug)
        stage_key = stage.replace("-", "_")
        if stage_key in state:
            state[stage_key]["status"] = "failed"
        save_state(slug, state)
    except Exception:
        pass


def _block_stage(stage: str, slug: str, reason: str) -> None:
    print(f"[lab] BLOCKED stage '{stage}': {reason}", file=sys.stderr)
    try:
        state = load_state(slug)
        stage_key = stage.replace("-", "_")
        if stage_key in state:
            state[stage_key]["status"] = "blocked"
        if reason not in state.get("ingest", {}).get("warnings", []):
            pass
        save_state(slug, state)
    except Exception:
        pass


def _report_complete(config: OrchestratorConfig, state: dict[str, Any]) -> None:
    slug = config.slug
    vault = state.get("vault", {})
    print(f"\n[lab] Pipeline complete for: {slug}")
    if vault.get("note_path"):
        print(f"      Vault note:   {vault['note_path']}")
    if vault.get("bundle_path"):
        print(f"      Asset bundle: {vault['bundle_path']}")


def _report_boundary(stage: str, config: OrchestratorConfig) -> None:
    slug = config.slug
    flag_hints = {
        "rebuild-project": "--rebuild",
        "fill-gaps": "--fill-gaps",
        "save-to-vault": "--vault",
    }
    flag = flag_hints.get(stage, f"--stage {stage}")
    print(
        f"[lab] Stopped at stage boundary: {stage}\n"
        f"      To continue: python lab.py {slug} {flag}"
    )


def _peek_next(stage: str, state: dict[str, Any]) -> dict[str, Any]:
    """Simulate stage completion in dry-run so the loop can advance."""
    import copy
    s = copy.deepcopy(state)
    stage_key = stage.replace("-", "_")
    if stage_key in s:
        s[stage_key]["status"] = "done"
    return s


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _extract_main_insight(note_body: str) -> str:
    """Extract the first non-empty sentence from the Core Thesis section."""
    lines = note_body.splitlines()
    in_thesis = False
    for line in lines:
        if "## Core Thesis" in line:
            in_thesis = True
            continue
        if in_thesis:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:200]
    return ""


def _log(config: OrchestratorConfig, msg: str) -> None:
    if config.verbose:
        print(f"[lab] {msg}")


def _warn(msg: str) -> None:
    print(f"[lab] WARNING: {msg}", file=sys.stderr)
