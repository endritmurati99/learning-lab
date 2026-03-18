# Workflow Plan

## Ziel

Aus `learning-lab` soll ein echter, wiederholbarer Workflow werden:

1. Eine Quelle rein
2. Ein klarer Status pro Schritt
3. Konsistente Artefakte in `sources/`, `workspace/`, optional `projects/`
4. Sauberer Abschluss Richtung Vault

Der Fokus ist nicht "mehr Doku", sondern **mehr Operabilitaet**.

---

## Ist-Zustand

### Was schon funktioniert

- Es gibt echte Quelldaten in `sources/`
- Es gibt mehrere ausgefuellte Lernpakete in `workspace/`
- Die Skill-Idee ist gut getrennt: lernen, Luecken fuellen, rebuilden, exportieren
- `gsd2-vs-claude-code` zeigt, dass der Flow grundsaetzlich durchfuehrbar ist

### Was den Workflow heute bricht

1. Der Pipeline-Status ist nirgends explizit gespeichert.
   Es gibt keinen Run-Status wie `ingested`, `nlm_done`, `workspace_done`, `gaps_done`, `rebuild_done`, `vault_done`.

2. Die Artefakte sind nicht konsistent.
   Zwei vorhandene Workspaces haben keinen `07_logik_check.md`, obwohl dieser laut Spezifikation Pflicht ist.

3. `04_projekt_rebuild.md` ist semantisch unscharf.
   Mal ist es "nicht anwendbar", mal ist es nur ein Blueprint, aber es gibt kein echtes Projekt in `projects/`.

4. `rebuild-project` produziert laut Skill lauffaehigen Code mit Tests, aber `projects/` ist faktisch leer.

5. `learn-source` verspricht Multi-Source ueber `notebook_id.txt`, aber nicht jeder vorhandene Source-Ordner enthaelt diese Datei.

6. Es gibt keinen Preflight.
   Tool-Warnungen und Umgebungsprobleme landen aktuell direkt in Artefakten statt sauber abgefangen zu werden.

7. Es gibt kein einheitliches Abschlusskriterium pro Skill.
   Dadurch fuehlt sich der Ablauf wie "Dokumente erzeugen" an, nicht wie ein belastbarer Prozess.

---

## Ziel-Workflow

Jeder Run soll kuenftig diesem Muster folgen:

1. `lab run <source>`
2. Preflight pruefen
3. Slug erzeugen
4. `sources/{slug}/run.json` anlegen
5. Ingest + NotebookLM
6. Vollstaendiges Workspace-Paket erzeugen
7. Optional: Luecken fuellen
8. Optional: Rebuild mit echtem Code in `projects/{slug}/`
9. Optional: Vault-Draft vorbereiten
10. Status aktualisieren und naechsten sinnvollen Schritt ausgeben

---

## Kanonische Statusdatei

Wir fuehren pro Slug eine kleine Zustandsdatei ein:

`sources/{slug}/run.json`

Vorschlag:

```json
{
  "schema_version": 1,
  "updated_at": "2026-03-18T16:00:00Z",
  "source": {
    "type": "youtube",
    "input": "https://...",
    "title": "Example",
    "slug": "example"
  },
  "ingest": {
    "status": "not_started",
    "artifacts": [],
    "warnings": [],
    "log_files": []
  },
  "notebooklm": {
    "status": "not_started",
    "notebook_id": null,
    "deliverables": [],
    "artifacts": []
  },
  "workspace": {
    "status": "not_started",
    "is_tutorial": false,
    "files_complete": false,
    "required_files": [
      "00_zusammenfassung.md",
      "01_kernkonzepte.md",
      "02_schritt_fuer_schritt.md",
      "03_uebungen.md",
      "04_projekt_rebuild.md",
      "05_offene_fragen.md",
      "06_notebooklm_artefakte.md",
      "07_logik_check.md"
    ],
    "optional_files": [],
    "generated_files": []
  },
  "fill_gaps": {
    "status": "not_started",
    "answered_questions": []
  },
  "rebuild": {
    "status": "not_started",
    "reason": null,
    "project_path": null
  },
  "vault": {
    "status": "not_started",
    "note_path": null
  },
  "next_recommended_step": "ingest"
}
```

Das ist die fehlende Bruecke zwischen "Skill-Beschreibung" und "Workflow".

State-Mutationen sollten nicht per ad-hoc Textbearbeitung erfolgen.
Fuer `run.json` nutzen wir einen kleinen Helper:

`python scripts/run_state.py ...`

---

## Ausfuehrungsplan

### Phase 1 - Workflow sichtbar machen

Ziel:
Eine Quelle bekommt einen eindeutigen Status und klare Done-Kriterien.

Tasks:

- `docs/workflow-spec.md` anlegen oder `CLAUDE.md` ergaenzen
- Kanonische Statusfelder fuer `run.json` festlegen
- Definieren, wann `learn-source` wirklich fertig ist
- Definieren, wann `fill-gaps`, `rebuild-project`, `save-to-vault` fertig sind
- Festlegen, welche Dateien Pflicht und welche optional sind

Definition of Done:

- Fuer jeden Skill gibt es Input, Output, Statuswechsel und Abschlusskriterium
- Es ist eindeutig, wann ein Run "haengt" und wann er "fertig" ist

