"""Pruebas de la lógica del PMV. Ejecutar:  python test_logica.py   (desde esta carpeta)"""
import os
import sys

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "04_Producto_Final"))
import logica as L  # noqa: E402

BD = os.path.join(AQUI, "..", "02_Datos", "aranita_roja_bd_v1.sqlite")
CSV = os.path.join(AQUI, "..", "02_Datos", "aranita_roja_analitico_v1.csv")

# 1. Carga desde SQLite: cifras de la Semana 9
d = L.cargar(BD)
ev, clima, cal = d["eval"], d["clima"], d["calidad"]
assert len(ev) == 1462 and ev["evaluacion_id"].is_unique
assert ev["fecha"].nunique() == 50 and len(clima) == 183
assert cal["evaluaciones_total"] == 1494 and cal["evaluaciones_observadas"] == 32
assert cal["duplicados_corregidos"] == 30 and cal["atipicos_postura"] == 2
assert not ev.duplicated(["fecha", "modulo", "valvula", "turno"]).any()
assert {"temperatura_minima_oc", "humedad_relativa_maxima"} <= set(ev.columns)
assert ev["unidad"].nunique() == ev[["modulo", "valvula"]].drop_duplicates().shape[0]   # válvula se identifica con módulo + válvula
assert abs(clima["gda_acum"].iloc[-1] - 2037.16) < 0.01 and abs(clima["generaciones_acum"].iloc[-1] - 12.43) < 0.01

# 2. Carga desde bytes (como lo hace el uploader de Streamlit) y desde CSV: mismos resultados clave
con_bytes = L.cargar(("aranita_roja_bd_v1.sqlite", open(BD, "rb").read()))
assert len(con_bytes["eval"]) == 1462
dc = L.cargar(CSV)
assert len(dc["eval"]) == 1462 and abs(dc["eval"]["hojas_inf_pct"].mean() - ev["hojas_inf_pct"].mean()) < 1e-9
assert abs(dc["eval"]["gda_acum"].max() - ev["gda_acum"].max()) < 0.01

# 3. Indicadores (mismos números del análisis de la Semana 10)
i = L.indicadores(ev, 10, 30)
assert abs(i["media"] - 10.13) < 0.01 and abs(i["mediana"] - 3.57) < 0.01 and round(i["pct_rojo"], 1) == 10.1 and round(i["pct_ambar_o_rojo"], 1) == 32.4
assert L.indicadores(ev.iloc[0:0], 10, 30)["evaluaciones"] == 0                      # vacío no falla
t = L.descriptivas_por_modulo(ev, 30)
assert t.loc[t["modulo"] == 1, "evaluaciones"].iloc[0] == 9 and "no comparar" in t.loc[t["modulo"] == 1, "lectura"].iloc[0]

# 4. Regla y semáforo (S11): casos límite, inválidos, umbral configurable
assert [L.clasificar(v, 10, 30) for v in (0, 9.99, 10, 29.99, 30, 100)] == ["Verde", "Verde", "Ámbar", "Ámbar", "Rojo", "Rojo"]
assert all(L.clasificar(v, 10, 30) == "No evaluable" for v in (-5, 101, float("nan"), float("inf"), "abc", None))
assert L.clasificar(15, 20, 40) == "Verde" and L.clasificar(15, 5, 12) == "Rojo"
for a, r in [(30, 10), (10, 10), (-1, 30), (10, 150)]:
    try:
        L.clasificar(5, a, r)
        raise AssertionError("debió fallar")
    except ValueError:
        pass
sf, ini, fin = L.semaforo_modulos(ev, "2026-08-28", 14, 5, 10, 30)
est = dict(zip(sf["modulo"], sf["estado"]))
assert est == {1: "Datos insuficientes", 2: "Verde", 3: "Verde", 4: "Verde", 5: "Ámbar", 6: "Verde"}, est
assert str(ini) == "2026-08-15" and str(fin) == "2026-08-28"
r4 = sf[sf["modulo"] == 4].iloc[0]
assert r4["evaluaciones"] == 35 and r4["evaluaciones_en_rojo"] == 3 and r4["observacion"].startswith("Revisar focos")
assert abs(sf[sf["modulo"] == 5]["media_%"].iloc[0] - 11.7509) < 1e-3
sf2, _, _ = L.semaforo_modulos(ev, "2026-08-28", 14, 50, 10, 30)
assert (sf2["estado"] == "Datos insuficientes").all()                                # mínimo configurable

# 5. Validación de estructura: datos sucios se rechazan, no se arreglan en silencio
malo = ev.copy(); malo.loc[malo.index[0], "hojas_inf_pct"] = 150
try:
    L.validar_estructura(malo); raise AssertionError("debió fallar")
except ValueError:
    pass
try:
    L.validar_estructura(ev.drop(columns=["modulo"])); raise AssertionError("debió fallar")
except ValueError as e:
    assert "Faltan columnas" in str(e)

# 6. Resumen del periodo (demostración final)
fr = L.resumen_periodo(ev, clima, "2026-06-01", "2026-08-28")
assert len(fr) >= 4 and "Spearman" in fr[-1]
assert "Con menos de 10 fechas" in L.resumen_periodo(ev, clima, "2026-03-01", "2026-03-31")[-1]
assert L.resumen_periodo(ev, clima, "2025-01-01", "2025-01-31") == ["No hay evaluaciones en el periodo elegido."]
ref = L.umbrales_de_referencia(ev)
assert 9 < ref["p68"] < 11 and 29 < ref["p90"] < 31

print("TODAS LAS PRUEBAS OK (", sum(1 for _ in open(__file__) if _.startswith("assert") or "assert " in _), "líneas con assert )")
