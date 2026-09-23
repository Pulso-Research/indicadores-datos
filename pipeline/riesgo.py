"""Riesgo país (índice EMBI+ Argentina de JP Morgan), valores diarios.

Fuente: API de ArgentinaDatos (https://argentinadatos.com), que publica la serie diaria.
Escribe data/riesgo.json desde DESDE.

Uso:  python pipeline/riesgo.py
"""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
URL = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais"
DESDE = "2007-01-01"


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "indicadores-de-la-realidad/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        filas = json.load(r)

    por_fecha = {}
    for f in filas:
        fecha, valor = f.get("fecha"), f.get("valor")
        if fecha and fecha >= DESDE and valor:
            por_fecha[fecha] = round(float(valor), 1)

    fechas = sorted(por_fecha)
    salida = {
        "id": "riesgo",
        "titulo": "Riesgo país",
        "frecuencia": "diaria",
        "unidad": "Puntos básicos",
        "fuente": "ArgentinaDatos — índice EMBI+ Argentina (JP Morgan)",
        "diario": {"fechas": fechas, "valores": [por_fecha[f] for f in fechas]},
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "riesgo.json").write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  riesgo: {fechas[0]} a {fechas[-1]} ({por_fecha[fechas[-1]]:.0f} puntos)")


if __name__ == "__main__":
    main()
