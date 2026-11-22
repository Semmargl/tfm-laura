# Como leer un `query_check` (F-05)

| Campo | Significado | Que hacer |
|---|---|---|
| `translation` | Como PubMed ha entendido la ecuacion (QueryTranslation) | Ensenar a Laura; comprobar que cada concepto se expande como se espera |
| `errors` (PhraseNotFound / FieldNotFound / MeSH no valido) | Termino que PubMed no encuentra o no es descriptor exacto | **Bloqueo**: no se guarda ningun conteo; corregir con Laura |
| `warnings` (PhraseIgnored / QuotedPhraseNotFound / OutputMessage) | Parte de la ecuacion ignorada | Ensenar a Laura y decidir con ella |
| `mesh[]` | Resultado por termino: `valid`, `descriptor`, `ui`, `message` | Un sinonimo (entry term) NO vale: usar el descriptor |

Formato de las respuestas de `esearch db=mesh` / `esummary db=mesh` (campo `ds_meshterms`): **pendiente de verificar con red real en B6**;
si el formato es otro, el script marca el termino como NO valido (nunca lo da por bueno en silencio).
En LITE: Laura copia el bloque «Search details» de pubmed.gov y Claude solo senala (advisory) si los terminos MeSH coinciden.
