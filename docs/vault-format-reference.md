# The Vault – Format Reference

Quick reference for the `save-to-vault` skill. Extracted from The Vault's CLAUDE.md and existing research notes.

## Vault Path

`c:/Users/endri/Desktop/Claude-Projects/The Vault/`

## Folder Structure

```
The Vault/
├── daily-notes/        # One file per day: YYYY-MM-DD.md
├── projects/           # Project-scoped notes
├── research/           # Research notes (disk path is "research/")
│   └── assets/         # Transcripts, NLM deliverables, source files
└── .obsidian/          # Do not edit
```

**Important:** The disk folder is `research/` but wiki-links inside notes use `[[reserch/assets/...]]` (intentional misspelling preserved for consistency).

## Research Note Template

```md
# {Title}

> Research generated: {YYYY-MM-DD}
> Source: [{Source Label}]({URL or path})
> {Additional metadata as needed}
> Transcript: [[reserch/assets/{slug}-transcript.txt]]

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

- **No YAML frontmatter** — use inline `>` header blocks
- **Wiki-link syntax** `[[...]]` for all internal references
- **Tone:** analytical, first-person, practical-implications-focused
- **Language:** English
- **Asset paths in wiki-links:** use `[[reserch/assets/...]]`
- **Asset paths on disk:** write to `research/assets/`

## Reference Note

See `The Vault/research/Claude-Code-Paperclip-AI-Agent-Companies.md` for a complete example of the target format.
