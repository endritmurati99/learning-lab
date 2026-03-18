"""
app/cognitive.py — Claude cognitive subroutines via `claude --print`.

Every function here calls `claude --print` as a subprocess (stdin pipe),
parses the output defensively, and writes results to disk.

Output contract with Claude: files are delimited with:
    <!-- FILE: filename.md -->
    ...content...
    <!-- END FILE -->

The parser strips ANSI escape codes and skips any conversational fluff
outside these delimiters. Claude prompts must include:
    "Return ONLY the file blocks. NO greetings, NO explanations."
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from app.config import (
    DEFAULT_WORKSPACE_FILES,
    ROOT,
    load_state,
    save_state,
    source_dir,
    workspace_dir,
)


# ---------------------------------------------------------------------------
# Core subprocess call
# ---------------------------------------------------------------------------

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def run_claude(prompt: str, timeout: int = 900) -> str:
    """
    Call `claude --print -` with the prompt on stdin.
    Returns stdout as plain text (ANSI codes stripped).
    Raises CognitiveError on failure.
    """
    try:
        result = subprocess.run(
            ["claude", "--print", "-"],
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise CognitiveError(f"claude --print timed out after {timeout}s")
    except FileNotFoundError:
        raise CognitiveError("claude CLI not found. Ensure it is installed and in PATH.")

    raw = result.stdout or ""
    clean = _ANSI_ESCAPE.sub("", raw)

    if result.returncode != 0:
        stderr_snippet = _ANSI_ESCAPE.sub("", result.stderr or "")[:400]
        raise CognitiveError(
            f"claude exited {result.returncode}: {stderr_snippet}\n"
            f"Prompt (first 200 chars): {prompt[:200]}"
        )

    return clean


# ---------------------------------------------------------------------------
# Output parser
# ---------------------------------------------------------------------------

_FILE_BLOCK = re.compile(
    r"<!--\s*FILE:\s*(?P<name>[^\s>]+)\s*-->(?P<content>.*?)<!--\s*END FILE\s*-->",
    re.DOTALL,
)


def parse_file_blocks(raw_output: str) -> dict[str, str]:
    """
    Extract <!-- FILE: name --> ... <!-- END FILE --> blocks from Claude output.
    Returns dict mapping filename → content.
    Raises CognitiveError if no blocks are found.
    """
    matches = _FILE_BLOCK.findall(raw_output)
    if not matches:
        snippet = raw_output[:300].strip()
        raise CognitiveError(
            f"Claude returned no parseable file blocks.\n"
            f"Raw output (first 300 chars): {snippet}"
        )
    return {name.strip(): content.strip() for name, content in matches}


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _read_file_safe(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _build_structure_workspace_prompt(
    slug: str,
    source_content: str,
    nlm_output: str,
    is_tutorial_hint: bool,
) -> str:
    existing_files = ""
    wdir = workspace_dir(slug)
    if wdir.exists():
        for fname in DEFAULT_WORKSPACE_FILES:
            fpath = wdir / fname
            if fpath.exists():
                existing_files += f"\n\n=== Existing: {fname} ===\n{_read_file_safe(fpath)}"

    tutorial_note = (
        "The source appears to be a tutorial/project-based resource. "
        "04_projekt_rebuild.md should explicitly describe what can be rebuilt."
        if is_tutorial_hint
        else "The source is NOT a tutorial. 04_projekt_rebuild.md should state 'Nicht anwendbar' with brief reasoning."
    )

    return f"""You are a German-language learning-package writer.
Your task: produce exactly 8 structured learning files in German for the slug "{slug}".

{tutorial_note}

SOURCE CONTENT:
{source_content}

NOTEBOOKLM OUTPUT:
{nlm_output}

{existing_files}

For each of the 8 files below, produce its complete content.
Use EXACTLY this delimiter format — no exceptions:

<!-- FILE: 00_zusammenfassung.md -->
...German content...
<!-- END FILE -->

<!-- FILE: 01_kernkonzepte.md -->
...German content...
<!-- END FILE -->

...and so on for all 8 files.

