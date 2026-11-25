"""Lógica de datos del PMV de arañita roja (sin Streamlit, para poder probarla).

Flujo: SQLite -> Pandas (consulta + validación + variables derivadas) -> indicadores -> semáforo.
La regla del semáforo es la misma del componente de la Semana 11.
"""
import os
import sqlite3
import tempfile

import numpy as np
import pandas as pd
from scipy import stats

TBASE = 10.34   # °C, supuesto de literatura (O. punicae), pendiente de validar en campo
K = 163.93      # GDA por generación, supuesto de literatura

SQL_ANALITICO = """
SELECT e.evaluacion_id, e.fecha, m.modulo, t.turno, e.valvula, e.plantas_evaluadas,
       e.aranita_hojas_infestadas    AS hojas_inf_pct,
       e.aranita_infestacion_postura AS postura_pct,
       c.temperatura_oc, c.temperatura_minima_oc, c.temperatura_maxima_oc,
       c.humedad_relativa, c.humedad_relativa_minima, c.humedad_relativa_maxima,
       c.estado_calidad_clima
FROM evaluacion_fitosanitaria e
JOIN clima_diario c ON c.fecha     = e.fecha
JOIN dim_modulo   m ON m.modulo_id = e.modulo_id
JOIN dim_turno    t ON t.turno_id  = e.turno_id
WHERE e.estado_calidad_evaluacion = 'ACEPTADO'
  AND e.fecha BETWEEN '2026-03-01' AND '2026-08-31'
ORDER BY e.fecha, m.modulo, e.valvula, t.turno;
"""

COLUMNAS_OBLIGATORIAS = ["evaluacion_id", "fecha", "modulo", "valvula", "hojas_inf_pct", "temperatura_oc", "humedad_relativa"]


# ----------------------------------------------------------------------------- carga
def _a_ruta(origen):
    """origen: ruta (str) o (nombre, bytes) de un archivo subido. Devuelve (ruta, es_temporal)."""
    if isinstance(origen, (tuple, list)):
        nombre, contenido = origen
        sufijo = os.path.splitext(nombre)[1] or ".dat"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
        tmp.write(contenido)
        tmp.close()
        return tmp.name, True
    return str(origen), False


def _agregar_gda(clima):
    clima = clima.sort_values("fecha").reset_index(drop=True).copy()
    clima["gda_dia"] = (clima["temperatura_oc"] - TBASE).clip(lower=0)
    clima["gda_acum"] = clima["gda_dia"].cumsum()
    clima["generaciones_acum"] = clima["gda_acum"] / K
    return clima


def _preparar_eval(ev, clima):
    ev = ev.copy()
    ev["fecha"] = pd.to_datetime(ev["fecha"])
    ev["mes"] = ev["fecha"].dt.to_period("M").astype(str)
    ev["unidad"] = "M" + ev["modulo"].astype(int).astype(str) + "-V" + ev["valvula"].astype(int).astype(str)
    cols = ["fecha", "gda_acum", "generaciones_acum"]
    ev = ev.drop(columns=[c for c in ["gda_acum", "generaciones_acum", "gda_dia"] if c in ev.columns]).merge(clima[cols], on="fecha", how="left", validate="m:1")
    return ev


def validar_estructura(ev):
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in ev.columns]
    if faltan:
        raise ValueError(f"Faltan columnas obligatorias: {faltan}")
    if ev["evaluacion_id"].duplicated().any():
        raise ValueError("Hay evaluacion_id repetidos")
    h = pd.to_numeric(ev["hojas_inf_pct"], errors="coerce")
    if h.isna().any() or not h.between(0, 100).all():
        raise ValueError("hojas_inf_pct tiene valores nulos o fuera de 0-100")


def cargar_sqlite(origen):
    """Lee la base de la Semana 8 y ejecuta la consulta analítica de la Semana 9."""
    ruta, temporal = _a_ruta(origen)
    try:
        con = sqlite3.connect(ruta)
        try:
            ev = pd.read_sql_query(SQL_ANALITICO, con)
            clima = pd.read_sql_query("SELECT * FROM clima_diario ORDER BY fecha", con, parse_dates=["fecha"])
            estados = pd.read_sql_query("SELECT estado_calidad_evaluacion AS estado, COUNT(*) AS n FROM evaluacion_fitosanitaria GROUP BY 1", con)
            flags = pd.read_sql_query(
                "SELECT SUM(flag_duplicado_logico_corregido) AS duplicados, SUM(flag_grado_postura_atipico) AS atipico_postura FROM evaluacion_fitosanitaria", con)
        finally:
            con.close()
    finally:
        if temporal:
            os.unlink(ruta)
    clima = _agregar_gda(clima)
    ev = _preparar_eval(ev, clima)
    validar_estructura(ev)
    total = int(estados["n"].sum())
    obs = int(estados.loc[estados["estado"] == "OBSERVADO", "n"].sum())
    calidad = {"fuente": "SQLite (consulta analítica S9)", "evaluaciones_total": total, "evaluaciones_aceptadas": len(ev),
               "evaluaciones_observadas": obs, "duplicados_corregidos": int(flags.loc[0, "duplicados"] or 0),
               "atipicos_postura": int(flags.loc[0, "atipico_postura"] or 0), "dias_clima": len(clima),
               "clima_observado": int((clima["estado_calidad_clima"] != "ACEPTADO").sum())}
    return {"eval": ev, "clima": clima, "calidad": calidad}


