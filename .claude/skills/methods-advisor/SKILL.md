---
name: methods-advisor
description: 'Plans review methods for the protocol: RoB tool by study design, PEDro vs RoB, GRADE, synthesis plan, TIDieR/CERT. Planning only. Use for "métodos", "sesgo", "GRADE", "síntesis".'
---

# methods-advisor (C5)

Plans the methods section of Laura's PRISMA-P protocol. **Planning only: it never assesses risk of bias of any study** (scope D-3). All output to Laura is Spanish; this file and code are English. Scripts: `python scripts/methods_plan.py ...` (project folder found automatically, or `--root`).

## Inputs
`state.md` · `config/project.yaml` · `02_pico/*.md` (study designs in the eligibility criteria) · `references/*.md` (tool notes; every one carries URL + `fecha de verificación`).

## Steps
1. Read `state.md` + `project.yaml`; check `mode` (see Modo LITE).
2. Ask Laura which study designs her criteria include (RCT, non-randomised, observational, qualitative...) and whether the interventions are exercise-based.
3. `methods_plan.py tools --design <d>` lists the applicable tools. Explain each option in plain Spanish with its source. **PEDro:** explain that it rates methodological quality (and reporting) of physiotherapy RCTs and is not a risk-of-bias tool in the strict sense (it is not a substitute for RoB 2); Laura chooses to use it as a complement or not.
4. Show a short plan and ask «¿Lo hago? (sí/no)». Then `methods_plan.py plan --designs a,b [--exercise yes]` writes `05_metodos/extraccion_es.md`, `rob_grade_es.md`, `sintesis_es.md` as `[draft-ai]` options (nothing chosen).
5. For each choice Laura makes: `methods_plan.py record-choice --topic rob:rct --tool rob2 --pedro use|skip --laura-confirmed --note "..."` (journal `decision`, actor laura). Same for `--topic grade`, `synthesis`, `reporting_exercise` (TIDieR / CERT).
6. Laura opens each tool's source URL, then `methods_plan.py confirm-source --choice J-xxxx --laura-confirmed` (C7 `verifier` may also check the URLs later).
7. `methods_plan.py check --journal` runs gate G-C5; then `ai_use` entry for the drafted text and `state_tool.py set stage=C5 step=… next_action_es=…`.

## Gate
G-C5: every design in the plan has a Laura-made tool choice that is applicable to that design, has a source URL, and its source is confirmed; RCT designs carry Laura's PEDro decision; GRADE and synthesis choices exist (and TIDieR/CERT choice if exercise). A script report (`07_verificacion/reports/g_c5_*.json`) closes the gate; Claude's judgment never does.

## Modo LITE
- **LITE-a:** scripts work offline (no network needed here).
- **LITE-b / LITE-P:** no scripts. Fill the tables in `templates/rob_grade_es.md` by hand with Laura; show each journal line to her before saving; the gate is the checklist at the end of that template, signed by Laura.

## Journal
`decision` (actor laura; `kind: c5_choice` / `c5_source_confirmed`), `ai_use` for each AI-drafted text, `verification` (G-C5, actor script with report).

## Never
- Assess the risk of bias of studies · choose a tool for Laura · state a citation, number or version not in `references/` · call PEDro a RoB tool · act as second reviewer.
