"""Controles de calidad antes de publicar los datos.

Compara cada data/<indicador>.json recién descargado con la última versión publicada
(la del último commit en git) y frena la publicación si algo no cierra:
  - falta un archivo, una serie o las fechas
  - las fechas retroceden o la historia se achica
  - la historia cambia demasiado (más allá de las revisiones habituales)
  - el último dato de la serie principal da un salto imposible
  - el dólar no se actualiza hace más de 10 días

Uso:  python pipeline/validar.py   (sale con código 1 si hay problemas)
"""
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INDICADORES = ["ipc", "emae", "pbi", "desempleo", "pobreza", "salarios", "canastas", "prestaciones", "proteccion"]

# salto máximo aceptable entre los dos últimos datos (proporción), por tipo de indicador
SALTO_MAX = {"indice": 0.5, "pesos": 0.5, "mixto": 1.0}
TASAS = {"desempleo", "pobreza"}  # valores entre 0 y 1
SIN_CONTROL_DE_SALTO = {"proteccion"}  # el gasto mensual es irregular (aguinaldos, pagos atrasados)
PERIODOS_RECIENTES = 6  # los últimos períodos pueden revisarse sin límite

problemas = []


def anterior(nombre):
    """Versión del archivo en el último commit, o None si todavía no existe."""
    try:
        out = subprocess.run(["git", "show", f"HEAD:data/{nombre}.json"], cwd=ROOT,
                             capture_output=True, check=True)
        return json.loads(out.stdout.decode("utf-8"))
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def valores_no_nulos(v):
    return sum(1 for x in v if x is not None)


def ultimos_dos(v):
    xs = [x for x in v if x is not None]
    return xs[-2:] if len(xs) >= 2 else None


def revisar_indicador(nombre):
    f = DATA / f"{nombre}.json"
    if not f.exists():
        problemas.append(f"{nombre}: falta el archivo")
        return
    try:
        nuevo = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        problemas.append(f"{nombre}: JSON inválido ({e})")
        return
    fechas, series = nuevo.get("fechas") or [], nuevo.get("series") or []
    if not fechas or not series:
        problemas.append(f"{nombre}: sin fechas o sin series")
        return
    if fechas != sorted(fechas):
        problemas.append(f"{nombre}: fechas desordenadas")

    for s in series:
        v = s.get("valores") or []
        if len(v) != len(fechas):
            problemas.append(f"{nombre}/{s.get('key')}: la cantidad de valores no coincide con las fechas")
            continue
        if nombre in TASAS and any(x is not None and not 0 <= x <= 1 for x in v):
            problemas.append(f"{nombre}/{s['key']}: hay tasas fuera del rango 0–1")
        tipo = nuevo.get("tipo", "indice")
        # el salto se controla solo en la serie principal: los sectores (pesca, agro) son muy estacionales
        par = ultimos_dos(v) if s is series[0] else None
        if par and nombre not in SIN_CONTROL_DE_SALTO and tipo in SALTO_MAX and par[0]:
            salto = abs(par[1] / par[0] - 1)
            if salto > SALTO_MAX[tipo]:
                problemas.append(f"{nombre}/{s['key']}: el último dato salta {salto:.0%} respecto del anterior")

    prev = anterior(nombre)
    if prev is None:
        return
    if fechas[-1] < prev["fechas"][-1]:
        problemas.append(f"{nombre}: la última fecha retrocede ({prev['fechas'][-1]} → {fechas[-1]})")
    claves_prev = {s["key"] for s in prev["series"]}
    claves = {s["key"] for s in series}
    if claves_prev - claves:
        problemas.append(f"{nombre}: desaparecieron series: {sorted(claves_prev - claves)}")

    idx_prev = {f: i for i, f in enumerate(prev["fechas"])}
    recientes = set(prev["fechas"][-PERIODOS_RECIENTES:])
    for s in series:
        ps = next((x for x in prev["series"] if x["key"] == s["key"]), None)
        if not ps:
            continue
        if valores_no_nulos(s["valores"]) < 0.9 * valores_no_nulos(ps["valores"]):
            problemas.append(f"{nombre}/{s['key']}: la historia perdió más del 10% de los datos")
        comparados = distintos = 0
        for i, fch in enumerate(fechas):
            j = idx_prev.get(fch)
            if j is None or fch in recientes:
                continue
            a, b = ps["valores"][j], s["valores"][i]
            if a is None or b is None or a == 0:
                continue
            comparados += 1
            if abs(b / a - 1) > 0.10:
                distintos += 1
        if comparados >= 12 and distintos / comparados > 0.05:
            problemas.append(f"{nombre}/{s['key']}: cambió más del 5% de la historia en más de un 10%")


def revisar_dolar():
    f = DATA / "dolar.json"
    if not f.exists():
        problemas.append("dolar: falta el archivo")
        return
    d = json.loads(f.read_text(encoding="utf-8"))
    fechas = d["diario"]["fechas"]
    if not fechas:
        problemas.append("dolar: sin cotizaciones")
        return
    atraso = (date.today() - datetime.strptime(fechas[-1], "%Y-%m-%d").date()).days
    if atraso > 10:
        problemas.append(f"dolar: la última cotización tiene {atraso} días")
    for casa, v in d["diario"]["series"].items():
        xs = [x for x in v if x]
        if casa != "solidario" and len(xs) < 30:
            problemas.append(f"dolar/{casa}: casi sin datos")
        if len(xs) >= 2 and abs(xs[-1] / xs[-2] - 1) > 0.30:
            problemas.append(f"dolar/{casa}: salto de {abs(xs[-1] / xs[-2] - 1):.0%} en un día")
    prev = anterior("dolar")
    if prev and fechas[-1] < prev["diario"]["fechas"][-1]:
        problemas.append("dolar: la última fecha retrocede")


def main():
    for nombre in INDICADORES:
        revisar_indicador(nombre)
    revisar_dolar()
    if problemas:
        print("Controles NO superados. No se publican los datos:")
        for p in problemas:
            print("  -", p)
        sys.exit(1)
    print("Controles superados.")


if __name__ == "__main__":
    main()
