from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import vault_sync  # noqa: E402


class VaultSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self._root = tempfile.TemporaryDirectory()
        self.temp_root = Path(self._root.name)
        self.repo_root = self.temp_root / "repo"
        self.vault_root = self.temp_root / "vault"
        (self.repo_root / ".claude").mkdir(parents=True)
        (self.repo_root / "sources" / "example").mkdir(parents=True)
        (self.repo_root / "workspace" / "example").mkdir(parents=True)
        (self.vault_root / "research" / "assets").mkdir(parents=True)
        (self.vault_root / "daily-notes").mkdir(parents=True)
        (self.vault_root / "projects").mkdir(parents=True)

        settings = {"vault_path": str(self.vault_root)}
        (self.repo_root / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

        run_json = {
            "schema_version": 1,
            "updated_at": "2026-03-18T00:00:00Z",
            "source": {
                "type": "youtube",
                "input": "https://example.com",
                "title": "Example",
                "slug": "example",
            },
            "ingest": {
                "status": "done",
                "artifacts": ["video.txt"],
                "warnings": [],
                "log_files": [],
            },
            "notebooklm": {
                "status": "done",
                "notebook_id": "nb",
                "deliverables": [],
                "artifacts": ["nlm-report.md"],
            },
            "workspace": {
                "status": "done",
                "is_tutorial": False,
                "files_complete": True,
                "required_files": [],
                "optional_files": [],
                "generated_files": [],
            },
            "fill_gaps": {"status": "done", "answered_questions": []},
            "rebuild": {"status": "skipped", "reason": "not_applicable", "project_path": None},
            "vault": {
                "status": "not_started",
                "note_path": None,
                "bundle_path": None,
                "project_bundle_path": None,
                "daily_note_path": None,
                "draft_title": None,
                "export_identity": {
                    "source_type": "youtube",
                    "source_slug": "example",
                    "project_slug": None,
                    "source_fingerprint": None,
                },
                "last_exported_at": None,
                "last_error_code": None,
                "last_error_message": None,
            },
            "next_recommended_step": "save-to-vault",
        }
        (self.repo_root / "sources" / "example" / "run.json").write_text(json.dumps(run_json), encoding="utf-8")
        (self.repo_root / "sources" / "example" / "video.txt").write_text("hello world\n", encoding="utf-8")
        (self.repo_root / "sources" / "example" / "nlm-report.md").write_text("# Report\n", encoding="utf-8")

        self.original_root = vault_sync.ROOT
        self.original_settings = vault_sync.SETTINGS_PATH
        vault_sync.ROOT = self.repo_root
        vault_sync.SETTINGS_PATH = self.repo_root / ".claude" / "settings.json"

    def tearDown(self) -> None:
        vault_sync.ROOT = self.original_root
        vault_sync.SETTINGS_PATH = self.original_settings
        self._root.cleanup()

    def test_export_draft_creates_bundle_note_and_deduped_daily_entry(self) -> None:
        note_body = self.temp_root / "note.md"
        note_body.write_text(
            "---\nexport_identity: \"youtube:example:sha256:placeholder\"\n---\n\n# Example\n",
            encoding="utf-8",
        )

        result_one = vault_sync.export_draft(
            slug="example",
            note_title="Example Note",
            note_body_file=note_body,
            main_insight="First insight.",
            project_slug=None,
            project_title=None,
        )

        result_two = vault_sync.export_draft(
            slug="example",
            note_title="Example Note",
            note_body_file=note_body,
            main_insight="Updated insight.",
            project_slug=None,
            project_title=None,
        )

        daily_note = (self.vault_root / result_two.daily_note_path).read_text(encoding="utf-8")
        self.assertEqual(result_one.note_path, "research/Example Note.md")
        self.assertTrue((self.vault_root / result_two.bundle_path / "Source Bundle.md").exists())
        self.assertEqual(daily_note.count("<!-- learning-lab:youtube:example -->"), 1)
        self.assertIn("Updated insight.", daily_note)

    def test_export_draft_blocks_on_note_path_collision(self) -> None:
        note_path = self.vault_root / "research" / "Collision Note.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("---\nexport_identity: other:slug:sha256:123\n---\n", encoding="utf-8")

        note_body = self.temp_root / "collision.md"
        note_body.write_text("---\nexport_identity: \"youtube:example:sha256:placeholder\"\n---\n", encoding="utf-8")

        with self.assertRaises(vault_sync.VaultSyncError) as context:
            vault_sync.export_draft(
                slug="example",
                note_title="Collision Note",
                note_body_file=note_body,
                main_insight="Insight",
                project_slug=None,
                project_title=None,
            )

        self.assertEqual(context.exception.code, "note_path_collision")

    def test_migrate_flat_assets_dry_run_produces_report_without_writes(self) -> None:
        assets_dir = self.vault_root / "research" / "assets"
        note_path = self.vault_root / "research" / "Legacy Note.md"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / "legacy-transcript.txt").write_text("text", encoding="utf-8")
        note_path.write_text(
            "# Legacy\n\n> Source: [Video](https://www.youtube.com/watch?v=x)\n> Transcript: [[research/assets/legacy-transcript.txt]]\n",
            encoding="utf-8",
        )

        report = vault_sync.migrate_flat_assets(dry_run=True, report_path=None, backup_dir=None)

        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["operation_count"], 1)
        self.assertTrue((assets_dir / "legacy-transcript.txt").exists())


if __name__ == "__main__":
    unittest.main()
