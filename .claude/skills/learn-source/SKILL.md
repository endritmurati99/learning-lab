---
name: learn-source
description: Analyze a source (YouTube URL, web page URL, PDF path, or local text file) and create a structured 6-file learning package. Uses NotebookLM as the primary analysis engine and Claude Code for structuring the output. Triggers when the user says "lerne von X", "learn from X", provides a URL or file path to learn from, or asks to analyze a source for learning purposes.
---

# Learn Source

Ingests a source, feeds it to NotebookLM for analysis, and produces a structured 6-file learning package in German. NotebookLM handles the heavy analysis at zero token cost. Claude Code orchestrates and structures the output.

## Prerequisites

- `yt-dlp` installed (`pip install yt-dlp`) — for YouTube sources
- `defuddle` installed (`npm install -g defuddle`) — for web page sources
- `notebooklm` CLI installed and authenticated (`pip install notebooklm`, then `notebooklm login` in a separate terminal)

## Inputs (ask user if missing)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `source` | required | YouTube URL, web page URL, PDF path, or local file path |
| `deliverable` | `study_guide` | NotebookLM deliverable type: `study_guide`, `flashcards`, `infographic`, `mindmap`, `podcast`, `slides` |
| `topic` | auto-derived from source title | Short topic label used for folder naming |

## Execution Steps

### Step 1 — Detect source type

Determine the source type from the input:
- **YouTube:** URL contains `youtube.com` or `youtu.be`
- **Web page:** URL starts with `http(s)://` and is not YouTube
- **PDF:** Path ends in `.pdf`
- **Local file:** Path to `.md`, `.txt`, or other text file

Create a sanitized slug from the topic for folder naming (lowercase, hyphens, no special chars).

### Step 2 — Ingest source

#### YouTube

Search and collect metadata:

```bash
yt-dlp "{youtube_url}" \
  --skip-download \
  --print "%(id)s\t%(title)s\t%(webpage_url)s\t%(view_count)s\t%(upload_date)s" \
  --no-playlist \
  > sources/{slug}/metadata.tsv
```

Download auto-generated transcripts:

```bash
yt-dlp "{youtube_url}" \
  --skip-download \
  --write-auto-sub \
  --write-sub \
  --sub-lang en \
  --sub-format ttml \
  --convert-subs srt \
  --no-playlist \
  -o "sources/{slug}/%(id)s.%(ext)s"
```

Clean SRT to plain text using this Python snippet:

```python
import re, pathlib

def clean_srt(srt_path: str) -> str:
    text = pathlib.Path(srt_path).read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', '', text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    deduped = [lines[0]] + [l for i, l in enumerate(lines[1:]) if l != lines[i]]
    return ' '.join(deduped)
```

Save clean transcripts as `sources/{slug}/{video_id}.txt`.

#### Web page

```bash
defuddle parse "{url}" --md > sources/{slug}/content.md
defuddle parse "{url}" -p title > sources/{slug}/title.txt
```

If defuddle is not installed, fall back to the WebFetch tool.

#### PDF

Use Claude Code's Read tool to read the PDF. Save a text summary to `sources/{slug}/content.txt`.

#### Local file

Use Claude Code's Read tool. Copy or reference the file in `sources/{slug}/`.

### Step 3 — Send to NotebookLM

Create a notebook and add all source files:

```bash
notebooklm create --title "Learn: {topic}"
# Save the returned notebook_id
```

Add each source file:

```bash
notebooklm add-source \
  --notebook-id {notebook_id} \
  --file sources/{slug}/{source_file}
```

Generate the requested deliverable:

```bash
notebooklm generate \
  --notebook-id {notebook_id} \
  --type {deliverable} \
  --output sources/{slug}/nlm-{deliverable}
```

Expected generation times:
- `study_guide`: < 1 minute
- `flashcards`: < 1 minute
- `infographic`: ~6 minutes
- `mindmap`: ~6 minutes
- `podcast`: ~8 minutes
- `slides`: ~15 minutes

Wait for completion. Do not cancel — the job runs on Google's servers at zero token cost.

Save all NLM output to `sources/{slug}/`.

### Step 4 — Structure learning package

Read the NLM output plus the original source material. Create 7 files in `workspace/{slug}/`:

| File | Content | Source |
|------|---------|--------|
| `00_zusammenfassung.md` | Executive summary | NLM study guide + source |
| `01_kernkonzepte.md` | Core concepts with definitions and context | NLM analysis |
| `02_schritt_fuer_schritt.md` | Step-by-step walkthrough | Source material |
| `03_uebungen.md` | Exercises and flashcards | NLM flashcards if generated |
| `04_projekt_rebuild.md` | Project rebuild blueprint | Only if source is tutorial/project |
| `05_offene_fragen.md` | Open questions and gaps | Claude analysis of NLM output |
| `06_notebooklm_artefakte.md` | Links to all NLM deliverables | File paths |

**Language:** All workspace files in German.

**Quality rules:**
- Distinguish strictly between facts from the source and own conclusions
- Mark uncertainties explicitly as `Unsicherheit`
- No invented APIs, tools, or features
- Source-faithful first, interpretation second

### Step 5 — Report completion

```
LEARN-SOURCE COMPLETE
Topic: {topic}
Source: {source_type} — {source}
NLM deliverable: {deliverable} → sources/{slug}/nlm-{deliverable}.*
Learning package: workspace/{slug}/ (7 files)

Next steps:
- /rebuild-project {slug}  (if this was a tutorial/project source)
- /save-to-vault {slug}    (to export to The Vault)
```

## Common Issues

| Problem | Fix |
|---------|-----|
| `yt-dlp: command not found` | `pip install yt-dlp` or `pip install -U yt-dlp` |
| No transcripts available | Some videos disable captions — skip and use video title/description |
| `notebooklm: command not found` | `pip install notebooklm` |
| NLM auth expired | Run `notebooklm login` in a separate terminal |
| `defuddle: command not found` | `npm install -g defuddle` or use WebFetch as fallback |
| Source too large for NLM | Split into chunks < 500KB each |
| NLM generation timeout | Long-form deliverables take up to 15 min — wait |
| Rate limiting (yt-dlp) | Add `--sleep-interval 2 --max-sleep-interval 5` |
