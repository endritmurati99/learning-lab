---
name: save-to-vault
description: Single-writer workflow for Obsidian exports. Prepares Vault drafts for all source types, then finalizes them only after explicit confirmation.
---

# Save to Vault

`save-to-vault` is the only business-layer owner of `vault.*` in `run.json`.
It has two modes:

- `draft` - prepare or refresh the Obsidian draft
- `finalize` - mark the reviewed draft as final

`vault_sync.py` may write files, but only under the direction of this skill.

## Prerequisites

- `sources/{slug}/run.json` exists
- `workspace/{slug}/` exists and is complete enough to summarize
- `docs/vault-format-reference.md` is the current Vault contract
- the Vault exists at `vault_path`

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | Learning-package slug |
| `mode` | `draft` | `draft` or `finalize` |
| `note_title` | auto | Concept-first title for the Vault note |
| `project_slug` | optional | Vault project mirror slug |

## Execution Steps

### Step 1 - Validate state

Always start with:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

### Step 2 - Read local inputs

Read:

- `00_zusammenfassung.md`
- `01_kernkonzepte.md`
- `02_schritt_fuer_schritt.md`
- `04_projekt_rebuild.md`
- `05_offene_fragen.md`
- `06_notebooklm_artefakte.md`
- `07_logik_check.md`
- source metadata from `sources/{slug}/`

If external web validation exists, keep it clearly separate as `External Validation`.

### Step 3 - Draft mode

Use `draft` mode when:

- `workspace.status = done`
- the Vault draft does not exist yet
- or the draft must be refreshed after rebuild / fill-gaps changes

Draft mode must:

1. choose a concept-first `note_title`
2. generate the draft note body in English
3. write that draft body to a temporary local file
4. call `vault_sync.py export-draft`
5. update `run.json` with the returned paths and identity

Required command:

```bash
python scripts/vault_sync.py export-draft --slug "{slug}" --note-title "{note_title}" --note-body-file "{temp_note_body}" --main-insight "{main_insight}" --project-slug "{project_slug}" --project-title "{project_title}"
```

After a successful draft export:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.note_path --value "{note_path}"
python scripts/run_state.py set --slug "{slug}" --path vault.bundle_path --value "{bundle_path}"
python scripts/run_state.py set --slug "{slug}" --path vault.project_bundle_path --value "{project_bundle_path_or_null}" --json
python scripts/run_state.py set --slug "{slug}" --path vault.daily_note_path --value "{daily_note_path}"
python scripts/run_state.py set --slug "{slug}" --path vault.draft_title --value "{note_title}"
python scripts/run_state.py set --slug "{slug}" --path vault.export_identity --json --value "{export_identity_json}"
python scripts/run_state.py set --slug "{slug}" --path vault.last_exported_at --value "{timestamp}"
python scripts/run_state.py set --slug "{slug}" --path vault.last_error_code --json --value "null"
python scripts/run_state.py set --slug "{slug}" --path vault.last_error_message --json --value "null"
python scripts/run_state.py set --slug "{slug}" --path vault.status --value draft_prepared
```

Important:

- draft mode is allowed before `fill-gaps` is complete
- draft mode must not force `next_recommended_step` away from `rebuild-project` or `fill-gaps`

### Step 4 - Finalize mode

Use `finalize` mode only when:

- `workspace.status = done`
- `rebuild.status` is `done` or `skipped`
- `fill_gaps.status` is `done` or `skipped`
- `vault.status` is `draft_prepared`, `awaiting_confirmation`, or `stale`

Before finalizing:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.status --value awaiting_confirmation
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value save-to-vault
```

Show the user:

- note title
- note path
- bundle path
- optional project bundle path
- daily note path
- summary of the draft content

Only after explicit confirmation:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.status --value done
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py validate --slug "{slug}" --check-files
```

### Step 5 - Error handling

If `vault_sync.py` fails, set:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.last_error_code --value "{error_code}"
python scripts/run_state.py set --slug "{slug}" --path vault.last_error_message --value "{error_message}"
python scripts/run_state.py set --slug "{slug}" --path vault.status --value failed
```

If the failure is a user/input problem such as note-path collision:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.last_error_code --value "{error_code}"
python scripts/run_state.py set --slug "{slug}" --path vault.last_error_message --value "{error_message}"
python scripts/run_state.py set --slug "{slug}" --path vault.status --value blocked_input
```

### Step 6 - Report

```text
SAVE-TO-VAULT STATUS
Slug: {slug}
Mode: {mode}
Vault status: {vault_status}
Note: {note_path}
Bundle: {bundle_path}
Project bundle: {project_bundle_path}
Daily note: {daily_note_path}
Next recommended step: {next_recommended_step}
```

## Quality Rules

- `save-to-vault` is the single writer for `vault.*`
- never finalize without explicit confirmation (unless `auto_mode` is active and no existing note would be overwritten)
- drafts are allowed early, finals are not
- note titles are concept-first, not source-clickbait-first
- daily-note entries must be updated by marker, never blindly appended
- project mirrors only exist when rebuild is actually done
