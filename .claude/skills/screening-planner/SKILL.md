---
name: screening-planner
description: Imports RIS/nbib/CSV exports, flags duplicates without deleting, writes the screening plan (PRISMA-P 11b) and runs a pilot. Use for "duplicados", "cribado", "piloto".
---

# screening-planner (C4)

All output to Laura is **Spanish**; this file and code are English. Scripts: `python scripts/<name>.py` (project found via cwd, `/mnt/*`, `--root`, `$TFM_ROOT`).
Exit codes: 0 ok · 1 gate failed · 2 no project · 4 mode does not allow it · 5 refused.

## Inputs
`state.md` · `config/project.yaml` (`supervisor_check_pct` 20, `pilot_n` 50) · exports Laura registered in `raw/exports/` (RIS, nbib, CSV; file name `<db>_<YYYY-MM-DD>_<vN>.<ext>`) · frozen PICO/criteria (`02_pico/`).

## Steps
1. **Start:** read `state.md` + `project.yaml`; orchestrator runs `integrity.py check`.
2. **Import.** Laura exports from each database and uploads to `raw/exports/`; you run `integrity.py register-export raw/exports/<file> --what-es "..." --stage C4 --db <db>`, then `scripts/import_refs.py`. Only registered, real database exports are read; skipped files are listed with the reason. Output: `04_seleccion/dedup/records_v<N>.csv` and per-database counts in the journal. PubMed exports as nbib; CENTRAL / PEDro / LILACS formats are «pendiente de verificar» (R-10): when a database has no usable export, Laura pastes the results into `templates/plantilla_pedro_manual.csv`, which you register as an export.
3. **Duplicates.** `scripts/dedup.py run` marks (never deletes) duplicates: same DOI, same PMID, same normalised title, fuzzy title (+ year +-1 + same first-author surname). A pair with different DOIs or PMIDs is **not merged**: it appears in `possible_duplicates` for Laura. The kept record is the richest one; the rest get `duplicate_of`. Numbers (identified / duplicates / unique, per database) go to the journal. Show Laura at most 20 records at a time.
4. **Screening plan (PRISMA-P 11b).** Draft `04_seleccion/plan_seleccion_es.md` from `templates/plan_seleccion_es.md` (mark it `[draft-ai]`): title/abstract, full text, closed list of exclusion reasons (`references/exclusion_reasons_es.md`), **single reviewer (Laura) + spot check by the supervisor**. `pilot_sample.py supervisor-sample` draws the supervisor's sample (default 20%, **pending agreement with the supervisor**). You are NOT a second reviewer: say so in the plan.
5. **Pilot (optional, W-1).** The protocol needs a screening PLAN, not its execution. A pilot only happens if the supervisor/Laura decide it: `pilot_sample.py record-go --by supervisor --says "..."`. Then `pilot_sample.py sample` (>= 50 unique records, deterministic) with EMPTY decision columns and the watermark «PRELIMINAR — piloto, no forma parte del protocolo». Laura fills `decision` (incluir / excluir / dudoso), `reason` (closed list, required when excluding), `decided_by: laura`. `pilot_sample.py check --file ...` verifies 100% decided by Laura.
6. **Numbers for the flow.** `scripts/flow_counts.py build` -> `04_seleccion/flow_counts.json` (`scope: preliminar`) for panel-builder.
7. **End:** `journal.py add` `ai_use` entries (plan draft); `state_tool.py set stage=C4 ...`.

## Scripts
`screen_lib.py` (shared) · `import_refs.py` · `dedup.py` (`run`, `selftest --fixture`) · `pilot_sample.py` (`record-go|sample|show|check|supervisor-sample`) · `flow_counts.py`.

## Gate (G-C4)
Dedup recall >= 95% on a planted set of >= 30 duplicates and <= 1 false merge (`dedup.py selftest`, eval) · numbers before/after in the journal · `duplicate_of` set, 0 deletions · pilot (if done) >= 50 records, 100% `decided_by: laura`, reasons from the closed list, watermark present · plan 11b = single reviewer + supervisor spot check (`supervisor_check_pct`) · warn before sending > 500 records to an LLM analysis · max 20 records in context at a time.

## Modo LITE
- **LITE-a:** all these scripts are offline and work.
- **LITE-b / LITE-P:** no scripts. Laura deduplicates in Rayyan Free or TERA Deduplicator, copies the counts (identified, duplicates, unique, per database) and you write the journal line and show it to her before saving (`templates/dedup_numbers_LITE_es.md`). The pilot, if any, is done in Rayyan with the supervisor (two reviewers there are theirs, not yours).

## Journal
`change` (`import_refs`, `pilot_sample`, `supervisor_sample`, `flow_counts`), `verification` (`G-C4-dedup`, `G-C4-pilot`), `decision` (pilot go / no-go by Laura or the supervisor), `ai_use`.

## Never
- Delete a record or merge records with different DOI/PMID · propose or fill include/exclude decisions · act as or describe yourself as the second reviewer · present pilot numbers as final PRISMA numbers (always PRELIMINAR) · write into `raw/` · read exports that are not registered.
