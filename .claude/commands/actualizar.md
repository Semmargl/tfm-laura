---
description: Actualiza los skills del sistema TFM desde GitHub sin tocar el trabajo de Laura
---

Update the TFM system from GitHub. Talk to Laura in Spanish.

1. `git status --short` — show Laura nothing technical; just check for problems.
2. `git fetch origin` then `git log --oneline HEAD..origin/main` — tell Laura in 1–3 lines what is new (read `CHANGELOG.md` on origin: `git show origin/main:CHANGELOG.md`).
3. Ask «¿Actualizo? (sí/no)». On «sí»: `git pull --ff-only origin main`.
   - If it fails because a file Laura worked on would be overwritten: **stop**, do not force anything, do not stash/reset/clean.
     Tell Laura to send the exact message to Vladyslav.
4. Run `python .claude/skills/tfm-orchestrator/scripts/integrity.py versions` and `python tools/doctor.py`.
5. Journal: `setup` entry «Actualización a vX.Y» (version from `VERSION`).
6. Tell Laura: «Actualizado a vX.Y. Cierra esta sesión y abre una nueva para cargar los skills nuevos.»

Never `git push`, `reset --hard`, `clean`, `checkout -- <file>` or `stash`.
