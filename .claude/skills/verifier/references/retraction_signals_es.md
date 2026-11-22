# Señales de retractación que lee el verificador (F-06, W2-1)

| Fuente | Señal | Estado |
|---|---|---|
| PubMed (efetch) | PublicationType «Retracted Publication» o CommentsCorrections `RetractionIn` | RETRACTED |
| PubMed | PublicationType «Retraction of Publication» (el PMID es el AVISO) | RETRACTED (no citar el aviso como artículo) |
| PubMed | PublicationType «Expression of Concern» o `ExpressionOfConcernIn` | EOC |
| PubMed | `ErratumIn` | aviso amarillo (fe de erratas) |
| Crossref (works) | `updated-by` con tipo retraction / withdrawal / removal | RETRACTED |
| Crossref (filter=updates:DOI) | un registro con `update-to` tipo retraction que apunta al DOI | RETRACTED |
| Crossref | tipo expression_of_concern | EOC |
| Crossref | `update-to` retraction en el propio DOI | RETRACTED (es el aviso) |

Una señal en CUALQUIERA de las dos fuentes bloquea. Retraction Watch Database (consulta manual) complementa a Crossref en el camino LITE. Ninguna señal no demuestra que no haya retractación: solo que estas fuentes no la registran.
