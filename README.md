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
        │  3. Structure output into 8-file learning package
        │  4. Run adversarial logic check
        ▼
  workspace/{slug}/          ← German, working drafts
        │
        ├── [fill-gaps]        →  Research answers for open questions
        ├── [rebuild-project]  →  projects/{slug}/    (optional, tutorials only)
        │
        └── [save-to-vault]    →  The Vault/research/{Note}.md  (English, final)
```

---

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `lab-master` | "lab run", "full pipeline" | Master skill that chains all skills together automatically |
| `learn-source` | URL or file path | Ingest → NLM analysis → 8-file learning package |
| `fill-gaps` | "fill gaps", "fülle Lücken" | Web search for open questions → integrate answers |
| `rebuild-project` | "rebuild", "baue nach" | Build a minimal MVP from a tutorial source |
| `save-to-vault` | "save to vault", "speichere im Vault" | Export to Obsidian vault in the correct format |

---

## Learning Package (8 files, German)

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
| `07_logik_check.md` | Bias analysis, missing counter-arguments |

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

# Token-efficiency tools:
cargo install --git https://github.com/rtk-ai/rtk  # or download rtk binary
winget install Buzz  # offline whisper transcription
```

---

## Repository Layout

```
learning-lab/
├── .claude/
│   ├── settings.json          # vault_path + tool permissions
│   └── skills/
│       ├── learn-source/
│       ├── fill-gaps/
│       ├── rebuild-project/
│       └── save-to-vault/
├── docs/
│   └── vault-format-reference.md
├── sources/        # gitignored — raw transcripts and NLM output
├── workspace/      # gitignored — 8-file learning packages
├── projects/       # gitignored — MVP project rebuilds
├── CLAUDE.md
└── README.md
```

---

## Vault Integration

Polished notes are exported to a separate Obsidian vault. Each export produces:

- `research/{Note-Title}.md` — English research note with YAML Properties and wiki-links
- `research/assets/{slug}-transcript.txt` — raw source transcript
- `research/assets/{slug}-study-guide.md` — NLM study guide
- `daily-notes/{YYYY-MM-DD}.md` — daily note entry (appended)

The vault path is configured in `.claude/settings.json` → `vault_path`.

---

## Language Convention

- **Workspace files** — German (working drafts)
- **Vault research notes** — English (final, analytical)
- **Config and docs** — English
