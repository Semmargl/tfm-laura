---
name: search-strategist
description: 'Designs and validates database search strings: MeSH/DeCS + free text, seed-set recall test, PRESS 2015 check, citation chasing, PRISMA-S log. Use for "búsqueda", "ecuación", "MeSH".'
---

# search-strategist (C3 - "contrato de verdad" of the search)

All output to Laura is **Spanish**; this file and code are English. Scripts: `python scripts/<name>.py` (they find `TFM_Laura/` via cwd, `/mnt/*`, `--root`, `$TFM_ROOT`).
Exit codes: 0 ok · 1 gate failed / errors · 2 no project · 3 needs Laura's confirmation (>50 requests: ask, rerun with `--confirmed`) · 4 mode does not allow it · 5 refused (precondition).

## Inputs
`state.md` · `config/project.yaml` (mode, `recall`, caps) · `config/databases.yaml` · frozen PICO (`02_pico/`) · `03_busqueda/seed_set.csv` (`pmid,doi,title,origin,held_out,notes`).

## Steps
1. **Start:** read `state.md` + `config/project.yaml`; orchestrator runs `integrity.py check`. Mode FULL needed for network scripts (LITE: see below).
2. **Seed set (F-02).** >= 10 articles from INDEPENDENT sources only: included studies of existing systematic reviews (`origin: existing_sr_included`), articles from the supervisor (`supervisor`), Laura's manual search (`laura_manual`). **Never** take seeds from the output of the string being tested. >= 5 marked `held_out: 1`. Put the `source_journal_id` of each seed in `notes`; verify the seeds with the verifier first. Then `python scripts/seed_seal.py check` and show Laura the summary; ask «¿Sello el seed set? (sí/no)». On yes: `seed_seal.py seal --independence-es "<how they were found>" --laura-ok "aprobado por Laura"`. After the seal, `seed_set.csv` is frozen.
3. **Terms.** Propose concepts from the frozen PICO; MeSH candidates come from MeSH on Demand / the MeSH Browser (never from memory); Spanish DeCS by hand. Everything you propose is `advisory`.
4. **String v1.** Write the draft to a temp file, show it to Laura, ask «¿Lo guardo? (sí/no)», then `scripts/save_string.py --db pubmed --from-file draft.txt --approved-by-laura` (creates `03_busqueda/strings/pubmed_v1.txt`; **refuses v1 without a seed seal**; logs `change` + `ai_use`). Comments in strings start with `//`; numbered lines (`1. ...`, `#1 AND #2`) are expanded.
5. **Query check (F-05).** `scripts/run_search.py run --db pubmed --string-file 03_busqueda/strings/pubmed_v1.txt --limits "..."`: logs QueryTranslation / ErrorList / WarningList, validates every `[mh]` term against `db=mesh`. **Any Error = blocker**: fix the string as a NEW version (`save_string.py`), never edit in place. Repeats within 1 h come from the cache; a fresh repeat with a different count is logged as «diferencia diaria».
6. **Recall (Q3-2).** `scripts/recall_test.py --db pubmed --string-file ...` (10 seed -> 10/10, held-out 5 -> 5/5; with more seeds >= 95% / >= 90%). It refuses if the seal is not strictly older than every `strings/*_v1.txt`. For each miss write the cause and either a new string version or a **decision of Laura + supervisor** in the journal; never mark it as fine yourself.
7. **PRESS 2015 (Q3-3).** `scripts/press_lint.py lint --string-file ...` closes only the syntax domains. `press_lint.py init` creates `03_busqueda/press/press_<db>_v<N>.md`; you fill the four content domains (translation of the question, subject headings, text words, limits/filters) as **advisory**. Laura sets `Estado de Laura: ok|revisar` and signs (`press_lint.py signoff --file ... --laura-says "..."`, only after she said so; ideally with the supervisor or a librarian). `press_lint.py status` shows if PRESS is closed.
8. **Other databases (F-07).** Required: PubMed (script) + **Cochrane CENTRAL + PEDro** (Laura runs them, exports to `raw/exports/`, you register with `integrity.py register-export`, then `prisma_s_log.py record --db cochrane_central ... --laura-says "..."`). Recommended: LILACS (+ paid ones only if Euneiz gives access). Europe PMC / OpenAlex (`run_search.py run --db europepmc|openalex`) are **supplementary and never count** toward the minimum. Translation between databases: TERA Polyglot (syntax) + manual MeSH -> Emtree/DeCS mapping (you suggest, Laura checks). Export formats of CENTRAL/PEDro/LILACS are «pendiente de verificar» (R-10).
9. **Registries.** ClinicalTrials.gov via `run_search.py run --db clinicaltrials_gov`; WHO ICTRP and PROSPERO/Epistemonikos by hand (`prisma_s_log.py record`).
10. **Citation chasing (Q3-4).** `scripts/chase_openalex.py run` (backward + forward for 100% of seeds, <= 500 OpenAlex requests). You may only sort. Laura fills `triage` («relevante» / «no») in `03_busqueda/chasing/triage.csv`; then `chase_openalex.py record-triage --laura-says "..."` and `status`.
11. **PRISMA-S log.** `scripts/prisma_s_log.py build` -> `03_busqueda/prisma_s_log.md` (6 fields per search: database, platform, date, verbatim string, limits, number of results) + coverage check. Laura approves.
12. **End:** `journal.py add` an `ai_use` for every AI contribution (terms, strings, PRESS advisories); then `state_tool.py set stage=C3 step=... next_action_es=...`.

