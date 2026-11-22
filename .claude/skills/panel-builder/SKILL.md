---
name: panel-builder
description: 'Builds offline single-file HTML dashboards (Spanish) from the project journal: topic feasibility, search yield, PRISMA flow, evidence map, PRISMA-P status. Use for "panel", "ver resultados".'
---

# panel-builder (C8)

Builds Spanish dashboards that contain **only numbers from `journal/journal.jsonl`** (and `config/project.yaml` thresholds). Never from the conversation.
Phase 1: **viabilidad** (topic feasibility) and a watermarked **flow** (pilot). `busqueda`, `mapa`, `prisma_p` arrive in phase 2–3.
Output to Laura Spanish; this file and code English. Scripts in `scripts/` (offline; FULL and LITE-a).

## Inputs
`state.md` + `config/project.yaml` · `journal/journal.jsonl` (entries with `topic_id` + `metric`: `total, rct_10y, ct, sr_5y, ctgov_records, prospero, epistemonikos, who_ictrp`,
`query_check`, `decision` kind `same_pico_sr` with `outcome`; for flow: `count` with `metric` ∈ `flow_identificados, flow_duplicados, flow_cribados, flow_excluidos, flow_incluidos`)
· `config/topics.yaml`.

## Steps
1. Read `state.md` and `config/project.yaml`.
2. Run `python scripts/integrity.py check` (orchestrator) if the session just started; a blocker must be explained first.
3. Say what you will build and ask «¿Lo hago? (sí/no)».
4. `python scripts/build_panel.py --panel viabilidad` → `08_paneles/panel_viabilidad.html`. It runs `panel_check` automatically (mismatch must be **0**).
   Flow: `--panel flow` → `08_paneles/panel_prisma_flow.html`, always stamped **«PRELIMINAR — piloto, no forma parte del protocolo»** (W-1; the protocol needs the selection plan, not results).
5. `python scripts/panel_check.py check --file 08_paneles/panel_viabilidad.html --journal` → script report + journal `verification` (G-C8). Only this closes the gate.
6. Tell Laura (ES): file path, how many numbers were checked, any «sin datos» cell, and that the recommendation is «Sugerencia; decide Laura».
   Hover a number to see its journal id. Missing data stays «sin datos» — do not fill it with an estimate.
7. A stale panel (journal moved on) → `STALE_PANEL` warning → rebuild.
8. `ai_use` entry for your contribution, then orchestrator `journal.py add` + `state_tool.py set stage=C8 …`.

## Gate
G-C8 / Q8-1 / Q8-2: panel↔journal mismatch **0** (`panel_check.py`) · one HTML file, offline (no CDN/scripts/links) · UI Spanish · 0 console errors (checked in a browser at B6) · flow/mapa watermarked.

## Modo LITE
- **LITE-a:** same scripts (no network needed).
- **LITE-b / LITE-P:** no scripts. Copy `templates/panel_viabilidad_skeleton.html`, fill it by hand copying every number **from the journal** with `data-journal-id`, `data-field`, `data-value`;
  Laura verifies 100 % of the numbers (≤ 20) with `templates/checklist_numeros_LITE.md`. Without her signature G-C8 is «no demostrado».
Never claim a script ran when it did not.

## Journal
`verification` (actor script, gate_name `G-C8`, with `script_report`) · `ai_use` for each AI contribution. Your narrative («insight → recomendación») is `advisory: true` and signed «Sugerencia; decide Laura».

## Never
Put a number in the panel that is not in the journal · invent or estimate missing data · recommend a topic without numbers · load external scripts, fonts, CDNs or images ·
present pilot flow or evidence-map figures without the PRELIMINAR watermark · close G-C8 on your own judgment.
