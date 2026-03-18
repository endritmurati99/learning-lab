# Learning Lab Workflow Specification

## Purpose

`learning-lab` uses a file-backed workflow state so that every run can be:

- resumed
- validated
- inspected
- kept consistent across `sources/`, `workspace/`, `projects/`, and the Vault

The canonical state file is:

`sources/{slug}/run.json`

This file is the workflow contract, not a casual note.

---

## State Mutation Rule

`run.json` must never be edited with ad-hoc text replacement.

All state writes must go through:

`python scripts/run_state.py ...`

This keeps writes atomic and avoids malformed JSON.

---

## Lifecycle

A run moves through these stages:

1. `source`
2. `ingest`
3. `notebooklm`
4. `workspace`
5. `fill_gaps`
6. `rebuild`
7. `vault`

Every stage has its own status plus stage-specific metadata.

---

## Allowed Status Values

The allowed generic status values are:

- `not_started`
- `in_progress`
- `awaiting_user_input`
- `awaiting_confirmation`
- `blocked`
- `failed`
- `skipped`
- `done`

`lab-master` or any downstream skill must not assume a stage is complete only because the status says `done`.
It must validate the filesystem state when the next action depends on it.

---

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
    "required_files": [
      "00_zusammenfassung.md",
      "01_kernkonzepte.md",
      "02_schritt_fuer_schritt.md",
      "03_uebungen.md",
      "04_projekt_rebuild.md",
      "05_offene_fragen.md",
      "06_notebooklm_artefakte.md",
      "07_logik_check.md"
    ],
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
    "note_path": null
  },
  "next_recommended_step": "ingest"
}
```

---

## Preflight Model

Preflight is staged, not global.

### Core preflight

Required for any run:

- `python`

Recommended for local reading and token control:

- `rtk`

### Source-type preflight

Required only when relevant:

- YouTube: `yt-dlp`
- Web pages: `defuddle`
- PDF compaction: `pandoc` if used, otherwise fall back

### Stage-type preflight

Required only for the stage being entered:

- NotebookLM generation: `notebooklm`
- Audio transcription fallback: `buzz` and ideally `ffmpeg`
- Vault export: `qmd`

If a stage cannot run, mark that stage as `blocked` or `failed` with a warning instead of silently continuing.

---

## Definition Of Done

### learn-source

`learn-source` is only `done` when all of the following are true:

- `sources/{slug}/run.json` exists and validates
- ingest artifacts exist for the chosen source type
- `notebooklm.notebook_id` is persisted in both:
  - `run.json`
  - `sources/{slug}/notebook_id.txt`
- `workspace/{slug}/` exists
- all required workspace files exist
- `workspace.files_complete` is `true`

### fill-gaps

`fill-gaps` is only `done` when:

- the selected questions were researched
- citations were added
- confidence was recorded
- unresolved questions remain marked as unresolved

### rebuild-project

`rebuild-project` is only `done` when:

- `projects/{slug}/` exists
- runnable code exists
- tests exist
- `workspace/{slug}/04_projekt_rebuild.md` points to the real project result

If the source is not rebuildable, use:

- `rebuild.status = "skipped"`
- `rebuild.reason = "..."`

### save-to-vault

`save-to-vault` is only `done` when:

- the draft was reviewed
- confirmation was received
- the note was written
- the asset copy step succeeded
- the daily note update succeeded

---

## Workspace File Contract

`workspace/{slug}/` must always contain the eight canonical files.

`04_projekt_rebuild.md` is not optional as a file.
Its contents may say one of:

- rebuildable now
- not applicable
- ready for rebuild later

`07_logik_check.md` is always required.

---

## Resume Rules

When a run is re-opened:

1. Read `run.json`
2. Validate it
3. Recompute `next_recommended_step`
4. Cross-check the filesystem
5. Resume from `next_recommended_step` only if the prerequisites for that step still hold

If the filesystem and state file disagree, prefer repairing the state over guessing.

---

## Example Commands

Initialize a new run:

```bash
python scripts/run_state.py init --slug example --source-type youtube --input "https://example.com" --title "Example"
```

Mark ingest in progress:

```bash
python scripts/run_state.py set --slug example --path ingest.status --value in_progress
python scripts/run_state.py set --slug example --path next_recommended_step --value ingest
```

Persist the NotebookLM notebook id:

```bash
python scripts/run_state.py persist-notebook-id --slug example --notebook-id 1234
```

Sync workspace file completeness:

```bash
python scripts/run_state.py sync-workspace --slug example
```

Show a concise workflow summary:

```bash
python scripts/run_state.py summary --slug example
```

Recompute the next recommended step:

```bash
python scripts/run_state.py refresh-next --slug example
```

Validate state plus required files:

```bash
python scripts/run_state.py validate --slug example --check-files
```
