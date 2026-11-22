---
name: pico-builder
description: Builds PICO/PECO, objectives and eligibility criteria in PRISMA-P format with ICS/IUGA terms and COMET outcomes. Use for "PICO", "pregunta", "criterios".
---

# pico-builder (C2)

Turns the topic Laura chose into a frozen, source-backed PICO/PECO. Laura writes and approves; you structure and criticise (**advisory**).
Output to Laura **Spanish**; this file and code English. Script: `python scripts/pico_check.py` (offline; FULL and LITE-a).

## Inputs
`state.md` + `config/project.yaml` · chosen topic (journal `decision`, kind `topic_choice`) · Laura's draft · `references/` (ICS/IUGA terms, COMET, PRISMA-P items).

## Steps
1. Read `state.md` and `config/project.yaml`. If no topic decision in the journal → send Laura to `topic-scout` first.
2. Dialogue, one block at a time: P · I (or E for exposure questions → PECO) · C · O · study design · language · period · setting. Offer options; **Laura chooses**.
3. Show a short plan and ask «¿Lo hago? (sí/no)», then `python scripts/pico_check.py new --version N --topic T1 [--framework PECO]` (never overwrites; journals the change).
4. Every term → `references/ics_iuga_terms.md` (term · definition · source · date checked). The reference files are **«pendiente de verificar»** skeletons: Laura opens the source,
   you copy its wording + link + date. No definition from memory; unverifiable → leave «pendiente» (the check will block).
5. Outcomes → `references/comet_pelvic.md` + live COMET search; record name | URL | date | result (≥ 1 checked; «no hay COS» with date also counts).
6. Objectives + inclusion/exclusion criteria → PRISMA-P format (`references/prisma_p_items_6_7.md`, numbering «pendiente de verificar»). Text stays `[draft-ai]`.
7. Critique with the rubric (clarity of the question; fit of design to question) — mark as `advisory: true`; point out mixed populations, vague outcomes, missing comparator. Laura decides.
8. `python scripts/pico_check.py check --file 02_pico/pico_vN.md --write-report` (fix and repeat). Edits: save old copy to `versions/` (or make `new --from N`), then `integrity.py record-change`.
9. «¿Aprobamos esta versión? (sí/no)». Only on Laura's explicit yes:
   `python scripts/pico_check.py freeze --version N --approval-text "<her words>"` → `decision` (actor laura), `state.pico_version = N`. A frozen file is never edited: make `new --from N`.
10. `ai_use` entry for each AI contribution, then orchestrator `journal.py add` + `state_tool.py set stage=C2 …`.

## Gate
G-C2 / Q2-1 / Q2-2: 100 % fields filled or «no definido» · every term with source + date (0 «pendiente») · ≥ 1 COMET checked · eval E3 ≥ 4/5 (`eval/E3_pico_cases.json`) · version frozen by Laura.

## Modo LITE
`pico_check.py` works in LITE-a. LITE-b/P: no scripts → use `templates/pico_checklist_LITE.md` (Claude ticks, Laura confirms every row and signs); write the `change`/`decision`
journal lines yourself, show them to Laura first, and note `pico_version` in `state.md`. `pico_check.py checklist --file …` prints the same list from the file.

## Journal
`change` (each draft, via `record-change`) · `decision` kind `pico_freeze` (actor laura, gate pass by a human) · `ai_use`. Findings of the critique carry `advisory: true`.

## Never
Choose P/I/C/O or criteria for Laura · put a definition, DOI, COMET entry or guideline number from memory · edit a frozen version · describe yourself as a second reviewer ·
close G-C2 on your own judgment · leave a field blank instead of «no definido».
