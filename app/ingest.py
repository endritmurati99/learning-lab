"""
app/ingest.py — Deterministic source ingestion.

Handles source type detection, slug derivation, and per-type ingest
(YouTube, web, PDF, local). Each ingest function updates run.json
directly via load_state/save_state — no subprocess calls to run_state.py.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.config import (
    ROOT,
    default_state,
    load_state,
    save_state,
    source_dir,
    state_path,
    atomic_write_json,
)


# ---------------------------------------------------------------------------
# Source type detection
# ---------------------------------------------------------------------------

def detect_source_type(source: str) -> str:
    """Return 'youtube' | 'web' | 'pdf' | 'local'."""
    low = source.lower()
    if "youtube.com" in low or "youtu.be" in low:
        return "youtube"
    if low.startswith("http://") or low.startswith("https://"):
        return "web"
    if low.endswith(".pdf"):
        return "pdf"
    return "local"


def derive_slug(source: str, topic: str | None = None) -> str:
    """
    Derive a sanitized slug from the topic or source URL/path.
    Rules: lowercase, hyphenated, no special chars, max 60 chars.
    """
    base = topic or source
    # Strip URL scheme
    base = re.sub(r"^https?://", "", base)
    # Strip query strings and fragments
    base = re.sub(r"[?#].*$", "", base)
    # Strip common domain suffixes if it looks like a URL
    base = re.sub(r"^(?:www\.|youtu\.be/|youtube\.com/watch\?v=)", "", base)
    # Replace non-alphanumeric runs with hyphens
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base)
    # Lowercase and strip leading/trailing hyphens
    base = base.lower().strip("-")
    # Truncate
    return base[:60]


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _init_state_if_missing(slug: str, source_type: str, source_input: str, title: str) -> dict[str, Any]:
    """Load existing state or create a fresh one on disk."""
    path = state_path(slug)
    if path.exists():
        return load_state(slug)
    state = default_state(source_type, source_input, slug, title)
    source_dir(slug).mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, state)
    return state


def _append_artifact(state: dict[str, Any], stage: str, field: str, value: str) -> None:
    """Append a value to a list field in state if not already present."""
    lst: list[str] = state[stage][field]
    if value not in lst:
        lst.append(value)


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------

def _run(cmd: list[str], log_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    """
    Run a subprocess. Append stderr to log_path if provided.
    Raises IngestError on non-zero exit.
    """
    with open(log_path, "a", encoding="utf-8") if log_path else _null_context() as log_fh:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=log_fh if log_path else subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
    if result.returncode != 0:
        stderr_snippet = (result.stderr or "")[:400]
        raise IngestError(
            f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n{stderr_snippet}"
        )
    return result


class _null_context:
    """No-op context manager used when log_path is None."""
    def __enter__(self) -> None:
        return None
    def __exit__(self, *_: object) -> None:
        pass


# ---------------------------------------------------------------------------
# SRT → plain text conversion
# ---------------------------------------------------------------------------

def _srt_to_txt(srt_path: Path, txt_path: Path) -> None:
    """Strip SRT timing lines and sequence numbers, write plain text."""
    srt_text = srt_path.read_text(encoding="utf-8", errors="replace")
    lines: list[str] = []
    for line in srt_text.splitlines():
        line = line.strip()
        # Skip sequence numbers and timing lines
        if re.match(r"^\d+$", line):
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*", line):
            continue
        if line:
            lines.append(line)
    txt_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# YouTube ingest
# ---------------------------------------------------------------------------

def ingest_youtube(slug: str, url: str, title: str | None = None) -> list[str]:
    """
    Run yt-dlp to download metadata, subtitles (with audio fallback),
    and extra context. Updates run.json status throughout.
    Returns list of artifact filenames created in sources/{slug}/.
    """
    sdir = source_dir(slug)
    sdir.mkdir(parents=True, exist_ok=True)
    log_path = sdir / "ingest.log"
    state = _init_state_if_missing(slug, "youtube", url, title or slug)

    state["ingest"]["status"] = "in_progress"
    state["next_recommended_step"] = "ingest"
    save_state(slug, state)

    artifacts: list[str] = []
    warnings: list[str] = []

    # --- Metadata ---
    meta_path = sdir / "metadata.tsv"
    try:
        result = subprocess.run(
            [
                "yt-dlp", url,
                "--skip-download",
                "--print", "%(id)s\t%(title)s\t%(webpage_url)s\t%(view_count)s\t%(upload_date)s",
                "--no-playlist",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        meta_path.write_text(result.stdout, encoding="utf-8")
        if result.returncode != 0:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(result.stderr)
        artifacts.append("metadata.tsv")
    except FileNotFoundError:
        raise IngestError("yt-dlp is not installed or not in PATH")

    # --- Subtitles ---
    subtitle_ok = False
    try:
        sub_result = subprocess.run(
            [
                "yt-dlp", url,
                "--skip-download",
                "--write-auto-sub", "--write-sub",
                "--sub-lang", "en",
                "--sub-format", "ttml",
                "--convert-subs", "srt",
                "--no-playlist",
                "-o", str(sdir / "%(id)s.%(ext)s"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(sub_result.stderr)

        srt_files = list(sdir.glob("*.srt"))
        if srt_files:
            subtitle_ok = True
            srt_path = srt_files[0]
            txt_path = sdir / f"{srt_path.stem}.txt"
            _srt_to_txt(srt_path, txt_path)
            artifacts.append(srt_path.name)
            artifacts.append(txt_path.name)
        else:
            warnings.append("no_subtitles_downloaded")
    except Exception as exc:
        warnings.append(f"subtitle_download_error: {exc}")

    # --- Audio fallback ---
    if not subtitle_ok:
        if shutil.which("buzz"):
            try:
                _run(
                    ["yt-dlp", url, "-x", "--audio-format", "mp3",
                     "-o", str(sdir / "audio.%(ext)s")],
                    log_path,
                )
                audio_path = sdir / "audio.mp3"
                if audio_path.exists():
                    _run(
                        ["buzz", "add", "--task", "transcribe",
                         "--model", "medium", "--output-format", "srt",
                         str(audio_path)],
                        log_path,
                    )
                    buzz_srt = sdir / "audio.srt"
                    if buzz_srt.exists():
                        txt_path = sdir / "audio.txt"
                        _srt_to_txt(buzz_srt, txt_path)
                        artifacts.extend(["audio.mp3", "audio.srt", "audio.txt"])
                        subtitle_ok = True
            except IngestError as exc:
                warnings.append(f"buzz_fallback_failed: {exc}")
        else:
            warnings.append("buzz_missing_for_audio_fallback")

    # --- Extra context (description, info) ---
    try:
        subprocess.run(
            [
                "yt-dlp", url,
                "--write-description", "--write-info-json",
                "--skip-download",
                "-o", str(sdir / "extra_context.%(ext)s"),
            ],
            stdout=subprocess.PIPE,
            stderr=open(log_path, "a", encoding="utf-8"),
            text=True,
            encoding="utf-8",
        )
        for ext in ("description", "info.json"):
            candidate = sdir / f"extra_context.{ext}"
            if candidate.exists():
                artifacts.append(candidate.name)
    except Exception:
        warnings.append("extra_context_download_failed")

    # Record log file
    if log_path.exists():
        if "ingest.log" not in artifacts:
            pass  # log files tracked separately

    # Update state
    state = load_state(slug)
    for art in artifacts:
        _append_artifact(state, "ingest", "artifacts", art)
    for w in warnings:
        _append_artifact(state, "ingest", "warnings", w)
    if log_path.exists():
        _append_artifact(state, "ingest", "log_files", "ingest.log")
    state["ingest"]["status"] = "done"
    state["notebooklm"]["status"] = "in_progress"
    state["next_recommended_step"] = "notebooklm"
    save_state(slug, state)

    return artifacts


# ---------------------------------------------------------------------------
# Web ingest
# ---------------------------------------------------------------------------

def ingest_web(slug: str, url: str, title: str | None = None) -> list[str]:
    """Run defuddle to extract clean markdown from a web page."""
    sdir = source_dir(slug)
    sdir.mkdir(parents=True, exist_ok=True)
    log_path = sdir / "ingest.log"
    state = _init_state_if_missing(slug, "web", url, title or slug)

    state["ingest"]["status"] = "in_progress"
    save_state(slug, state)

    artifacts: list[str] = []

    # Content
    content_path = sdir / "content.md"
    try:
        result = subprocess.run(
            ["defuddle", "parse", url, "--md"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        content_path.write_text(result.stdout, encoding="utf-8")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(result.stderr)
        if result.returncode != 0:
            raise IngestError(f"defuddle failed (exit {result.returncode}): {result.stderr[:200]}")
        artifacts.append("content.md")
    except FileNotFoundError:
        raise IngestError("defuddle is not installed or not in PATH")

    # Title
    try:
        t = subprocess.run(
            ["defuddle", "parse", url, "-p", "title"],
            capture_output=True, text=True, encoding="utf-8",
        )
        title_path = sdir / "title.txt"
        title_path.write_text(t.stdout.strip(), encoding="utf-8")
        artifacts.append("title.txt")
    except Exception:
        pass

    state = load_state(slug)
    for art in artifacts:
        _append_artifact(state, "ingest", "artifacts", art)
    if log_path.exists():
        _append_artifact(state, "ingest", "log_files", "ingest.log")
    state["ingest"]["status"] = "done"
    state["notebooklm"]["status"] = "in_progress"
    state["next_recommended_step"] = "notebooklm"
    save_state(slug, state)

    return artifacts


# ---------------------------------------------------------------------------
# PDF ingest
# ---------------------------------------------------------------------------

def ingest_pdf(slug: str, path: str, title: str | None = None) -> list[str]:
    """Convert PDF to markdown via pandoc (falls back to direct copy)."""
    sdir = source_dir(slug)
    sdir.mkdir(parents=True, exist_ok=True)
    state = _init_state_if_missing(slug, "pdf", path, title or Path(path).stem)

    state["ingest"]["status"] = "in_progress"
    save_state(slug, state)

    artifacts: list[str] = []
    src = Path(path)
    if not src.exists():
        raise IngestError(f"PDF file not found: {path}")

    # Try pandoc first
    content_path = sdir / "content.md"
    if shutil.which("pandoc"):
        result = subprocess.run(
            ["pandoc", str(src), "-t", "markdown", "-o", str(content_path)],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode == 0 and content_path.exists():
            artifacts.append("content.md")
        else:
            # Pandoc failed — copy raw
            dest = sdir / src.name
            shutil.copy2(str(src), str(dest))
            artifacts.append(src.name)
            state["ingest"]["warnings"].append("pandoc_conversion_failed")
    else:
        # No pandoc — copy raw PDF
        dest = sdir / src.name
        shutil.copy2(str(src), str(dest))
        artifacts.append(src.name)
        state["ingest"]["warnings"].append("pandoc_missing_raw_copy_used")

    state = load_state(slug)
    for art in artifacts:
        _append_artifact(state, "ingest", "artifacts", art)
    state["ingest"]["status"] = "done"
    state["notebooklm"]["status"] = "in_progress"
    state["next_recommended_step"] = "notebooklm"
    save_state(slug, state)

    return artifacts


# ---------------------------------------------------------------------------
# Local file ingest
# ---------------------------------------------------------------------------

def ingest_local(slug: str, path: str, title: str | None = None) -> list[str]:
    """Copy a local .md / .txt file into sources/{slug}/."""
    sdir = source_dir(slug)
    sdir.mkdir(parents=True, exist_ok=True)
    src = Path(path)
    if not src.exists():
        raise IngestError(f"Local file not found: {path}")

    state = _init_state_if_missing(slug, "local", path, title or src.stem)
    state["ingest"]["status"] = "in_progress"
    save_state(slug, state)

    dest = sdir / src.name
    shutil.copy2(str(src), str(dest))

    state = load_state(slug)
    _append_artifact(state, "ingest", "artifacts", src.name)
    state["ingest"]["status"] = "done"
    state["notebooklm"]["status"] = "in_progress"
    state["next_recommended_step"] = "notebooklm"
    save_state(slug, state)

    return [src.name]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def run_ingest(slug: str, source: str, title: str | None = None) -> list[str]:
    """Detect source type and dispatch to the appropriate ingest function."""
    source_type = detect_source_type(source)
    if source_type == "youtube":
        return ingest_youtube(slug, source, title)
    if source_type == "web":
        return ingest_web(slug, source, title)
    if source_type == "pdf":
        return ingest_pdf(slug, source, title)
    return ingest_local(slug, source, title)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class IngestError(RuntimeError):
    pass
