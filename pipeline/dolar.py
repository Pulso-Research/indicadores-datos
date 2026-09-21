"""Cotizaciones del dólar (oficial, mayorista, blue, MEP, CCL, cripto y tarjeta).

Fuente: API de ArgentinaDatos (https://argentinadatos.com), que recopila las
cotizaciones diarias de cierre. Escribe data/dolar.json con:
  - diario:  precio de venta de cada día desde DESDE_DIARIO
  - mensual: promedio mensual de venta desde el inicio de cada serie

Uso:  python pipeline/dolar.py
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares"
DESDE_DIARIO = "2020-01-01"
CASAS = [
    ("oficial", "Oficial (Banco Nación)"),
    ("mayorista", "Mayorista"),
    ("blue", "Blue"),
    ("bolsa", "MEP"),
    ("contadoconliqui", "Contado con liquidación"),
    ("cripto", "Cripto"),
    ("tarjeta", "Tarjeta"),
]


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "indicadores-de-la-realidad/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        filas = json.load(r)

    venta = {k: {} for k, _ in CASAS}
    for f in filas:
        if f.get("casa") in venta and f.get("venta"):
            venta[f["casa"]][f["fecha"]] = f["venta"]

    dias = sorted({d for serie in venta.values() for d in serie if d >= DESDE_DIARIO})
    diario = {k: [venta[k].get(d) for d in dias] for k, _ in CASAS}

    por_mes = {k: {} for k, _ in CASAS}
    for k, serie in venta.items():
        for d, v in serie.items():
            por_mes[k].setdefault(d[:7], []).append(v)
    meses = sorted({m for serie in por_mes.values() for m in serie})
    mensual = {k: [round(sum(por_mes[k][m]) / len(por_mes[k][m]), 2) if m in por_mes[k] else None for m in meses]
               for k, _ in CASAS}

    salida = {
        "id": "dolar",
        "titulo": "Dólar",
        "fuente": "ArgentinaDatos (cotizaciones de cierre; oficial y mayorista según BCRA y Banco Nación)",
        "casas": [{"key": k, "nombre": n} for k, n in CASAS],
        "diario": {"fechas": dias, "series": diario},
        "mensual": {"fechas": meses, "series": mensual},
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "dolar.json").write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  dolar: diario {dias[0]} a {dias[-1]}, mensual desde {meses[0]}")


if __name__ == "__main__":
    main()