def cargar_csv(origen):
    """Alternativa: CSV analítico de la Semana 9 (no trae temperatura/humedad mín-máx)."""
    ruta, temporal = _a_ruta(origen)
    try:
        ev = pd.read_csv(ruta, encoding="utf-8-sig")
    finally:
        if temporal:
            os.unlink(ruta)
    ev["fecha"] = pd.to_datetime(ev["fecha"])
    base = ["fecha", "temperatura_oc", "humedad_relativa"]
    extra = [c for c in ["temperatura_minima_oc", "temperatura_maxima_oc", "humedad_relativa_minima", "humedad_relativa_maxima", "estado_calidad_clima", "gda_dia", "gda_acum"] if c in ev.columns]
    clima = ev.drop_duplicates("fecha")[base + extra].sort_values("fecha").reset_index(drop=True).copy()
    if "gda_acum" in clima.columns:
        # El CSV ya trae el GDA acumulado calculado sobre los 183 días de clima: no se recalcula con solo las fechas evaluadas.
        clima["generaciones_acum"] = clima["gda_acum"] / K
        if "gda_dia" not in clima.columns:
            clima["gda_dia"] = (clima["temperatura_oc"] - TBASE).clip(lower=0)
    else:
        clima = _agregar_gda(clima)
    ev = _preparar_eval(ev.drop(columns=[c for c in ["mes", "unidad"] if c in ev.columns]), clima)
    validar_estructura(ev)
    calidad = {"fuente": "CSV analítico (S9)", "evaluaciones_total": len(ev), "evaluaciones_aceptadas": len(ev), "evaluaciones_observadas": None,
               "duplicados_corregidos": None, "atipicos_postura": None, "dias_clima": clima["fecha"].nunique(), "clima_observado": None}
    return {"eval": ev, "clima": clima, "calidad": calidad}


def cargar(origen):
    nombre = origen[0] if isinstance(origen, (tuple, list)) else str(origen)
    return cargar_csv(origen) if nombre.lower().endswith(".csv") else cargar_sqlite(origen)


# ----------------------------------------------------------------------------- regla (S11)
def clasificar(valor, ambar, rojo):
    if not (np.isfinite(ambar) and np.isfinite(rojo)) or not (0 <= ambar < rojo <= 100):
        raise ValueError("Los umbrales deben cumplir 0 <= ámbar < rojo <= 100")
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "No evaluable"
    if not np.isfinite(v) or v < 0 or v > 100:
        return "No evaluable"
    if v >= rojo:
        return "Rojo"
    if v >= ambar:
        return "Ámbar"
    return "Verde"


def niveles(ev, ambar, rojo):
    return ev["hojas_inf_pct"].apply(lambda v: clasificar(v, ambar, rojo))


def semaforo_modulos(ev, fecha_corte, ventana_dias, min_eval, ambar, rojo):
    corte = pd.Timestamp(fecha_corte)
    inicio = corte - pd.Timedelta(days=int(ventana_dias) - 1)
    ventana = ev[(ev["fecha"] >= inicio) & (ev["fecha"] <= corte)]
    filas = []
    for m in sorted(ev["modulo"].unique()):
        sub = ventana[ventana["modulo"] == m]
        n = len(sub)
        media = sub["hojas_inf_pct"].mean() if n else np.nan
        rojas = int((sub["hojas_inf_pct"] >= rojo).sum())
        estado = "Datos insuficientes" if n < min_eval else clasificar(media, ambar, rojo)
        focos = estado in ("Verde", "Ámbar") and rojas > 0
        filas.append({"modulo": int(m), "evaluaciones": n, "fechas": sub["fecha"].nunique(), "media_%": media,
                      "maximo_%": sub["hojas_inf_pct"].max() if n else np.nan, "evaluaciones_en_rojo": rojas,
                      "estado": estado, "observacion": "Revisar focos: hay evaluaciones en Rojo aunque el promedio es menor" if focos else ""})
    return pd.DataFrame(filas), inicio.date(), corte.date()


