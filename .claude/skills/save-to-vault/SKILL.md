---
name: save-to-vault
description: Transfer a completed learning package from workspace to The Vault (Obsidian) in the correct format. Converts German workspace files into a single English research note matching The Vault's conventions, copies assets, and updates the daily note. Use when the user says "speichere im Vault", "save to vault", "ab in den Vault", or wants to persist learning results to Obsidian.
---

# Save to Vault

Exports a completed learning package from `workspace/{slug}/` to The Vault as a properly formatted Obsidian research note. Handles format transformation (German workspace → English Vault), asset copying, and daily note updates.

## Prerequisites

- A completed learning package in `workspace/{slug}/` (created by `learn-source`)
- The Vault must exist at the path configured in `.claude/settings.json` → `vault_path`

## Inputs (ask user if missing)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | The slug of the learning package in `workspace/` |
| `note_title` | auto-derived from slug | Title for the Vault research note |

## Execution Steps

### Step 1 — Resolve Vault path and verify prerequisites

Read `vault_path` from `.claude/settings.json`. If not set, fall back to `c:/Users/endri/Desktop/Claude-Projects/The Vault/`.

Check that `workspace/{slug}/` exists with at least `00_zusammenfassung.md`. If not, tell the user to run `learn-source` first.

Check that The Vault exists at the resolved `{vault_path}`.

### Step 2 — Check Vault & Conventions

Use the `qmd search "{topic}"` command to semantically check if a note on this exact topic already exists.

Read `{vault_path}/CLAUDE.md` to confirm current conventions are still in effect. Also read `docs/vault-format-reference.md` in this project for the note template.

### Step 3 — Read workspace files

Read all files in `workspace/{slug}/`:
- `00_zusammenfassung.md`
- `01_kernkonzepte.md`
- `02_schritt_fuer_schritt.md`
- `03_uebungen.md` (will not be exported)
- `04_projekt_rebuild.md` (if exists)
- `05_offene_fragen.md`
- `06_notebooklm_artefakte.md` (if exists)
- `07_logik_check.md` (if exists)

Also read `sources/{slug}/metadata.tsv` or similar for source metadata.

### Step 4 — Transform to Vault format

Convert German workspace content into a single English research note. The note must be analytical, first-person, and practical-implications-focused.

**Mapping:**

| Workspace File | Vault Section |
|----------------|---------------|
| `00_zusammenfassung.md` | **Core Thesis** (1-2 paragraph synthesis) + **Executive Summary** (longer narrative) |
| `01_kernkonzepte.md` | **Key Takeaways** (bullet points with `[[wiki-links]]`) + **High-Signal Concepts To Revisit** (each concept as `[[wiki-link]]`). *Note: Utilize the `obsidian-markdown` skill to generate appropriate callouts for important concepts.* |
| `02_schritt_fuer_schritt.md` | Folded into **Executive Summary** if relevant, otherwise omitted |
| `03_uebungen.md` | **Not exported** — stays in workspace only |
| `04_projekt_rebuild.md` | **Practical Implications For My Workflow** (if exists) |
| `05_offene_fragen.md` | **Open Questions** |
| `06_notebooklm_artefakte.md` | Referenced in **Source Notes** section |
| `07_logik_check.md` | Folded into **Open Questions** or a **Critical Analysis** subsection |

### Step 5 — Generate the research note

Write the note to `{vault_path}/research/{Note-Title}.md` using this exact structure:

```markdown
---
research_date: {YYYY-MM-DD}
source_url: "{URL or path}"
source_label: "{Source Label}"
tags:
  - research
  - {topic-tag}
transcript: "[[research/assets/{slug}-transcript.txt]]"
---

# {Title}

## Core Thesis

{Synthesized from 00_zusammenfassung — central argument in 1-2 paragraphs}

## Key Takeaways

{Bullet points from 01_kernkonzepte, each with [[wiki-links]] to concepts}

## Executive Summary

{Longer narrative from 00_zusammenfassung + 02_schritt_fuer_schritt}

## Practical Implications For My Workflow

{From 04_projekt_rebuild if exists, otherwise derive from 01_kernkonzepte}

## High-Signal Concepts To Revisit

{Each core concept as a [[wiki-link]], extracted from 01_kernkonzepte}

## Open Questions

{From 05_offene_fragen + critical analysis from 07_logik_check if exists}

## Source Notes

{Provenance: source type, capture date, method used}
{List of NLM deliverables generated, if any}
```

**Critical format rules:**
- **YAML Properties (frontmatter)** for metadata — `research_date`, `source_url`, `source_label`, `tags`, `transcript`
- **Wiki-link syntax** `[[...]]` for all internal concept references
- **Asset paths in wiki-links:** use `[[research/assets/...]]`
- **Asset paths on disk:** write to `research/assets/`
- **Language:** English
- **Tone:** analytical, first-person, practical-implications-focused

### Step 6 — Verify backlinks against existing Vault notes

Instead of manually scanning directories, use semantic vector search via `qmd`.

**Critical Backlink Strategy:**
Cross-reference every concept from `workspace/{slug}/01_kernkonzepte.md` against The Vault using:
`qmd search "{Concept}"`

Since `qmd` is semantic, it natively understands synonyms and variations, solving the duplicate-note problem. Append limits if necessary or let QMD return its top semantic matches.

**If the concept already has its own note in The Vault, it MUST be wiki-linked as `[[Existing-Note-Title]]` in the research note.** Do not create orphan references when a linkable target exists.

Log any new concepts that do not yet have Vault notes — these are candidates for future standalone notes.

### Step 7 — Copy assets

Copy source assets to The Vault:

- Transcript: `sources/{slug}/*.txt` → `{vault_path}/research/assets/{slug}-transcript.txt`
- NLM deliverables: `sources/{slug}/nlm-*` → `{vault_path}/research/assets/{slug}-{type}.{ext}`

### Step 8 — Update daily note

Check if `{vault_path}/daily-notes/{YYYY-MM-DD}.md` exists.

**If it exists:** Append under the `## Research` section:

```markdown
- Added [[{Note-Title}]]
- Main insight: {one-sentence summary of the core thesis}
```

**If it does not exist:** Create it:

```markdown
# {YYYY-MM-DD}

## Research
- Added [[{Note-Title}]]
- Main insight: {one-sentence summary of the core thesis}
```

### Step 9 — Confirm and ask before writing

**Important:** Before writing any files to The Vault, show the user:
1. The research note content (or a summary)
2. The list of assets to copy
3. The daily note update

Ask for explicit confirmation before proceeding.

### Step 10 — Report completion

```
SAVE-TO-VAULT COMPLETE
Research note: {vault_path}/research/{Note-Title}.md
Assets copied: {list of files}
Daily note updated: {vault_path}/daily-notes/{YYYY-MM-DD}.md

Open Obsidian to verify [[wiki-links]] and graph view.

Optional cleanup:
- sources/{slug}/   (raw source material)
- workspace/{slug}/ (learning package drafts)
Shall I clean these up?
```

## Common Issues

| Problem | Fix |
|---------|-----|
| Vault not found | Verify `vault_path` in `.claude/settings.json` |
| research/ folder missing | Create it: `mkdir -p "{vault_path}/research/assets/"` |
| Daily note format mismatch | Re-read The Vault's CLAUDE.md for current conventions |
| Wiki-links not resolving in Obsidian | Ensure `[[Note-Title]]` matches the exact filename without `.md` |
