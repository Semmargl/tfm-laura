# LEEME PRIMERO — Sistema de ayuda para tu protocolo PRISMA-P

Hola, Laura. Este sistema trabaja contigo (no en tu lugar) para elegir tema, definir el PICO, diseñar la búsqueda,
verificar referencias y redactar tu protocolo. Tú decides todo lo importante; los números y las referencias solo
salen de PubMed y de tus archivos, nunca de la memoria de Claude. Todo queda anotado en un diario.

## Instalación

- **Claude para escritorio, pestaña Code (recomendado):** pega en Claude
  «Instala mi sistema TFM desde https://github.com/Semmargl/tfm-laura», luego abre una sesión nueva en la carpeta
  `TFM_Laura` y escribe `/instalar`. Detalles: `README.md` e `INSTALL.md`.
- **Cowork:** sigue `EMPIEZA_AQUI.md` del paquete de instalación (sube los **10** skills y conecta la carpeta `TFM_Laura`).

En los dos casos Claude hace la prueba del sistema (GATE-0) y te dice **«Modo: FULL»** o **«Modo: LITE»**
(en LITE el sistema funciona igual, pero algunas comprobaciones las haces tú con una lista y tu firma),
te pide tu **email** para `config/project.yaml` (solo lo usan las bases de datos gratuitas) y termina con «Listo».
Después escribe **«Quiero elegir tema»**.

## Frases que entiende

«¿Por dónde voy?» · «Sigamos» · «Quiero elegir tema» · «PICO» · «Búsqueda» · «Duplicados» · «Verificar referencias» · «Panel» · «Declaración IA» · «Revisa el sistema».

## Si algo falla

- Un mensaje de error de red o de herramienta: escribe **«Revisa el sistema»**. Claude repite la prueba y, si hace falta, pasa a modo LITE avisándote.
- Claude no sigue las reglas (por ejemplo, te inventa una referencia): *Settings → Cowork → Global instructions* y pega ahí el texto del archivo `CLAUDE.md` de tu carpeta.
- No aparece la carpeta o el estado: comprueba que `TFM_Laura` sigue conectada en Cowork.
- Cualquier otra cosa: copia el mensaje exacto y envíaselo a Vladyslav.

## Cuando Vladyslav te envíe una actualización

**Pestaña Code:** escribe `/actualizar` (o «Actualiza el sistema»). Claude descarga la nueva versión de GitHub sin tocar tus archivos.

**Cowork:**

1. Recibirás **solo los zip que cambiaron** y una nota «Actualización vX.Y» con la lista (y el archivo `UPDATE_NOTE.json`: guárdalo en la carpeta `TFM_Laura/_update/`).
2. En *Customize → Skills*: **borra la versión anterior** de cada skill de la lista y sube el zip nuevo (mismo nombre). **Orden: primero `tfm-orchestrator`, después los demás.**
3. Escribe **«Revisa el sistema»**: el orquestador compara la versión de cada skill con la nota, te dice si falta volver a subir alguno y anota la actualización en el diario.
4. Tus archivos de `TFM_Laura/` **no se tocan**: solo se sustituyen los skills.

## Reglas de oro

- Nada de referencias «de memoria»: cada referencia viene de PubMed o de un archivo tuyo con identificador.
- Antes de cambiar algo, Claude te enseña un plan y pregunta **«¿Lo hago? (sí/no)»**.
- Los textos que genera Claude son borradores `[draft-ai]` hasta que tú los reescribes y los marcas `[author-reviewed]`.
- No borres ni edites a mano `raw/` ni `journal/`.
