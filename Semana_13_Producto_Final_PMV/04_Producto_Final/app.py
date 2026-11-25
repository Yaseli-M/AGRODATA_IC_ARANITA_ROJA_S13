"""PMV: Sistema de monitoreo y análisis fitosanitario de la arañita roja (Oligonychus punicae).
Fundo Loma Verde S.A.C. · Proyecto Productivo IB · Equipo AgroData IC.

Arquitectura: SQLite -> Pandas (logica.py) -> Plotly -> Streamlit.
Ejecutar desde esta carpeta:  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import logica as L

st.set_page_config(page_title="Monitoreo de arañita roja · AgroData IC", layout="wide")

RUTA_BD = Path(__file__).resolve().parent.parent / "02_Datos" / "aranita_roja_bd_v1.sqlite"
ICONO = {"Verde": "🟢 Verde", "Ámbar": "🟠 Ámbar", "Rojo": "🔴 Rojo", "Datos insuficientes": "⚪ Datos insuficientes", "No evaluable": "⚪ No evaluable"}


@st.cache_data(show_spinner=False)
def cargar_datos(nombre, contenido):
    """Con contenido = None lee la base del proyecto; si no, el archivo que subió el usuario."""
    return L.cargar(str(RUTA_BD) if contenido is None else (nombre, contenido))


# ----------------------------------------------------------------------------- barra lateral
st.sidebar.header("Datos")
subido = st.sidebar.file_uploader("Cargar otra base (.sqlite) o CSV analítico (.csv)", type=["sqlite", "db", "csv"])
try:
    if subido is not None:
        datos = cargar_datos(subido.name, subido.getvalue())
    elif RUTA_BD.exists():
        datos = cargar_datos(RUTA_BD.name, None)
    else:
        st.error("No se encontró 02_Datos/aranita_roja_bd_v1.sqlite. Sube la base o el CSV desde la barra lateral.")
        st.stop()
except Exception as e:  # el producto explica el error en vez de mostrar un traceback
    st.error(f"No se pudo leer el archivo: {e}")
    st.stop()

ev_all, clima, calidad = datos["eval"], datos["clima"], datos["calidad"]
f_min, f_max = ev_all["fecha"].min().date(), ev_all["fecha"].max().date()

st.sidebar.header("Filtros de consulta")
rango = st.sidebar.date_input("Periodo", value=(f_min, f_max), min_value=f_min, max_value=f_max)
if isinstance(rango, (tuple, list)) and len(rango) == 2:
    ini, fin = rango
else:  # mientras el usuario elige la segunda fecha
    ini, fin = f_min, f_max
modulos_sel = st.sidebar.multiselect("Módulo", sorted(ev_all["modulo"].unique().tolist()), default=sorted(ev_all["modulo"].unique().tolist()))
unidades_posibles = sorted(ev_all.loc[ev_all["modulo"].isin(modulos_sel), "unidad"].unique().tolist(), key=lambda u: (int(u.split("-")[0][1:]), int(u.split("-")[1][1:])))
unidades_sel = st.sidebar.multiselect("Unidad de monitoreo (módulo-válvula)", unidades_posibles, default=[])
st.sidebar.caption("Una válvula se identifica con módulo + válvula: el mismo número de válvula existe en varios módulos.")

st.sidebar.header("Umbrales del semáforo")
ambar = st.sidebar.number_input("Ámbar desde (% de hojas infestadas)", min_value=0.0, max_value=99.0, value=10.0, step=1.0)
rojo = st.sidebar.number_input("Rojo desde (% de hojas infestadas)", min_value=1.0, max_value=100.0, value=30.0, step=1.0)
ventana = st.sidebar.selectbox("Ventana del semáforo (días)", [7, 14, 21, 28], index=1)
min_eval = st.sidebar.selectbox("Mínimo de evaluaciones por módulo", [1, 3, 5, 10], index=2)
fechas_eval = sorted(ev_all["fecha"].dt.date.unique().tolist())
corte = st.sidebar.selectbox("Fecha de corte", fechas_eval[::-1], index=0)
umbrales_ok = ambar < rojo
if not umbrales_ok:
    st.sidebar.error("El umbral ámbar debe ser menor que el rojo. Se usan 10 % y 30 %.")
    ambar, rojo = 10.0, 30.0

# datos filtrados
ev = ev_all[(ev_all["fecha"].dt.date >= ini) & (ev_all["fecha"].dt.date <= fin) & (ev_all["modulo"].isin(modulos_sel))]
if unidades_sel:
    ev = ev[ev["unidad"].isin(unidades_sel)]

# ----------------------------------------------------------------------------- encabezado
st.title("Monitoreo de arañita roja en palto Hass")
st.caption("Fundo Loma Verde S.A.C. (Supe, Barranca) · campaña marzo a agosto de 2026 · Proyecto Productivo IB · AgroData IC")
st.write("**Decisión que apoya:** priorizar qué módulos revisar o intervenir según la infestación observada en campo. "
         "El grado-día se muestra como contexto térmico; no activa el semáforo.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1 · Carga de registros", "2 · Indicadores", "3 · Análisis temporal", "4 · Consulta", "Semáforo por módulo"])

# ----------------------------------------------------------------------------- 1. carga y calidad
with tab1:
    st.subheader("Registros cargados y su calidad")
    st.write(f"Fuente: **{calidad['fuente']}**")
    c = st.columns(4)
    c[0].metric("Evaluaciones usadas", f"{calidad['evaluaciones_aceptadas']:,}")
    c[1].metric("Fechas de evaluación", ev_all["fecha"].nunique())
    c[2].metric("Días de clima", calidad["dias_clima"])
    c[3].metric("Periodo", f"{f_min:%d/%m} – {f_max:%d/%m}")
    if calidad["evaluaciones_observadas"] is not None:
        st.write(f"De **{calidad['evaluaciones_total']:,}** evaluaciones en la base, **{calidad['evaluaciones_observadas']}** quedaron observadas y no entran al análisis: "
                 f"{calidad['duplicados_corregidos']} duplicados lógicos corregidos y {calidad['atipicos_postura']} valores atípicos de grado de postura. "
                 "Siguen en la base para trazabilidad; solo se excluyen de la consulta.")
        if calidad["clima_observado"]:
            st.write(f"{calidad['clima_observado']} días de clima están marcados como observados; se conservan con su marca.")
    else:
        st.info("Se cargó un CSV analítico: ya viene filtrado por la Semana 9, y el clima solo cubre las fechas evaluadas. Para ver la calidad completa usa la base SQLite.")
    st.write("**Validaciones al cargar:** columnas obligatorias, `evaluacion_id` único, porcentajes entre 0 y 100, unión con el clima sin duplicar filas.")
    st.dataframe(ev_all.head(20), use_container_width=True)

# ----------------------------------------------------------------------------- 2. indicadores
with tab2:
    st.subheader("Indicadores de infestación (según los filtros)")
    if ev.empty:
        st.warning("No hay evaluaciones con los filtros elegidos.")
    else:
        ind = L.indicadores(ev, ambar, rojo)
        c = st.columns(5)
        c[0].metric("Evaluaciones", f"{ind['evaluaciones']:,}")
        c[1].metric("Infestación media", f"{ind['media']:.1f} %")
        c[2].metric("Mediana", f"{ind['mediana']:.1f} %")
        c[3].metric(f"Evaluaciones ≥ {ambar:.0f} %", f"{ind['pct_ambar_o_rojo']:.1f} %")
        c[4].metric(f"Evaluaciones ≥ {rojo:.0f} %", f"{ind['pct_rojo']:.1f} %")
        st.caption("La media supera a la mediana porque la distribución es asimétrica: pocos focos concentran la infestación.")
        g1, g2 = st.columns(2)
        fig = px.histogram(ev, x="hojas_inf_pct", nbins=20, labels={"hojas_inf_pct": "% de hojas infestadas por evaluación"})
        fig.update_layout(yaxis_title="Número de evaluaciones", title="Distribución de la infestación", bargap=0.05)
        fig.add_vline(x=ambar, line_dash="dash", annotation_text="ámbar")
        fig.add_vline(x=rojo, line_dash="dash", annotation_text="rojo")
        g1.plotly_chart(fig, use_container_width=True)
        n = L.niveles(ev, ambar, rojo).value_counts().reindex(["Verde", "Ámbar", "Rojo"], fill_value=0).reset_index()
        n.columns = ["nivel", "evaluaciones"]
        fig2 = px.bar(n, x="nivel", y="evaluaciones", color="nivel", text="evaluaciones",
                      color_discrete_map={"Verde": "#2e8b57", "Ámbar": "#e08a00", "Rojo": "#c62828"}, title="Evaluaciones por nivel")
        fig2.update_layout(showlegend=False)
        g2.plotly_chart(fig2, use_container_width=True)
        st.write("**Medidas descriptivas por módulo**")
        st.dataframe(L.descriptivas_por_modulo(ev, rojo).round(2), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------- 3. análisis temporal
with tab3:
    st.subheader("Evolución de la infestación y variables ambientales")
    if ev.empty:
        st.warning("No hay evaluaciones con los filtros elegidos.")
    else:
        pf = L.por_fecha(ev)
        cl = clima[(clima["fecha"].dt.date >= ini) & (clima["fecha"].dt.date <= fin)]
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07, row_heights=[0.4, 0.3, 0.3],
                            subplot_titles=("Infestación media por fecha (% de hojas)", "Temperatura diaria (°C)", "Humedad relativa diaria (%)"))
        fig.add_trace(go.Scatter(x=pf["fecha"], y=pf["infestacion_media"], mode="lines+markers", name="Infestación media",
                                 marker=dict(size=7), hovertemplate="%{x|%d %b}: %{y:.1f} %"), row=1, col=1)
        fig.add_hline(y=ambar, line_dash="dot", row=1, col=1)
        fig.add_hline(y=rojo, line_dash="dot", row=1, col=1)
        if "temperatura_maxima_oc" in cl.columns and cl["temperatura_maxima_oc"].notna().any():
            fig.add_trace(go.Scatter(x=cl["fecha"], y=cl["temperatura_maxima_oc"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=2, col=1)
            fig.add_trace(go.Scatter(x=cl["fecha"], y=cl["temperatura_minima_oc"], mode="lines", line=dict(width=0), fill="tonexty",
                                     fillcolor="rgba(120,120,120,0.2)", name="Rango mín-máx", hoverinfo="skip"), row=2, col=1)
        fig.add_trace(go.Scatter(x=cl["fecha"], y=cl["temperatura_oc"], mode="lines", name="Temperatura media"), row=2, col=1)
        if "humedad_relativa_maxima" in cl.columns and cl["humedad_relativa_maxima"].notna().any():
            fig.add_trace(go.Scatter(x=cl["fecha"], y=cl["humedad_relativa_maxima"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=3, col=1)
            fig.add_trace(go.Scatter(x=cl["fecha"], y=cl["humedad_relativa_minima"], mode="lines", line=dict(width=0), fill="tonexty",
                                     fillcolor="rgba(120,120,120,0.2)", showlegend=False, hoverinfo="skip"), row=3, col=1)
        fig.add_trace(go.Scatter(x=cl["fecha"], y=cl["humedad_relativa"], mode="lines", name="Humedad media"), row=3, col=1)
        fig.update_layout(height=700, hovermode="x unified", margin=dict(t=60))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Las líneas punteadas del primer gráfico son los umbrales ámbar y rojo. La banda gris es el rango mínimo-máximo del día.")

        st.write("**Infestación media mensual por módulo**")
        m = ev.groupby(["mes", "modulo"])["hojas_inf_pct"].agg(["mean", "count"]).reset_index()
        m = m[m["count"] >= 5]
        m["modulo"] = "Módulo " + m["modulo"].astype(str)
        fig3 = px.line(m, x="mes", y="mean", color="modulo", markers=True, labels={"mean": "% medio de hojas infestadas", "mes": "Mes"},
                       hover_data={"count": True})
        fig3.update_xaxes(type="category", title_text="Mes")
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("Solo se dibujan combinaciones módulo-mes con al menos 5 evaluaciones.")

        st.subheader("Explicación del periodo elegido")
        for frase in L.resumen_periodo(ev_all if not unidades_sel and len(modulos_sel) == ev_all["modulo"].nunique() else ev, clima, ini, fin):
            st.write("• " + frase)
        st.info("Esto describe lo observado en el periodo. No demuestra que la temperatura cause la infestación. Tbase = 10.34 °C y K = 163.93 GDA vienen de la literatura y no están validados en campo.")

# ----------------------------------------------------------------------------- 4. consulta
with tab4:
    st.subheader("Consulta de evaluaciones")
    st.write(f"{len(ev):,} evaluaciones con los filtros actuales (periodo, módulo y unidad de monitoreo).")
    cols = ["fecha", "modulo", "valvula", "turno", "plantas_evaluadas", "hojas_inf_pct", "postura_pct", "temperatura_oc", "humedad_relativa", "gda_acum"]
    tabla = ev[cols].sort_values(["hojas_inf_pct", "fecha"], ascending=[False, False]).copy()
    tabla["nivel"] = L.niveles(tabla, ambar, rojo)
    tabla["fecha"] = tabla["fecha"].dt.strftime("%Y-%m-%d")
    st.dataframe(tabla.round(2), use_container_width=True, hide_index=True)
    st.download_button("Descargar esta consulta (CSV)", tabla.to_csv(index=False).encode("utf-8-sig"), file_name="consulta_aranita_roja.csv", mime="text/csv")

# ----------------------------------------------------------------------------- semáforo
with tab5:
    st.subheader("Semáforo de infestación por módulo")
    sf, v_ini, v_fin = L.semaforo_modulos(ev_all, corte, ventana, min_eval, ambar, rojo)
    st.write(f"Ventana: **{v_ini} a {v_fin}** ({ventana} días). Ámbar desde {ambar:.0f} %, Rojo desde {rojo:.0f} %, mínimo {min_eval} evaluaciones por módulo.")
    tarjetas = st.columns(len(sf))
    for col, (_, f) in zip(tarjetas, sf.iterrows()):
        col.markdown(f"**Módulo {f['modulo']}**")
        col.markdown(ICONO[f["estado"]])
        col.metric("Promedio", "—" if f["evaluaciones"] == 0 else f"{f['media_%']:.1f} %")
        col.caption(f"Máx. {'—' if f['evaluaciones'] == 0 else format(f['maximo_%'], '.1f') + ' %'} · {f['evaluaciones_en_rojo']} de {f['evaluaciones']} en Rojo")
        if f["observacion"]:
            col.warning("Revisar focos en Rojo")
    st.caption("“Datos insuficientes” significa que no hay base para opinar, no que el módulo esté sano. Si el promedio esconde evaluaciones en Rojo, se avisa.")
    detalle = sf.copy()
    detalle["estado"] = detalle["estado"].map(ICONO)
    st.dataframe(detalle.round(2), use_container_width=True, hide_index=True)

    st.write("**Evaluaciones para revisar primero** (Ámbar o Rojo dentro de la ventana)")
    rev = ev_all[(ev_all["fecha"].dt.date >= v_ini) & (ev_all["fecha"].dt.date <= v_fin) & (ev_all["hojas_inf_pct"] >= ambar)]
    rev = rev.sort_values(["hojas_inf_pct", "fecha"], ascending=[False, False]).head(15)[["evaluacion_id", "fecha", "modulo", "valvula", "turno", "hojas_inf_pct"]].copy()
    rev["fecha"] = rev["fecha"].dt.strftime("%Y-%m-%d")
    rev["nivel"] = L.niveles(rev, ambar, rojo)
    st.dataframe(rev, use_container_width=True, hide_index=True)

    with st.expander("¿De dónde salen los umbrales? (provisionales)"):
        ref = L.umbrales_de_referencia(ev_all)
        st.write(f"No existe un umbral numérico documentado en el fundo: el criterio actual es empírico. Como punto de partida usamos la propia distribución de 1,462 evaluaciones: "
                 f"el corte de {ambar:.0f} % deja a {100 - ref['pct_ge_10']:.0f} % de las evaluaciones por debajo (percentil ≈ 68 = {ref['p68']:.1f} %) y el de 30 % marca el 10 % más alto "
                 f"(percentil 90 = {ref['p90']:.1f} %). **Son provisionales y deben validarse con el Ing. Kiyoshi.** Por eso son configurables y la sensibilidad se discute en la sustentación.")
    with st.expander("Limitaciones"):
        st.write("- Un solo ciclo de 6 meses y 50 fechas de evaluación.\n- El módulo 1 tiene solo 9 evaluaciones: casi siempre sale “Datos insuficientes”.\n"
                 "- El grado-día acumulado crece con el calendario; su relación con la infestación fue débil (ρ = 0.25, p = 0.08).\n"
                 "- El semáforo describe lo observado; no predice la plaga ni demuestra causas.")
