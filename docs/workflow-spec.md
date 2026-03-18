# Learning Lab Workflow Specification

## Purpose

`learning-lab` uses a file-backed workflow state so every run can be:

- resumed
- validated
- inspected
- exported to The Vault without guesswork

The canonical state file is:

`sources/{slug}/run.json`

## State Mutation Rule

`run.json` must never be edited with ad-hoc text replacement.

All state writes go through:

`python scripts/run_state.py ...`

## Lifecycle

A run moves through these stages:

1. `source`
2. `ingest`
3. `notebooklm`
4. `workspace`
5. `rebuild`
6. `fill_gaps`
7. `vault`

## Allowed Status Values

### Generic stage statuses

- `not_started`
- `in_progress`
- `awaiting_user_input`
- `awaiting_confirmation`
- `blocked`
- `failed`
- `skipped`
- `done`

### Vault-only statuses

- `not_started`
- `draft_prepared`
- `blocked_input`
- `awaiting_confirmation`
- `done`
- `failed`
- `stale`

## Canonical State Shape

```json
{
  "schema_version": 1,
  "updated_at": "2026-03-18T16:00:00Z",
  "source": {
    "type": "youtube",
    "input": "https://example.com",
    "title": "Example",
    "slug": "example"
  },
  "ingest": {
    "status": "not_started",
    "artifacts": [],
    "warnings": [],
    "log_files": []
  },
  "notebooklm": {
    "status": "not_started",
    "notebook_id": null,
    "deliverables": [],
    "artifacts": []
  },
  "workspace": {
    "status": "not_started",
    "is_tutorial": false,
    "files_complete": false,
    "required_files": [],
    "optional_files": [],
    "generated_files": []
  },
  "fill_gaps": {
    "status": "not_started",
    "answered_questions": []
  },
  "rebuild": {
    "status": "not_started",
    "reason": null,
    "project_path": null
  },
  "vault": {
    "status": "not_started",
    "note_path": null,
    "bundle_path": null,
    "project_bundle_path": null,
    "daily_note_path": null,
    "draft_title": null,
    "export_identity": {
      "source_type": "youtube",
      "source_slug": "example",
      "project_slug": null,
      "source_fingerprint": null
    },
    "last_exported_at": null,
    "last_error_code": null,
    "last_error_message": null
  },
  "next_recommended_step": "ingest"
}
```

## Vault Invariants

- `draft_prepared` means note, bundle, and daily-note draft already exist
- `awaiting_confirmation` means the draft was shown and final approval is pending
- `done` means the approved draft is the final Vault export
- `blocked_input` means a user/input problem is preventing progress
- `failed` means a technical/system problem occurred and an error code was persisted

## Export Identity

The Vault export identity is:

- stable key: `source_type + source_slug`
- content validation: `source_fingerprint`

Re-runs:

- same key + same fingerprint -> update in place, no duplicate daily-note entry
- same key + different fingerprint -> update in place, refresh draft/final content
- different key + same content -> warn, do not auto-merge

## Primary Workflow Priority

`next_recommended_step` follows this order:

1. `ingest`
2. `notebooklm`
3. `workspace`
4. `rebuild-project`
5. `fill-gaps`
6. `save-to-vault`
7. `complete`

Vault drafts may exist early, but they must not overtake rebuild or fill-gaps in the primary route.

## Definition Of Done

### learn-source

- source artifacts exist
- NotebookLM artifacts exist
- workspace files exist
- `workspace.files_complete = true`

### rebuild-project

- local project exists
- runnable code exists
- tests exist
- `04_projekt_rebuild.md` points to the real result

### fill-gaps

- chosen questions were researched
- citations were integrated
- confidence was recorded

### save-to-vault

- draft exists in the Vault
- final confirmation was received
- `vault.status = done`
- note, bundle, and daily-note paths still validate

## Resume Rules

On resume:

1. read `run.json`
2. validate it
3. recompute `next_recommended_step`
4. cross-check filesystem state
5. continue from the computed next step

If state and filesystem disagree, repair state before proceeding.
