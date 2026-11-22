# Comprobación manual de cifras del panel (modo LITE-b/P)

Claude escribe el HTML copiando cada cifra **del diario** y su identificador (`data-journal-id`). Laura comprueba el **100 %** de las cifras (el panel de viabilidad tiene ≤ 20).
En LITE-a, `python scripts/panel_check.py checklist --file 08_paneles/panel_viabilidad.html` genera esta tabla sola.

| # | Cifra en el panel | Identificador del diario | Campo | Valor en el diario | ✔ Laura |
|---|---|---|---|---|---|
| 1 |  | J-____ | query.count |  | ☐ |
| 2 |  | J-____ | query.count |  | ☐ |

Comprobaciones finales (Laura):
- ☐ El archivo es uno solo y se abre sin internet.
- ☐ Todo el texto está en español.
- ☐ La recomendación dice «Sugerencia; decide Laura» y no hay recomendación sin número.
- ☐ Los paneles de flujo / mapa llevan la marca «PRELIMINAR — piloto, no forma parte del protocolo».

Firma de Laura: ____________   Fecha: ____________
