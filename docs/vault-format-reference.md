# The Vault – Format Reference

Quick reference for the `save-to-vault` skill. Extracted from The Vault's CLAUDE.md and existing research notes.

## Vault Path

Configured in `.claude/settings.json` → `vault_path`.
Default: `c:/Users/endri/Desktop/Claude-Projects/The Vault/`

## Folder Structure

```
The Vault/
├── daily-notes/        # One file per day: YYYY-MM-DD.md
├── projects/           # Project-scoped notes
├── research/           # Research notes
│   └── assets/         # Transcripts, NLM deliverables, source files
└── .obsidian/          # Do not edit
```

## Research Note Template

```md
---
research_date: YYYY-MM-DD
source_url: "https://example.com"
source_label: "Source Label"
tags:
  - research
  - topic-tag
transcript: "[[research/assets/{slug}-transcript.txt]]"
---

# {Title}

## Core Thesis

{Central argument in 1-2 paragraphs}

## Key Takeaways

{Bullet points with [[wiki-links]] to concepts}

## Executive Summary

{Longer narrative synthesis}

## Practical Implications For My Workflow

{First-person, actionable insights}

## High-Signal Concepts To Revisit

{Each concept as a [[wiki-link]]}

## Open Questions

{Gaps, disagreements, topics for deeper research}

## Source Notes

{Provenance: source type, capture date, method, NLM deliverables generated}
```

## Daily Note Template

```md
# YYYY-MM-DD

## Research
- Added [[{Note-Title}]]
- Main insight: {one-sentence summary}
```

If the daily note already exists, append under the existing `## Research` section.

## Format Rules

- **YAML Properties (frontmatter)** for metadata — `research_date`, `source_url`, `source_label`, `tags`, `transcript`
- **Wiki-link syntax** `[[...]]` for all internal references
- **Tone:** analytical, first-person, practical-implications-focused
- **Language:** English
- **Asset paths in wiki-links:** use `[[research/assets/...]]`
- **Asset paths on disk:** write to `research/assets/`

## Reference Note

See `The Vault/research/Claude-Code-Paperclip-AI-Agent-Companies.md` for a complete example of the target format.
