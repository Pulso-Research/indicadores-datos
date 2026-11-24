"""Suma a los datos automáticos las series que se cargan a mano.

Hoy son dos: la informalidad laboral total y la indigencia, que el INDEC publica en
informes en PDF y no como datos abiertos.

Cada archivo de manual/ tiene columnas periodo,valor,fuente. El período usa el mes en que
empieza el trimestre (01, 04, 07 o 10), igual que las series trimestrales de la API.

Además, manual/completar.csv adelanta datos que el INDEC ya publicó pero la API de
datos.gob.ar todavía no cargó (columnas indicador,serie,periodo,valor,fuente). Solo llena
los huecos: en cuanto la API trae ese período, se usa el dato de la API y la fila manual
deja de tener efecto, así que se puede borrar.

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
    ("indigencia.csv", "pobreza", "indigencia",
     "Indigencia (carga manual)", "General", 100),
]


def leer(archivo):
    filas = {}
    with open(MANUAL / archivo, encoding="utf-8") as f:
        for fila in csv.DictReader(l for l in f if not l.lstrip().startswith("#")):
            filas[fila["periodo"].strip()] = float(fila["valor"])
    return filas


def completar():
    ruta_csv = MANUAL / "completar.csv"
    if not ruta_csv.exists():
        return
    with open(ruta_csv, encoding="utf-8") as f:
        filas = list(csv.DictReader(l for l in f if not l.lstrip().startswith("#")))
    resumen_path = DATA / "resumen.json"
    resumen = json.loads(resumen_path.read_text(encoding="utf-8")) if resumen_path.exists() else None
    for indicador in sorted({r["indicador"].strip() for r in filas}):
        ruta = DATA / f"{indicador}.json"
        d = json.loads(ruta.read_text(encoding="utf-8"))
        usados, ignorados = [], []
        for r in (r for r in filas if r["indicador"].strip() == indicador):
            key, periodo, valor = r["serie"].strip(), r["periodo"].strip(), float(r["valor"])
            serie = next((s for s in d["series"] if s["key"] == key), None)
            if serie is None:
                print(f"  aviso: completar.csv: {indicador} no tiene la serie {key}")
                continue
            if periodo not in d["fechas"]:
                i = sum(1 for x in d["fechas"] if x < periodo)
                d["fechas"].insert(i, periodo)
                for s in d["series"]:
                    s["valores"].insert(i, None)
            i = d["fechas"].index(periodo)
            if serie["valores"][i] is None:
                serie["valores"][i] = valor
                serie.setdefault("manual_periodos", []).append(periodo)
                usados.append(f"{key} {periodo}")
            else:
                ignorados.append(f"{key} {periodo}")
        ruta.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if usados:
            print(f"  {indicador}: {len(usados)} datos completados a mano ({usados[0]}...)")
        if ignorados:
            print(f"  {indicador}: la API ya trae {len(ignorados)} datos de completar.csv; se pueden borrar")
        if resumen and indicador in resumen.get("indicadores", {}):
            s0 = d["series"][0]
            for fch, v in zip(reversed(d["fechas"]), reversed(s0["valores"])):
                if v is not None:
                    resumen["indicadores"][indicador].update({"fecha": fch, "valor": v})
                    break
    if resumen:
        resumen_path.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    completar()
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
