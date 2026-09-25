# Indicadores de la realidad — datos

Datos que alimentan la sección **Indicadores de la realidad** de [Pulso Research](https://pulsoresearch.com).
Se actualizan solos con GitHub Actions y se publican en GitHub Pages:

- **Todo junto:** https://pulso-research.github.io/indicadores-datos/datos.json
- **Por indicador:** `https://pulso-research.github.io/indicadores-datos/data/<indicador>.json`

## Qué incluye

| Archivo | Contenido | Fuente |
|---|---|---|
| `ipc` | Inflación: nivel general, categorías y 12 divisiones | INDEC |
| `emae` | Actividad económica: total y sectores | INDEC |
| `pbi` | PBI trimestral: total, demanda y sectores | INDEC |
| `desempleo` | Desocupación, actividad e informalidad (EPH) | INDEC |
| `pobreza` | Personas bajo la línea de pobreza (EPH) | INDEC |
| `salarios` | Índice de salarios | INDEC |
| `canastas` | Canasta básica total y alimentaria | INDEC |
| `prestaciones` | Montos y beneficiarios de AUH, AUE, jubilaciones y PUAM | ANSES |
| `proteccion` | Gasto mensual devengado en programas sociales | Presupuesto Abierto (Ministerio de Economía) |
| `consumo` | Ventas en supermercados, mayoristas y shoppings, con rubros | INDEC |
| `dolar` | Oficial, mayorista, blue, MEP, CCL, cripto y tarjeta | ArgentinaDatos |
| `riesgo` | Riesgo país (EMBI+ Argentina), desde 2007 | ArgentinaDatos (JP Morgan) |

Las series del INDEC y la ANSES se toman de la [API de Series de Tiempo](https://datos.gob.ar/series) de datos.gob.ar.

## Cuándo se actualiza

- **Días hábiles a las 10:30 y 15:05 (hora de Argentina):** dólar y riesgo país.
- **Lunes, miércoles y viernes a las 8:00 y a las 19:00:** actualización completa (la de las 19:00 alcanza los informes que el INDEC publica alrededor de las 16:00).

Antes de publicar, `pipeline/validar.py` controla que no falten series, que las fechas no retrocedan
y que no haya saltos imposibles. Si algo falla, no se publica nada y la web sigue mostrando los datos anteriores.

## Correr a mano

Requiere Python 3.12, sin librerías extra.

```
python pipeline/fetch.py              # todo
python pipeline/fetch.py --solo-dolar # solo el dólar
python pipeline/validar.py
python pipeline/combinar.py
```