### Phase 2 - `learn-source` hart machen

Ziel:
Der erste Schritt muss stabil und reproduzierbar sein.

Tasks:

- Gestuften Preflight einfuehren:
  - core (`python`, optional `rtk`)
  - source-typ (`yt-dlp`, `defuddle`, `pandoc`)
  - stage-typ (`notebooklm`, `buzz`, `ffmpeg`)
- Warnings aus Datenartefakten fernhalten
- `metadata.tsv` nur noch fuer Daten, Logs in eigene `.log`-Dateien
- `notebook_id.txt` immer schreiben
- `workspace/{slug}/` immer vollstaendig erzeugen
- `07_logik_check.md` immer erzeugen
- `04_projekt_rebuild.md` nur noch mit einem klaren Zustand:
  - `anwendbar`
  - `nicht anwendbar`
  - `bereit fuer rebuild`

Definition of Done:

- Ein neuer Source-Run endet mit sauberem `sources/{slug}/run.json`
- Keine Warnungen mehr in `metadata.tsv`
- Jeder Workspace ist konsistent

### Phase 3 - `lab-master` zu echtem Orchestrator machen

Ziel:
Der User startet nicht mehr "irgendwie", sondern bekommt einen gefuehrten Ablauf.

Tasks:

- `lab-master` auf einen echten Ablauf reduzieren:
  - nur lernen
  - lernen + gaps
  - lernen + gaps + vault
  - full pipeline
- Nach `learn-source` automatisch entscheiden:
  - tutorial => rebuild anbieten
  - non-tutorial => rebuild skippen und begruenden
- `next_recommended_step` immer setzen
- Ein standardisiertes Abschlussformat ausgeben

Definition of Done:

- `lab run <source>` fuehlt sich wie ein Produkt-Flow an
- Nach jedem Run ist der naechste Schritt eindeutig

### Phase 4 - `rebuild-project` echt machen

Ziel:
Rebuild ist nicht mehr nur Text, sondern wirklich ein testbares Projekt.

Tasks:

- Einen technischen Beispiel-Slug auswaehlen
- `projects/{slug}/` mit minimalem MVP erzeugen
- README + Tests verpflichtend machen
- `04_projekt_rebuild.md` auf reales Projekt verlinken
- "Nicht anwendbar" sauber als Skip-Status modellieren

Definition of Done:

- Mindestens ein echter Rebuild existiert
- `projects/{slug}/` ist lauffaehig und testbar

### Phase 5 - `fill-gaps` und Vault sauber anschliessen

Ziel:
Nach dem Lernen entsteht belastbares Wissen statt offener Enden.

Tasks:

- `fill-gaps` auf maximal 3-5 Fragen pro Run begrenzen
- `## Geloest` als Standardstruktur durchziehen
- Quellen + Konfidenz verpflichtend machen
- `save-to-vault` von nicht vorhandenen Skills entkoppeln
- Draft-vor-dem-Schreiben als Standard beibehalten

Definition of Done:

- Ein Nutzer kann ein Thema lernen, gezielt nachrecherchieren und sauber exportieren

---

## Reihenfolge fuer die Umsetzung

Nicht alles gleichzeitig. Die beste Reihenfolge ist:

1. Workflow-Spec + `run.json`
2. Preflight + Artefakt-Konsistenz in `learn-source`
3. `lab-master` als klarer Einstieg
4. Ein echter `rebuild-project`-Pilot
5. `fill-gaps` und Vault-Flow haerten

---

## Pilot fuer den ersten echten Durchlauf

Als Pilot nehmen wir `gsd2-vs-claude-code`, weil dort am meisten Material schon vorhanden ist:

- Notebook-ID existiert
- Mehrere NLM-Artefakte existieren
- Workspace ist am vollstaendigsten
- Der Fall ist gut zum Definieren von Skip-/Optional-Logik

Konkrete Pilot-Aufgaben:

1. `sources/gsd2-vs-claude-code/run.json` entwerfen
2. Pflicht-/Optional-Status fuer alle 8 Workspace-Dateien festlegen
3. `04_projekt_rebuild.md` als "Blueprint, aber kein echter Rebuild" markieren
4. Abschlussformat fuer `lab-master` an diesem Slug testen

---

## Was wir nicht zuerst tun sollten

- Nicht sofort die ganze Pipeline in Python automatisieren
- Nicht zuerst Vault-Export perfektionieren
- Nicht zuerst neue Skills bauen
- Nicht zuerst weitere Quellen analysieren

Erst muss der Kernfluss stabil werden.
Ein kleiner Python-State-Helper ist dafuer okay, solange nicht die komplette Pipeline darin verschwindet.

---

## Nächster konkreter Schritt

Der sinnvollste direkte Next Step ist:

**Phase 1 und Phase 2 gemeinsam starten**

Das heisst ganz konkret:

1. Eine kleine Workflow-Spec schreiben
2. `run.json`-Schema festlegen
3. Einen kleinen State-Helper bauen
4. `learn-source` so anpassen, dass es immer:
   - Preflight macht
   - `notebook_id.txt` speichert
   - `07_logik_check.md` schreibt
   - klare Skip-/Done-Status setzt

Wenn das sitzt, fuehlt sich das Projekt zum ersten Mal wie ein echter Workflow an.
