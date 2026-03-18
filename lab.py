#!/usr/bin/env python3
"""
lab.py — Learning-lab headless pipeline runner.

This is the single entry point for running the learning-lab pipeline
from the command line. Python handles all deterministic work;
Claude is invoked only for cognitive subroutines.

Usage:
    python lab.py <source_or_slug> [options]

Examples:
    python lab.py https://www.youtube.com/watch?v=xyz --verbose
    python lab.py https://example.com/article --full-pipeline --auto
    python lab.py my-existing-slug --fill-gaps --vault
    python lab.py https://... --stage ingest
    python lab.py my-slug --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path so app.* and scripts.* resolve
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.ingest import detect_source_type, derive_slug  # noqa: E402
from app.orchestrator import OrchestratorConfig, run  # noqa: E402
from app.config import state_path  # noqa: E402


VALID_STAGES = ("ingest", "notebooklm", "workspace", "rebuild", "fill-gaps", "vault")
VALID_DELIVERABLES = ("study_guide", "flashcards", "infographic", "mindmap", "podcast", "slides")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab",
        description="learning-lab headless pipeline runner. Python orchestrates, Claude thinks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python lab.py https://www.youtube.com/watch?v=xyz --verbose
  python lab.py https://example.com/article --full-pipeline --auto
  python lab.py gsd2-vs-claude-code --fill-gaps --vault
  python lab.py https://... --stage ingest --verbose
  python lab.py my-slug --dry-run
        """,
    )
    parser.add_argument(
        "source",
        help=(
            "YouTube URL, web URL, PDF path, local file path, "
            "or an existing slug to resume from"
        ),
    )
    parser.add_argument(
        "--deliverable",
        default="study_guide",
        choices=VALID_DELIVERABLES,
        help="NotebookLM deliverable type (default: study_guide)",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="Override slug/topic label (used for folder naming)",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Human-readable title for the source (stored in run.json)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Include rebuild stage if source is a tutorial",
    )
    parser.add_argument(
        "--fill-gaps",
        dest="fill_gaps",
        action="store_true",
        help="Include fill-gaps stage (web research on open questions)",
    )
    parser.add_argument(
        "--vault",
        action="store_true",
        help="Include vault export stage",
    )
    parser.add_argument(
        "--full-pipeline",
        dest="full_pipeline",
        action="store_true",
        help="Run all stages end-to-end (implies --rebuild --fill-gaps --vault)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help=(
            "Non-interactive: set auto_mode=true in run.json, skip all confirmation prompts. "
            "Blocks if a vault note already exists with a different identity."
        ),
    )
    parser.add_argument(
        "--stage",
        default=None,
        choices=VALID_STAGES,
        metavar="STAGE",
        help=f"Run only a specific stage: {{{', '.join(VALID_STAGES)}}}",
    )
    parser.add_argument(
        "--force-reingest",
        dest="force_reingest",
        action="store_true",
        help="Re-run ingest even if it is already marked done",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print stage-by-stage progress to stdout",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Show what stages would run without executing them",
    )
    return parser


def _is_existing_slug(source: str) -> bool:
    """Return True if source looks like an existing slug (run.json exists)."""
    # A slug has no slashes, dots (as path separators), or URL schemes
    if "://" in source or "/" in source or source.endswith(".pdf"):
        return False
    return state_path(source).exists()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_input = args.source

    # Determine if this is a resume (existing slug) or a new source
    if _is_existing_slug(source_input):
        slug = source_input
        # Load source type from existing state
        try:
            from app.config import load_state
            existing = load_state(slug)
            source_type = existing["source"]["type"]
            resolved_source = existing["source"]["input"]
        except Exception as exc:
            print(f"[lab] ERROR loading existing state for '{slug}': {exc}", file=sys.stderr)
            return 1
    else:
        resolved_source = source_input
        source_type = detect_source_type(source_input)
        slug = derive_slug(source_input, args.topic)

    if args.verbose or args.dry_run:
        mode = "(dry-run)" if args.dry_run else ""
        print(f"[lab] {mode} slug={slug}  source_type={source_type}  next_stage=auto")

    config = OrchestratorConfig(
        slug=slug,
        source_input=resolved_source,
        source_type=source_type,
        deliverable=args.deliverable,
        topic=args.topic,
        title=args.title,
        include_rebuild=args.rebuild,
        include_fill_gaps=args.fill_gaps,
        include_vault=args.vault,
        full_pipeline=args.full_pipeline,
        auto_mode=args.auto,
        force_reingest=args.force_reingest,
        verbose=args.verbose,
        dry_run=args.dry_run,
        specific_stage=args.stage,
    )

    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
