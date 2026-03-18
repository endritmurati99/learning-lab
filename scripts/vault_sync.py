from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / ".claude" / "settings.json"


FLAT_SUFFIXES = [
    "-transcript.txt",
    "-study-guide.md",
    "-nlm-flashcards.md",
    "-nlm-mindmap.json",
    "-nlm-report.md",
    "-nlm-slides.pdf",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def vault_path() -> Path:
    settings = load_json(SETTINGS_PATH)
    return Path(settings["vault_path"]).resolve()


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


def canonical_asset_name(path: Path) -> str:
    lowered = path.name.lower()
    if lowered == "metadata.tsv":
        return "metadata.tsv"
    if lowered == "notebook_id.txt":
        return "notebook_id.txt"
    if lowered.endswith(".en.srt") or lowered.endswith(".srt"):
        return "transcript.srt"
    if lowered.endswith("-transcript.txt") or lowered == "transcript.txt":
        return "transcript.txt"
    if lowered.endswith(".txt") and not lowered.startswith("ingest") and not lowered.startswith("notebook"):
        return "transcript.txt"
    if "study-guide" in lowered:
        return "study-guide.md"
    if "flashcards" in lowered:
        return "nlm-flashcards.md"
    if "mindmap" in lowered:
        return "nlm-mindmap.json"
    if "slides" in lowered:
        return "nlm-slides.pdf"
    if "report" in lowered:
        return "nlm-report.md"
    return path.name


def research_dir(vault_root: Path) -> Path:
    return vault_root / "research"


def assets_root(vault_root: Path) -> Path:
    return research_dir(vault_root) / "assets"


def bundle_dir(vault_root: Path, source_type: str, slug: str) -> Path:
    return assets_root(vault_root) / source_type / slug


def bundle_link(source_type: str, slug: str) -> str:
    return f"[[research/assets/{source_type}/{slug}/Source Bundle]]"


def write_source_bundle(
    target_dir: Path,
    source_type: str,
    slug: str,
    note_title: str | None,
    source_url: str | None,
) -> None:
    asset_files = sorted(path.name for path in target_dir.iterdir() if path.is_file() and path.name != "Source Bundle.md")
    lines = [
        "# Source Bundle",
        "",
        f"- Source type: `{source_type}`",
        f"- Source slug: `{slug}`",
    ]
    if note_title:
        lines.append(f"- Research note: [[{note_title}]]")
    if source_url:
        lines.append(f"- Source URL: {source_url}")
    lines.extend(["", "## Assets", ""])
    for asset_name in asset_files:
        lines.append(f"- [[research/assets/{source_type}/{slug}/{asset_name}]]")
    lines.append("")
    write_text(target_dir / "Source Bundle.md", "\n".join(lines))


def copy_file_if_present(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def parse_note_source_url(text: str) -> str | None:
    frontmatter_match = re.search(r"source_url:\s*\"([^\"]+)\"", text)
    if frontmatter_match:
        return frontmatter_match.group(1)
    source_match = re.search(r"> Source: \[[^\]]+\]\(([^)]+)\)", text)
    if source_match:
        return source_match.group(1)
    return None


def ensure_bundle_line(note_text: str, source_type: str, slug: str) -> str:
    bundle = f"> Asset Bundle: {bundle_link(source_type, slug)}"
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


def migrate_flat_assets() -> int:
    vault_root = vault_path()
    research_root = research_dir(vault_root)
    flat_assets = assets_root(vault_root)
    note_paths = sorted(path for path in research_root.glob("*.md") if path.is_file())

    for note_path in note_paths:
        note_text = note_path.read_text(encoding="utf-8")
        source_url = parse_note_source_url(note_text)
        source_type = infer_source_type_from_url(source_url)
        replacements: dict[str, str] = {}
        note_slug: str | None = None

        for asset_rel in re.findall(r"\[\[research/assets/([^\]]+)\]\]", note_text):
            asset_parts = Path(asset_rel).parts
            if len(asset_parts) > 1:
                continue
            asset_name = asset_parts[0]
            slug = infer_slug_from_asset_name(asset_name)
            if not slug:
                continue
            note_slug = note_slug or slug
            source = flat_assets / asset_name
            target_dir = bundle_dir(vault_root, source_type, slug)
            target_name = canonical_asset_name(Path(asset_name))
            target = target_dir / target_name
            if source.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.move(str(source), str(target))
            replacements[asset_name] = f"{source_type}/{slug}/{target_name}"

        for old_name, new_rel in replacements.items():
            note_text = note_text.replace(f"[[research/assets/{old_name}]]", f"[[research/assets/{new_rel}]]")

        if note_slug:
            note_text = ensure_bundle_line(note_text, source_type, note_slug)
            write_source_bundle(bundle_dir(vault_root, source_type, note_slug), source_type, note_slug, note_path.stem, source_url)

        note_path.write_text(note_text, encoding="utf-8")

    return 0


def load_run(slug: str) -> dict:
    run_path = ROOT / "sources" / slug / "run.json"
    return load_json(run_path)


def collect_exportable_assets(run_data: dict) -> list[Path]:
    slug = run_data["source"]["slug"]
    source_root = ROOT / "sources" / slug
    paths: list[Path] = []

    for rel in run_data.get("ingest", {}).get("artifacts", []):
        paths.append(source_root / rel)
    for rel in run_data.get("ingest", {}).get("log_files", []):
        paths.append(source_root / rel)
    for rel in run_data.get("notebooklm", {}).get("artifacts", []):
        paths.append(source_root / rel)

    notebook_id_path = source_root / "notebook_id.txt"
    if notebook_id_path.exists():
        paths.append(notebook_id_path)

    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def export_run_assets(run_data: dict, note_title: str | None) -> tuple[str, Path]:
    vault_root = vault_path()
    source_type = run_data["source"]["type"]
    slug = run_data["source"]["slug"]
    source_url = run_data["source"].get("input")
    target_dir = bundle_dir(vault_root, source_type, slug)
    target_dir.mkdir(parents=True, exist_ok=True)

    for source_path in collect_exportable_assets(run_data):
        target_name = canonical_asset_name(source_path)
        copy_file_if_present(source_path, target_dir / target_name)

    write_source_bundle(target_dir, source_type, slug, note_title, source_url)
    return bundle_link(source_type, slug), target_dir


def copy_tree_filtered(source_dir: Path, target_dir: Path, include_suffixes: set[str]) -> None:
    for path in source_dir.rglob("*"):
        if path.is_dir():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in include_suffixes:
            continue
        relative = path.relative_to(source_dir)
        copy_file_if_present(path, target_dir / relative)


def export_project_mirror(
    run_data: dict,
    project_slug: str,
    project_title: str,
    research_note_title: str,
) -> str | None:
    if run_data.get("rebuild", {}).get("status") != "done":
        return None

    project_path_value = run_data.get("rebuild", {}).get("project_path")
    if not project_path_value:
        return None

    local_project_dir = (ROOT / project_path_value).resolve()
    if not local_project_dir.exists():
        return None

    vault_root = vault_path()
    vault_project_dir = vault_root / "projects" / project_slug
    vault_project_dir.mkdir(parents=True, exist_ok=True)

    top_level_files = ["README.md", "skill_scaffold.py", "example_spec.json"]
    for file_name in top_level_files:
        copy_file_if_present(local_project_dir / file_name, vault_project_dir / "code" / file_name)

    tests_dir = local_project_dir / "tests"
    if tests_dir.exists():
        copy_tree_filtered(tests_dir, vault_project_dir / "code" / "tests", {".py"})

    generated_skills_root = local_project_dir / "generated" / ".claude" / "skills"
    if generated_skills_root.exists():
        for skill_dir in generated_skills_root.iterdir():
            if not skill_dir.is_dir():
                continue
            target_skill_dir = vault_project_dir / "example-output" / skill_dir.name
            copy_tree_filtered(skill_dir, target_skill_dir, {".md", ".json", ".txt", ".py"})

    project_note = "\n".join(
        [
            "# Project Note",
            "",
            f"- Title: {project_title}",
            f"- Related research: [[{research_note_title}]]",
            f"- Local project path: `{local_project_dir}`",
            "",
            "## Contents",
            "",
            "- `code/` mirrors the main rebuild files for reading inside Obsidian.",
            "- `example-output/` contains a visible generated skill example.",
            "",
            "## Why this exists",
            "",
            "This mirror keeps the rebuild output readable from Obsidian without forcing the Vault to become the executable source of truth.",
            "",
        ]
    )
    write_text(vault_project_dir / "Project Note.md", project_note)
    return f"[[projects/{project_slug}/Project Note]]"


def append_daily_note(vault_root: Path, note_title: str, main_insight: str) -> None:
    from datetime import date

    daily_path = vault_root / "daily-notes" / f"{date.today().isoformat()}.md"
    if daily_path.exists():
        existing = daily_path.read_text(encoding="utf-8")
    else:
        existing = f"# {date.today().isoformat()}\n\n## Research\n"

    if "## Research" not in existing:
        existing = existing.rstrip() + "\n\n## Research\n"

    addition = f"- Added [[{note_title}]]\n- Main insight: {main_insight}\n"
    if f"[[{note_title}]]" not in existing:
        existing = existing.rstrip() + "\n" + addition
        write_text(daily_path, existing.rstrip() + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate and export Obsidian Vault research bundles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("migrate-flat-assets", help="Move flat research/assets files into source-type/slug folders and rewrite note links.")

    export_parser = subparsers.add_parser("export-run-support", help="Copy run assets and mirrored project files into the Vault.")
    export_parser.add_argument("--slug", required=True)
    export_parser.add_argument("--note-title", required=True)
    export_parser.add_argument("--project-slug")
    export_parser.add_argument("--project-title")
    export_parser.add_argument("--main-insight")
    return parser


def cmd_export_run_support(args: argparse.Namespace) -> int:
    run_data = load_run(args.slug)
    vault_root = vault_path()
    asset_bundle, _ = export_run_assets(run_data, args.note_title)
    project_link = None
    if args.project_slug and args.project_title:
        project_link = export_project_mirror(run_data, args.project_slug, args.project_title, args.note_title)
    if args.main_insight:
        append_daily_note(vault_root, args.note_title, args.main_insight)
    payload = {
        "asset_bundle": asset_bundle,
        "project_link": project_link,
    }
    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "migrate-flat-assets":
        return migrate_flat_assets()
    if args.command == "export-run-support":
        return cmd_export_run_support(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
