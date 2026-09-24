"""Indicadores de consumo del INDEC: supermercados, autoservicios mayoristas y
centros de compras (shoppings), más los saldos de préstamos al consumo del BCRA.

Los tres canales se toman de los índices oficiales a precios constantes.
Los rubros se publican en pesos corrientes: acá se deflactan por el IPC nacional
(estimación propia) y se expresan como índice base 2017 = 100, para poder compararlos.

Escribe data/consumo.json. Requiere data/ipc.json, así que corre después de fetch.py.

Uso:  python pipeline/consumo.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import fetch  # reutiliza la descarga por lotes de la API de series

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "2017"  # año base del índice

# (key, nombre, grupo, id, deflactar)
SERIES = [
    ("general", "Supermercados", "Canales", "455.1_VENTAS_PRENAL_0_M_34_10", False),
    ("general_desest", "Supermercados (desestacionalizado)", "Canales", "455.1_VENTAS_PREADA_0_M_44_44", False),
    ("mayoristas", "Autoservicios mayoristas", "Canales", "456.1_VENTAS_PRETES_0_M_25_67", False),
    ("shoppings", "Centros de compras (shoppings)", "Canales", "458.1_VENTAS_TOTNAL_0_M_42_19", False),

    ("s_almacen", "Almacén", "Rubros de supermercados", "455.1_ALMACENCEN_0_M_7_95", True),
    ("s_bebidas", "Bebidas", "Rubros de supermercados", "455.1_BEBIDASDAS_0_M_7_9", True),
    ("s_carnes", "Carnes", "Rubros de supermercados", "455.1_CARNESNES_0_M_6_38", True),
    ("s_lacteos", "Lácteos", "Rubros de supermercados", "455.1_LACTEOSEOS_0_M_7_27", True),
    ("s_panaderia", "Panadería", "Rubros de supermercados", "455.1_PANADERIARIA_0_M_9_14", True),
    ("s_verduleria", "Verdulería y frutería", "Rubros de supermercados", "455.1_VERDULERIARIA_0_M_19_68", True),
    ("s_rotiseria", "Alimentos preparados y rotisería", "Rubros de supermercados", "455.1_ALIMENTOS_RIA_0_M_30_74", True),
    ("s_limpieza", "Limpieza y perfumería", "Rubros de supermercados", "455.1_ARTICULOS_RIA_0_M_29_41", True),
    ("s_indumentaria", "Indumentaria y textiles para el hogar", "Rubros de supermercados", "455.1_INDUMENTARGAR_0_M_35_24", True),
    ("s_electronica", "Electrónicos y artículos para el hogar", "Rubros de supermercados", "455.1_ELECTRONICGAR_0_M_28_99", True),
    ("s_online", "Compras online", "Rubros de supermercados", "455.1_CANALES_ONINE_0_M_15_84", True),

    ("c_indumentaria", "Indumentaria, calzado y marroquinería", "Rubros de shoppings", "458.1_INDUMENTARRIA_ABRI_M_34_29", True),
    ("c_electronica", "Electrónicos, electrodomésticos y computación", "Rubros de shoppings", "458.1_ELECTRONICION_ABRI_M_42_47", True),
    ("c_comidas", "Patio de comidas, alimentos y kioscos", "Rubros de shoppings", "458.1_PATIO_COMIDAS_ABRI_M_13_59", True),
    ("c_perfumeria", "Perfumería y farmacia", "Rubros de shoppings", "458.1_PERFUMERIACIA_ABRI_M_19_16", True),
    ("c_deportes", "Ropa y accesorios deportivos", "Rubros de shoppings", "458.1_ROPA_ACCESVOS_ABRI_M_26_72", True),
    ("c_amoblamientos", "Amoblamientos y decoración", "Rubros de shoppings", "458.1_AMOBLAMIENGAR_ABRI_M_39_10", True),
    ("c_jugueteria", "Juguetería", "Rubros de shoppings", "458.1_JUGUETERIARIA_ABRI_M_10_48", True),
    ("c_libreria", "Librería y papelería", "Rubros de shoppings", "458.1_LIBRERIA_PRIA_ABRI_M_18_18", True),
    ("c_diversion", "Diversión y esparcimiento", "Rubros de shoppings", "458.1_DIVERSION_NTO_ABRI_M_23_37", True),

    # Saldos de préstamos en pesos al sector privado (BCRA), deflactados por IPC
    ("p_consumo", "Préstamos al consumo (total)", "Financiamiento", "91.1_DETALLE_PREND_0_0_33", True),
    ("p_personales", "Préstamos personales", "Financiamiento", "91.1_DETALLE_PRLES_0_0_52", True),
    ("p_tarjetas", "Tarjetas de crédito", "Financiamiento", "91.1_DETALLE_PRTAS_0_0_60", True),
    ("p_prendarios", "Prendarios (autos)", "Financiamiento", "91.1_DETALLE_PREND_0_0_53", True),
]


def ipc_por_mes():
    d = json.loads((DATA / "ipc.json").read_text(encoding="utf-8"))
    v = d["series"][0]["valores"]
    return {f: v[i] for i, f in enumerate(d["fechas"]) if v[i] is not None}


def a_indice(valores, fechas):
    """Lleva la serie a índice base 2017 = 100."""
    base = [v for f, v in zip(fechas, valores) if f.startswith(BASE) and v is not None]
    if not base:
        return [None] * len(valores)
    prom = sum(base) / len(base)
    return [None if v is None else round(v / prom * 100, 2) for v in valores]


def main():
    indicador = {
        "id": "consumo",
        "titulo": "Consumo",
        "frecuencia": "mensual",
        "unidad": "Índice base 2017 = 100, a precios constantes",
        "fuente": "INDEC (encuestas de supermercados, autoservicios mayoristas y centros de compras) y BCRA (préstamos)",
        "series": [{"key": k, "nombre": n, "grupo": g, "id": i} for k, n, g, i, _ in SERIES],
    }
    datos = fetch.descargar(indicador)
    fechas = datos["fechas"]
    ipc = ipc_por_mes()

    for s, (_, _, _, _, deflactar) in zip(datos["series"], SERIES):
        v = s["valores"]
        if deflactar:  # rubros en pesos corrientes -> a precios constantes con el IPC
            v = [None if (x is None or ipc.get(f) is None) else x / ipc[f] for x, f in zip(v, fechas)]
        s["valores"] = a_indice(v, fechas)

    # recorta los meses iniciales sin ningún dato (el IPC, que deflacta, empieza en dic-2016)
    corte = 0
    while corte < len(fechas) and all(s["valores"][corte] is None for s in datos["series"]):
        corte += 1
    if corte:
        datos["fechas"] = fechas[corte:]
        for s in datos["series"]:
            s["valores"] = s["valores"][corte:]

    datos.update({
        "titulo": "Consumo",
        "frecuencia": "mensual",
        "unidad": "Índice base 2017 = 100, a precios constantes",
        "fuente": "INDEC (encuestas de supermercados, autoservicios mayoristas y centros de compras) y BCRA (préstamos)",
        "tipo": "volumen",
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
    })
    for s in datos["series"]:
        if s["key"] == "general_desest":
            s["oculta"] = True

    (DATA / "consumo.json").write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ult = datos["fechas"][-1]
    print(f"  consumo: {datos['fechas'][0]} a {ult} ({len(datos['series'])} series)")


if __name__ == "__main__":
    main()
