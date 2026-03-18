from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import run_state  # noqa: E402


class RunStateTests(unittest.TestCase):
    def test_normalize_state_backfills_vault_fields_and_maps_legacy_status(self) -> None:
        state = {
            "schema_version": 1,
            "updated_at": "2026-03-18T00:00:00Z",
            "source": {
                "type": "youtube",
                "input": "https://example.com",
                "title": "Example",
                "slug": "example",
            },
            "ingest": {"status": "done", "artifacts": [], "warnings": [], "log_files": []},
            "notebooklm": {"status": "done", "notebook_id": "abc", "deliverables": [], "artifacts": []},
            "workspace": {
                "status": "done",
                "is_tutorial": False,
                "files_complete": True,
                "required_files": list(run_state.DEFAULT_WORKSPACE_FILES),
                "optional_files": [],
                "generated_files": list(run_state.DEFAULT_WORKSPACE_FILES),
            },
            "fill_gaps": {"status": "not_started", "answered_questions": []},
            "rebuild": {"status": "skipped", "reason": "not_applicable", "project_path": None},
            "vault": {"status": "in_progress", "note_path": None},
            "next_recommended_step": "save-to-vault",
        }

        normalized = run_state.normalize_state(state)

        self.assertEqual(normalized["vault"]["status"], "draft_prepared")
        self.assertIn("bundle_path", normalized["vault"])
        self.assertIn("export_identity", normalized["vault"])
        self.assertEqual(normalized["vault"]["export_identity"]["source_slug"], "example")

    def test_infer_next_step_keeps_fill_gaps_ahead_of_vault_finalize(self) -> None:
        state = run_state.default_state("youtube", "https://example.com", "example", "Example")
        state["ingest"]["status"] = "done"
        state["notebooklm"]["status"] = "done"
        state["workspace"]["status"] = "done"
        state["workspace"]["files_complete"] = True
        state["rebuild"]["status"] = "skipped"
        state["fill_gaps"]["status"] = "awaiting_user_input"
        state["vault"]["status"] = "draft_prepared"
        state["vault"]["note_path"] = "research/Example.md"
        state["vault"]["bundle_path"] = "research/assets/youtube/example"
        state["vault"]["daily_note_path"] = "daily-notes/2026-03-18.md"
        state["vault"]["draft_title"] = "Example"
        state["vault"]["export_identity"]["source_fingerprint"] = "sha256:test"

        self.assertEqual(run_state.infer_next_step(state), "fill-gaps")

    def test_validate_state_requires_vault_contract_for_drafts(self) -> None:
        state = run_state.default_state("youtube", "https://example.com", "example", "Example")
        state["ingest"]["status"] = "done"
        state["notebooklm"]["status"] = "done"
        state["workspace"]["status"] = "done"
        state["workspace"]["files_complete"] = True
        state["fill_gaps"]["status"] = "done"
        state["rebuild"]["status"] = "skipped"
        state["vault"]["status"] = "draft_prepared"

        errors, warnings = run_state.validate_state(state, "example", check_files=False)

        self.assertTrue(any("vault.bundle_path" in error for error in errors))
        self.assertTrue(any("source_fingerprint" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
