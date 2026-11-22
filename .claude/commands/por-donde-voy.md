---
description: Resumen de en qué etapa está el proyecto y qué toca ahora
---

Use the skill `tfm-orchestrator` (briefing): run `integrity.py check`, read `state.md` and the last 20 journal lines
(`journal.py tail -n 20`), then answer in Spanish: «Estás en {stage}/{step}. Siguiente: {next_action_es}. ¿Seguimos? (sí / cambió algo)».
If `config/project.yaml: mode` is `PENDING`, run `/instalar` instead.
