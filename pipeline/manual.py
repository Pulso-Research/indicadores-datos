"""Suma a los datos automáticos las series que se cargan a mano.

Hoy es una sola: la informalidad laboral total (manual/informalidad_total.csv), que el
INDEC publica en informes en PDF y no como dato abierto.

Cada archivo de manual/ tiene columnas periodo,valor,fuente. El período usa el mes en que
empieza el trimestre (01, 04, 07 o 10), igual que las series trimestrales de la API.

Uso:  python pipeline/manual.py   (lo llama fetch.py al final)
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANUAL = ROOT / "manual"

# archivo -> (indicador donde se agrega, clave, nombre, grupo, divisor)
CARGAS = [
    ("informalidad_total.csv", "desempleo", "informalidad_total",
     "Informalidad total (carga manual)", "Informalidad", 100),
]


def leer(archivo):
    filas = {}
    with open(MANUAL / archivo, encoding="utf-8") as f:
        for fila in csv.DictReader(l for l in f if not l.lstrip().startswith("#")):
            filas[fila["periodo"].strip()] = float(fila["valor"])
    return filas


def main():
    for archivo, indicador, key, nombre, grupo, divisor in CARGAS:
        ruta = DATA / f"{indicador}.json"
        d = json.loads(ruta.read_text(encoding="utf-8"))
        filas = leer(archivo)
        faltan = [p for p in filas if p not in d["fechas"]]
        if faltan:
            print(f"  aviso: {archivo} tiene períodos que no existen en {indicador}: {faltan}")
        valores = [round(filas[f] / divisor, 4) if f in filas else None for f in d["fechas"]]
        d["series"] = [s for s in d["series"] if s["key"] != key]
        d["series"].append({"key": key, "nombre": nombre, "grupo": grupo,
                            "manual": True, "valores": valores})
        d["actualizado"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        ruta.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        ultimo = max(p for p in filas)
        print(f"  {key}: {len(filas)} períodos cargados a mano (último {ultimo} = {filas[ultimo]}%)")


if __name__ == "__main__":
    main()
