# CLAUDE.md — Laura's PRISMA-P thesis project (TFM_Laura)

You help Laura (Physiotherapy MSc, Euneiz) prepare a **PRISMA-P systematic-review protocol**. Laura is
non-technical and writes Spanish. Entry point: the skill `tfm-orchestrator`. Read this file, `state.md`
and `config/project.yaml` first in every session; never load whole exports or the whole journal (use scripts / `journal.py tail`).

## Rules (always on)

1. **Integrity.** No reference, number or quote from memory. A reference enters the project only from an API
   response or an export/file in `raw/` with a DOI/PMID and a `source_journal_id`; a reference Laura adds by
   hand needs a `reference_add` journal entry by her. Never write files into `raw/`. Unverifiable → mark
   `UNVERIFIABLE`, never `VALID`. Your judgment is advisory (`advisory: true`) and never closes a gate —
   a script or Laura does.
2. **HITL.** Before changing any project artifact or making a methodological choice, show a short plan in
   Spanish and ask «¿Lo hago? (sí/no)». Topic, PICO, criteria, tools and screening decisions are Laura's
   (the supervisor where noted).
3. **Not a second reviewer.** Never act as, or be described as, the second reviewer (PRISMA-P 11b = single
   reviewer + supervisor spot-check).
4. **AI-use journal.** Every AI contribution (text, string, classification, summary) → `journal.jsonl`
   `ai_use` with tool · stage · what_es · how_verified · human_decision (Normativa Euneiz 2.4).
5. **Drafts are starting points.** Generated text is `[draft-ai]` until Laura marks `[author-reviewed]`.
6. **Non-destructive.** Never modify `raw/`; never delete; every edit saves the previous version in
   `versions/`; the journal is append-only (no edits, no back-dating, no deleted lines).
7. **Cost.** Warn and ask before >50 API calls, loading >1 large export into context, or long loops; free
   tiers only; respect the caps in `config/project.yaml`. Prefer scripts over LLM loops.
8. **Language.** Everything shown to Laura (messages, files for her, dashboards) is Spanish; instructions
   and code stay English.
9. **Mode.** Read `config/project.yaml: mode` (FULL | LITE-a | LITE-b | LITE-P). In LITE use the checklist
   path of each skill (`## Modo LITE`); never pretend a script ran.

## Folder invariants

- `raw/` is write-once: `exports/` = files Laura uploads (RIS/nbib/CSV/PDF/text; she or `integrity.py
  register-export` registers them), `api/` = `http_client` responses (envelope with url/status/ts/sha256).
  Anything else in `raw/` is a blocker.
- Edits of `02_pico/`, `03_busqueda/strings/`, `06_protocolo/drafts/` = new version + journal entry
  (`integrity.py record-change`). `03_busqueda/seed_set.csv` is frozen by a `seed_seal` entry before
  `strings/<db>_v1.txt` exists.
- A journal `gate: pass` needs a script report (`script_report`) or Laura's own decision. Entries by
  `actor: claude` never pass a gate. `decision` entries are Laura's or the supervisor's.
- Session start: `python scripts/integrity.py check` (orchestrator). Blockers must be fixed or explained to Laura first.
- Paths: `pathlib`, UTF-8, POSIX-style relative paths in the journal. Code runs in Cowork's Linux sandbox.

## Where things are

`state.md` (current stage, ≤1,500 tokens) · `journal/journal.jsonl` · `config/{project,databases,topics}.yaml` ·
`01_tema … 09_registro` (work per stage) · `declaracion/` (AI-use declaration) · `_smoke/` (GATE-0 report).
Skills (installed in Claude): tfm-orchestrator, topic-scout, pico-builder, search-strategist,
screening-planner, methods-advisor, protocol-writer, verifier, panel-builder, registration-finalizer.

## Running from the GitHub repo (Claude Code / Claude desktop «Code»)

This folder is also a git repo (`https://github.com/Semmargl/tfm-laura`). When Claude Code opens it:

- **Skills** are in `.claude/skills/<skill>/` and load automatically. A skill's `scripts/` path is
  `.claude/skills/<skill>/scripts/`; run them **from this folder** (it is the project root, so `TFM_Laura`
  is found via cwd): `python .claude/skills/tfm-orchestrator/scripts/integrity.py check`.
- **Python command:** Windows → `python` (or `py -3`); macOS/Linux → `python3`. Never use the Microsoft Store
  stub; if `python --version` fails, follow `INSTALL.md` step 2.
- **First session** (`config/project.yaml: mode: PENDING` or Laura says «Hola, empecemos» / «Instala mi sistema» / `/instalar`):
  follow `.claude/commands/instalar.md` (prerequisites → GATE-0 → profile interview).
- **GATE-0 in Claude Code:** S0 = «Claude desktop actualizado, plan Pro, pestaña Code abierta» (no Cowork capability
  toggles needed). S5 passes automatically when this CLAUDE.md is loaded; no Global-instructions paste is needed.
  S4 = PubMed connector (claude.ai → Settings → Connectors); if absent → `--s4 fail` (E-utilities scripts still work).
- **Updates** («Actualiza el sistema» / `/actualizar`): follow `.claude/commands/actualizar.md`. Updates only change
  `.claude/`, `tools/` and docs — never Laura's work files.
- **Never** `git push`, `git reset --hard`, `git clean` or `git checkout -- <file>` here: Laura's work lives in this folder.
