"""Descarga las series definidas en catalog.json desde la API de Series de Tiempo
(datos.gob.ar) y escribe un JSON por indicador en data/, más data/resumen.json.

Uso:  python pipeline/fetch.py               (todo: INDEC/ANSES, presupuesto y dólar)
      python pipeline/fetch.py --solo-dolar  (dólar y riesgo país, para la corrida diaria)
Solo usa la biblioteca estándar de Python.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "pipeline" / "catalog.json"
DATA = ROOT / "data"
API = "https://apis.datos.gob.ar/series/api/series/"
IDS_POR_PEDIDO = 20  # la API acepta hasta 40 ids por consulta


def pedir(ids):
    """Devuelve {fecha: [valor por id]} para ids de la misma frecuencia."""
    params = {"ids": ",".join(ids), "limit": 5000, "format": "json", "metadata": "none"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "indicadores-de-la-realidad/0.1"})
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                filas = json.load(r)["data"]
            return {f[0][:7]: f[1:] for f in filas}
        except Exception:
            if intento == 2:
                raise
            time.sleep(3)


def descargar(indicador):
    series = indicador["series"]
    por_fecha = {}
    for i in range(0, len(series), IDS_POR_PEDIDO):
        lote = series[i : i + IDS_POR_PEDIDO]
        datos = pedir([s["id"] for s in lote])
        for fecha, valores in datos.items():
            fila = por_fecha.setdefault(fecha, [None] * len(series))
            fila[i : i + len(lote)] = valores

    fechas = sorted(por_fecha)
    # Recorta meses iniciales sin ningún dato
    while fechas and all(v is None for v in por_fecha[fechas[0]]):
        fechas.pop(0)

    salida_series = []
    for j, s in enumerate(series):
        valores = [por_fecha[f][j] for f in fechas]
        valores = [round(v, 4) if isinstance(v, (int, float)) else None for v in valores]
        if s.get("cero_es_nulo"):  # series discontinuadas que la API completa con ceros
            valores = [v or None for v in valores]
        salida_series.append({k: s[k] for k in ("key", "nombre", "grupo", "id") if k in s}
                             | ({"oculta": True} if s.get("oculta") else {})
                             | {"valores": valores})

    return {
        "id": indicador["id"],
        "titulo": indicador["titulo"],
        "frecuencia": indicador["frecuencia"],
        "unidad": indicador["unidad"],
        "fuente": indicador["fuente"],
        "tipo": indicador.get("tipo", "indice"),
        "fechas": fechas,
        "series": salida_series,
    }


def ultimo(serie, fechas):
    for f, v in zip(reversed(fechas), reversed(serie["valores"])):
        if v is not None:
            return {"fecha": f, "valor": v}
    return None


def diarios():
    """Series diarias: cotizaciones del dólar y riesgo país (ArgentinaDatos)."""
    print("Descargando cotizaciones del dólar (ArgentinaDatos)...", flush=True)
    import dolar
    dolar.main()
    print("Descargando riesgo país (ArgentinaDatos)...", flush=True)
    import riesgo
    riesgo.main()


def main():
    if "--solo-dolar" in sys.argv:
        diarios()
        return

    catalogo = json.loads(CATALOG.read_text(encoding="utf-8"))
    DATA.mkdir(exist_ok=True)
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    resumen = {"actualizado": ahora, "indicadores": {}}

    for ind in catalogo["indicadores"]:
        print(f"Descargando {ind['id']} ({len(ind['series'])} series)...", flush=True)
        datos = descargar(ind)
        datos["actualizado"] = ahora
        (DATA / f"{ind['id']}.json").write_text(
            json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        principal = datos["series"][0]
        resumen["indicadores"][ind["id"]] = {"titulo": ind["titulo"], **(ultimo(principal, datos["fechas"]) or {})}
        print(f"  último dato: {resumen['indicadores'][ind['id']].get('fecha')}")

    (DATA / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Descargando gasto en protección social (Presupuesto Abierto)...", flush=True)
    import presupuesto
    presupuesto.main()

    diarios()
    print("Listo.")


if __name__ == "__main__":
    main()
