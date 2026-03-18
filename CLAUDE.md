# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A skill-based learning pipeline for Claude Code. Take any source (YouTube video, web page, PDF, local file) and produce a structured 7-file learning package in German, with final polished notes exported to The Vault (Obsidian).

**Core principle:** Im Projekt wird gearbeitet. Im Vault wird Wissen gespeichert. (Work in the project. Store knowledge in The Vault.)

---

## Architecture Overview

### Three-Skill Pipeline

1. **`learn-source`** — Detect source type → ingest via yt-dlp/defuddle/Read tool → send to NotebookLM → structure output into 7-file learning package in `workspace/{slug}/`
2. **`rebuild-project`** — Take a tutorial source and create a minimal MVP project in `projects/{slug}/`
3. **`save-to-vault`** — Transform German workspace files into English research note and copy to The Vault (`The Vault/research/{Note-Title}.md`), plus append daily note

### Key Separation

- **Workspace** (`sources/`, `workspace/`, `projects/`) — German, working drafts, gitignored ephemeral files
- **The Vault** (`The Vault/research/`, `The Vault/daily-notes/`) — English, final polished output, separate Obsidian vault (not tracked in this repo)
- **The Vault path:** `c:/Users/endri/Desktop/Claude-Projects/The Vault/`

---

## Working with Skills

### NotebookLM Is The Analysis Engine

- Zero token cost — all heavy computation runs on Google's servers
- Accessible via `notebooklm` CLI (unofficial wrapper)
- **Auth:** `notebooklm login` in a *separate terminal* (opens browser OAuth). Do not run inside Claude Code.

### Deliverable Types

| Type | Time | Best For |
|------|------|----------|
| `study_guide` | <1 min | Text summaries (default) |
| `flashcards` | <1 min | Q&A and exercises |
| `infographic` | ~6 min | Visual summaries |
| `mindmap` | ~6 min | Topic relationships |
| `podcast` | ~8 min | Audio discussions |
| `slides` | ~15 min | Presentation decks |

### Source Type Detection

- **YouTube:** `https://youtube.com` or `https://youtu.be` → `yt-dlp` extracts transcript (SRT → plaintext)
- **Web page:** `http(s)://` (not YouTube) → `defuddle parse <url> --md`
- **PDF:** `.pdf` extension → Claude Code Read tool → summarize
- **Local file:** `.md`, `.txt` → Claude Code Read tool

---

## 7-File Learning Package Format

Each `workspace/{slug}/` contains:

| File | Purpose | Language |
|------|---------|----------|
| `00_zusammenfassung.md` | Executive summary + core thesis | German |
| `01_kernkonzepte.md` | Concepts with definitions | German |
| `02_schritt_fuer_schritt.md` | Step-by-step walkthrough | German |
| `03_uebungen.md` | Flashcards + exercises (not exported to Vault) | German |
| `04_projekt_rebuild.md` | Rebuild blueprint (only for tutorials) | German |
| `05_offene_fragen.md` | Open questions, gaps, uncertainties | German |
| `06_notebooklm_artefakte.md` | File paths to NLM outputs + notebook metadata | German |

---

## The Vault Export Format

When exporting via `save-to-vault`:

### Research Note

- Location: `The Vault/research/{Note-Title}.md`
- **No YAML frontmatter** — use inline header blocks (`> Research generated:`, `> Source:`)
- Language: English
- Structure:
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
- All internal references use wiki-links: `[[Note-Title]]`
- Tone: analytical, first-person, practical-implications-focused

### Assets

- Transcripts: `The Vault/research/assets/{slug}-transcript.txt`
- NLM outputs: `The Vault/research/assets/{slug}-{type}.{ext}`
- **Important:** Wiki-link references use intentional misspelling: `[[reserch/assets/...]]` (not `research`)

### Daily Note

- Location: `The Vault/daily-notes/{YYYY-MM-DD}.md`
- Append new entries under `## Research` section

---

## Permissions & Safety

### Allowed Tools

Per `.claude/settings.json`:
- `Bash(yt-dlp:*)`, `Bash(notebooklm:*)`, `Bash(defuddle:*)`
- `Bash(python:*)`, `Bash(python3:*)`

### Safety Rules

- Never auto-delete `sources/` or `workspace/` files — always ask first
- Never commit to git: `.env`, `vault/**`, NotebookLM credentials, secrets
- Write to The Vault only with explicit user confirmation (via `save-to-vault` skill)
- Distinguish strictly: facts from source vs. own interpretation/conclusions
- Mark uncertainties explicitly as "Unsicherheit" in German workspace files
- No invented APIs, tools, or features — source-faithful first

---

## Common Tasks

### Ingest a Source

```
User provides URL or file → trigger `learn-source`
→ Ask which NLM deliverable (default: study_guide)
→ Auto-create workspace/{slug}/
→ Detect source type
→ Extract transcript / markdown
→ Create NLM notebook
→ Add source + generate deliverable
→ Structure into 7-file package
→ Report completion
```

### Export to The Vault

```
User: "save to vault {slug}"
→ Read workspace files
→ Check Vault conventions (CLAUDE.md)
→ Transform German → English
→ Create research note with inline headers
→ Copy assets to research/assets/
→ Update daily note
→ Ask for confirmation before writing
```

---

## Language Convention

- **Workspace files:** German (working drafts, closer to source material)
- **Vault research notes:** English (final, polished, analytical)
- **Config & docs:** English
- Workspace file quality rule: source-faithful first, interpretation second

---

## Related Projects

This project complements two related systems:
- **NLM+Obsidian** — same analysis engine (NotebookLM), but builds the vault inside the repo with Python orchestration
- **agentic-lab** — a note-capture pipeline using n8n + Claude Code, separate Obsidian vault 
