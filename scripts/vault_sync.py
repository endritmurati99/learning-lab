from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / ".claude" / "settings.json"
TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".toml", ".yaml", ".yml", ".tsv"}
PROJECT_FILE_SUFFIXES = {".md", ".txt", ".json", ".py", ".toml", ".yaml", ".yml"}
CANONICAL_DIRECT_NAMES = {
    "metadata.tsv": "metadata.tsv",
    "notebook_id.txt": "notebook_id.txt",
}
FLAT_SUFFIXES = [
    "-transcript.txt",
    "-study-guide.md",
    "-nlm-flashcards.md",
    "-nlm-mindmap.json",
    "-nlm-report.md",
    "-nlm-slides.pdf",
]
PRIMARY_CONTENT_CANDIDATES = {
    "youtube": ("transcript.txt",),
    "web": ("content.md", "content.txt", "transcript.txt"),
    "pdf": ("content.md", "content.txt", "transcript.txt"),
    "source": ("content.md", "content.txt", "transcript.txt"),
}


class VaultSyncError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ExportResult:
    note_path: str
    bundle_path: str
    project_bundle_path: str | None
    daily_note_path: str
    draft_title: str
    export_identity: dict[str, Any]
    last_exported_at: str


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def settings() -> dict[str, Any]:
    return load_json(SETTINGS_PATH)


def vault_root() -> Path:
    configured = settings().get("vault_path")
    if not configured:
        raise VaultSyncError("vault_missing", f"vault_path missing in {SETTINGS_PATH}")
    root = Path(configured).resolve()
    if not root.exists():
        raise VaultSyncError("vault_missing", f"Vault path does not exist: {root}")
    return root


def research_root(vault: Path) -> Path:
    return vault / "research"


def assets_root(vault: Path) -> Path:
    return research_root(vault) / "assets"


def daily_root(vault: Path) -> Path:
    return vault / "daily-notes"


def load_run(slug: str) -> dict[str, Any]:
    return load_json(ROOT / "sources" / slug / "run.json")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "untitled"


def infer_source_type_from_url(url: str | None) -> str:
    if not url:
        return "source"
    lowered = url.lower()
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return "youtube"
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return "web"
    return "source"


def infer_slug_from_asset_name(asset_name: str) -> str | None:
    lowered = asset_name.lower()
    for suffix in FLAT_SUFFIXES:
        if lowered.endswith(suffix):
            return lowered[: -len(suffix)]
    return None


def relative_to_vault(path: Path) -> str:
    return path.relative_to(vault_root()).as_posix()


def parse_note_source_url(text: str) -> str | None:
    frontmatter_match = re.search(r"source_url:\s*\"([^\"]+)\"", text)
    if frontmatter_match:
        return frontmatter_match.group(1)
    source_match = re.search(r"> Source: \[[^\]]+\]\(([^)]+)\)", text)
    if source_match:
        return source_match.group(1)
    return None


def parse_note_export_identity(text: str) -> str | None:
    match = re.search(r"export_identity:\s*\"?([^\n\"]+)\"?", text)
    return match.group(1).strip() if match else None


def build_export_identity(source_type: str, source_slug: str, source_fingerprint: str) -> str:
    return f"{source_type}:{source_slug}:{source_fingerprint}"


def ensure_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[4:end], text[end + 5 :]
    return "", text


