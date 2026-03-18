---
name: lab-master
description: Orchestrates the learning-lab workflow from either a fresh source or an existing slug. Uses `sources/{slug}/run.json` as the workflow contract, validates the current state, resumes from the next recommended step, and stops at user-decision boundaries when needed.
---

# Lab Master

`lab-master` is the entrypoint for `learning-lab`.
It should feel like a product workflow, not a loose sequence of manually chained skills.

The central rule:

- always inspect `sources/{slug}/run.json` first when a run already exists
- never guess the next step if the state file and filesystem can tell you

## Prerequisites

- `learn-source`, `fill-gaps`, `rebuild-project`, and `save-to-vault` skills must be available
- `python` must be available for `scripts/run_state.py`

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `source` | required | Raw source input or an existing slug |
| `--rebuild` | optional | Explicitly include rebuild if applicable |
| `--fill-gaps` | optional | Explicitly include fill-gaps |
| `--vault` | optional | Explicitly include Vault export |
| `--full-pipeline` | optional | Continue through all relevant stages until the next user confirmation boundary |

## Execution Model

`lab-master` has two modes:

1. fresh run mode
   - input is a raw URL or local path
   - trigger `learn-source`
2. resume mode
   - input matches an existing slug in `sources/{slug}/` or `workspace/{slug}/`
   - validate and resume from state

## Execution Steps

### Step 1 - Resolve target

Interpret the user input:

- if it matches an existing slug directory, treat it as `{slug}`
- otherwise treat it as a fresh `{source}`

If you only have a fresh source, derive or wait for `learn-source` to derive the slug.

### Step 2 - Validate or initialize workflow state

If `sources/{slug}/run.json` already exists:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

If the state file does not exist yet:

- trigger `learn-source` with the provided source
- after `learn-source` completes, validate and summarize the new state:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

### Step 3 - Determine execution envelope

Default behavior:

- continue only to the next sensible workflow step
- do not force later stages if the user did not ask for them

If flags are present:

- `--rebuild` means include rebuild if applicable
- `--fill-gaps` means include research for open questions
- `--vault` means prepare Vault export
- `--full-pipeline` means try to continue through all relevant stages

Important:

- stop at explicit confirmation boundaries
- do not bypass the confirmation behavior of `fill-gaps` or `save-to-vault`

### Step 4 - Resume from `next_recommended_step`

Read `next_recommended_step` from `run.json`.
Treat it as the default route after running `refresh-next`.

Use this routing table:

- `ingest`, `notebooklm`, or `workspace`
  - trigger `learn-source` on the same source / slug context
- `rebuild-project`
  - if the source is tutorial-like and rebuild is requested or implied by `--full-pipeline`, trigger `rebuild-project`
  - otherwise leave rebuild untouched and continue to the next requested stage only if appropriate
- `fill-gaps`
  - if requested or `--full-pipeline`, trigger `fill-gaps`
  - otherwise stop and report that this is the next recommended step
- `save-to-vault`
  - if requested or `--full-pipeline`, trigger `save-to-vault`
  - otherwise stop and report that this is the next recommended step
- `complete`
  - report that the run is fully completed

### Step 5 - Refresh state after every executed stage

After each executed stage:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

This is what gives the workflow resumability and idempotence.

### Step 6 - Stop at user-decision boundaries

`lab-master` must stop and report clearly when:

- `fill-gaps` is waiting for the user to choose which questions to research
- `fill-gaps` is waiting for confirmation before modifying workspace files
- `save-to-vault` is waiting for confirmation before writing to the Vault

In these cases, do not present the run as complete.
Present it as paused at a known workflow boundary.

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

Executed in this run:
- [x/ ] learn-source
- [x/ ] rebuild-project
- [x/ ] fill-gaps
- [x/ ] save-to-vault

Stored next step: {stored_next}
Computed next step: {computed_next}

Primary outputs:
- Workspace: workspace/{slug}/
- Project: projects/{slug}/
- State: sources/{slug}/run.json
- Vault note: {vault_note_if_any}
```

## Quality Rules

- validate state before resuming
- refresh `next_recommended_step` before trusting it
- stop at confirmation boundaries
- do not skip rebuild for tutorial sources without marking why
- do not claim completion if the state says otherwise

## Common Cases

### Fresh source, no flags

- run `learn-source`
- stop after summarizing the next recommended step

### Existing slug, no flags

- validate state
- summarize current stage
- continue only if the next step is still inside `learn-source`
- otherwise stop and tell the user what comes next

### Existing slug with `--full-pipeline`

- validate state
- refresh the next step
- continue stage by stage
- stop when the workflow reaches:
  - question selection
  - edit confirmation
  - Vault write confirmation

### Existing slug already complete

- report `complete`
- do not rerun completed stages unless the user explicitly asks
