---
name: protocol-writer
description: Drafts and assembles the PRISMA-P protocol in academic Spanish as [draft-ai] starting points, with versions and the mandatory AI-use declaration section. Use for "redactar", "escribir sección".
---

# protocol-writer (C6)

Writes Laura's protocol section by section and assembles it in Euneiz format (Times New Roman 12, line spacing 1.5). Text for Laura is academic Spanish; this file and code are English. Scripts in `scripts/` (`--root` or auto-detect).

## Inputs
`state.md` · `config/project.yaml` (`citation_style`, `citation_style_status`) · artifacts of C1–C5 (`02_pico/`, `03_busqueda/strings/`, `05_metodos/`) · journal tail · `templates/protocol_skeleton_es.md` · `declaracion/declaracion_IA_es.md` (via the orchestrator's `declaration.py`).

## Steps
1. Read `state.md` + `project.yaml`; check `mode` (Modo LITE).
2. First time: `python scripts/assemble_protocol.py init-skeleton` (after «¿Lo hago? (sí/no)»). Creates `06_protocolo/drafts/<section>.md` with `[PENDIENTE: …]` instructions.
3. Context: read only the artifact for the section being written (never whole exports). Tell Laura which PRISMA-P items the section covers (table in `protocol_lib.py`).
4. Draft the section in academic Spanish → `python scripts/version_save.py replace --section S --text-file draft.md --what-es "…"` (saves the previous version, marks `[draft-ai]`, journals it). Every number or quotation carries `[ref:id|loc]` and comes from a verified source in `raw/`; nothing from memory. Cite the PICO and search-string versions with `[pico:vN]` and `[busqueda:base_vM]`. Write an `ai_use` entry per AI contribution.
5. Laura rewrites in her own words, then: `assemble_protocol.py mark-reviewed --section S --laura-confirmed`. Only her confirmation changes the label; an edit afterwards returns it to `[draft-ai]`. `mark-final` closes a section.
6. «Reader test» (advisory): a fresh chat reads the section and asks committee-style questions.
7. `assemble_protocol.py assemble [--docx] [--style vancouver|apa|harvard] [--placement anexo|metodologia] --title … --author … --supervisor …`. It inserts the live output of `declaration.render_section` as «Declaración de uso de inteligencia artificial» (default: Anexo B, plus the paragraph «Uso de herramientas de inteligencia artificial» in Metodología; placement per guía docente). Laura writes the subsection «Justificación de la utilidad para la investigación» (`declaration.py set-justification`).
8. `assemble_protocol.py check --journal` → gate G-C6. `assemble --release` (numbers Vancouver citations) only when the gate passes and all sections are reviewed.
9. Journal + `state_tool.py set stage=C6 step=… next_action_es=…`.

Default citation style is Vancouver, **provisional** until Laura gets the guía docente (A-4); APA/Harvard author-year formatting needs `ref_style.py` of the verifier. The `.docx` needs python-docx; if it is missing the script keeps the Markdown and says so — then ask Claude's built-in docx skill to convert it with the same format.

## Gate
G-C6: 100% of skeleton sections present, filled (no `[PENDIENTE]`) and with a valid label; 0 `[final]` without `[author-reviewed]` backed by Laura's journal decision on the current text; resumen ≤ 15 lines; every edit has its previous version in `versions/`; the assembled document contains the AI-declaration section, fresher than the last `ai_use`, with Laura's non-empty justification. Otherwise release is blocked (F-08).

## Modo LITE
- **LITE-a:** scripts work offline.
- **LITE-b / LITE-P:** no scripts. Draft sections in chat, Laura saves them in `06_protocolo/drafts/`, keep the old file in `versions/`, paste the declaration text from the orchestrator's template into the annex by hand, and sign the G-C6 checklist (sections complete, labels, declaration + justification, previous versions). Show each journal line before saving it.

## Journal
`change` (create/edit, with `previous_version`), `decision` (actor laura: `author_reviewed`, `section_final`), `ai_use`, `verification` (G-C6, actor script with report).

## Never
- Write a reference, number or quote from memory · mark a section `[author-reviewed]` yourself · skip the declaration section · edit a draft without saving the previous version · act as second reviewer.