## Scripts
`search_lib.py` (shared) · `seed_seal.py` · `save_string.py` · `run_search.py` (`run`, `record-details`) · `recall_test.py` · `press_lint.py` (`lint|init|status|signoff`) · `chase_openalex.py` (`run|record-triage|status`) · `prisma_s_log.py` (`record|build`).

## Gate (G-C3)
seed >= 10 independent, `seed_seal` before `strings/*_v1` · recall 10/10 + held-out 5/5 (or >= 95% / >= 90%) · 0 Error in `query_check`, 100% `[mh]` valid · PRESS: 0 syntax errors + 4 content domains signed by Laura (0 «revisar») · chasing 100% of seeds, triage by Laura · PubMed + CENTRAL + PEDro + CT.gov + WHO ICTRP + >= 1 review registry · PRISMA-S 6 fields on 100% of searches · repeat within 1 h = 0 or = cache · <= 30,000 tokens/session · never load a whole export into context (use scripts). A string without the recall threshold cannot become `final` without Laura + supervisor decision (journal).

## Modo LITE
- **LITE-a** (no network, scripts work): `run_search.py run --lint-only` (syntax only, gate stays «pending»); Laura runs the string on pubmed.gov, pastes «Search details» -> `run_search.py record-details`; she exports the results to `raw/exports/` -> `recall_test.py --offline --results-file raw/exports/<file>` (deterministic). Chasing: PubMed «Cited by» / TERA SpiderCite exports in `raw/exports/` (triage still hers).
- **LITE-b** (no scripts): `templates/recall_table_LITE_es.md` - you prepare the table «seed -> found / not found + line of the file», **Laura confirms 100% of rows (both outcomes)**; without her confirmation Q3-2 = «no demostrado». PRESS syntax by checklist, content domains advisory + her signature. Search details: `templates/search_details_LITE_es.md`; chasing: `templates/chasing_LITE_es.md`. You write the JSON journal line and show it to Laura before saving.
- **LITE-P:** same tables, kept in the Project; she downloads `state.md` + `journal.jsonl` at the end.
Never claim a script ran when it did not.

## Journal
`seed_seal`, `change` (strings), `ai_use`, `query_check`, `count`, `search` (chasing), `verification` (`G-C3-recall`, `G-C3-press-syntax`, `G-C3-prisma-s`, `G-C3-chasing`), `decision` (Laura: PRESS sign-off, chasing triage, recall exceptions). `gate: pass` only through a tfm-report/v1 script report or Laura's own decision; your judgments carry `advisory: true`.

## Never
- Take seeds from the tested string's results, or create `strings/<db>_v1.txt` before the seal · edit a string in place or the frozen seed set · accept a query with an Error · count Europe PMC/OpenAlex as a required database.
- Mark a seed «found» yourself, sign PRESS for Laura, decide chasing relevance, or write into `raw/` · invent MeSH terms, counts or references from memory.
