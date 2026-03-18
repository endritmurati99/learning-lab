---
name: learn-source
description: Analyze a source (YouTube URL, web page URL, PDF path, or local text file) and create a structured 8-file learning package. Uses NotebookLM as the primary analysis engine and Claude Code for structuring the output. Triggers when the user says "lerne von X", "learn from X", provides a URL or file path to learn from, or asks to analyze a source for learning purposes. Supports resuming an existing run via `sources/{slug}/run.json`.
---

# Learn Source

Ingest a source, feed it to NotebookLM, and produce a structured 8-file learning package in German.
NotebookLM handles the heavy analysis. Claude Code orchestrates the workflow and keeps state in `sources/{slug}/run.json`.

## Prerequisites

- `python` available for `scripts/run_state.py`
- `rtk` available for token-efficient reading
- `yt-dlp` for YouTube sources
- `defuddle` for web page sources
- `notebooklm` CLI installed and authenticated
- `buzz` available if YouTube subtitles are missing and audio transcription fallback is needed
- `ffmpeg` strongly recommended for audio workflows
- `pandoc` optional for PDF compaction

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `source` | required | YouTube URL, web page URL, PDF path, or local file path |
| `deliverable` | `study_guide` | NotebookLM deliverable type: `study_guide`, `flashcards`, `infographic`, `mindmap`, `podcast`, `slides` |
| `topic` | auto-derived | Short topic label used for folder naming |

## Execution Steps

### Step 1 - Detect source type and slug

Determine the source type:

- YouTube: URL contains `youtube.com` or `youtu.be`
- Web page: URL starts with `http(s)://` and is not YouTube
- PDF: path ends in `.pdf`
- Local file: local `.md`, `.txt`, or other text-like file

Create a sanitized slug from the topic:

- lowercase
- hyphenated
- no special characters

If `sources/{slug}/run.json` already exists, this is a resume or multi-source update.
Validate the state file before doing more work:

```bash
python scripts/run_state.py validate --slug "{slug}"
```

### Step 2 - Staged preflight and state initialization

Run staged preflight instead of a single global all-or-nothing gate.

Core:

- required: `python`
- strongly preferred: `rtk`

Source-type checks:

- YouTube: `yt-dlp`
- Web page: `defuddle`
- PDF: `pandoc` if using PDF-to-Markdown compaction

Stage-type checks:

- NotebookLM generation: `notebooklm`
- Audio transcription fallback: `buzz`, ideally `ffmpeg`

If a required dependency for the chosen source or next stage is missing:

- stop before continuing
- mark the affected stage as `blocked` or `failed`
- add a warning to `run.json`

If `run.json` does not exist yet:

```bash
python scripts/run_state.py init --slug "{slug}" --source-type "{source_type}" --input "{source}" --title "{topic}"
```

Mark the ingest stage as active:

```bash
python scripts/run_state.py set --slug "{slug}" --path ingest.status --value in_progress
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value ingest
```

### Step 3 - Ingest source

Create `sources/{slug}/` if needed.

Important rule:

- data files keep data only
- warnings and stderr go to `.log` files

#### YouTube

Collect metadata:

```bash
yt-dlp "{youtube_url}" --skip-download --print "%(id)s\t%(title)s\t%(webpage_url)s\t%(view_count)s\t%(upload_date)s" --no-playlist > sources/{slug}/metadata.tsv 2>> sources/{slug}/ingest.log
```

Download subtitles:

```bash
yt-dlp "{youtube_url}" --skip-download --write-auto-sub --write-sub --sub-lang en --sub-format ttml --convert-subs srt --no-playlist -o "sources/{slug}/%(id)s.%(ext)s" 2>> sources/{slug}/ingest.log
```

If no subtitles exist, fall back to local audio transcription:

```bash
yt-dlp "{youtube_url}" -x --audio-format mp3 -o "sources/{slug}/audio.%(ext)s" 2>> sources/{slug}/ingest.log
buzz add --task transcribe --model medium --output-format srt "sources/{slug}/audio.mp3"
```

Download description and extra context:

```bash
yt-dlp "{youtube_url}" --write-description --write-info-json --get-comments --max-comments 20 --skip-download -o "sources/{slug}/extra_context.%(ext)s" 2>> sources/{slug}/ingest.log
```

Clean SRT to plain text and save `sources/{slug}/{video_id}.txt`.

#### Web page

```bash
defuddle parse "{url}" --md > sources/{slug}/content.md 2>> sources/{slug}/ingest.log
defuddle parse "{url}" -p title > sources/{slug}/title.txt 2>> sources/{slug}/ingest.log
```

If `defuddle` is unavailable, fall back to a web fetch / read flow and record that fallback in warnings.

#### PDF

Preferred if `pandoc` is available:

```bash
pandoc "{pdf_path}" -t markdown -o sources/{slug}/content.md
```

If `pandoc` is unavailable or fails, use the Read tool and save a text summary to `sources/{slug}/content.txt`.

#### Local file

