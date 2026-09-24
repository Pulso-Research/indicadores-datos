"""Une todos los data/<indicador>.json en un único datos.json, que es lo que lee la
sección de la web.

Uso:  python pipeline/combinar.py [carpeta_de_salida]   (por defecto, la raíz del repo)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARCHIVOS = ["ipc", "emae", "pbi", "desempleo", "pobreza", "salarios", "canastas",
            "prestaciones", "proteccion", "consumo", "dolar", "riesgo"]


def main():
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    datos = {n: json.loads((DATA / f"{n}.json").read_text(encoding="utf-8")) for n in ARCHIVOS}
    datos["_actualizado"] = max(d.get("actualizado", "") for d in datos.values())
    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / "datos.json"
    destino.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK: {destino} ({destino.stat().st_size // 1024} KB, actualizado {datos['_actualizado']})")


if __name__ == "__main__":
    main()