Files to produce:
1. 00_zusammenfassung.md — Executive summary + core thesis (German)
2. 01_kernkonzepte.md — Key concepts with definitions (German)
3. 02_schritt_fuer_schritt.md — Step-by-step walkthrough (German)
4. 03_uebungen.md — Flashcards + exercises (German)
5. 04_projekt_rebuild.md — Rebuild blueprint or "Nicht anwendbar" (German)
6. 05_offene_fragen.md — Open questions and uncertainties (German)
7. 06_notebooklm_artefakte.md — NLM notebook metadata and artifact paths (German)
8. 07_logik_check.md — Adversarial bias/assumption analysis (German)

Quality rules:
- Source-faithful first, interpretation second
- Mark uncertainties as "Unsicherheit"
- 07_logik_check.md must cover: confirmation bias, missing counter-perspectives, unstated assumptions, exaggerations, overall trust assessment
- No invented APIs, tools, or features

Return ONLY the 8 file blocks above. NO greetings, NO explanations, NO preamble outside the delimiters."""


def _build_logic_check_prompt(slug: str) -> str:
    wdir = workspace_dir(slug)
    content = ""
    for fname in ["00_zusammenfassung.md", "01_kernkonzepte.md", "02_schritt_fuer_schritt.md"]:
        fpath = wdir / fname
        if fpath.exists():
            content += f"\n\n=== {fname} ===\n{_read_file_safe(fpath)}"

    return f"""You are an adversarial critic performing a logic and bias check for slug "{slug}".

Existing workspace content:
{content}

Produce ONLY the following file:

<!-- FILE: 07_logik_check.md -->
# Logik-Check und Bias-Analyse

## Bestätigungsfehler (Confirmation Bias)
...

## Fehlende Gegenperspektiven
...

## Unausgesprochene Annahmen
...

## Übertreibungen und Vereinfachungen
...

## Gesamtbewertung (Vertrauensgrad)
...
<!-- END FILE -->

Return ONLY the file block above. NO greetings, NO explanations."""


def _build_vault_note_prompt(slug: str, workspace_files: dict[str, str], source_meta: dict[str, Any]) -> str:
    zusammenfassung = workspace_files.get("00_zusammenfassung.md", "")
    kernkonzepte = workspace_files.get("01_kernkonzepte.md", "")
    logik = workspace_files.get("07_logik_check.md", "")
    offene = workspace_files.get("05_offene_fragen.md", "")

    source_url = source_meta.get("input", "")
    source_label = source_meta.get("title", slug)
    source_type = source_meta.get("type", "unknown")

    return f"""You are writing an English research note for an Obsidian vault.

Source: {source_label}
URL: {source_url}
Type: {source_type}
Slug: {slug}

German workspace content:
=== 00_zusammenfassung.md ===
{zusammenfassung}

=== 01_kernkonzepte.md ===
{kernkonzepte}

=== 07_logik_check.md ===
{logik}

=== 05_offene_fragen.md ===
{offene}

Produce ONLY the following file:

<!-- FILE: vault_note_body.md -->
## Core Thesis
...

## Key Takeaways
...

## Executive Summary
...

## Practical Implications For My Workflow
...

## High-Signal Concepts To Revisit
...

## External Validation
...

## Open Questions
...

## Source Notes
...
<!-- END FILE -->

Rules:
- Write in English, analytical first-person tone
- Practical-implications-focused
- Use wikilinks for internal references: [[Note-Title]]
- DO NOT include YAML frontmatter (that will be added separately)

