# learning-lab

## What This Is

A skill-based learning pipeline for Claude Code. Give it a source (YouTube video, web page, PDF, local text file) and it produces a structured learning package. Optionally rebuild tutorial projects as MVPs. Final consolidated knowledge goes to The Vault.

**NotebookLM is the primary analysis engine.** It offloads heavy AI analysis to Google at zero token cost. Claude Code orchestrates the pipeline and formats outputs.

## Core Principle

> Im Projekt wird gearbeitet. Im Vault wird Wissen gespeichert.

- This project folder = workspace. Sources, drafts, temp files live here.
- The Vault = final knowledge store. Only polished, consolidated output goes there.
- The Vault path: `c:/Users/endri/Desktop/Claude-Projects/The Vault/`

## Pipeline

```
Source (YouTube / web / PDF / text)
    │
    ▼
[learn-source]
    │  1. Detect & ingest source (yt-dlp / defuddle / Read)
    │  2. Feed to NotebookLM (create → add-source → generate)
    │  3. Structure NLM output into 6-file learning package
    ▼
workspace/{slug}/  (German, working drafts)
    │
    ├── [rebuild-project]  →  projects/{slug}/  (optional, for tutorials)
    │
    └── [save-to-vault]    →  The Vault/research/{Note-Title}.md  (English, final)
                               The Vault/daily-notes/{date}.md  (append)
```

## Skills

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `learn-source` | URL, file path, "lerne von X" | Ingest source → NLM analysis → 6-file learning package |
| `rebuild-project` | "baue nach", "rebuild" | Create MVP from tutorial/project source |
| `save-to-vault` | "speichere im Vault", "save to vault" | Export to The Vault in correct Obsidian format |

## NotebookLM

Primary analysis engine. Zero token cost — compute runs on Google.

### CLI Commands

```bash
notebooklm create --title "{title}"
notebooklm add-source --notebook-id {id} --file {source_file}
notebooklm generate --notebook-id {id} --type {deliverable} --output {path}
```

### Auth

Run `notebooklm login` in a separate terminal (browser OAuth). Not inside Claude Code.

### Deliverable Types

| Type | Time | Notes |
|------|------|-------|
| `study_guide` | <1 min | Default. Text analysis. |
| `flashcards` | <1 min | PDF/JSON. Feeds into exercises. |
| `infographic` | ~6 min | PNG/PDF. Visual summary. |
| `mindmap` | ~6 min | PNG/SVG. Topic relationships. |
| `podcast` | ~8 min | MP3. AI audio discussion. |
| `slides` | ~15 min | PDF. Full presentation. |

## Source Intake

| Source Type | Method |
|-------------|--------|
| YouTube URL | `yt-dlp` for metadata + transcript (SRT → clean text) |
| Web page URL | `defuddle parse <url> --md` for clean markdown |
| PDF file | Claude Code Read tool |
| Local .md/.txt | Claude Code Read tool |

## Repository Layout

```
learning-lab/
├── sources/        # Raw ingested material (transcripts, NLM output)
├── workspace/      # Learning packages (6 files per source, German)
├── projects/       # MVP project rebuilds
├── docs/           # Conventions and references
├── .claude/
│   ├── settings.json
│   └── skills/     # learn-source, rebuild-project, save-to-vault
```

## Language

- **Workspace files** (learning packages): German
- **Vault research notes**: English (matches existing Vault tone)
- **Config and docs**: English

## Working File Policy

- `sources/` and `workspace/` contain working files
- Never auto-delete. Always ask before cleanup.
- `projects/` persists — rebuilds have ongoing value.

## The Vault Integration

| Target | Path | Format |
|--------|------|--------|
| Research note | `The Vault/research/{Note-Title}.md` | Inline header block, no YAML, wiki-links |
| Source asset | `The Vault/research/assets/{slug}-transcript.txt` | Plain text |
| NLM deliverables | `The Vault/research/assets/{slug}-{type}.{ext}` | PNG/PDF/MP3/JSON |
| Daily note | `The Vault/daily-notes/{YYYY-MM-DD}.md` | Append under `## Research` |

**Important:** Write files to `research/` (real disk path). Use `[[reserch/assets/...]]` in wiki-link references inside note content.

## Vault Note Format

```md
# {Title}

> Research generated: YYYY-MM-DD
> Source: [Label](URL)

## Core Thesis
## Key Takeaways
## Executive Summary
## Practical Implications For My Workflow
## High-Signal Concepts To Revisit
## Open Questions
## Source Notes
```

- No YAML frontmatter — use inline header blocks
- Wiki-link syntax `[[...]]` for all internal references
- Analytical, first-person, practical-implications-focused tone

## Global Skills Available

These are installed globally (`~/.claude/skills/`) and should be used, not duplicated:
- `obsidian-markdown`: wiki-links, callouts, embeds, properties
- `defuddle`: extract clean markdown from web pages

## Safety Rules

- Never write to The Vault without explicit user confirmation via save-to-vault
- Never auto-delete sources or workspace files
- Never commit secrets, .env files, or vault content to git
- Distinguish strictly between facts from the source and own conclusions
- Mark uncertainties explicitly

## Relation to NLM+Obsidian

Same analysis engine (NotebookLM), different architecture:
- No Python `src/` pipeline — Claude Code orchestrates via skills
- The Vault is a separate target, not the project folder
- Extended source types (web via defuddle, PDF, local files)
- Structured 6-file learning package instead of single research note
