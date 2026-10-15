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
# La API a veces devuelve series vacías o con huecos al azar (pasó en octubre de 2026).
# Las series a las que les falta algún dato ya publicado se vuelven a pedir de a pocas.
LOTE_REINTENTO = 5
REINTENTOS_SEG = 90  # tiempo máximo de reintentos por indicador


def pedir(ids, intentos=3, timeout=60):
    """Devuelve {fecha: [valor por id]} para ids de la misma frecuencia."""
    params = {"ids": ",".join(ids), "limit": 5000, "format": "json", "metadata": "none"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "indicadores-de-la-realidad/0.1"})
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                filas = json.load(r)["data"]
            return {f[0][:7]: f[1:] for f in filas}
        except Exception:
            if intento == intentos - 1:
                raise
            time.sleep(3)


def leer_previo(nombre):
    """{key: {fecha: valor}} de la versión guardada, para detectar y tapar huecos."""
    ruta = DATA / f"{nombre}.json"
    if not ruta.exists():
        return {}
    d = json.loads(ruta.read_text(encoding="utf-8"))
    return {s["key"]: {f: v for f, v in zip(d["fechas"], s["valores"]) if v is not None}
            for s in d["series"]}


def descargar(indicador, previo=None, completar=True):
    """Baja las series del indicador. Con `previo` (ver leer_previo) vuelve a pedir las series
    a las que les falta algún dato ya publicado; si la API sigue sin darlo y `completar` es
    True, conserva el dato anterior. Con completar=False devuelve en "incompletas" las claves
    que quedaron con huecos, para que quien llama decida qué hacer."""
    series = indicador["series"]
    previo = previo or {}
    por_fecha = {}

    def volcar(datos, posiciones):
        for fecha, valores in datos.items():
            fila = por_fecha.setdefault(fecha, [None] * len(series))
            for j, v in zip(posiciones, valores):
                if v is not None:
                    fila[j] = v

    def incompletas():
        return [j for j, s in enumerate(series)
                if any(f not in por_fecha or por_fecha[f][j] is None for f in previo.get(s["key"], {}))]

    for i in range(0, len(series), IDS_POR_PEDIDO):
        lote = list(range(i, min(i + IDS_POR_PEDIDO, len(series))))
        try:
            volcar(pedir([series[j]["id"] for j in lote]), lote)
        except Exception as e:
            if not previo:
                raise
            print(f"  aviso: falló un pedido a la API ({e}); se reintenta de a pocas series")

    faltan = incompletas()
    limite = time.monotonic() + REINTENTOS_SEG
    while faltan and time.monotonic() < limite:
        print(f"  reintentando {len(faltan)} series incompletas...", flush=True)
        time.sleep(5)
        for k in range(0, len(faltan), LOTE_REINTENTO):
            lote = faltan[k : k + LOTE_REINTENTO]
            try:
                volcar(pedir([series[j]["id"] for j in lote], intentos=1, timeout=30), lote)
            except Exception:
                pass
            if time.monotonic() >= limite:
                break
        faltan = incompletas()

    if faltan and completar:
        for j in faltan:
            tapados = 0
            for f, v in previo[series[j]["key"]].items():
                fila = por_fecha.setdefault(f, [None] * len(series))
                if fila[j] is None:
                    fila[j] = v
                    tapados += 1
            print(f"  aviso: {indicador['id']}/{series[j]['key']}: la API no devolvió {tapados} datos; "
                  "se mantienen los ya publicados")
        faltan = []

    fechas = sorted(por_fecha)
    if indicador.get("desde"):  # el catálogo puede pedir arrancar más tarde
        fechas = [f for f in fechas if f >= indicador["desde"]]
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
    } | ({"incompletas": [series[j]["key"] for j in faltan]} if faltan else {})


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
        datos = descargar(ind, leer_previo(ind["id"]))
        datos["actualizado"] = ahora
        (DATA / f"{ind['id']}.json").write_text(
            json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        principal = datos["series"][0]
        resumen["indicadores"][ind["id"]] = {"titulo": ind["titulo"], **(ultimo(principal, datos["fechas"]) or {})}
        print(f"  último dato: {resumen['indicadores'][ind['id']].get('fecha')}")

    (DATA / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Sumando las series de carga manual...", flush=True)
    import manual
    manual.main()

    print("Calculando indicadores de consumo (INDEC)...", flush=True)
    import consumo
    consumo.main()

    print("Descargando gasto en protección social (Presupuesto Abierto)...", flush=True)
    import presupuesto
    presupuesto.main()

    diarios()
    print("Listo.")


if __name__ == "__main__":
    main()
