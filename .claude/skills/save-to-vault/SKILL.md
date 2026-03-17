---
name: save-to-vault
description: Transfer a completed learning package from workspace to The Vault (Obsidian) in the correct format. Converts German workspace files into a single English research note matching The Vault's conventions, copies assets, and updates the daily note. Use when the user says "speichere im Vault", "save to vault", "ab in den Vault", or wants to persist learning results to Obsidian.
---

# Save to Vault

Exports a completed learning package from `workspace/{slug}/` to The Vault as a properly formatted Obsidian research note. Handles format transformation (German workspace → English Vault), asset copying, and daily note updates.

## Prerequisites

- A completed learning package in `workspace/{slug}/` (created by `learn-source`)
- The Vault must exist at `c:/Users/endri/Desktop/Claude-Projects/The Vault/`

## Inputs (ask user if missing)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | The slug of the learning package in `workspace/` |
| `note_title` | auto-derived from slug | Title for the Vault research note |

## Execution Steps

### Step 1 — Verify prerequisites

Check that `workspace/{slug}/` exists with at least `00_zusammenfassung.md`. If not, tell the user to run `learn-source` first.

Check that The Vault exists at `c:/Users/endri/Desktop/Claude-Projects/The Vault/`.

### Step 2 — Read current Vault conventions

Read `c:/Users/endri/Desktop/Claude-Projects/The Vault/CLAUDE.md` to confirm current conventions are still in effect. Also read `docs/vault-format-reference.md` in this project for the note template.

### Step 3 — Read workspace files

Read all files in `workspace/{slug}/`:
- `00_zusammenfassung.md`
- `01_kernkonzepte.md`
- `02_schritt_fuer_schritt.md`
- `03_uebungen.md` (will not be exported)
- `04_projekt_rebuild.md` (if exists)
- `05_offene_fragen.md`
- `06_notebooklm_artefakte.md` (if exists)

Also read `sources/{slug}/metadata.tsv` or similar for source metadata.

### Step 4 — Transform to Vault format

Convert German workspace content into a single English research note. The note must be analytical, first-person, and practical-implications-focused.

**Mapping:**

| Workspace File | Vault Section |
|----------------|---------------|
| `00_zusammenfassung.md` | **Core Thesis** (1-2 paragraph synthesis) + **Executive Summary** (longer narrative) |
| `01_kernkonzepte.md` | **Key Takeaways** (bullet points with `[[wiki-links]]`) + **High-Signal Concepts To Revisit** (each concept as `[[wiki-link]]`) |
| `02_schritt_fuer_schritt.md` | Folded into **Executive Summary** if relevant, otherwise omitted |
| `03_uebungen.md` | **Not exported** — stays in workspace only |
| `04_projekt_rebuild.md` | **Practical Implications For My Workflow** (if exists) |
| `05_offene_fragen.md` | **Open Questions** |
| `06_notebooklm_artefakte.md` | Referenced in **Source Notes** section |

### Step 5 — Generate the research note

Write the note to `c:/Users/endri/Desktop/Claude-Projects/The Vault/research/{Note-Title}.md` using this exact structure:

```markdown
# {Title}

> Research generated: {YYYY-MM-DD}
> Source: [{Source Label}]({URL or path})
> {Additional metadata: publish date, views, etc.}
> Transcript: [[reserch/assets/{slug}-transcript.txt]]

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

{From 05_offene_fragen}

## Source Notes

{Provenance: source type, capture date, method used}
{List of NLM deliverables generated, if any}
```

**Critical format rules:**
- **NO YAML frontmatter** — use inline `>` header blocks
- **Wiki-link syntax** `[[...]]` for all internal concept references
- **Asset paths in wiki-links:** use `[[reserch/assets/...]]` (intentional spelling)
- **Asset paths on disk:** write to `research/assets/` (correct spelling)
- **Language:** English
- **Tone:** analytical, first-person, practical-implications-focused

### Step 6 — Copy assets

Copy source assets to The Vault:

- Transcript: `sources/{slug}/*.txt` → `The Vault/research/assets/{slug}-transcript.txt`
- NLM deliverables: `sources/{slug}/nlm-*` → `The Vault/research/assets/{slug}-{type}.{ext}`

### Step 7 — Update daily note

Check if `c:/Users/endri/Desktop/Claude-Projects/The Vault/daily-notes/{YYYY-MM-DD}.md` exists.

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

### Step 8 — Confirm and ask before writing

**Important:** Before writing any files to The Vault, show the user:
1. The research note content (or a summary)
2. The list of assets to copy
3. The daily note update

Ask for explicit confirmation before proceeding.

### Step 9 — Report completion

```
SAVE-TO-VAULT COMPLETE
Research note: The Vault/research/{Note-Title}.md
Assets copied: {list of files}
Daily note updated: The Vault/daily-notes/{YYYY-MM-DD}.md

Open Obsidian to verify [[wiki-links]] and graph view.

Optional cleanup:
- sources/{slug}/   (raw source material)
- workspace/{slug}/ (learning package drafts)
Shall I clean these up?
```

## Common Issues

| Problem | Fix |
|---------|-----|
| Vault not found | Verify path: `c:/Users/endri/Desktop/Claude-Projects/The Vault/` |
| research/ folder missing | Create it: `mkdir -p "The Vault/research/assets/"` |
| Daily note format mismatch | Re-read The Vault's CLAUDE.md for current conventions |
| Wiki-links not resolving in Obsidian | Ensure `[[Note-Title]]` matches the exact filename without `.md` |
