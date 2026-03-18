# The Vault - Format Reference

Quick reference for the `save-to-vault` flow and the new Obsidian bundle structure.

## Vault Path

Configured in `.claude/settings.json` via `vault_path`.

Current default:

`c:/Users/endri/Desktop/Claude-Projects/The Vault/`

## Folder Structure

```text
The Vault/
├── daily-notes/
├── projects/
│   └── {project-slug}/
│       ├── Project Note.md
│       ├── code/
│       └── example-output/
├── research/
│   ├── {Note Title}.md
│   └── assets/
│       ├── youtube/{source-slug}/
│       ├── web/{source-slug}/
│       ├── pdf/{source-slug}/
│       └── source/{source-slug}/
└── .obsidian/
```

## Core Idea

The research note should be the human-readable synthesis.
The asset bundle should keep every source-specific artifact together.
The project bundle should mirror rebuild code in a readable, Obsidian-friendly way.

This avoids a flat `research/assets/` graveyard and gives every note a clear source home.

## Asset Bundle Rules

Assets belong under:

`research/assets/{source_type}/{source_slug}/`

Typical files:

- `Source Bundle.md`
- `transcript.txt`
- `transcript.srt`
- `metadata.tsv`
- `study-guide.md`
- `nlm-report.md`
- `nlm-flashcards.md`
- `nlm-mindmap.json`
- `nlm-slides.pdf`

Rules:

- group by source type first, then slug
- keep filenames canonical inside the folder
- always create `Source Bundle.md`
- every research note should link to the bundle

## Project Bundle Rules

When a rebuild exists, mirror selected project files into:

`projects/{project-slug}/`

Minimum contents:

- `Project Note.md`
- `code/README.md`
- main source files
- tests
- visible example output if useful

Important:

- the Vault mirror is for reading, navigation, and learning
- the executable source of truth stays in the repo

## Research Note Title Rules

Do not blindly reuse the source title.

Prefer:

- concept-first titles
- shorter, calmer names
- titles that describe what I want to remember

Good pattern:

- `Reusable Claude Skills for Agent Workflows`

Less useful pattern:

- `Master 95% of Claude Code Skills in 28 Minutes`

## Research Note Template

```md
---
research_date: YYYY-MM-DD
source_url: "https://example.com"
source_label: "Source Label"
source_type: "youtube"
source_slug: "example-slug"
tags:
  - research
  - topic-tag
transcript: "[[research/assets/{source_type}/{source_slug}/transcript.txt]]"
asset_bundle: "[[research/assets/{source_type}/{source_slug}/Source Bundle]]"
project_bundle: "[[projects/{project-slug}/Project Note]]" # optional
---

# {Note Title}

> Research generated: YYYY-MM-DD
> Source: [Label](URL)
> Transcript: [[research/assets/{source_type}/{source_slug}/transcript.txt]]
> Asset Bundle: [[research/assets/{source_type}/{source_slug}/Source Bundle]]
> Project Bundle: [[projects/{project-slug}/Project Note]] # optional

## Core Thesis

## Key Takeaways

## Executive Summary

## Practical Implications For My Workflow

## High-Signal Concepts To Revisit

## External Validation

## Open Questions

## Source Notes
```

## Daily Note Template

```md
# YYYY-MM-DD

## Research
- Added [[{Note Title}]]
- Main insight: {one-sentence summary}
```

If the daily note already exists, append under `## Research`.

## Format Rules

- use wiki-links for all internal references
- use YAML frontmatter for metadata
- keep the main research note analytical and synthesis-first
- keep raw artifacts out of the root `research/` folder
- add `External Validation` when web research or official docs were used
- if a rebuild exists, link it from the research note instead of burying it in repo paths only

## Automation Helpers

Use `scripts/vault_sync.py` for:

- migrating old flat assets into bundles
- copying run artifacts into the correct asset folder
- mirroring rebuild code into `projects/`
- updating daily notes with the new research note
