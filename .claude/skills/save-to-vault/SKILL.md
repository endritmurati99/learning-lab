---
name: save-to-vault
description: Transfer a completed or near-complete learning package into The Vault using source bundles, project mirrors, and a concept-first research note title. Tracks draft/export progress in `run.json`.
---

# Save to Vault

`save-to-vault` exports an existing learning package into The Vault as:

- a research note in `research/`
- a source-specific asset bundle in `research/assets/{source_type}/{slug}/`
- an optional project mirror in `projects/{project-slug}/`
- a daily-note update

This step always stops for explicit confirmation before the final write.

## Prerequisites

- `sources/{slug}/run.json` exists
- `workspace/{slug}/` exists and is complete enough to summarize
- the Vault exists at `vault_path`
- `docs/vault-format-reference.md` is the current source of truth

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | The learning-package slug |
| `note_title` | concept-first auto-suggestion | Human-facing Vault note title |
| `project_slug` | optional | Vault folder slug for mirrored rebuild output |

## Execution Steps

### Step 1 - Validate state and local files

Before doing any Vault work:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

Resolve `vault_path` from `.claude/settings.json`.
Confirm that the Vault exists.

### Step 2 - Check Vault conventions and existing notes

Read:

- `docs/vault-format-reference.md`
- `{vault_path}/CLAUDE.md` if available

Check whether a closely related research note already exists.

Title rule:

- do not blindly reuse clicky source titles
- prefer a calmer, concept-first note title
- example: `Reusable Claude Skills for Agent Workflows`

### Step 3 - Read workspace, source metadata, and external research

Read the workspace package plus source metadata from `sources/{slug}/`.

Relevant files:

- `00_zusammenfassung.md`
- `01_kernkonzepte.md`
- `02_schritt_fuer_schritt.md`
- `04_projekt_rebuild.md`
- `05_offene_fragen.md`
- `06_notebooklm_artefakte.md`
- `07_logik_check.md`
- `metadata.tsv`
- available `nlm-*` files

If `fill-gaps` has already been run or official docs / web research were used, include them as `External Validation`.

### Step 4 - Build the Vault draft

Create a draft research note in English with:

- YAML frontmatter
- `transcript`
- `asset_bundle`
- optional `project_bundle`
- core thesis
- key takeaways
- executive summary
- practical implications
- high-signal concepts
- external validation
- open questions
- source notes

The note should be the synthesis layer, not a dump of raw artifacts.

### Step 5 - Enter confirmation boundary

Before writing anything to the Vault:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.status --value awaiting_confirmation
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value save-to-vault
```

Show the user:

1. the draft note
2. the target note title
3. the asset bundle destination
4. the optional project mirror destination
5. the daily-note update

Ask for explicit confirmation.

### Step 6 - Write to the Vault

After confirmation:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.status --value in_progress
```

Use `scripts/vault_sync.py` to prepare support files:

```bash
python scripts/vault_sync.py export-run-support --slug "{slug}" --note-title "{note_title}" --project-slug "{project_slug}" --project-title "{project_title}" --main-insight "{main_insight}"
```

Write:

- the research note to `{vault_path}/research/{note_title}.md`
- source assets to `{vault_path}/research/assets/{source_type}/{slug}/`
- optional project mirror to `{vault_path}/projects/{project_slug}/`
- the daily-note update to `{vault_path}/daily-notes/{YYYY-MM-DD}.md`

### Step 7 - Persist completion in state

After a successful write:

```bash
python scripts/run_state.py set --slug "{slug}" --path vault.note_path --value "{vault_path}/research/{note_title}.md"
python scripts/run_state.py set --slug "{slug}" --path vault.status --value done
python scripts/run_state.py refresh-next --slug "{slug}"
```

If the write fails:

- set `vault.status = failed`
- do not claim completion

### Step 8 - Report completion

```text
SAVE-TO-VAULT COMPLETE
Slug: {slug}
Research note: {vault_path}/research/{note_title}.md
Asset bundle: {vault_path}/research/assets/{source_type}/{slug}/
Project mirror: {vault_path}/projects/{project_slug}/
Daily note updated: {vault_path}/daily-notes/{YYYY-MM-DD}.md
Next recommended step: {next_recommended_step}
```

## Quality Rules

- never write to the Vault without confirmation
- keep the research note readable and synthesis-first
- keep raw files inside source bundles, not flat in `research/assets/`
- prefer concept-first titles over source clickbait
- include web validation when it materially improves trust
- if a rebuild exists, mirror the readable files into `projects/`
