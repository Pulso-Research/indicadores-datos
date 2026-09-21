"""Gasto mensual devengado de los programas de protección social, a partir de los
datasets de Presupuesto Abierto (Ministerio de Economía).

Descarga credito-mensual-<año>.zip, suma el crédito devengado por programa según
las reglas de PROGRAMAS y escribe data/proteccion.json (millones de pesos corrientes).
Los zip se guardan en pipeline/cache/ y solo se vuelven a bajar si cambiaron.

Uso:  python pipeline/presupuesto.py
"""
import csv
import io
import json
import re
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "pipeline" / "cache"
DATA = ROOT / "data"
URL = "https://dgsiaf-repo.mecon.gob.ar/repository/pa/datasets/{y}/credito-mensual-{y}.zip"
DESDE = 2020
UA = {"User-Agent": "indicadores-de-la-realidad/0.1"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


# Cada programa: función que recibe (jurisdicción, programa, actividad) normalizados.
PROGRAMAS = [
    {"key": "auh", "nombre": "AUH y AUE", "grupo": "Niñez y alimentación",
     "regla": lambda j, p, a: p == "asignaciones familiares" and a.startswith("asignacion universal para proteccion social")},
    {"key": "alimentar", "nombre": "Tarjeta Alimentar", "grupo": "Niñez y alimentación",
     "regla": lambda j, p, a: p == "politicas alimentarias" and (a.startswith("prestacion alimentar") or a.startswith("tarjeta"))},
    {"key": "mil_dias", "nombre": "Plan 1000 Días (Ministerio de Salud)", "grupo": "Niñez y alimentación",
     "regla": lambda j, p, a: "salud" in j and ("1000 dias" in a or "embarazo y la primera infancia" in a)},
    {"key": "volver", "nombre": "Volver al Trabajo", "grupo": "Empleo",
     "regla": lambda j, p, a: a == "volver al trabajo"},
    {"key": "acompanamiento", "nombre": "Acompañamiento Social", "grupo": "Empleo",
     "regla": lambda j, p, a: "inclusion social" in p and a == "acompanamiento social"},
    {"key": "potenciar", "nombre": "Potenciar Trabajo (hasta 2024)", "grupo": "Empleo",
     "regla": lambda j, p, a: a.startswith("acciones del programa nacional de inclusion socio-productiva")},
    {"key": "jubilaciones", "nombre": "Jubilaciones y pensiones (SIPA)", "grupo": "Previsión social",
     "regla": lambda j, p, a: p == "prestaciones previsionales"},
    {"key": "bono", "nombre": "Bono previsional (complementos)", "grupo": "Previsión social",
     "regla": lambda j, p, a: p == "complementos a las prestaciones previsionales"},
    {"key": "puam", "nombre": "Pensión Universal para el Adulto Mayor", "grupo": "Previsión social",
     "regla": lambda j, p, a: p == "pension universal para el adulto mayor"},
]


def bajar(y):
    """Devuelve la ruta del zip del año y, bajándolo solo si cambió en el servidor."""
    CACHE.mkdir(exist_ok=True)
    url = URL.format(y=y)
    destino, sello = CACHE / f"credito-mensual-{y}.zip", CACHE / f"credito-mensual-{y}.stamp"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA, method="HEAD"), timeout=60) as r:
            remoto = r.headers.get("Last-Modified", "")
    except Exception:
        return destino if destino.exists() else None
    if destino.exists() and sello.exists() and sello.read_text() == remoto:
        return destino
    print(f"  bajando {url}", flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        destino.write_bytes(r.read())
    sello.write_text(remoto)
    return destino


def leer(zpath):
    z = zipfile.ZipFile(zpath)
    raw = z.read(z.namelist()[0])
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = raw.decode("latin-1")
    return csv.DictReader(io.StringIO(txt))


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_actualizacion(texto):
    """'Última actualización del ejercicio 2026: 18 Septiembre 2026.' -> '2026-09-18'."""
    m = re.search(r"(\d{1,2}) (\w+) (\d{4})", norm(texto))
    if not m or m.group(2) not in MESES:
        return ""
    return f"{m.group(3)}-{MESES.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"


def main():
    anio_actual = datetime.now().year
    totales = {}  # (key, "AAAA-MM") -> millones
    ultima_act = ""
    for y in range(DESDE, anio_actual + 1):
        zpath = bajar(y)
        if not zpath:
            print(f"  sin datos para {y}")
            continue
        for fila in leer(zpath):
            j, p, a = norm(fila["jurisdiccion_desc"]), norm(fila["programa_desc"]), norm(fila["actividad_desc"])
            for prog in PROGRAMAS:
                if prog["regla"](j, p, a):
                    mes = f"{int(fila['impacto_presupuestario_anio']):04d}-{int(fila['impacto_presupuestario_mes']):02d}"
                    monto = float((fila["credito_devengado"] or "0").replace(",", "."))
                    totales[(prog["key"], mes)] = totales.get((prog["key"], mes), 0.0) + monto
                    break
            if y == anio_actual and not ultima_act:
                ultima_act = fecha_actualizacion(fila.get("ultima_actualizacion_fecha", ""))

    meses = sorted({m for _, m in totales})
    # El mes en curso al momento de la última actualización está incompleto: se descarta.
    if meses and ultima_act and meses[-1] >= ultima_act[:7]:
        meses = [m for m in meses if m < ultima_act[:7]]

    series = [{"key": "general", "nombre": "Total de estos programas", "grupo": "Total", "valores": []}]
    for prog in PROGRAMAS:
        vals = [totales.get((prog["key"], m)) for m in meses]
        series.append({"key": prog["key"], "nombre": prog["nombre"], "grupo": prog["grupo"],
                       "valores": [round(v, 2) if v else None for v in vals]})
    series[0]["valores"] = [round(sum(s["valores"][i] or 0 for s in series[1:]), 2) for i in range(len(meses))]

    salida = {
        "id": "proteccion",
        "titulo": "Gasto en protección social",
        "frecuencia": "mensual",
        "unidad": "Millones de pesos corrientes (crédito devengado)",
        "fuente": "Presupuesto Abierto — Ministerio de Economía (crédito devengado mensual)",
        "tipo": "gasto",
        "fechas": meses,
        "series": series,
        "fuente_actualizada": ultima_act,
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "proteccion.json").write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  proteccion: {meses[0]} a {meses[-1]} (fuente actualizada {ultima_act})")


if __name__ == "__main__":
    main()
