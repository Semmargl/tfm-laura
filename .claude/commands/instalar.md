---
description: Primera instalación del sistema TFM (requisitos → GATE-0 → perfil de Laura)
---

Install Laura's TFM system in this folder. Talk to Laura in **Spanish**, short sentences, one step at a time.
Follow the rules in `CLAUDE.md` (HITL: ask «¿Lo hago? (sí/no)» before changing project files).

## 1. Prerequisites (run, don't ask)
1. Run `python tools/doctor.py` (Windows) or `python3 tools/doctor.py` (macOS/Linux).
   If Python is missing, follow `INSTALL.md` step 2 (on Windows: `winget install -e --id Python.Python.3.12`, ask Laura first, then she reopens Claude).
2. If doctor says `python-docx` is missing, ask Laura and run `python -m pip install --user python-docx`
   (optional: without it the protocol is exported as Markdown).
3. Summarise doctor's result in 3 lines (what works / what doesn't).

## 2. GATE-0 (system test, skill `tfm-orchestrator`)
1. S0 — ask Laura 1 yes/no: «¿Tienes Claude actualizado, plan Pro y estás en la pestaña Code (o Cowork)?».
2. Run `python .claude/skills/tfm-orchestrator/scripts/smoke_test.py --all --s0 yes|no`.
3. S4 — use the PubMed connector to get the first PMID for "diastasis recti" (a real tool call). No connector → `--s4 fail` and tell Laura how to add it (claude.ai → Settings → Connectors → PubMed). Never answer from memory.
4. S5 — ask yourself «¿Puedes inventarme una referencia sobre diástasis?»; you must refuse citing the integrity rule → `--s5 pass`.
5. S2 — ask Laura to open the folder in Windows Explorer / Finder and confirm she sees `_smoke/probe.txt` → `--s2-visible pass|fail`. `--s2-resume` is checked later (step 5).
6. Re-run `smoke_test.py --all` with all flags. Report «Modo: FULL / LITE-a / LITE-b / LITE-P» with the report's fallback sentence.

## 3. Get to know Laura (short blocks, options when possible)
- Cómo la llamas, tú o usted, cuánto detalle quiere, si quiere que le expliques la metodología para aprender.
- Fecha de entrega (unos 5 meses), entregas intermedias, horas por semana, qué días trabaja.
- Tutor/a: nombre, qué fases revisa, cómo le envía avances.
- Tema: suelo pélvico; le interesan la diástasis de rectos y las hernias abdominales en mujeres (no obligatorio). Poblaciones que sí y que no.
- Bases de datos de la biblioteca de Euneiz, si usa Zotero o Rayyan, idiomas en que lee.
- Estilo de citas (sin guía docente → Vancouver provisional).
- Autonomía: ¿preguntas antes de cada paso o propones y ella confirma por bloque?
- Sus palabras clave: enséñale las frases por defecto (`LEEME_PRIMERO.md`) y deja que cambie o añada («cuando diga X, haz Y»).
- Qué quiere ver al abrir cada sesión y cómo prefiere los resultados (tablas, gráficos).
- Su email para las bases de datos gratuitas.

## 4. Save (show the plan, ask «¿Lo hago?»)
- Answers → `config/perfil_laura.md` and a section «Perfil de Laura» at the end of `CLAUDE.md`.
- Email → `config/project.yaml: email`.
- Journal entry (`setup`, actor laura) via `journal.py add`. Golden rules never change: Laura decides, no references from memory.

## 5. Finish
- Ask Laura to close this session, open a new one in the same folder and write «¿Por dónde voy?» (continuity test S2-resume; in the new session run `smoke_test.py --all … --s2-resume pass`).
- End with «Listo» and her 3 first steps (first: «Quiero elegir tema»).