# ----------------------------------------------------------------------------- indicadores
def indicadores(ev, ambar, rojo):
    n = len(ev)
    if n == 0:
        return {"evaluaciones": 0, "fechas": 0, "modulos": 0, "media": np.nan, "mediana": np.nan, "p90": np.nan, "pct_ambar_o_rojo": np.nan, "pct_rojo": np.nan}
    h = ev["hojas_inf_pct"]
    return {"evaluaciones": n, "fechas": ev["fecha"].nunique(), "modulos": ev["modulo"].nunique(), "media": h.mean(), "mediana": h.median(),
            "p90": h.quantile(0.9), "pct_ambar_o_rojo": 100 * (h >= ambar).mean(), "pct_rojo": 100 * (h >= rojo).mean()}


def descriptivas_por_modulo(ev, rojo):
    g = ev.groupby("modulo")["hojas_inf_pct"]
    t = g.agg(evaluaciones="count", media="mean", mediana="median", p90=lambda s: s.quantile(0.9), maximo="max").reset_index()
    t["pct_en_rojo"] = [100 * (ev.loc[ev["modulo"] == m, "hojas_inf_pct"] >= rojo).mean() for m in t["modulo"]]
    t["lectura"] = np.where(t["evaluaciones"] < 30, "pocas evaluaciones: no comparar", "")
    return t


def por_fecha(ev):
    return ev.groupby("fecha").agg(infestacion_media=("hojas_inf_pct", "mean"), evaluaciones=("evaluacion_id", "count")).reset_index()


def umbrales_de_referencia(ev):
    """Percentiles de la propia distribución: sustento provisional de los umbrales."""
    h = ev["hojas_inf_pct"]
    return {"p50": h.quantile(.5), "p68": h.quantile(.68), "p75": h.quantile(.75), "p90": h.quantile(.9), "p95": h.quantile(.95),
            "pct_ge_10": 100 * (h >= 10).mean(), "pct_ge_30": 100 * (h >= 30).mean()}


def resumen_periodo(ev, clima, ini, fin):
    """Frases descriptivas del periodo (para la demostración). No afirman causas."""
    ini, fin = pd.Timestamp(ini), pd.Timestamp(fin)
    sub = ev[(ev["fecha"] >= ini) & (ev["fecha"] <= fin)]
    cl = clima[(clima["fecha"] >= ini) & (clima["fecha"] <= fin)]
    if sub.empty:
        return ["No hay evaluaciones en el periodo elegido."]
    pf = por_fecha(sub)
    frases = [f"Periodo {ini.date()} a {fin.date()}: {len(sub)} evaluaciones en {len(pf)} fechas; infestación media {sub['hojas_inf_pct'].mean():.1f} % "
              f"(mediana {sub['hojas_inf_pct'].median():.1f} %, máximo {sub['hojas_inf_pct'].max():.1f} %)."]
    if len(pf) >= 4:
        mitad = len(pf) // 2
        a, b = pf["infestacion_media"].iloc[:mitad].mean(), pf["infestacion_media"].iloc[mitad:].mean()
        verbo = "subió" if b > a * 1.1 else ("bajó" if b < a * 0.9 else "se mantuvo similar")
        frases.append(f"Entre la primera y la segunda mitad de las fechas evaluadas la infestación media {verbo} ({a:.1f} % a {b:.1f} %).")
    if len(cl):
        frases.append(f"Temperatura media diaria {cl['temperatura_oc'].mean():.1f} °C (de {cl['temperatura_oc'].min():.1f} a {cl['temperatura_oc'].max():.1f}); "
                      f"humedad relativa media {cl['humedad_relativa'].mean():.1f} % (de {cl['humedad_relativa'].min():.1f} a {cl['humedad_relativa'].max():.1f}).")
        frases.append(f"GDA acumulado al {fin.date()}: {cl['gda_acum'].iloc[-1]:.0f} (≈ {cl['generaciones_acum'].iloc[-1]:.1f} generaciones teóricas, supuesto de literatura).")
    if len(pf) >= 10:
        t = clima.set_index("fecha")["temperatura_oc"]
        x = pf["fecha"].map(t)
        rho, p = stats.spearmanr(x, pf["infestacion_media"])
        if p < 0.05:
            frases.append(f"Asociación detectable entre temperatura e infestación por fecha (Spearman ρ = {rho:.2f}, p = {p:.3f}); describe el periodo, no demuestra causa.")
        else:
            frases.append(f"No hay evidencia suficiente de asociación entre temperatura e infestación por fecha (Spearman ρ = {rho:.2f}, p = {p:.2f}, {len(pf)} fechas).")
    else:
        frases.append("Con menos de 10 fechas no se calcula correlación: sería poco confiable.")
    return frases
