# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A skill-based learning pipeline for Claude Code. Take any source (YouTube video, web page, PDF, local file) and produce a structured 8-file learning package in German, with final polished notes exported to The Vault (Obsidian).

**Core principle:** Im Projekt wird gearbeitet. Im Vault wird Wissen gespeichert. (Work in the project. Store knowledge in The Vault.)

---

## Architecture Overview

### Five-Skill Pipeline

0. **`lab-master`** — Master orchestrator that natively chains the entire pipeline (`learn-source` → `fill-gaps` → `rebuild-project` → `save-to-vault`) across a single source in one command. Supports `--auto` flag for fully non-interactive runs.
1. **`learn-source`** — Detect source type → ingest via yt-dlp/defuddle/Read tool → send to NotebookLM → structure output into 8-file learning package in `workspace/{slug}/`. Supports multi-source: adding new sources to an existing slug's NLM notebook.
2. **`rebuild-project`** — Take a tutorial source and create a minimal MVP project in `projects/{slug}/`
3. **`fill-gaps`** — Read open questions from `05_offene_fragen.md` → web search → integrate answers back into workspace with source attribution
4. **`save-to-vault`** — Transform German workspace files into English research note with YAML Properties and copy to The Vault (`{vault_path}/research/{Note-Title}.md`), plus append daily note

### Key Separation

- **Workspace** (`sources/`, `workspace/`, `projects/`) — German, working drafts, gitignored ephemeral files
- **The Vault** (`The Vault/research/`, `The Vault/daily-notes/`) — English, final polished output, separate Obsidian vault (not tracked in this repo)
- **The Vault path:** Configured in `.claude/settings.json` → `vault_path` (default: `c:/Users/endri/Desktop/Claude-Projects/The Vault/`)

### Token Efficiency Tools

- **`rtk`**: Proxy for file reading (`rtk read`) that strips boilerplate and compresses tokens by ~80-90%.
- **`buzz`**: Local, offline Whisper transcription CLI that replaces costly LLM-based web transcription at zero token and zero API cost.
- **`obsidian-cli`**: Global skill used to semantically search the Vault (`obsidian search` and `obsidian backlinks`) without dumping mass file context into Claude.

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

## 8-File Learning Package Format

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
| `07_logik_check.md` | Bias analysis, missing counter-arguments | German |

---

## The Vault Export Format

When exporting via `save-to-vault`:

### Research Note

- Location: `{vault_path}/research/{Note-Title}.md`
- **YAML frontmatter** — see `docs/vault-format-reference.md` for the canonical template
- Key frontmatter fields: `research_date`, `source_url`, `source_label`, `source_type`, `source_slug`, `tags`, `transcript`, `asset_bundle`, `project_bundle` (optional), `draft_status`, `export_identity`, `external_validation`
- Language: English
- Structure:
  ```md
  ---
  research_date: YYYY-MM-DD
  source_url: "https://..."
  source_label: "Label"
  source_type: "youtube"
  source_slug: "example-slug"
  tags: [research, topic]
  transcript: "[[research/assets/{source_type}/{source_slug}/transcript.txt]]"
  asset_bundle: "[[research/assets/{source_type}/{source_slug}/Source Bundle]]"
  draft_status: draft_prepared
  export_identity: "{source_type}:{source_slug}:sha256:..."
  external_validation: false
  ---

  # {Title}

  ## Core Thesis
  ## Key Takeaways
  ## Executive Summary
  ## Practical Implications For My Workflow
  ## High-Signal Concepts To Revisit
  ## External Validation
  ## Open Questions
  ## Source Notes
  ```
- All internal references use wiki-links: `[[Note-Title]]`
- Tone: analytical, first-person, practical-implications-focused

### Assets

- Location: `{vault_path}/research/assets/{source_type}/{source_slug}/`
- Contains: `Source Bundle.md`, `transcript.txt`, `metadata.tsv`, NLM deliverables
- Wiki-link: `[[research/assets/{source_type}/{source_slug}/Source Bundle]]`

### Daily Note

- Location: `{vault_path}/daily-notes/{YYYY-MM-DD}.md`
- Update existing `<!-- learning-lab:{source_type}:{source_slug} -->` block or append under `## Research`

---

## Permissions & Safety

### Allowed Tools

Per `.claude/settings.json`:
- `Bash(yt-dlp:*)`, `Bash(notebooklm:*)`, `Bash(defuddle:*)`
- `Bash(python:*)`, `Bash(python3:*)`

### Safety Rules

- Never auto-delete `sources/` or `workspace/` files — always ask first
- Never commit to git: `.env`, `vault/**`, NotebookLM credentials, secrets
- Write to The Vault only with explicit user confirmation (via `save-to-vault` skill) — exception: `--auto` mode skips confirmation for new notes, but always stops if a note already exists
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
→ Structure into 8-file package (incl. adversarial logic check)
→ Report completion
```

### Fill Knowledge Gaps

```
User: "fill gaps {slug}" or "fülle Lücken"
→ Read 05_offene_fragen.md
→ Prioritize questions by researchability
→ Web search per question
→ Integrate answers into 01_kernkonzepte.md (marked "Extern recherchiert")
→ Move answered questions to "Gelöst" section
→ Report completion
```

### Export to The Vault

```
User: "save to vault {slug}"
→ Read vault_path from settings.json
→ Read workspace files + source metadata
→ Check Vault conventions (docs/vault-format-reference.md)
→ Transform German → English
→ Build draft research note with full YAML frontmatter
→ Check for existing note at target path
→ Ask for confirmation before writing (skipped in --auto mode for new notes)
→ Call: python scripts/vault_sync.py export-draft --slug ... --note-title ... --main-insight ...
→ Update daily note via marker block
```

---

## Language Convention

- **Workspace files:** German (working drafts, closer to source material)
- **Vault research notes:** English (final, polished, analytical)
- **Config & docs:** English
- Workspace file quality rule: source-faithful first, interpretation second

---

## Scripts

| Script | Commands | Purpose |
|--------|----------|---------|
| `scripts/run_state.py` | `init`, `show`, `set`, `append`, `validate`, `persist-notebook-id`, `sync-workspace`, `summary`, `refresh-next` | Sole writer for `sources/{slug}/run.json`. All state changes go through this. |
| `scripts/vault_sync.py` | `export-draft`, `migrate-flat-assets` | Prepare Vault export bundles; migrate old flat assets to typed subfolders |

### Vault-only Run Statuses

The `vault` stage uses its own status vocabulary:

| Status | Meaning |
|--------|---------|
| `draft_prepared` | Draft note built, ready for confirmation |
| `blocked_input` | Waiting for user to provide missing input |
| `awaiting_confirmation` | Waiting for explicit write approval |
| `done` | Successfully written to Vault |
| `failed` | Write failed |
| `stale` | Draft exists but source data has changed |

---

## Related Projects

This project complements two related systems:
- **NLM+Obsidian** — same analysis engine (NotebookLM), but builds the vault inside the repo with Python orchestration
- **agentic-lab** — a note-capture pipeline using n8n + Claude Code, separate Obsidian vault 
