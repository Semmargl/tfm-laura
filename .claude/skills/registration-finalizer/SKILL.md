---
name: registration-finalizer
description: Prepares PROSPERO/OSF registration fields for Laura to submit herself and runs the final consistency check before delivery. Use for "PROSPERO", "OSF", "entrega".
---

# registration-finalizer (C9)

Last stage: registration fields + final consistency gate. **It never registers or sends anything**; Laura does it herself. Text for Laura is Spanish; this file and code are English. Scripts in `scripts/` (`--root` or auto-detect).

## Inputs
`state.md` · `config/project.yaml` · `06_protocolo/drafts/*.md` + `06_protocolo/export/protocolo_ensamblado_es.md` · `02_pico/` · `03_busqueda/strings/` · `07_verificacion/` · `declaracion/` · journal tail.

## Steps
1. Read `state.md` + `project.yaml`; check `mode` (Modo LITE).
2. «¿Lo hago? (sí/no)» → `python scripts/consistency_check.py fields --target prospero` (and/or `osf`): copies protocol text into `09_registro/<target>_campos_es.md` as `[draft-ai]`; fields without source stay `[PENDIENTE]` for Laura. The templates are orientative (not verified against the live form): Laura must compare with the current PROSPERO/OSF form and acceptance criteria.
3. `python scripts/consistency_check.py check --journal` → writes `09_registro/checklist_entrega_es.md` and gate G-C9. Explain each red item in plain Spanish and route to the right skill (protocol-writer, verifier, search-strategist…). Never fix `raw/` or edit the journal.
4. Manual items are Laura's: `consistency_check.py sign --item M1|M2|M3 --laura-confirmed` after she says so.
5. When the gate passes: tell Laura the registration and delivery are hers to do. Journal + `state_tool.py set stage=C9 …`.

## Gate
G-C9 = checklist 100%: G-C6 passed with no later draft changes; all sections author-reviewed; assembled protocol up to date; section «Declaración de uso de inteligencia artificial» inside the document with Laura's non-empty justification, fresh against the last `ai_use` (F-08); PICO / search-string versions cited in the text match the latest files; references 0 NO_PROVENANCE / 0 UNVERIFIABLE with a G-C7 run ≤ 7 days old (or the LITE checklist 100% ✔); `integrity.py` clean; 0 external actions; manual items signed by Laura.

## Modo LITE
- **LITE-a:** scripts work offline; references are proven by the signed LITE checklist when there is no recent script run.
- **LITE-b / LITE-P:** no scripts. Use the table of items above as a manual checklist in `09_registro/checklist_entrega_es.md`; Claude proposes, Laura ticks each line and signs; show each journal line before saving.

## Journal
`change` (fields draft), `decision` (actor laura: `c9_item_signed`), `verification` (G-C9, actor script with report). Your judgment is `advisory: true` and never closes the gate.

## Never
- Register, submit or email anything on Laura's behalf · mark a manual item signed yourself · invent registry numbers, dates or references · hide a red item.
