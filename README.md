# TFM Laura — asistente para tu protocolo PRISMA-P

Sistema de skills de Claude que te acompaña en el protocolo de revisión sistemática (PRISMA-P):
tema → PICO → búsqueda → selección → métodos → redacción → verificación de referencias → registro.
**Tú decides todo lo importante.** Las referencias y los números solo salen de PubMed y de tus archivos, nunca de la memoria de Claude. Todo queda en un diario (`journal/`), del que sale tu declaración de uso de IA (Normativa Euneiz 2.4).

## Instalación rápida (unos 15 minutos)

1. Instala **Claude para escritorio** (https://claude.com/download), entra con tu cuenta **Pro** y abre la pestaña **Code**.
   Si te pide instalar **Git**, instálalo (https://git-scm.com/download/win, todo por defecto) y vuelve a abrir Claude.
2. En la pestaña Code elige cualquier carpeta (por ejemplo *Documentos*) y pega este mensaje:

   ```
   Instala mi sistema TFM desde https://github.com/Semmargl/tfm-laura
   ```

3. Claude descarga el sistema en la carpeta `TFM_Laura` (en tu carpeta de usuario), instala lo que falte (te pedirá permiso) y lo comprueba.
4. Abre una **sesión nueva** en Code con la carpeta **`TFM_Laura`** y escribe **`/instalar`** (o «Hola, empecemos»).
   Claude hace la prueba del sistema, te hace unas preguntas para conocerte y termina con «Listo».
5. Recomendado: en *claude.ai → Settings → Connectors* conecta **PubMed**.

¿Usas **Cowork** en vez de Code? Descarga el paquete `TFM_Laura_instalacion_v….zip` de
[Releases](https://github.com/Semmargl/tfm-laura/releases/latest) y sigue su `EMPIEZA_AQUI.md`.

## Uso diario

| Escribe | Qué pasa |
|---|---|
| `/por-donde-voy` o «¿Por dónde voy?» | En qué etapa estás y qué toca |
| «Quiero elegir tema» · «PICO» · «Búsqueda» · «Duplicados» | Trabajo de cada etapa |
| «Verificar referencias» · «Panel» · «Declaración IA» | Comprobaciones, paneles HTML, declaración |
| `/revisa-sistema` | Vuelve a probar que todo funciona |
| `/actualizar` | Instala la última versión (tu trabajo no se toca) |

Más detalle: [LEEME_PRIMERO.md](LEEME_PRIMERO.md) · [GUIA_LAURA.md](GUIA_LAURA.md) · problemas: [INSTALL.md](INSTALL.md#si-algo-falla).

---

## For Claude — installer instructions

If a user gives you this repository URL and asks to install it, do the following. Talk to the user in **Spanish**,
short sentences; ask before installing software. Full details and troubleshooting: [INSTALL.md](INSTALL.md).

1. **You need a shell** (Claude Code / Claude desktop «Code» tab). If you are a plain chat without a shell,
   tell the user to open the **Code** tab of Claude desktop and paste the same message there, or use the Cowork package from Releases.
2. **Git.** `git --version`. Missing → Windows: `winget install -e --id Git.Git`; macOS: `xcode-select --install`.
3. **Clone** into the user's home folder (not a OneDrive-synced folder):
   `git clone https://github.com/Semmargl/tfm-laura.git ~/TFM_Laura`
   If `~/TFM_Laura` already exists: if it is this repo → `git -C ~/TFM_Laura pull --ff-only`; otherwise stop and ask.
4. **Python ≥ 3.8** (3.12 recommended). Check `python --version`, then `py -3 --version` (Windows), `python3 --version` (macOS).
   Missing → Windows: `winget install -e --id Python.Python.3.12` (then use `py -3` or
   `"$LOCALAPPDATA/Programs/Python/Python312/python.exe"` until Claude is restarted); macOS: `brew install python@3.12` or python.org.
   Never use the Microsoft Store `python` stub.
5. **Check:** `cd ~/TFM_Laura && python tools/doctor.py` (use the Python command that worked).
   Fix every `[FALTA]` line; for `[AVISO]` follow the hint printed (python-docx, SSL certificates).
6. **Hand over:** tell the user (Spanish): «Listo. Abre una sesión nueva en la pestaña Code con la carpeta `TFM_Laura`
   (está en tu carpeta de usuario) y escribe `/instalar`.» Skills in `.claude/skills/` load only in a session opened in that folder.

Do not run GATE-0 or the profile interview from the install session — `/instalar` does that inside `TFM_Laura`.
Never `git push` from the user's machine.

## Para Vladyslav (mantenimiento)

- Estructura: la raíz del repo **es** la carpeta del proyecto (`state.md`, `config/`, `journal/`, `01_tema…09_registro`);
  skills en `.claude/skills/` (versión 1.0.1 del kit), comandos en `.claude/commands/`, `tools/doctor.py`, `tools/build_release.py`.
- Nueva versión: cambiar skills → subir `VERSION` → `CHANGELOG.md` → `git tag vX.Y.Z && git push --tags`.
  GitHub Actions comprueba y publica en Releases el paquete Cowork + los 10 zip de skills.
- No modificar los archivos de trabajo de Laura (`state.md`, `config/project.yaml`, `journal/`, carpetas de etapas) después de v1.1.0:
  su `git pull` fallaría si ella los ha editado.
