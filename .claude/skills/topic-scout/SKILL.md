---
name: topic-scout
description: Compares 3–5 candidate review topics with live PubMed/registry counts and existing reviews. Use for "quiero elegir tema", "¿es viable?", "comparar temas".
---

# topic-scout (C1)

Compares candidate topics with **numbers from PubMed / ClinicalTrials.gov, never from memory**. Laura decides; you show data.
All output to Laura is **Spanish**; this file and code are English. Scripts: `python scripts/<name>.py` (they find `TFM_Laura/`
by themselves, or pass `--root`). Exit codes: 0 ok · 1 blocker · 2 usage/mode · 3 needs Laura's confirmation · 4 network.

## Inputs
`state.md` + `config/project.yaml` (mode, email, `feasibility`) · `config/topics.yaml` (3–5 topics) · Laura's interests.
First hypothesis (not hard-wired): **T1 = diástasis de los rectos abdominales (DRA) y hernias abdominales en mujeres**;
neighbouring formulations to offer (Laura chooses): ejercicio terapéutico en DRA posparto · DRA y disfunción del suelo pélvico (PECO) ·
fisioterapia peri-reparación de hernia/DRA · entrenamiento de transverso/PFMT en DRA. Draft file: `templates/topics_T1_borrador.yaml`.

## Steps
1. Read `state.md` and `config/project.yaml`. Note `mode`.
2. With Laura, settle 3–5 topics. Show a short plan and ask «¿Lo hago? (sí/no)» before writing `config/topics.yaml`
   (one flow-map per topic: `- {id: T1, title_es: "...", query: "...", ctgov_cond: "...", epmc_query: "..."}`). Claude may suggest wordings; Laura decides.
3. **MeSH is never typed from memory.** Every `"term"[mh]` is checked by the script with `esearch db=mesh` (exact descriptor, F-05).
   In drafts mark such terms «pendiente de verificar». `python scripts/topic_counts.py check-query --topic T1`.
4. `python scripts/topic_counts.py run --topic T1` — writes `query_check` (QueryTranslation, ErrorList, WarningList, MeSH) and, only if there is
   **0 Error**, the counts (total, RCT 10 y per year, clinical trials, SR 5 y) to `01_tema/counts/` + journal `count` entries.
   Any Error = blocker: explain it to Laura in Spanish, fix the string with her, re-run. Show her every Warning.
   Exit 3 → tell Laura «voy a hacer más de 50 consultas; ¿continúo? (sí/no)» and re-run with `--confirmed` only after her yes.
5. `python scripts/registry_counts.py --topic T1` (ClinicalTrials.gov) and `python scripts/existing_reviews.py --topic T1` (SR list, 5 y; Europe PMC is supplementary).
6. Manual registries (PROSPERO, Epistemonikos, WHO ICTRP): Laura searches, pastes link + date + number →
   `python scripts/record_manual.py count --topic T1 --metric prospero --db prospero --string "..." --count N --url URL`.
7. **Same-PICO criterion is Laura's decision (F-03):** show the SR table next to the topic's PICO, ask «¿alguna tiene el mismo PICO?», then
   `python scripts/record_manual.py decision --topic T1 --kind same_pico_sr --outcome no_same_pico|same_pico --text "<her words>"`.
8. Hand over to `panel-builder` (`build_panel.py --panel viabilidad`). Reproducibility (W-3): `python scripts/topic_counts.py repeat --topic T1`
   (within 1 h: ±0 or equal to the cached answer; a day later differences are legitimate and logged).
9. Recommendation = criteria met / not met **with the number beside each**: «Sugerencia; decide Laura». No number → «sin datos», never a recommendation.
   Default feasibility (parameter, «pendiente de validar con tutor»): ≥ 10 RCT/CT **and** no SR with the same PICO in 3 years (second one = Laura).
10. Topic chosen by Laura (and supervisor) → `record_manual.py decision --kind topic_choice`; then `ai_use` entry for every AI contribution;
    finally `journal.py add` + `state_tool.py set stage=C1 step=… next_action_es=…` via the orchestrator.

Message templates (ES): «Voy a comparar {n} temas con datos de PubMed. Son unas {k} consultas gratuitas. ¿Lo hago? (sí/no)» ·
«La ecuación del tema {id} tiene un error: {error}. No guardo ningún conteo hasta corregirlo.» · «Conteo del tema {id}: {n} (consulta y fecha anotadas en el diario {J-xxxx}).»

## Gate
G-C1 / Q1-1 / Q1-2: 3–5 topics; per topic 4 numbers + string + date in the journal; `query_check` 0 Error (Warnings shown); repeat within 1 h ±0 or = cache;
≤ 200 requests per panel, 0 × 429 (≤ 3 req/s, enforced by `http_client`); 0 recommendations without a number; «same PICO» = `actor: laura`.

## Modo LITE
- **LITE-a / LITE-b (no network scripts):** counts through the PubMed connector (say «conteo del conector, no reproducible por script») **or** Laura copies
  «Results: N» from pubmed.gov with the filter applied (give her the ready link: `topic_lib.pubmed_link` / pubmed.ncbi.nlm.nih.gov/?term=…). Register with
  `record_manual.py count` (number + date + URL; in LITE-b write the journal line yourself and show it first). Laura also copies the
  **«Search details»** block (Advanced → History and Search Details) → `--search-details-file`; you only say whether the MeSH terms match (advisory).
  Repeat check = Laura repeats the search the same day.
- **LITE-P:** same, results kept in `state.md`/`journal.jsonl` Project files.
Never claim a script ran when it did not.

## Journal
`query_check` (script, gate pass only with script report) · `count` (script or Laura, with `topic_id`, `metric`) · `search` (SR lists) ·
`verification` (repeat) · `decision` (Laura / supervisor only) · `ai_use` for each AI contribution (tool, stage, what_es, how_verified, human_decision).
Claude's judgments carry `advisory: true`.

## Never
Invent or "remember" a number, reference or MeSH term · choose the topic or decide «same PICO» for Laura · save counts when `query_check` has an Error ·
write into `raw/` (only `http_client` does) · hide a Warning · send more than 50 requests without Laura's yes.
