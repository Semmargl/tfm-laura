# Instalación detallada / Detailed install

Lo normal es que Claude haga todo esto solo (ver «Instalación rápida» en el [README](README.md)).
Este archivo es para cuando algo falla, o para hacerlo a mano.

## Requisitos

| Qué | Para qué | Cómo |
|---|---|---|
| Claude para escritorio + plan **Pro** | Pestaña **Code** (Claude Code) | https://claude.com/download |
| **Git** | Descargar y actualizar el sistema | Windows: https://git-scm.com/download/win o `winget install -e --id Git.Git` · macOS: `xcode-select --install` |
| **Python 3.8+** (recomendado 3.12) | Scripts de comprobación (stdlib, sin paquetes) | Windows: `winget install -e --id Python.Python.3.12` o python.org (marca «Add python.exe to PATH») · macOS: `brew install python@3.12` |
| python-docx (opcional) | Exportar el protocolo a .docx | `python -m pip install --user python-docx` |
| Conector **PubMed** (recomendado) | Búsquedas desde Claude | claude.ai → Settings → Connectors → PubMed |
| Internet hacia `eutils.ncbi.nlm.nih.gov`, `api.crossref.org`, `api.openalex.org` | Modo FULL (sin esto: LITE-a) | — |

## Pasos a mano

1. Instala Claude, Git y Python (tabla de arriba). Cierra y abre Claude después de instalar Python.
2. Abre una terminal (Windows: «Git Bash») y ejecuta:
   ```bash
   git clone https://github.com/Semmargl/tfm-laura.git ~/TFM_Laura
   ```
3. Comprueba:
   ```bash
   cd ~/TFM_Laura && python tools/doctor.py
   ```
   Debe terminar con `RESULTADO: LISTO`.
4. En Claude → pestaña Code → abre la carpeta `TFM_Laura` (en tu carpeta de usuario, `C:\Users\<tú>\TFM_Laura`) → escribe `/instalar`.

## Si algo falla

| Síntoma | Solución |
|---|---|
| `python` no se encuentra / abre la Microsoft Store | Instala Python de python.org marcando «Add python.exe to PATH», o usa `py -3`. Cierra y abre Claude |
| `[AVISO] Error de certificados SSL` | Windows: `python -m pip install --user pip-system-certs` · macOS: doble clic en `/Applications/Python 3.x/Install Certificates.command` |
| `[AVISO] Sin acceso a …` (sin error SSL) | Red o antivirus bloquean la conexión. El sistema funciona en **LITE-a** (algunas comprobaciones las haces tú con lista y firma) |
| `/instalar` no aparece | La sesión no está abierta en la carpeta `TFM_Laura`. Ábrela ahí (sesión nueva) |
| Claude no sigue las reglas (p. ej. inventa una referencia) | Comprueba que la sesión está en `TFM_Laura` (ahí está `CLAUDE.md`). En Cowork: pega `CLAUDE.md` en *Settings → Cowork → Global instructions* |
| `/actualizar` dice que un archivo se sobrescribiría | No fuerces nada. Copia el mensaje exacto y envíaselo a Vladyslav |
| Cualquier otra cosa | Escribe `/revisa-sistema`; si sigue, copia el error y envíaselo a Vladyslav |

## Cowork (sin pestaña Code)

Descarga `TFM_Laura_instalacion_v….zip` de [Releases](https://github.com/Semmargl/tfm-laura/releases/latest),
descomprímelo y sigue `EMPIEZA_AQUI.md` (subes los 10 skills en *Customize → Skills* y conectas la carpeta `TFM_Laura`).
