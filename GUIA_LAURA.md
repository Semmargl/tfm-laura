# Guía de uso (2 páginas)

## 1. Cómo es una sesión

1. Abre Cowork con la carpeta `TFM_Laura` conectada y escribe **«¿Por dónde voy?»**.
2. Claude comprueba que nada se ha tocado por error (integridad), te dice en qué etapa estás y qué toca. Responde «sí» o cuéntale qué cambió.
3. Pide lo que quieras con tus palabras («quiero comparar temas», «revisa mi PICO»). Claude te propone un plan y pregunta **«¿Lo hago? (sí/no)»**.
4. Al terminar, Claude anota en el diario lo que se hizo y actualiza `state.md`. Si cierras Cowork, la próxima vez continúas donde lo dejaste.

Consejo: las conversaciones largas sin archivos (dudas, explicaciones) hazlas en un chat normal; Cowork gasta más límite de tu plan.

## 2. Qué decides tú (y nadie más)

- El **tema**, el **PICO** y los **criterios** de inclusión/exclusión.
- Qué referencias entran, qué resultados del *citation chasing* son relevantes y si «ya existe una revisión con el mismo PICO».
- Las **firmas** de las comprobaciones de la búsqueda (revisión PRESS) y, en modo LITE, de las listas de verificación.
- El **texto final** de tu protocolo y la **justificación de la utilidad** de la IA para tu investigación.

Claude da sugerencias (siempre marcadas como tales) y hace el trabajo mecánico. Nunca actúa como segundo revisor.

## 3. Archivos que verás

| Carpeta / archivo | Para qué sirve |
|---|---|
| `state.md` | Dónde estás y qué toca (lo mantiene el sistema) |
| `01_tema` … `09_registro` | El trabajo de cada etapa |
| `08_paneles/*.html` | Paneles que se abren con doble clic en el navegador, sin internet |
| `raw/exports/` | **Tú** guardas aquí tus exportaciones (RIS, nbib, CSV) de CENTRAL, PEDro, LILACS… y los PDF/textos de artículos. No las edites después |
| `declaracion/declaracion_IA_es.md` | Declaración de uso de IA (Normativa Euneiz 2.4), generada del diario |
| `journal/journal.jsonl` | Diario del proyecto. No lo edites a mano |

Cuando guardes un archivo en `raw/exports/`, dile a Claude «he guardado el archivo X de la base Y»: lo registrará (y lo rechazará si no parece una exportación real).

## 4. Los paneles

Cada número de un panel indica de qué entrada del diario sale (pasa el ratón por encima). Si un número del panel no coincide con el diario, el sistema lo marca como error. Los paneles de flujo PRISMA y mapa de evidencia llevan la marca «PRELIMINAR — piloto, no forma parte del protocolo».

## 5. Declaración de uso de IA

Escribe **«Declaración IA»** cuando quieras ver el borrador. Se genera sola a partir del diario (herramientas, etapas, qué hizo la IA, cómo se verificó, decisión humana). El apartado final, **«Justificación de la utilidad para la investigación»**, lo escribes tú con tus palabras; Claude lo guarda tal cual. Esta declaración debe estar también dentro de tu protocolo (Anexo, con una mención en Metodología).

## 6. Modos de funcionamiento

- **FULL:** todo comprobado por scripts (conteos de PubMed, verificación de referencias, retractaciones, etc.).
- **LITE:** mismas reglas y mismos umbrales, pero parte de las comprobaciones las haces tú con una lista y tu firma. Claude te dirá cuál (LITE-a, LITE-b o LITE-P).
- El sistema puede bajar de FULL a LITE-a si falla internet; te avisará. «Revisa el sistema» vuelve a probar.

## 7. Límites y buenas prácticas

- Tu plan Pro tiene un límite de uso; si una sesión se corta, vuelve a abrir y escribe «Sigamos».
- Todo es gratuito: el sistema pide confirmación antes de hacer más de 50 consultas seguidas.
- Si Claude no encuentra una referencia en PubMed ni en tus archivos, la marcará **«no verificable»**: tendrás que encontrarle un identificador, aportar el archivo o sustituirla.
- Las bases de pago (Embase, CINAHL, Scopus…) solo se usan si Euneiz te da acceso; tú ejecutas la búsqueda y guardas la exportación.
