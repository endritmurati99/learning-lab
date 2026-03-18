---
name: lab-master
description: Orchestrates learning-lab runs from source ingestion to Vault finalization, while preserving run.json as the workflow contract and save-to-vault as the single Vault writer.
---

# Lab Master

`lab-master` is the orchestrator.
It never owns `vault.*` state directly.
Its job is to:

- validate and resume
- choose the next stage
- trigger the right skill
- preserve confirmation boundaries

## Prerequisites

- `learn-source`, `fill-gaps`, `rebuild-project`, and `save-to-vault` are available
- `python` is available for `scripts/run_state.py`

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `source` | required | Raw source input or existing slug |
| `--rebuild` | optional | Include rebuild if applicable |
| `--fill-gaps` | optional | Include web research for open questions |
| `--vault` | optional | Allow Vault finalization when the workflow reaches that point |
| `--full-pipeline` | optional | Continue through all stages until the next hard boundary |

## Execution Model

### Fresh run mode

- input is a raw URL or local path
- trigger `learn-source`

### Resume mode

- input matches an existing slug
- validate `run.json`
- resume from `next_recommended_step`

## Execution Steps

### Step 1 - Resolve and validate

If `sources/{slug}/run.json` already exists:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

If no run exists yet:

- trigger `learn-source`
- then run the same validation steps

### Step 2 - Respect primary workflow priority

The primary stage order is:

1. ingest
2. notebooklm
3. workspace
4. rebuild-project
5. fill-gaps
6. save-to-vault

Vault drafts are side effects and must not overtake rebuild or fill-gaps.

### Step 3 - Auto-draft Vault support

When all of the following are true:

- `workspace.status = done`
- `vault.status = not_started`
- there is no hard Vault blocker

then `lab-master` should automatically trigger:

`save-to-vault` in `draft` mode

Important:

- `lab-master` must not set `vault.status` itself
- `lab-master` may only trigger the skill
- after the draft is prepared, `lab-master` must refresh state and continue using the primary stage order

This means:

- if rebuild is still pending, next step remains `rebuild-project`
- if fill-gaps is still pending, next step remains `fill-gaps`
- only after those are settled does `save-to-vault` become the next recommended step

### Step 4 - Route by `next_recommended_step`

Use this routing table:

- `ingest`, `notebooklm`, `workspace`
  - trigger `learn-source`
- `rebuild-project`
  - trigger `rebuild-project` if requested or implied by `--full-pipeline`
  - otherwise stop and report
- `fill-gaps`
  - trigger `fill-gaps` if requested or implied by `--full-pipeline`
  - otherwise stop and report
- `save-to-vault`
  - trigger `save-to-vault` in `finalize` mode only if requested via `--vault` or implied by `--full-pipeline`
  - otherwise stop and report
- `complete`
  - report completion

### Step 5 - Refresh after each stage

After every executed stage:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

### Step 6 - Stop at boundaries

`lab-master` must pause and report clearly when:

- `fill-gaps` is waiting for question selection
- `fill-gaps` is waiting for edit confirmation
- `save-to-vault` is waiting for final confirmation
- `save-to-vault` is in `blocked_input`
- `save-to-vault` is in `failed`

### Step 7 - Report status

Use a report shaped like this:

```text
LAB-MASTER STATUS
Input: {source_or_slug}
Slug: {slug}

Current state:
- Ingest: {status}
- NotebookLM: {status}
- Workspace: {status}
- Rebuild: {status}
- Fill Gaps: {status}
- Vault: {status}

Stored next step: {stored_next}
Computed next step: {computed_next}

Primary outputs:
- Workspace: workspace/{slug}/
- Project: projects/{slug}/
- Vault note: {vault_note_if_any}
- State: sources/{slug}/run.json
```

## Quality Rules

- `run.json` is the workflow contract
- `save-to-vault` is the only writer of `vault.*`
- auto-draft is allowed for all source types
- final Vault completion always requires confirmation
- do not let Vault draft logic hide a pending rebuild or fill-gaps step
