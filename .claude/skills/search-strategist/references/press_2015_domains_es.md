# PRESS 2015 - dominios y quién los cierra

Fuente: PRESS Peer Review of Electronic Search Strategies, 2015 Guideline Statement (McGowan et al., J Clin Epidemiol 2016). Verificar la cita completa (volumen, páginas, DOI) en la fuente antes de citarla en el protocolo (riesgo R-5).

| # | Dominio | Cierra |
|---|---|---|
| 1 | Traducción de la pregunta de investigación | advisory de Claude + firma de Laura |
| 2 | Operadores booleanos y de proximidad | `press_lint.py lint` (sintaxis) |
| 3 | Descriptores (subject headings) | advisory de Claude + firma de Laura |
| 4 | Palabras de texto libre | advisory de Claude + firma de Laura |
| 5 | Ortografía, sintaxis de campos y números de línea | `press_lint.py lint` (la ortografía no está automatizada: la mira Laura) |
| 6 | Límites y filtros | advisory de Claude + firma de Laura |

Una valoración de Claude nunca cierra un dominio. Lo recomendable es que el tutor o una bibliotecaria revise los cuatro dominios de contenido.

## Notas de sintaxis de PubMed que revisa el script
- Los operadores AND / OR / NOT van en MAYÚSCULAS; en minúsculas PubMed los trata como palabras.
- Sin comillas, una etiqueta de campo (`pelvic floor[tiab]`) solo afecta a la última palabra; con comillas (`"pelvic floor"[tiab]`) afecta a la frase.
- El truncamiento `*` dentro de comillas no se expande.
- Cada término `[mh]` se comprueba contra `db=mesh` (el descriptor debe existir).
