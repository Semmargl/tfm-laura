---
name: verifier
description: Deterministically verifies references (DOI/PMID metadata, retractions, duplicates), numbers and quotes against saved sources, and audits PRISMA-P 26 sub-items. Use for "verificar".
---

# verifier (C7 - the integrity gate)

All output to Laura is **Spanish**; this file and code are English. Scripts: `python scripts/<name>.py` (project via cwd, `/mnt/*`, `--root`, `$TFM_ROOT`).
Exit codes: 0 ok · 1 gate failed · 2 no project · 3 needs confirmation (`--confirmed`) · 4 mode · 5 refused. The verifier only REPORTS (`07_verificacion/reports/*_es.md`: ROJO / AMARILLO / VERDE); it never edits the reference list, and every fix is Laura's decision.

## Inputs
`state.md` · `config/project.yaml` (`citation_style`, `verification.max_report_age_days`) · `07_verificacion/references.csv`: `ref_id,doi,pmid,source_journal_id,provenance_status` plus optional `claimed_title, claimed_first_author, claimed_year, claimed_journal, claimed_issn` (what the DRAFT says; you may fill these from the reference list text, the script compares them with the databases) · drafts `06_protocolo/drafts/*.md` with tags `[ref:ref_id|loc]`.

## Steps
1. **Start:** read `state.md` + `project.yaml`; orchestrator runs `integrity.py check`.
2. **Provenance first (F-01).** `scripts/verify_refs.py run` (or `--offline` in LITE-a). Each reference must name a `source_journal_id`: a journal entry that links a valid file in `raw/api/` (script-written) or `raw/exports/` (Laura's registered export) **containing its DOI/PMID**, or a `reference_add` entry by Laura. Otherwise **NO_PROVENANCE = release blocker**: a real DOI recalled from memory does not pass. To add a reference by hand, Laura says where she took it from: `verify_refs.py add-ref --ref-id R9 --doi ... --origin-es "..." --laura-says "..."`.
3. **Existence, metadata, retractions (FULL).** PubMed `efetch` by PMID (metadata, `PublicationType`: Retracted Publication / Expression of Concern / Retraction of Publication, `CommentsCorrections`: RetractionIn / ExpressionOfConcernIn / ErratumIn) and Crossref by DOI (metadata, `updated-by`, `filter=updates:<doi>`; Retraction Watch data). Retracted or EoC by **either** source blocks. Metadata vs `claimed_*`: title similarity >= 0.90, first-author surname, year (+-0, any official year of the record), ISSN. Duplicates by DOI / PMID / normalised title.
4. **References without DOI or PMID** (PEDro, LILACS, regional literature) are `UNVERIFIABLE`, never `VALID`. Laura chooses one way and `verify_refs.py resolve --ref-id R5 --via 1|2|3 ... --laura-says "..."`: (1) official URL / ISSN / handle, (2) find the PMID or DOI and add it with `add-ref`, (3) replace the reference. Resolved ones show as `UNVERIFIABLE_RESOLVED` (not blocking, never counted as verified).
5. **Numbers and quotes (F-04).** `scripts/check_claims.py run`: each `[ref:id|loc]` claim is matched literally (numbers, quoted passages) against a legitimate source only: `raw/api` written by a script, or a text/PDF Laura uploaded to `raw/exports/` (registered, sha256, actor laura). Text written by you is refused (`NO_SOURCE`). Untagged quotes (>= 4 words) and statistics are blockers; Laura's own parameters carry `[propio]`.
6. **Meaning (advisory).** For each claim, follow the citation-verifier protocol: quote VERBATIM the sentence from the draft and the passage from the source; verdict VALID / ADJUST / INVALID / UNVERIFIABLE, with `advisory: true`. A source that is unreachable is UNVERIFIABLE, not VALID. This never closes a gate.
7. **PRISMA-P audit.** `scripts/prisma_p_audit.py init`, fill `07_verificacion/prisma_p_locators.csv` (locator = `file#Heading` or `file:L12`; `advisory_claude`: your view; `laura_decision`: cumple | parcial | ausente - hers), `prisma_p_audit.py run`. The script checks that locators exist; the substance is Laura's call. The official PRISMA-P wording (26 sub-items) is loaded in `data/prisma_p_2015_checklist.json` (`text_loaded: true`; source, sha256 and access date in `source`). For conditional items (1b «if an update», 4, 15d) Laura writes an explicit sentence in the draft («No es una actualización…») and the locator points to it; otherwise the item stays `ausente`.
8. **Style.** `scripts/ref_style.py format [--style vancouver|apa|harvard]` formats VALID references from saved API metadata (Vancouver is provisional until the guía docente).
9. **End:** `journal.py add` an `ai_use` for each advisory; `state_tool.py set stage=C7 ...`. Before delivery a fresh `verify_refs.py run` (<= 7 days old) is mandatory.

## Scripts
`verify_lib.py` (shared) · `verify_refs.py` (`run [--offline]`, `resolve`, `add-ref`) · `check_claims.py` · `prisma_p_audit.py` (`init`, `run [--checklist F]`) · `ref_style.py` · data `data/prisma_p_2015_checklist.json`.

## Gate (G-C7)
0 `NO_PROVENANCE` · 0 `UNVERIFIABLE` without Laura's decision · 0 NOT_FOUND / MISMATCH / retracted / EoC (Crossref AND PubMed) / duplicates · release forbidden if `unverified_count + no_provenance_count > 0` · 100% of numbers/quotes tagged and matched against a `raw/` source with actor != claude · PRISMA-P 0 ausente and 0 parcial · style 100% · Crossref <= 1,000 requests/run · planted eval 10/10 and false positives <= 1/20 (eval E2, filled live in B6).

## Modo LITE
- **LITE-a:** `verify_refs.py run --offline` does the provenance + duplicate part (report `G-C7-provenance`; `release_allowed` is always false). Existence and retractions: PubMed connector by PMID, Claude prints the metadata next to the citation, Laura opens `https://doi.org/<DOI>` and ticks `07_verificacion/checklist_refs_LITE.md` (column «Fuente» = export / PMID / file). For retractions: publication type in PubMed + Retraction Watch Database by hand. Release only with 100% of rows ticked by Laura. `check_claims.py` and `prisma_p_audit.py` are offline and work.
- **LITE-b:** no scripts: the same checklist (`checklist_refs_LITE.md`, including the section for references without DOI/PMID) and `templates/prisma_p_audit_LITE_es.md`, signed by Laura. Her conclusion «0 sin verificar» is hers, not yours.
- **LITE-P:** same checklists inside the Project.

## Journal
`verification` (`G-C7-refs`, `G-C7-provenance`, `G-C7-claims`, `G-C7-prisma-p`), `decision` (Laura: `unverifiable_resolution`), `reference_add` (Laura only), `change` (`ref_style`), `ai_use`.

## Never
- Mark a reference VALID without provenance, a DOI/PMID or a successful comparison · accept a source written by Claude · edit `references.csv` or the draft to make a check pass · write into `raw/`.
- Treat your semantic judgment as closing a gate · invent retraction status, metadata or the PRISMA-P wording.
