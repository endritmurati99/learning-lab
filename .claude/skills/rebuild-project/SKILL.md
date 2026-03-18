---
name: rebuild-project
description: Take a tutorial or project-based source that was already analyzed by learn-source and create a minimal, testable MVP project rebuild. Use when the user says "baue nach", "rebuild", "erstelle das Projekt", or wants to create working code from a tutorial or project source.
---

# Rebuild Project

Takes an already-analyzed source (from `learn-source`) and reconstructs the smallest meaningful end-to-end project. Produces runnable code, not just documentation.

## Prerequisites

- A completed learning package in `workspace/{slug}/` (created by `learn-source`)
- At least `00_zusammenfassung.md` and `02_schritt_fuer_schritt.md` must exist

## Inputs (ask user if missing)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | The slug of the learning package in `workspace/` |
| `target_lang` | auto-derived | Programming language if not obvious from the source |
| `scope` | `mvp` | `mvp` (minimal viable) or `full` (closer to original) |

## Execution Steps

### Step 1 — Verify prerequisites

Check that `workspace/{slug}/` exists with at least `00_zusammenfassung.md` and `02_schritt_fuer_schritt.md`. If not, tell the user to run `learn-source` first.

### Step 2 — Read all available material

Read in order:
1. `workspace/{slug}/00_zusammenfassung.md` — what the source is about
2. `workspace/{slug}/01_kernkonzepte.md` — core concepts and patterns
3. `workspace/{slug}/02_schritt_fuer_schritt.md` — step-by-step breakdown
4. Original source from `sources/{slug}/` — transcript, content, or text
5. NLM analysis from `sources/{slug}/nlm-*` — if available

### Step 3 — Design MVP architecture

Based on the material, determine:

1. **Business goal** — what the project does, in 1 sentence
2. **Success metric** — how to verify it works, in 1 sentence
3. **Technology stack** — language, framework, dependencies
4. **Minimal increment** — the smallest set of features for a working demo
5. **What to skip** — features that are not essential for the MVP

### Step 4 — Create project

Build the project in `projects/{slug}/`:

- Generate all necessary code files
- Create a `README.md` with:
  - What this is and where it came from
  - How to install dependencies
  - How to run it
  - What was simplified vs. the original
  - Link back to `workspace/{slug}/` for the full learning package
- **Every rebuild MUST include a `tests/` directory with at least 3 functional tests** (Pytest for Python, Jest for JS/TS). Tests should cover the core success metric, one happy path, and one edge case.
- Keep it minimal and runnable
- MVP first — no over-engineering

### Step 5 — Update learning package

Write or update `workspace/{slug}/04_projekt_rebuild.md` with:

```markdown
# Projekt-Rebuild: {topic}

## Ziel
{Business goal in 1 sentence}

## Success Metric
{How to verify it works}

## Annahmen
{List of assumptions made during rebuild}

## Architektur
{Technology stack and high-level design as text}

## Dateistruktur
{Tree view of projects/{slug}/}

## Umsetzungsreihenfolge
{Numbered steps taken to build the MVP}

## Testfälle
{How to verify the project works}

## Failure Path
{What could go wrong and how to debug}

## Nächster Sprint
{3 items for extending the MVP}

## Fehlende Information
{Anything that was unclear or had to be guessed — marked as "Zu verifizieren"}
```

### Step 6 — Report completion

```
REBUILD-PROJECT COMPLETE
Project: projects/{slug}/
Files created: {list}
Tech stack: {stack}
MVP scope: {what's included}

To run: {instructions}
To extend: see workspace/{slug}/04_projekt_rebuild.md

Next step:
- /save-to-vault {slug}  (to export learnings to The Vault)
```

## Quality Rules

- **MVP first** — the smallest testable end-to-end system
- **No invented APIs or features** — only use what the source describes
- **Mark assumptions** explicitly as `Annahme`
- **Mark missing information** as `Fehlende Information` or `Zu verifizieren`
- **Erst verstehen, dann bauen** — understand before building

## Common Issues

| Problem | Fix |
|---------|-----|
| Source not technical enough | Tell user this source is not suitable for rebuild |
| Missing dependency info | Mark as assumption, suggest most common default |
| Incomplete tutorial steps | Note gaps, build what's possible, document missing pieces |
