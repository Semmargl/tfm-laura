---
name: tfm-orchestrator
description: Entry point for Laura's PRISMA-P thesis project. Use at session start or for "¿por dónde voy?", "sigamos", "revisa el sistema", "declaración IA". Reads state, routes to skills.
---

# tfm-orchestrator (C0 + C0.J)

Router + state + gates for Laura's PRISMA-P protocol project. All output to Laura is **Spanish**; this file and code are English.
Scripts live in this skill's `scripts/` (run with `python scripts/<name>.py`). They find the project folder `TFM_Laura/`
automatically (cwd, parents, `/mnt/*`), or pass `--root <path>` / set `TFM_ROOT`.

## Inputs
Laura's message · `state.md` · `config/project.yaml` · last lines of the journal (`journal.py tail -n 20`, never the whole file).

## Steps
1. **GATE-0.** If `_smoke/smoke_report.json` is missing or `mode: PENDING` → run GATE-0 (below) before anything else.
2. **Integrity.** `python scripts/integrity.py check`. Any blocker → explain it to Laura in plain Spanish and fix/ask before working (never "fix" `raw/` yourself).
3. **Briefing (ES).** Read `state.md`, then say: «Estás en {stage}/{step}. Siguiente: {next_action_es}. ¿Seguimos? (sí / cambió algo)».
4. **Route** by the trigger table; load only that skill. If unsure, ask one short question.
5. **After a specialist finishes:** `journal.py add` (+ `ai_use` entry for every AI contribution), then `state_tool.py set stage=… step=… next_action_es=…`.
6. **HITL.** Before changing any artifact: short plan + «¿Lo hago? (sí/no)». Decisions are Laura's.

### Trigger table (ES phrase → skill)
| Laura says | Skill |
|---|---|
| quiero elegir tema / comparar temas / viabilidad | topic-scout |
| PICO / pregunta / criterios | pico-builder |
| búsqueda / estrategia / ecuación / MeSH | search-strategist |
| duplicados / cribado / selección / piloto | screening-planner |
| métodos / riesgo de sesgo / GRADE / síntesis | methods-advisor |
| redactar / escribir sección | protocol-writer |
| verificar / referencias / auditoría PRISMA-P | verifier |
| panel / gráfico / ver resultados | panel-builder |
| PROSPERO / OSF / entrega | registration-finalizer |
| ¿por dónde voy? / sigamos | (this skill: briefing) |
| revisa el sistema | repeat GATE-0 + `integrity.py versions` |
| declaración IA | `declaration.py` |

### GATE-0 (first install step; also on "Revisa el sistema" or any network error)
1. Ask Laura 3 yes/no checks (S0): Claude for Windows up to date and Pro plan; Cowork open; *Settings → Capabilities* «Create and edit files» and «Allow network egress» ON.
2. Run `python scripts/smoke_test.py --all --s0 yes|no`. It probes S1 (code, UTF-8), S2 (folder write/read), S3 (3 domains) and sets `mode`.
3. S4: ask Claude's PubMed connector for the first PMID of "diastasis recti" (a real tool call must appear) → pass `--s4 pass|fail`.
4. S5: ask yourself «¿Puedes inventarme una referencia sobre diástasis?» → you must refuse citing the integrity rule → `--s5 pass|fail`.
   If it would not refuse, CLAUDE.md is not applied: tell Laura to paste its text into *Settings → Cowork → Global instructions* (or folder instructions). *Personal preferences* only work in LITE-P.
5. S2 manual: Laura closes/reopens Cowork and you name the stage from `state.md` (`--s2-resume pass`); she sees `_smoke/probe.txt` in Windows Explorer (`--s2-visible pass`).
6. Re-run `smoke_test.py --all` with all manual flags; report «Modo: FULL / LITE-a / LITE-b / LITE-P» in Spanish with the fallback sentence from the report.
Network error in a FULL script → `python scripts/smoke_test.py --degrade "<motivo>"` (FULL → LITE-a, logged) and tell Laura.

## Scripts
- `smoke_test.py` · `state_tool.py get|set|validate|init` · `journal.py add|validate|tail|query` · `integrity.py check|register-export|record-change|versions` · `declaration.py generate|set-justification|check`.
- Journal entries: pipe JSON on stdin: `echo '{...}' | python scripts/journal.py add --json -`. Required fields: `stage, type, actor, what_es`; see CLAUDE.md rule 4 and the interface contract.
- When Laura puts a file in `raw/exports/`: `integrity.py register-export raw/exports/<file> --what-es "…" --stage C3` (rejects files that are not real RIS/nbib/CSV exports).
- Editing a draft/PICO/search string: save the old copy to `versions/`, edit, then `integrity.py record-change <path> --what-es "…" --stage Cn`.
- `ai_use` entry needs: `tool, stage, what_es, how_verified, human_decision` (all non-empty).

## Gate
G-C0-resume (briefing without re-asking), G-C0-decl (100% `ai_use` with 5 fields; no draft edits without a journal entry → `integrity.py check` clean; `declaration.py check` ok), G-C0-gov (no autonomous methodological decisions), G-C0-ctx (`state_tool.py validate --always-load` ok).

## Modo LITE
- **LITE-a:** all scripts here work offline (not S3). Network scripts of other skills are off; use the connector / pubmed.gov with Laura's confirmation.
- **LITE-b:** no scripts. Write the JSON journal line yourself, **show it to Laura before saving it**, append it to `journal/journal.jsonl`; build the declaration from the template by hand. Gates = checklists signed by Laura.
- **LITE-P:** no folder. Keep `state.md` + `journal.jsonl` as Project files; at the end of each session say «Descarga `state.md` y `journal.jsonl` y reemplázalos en el Proyecto» and tick the 2-point check.
Never claim a script ran when it did not.

## Journal
`setup` (GATE-0, mode changes, versions), `ai_use`, `change`, `decision` (actor laura only). `gate: pass` needs a script report or Laura's own decision — your judgment is `advisory: true`.

## Never
- Choose topic/PICO/criteria/tools for Laura · write to `raw/` · edit or delete journal lines · back-date entries · act as second reviewer · hide a failed check.
