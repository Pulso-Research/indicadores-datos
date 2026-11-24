"""Adelanta el EMAE desde los cuadros del INDEC cuando la API de datos.gob.ar viene atrasada.

Baja los Excel del INDEC (total y sectores), busca los meses que data/emae.json todavía no
tiene y los agrega a manual/completar.csv. Las columnas del Excel se asignan a las series
comparando con los meses que ya están publicados, así que si el INDEC cambia el orden no se
cruzan los datos: si alguna serie no coincide, el script frena sin escribir nada.

Es una herramienta para correr a mano (necesita la librería xlrd); la actualización
automática no la usa. Después hay que commitear manual/completar.csv y correr el workflow.

Uso:  python pipeline/completar_emae.py
"""
import csv
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.indec.gob.ar/ftp/cuadros/economia/"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
TOLERANCIA = 0.001  # diferencia relativa máxima para dar por buena una columna


def bajar(nombre, carpeta):
    ruta = Path(carpeta) / nombre
    pedido = urllib.request.Request(BASE + nombre, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        ruta.write_bytes(r.read())
    return ruta


def columnas(ruta, hoja):
    """{columna: {periodo: valor}} de una hoja con año en la columna 0 y mes en la 1."""
    sh = xlrd.open_workbook(ruta).sheet_by_name(hoja)
    salida, anio = {}, None
    for r in range(sh.nrows):
        a, m = sh.cell_value(r, 0), str(sh.cell_value(r, 1)).strip().lower()
        if isinstance(a, float):
            anio = int(a)
        if anio is None or m.rstrip("*") not in MESES:
            continue
        periodo = f"{anio}-{MESES.index(m.rstrip('*')) + 1:02d}"
        for c in range(2, sh.ncols):
            v = sh.cell_value(r, c)
            if isinstance(v, float):
                salida.setdefault(c, {})[periodo] = v
    return salida


def coincide(col, publicados):
    comunes = [p for p in publicados if p in col and publicados[p]]
    return len(comunes) >= 24 and all(abs(col[p] / publicados[p] - 1) < TOLERANCIA for p in comunes)


def main():
    d = json.loads((ROOT / "data" / "emae.json").read_text(encoding="utf-8"))
    publicados = {s["key"]: dict(zip(d["fechas"], s["valores"])) for s in d["series"]}
    ultimo = d["fechas"][-1]

    with tempfile.TemporaryDirectory() as tmp:
        cols = columnas(bajar("sh_emae_mensual_base2004.xls", tmp), "Tabla")
        sect = columnas(bajar("sh_emae_actividad_base2004.xls", tmp), "Tabla Letras")
    candidatas = [cols[2], cols[4]] + [sect[c] for c in sorted(sect)]  # original, desestacionalizada, sectores

    asignadas, sin_par = {}, []
    for key, pub in publicados.items():
        col = next((c for c in candidatas if coincide(c, pub)), None)
        if col is None:
            sin_par.append(key)
        else:
            asignadas[key] = col
    if sin_par:
        sys.exit(f"No se pudo identificar en el Excel del INDEC: {sin_par}. No se escribió nada.")

    nuevos = sorted({p for col in asignadas.values() for p in col if p > ultimo})
    if not nuevos:
        print(f"El INDEC no tiene meses posteriores a {ultimo}. Nada para completar.")
        return

    ruta_csv = ROOT / "manual" / "completar.csv"
    existentes = set()
    with open(ruta_csv, encoding="utf-8") as f:
        for r in csv.DictReader(l for l in f if not l.lstrip().startswith("#")):
            existentes.add((r["indicador"], r["serie"], r["periodo"]))
    filas = [("emae", key, p, round(col[p], 4), "INDEC, cuadros del EMAE (carga manual)")
             for p in nuevos for key, col in asignadas.items()
             if p in col and ("emae", key, p) not in existentes]
    with open(ruta_csv, "a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(filas)
    print(f"Agregados {len(filas)} datos del EMAE ({', '.join(nuevos)}) a manual/completar.csv")
    for key in ("general", "general_desest"):
        for p in nuevos:
            if p in asignadas[key]:
                print(f"  {key} {p}: {asignadas[key][p]:.4f}")


if __name__ == "__main__":
    main()
