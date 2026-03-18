---
name: rebuild-project
description: Take a tutorial or project-based source that was already analyzed by learn-source and create a minimal, testable MVP project rebuild. Uses `run.json` to validate preconditions, track rebuild progress, and persist the resulting project path.
---

# Rebuild Project

`rebuild-project` turns a rebuildable learning package into a real MVP in `projects/{slug}/`.
This is not a documentation-only step.

## Prerequisites

- `sources/{slug}/run.json` exists
- `workspace/{slug}/` exists
- `workspace.status` is effectively complete

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | The slug of the learning package |
| `target_lang` | auto-derived | Programming language if not obvious |
| `scope` | `mvp` | `mvp` or `full` |

## Execution Steps

### Step 1 - Validate state and workspace

Before doing any rebuild work:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

If the workspace is incomplete, stop and fix `learn-source` first.

### Step 2 - Decide whether rebuild is applicable

Check whether the source is actually technical and rebuildable.

If it is not suitable for rebuild:

```bash
python scripts/run_state.py set --slug "{slug}" --path rebuild.status --value skipped
python scripts/run_state.py set --slug "{slug}" --path rebuild.reason --value not_applicable
python scripts/run_state.py refresh-next --slug "{slug}"
```

Then report that rebuild was explicitly skipped.

### Step 3 - Mark rebuild in progress

If rebuild is applicable:

```bash
python scripts/run_state.py set --slug "{slug}" --path rebuild.status --value in_progress
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value rebuild-project
```

### Step 4 - Read the source package

Read in this order:

1. `workspace/{slug}/00_zusammenfassung.md`
2. `workspace/{slug}/01_kernkonzepte.md`
3. `workspace/{slug}/02_schritt_fuer_schritt.md`
4. `workspace/{slug}/04_projekt_rebuild.md`
5. original source material in `sources/{slug}/`
6. available NotebookLM outputs in `sources/{slug}/nlm-*`

Use `rtk read` when useful for local reading.

### Step 5 - Design the MVP

Determine:

1. business goal
2. success metric
3. stack
4. minimum viable scope
5. what will be intentionally skipped

Mark assumptions explicitly as `Annahme`.
Mark unclear source gaps as `Zu verifizieren`.

### Step 6 - Build the project

Create `projects/{slug}/` with:

- runnable code
- a `README.md`
- a `tests/` directory
- at least 3 functional tests

The rebuild must be minimal but real.

### Step 7 - Update the learning package

Update `workspace/{slug}/04_projekt_rebuild.md` so it points to the real rebuild result, not just a speculative blueprint.

It should include:

- goal
- success metric
- assumptions
- architecture
- file structure
- implementation order
- tests
- failure path
- next sprint
- missing information

### Step 8 - Persist rebuild result in state

After a successful rebuild:

```bash
python scripts/run_state.py set --slug "{slug}" --path rebuild.project_path --value "projects/{slug}"
python scripts/run_state.py set --slug "{slug}" --path rebuild.status --value done
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py validate --slug "{slug}" --check-files
```

If the rebuild fails partway through:

- use `rebuild.status = failed`
- record the reason in `rebuild.reason`
- do not claim completion

### Step 9 - Report completion

```text
REBUILD-PROJECT COMPLETE
Slug: {slug}
Project: projects/{slug}/
Tech stack: {stack}
Scope: {scope}
Next recommended step: {next_recommended_step}
```

## Quality Rules

- MVP first
- real code, not just notes
- tests are required
- keep `run.json` synchronized with the actual result
- skip explicitly when rebuild does not apply
