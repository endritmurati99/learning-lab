---
name: learn-source
description: Analyze a source (YouTube URL, web page URL, PDF path, or local text file) and create a structured 8-file learning package. Preferred invocation: `python lab.py <source> [options]` — the Python orchestrator handles all deterministic steps. This skill is the cognitive-only fallback for interactive Claude Code sessions when lab.py is unavailable. Triggers when the user says "lerne von X", "learn from X", provides a URL or file path to learn from.
---

# Learn Source

> **Preferred path:** Use `python lab.py <source> [--auto] [--full-pipeline]`
> The Python orchestrator handles all deterministic steps (ingest, NotebookLM, state) without burning tokens.
> This skill is for interactive fallback when `lab.py` is not usable.

---

## When to use this skill (vs. lab.py)

| Situation | Use |
|-----------|-----|
| Normal run | `python lab.py <url> --verbose` |
| Full auto run | `python lab.py <url> --full-pipeline --auto` |
| Resume from slug | `python lab.py <slug> --fill-gaps --vault` |
| Claude Code interactive only | This skill |

---

## Interactive Fallback: Full Steps

If `lab.py` is unavailable, this skill runs the full pipeline interactively.

### Step 1 — Detect source type and slug

- YouTube: URL contains `youtube.com` or `youtu.be`
- Web page: URL starts with `http(s)://` and is not YouTube
- PDF: path ends in `.pdf`
- Local file: local `.md`, `.txt`, or other text-like file

Create sanitized slug (lowercase, hyphenated, no special characters).

If `sources/{slug}/run.json` exists, validate and resume:
```bash
python scripts/run_state.py validate --slug "{slug}"
```

### Step 2 — Preflight and state init

Core requirements: `python`, `rtk`
Source-type: `yt-dlp` (YouTube), `defuddle` (web), `pandoc` (PDF optional)
Stage: `notebooklm`, `buzz`/`ffmpeg` (audio fallback)

If `run.json` does not exist:
```bash
python scripts/run_state.py init --slug "{slug}" --source-type "{source_type}" --input "{source}" --title "{topic}"
python scripts/run_state.py set --slug "{slug}" --path ingest.status --value in_progress
```

### Step 3 — Ingest source

#### YouTube
```bash
yt-dlp "{url}" --skip-download --print "%(id)s\t%(title)s\t%(webpage_url)s\t%(view_count)s\t%(upload_date)s" --no-playlist > sources/{slug}/metadata.tsv 2>> sources/{slug}/ingest.log
yt-dlp "{url}" --skip-download --write-auto-sub --write-sub --sub-lang en --sub-format ttml --convert-subs srt --no-playlist -o "sources/{slug}/%(id)s.%(ext)s" 2>> sources/{slug}/ingest.log
```
Clean SRT to plain text → `sources/{slug}/{video_id}.txt`
Audio fallback if no subtitles: `yt-dlp -x --audio-format mp3` → `buzz transcribe`

#### Web page
```bash
defuddle parse "{url}" --md > sources/{slug}/content.md 2>> sources/{slug}/ingest.log
```

#### PDF
```bash
pandoc "{path}" -t markdown -o sources/{slug}/content.md
```

Record artifacts:
```bash
python scripts/run_state.py append --slug "{slug}" --path ingest.artifacts --value metadata.tsv
python scripts/run_state.py set --slug "{slug}" --path ingest.status --value done
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value notebooklm
```

### Step 4 — Send to NotebookLM

Reuse `sources/{slug}/notebook_id.txt` if it exists, else:
```bash
notebooklm create --title "Learn: {topic}"
python scripts/run_state.py persist-notebook-id --slug "{slug}" --notebook-id "{notebook_id}"
notebooklm add-source --notebook-id {notebook_id} --file sources/{slug}/{source_file}
notebooklm generate --notebook-id {notebook_id} --type {deliverable} --output sources/{slug}/nlm-{deliverable}
```

```bash
python scripts/run_state.py set --slug "{slug}" --path notebooklm.status --value done
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value workspace
```

### Step 5–6 — Structure workspace (cognitive work)

Delegate to the `cognitive-structurer` skill for the actual file writing.
The cognitive-structurer handles all 8 files + logic check + state sync.

---

## Quality Rules

- no invented APIs, tools, or features
- keep `metadata.tsv` data-only; warnings to `.log` files
- all eight workspace files are required
- `run.json` and filesystem must stay in sync
