---
name: learn-source
description: Analyze a source (YouTube URL, web page URL, PDF path, or local text file) and create a structured 8-file learning package. Uses NotebookLM as the primary analysis engine and Claude Code for structuring the output. Triggers when the user says "lerne von X", "learn from X", provides a URL or file path to learn from, or asks to analyze a source for learning purposes. Supports adding multiple sources to an existing topic.
---

# Learn Source

Ingests a source, feeds it to NotebookLM for analysis, and produces a structured 8-file learning package in German. NotebookLM handles the heavy analysis at zero token cost. Claude Code orchestrates and structures the output. Supports multi-source mode: adding new sources to an existing slug's notebook.

## Prerequisites

- `yt-dlp` installed (`pip install yt-dlp`) — for YouTube sources
- `buzz` installed (`winget install Buzz`) — for offline Whisper transcription
- `rtk` installed — for token-efficient file reading
- `defuddle` installed (`npm install -g defuddle`) — for web page sources
- `notebooklm` CLI installed and authenticated

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

**Multi-source check:** If `sources/{slug}/` already exists, this is an additional source for an existing topic. Read `sources/{slug}/notebook_id.txt` to get the existing NLM notebook ID. Skip notebook creation in Step 3 and add the new source to the existing notebook instead.

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

If no transcripts are available, download the audio and use Buzz for 100% local, token-free transcription:
```bash
yt-dlp "{youtube_url}" -x --audio-format mp3 -o "sources/{slug}/audio.%(ext)s"
buzz add --task transcribe --model medium --output-format srt "sources/{slug}/audio.mp3"
```

Download description, metadata JSON, and top comments for extra context:

```bash
yt-dlp "{youtube_url}" \
  --write-description \
  --write-info-json \
  --get-comments \
  --max-comments 20 \
  --skip-download \
  -o "sources/{slug}/extra_context.%(ext)s"
```

Clean SRT to plain text using this Python snippet:

```python
import re, pathlib

def clean_srt(srt_path: str) -> str:
    path = pathlib.Path(srt_path)
    if not path.exists(): return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Remove index lines, timestamps, and HTML tags in one pass
    text = re.sub(r'(\d+\n)?\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', text)
    text = re.sub(r'<[^>]*>', '', text)
    # Efficient line deduplication (preserves order)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cleaned = []
    for i, line in enumerate(lines):
        if i == 0 or line != lines[i-1]:
            cleaned.append(line)
    return ' '.join(cleaned)
```

Save clean transcripts as `sources/{slug}/{video_id}.txt`.

#### Web page

```bash
defuddle parse "{url}" --md > sources/{slug}/content.md
defuddle parse "{url}" -p title > sources/{slug}/title.txt
```

If defuddle is not installed, fall back to the WebFetch tool.

#### PDF

Use `pandoc` if available to convert PDF strictly to compact Markdown, saving up to 50% tokens:
```bash
pandoc "{pdf_path}" -t markdown -o sources/{slug}/content.md
```
If Pandoc fails or is not installed, use Claude Code's Read tool. Save a text summary to `sources/{slug}/content.txt`.

#### Local file

When reading the local file (`.md`, `.txt`), prefer `rtk read` instead of `cat` or raw tools to drastically reduce token usage:
```bash
rtk read "{file_path}"
```
Copy or reference the file in `sources/{slug}/`.

### Step 3 — Send to NotebookLM

**New topic (no existing slug):** Create a notebook and add all source files:

```bash
notebooklm create --title "Learn: {topic}"
# Save the returned notebook_id to sources/{slug}/notebook_id.txt
```

**Existing topic (slug already exists):** Read the notebook ID:

```bash
set /p notebook_id=<sources/{slug}/notebook_id.txt
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
  --instructions "Identify and explicitly list any hidden assumptions the author makes. Flag unstated prerequisites, implicit biases, and conclusions that lack direct evidence." \
  --output sources/{slug}/nlm-{deliverable}
```

> **Note:** The `--instructions` flag passes custom prompting to NLM. If the CLI version does not support it, omit it — the generation will still work without custom instructions.

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

Read the NLM output plus the original source material. **CRITICAL:** Use `rtk read` to read the files to filter out boilerplate and save context tokens!

Create 8 files in `workspace/{slug}/`:

| File | Content | Source |
|------|---------|--------|
| `00_zusammenfassung.md` | Executive summary | NLM study guide + source |
| `01_kernkonzepte.md` | Core concepts with definitions and context | NLM analysis |
| `02_schritt_fuer_schritt.md` | Step-by-step walkthrough | Source material |
| `03_uebungen.md` | Exercises and flashcards | NLM flashcards if generated |
| `04_projekt_rebuild.md` | Project rebuild blueprint | Only if source is tutorial/project |
| `05_offene_fragen.md` | Open questions and gaps | Claude analysis of NLM output |
| `06_notebooklm_artefakte.md` | Links to all NLM deliverables | File paths |
| `07_logik_check.md` | Bias analysis and missing perspectives | Adversarial Claude analysis |

**For multi-source mode:** Merge new material into existing workspace files rather than overwriting. Append new concepts to `01_kernkonzepte.md`, add new questions to `05_offene_fragen.md`, etc.

**Language:** All workspace files in German.

**Quality rules:**
- Distinguish strictly between facts from the source and own conclusions
- Mark uncertainties explicitly as `Unsicherheit`
- No invented APIs, tools, or features
- Source-faithful first, interpretation second

### Step 4b — Adversarial logic check

After structuring the learning package, run an adversarial analysis of the NLM output and source material. Write `workspace/{slug}/07_logik_check.md`:

```markdown
# Logik-Check: {topic}

## Bestätigungsfehler (Confirmation Bias)
{List any claims the source presents as fact without evidence}
{Note where the NLM summary amplified the source's bias}

## Fehlende Gegenperspektiven
{Counter-arguments or alternative viewpoints not addressed in the source}

## Unausgesprochene Annahmen
{Assumptions the author makes implicitly without stating them}

## Übertreibungen / Vereinfachungen
{Claims that are overstated or oversimplified}

## Gesamtbewertung
{1-2 sentence assessment of how trustworthy and balanced the source is}
```

This step is critical for preventing uncritical knowledge absorption. The analysis should be honest and specific — vague "could be biased" statements are not useful.

### Step 5 — Report completion

```
LEARN-SOURCE COMPLETE
Topic: {topic}
Source: {source_type} — {source}
NLM deliverable: {deliverable} → sources/{slug}/nlm-{deliverable}.*
Learning package: workspace/{slug}/ (8 files)

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
