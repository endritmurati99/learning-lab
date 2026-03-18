---
name: cognitive-structurer
description: Structure the 8-file German learning package from already-ingested source material and NotebookLM output. Called by the Python orchestrator (lab.py) after ingest and NLM stages are done. Assumes sources/{slug}/ already contains transcript/content and NLM deliverable. Triggers when: orchestrator calls this after workspace.status is in_progress, or user manually says "structure workspace {slug}".
---

# Cognitive Structurer

**This skill does cognitive work only.**
All deterministic steps (source detection, yt-dlp, defuddle, notebooklm, state init) are handled by `python lab.py` BEFORE this skill runs.

When called, `sources/{slug}/` already contains:
- transcript / content file
- NotebookLM deliverable (e.g., `nlm-study_guide.md`)

Your job: read that material and write the 8 German workspace files.

## Prerequisites

- `sources/{slug}/run.json` exists with `workspace.status = in_progress`
- At least one source content file exists in `sources/{slug}/`
- At least one NLM artifact exists in `sources/{slug}/`

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | Source slug |

## Execution Steps

### Step 1 — Read source material

Read source content and NLM output from `sources/{slug}/`:
- Prefer `rtk read` for token-efficient reading

Identify whether the source is tutorial-like (contains step-by-step instructions, code, project builds) or conceptual (comparison, analysis, lecture).

### Step 2 — Structure the 8 workspace files

Create or update all eight files in `workspace/{slug}/`:

| File | Content |
|------|---------|
| `00_zusammenfassung.md` | Executive summary and core thesis |
| `01_kernkonzepte.md` | Key concepts with definitions and context |
| `02_schritt_fuer_schritt.md` | Step-by-step walkthrough |
| `03_uebungen.md` | Exercises and flashcards |
| `04_projekt_rebuild.md` | Rebuild blueprint or explicit "Nicht anwendbar" |
| `05_offene_fragen.md` | Open questions and uncertainties |
| `06_notebooklm_artefakte.md` | NLM notebook metadata and artifact paths |
| `07_logik_check.md` | Adversarial bias/assumption analysis (mandatory) |

`04_projekt_rebuild.md` must always be present and must clearly say one of:
- rebuildable now
- nicht anwendbar (not applicable)
- ready for rebuild later

`07_logik_check.md` must cover:
- confirmation bias
- missing counter-perspectives
- unstated assumptions
- exaggerations and simplifications
- overall trust assessment

Multi-source mode: merge into existing files; do not overwrite earlier insights unless contradicted.

Language rules:
- workspace files stay in German
- source-faithful first, interpretation second
- mark uncertainties as `Unsicherheit`

### Step 3 — Sync state and set next step

```bash
python scripts/run_state.py sync-workspace --slug "{slug}"
python scripts/run_state.py set --slug "{slug}" --path workspace.status --value done
```

Set tutorial/rebuild state explicitly:

- Tutorial source (is_tutorial = true):
  ```bash
  python scripts/run_state.py set --slug "{slug}" --path workspace.is_tutorial --value true --json
  python scripts/run_state.py set --slug "{slug}" --path rebuild.status --value not_started
  python scripts/run_state.py set --slug "{slug}" --path rebuild.reason --value null --json
  python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value rebuild-project
  ```

- Non-tutorial source:
  ```bash
  python scripts/run_state.py set --slug "{slug}" --path workspace.is_tutorial --value false --json
  python scripts/run_state.py set --slug "{slug}" --path rebuild.status --value skipped
  python scripts/run_state.py set --slug "{slug}" --path rebuild.reason --value not_applicable
  python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value fill-gaps
  ```

Validate:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
```

### Step 4 — Report

```text
COGNITIVE-STRUCTURER COMPLETE
Slug: {slug}
Workspace: workspace/{slug}/
Files written: {list}
Next recommended step: {next_recommended_step}
```

## Quality Rules

- no invented APIs, tools, or features
- all eight workspace files are required
- `07_logik_check.md` is mandatory — never skip it
- mark uncertainties explicitly
- `run.json` must reflect actual file state after sync
