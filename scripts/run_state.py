from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / ".claude" / "settings.json"
DEFAULT_WORKSPACE_FILES = [
    "00_zusammenfassung.md",
    "01_kernkonzepte.md",
    "02_schritt_fuer_schritt.md",
    "03_uebungen.md",
    "04_projekt_rebuild.md",
    "05_offene_fragen.md",
    "06_notebooklm_artefakte.md",
    "07_logik_check.md",
]
GENERIC_ALLOWED_STATUSES = {
    "not_started",
    "in_progress",
    "awaiting_user_input",
    "awaiting_confirmation",
    "blocked",
    "failed",
    "skipped",
    "done",
}
VAULT_ALLOWED_STATUSES = {
    "not_started",
    "draft_prepared",
    "blocked_input",
    "awaiting_confirmation",
    "done",
    "failed",
    "stale",
}
ALLOWED_STATUSES = GENERIC_ALLOWED_STATUSES | VAULT_ALLOWED_STATUSES
REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "updated_at",
    "source",
    "ingest",
    "notebooklm",
    "workspace",
    "fill_gaps",
    "rebuild",
    "vault",
    "next_recommended_step",
}
REQUIRED_NESTED_KEYS = {
    "source": {"type", "input", "title", "slug"},
    "ingest": {"status", "artifacts", "warnings", "log_files"},
    "notebooklm": {"status", "notebook_id", "deliverables", "artifacts"},
    "workspace": {
        "status",
        "is_tutorial",
        "files_complete",
        "required_files",
        "optional_files",
        "generated_files",
    },
    "fill_gaps": {"status", "answered_questions"},
    "rebuild": {"status", "reason", "project_path"},
    "vault": {
        "status",
        "note_path",
        "bundle_path",
        "project_bundle_path",
        "daily_note_path",
        "draft_title",
        "export_identity",
        "last_exported_at",
        "last_error_code",
        "last_error_message",
    },
}
VAULT_PATH_REQUIRED_STATUSES = {"draft_prepared", "awaiting_confirmation", "done", "stale"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_settings() -> dict[str, Any]:
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def vault_root() -> Path:
    return Path(load_settings()["vault_path"]).resolve()


def source_dir(slug: str) -> Path:
    return ROOT / "sources" / slug


def workspace_dir(slug: str) -> Path:
    return ROOT / "workspace" / slug


def state_path(slug: str) -> Path:
    return source_dir(slug) / "run.json"


def default_vault_state(source_type: str, slug: str) -> dict[str, Any]:
    return {
        "status": "not_started",
        "note_path": None,
        "bundle_path": None,
        "project_bundle_path": None,
        "daily_note_path": None,
        "draft_title": None,
        "export_identity": {
            "source_type": source_type,
            "source_slug": slug,
            "project_slug": None,
            "source_fingerprint": None,
        },
        "last_exported_at": None,
        "last_error_code": None,
        "last_error_message": None,
    }


def default_state(source_type: str, source_input: str, slug: str, title: str | None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": utc_now(),
        "source": {
            "type": source_type,
            "input": source_input,
            "title": title or slug,
            "slug": slug,
        },
        "ingest": {
            "status": "not_started",
            "artifacts": [],
            "warnings": [],
            "log_files": [],
        },
        "notebooklm": {
            "status": "not_started",
            "notebook_id": None,
            "deliverables": [],
            "artifacts": [],
        },
        "workspace": {
            "status": "not_started",
            "is_tutorial": False,
            "files_complete": False,
            "required_files": list(DEFAULT_WORKSPACE_FILES),
            "optional_files": [],
            "generated_files": [],
        },
        "fill_gaps": {
            "status": "not_started",
            "answered_questions": [],
        },
        "rebuild": {
            "status": "not_started",
            "reason": None,
            "project_path": None,
        },
        "vault": default_vault_state(source_type, slug),
        "next_recommended_step": "ingest",
    }


def parse_value(raw: str, as_json: bool) -> Any:
    if as_json:
        return json.loads(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def deep_fill_defaults(target: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    for key, value in defaults.items():
        if key not in target:
            target[key] = value
            continue
        if isinstance(value, dict) and isinstance(target[key], dict):
            deep_fill_defaults(target[key], value)
    return target


def normalize_state(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("source", {})
    source_type = source.get("type", "source")
    slug = source.get("slug", "unknown")
    defaults = default_state(source_type, source.get("input", ""), slug, source.get("title"))
    deep_fill_defaults(data, defaults)

    vault = data.get("vault", {})
    if vault.get("status") == "in_progress":
        vault["status"] = "draft_prepared"
    if vault.get("status") == "blocked":
        vault["status"] = "blocked_input"

    export_identity = vault.get("export_identity", {})
    if isinstance(export_identity, dict):
        export_identity["source_type"] = export_identity.get("source_type") or source_type
        export_identity["source_slug"] = export_identity.get("source_slug") or slug
        export_identity.setdefault("project_slug", None)
        export_identity.setdefault("source_fingerprint", None)

    return data


def load_state(slug: str) -> dict[str, Any]:
    path = state_path(slug)
    if not path.exists():
        raise FileNotFoundError(f"State file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return normalize_state(data)


def save_state(slug: str, state: dict[str, Any]) -> None:
    update_timestamp(state)
    atomic_write_json(state_path(slug), state)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def set_path(data: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    cursor: Any = data
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            raise ValueError(f"Cannot descend into non-object at: {part}")
        if part not in cursor:
            raise KeyError(f"Missing path segment: {part}")
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        raise ValueError(f"Cannot set value on non-object path: {dotted_path}")
    cursor[parts[-1]] = value


def get_path(data: dict[str, Any], dotted_path: str) -> Any:
    parts = dotted_path.split(".")
    cursor: Any = data
    for part in parts:
        if not isinstance(cursor, dict):
            raise ValueError(f"Cannot descend into non-object at: {part}")
        if part not in cursor:
            raise KeyError(f"Missing path segment: {part}")
        cursor = cursor[part]
    return cursor


def update_timestamp(data: dict[str, Any]) -> None:
    data["updated_at"] = utc_now()


def ensure_list(value: Any, dotted_path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"Path is not a list: {dotted_path}")
    return value


def normalize_repo_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def normalize_vault_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return vault_root() / candidate


def validate_export_identity(
    export_identity: dict[str, Any],
    source_type: str,
    slug: str,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(export_identity, dict):
        errors.append("vault.export_identity must be an object")
        return errors, warnings

    if export_identity.get("source_type") != source_type:
        errors.append("vault.export_identity.source_type must match source.type")
    if export_identity.get("source_slug") != slug:
        errors.append("vault.export_identity.source_slug must match source.slug")
    if not export_identity.get("source_fingerprint"):
        warnings.append("vault.export_identity.source_fingerprint is empty")

    project_slug = export_identity.get("project_slug")
    if project_slug is not None and not isinstance(project_slug, str):
        errors.append("vault.export_identity.project_slug must be a string or null")

    return errors, warnings


def validate_state(data: dict[str, Any], slug: str, check_files: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    missing_top = sorted(REQUIRED_TOP_LEVEL_KEYS - set(data.keys()))
    if missing_top:
        errors.append(f"Missing top-level keys: {', '.join(missing_top)}")

    for section, keys in REQUIRED_NESTED_KEYS.items():
        value = data.get(section)
        if not isinstance(value, dict):
            errors.append(f"Section '{section}' must be an object")
            continue
        missing_nested = sorted(keys - set(value.keys()))
        if missing_nested:
            errors.append(f"Section '{section}' is missing keys: {', '.join(missing_nested)}")

    source = data.get("source", {})
    source_type = source.get("type", "source")
    if source.get("slug") != slug:
        errors.append(f"Slug mismatch: expected '{slug}', found '{source.get('slug')}'")

    for section in ("ingest", "notebooklm", "workspace", "fill_gaps", "rebuild"):
        stage = data.get(section, {})
        status = stage.get("status")
        if status not in GENERIC_ALLOWED_STATUSES:
            errors.append(f"Invalid status in '{section}': {status}")

    vault_status = data.get("vault", {}).get("status")
    if vault_status not in VAULT_ALLOWED_STATUSES:
        errors.append(f"Invalid status in 'vault': {vault_status}")

    for dotted_path in (
        "ingest.artifacts",
        "ingest.warnings",
        "ingest.log_files",
        "notebooklm.deliverables",
        "notebooklm.artifacts",
        "workspace.required_files",
        "workspace.optional_files",
        "workspace.generated_files",
        "fill_gaps.answered_questions",
    ):
        try:
            value = get_path(data, dotted_path)
        except (KeyError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if not isinstance(value, list):
            errors.append(f"Path '{dotted_path}' must be a list")

    if not isinstance(data.get("workspace", {}).get("is_tutorial"), bool):
        errors.append("workspace.is_tutorial must be a boolean")
    if not isinstance(data.get("workspace", {}).get("files_complete"), bool):
        errors.append("workspace.files_complete must be a boolean")

    vault = data.get("vault", {})
    note_path = vault.get("note_path")
    bundle_path = vault.get("bundle_path")
    project_bundle_path = vault.get("project_bundle_path")
    daily_note_path = vault.get("daily_note_path")
    draft_title = vault.get("draft_title")
    export_identity = vault.get("export_identity", {})

    if vault_status in VAULT_PATH_REQUIRED_STATUSES:
        if not note_path:
            errors.append(f"vault.status={vault_status} requires vault.note_path")
        if not bundle_path:
            errors.append(f"vault.status={vault_status} requires vault.bundle_path")
        if not daily_note_path:
            errors.append(f"vault.status={vault_status} requires vault.daily_note_path")
        if not draft_title:
            errors.append(f"vault.status={vault_status} requires vault.draft_title")
        identity_errors, identity_warnings = validate_export_identity(export_identity, source_type, slug)
        errors.extend(identity_errors)
        warnings.extend(identity_warnings)

    if vault_status == "blocked_input" and not vault.get("last_error_code"):
        errors.append("vault.status=blocked_input requires vault.last_error_code")

    if vault_status == "failed" and not vault.get("last_error_code"):
        errors.append("vault.status=failed requires vault.last_error_code")

    if project_bundle_path and data.get("rebuild", {}).get("status") != "done":
        errors.append("vault.project_bundle_path is only allowed when rebuild.status=done")

    if check_files:
        src_dir = source_dir(slug)
        ws_dir = workspace_dir(slug)
        if not src_dir.exists():
            errors.append(f"Source directory missing: {src_dir}")

        for artifact in data.get("ingest", {}).get("artifacts", []):
            artifact_path = src_dir / artifact
            if not artifact_path.exists():
                errors.append(f"Missing ingest artifact: {artifact_path}")

        for artifact in data.get("notebooklm", {}).get("artifacts", []):
            artifact_path = src_dir / artifact
            if not artifact_path.exists():
                errors.append(f"Missing NotebookLM artifact: {artifact_path}")

        notebook_status = data.get("notebooklm", {}).get("status")
        notebook_id = data.get("notebooklm", {}).get("notebook_id")
        notebook_id_file = src_dir / "notebook_id.txt"
        if notebook_status == "done":
            if not notebook_id:
                errors.append("notebooklm.status is done but notebooklm.notebook_id is empty")
            if not notebook_id_file.exists():
                errors.append(f"Notebook id file missing: {notebook_id_file}")

        required_files = data.get("workspace", {}).get("required_files", [])
        generated_files = set(data.get("workspace", {}).get("generated_files", []))
        actual_files = {item.name for item in ws_dir.iterdir()} if ws_dir.exists() else set()
        missing_required = [name for name in required_files if name not in actual_files]
        if data.get("workspace", {}).get("status") == "done" and missing_required:
            errors.append(f"Workspace missing required files: {', '.join(missing_required)}")

        if generated_files and generated_files != actual_files:
            warnings.append("workspace.generated_files does not match actual workspace contents")

        project_path = normalize_repo_path(data.get("rebuild", {}).get("project_path"))
        if data.get("rebuild", {}).get("status") == "done":
            if project_path is None:
                errors.append("rebuild.status is done but rebuild.project_path is empty")
            elif not project_path.exists():
                errors.append(f"Rebuild project path missing: {project_path}")

        if vault_status in VAULT_PATH_REQUIRED_STATUSES:
            normalized_note_path = normalize_vault_path(note_path)
            normalized_bundle_path = normalize_vault_path(bundle_path)
            normalized_daily_note_path = normalize_vault_path(daily_note_path)
            if normalized_note_path is None or not normalized_note_path.exists():
                errors.append(f"Vault note path missing: {normalized_note_path}")
            if normalized_bundle_path is None or not normalized_bundle_path.exists():
                errors.append(f"Vault bundle path missing: {normalized_bundle_path}")
            if normalized_daily_note_path is None or not normalized_daily_note_path.exists():
                errors.append(f"Vault daily note path missing: {normalized_daily_note_path}")
            if project_bundle_path:
                normalized_project_bundle_path = normalize_vault_path(project_bundle_path)
                if normalized_project_bundle_path is None or not normalized_project_bundle_path.exists():
                    errors.append(f"Vault project bundle path missing: {normalized_project_bundle_path}")

    return errors, warnings


def infer_next_step(data: dict[str, Any]) -> str:
    ingest_status = data.get("ingest", {}).get("status")
    notebook_status = data.get("notebooklm", {}).get("status")
    workspace = data.get("workspace", {})
    workspace_status = workspace.get("status")
    rebuild = data.get("rebuild", {})
    fill_gaps = data.get("fill_gaps", {})
    vault = data.get("vault", {})

    if ingest_status != "done":
        return "ingest"
    if notebook_status != "done":
        return "notebooklm"
    if workspace_status != "done" or not workspace.get("files_complete", False):
        return "workspace"

    if workspace.get("is_tutorial", False):
        rebuild_status = rebuild.get("status")
        if rebuild_status in {
            "not_started",
            "in_progress",
            "awaiting_user_input",
            "awaiting_confirmation",
            "blocked",
            "failed",
        }:
            return "rebuild-project"

    fill_gaps_status = fill_gaps.get("status")
    if fill_gaps_status in {
        "not_started",
        "in_progress",
        "awaiting_user_input",
        "awaiting_confirmation",
        "blocked",
        "failed",
    }:
        return "fill-gaps"

    vault_status = vault.get("status")
    if vault_status in {
        "not_started",
        "draft_prepared",
        "blocked_input",
        "awaiting_confirmation",
        "failed",
        "stale",
    }:
        return "save-to-vault"

    return "complete"


def format_summary(data: dict[str, Any]) -> str:
    stored_next = data.get("next_recommended_step", "unknown")
    computed_next = infer_next_step(data)
    vault = data.get("vault", {})
    lines = [
        f"Slug: {data.get('source', {}).get('slug', 'unknown')}",
        f"Source Type: {data.get('source', {}).get('type', 'unknown')}",
        f"Ingest: {data.get('ingest', {}).get('status', 'unknown')}",
        f"NotebookLM: {data.get('notebooklm', {}).get('status', 'unknown')}",
        (
            "Workspace: "
            f"{data.get('workspace', {}).get('status', 'unknown')} "
            f"(files_complete={data.get('workspace', {}).get('files_complete', False)})"
        ),
        f"Fill Gaps: {data.get('fill_gaps', {}).get('status', 'unknown')}",
        f"Rebuild: {data.get('rebuild', {}).get('status', 'unknown')}",
        f"Vault: {vault.get('status', 'unknown')}",
        f"Vault Draft Title: {vault.get('draft_title') or 'n/a'}",
        f"Stored Next: {stored_next}",
        f"Computed Next: {computed_next}",
    ]
    return "\n".join(lines)


def cmd_init(args: argparse.Namespace) -> int:
    path = state_path(args.slug)
    if path.exists() and not args.force:
        print(f"State file already exists: {path}", file=sys.stderr)
        return 1
    payload = default_state(args.source_type, args.input_value, args.slug, args.title)
    atomic_write_json(path, payload)
    print(path)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    set_path(data, args.path, parse_value(args.value, args.json_value))
    update_timestamp(data)
    atomic_write_json(state_path(args.slug), data)
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    target = ensure_list(get_path(data, args.path), args.path)
    value = parse_value(args.value, args.json_value)
    if value not in target:
        target.append(value)
    update_timestamp(data)
    atomic_write_json(state_path(args.slug), data)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    errors, warnings = validate_state(data, args.slug, args.check_files)
    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_persist_notebook_id(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    set_path(data, "notebooklm.notebook_id", args.notebook_id)
    update_timestamp(data)
    src_dir = source_dir(args.slug)
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "notebook_id.txt").write_text(f"{args.notebook_id}\n", encoding="utf-8")
    atomic_write_json(state_path(args.slug), data)
    return 0


def cmd_sync_workspace(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    ws_dir = workspace_dir(args.slug)
    files = sorted(item.name for item in ws_dir.iterdir() if item.is_file()) if ws_dir.exists() else []
    required_files = data.get("workspace", {}).get("required_files", DEFAULT_WORKSPACE_FILES)
    files_complete = all(file_name in files for file_name in required_files)
    set_path(data, "workspace.generated_files", files)
    set_path(data, "workspace.files_complete", files_complete)
    update_timestamp(data)
    atomic_write_json(state_path(args.slug), data)
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    print(format_summary(data))
    return 0


def cmd_refresh_next(args: argparse.Namespace) -> int:
    data = load_state(args.slug)
    next_step = infer_next_step(data)
    set_path(data, "next_recommended_step", next_step)
    update_timestamp(data)
    atomic_write_json(state_path(args.slug), data)
    print(next_step)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage learning-lab run.json state files")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a new run.json")
    init_parser.add_argument("--slug", required=True)
    init_parser.add_argument("--source-type", required=True)
    init_parser.add_argument("--input", dest="input_value", required=True)
    init_parser.add_argument("--title")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=cmd_init)

    show_parser = subparsers.add_parser("show", help="Print the current state")
    show_parser.add_argument("--slug", required=True)
    show_parser.set_defaults(func=cmd_show)

    set_parser = subparsers.add_parser("set", help="Set a value via dotted path")
    set_parser.add_argument("--slug", required=True)
    set_parser.add_argument("--path", required=True)
    set_parser.add_argument("--value", required=True)
    set_parser.add_argument("--json", dest="json_value", action="store_true")
    set_parser.set_defaults(func=cmd_set)

    append_parser = subparsers.add_parser("append", help="Append a unique item to a list path")
    append_parser.add_argument("--slug", required=True)
    append_parser.add_argument("--path", required=True)
    append_parser.add_argument("--value", required=True)
    append_parser.add_argument("--json", dest="json_value", action="store_true")
    append_parser.set_defaults(func=cmd_append)

    validate_parser = subparsers.add_parser("validate", help="Validate run.json")
    validate_parser.add_argument("--slug", required=True)
    validate_parser.add_argument("--check-files", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    notebook_parser = subparsers.add_parser(
        "persist-notebook-id",
        help="Write notebook_id.txt and keep run.json in sync",
    )
    notebook_parser.add_argument("--slug", required=True)
    notebook_parser.add_argument("--notebook-id", required=True)
    notebook_parser.set_defaults(func=cmd_persist_notebook_id)

    sync_workspace_parser = subparsers.add_parser(
        "sync-workspace",
        help="Sync workspace.generated_files and files_complete from disk",
    )
    sync_workspace_parser.add_argument("--slug", required=True)
    sync_workspace_parser.set_defaults(func=cmd_sync_workspace)

    summary_parser = subparsers.add_parser("summary", help="Print a concise workflow summary")
    summary_parser.add_argument("--slug", required=True)
    summary_parser.set_defaults(func=cmd_summary)

    refresh_next_parser = subparsers.add_parser(
        "refresh-next",
        help="Recompute next_recommended_step from the current state",
    )
    refresh_next_parser.add_argument("--slug", required=True)
    refresh_next_parser.set_defaults(func=cmd_refresh_next)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
