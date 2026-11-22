# EMPIEZA AQUÍ — Tu asistente para el protocolo PRISMA-P

Unos 20 minutos. Solo una vez.

## 1. Prepara Claude (5 min)
1. Instala o actualiza **Claude para Windows** (claude.com/download) y abre la pestaña **Cowork**.
2. *Settings → Capabilities*: activa **«Create and edit files»** y **«Allow network egress»**.
3. *Settings → Connectors*: conecta **PubMed**.

## 2. Copia tus archivos (5 min)
- Si aún no tienes el paquete: descarga `TFM_Laura_instalacion_vX.Y.Z.zip` de https://github.com/Semmargl/tfm-laura/releases/latest y descomprímelo.
4. Copia la carpeta **`TFM_Laura`** a *Documentos*.
5. En *Customize → Skills → + → Upload a skill*, sube **los 10 archivos** de la carpeta `skills`, uno por uno.
6. En Cowork, **conecta la carpeta** `Documentos\TFM_Laura`.

## 3. Deja que Claude haga el resto (10 min)
7. Abre una tarea nueva en Cowork y **pega este mensaje entero**:

```
Instala mi sistema TFM.
1) Comprobación: ejecuta la prueba del sistema del skill tfm-orchestrator (GATE-0). Si puedes usar subagentes, lánzalos en paralelo: uno comprueba que puedes ejecutar código y Python (instala python-docx si falta; si no se puede, sigue), otro que hay red a eutils.ncbi.nlm.nih.gov, api.crossref.org y api.openalex.org, otro que puedes leer y escribir en la carpeta TFM_Laura, y otro que el conector PubMed responde. Dime en 3-5 líneas qué funciona, qué no y el modo (FULL o LITE).
2) Conóceme: hazme estas preguntas en bloques cortos, con opciones cuando se pueda:
   - Cómo me llamas, tú o usted, cuánto detalle quiero y si quiero que me expliques la metodología para aprender.
   - Fecha de entrega (unos 5 meses), entregas intermedias, horas por semana y qué días trabajo.
   - Mi tutor/a: nombre, qué fases revisa y cómo le envío avances.
   - Tema: suelo pélvico; me interesa la diástasis de rectos y las hernias abdominales en mujeres (no es obligatorio). Poblaciones que sí y que no.
   - Bases de datos de la biblioteca de Euneiz, si uso Zotero o Rayyan, idiomas en que leo.
   - Estilo de citas (si aún no tengo la guía docente, Vancouver provisional).
   - Cuánta autonomía: ¿preguntas antes de cada paso o propones y yo confirmo por bloque?
   - Mis palabras clave: enséñame las frases por defecto y déjame cambiarlas o añadir las mías («cuando diga X, haz Y»).
   - Qué quiero ver al abrir cada sesión y cómo prefiero ver los resultados (tablas, gráficos).
   - Mi email para las bases de datos gratuitas.
3) Guarda mis respuestas: en config/perfil_laura.md, en una sección «Perfil de Laura» al final de TFM_Laura/CLAUDE.md, mi email en config/project.yaml, y anótalo en el diario. Las reglas de oro no cambian: yo decido, nada de referencias de memoria.
4) Escríbeme un texto corto (máximo 1500 caracteres) con mis preferencias, palabras clave y reglas, para que yo lo pegue en Settings → Cowork → Global instructions.
5) Termina con «Listo» y los 3 primeros pasos.
```

8. Responde a las preguntas y pega el texto final en *Settings → Cowork → Global instructions*.
9. Escribe **«Quiero elegir tema»**.

## Si algo falla
- Escribe **«Revisa el sistema»**.
- Más detalles: `TFM_Laura/LEEME_PRIMERO.md` y `TFM_Laura/GUIA_LAURA.md`.
- Si nada funciona, copia el mensaje de error y envíaselo a Vladyslav.