def upsert_frontmatter_field(frontmatter: str, key: str, rendered_value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:\s*.*$", flags=re.MULTILINE)
    replacement = f"{key}: {rendered_value}"
    if pattern.search(frontmatter):
        return pattern.sub(replacement, frontmatter)
    frontmatter = frontmatter.rstrip()
    if frontmatter:
        return frontmatter + "\n" + replacement + "\n"
    return replacement + "\n"


def stamp_note_metadata(
    note_text: str,
    *,
    source_url: str | None,
    source_label: str,
    source_type: str,
    source_slug: str,
    bundle_path: str,
    transcript_path: str,
    project_bundle_path: str | None,
    draft_status: str,
    export_identity: str,
) -> str:
    frontmatter, body = ensure_frontmatter(note_text)
    frontmatter = upsert_frontmatter_field(frontmatter, "research_date", date.today().isoformat())
    if source_url:
        frontmatter = upsert_frontmatter_field(frontmatter, "source_url", json.dumps(source_url))
    frontmatter = upsert_frontmatter_field(frontmatter, "source_label", json.dumps(source_label))
    frontmatter = upsert_frontmatter_field(frontmatter, "source_type", json.dumps(source_type))
    frontmatter = upsert_frontmatter_field(frontmatter, "source_slug", json.dumps(source_slug))
    frontmatter = upsert_frontmatter_field(frontmatter, "transcript", json.dumps(f"[[{transcript_path}]]"))
    frontmatter = upsert_frontmatter_field(frontmatter, "asset_bundle", json.dumps(f"[[{bundle_path}/Source Bundle]]"))
    if project_bundle_path:
        frontmatter = upsert_frontmatter_field(frontmatter, "project_bundle", json.dumps(f"[[{project_bundle_path}/Project Note]]"))
    frontmatter = upsert_frontmatter_field(frontmatter, "draft_status", draft_status)
    frontmatter = upsert_frontmatter_field(frontmatter, "export_identity", json.dumps(export_identity))
    if "external_validation:" not in frontmatter:
        frontmatter = upsert_frontmatter_field(frontmatter, "external_validation", "false")
    return f"---\n{frontmatter.rstrip()}\n---\n{body.lstrip()}"


def bundle_dir(vault: Path, source_type: str, source_slug: str) -> Path:
    return assets_root(vault) / source_type / source_slug


def note_path_for_title(vault: Path, note_title: str) -> Path:
    return research_root(vault) / f"{note_title}.md"


def daily_note_path(vault: Path) -> Path:
    return daily_root(vault) / f"{date.today().isoformat()}.md"


def daily_marker(source_type: str, source_slug: str) -> str:
    return f"<!-- learning-lab:{source_type}:{source_slug} -->"


def canonical_asset_name(source_path: Path) -> tuple[Path, str]:
    lowered = source_path.name.lower()
    if lowered in CANONICAL_DIRECT_NAMES:
        return Path(CANONICAL_DIRECT_NAMES[lowered]), CANONICAL_DIRECT_NAMES[lowered]
    if lowered.endswith(".en.srt") or lowered.endswith(".srt"):
        return Path("transcript.srt"), "transcript.srt"
    if lowered.endswith("-transcript.txt") or lowered == "transcript.txt":
        return Path("transcript.txt"), "transcript.txt"
    if lowered.endswith(".txt") and not lowered.startswith("ingest") and not lowered.startswith("notebook"):
        return Path("transcript.txt"), "transcript.txt"
    if "study-guide" in lowered:
        return Path("study-guide.md"), "study-guide.md"
    if "flashcards" in lowered:
        return Path("nlm-flashcards.md"), "nlm-flashcards.md"
    if "mindmap" in lowered:
        return Path("nlm-mindmap.json"), "nlm-mindmap.json"
    if "slides" in lowered:
        return Path("nlm-slides.pdf"), "nlm-slides.pdf"
    if "report" in lowered:
        return Path("nlm-report.md"), "nlm-report.md"
    if source_path.suffix.lower() in TEXT_SUFFIXES:
        return Path("attachments") / source_path.name, f"attachments/{source_path.name}"
    return Path("attachments") / source_path.name, f"attachments/{source_path.name}"


def collect_source_assets(run_data: dict[str, Any]) -> list[Path]:
    slug = run_data["source"]["slug"]
    source_root = ROOT / "sources" / slug
    paths: list[Path] = []
    for rel in run_data.get("ingest", {}).get("artifacts", []):
        paths.append(source_root / rel)
    for rel in run_data.get("ingest", {}).get("log_files", []):
        paths.append(source_root / rel)
    for rel in run_data.get("notebooklm", {}).get("artifacts", []):
        paths.append(source_root / rel)
    notebook_id = source_root / "notebook_id.txt"
    if notebook_id.exists():
        paths.append(notebook_id)

    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def normalized_primary_text(run_data: dict[str, Any]) -> str:
    slug = run_data["source"]["slug"]
    source_type = run_data["source"]["type"]
    source_root = ROOT / "sources" / slug
    candidates = list(PRIMARY_CONTENT_CANDIDATES.get(source_type, PRIMARY_CONTENT_CANDIDATES["source"]))

    for artifact in collect_source_assets(run_data):
        _, canonical_name = canonical_asset_name(artifact)
        if canonical_name not in candidates:
            continue
        if artifact.exists():
            text = artifact.read_text(encoding="utf-8", errors="replace")
            normalized_lines = [" ".join(line.split()) for line in text.splitlines()]
            normalized = "\n".join(line for line in normalized_lines if line).strip()
            if normalized:
                return normalized

    for candidate in candidates:
        candidate_path = source_root / candidate
        if candidate_path.exists():
            text = candidate_path.read_text(encoding="utf-8", errors="replace")
            normalized_lines = [" ".join(line.split()) for line in text.splitlines()]
            normalized = "\n".join(line for line in normalized_lines if line).strip()
            if normalized:
                return normalized

    raise VaultSyncError("missing_primary_content", f"No primary normalized content found for slug '{slug}'")


def source_fingerprint(run_data: dict[str, Any]) -> str:
    normalized = normalized_primary_text(run_data)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def write_source_bundle(
    target_dir: Path,
    source_type: str,
    source_slug: str,
    note_title: str,
    source_url: str | None,
) -> None:
    asset_files = sorted(path for path in target_dir.rglob("*") if path.is_file() and path.name != "Source Bundle.md")
    lines = [
        "# Source Bundle",
        "",
        f"- Source type: `{source_type}`",
        f"- Source slug: `{source_slug}`",
        f"- Research note: [[{note_title}]]",
    ]
    if source_url:
        lines.append(f"- Source URL: {source_url}")
    lines.extend(["", "## Assets", ""])
    for asset_path in asset_files:
        rel = asset_path.relative_to(vault_root()).as_posix()
        lines.append(f"- [[{rel}]]")
    lines.append("")
    write_text(target_dir / "Source Bundle.md", "\n".join(lines))


def ensure_text_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def ensure_note_identity_or_raise(note_path: Path, export_identity: str) -> None:
    if not note_path.exists():
        return
    current = parse_note_export_identity(note_path.read_text(encoding="utf-8"))
    if current == export_identity:
        return
    raise VaultSyncError("note_path_collision", f"Vault note path already exists with different export identity: {note_path}")


def update_daily_note(vault: Path, note_title: str, main_insight: str, source_type: str, source_slug: str, status: str) -> Path:
    note_path = daily_note_path(vault)
    marker = daily_marker(source_type, source_slug)
    block = "\n".join(
        [
            marker,
            f"- [{status}] [[{note_title}]]",
            f"- Main insight: {main_insight}",
        ]
    )

    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
    else:
        existing = f"# {date.today().isoformat()}\n\n## Research\n"

    if "## Research" not in existing:
        existing = existing.rstrip() + "\n\n## Research\n"

    marker_pattern = re.compile(rf"{re.escape(marker)}\n- \[[^\]]+\] \[\[[^\]]+\]\]\n- Main insight: .*(?:\n|$)")
    if marker_pattern.search(existing):
        updated = marker_pattern.sub(block + "\n", existing)
    else:
        updated = existing.rstrip() + "\n" + block + "\n"

    write_text(note_path, updated.rstrip() + "\n")
    return note_path


def top_level_project_files(project_root: Path) -> list[Path]:
    allowed: list[Path] = []
    for path in project_root.iterdir():
        if path.is_dir():
            continue
        if path.name.startswith("README"):
            allowed.append(path)
            continue
        if path.suffix.lower() in PROJECT_FILE_SUFFIXES:
            allowed.append(path)
    return sorted(allowed)


def copy_filtered_tree(source_dir: Path, target_dir: Path, allow_suffixes: set[str]) -> None:
    if not source_dir.exists():
        return
    for path in source_dir.rglob("*"):
        if path.is_dir():
            continue
        if "__pycache__" in path.parts or ".venv" in path.parts or "venv" in path.parts:
            continue
        if path.suffix.lower() not in allow_suffixes:
            continue
        ensure_text_copy(path, target_dir / path.relative_to(source_dir))


def export_project_mirror(
    run_data: dict[str, Any],
    project_slug: str,
    project_title: str,
    note_title: str,
) -> Path | None:
    if run_data.get("rebuild", {}).get("status") != "done":
        return None
    project_path_value = run_data.get("rebuild", {}).get("project_path")
    if not project_path_value:
        return None

    local_project_dir = (ROOT / project_path_value).resolve()
    if not local_project_dir.exists():
        raise VaultSyncError("project_mirror_scope_violation", f"Local project path missing: {local_project_dir}")

    vault = vault_root()
    target_root = vault / "projects" / project_slug
    target_root.mkdir(parents=True, exist_ok=True)

    for source_path in top_level_project_files(local_project_dir):
        ensure_text_copy(source_path, target_root / "code" / source_path.name)

    for subdir_name in ("docs", "src", "tests"):
        copy_filtered_tree(local_project_dir / subdir_name, target_root / "code" / subdir_name, PROJECT_FILE_SUFFIXES)

    generated_root = local_project_dir / "generated" / ".claude" / "skills"
    if generated_root.exists():
        for skill_dir in generated_root.iterdir():
            if not skill_dir.is_dir():
                continue
            copy_filtered_tree(skill_dir, target_root / "example-output" / skill_dir.name, PROJECT_FILE_SUFFIXES)

    project_note = "\n".join(
        [
            "# Project Note",
            "",
            f"- Title: {project_title}",
            f"- Related research: [[{note_title}]]",
            f"- Local project path: `{local_project_dir}`",
            "",
            "## Contents",
            "",
            "- `code/` mirrors allowlisted project files for reading in Obsidian.",
            "- `example-output/` contains small, text-only generated examples when available.",
            "",
            "## Scope",
            "",
            "- Included: README, docs, src, tests, small text artifacts",
            "- Excluded: binaries, builds, caches, secrets, environments",
            "",
        ]
    )
    write_text(target_root / "Project Note.md", project_note)
    return target_root


def read_note_body(note_body_file: Path | None) -> str:
    if note_body_file is None:
        raise VaultSyncError("missing_note_body", "export-draft requires --note-body-file for first draft creation")
    return note_body_file.read_text(encoding="utf-8")


def export_draft(
    slug: str,
    note_title: str,
    note_body_file: Path | None,
    main_insight: str,
    project_slug: str | None,
    project_title: str | None,
) -> ExportResult:
    vault = vault_root()
    run_data = load_run(slug)
    source_type = run_data["source"]["type"]
    source_slug = run_data["source"]["slug"]
    source_url = run_data["source"].get("input")
    fingerprint = source_fingerprint(run_data)
    export_identity = {
        "source_type": source_type,
        "source_slug": source_slug,
        "project_slug": project_slug,
        "source_fingerprint": fingerprint,
    }
    export_identity_string = build_export_identity(source_type, source_slug, fingerprint)

    note_path = note_path_for_title(vault, note_title)
    existing_note_path_value = run_data.get("vault", {}).get("note_path")
    if existing_note_path_value:
        existing_note_path = Path(existing_note_path_value)
        note_path = existing_note_path if existing_note_path.is_absolute() else vault / existing_note_path

    ensure_note_identity_or_raise(note_path, export_identity_string)

    bundle_root = bundle_dir(vault, source_type, source_slug)
    bundle_root.mkdir(parents=True, exist_ok=True)
    for source_path in collect_source_assets(run_data):
        target_rel_path, _ = canonical_asset_name(source_path)
        ensure_text_copy(source_path, bundle_root / target_rel_path)
    write_source_bundle(bundle_root, source_type, source_slug, note_title, source_url)

    project_bundle_root = None
    if project_slug and project_title:
        project_bundle_root = export_project_mirror(run_data, project_slug, project_title, note_title)

    note_body = read_note_body(note_body_file) if (note_body_file or not note_path.exists()) else note_path.read_text(encoding="utf-8")
    note_body = stamp_note_metadata(
        note_body,
        source_url=source_url,
        source_label=run_data["source"].get("title", source_slug),
        source_type=source_type,
        source_slug=source_slug,
        bundle_path=relative_to_vault(bundle_root),
        transcript_path=f"{relative_to_vault(bundle_root)}/transcript.txt",
        project_bundle_path=relative_to_vault(project_bundle_root) if project_bundle_root else None,
        draft_status="draft_prepared",
        export_identity=export_identity_string,
    )
    write_text(note_path, note_body)

    daily_path = update_daily_note(vault, note_title, main_insight, source_type, source_slug, "draft")

    return ExportResult(
        note_path=relative_to_vault(note_path),
        bundle_path=relative_to_vault(bundle_root),
        project_bundle_path=relative_to_vault(project_bundle_root) if project_bundle_root else None,
        daily_note_path=relative_to_vault(daily_path),
        draft_title=note_title,
        export_identity=export_identity,
        last_exported_at=utc_now(),
    )


def ensure_bundle_line(note_text: str, source_type: str, slug: str) -> str:
    bundle = f"> Asset Bundle: [[research/assets/{source_type}/{slug}/Source Bundle]]"
    if bundle in note_text:
        return note_text
    transcript_line = re.search(r"^> Transcript: .*$", note_text, flags=re.MULTILINE)
    if transcript_line:
        insert_at = transcript_line.end()
        return note_text[:insert_at] + "\n" + bundle + note_text[insert_at:]
    source_line = re.search(r"^> Source: .*$", note_text, flags=re.MULTILINE)
    if source_line:
        insert_at = source_line.end()
        return note_text[:insert_at] + "\n" + bundle + note_text[insert_at:]
    return bundle + "\n\n" + note_text


def gather_migration_operations(vault: Path) -> list[dict[str, str]]:
    operations: list[dict[str, str]] = []
    flat_assets_dir = assets_root(vault)
    for note_path in sorted(research_root(vault).glob("*.md")):
        note_text = note_path.read_text(encoding="utf-8")
        source_type = infer_source_type_from_url(parse_note_source_url(note_text))
        for asset_rel in re.findall(r"\[\[research/assets/([^\]]+)\]\]", note_text):
            asset_parts = Path(asset_rel).parts
            if len(asset_parts) > 1:
                continue
            flat_name = asset_parts[0]
            slug = infer_slug_from_asset_name(flat_name)
            if not slug:
                continue
            source = flat_assets_dir / flat_name
            target_rel, _ = canonical_asset_name(Path(flat_name))
            target = bundle_dir(vault, source_type, slug) / target_rel
            operations.append(
                {
                    "note": str(note_path),
                    "old_link": f"[[research/assets/{flat_name}]]",
                    "new_link": f"[[research/assets/{source_type}/{slug}/{target_rel.as_posix()}]]",
                    "source": str(source),
                    "target": str(target),
                    "source_type": source_type,
                    "source_slug": slug,
                }
            )
    return operations


def backup_targets(operations: list[dict[str, str]], backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    seen_files: set[Path] = set()
    for operation in operations:
        for raw_path in (operation["note"], operation["source"]):
            path = Path(raw_path)
            if not path.exists() or path in seen_files:
                continue
            seen_files.add(path)
            relative = path.relative_to(vault_root())
            ensure_text_copy(path, backup_dir / relative)


def run_link_check(vault: Path, note_paths: set[Path]) -> list[str]:
    failures: list[str] = []
    for note_path in note_paths:
        note_text = note_path.read_text(encoding="utf-8")
        for rel in re.findall(r"\[\[([^\]]+)\]\]", note_text):
            if not rel.startswith("research/assets/"):
                continue
            target = vault / rel
            if target.suffix:
                if not target.exists():
                    failures.append(f"Missing target: {target}")
                continue
            if not target.with_suffix(".md").exists():
                failures.append(f"Missing target: {target.with_suffix('.md')}")
    return failures


def migrate_flat_assets(dry_run: bool, report_path: Path | None, backup_dir: Path | None) -> dict[str, Any]:
    vault = vault_root()
    operations = gather_migration_operations(vault)
    report = {
        "mode": "dry_run" if dry_run else "execute",
        "operations": operations,
        "operation_count": len(operations),
        "backup_dir": str(backup_dir) if backup_dir else None,
    }

    if report_path:
        write_text(report_path, json.dumps(report, indent=2))

    if dry_run:
        return report

    if backup_dir is None:
        raise VaultSyncError("backup_required", "migrate-flat-assets --execute requires --backup-dir")

    backup_targets(operations, backup_dir)
    touched_notes: set[Path] = set()
    for operation in operations:
        source = Path(operation["source"])
        target = Path(operation["target"])
        note_path = Path(operation["note"])
        touched_notes.add(note_path)

        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.move(str(source), str(target))

        note_text = note_path.read_text(encoding="utf-8")
        note_text = note_text.replace(operation["old_link"], operation["new_link"])
        note_text = ensure_bundle_line(note_text, operation["source_type"], operation["source_slug"])
        note_path.write_text(note_text, encoding="utf-8")
        write_source_bundle(
            bundle_dir(vault, operation["source_type"], operation["source_slug"]),
            operation["source_type"],
            operation["source_slug"],
            note_path.stem,
            parse_note_source_url(note_text),
        )

    link_failures = run_link_check(vault, touched_notes)
    report["link_failures"] = link_failures
    if report_path:
        write_text(report_path, json.dumps(report, indent=2))
    if link_failures:
        raise VaultSyncError("migration_link_check_failed", "\n".join(link_failures))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate and export Obsidian Vault research bundles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_parser = subparsers.add_parser("migrate-flat-assets", help="Move flat research/assets files into source bundles.")
    migrate_parser.add_argument("--dry-run", action="store_true")
    migrate_parser.add_argument("--execute", action="store_true")
    migrate_parser.add_argument("--report")
    migrate_parser.add_argument("--backup-dir")

    export_parser = subparsers.add_parser("export-draft", help="Prepare a Vault draft export for a slug.")
    export_parser.add_argument("--slug", required=True)
    export_parser.add_argument("--note-title", required=True)
    export_parser.add_argument("--note-body-file")
    export_parser.add_argument("--main-insight", required=True)
    export_parser.add_argument("--project-slug")
    export_parser.add_argument("--project-title")
    return parser


def cmd_export_draft(args: argparse.Namespace) -> int:
    note_body_file = Path(args.note_body_file) if args.note_body_file else None
    result = export_draft(
        slug=args.slug,
        note_title=args.note_title,
        note_body_file=note_body_file,
        main_insight=args.main_insight,
        project_slug=args.project_slug,
        project_title=args.project_title,
    )
    print(
        json.dumps(
            {
                "note_path": result.note_path,
                "bundle_path": result.bundle_path,
                "project_bundle_path": result.project_bundle_path,
                "daily_note_path": result.daily_note_path,
                "draft_title": result.draft_title,
                "export_identity": result.export_identity,
                "last_exported_at": result.last_exported_at,
            },
            indent=2,
        )
    )
    return 0


def cmd_migrate_flat_assets(args: argparse.Namespace) -> int:
    if args.dry_run == args.execute:
        raise VaultSyncError("migration_mode_required", "Choose exactly one of --dry-run or --execute")
    report = migrate_flat_assets(
        dry_run=args.dry_run,
        report_path=Path(args.report) if args.report else None,
        backup_dir=Path(args.backup_dir) if args.backup_dir else None,
    )
    print(json.dumps(report, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "migrate-flat-assets":
            return cmd_migrate_flat_assets(args)
        if args.command == "export-draft":
            return cmd_export_draft(args)
        parser.error(f"Unknown command: {args.command}")
        return 2
    except VaultSyncError as exc:
        print(f"ERROR[{exc.code}]: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
