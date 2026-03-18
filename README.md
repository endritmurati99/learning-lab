# learning-lab

A skill-based learning pipeline for Claude Code. Feed it any source — YouTube video, web page, PDF, or local file — and it produces a structured learning package. Final knowledge gets exported to an Obsidian vault.

**NotebookLM is the primary analysis engine.** Heavy AI analysis runs on Google at zero token cost. Claude Code orchestrates the pipeline and formats the output.

---

## How It Works

```
Source (YouTube / web / PDF / text)
        │
        ▼
  [learn-source]
        │  1. Detect & ingest (yt-dlp / defuddle / Read)
        │  2. Send to NotebookLM (create → add source → generate)
        │  3. Structure output into 7-file learning package
        ▼
  workspace/{slug}/          ← German, working drafts
        │
        ├── [rebuild-project]  →  projects/{slug}/    (optional, tutorials only)
        │
        └── [save-to-vault]    →  The Vault/research/{Note}.md  (English, final)
```

---

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `learn-source` | URL or file path | Ingest → NLM analysis → 7-file learning package |
| `rebuild-project` | "rebuild", "baue nach" | Build a minimal MVP from a tutorial source |
| `save-to-vault` | "save to vault", "speichere im Vault" | Export to Obsidian vault in the correct format |

---

## Learning Package (7 files, German)

Each source produces a `workspace/{slug}/` folder:

| File | Contents |
|------|----------|
| `00_zusammenfassung.md` | Executive summary + core thesis |
| `01_kernkonzepte.md` | Key concepts with definitions |
| `02_schritt_fuer_schritt.md` | Step-by-step walkthrough |
| `03_uebungen.md` | Flashcards and exercises |
| `04_projekt_rebuild.md` | Rebuild blueprint (tutorial sources only) |
| `05_offene_fragen.md` | Open questions and gaps |
| `06_notebooklm_artefakte.md` | NLM deliverable paths and notebook info |

---

## Source Types

| Type | Tool |
|------|------|
| YouTube URL | `yt-dlp` → transcript → NLM |
| Web page URL | `defuddle` → clean markdown → NLM |
| PDF file | Claude Code Read → NLM |
| Local `.md` / `.txt` | Claude Code Read → NLM |

---

## Prerequisites

```bash
pip install yt-dlp notebooklm
npm install -g defuddle
notebooklm login   # browser OAuth — run once in a separate terminal
```

---

## Repository Layout

```
learning-lab/
├── .claude/
│   ├── settings.json
│   └── skills/
│       ├── learn-source/
│       ├── rebuild-project/
│       └── save-to-vault/
├── docs/
│   └── vault-format-reference.md
├── sources/        # gitignored — raw transcripts and NLM output
├── workspace/      # gitignored — 7-file learning packages
├── projects/       # gitignored — MVP project rebuilds
├── CLAUDE.md
└── README.md
```

---

## Vault Integration

Polished notes are exported to a separate Obsidian vault (`The Vault/`). Each export produces:

- `research/{Note-Title}.md` — English research note with wiki-links
- `research/assets/{slug}-transcript.txt` — raw source transcript
- `research/assets/{slug}-study-guide.md` — NLM study guide
- `daily-notes/{YYYY-MM-DD}.md` — daily note entry (appended)

The vault path is not tracked in this repo — it lives at `c:/Users/endri/Desktop/Claude-Projects/The Vault/`.

---

## Language Convention

- **Workspace files** — German (working drafts)
- **Vault research notes** — English (final, analytical)
- **Config and docs** — English