Prefer `rtk read` when reading local files for analysis.
Copy or reference the local file in `sources/{slug}/`.

After ingest artifacts exist, record them in state:

```bash
python scripts/run_state.py append --slug "{slug}" --path ingest.artifacts --value metadata.tsv
python scripts/run_state.py append --slug "{slug}" --path ingest.log_files --value ingest.log
python scripts/run_state.py set --slug "{slug}" --path ingest.status --value done
python scripts/run_state.py set --slug "{slug}" --path notebooklm.status --value in_progress
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value notebooklm
```

Only append artifacts that actually exist.

### Step 4 - Send source to NotebookLM

If `sources/{slug}/notebook_id.txt` already exists, reuse it.
Otherwise create a new notebook:

```bash
notebooklm create --title "Learn: {topic}"
```

Persist the notebook id in both places:

```bash
python scripts/run_state.py persist-notebook-id --slug "{slug}" --notebook-id "{notebook_id}"
```

Add source files:

```bash
notebooklm add-source --notebook-id {notebook_id} --file sources/{slug}/{source_file}
```

Generate the requested deliverable:

```bash
notebooklm generate --notebook-id {notebook_id} --type {deliverable} --instructions "Identify hidden assumptions, unstated prerequisites, implicit biases, and conclusions that lack direct evidence." --output sources/{slug}/nlm-{deliverable}
```

If the CLI does not support `--instructions`, omit it and continue.

Record successful NotebookLM output:

```bash
python scripts/run_state.py append --slug "{slug}" --path notebooklm.deliverables --value "{deliverable}"
python scripts/run_state.py append --slug "{slug}" --path notebooklm.artifacts --value "nlm-{deliverable}"
python scripts/run_state.py set --slug "{slug}" --path notebooklm.status --value done
python scripts/run_state.py set --slug "{slug}" --path workspace.status --value in_progress
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value workspace
```

### Step 5 - Structure the learning package

Read source material plus NotebookLM output.
Prefer `rtk read` for local reading.

Create all eight files in `workspace/{slug}/`:

| File | Content |
|------|---------|
| `00_zusammenfassung.md` | Executive summary and core thesis |
| `01_kernkonzepte.md` | Core concepts with definitions and context |
| `02_schritt_fuer_schritt.md` | Step-by-step walkthrough |
| `03_uebungen.md` | Exercises and flashcards |
| `04_projekt_rebuild.md` | Always present; explicitly mark whether rebuild is applicable |
| `05_offene_fragen.md` | Open questions and gaps |
| `06_notebooklm_artefakte.md` | Notebook id plus deliverable paths |
| `07_logik_check.md` | Adversarial logic and bias check |

`04_projekt_rebuild.md` must never silently disappear.
Its content should clearly say one of:

- rebuildable now
- not applicable
- ready for rebuild later

Multi-source mode:

- merge into existing workspace files
- do not overwrite blindly
- keep earlier insights unless contradicted by new material

Language rules:

- workspace files stay in German
- source-faithful first
- interpretation second
- mark uncertainties as `Unsicherheit`

### Step 6 - Logic check, workspace sync, and next-step state

`07_logik_check.md` is mandatory.
It must cover:

- confirmation bias
- missing counter-perspectives
- unstated assumptions
- exaggerations or simplifications
- overall trust assessment

After writing workspace files, sync the workspace state:

```bash
python scripts/run_state.py sync-workspace --slug "{slug}"
python scripts/run_state.py set --slug "{slug}" --path workspace.status --value done
```

Set tutorial / rebuild state explicitly:

- if the source is tutorial-like or project-like:
  - `workspace.is_tutorial = true`
  - `rebuild.status = not_started`
  - `rebuild.reason = null`
  - `next_recommended_step = rebuild-project`
- otherwise:
  - `workspace.is_tutorial = false`
  - `rebuild.status = skipped`
  - `rebuild.reason = not_applicable`
  - `next_recommended_step = fill-gaps`

Then validate the full local state:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
```

### Step 7 - Report completion

Report:

```text
LEARN-SOURCE COMPLETE
Topic: {topic}
Source: {source_type} - {source}
NLM deliverable: {deliverable}
Learning package: workspace/{slug}/
State file: sources/{slug}/run.json
Next recommended step: {next_recommended_step}
```

## Quality Rules

- no invented APIs, tools, or features
- keep `metadata.tsv` data-only
- write warnings to `.log` files or `run.json`
- keep `run.json` and the filesystem in sync
- persist `notebook_id.txt` every time
- all eight workspace files are required

## Common Issues

| Problem | Fix |
|---------|-----|
| `yt-dlp` missing | Install or block YouTube ingestion before any further step |
| `notebooklm` missing | Stop before generation and mark NotebookLM stage as blocked |
| `buzz` missing | Only matters if subtitle fallback is needed |
| `pandoc` missing | Fall back to Read tool for PDFs |
| `run.json` invalid | Repair state with `scripts/run_state.py` before continuing |
| Workspace incomplete | Rebuild missing files and rerun `sync-workspace` plus `validate --check-files` |
