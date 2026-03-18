---
name: fill-gaps
description: Read open questions from `workspace/{slug}/05_offene_fragen.md`, research selected questions, integrate sourced answers back into the workspace, and update `run.json` so the workflow can resume cleanly.
---

# Fill Gaps

`fill-gaps` closes research gaps in an existing learning package.
This step is intentionally interactive because question selection and file edits require user agreement.

## Prerequisites

- `sources/{slug}/run.json` exists
- `workspace/{slug}/05_offene_fragen.md` exists
- the workspace package is complete enough to research from

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `slug` | required | The slug of the learning package |
| `max_questions` | `5` | Maximum number of questions to research in one run |

## Execution Steps

### Step 1 - Validate state and inspect the current package

Before doing any research:

```bash
python scripts/run_state.py validate --slug "{slug}" --check-files
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py summary --slug "{slug}"
```

### Step 2 - Read open questions

Read `workspace/{slug}/05_offene_fragen.md`.
Extract each question as a discrete research target.

If there are no meaningful open questions:

```bash
python scripts/run_state.py set --slug "{slug}" --path fill_gaps.status --value skipped
python scripts/run_state.py refresh-next --slug "{slug}"
```

Then report that there is nothing to research.

### Step 3 - Enter user-selection boundary

Rank questions by researchability:

1. factual
2. conceptual
3. speculative

**Check auto mode:** read `auto_mode` from `sources/{slug}/run.json`.

If `auto_mode` is `true`:

- do NOT set `fill_gaps.status = awaiting_user_input`
- auto-select all questions ranked factual or conceptual, up to `max_questions`
- skip speculative questions
- set `fill_gaps.status = in_progress` and proceed directly to Step 5

If `auto_mode` is not set or `false`:

```bash
python scripts/run_state.py set --slug "{slug}" --path fill_gaps.status --value awaiting_user_input
python scripts/run_state.py set --slug "{slug}" --path next_recommended_step --value fill-gaps
```

Present the ranked list and confirm which questions to research.
Respect `max_questions`.

### Step 4 - Enter edit-confirmation boundary

**Check auto mode:** read `auto_mode` from `sources/{slug}/run.json`.

If `auto_mode` is `true`:

- do NOT set `fill_gaps.status = awaiting_confirmation`
- apply all intended workspace updates directly
- proceed immediately to Step 5

If `auto_mode` is not set or `false`:

Before modifying workspace files:

```bash
python scripts/run_state.py set --slug "{slug}" --path fill_gaps.status --value awaiting_confirmation
```

Show the intended updates and ask for confirmation.

### Step 5 - Research and integrate

After confirmation:

```bash
python scripts/run_state.py set --slug "{slug}" --path fill_gaps.status --value in_progress
```

For each selected question:

1. search
2. read the top credible results
3. extract an answer with source attribution
4. assess confidence
5. integrate the answer into:
   - `01_kernkonzepte.md`
   - `05_offene_fragen.md`

Use this marker for sourced findings:

```markdown
> [Extern recherchiert] {finding} - Quelle: [{source title}]({url})
```

Move answered questions to `## Geloest`.
Keep unresolved questions clearly marked as unresolved.

### Step 6 - Persist research result in state

When useful, append answered question objects to `fill_gaps.answered_questions` with `--json`.

Example:

```bash
python scripts/run_state.py append --slug "{slug}" --path fill_gaps.answered_questions --json --value "{\"question\":\"...\",\"confidence\":\"Hoch\"}"
```

After the run:

```bash
python scripts/run_state.py set --slug "{slug}" --path fill_gaps.status --value done
python scripts/run_state.py refresh-next --slug "{slug}"
python scripts/run_state.py validate --slug "{slug}" --check-files
```

### Step 7 - Report completion

```text
FILL-GAPS COMPLETE
Slug: {slug}
Questions researched: {n}
Next recommended step: {next_recommended_step}
```

## Quality Rules

- source attribution is mandatory
- confidence is mandatory
- no invented answers
- preserve existing content
- use `run.json` to mark interactive boundaries and completion