Return ONLY the file block above. NO greetings, NO explanations."""


# ---------------------------------------------------------------------------
# Public cognitive functions
# ---------------------------------------------------------------------------

def structure_workspace(slug: str) -> None:
    """
    Read source content + NLM output from disk, call Claude to write all
    8 workspace files. Writes files to workspace/{slug}/.
    Updates run.json: workspace.status = done.
    """
    sdir = source_dir(slug)
    wdir = workspace_dir(slug)
    wdir.mkdir(parents=True, exist_ok=True)

    state = load_state(slug)
    source_type = state["source"]["type"]

    # Find primary source content
    source_content = _load_source_content(sdir, source_type)

    # Find NLM output
    nlm_output = _load_nlm_output(sdir, state)

    # Tutorial hint from state (if already set) or simple heuristic
    is_tutorial_hint = state["workspace"].get("is_tutorial", False)

    prompt = _build_structure_workspace_prompt(slug, source_content, nlm_output, is_tutorial_hint)
    raw_output = run_claude(prompt)
    file_blocks = parse_file_blocks(raw_output)

    # Write workspace files
    for fname in DEFAULT_WORKSPACE_FILES:
        if fname in file_blocks:
            (wdir / fname).write_text(file_blocks[fname], encoding="utf-8")

    # Determine is_tutorial from 04_projekt_rebuild.md content
    rebuild_content = file_blocks.get("04_projekt_rebuild.md", "").lower()
    is_tutorial = "nicht anwendbar" not in rebuild_content and len(rebuild_content) > 100

    # Sync workspace state
    state = load_state(slug)
    generated = [f for f in DEFAULT_WORKSPACE_FILES if (wdir / f).exists()]
    state["workspace"]["generated_files"] = generated
    state["workspace"]["files_complete"] = len(generated) == len(DEFAULT_WORKSPACE_FILES)
    state["workspace"]["is_tutorial"] = is_tutorial
    state["workspace"]["status"] = "done"

    if is_tutorial:
        state["rebuild"]["status"] = "not_started"
        state["rebuild"]["reason"] = None
        state["next_recommended_step"] = "rebuild-project"
    else:
        state["rebuild"]["status"] = "skipped"
        state["rebuild"]["reason"] = "not_applicable"
        state["next_recommended_step"] = "fill-gaps"

    save_state(slug, state)


def run_logic_check(slug: str) -> None:
    """
    Read existing workspace files, call Claude for adversarial analysis,
    write 07_logik_check.md to workspace/{slug}/.
    """
    wdir = workspace_dir(slug)
    wdir.mkdir(parents=True, exist_ok=True)

    prompt = _build_logic_check_prompt(slug)
    raw_output = run_claude(prompt)
    file_blocks = parse_file_blocks(raw_output)

    if "07_logik_check.md" in file_blocks:
        (wdir / "07_logik_check.md").write_text(file_blocks["07_logik_check.md"], encoding="utf-8")
    else:
        raise CognitiveError("Claude did not return 07_logik_check.md block")


def generate_vault_note(slug: str) -> str:
    """
    Read workspace files, call Claude to produce English vault note body.
    Returns the note body as a string (does NOT write to Vault).
    """
    wdir = workspace_dir(slug)
    state = load_state(slug)

    workspace_files: dict[str, str] = {}
    for fname in DEFAULT_WORKSPACE_FILES:
        fpath = wdir / fname
        if fpath.exists():
            workspace_files[fname] = fpath.read_text(encoding="utf-8", errors="replace")

    prompt = _build_vault_note_prompt(slug, workspace_files, state["source"])
    raw_output = run_claude(prompt)
    file_blocks = parse_file_blocks(raw_output)

    body = file_blocks.get("vault_note_body.md")
    if not body:
        raise CognitiveError("Claude did not return vault_note_body.md block")
    return body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOURCE_CONTENT_CANDIDATES: dict[str, list[str]] = {
    "youtube": ["*.txt", "*.srt"],
    "web": ["content.md", "content.txt"],
    "pdf": ["content.md", "content.txt", "*.pdf"],
    "local": ["*.md", "*.txt"],
}


def _load_source_content(sdir: Path, source_type: str) -> str:
    patterns = _SOURCE_CONTENT_CANDIDATES.get(source_type, ["*.md", "*.txt"])
    for pattern in patterns:
        if "*" in pattern:
            matches = [
                f for f in sdir.glob(pattern)
                if f.name not in ("metadata.tsv",)
                and "extra_context" not in f.name
                and "nlm-" not in f.name
            ]
            if matches:
                best = min(matches, key=lambda f: len(f.name))
                return best.read_text(encoding="utf-8", errors="replace")
        else:
            candidate = sdir / pattern
            if candidate.exists():
                return candidate.read_text(encoding="utf-8", errors="replace")
    return "[No source content found]"


def _load_nlm_output(sdir: Path, state: dict[str, Any]) -> str:
    artifacts: list[str] = state.get("notebooklm", {}).get("artifacts", [])
    for artifact_name in artifacts:
        candidate = sdir / artifact_name
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="replace")
    # Fallback: find any nlm-* file
    nlm_files = list(sdir.glob("nlm-*.md"))
    if nlm_files:
        return nlm_files[0].read_text(encoding="utf-8", errors="replace")
    return "[No NotebookLM output found]"


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class CognitiveError(RuntimeError):
    pass
