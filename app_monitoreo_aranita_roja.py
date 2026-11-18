import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

# ==============================================================================
# I. IMPORTACIÓN DE LIBRERÍAS Y CONFIGURACIÓN DE PANTALLA
# ==============================================================================
st.set_page_config(
    page_title="Sistema de Monitoreo — Arañita Roja",
    page_icon="🥑",
    layout="wide"
)

# Encabezado principal del prototipo
st.title("🥑 SISTEMA DE ALERTA TEMPRANA Y MONITOREO FITOSANITARIO (GDA)")
st.caption("Fundo Loma Verde S.A.C. — Palto Hass (Barranca) | Módulo I - Proyecto Productivo IB")
st.markdown("---")

# ==============================================================================
# II. CARGA Y GESTIÓN DE DATOS EVALUADOS (GDA)
# ==============================================================================
@st.cache_data
def cargar_datos_evaluados():
    posibles_rutas = [
        'semana11_registros_evaluados.csv',
        '/content/drive/MyDrive/AGRODATA_IC_ARAÑITA_ROJA_PROYECTO_PRODUCTIVO_IB/Semana_13_Producto_Final/semana11_registros_evaluados.csv',
        '/content/drive/MyDrive/AGRODATA_IC_ARAÑITA_ROJA_PROYECTO_PRODUCTIVO_IB/Semana_11_Componente_Analitico_GDA/semana11_registros_evaluados.csv'
    ]
    for r in posibles_rutas:
        if os.path.exists(r):
            return pd.read_csv(r, parse_dates=['fecha'])

    for root, dirs, files in os.walk('.'):
        if 'semana11_registros_evaluados.csv' in files:
            return pd.read_csv(os.path.join(root, 'semana11_registros_evaluados.csv'), parse_dates=['fecha'])
    return None

df = cargar_datos_evaluados()

if df is None:
    st.error(" No se encontró 'semana11_registros_evaluados.csv'. Verifica haber ejecutado la copia del dataset a la carpeta S13.")
    st.stop()

# ==============================================================================
# III. PANEL LATERAL DE FILTROS DINÁMICOS (SIDEBAR)
# ==============================================================================
st.sidebar.header("⚙️ Filtros de Consulta Fitosanitaria")

# Filtro por Módulo de Riego
modulos_disponibles = sorted(df['modulo'].unique())
modulos_sel = st.sidebar.multiselect(
    "Seleccionar Módulo(s) de Riego:",
    options=modulos_disponibles,
    default=modulos_disponibles
)

# Filtro por Nivel de Semáforo (GDA)
estados_disponibles = sorted(df['estado_semaforo'].unique())
estados_sel = st.sidebar.multiselect(
    "Seleccionar Nivel de Semáforo:",
    options=estados_disponibles,
    default=estados_disponibles
)

# Filtro por Rango de Fechas
fecha_min = df['fecha'].min().date()
fecha_max = df['fecha'].max().date()
fechas_sel = st.sidebar.date_input(
    "Rango de Fechas de Evaluación:",
    value=(fecha_min, fecha_max),
    min_value=fecha_min,
    max_value=fecha_max
)

# Aplicar filtros al Dataframe
if isinstance(fechas_sel, (tuple, list)) and len(fechas_sel) == 2:
    f_inicio, f_fin = fechas_sel
    df_filtrado = df[
        (df['modulo'].isin(modulos_sel)) &
        (df['estado_semaforo'].isin(estados_sel)) &
        (df['fecha'].dt.date >= f_inicio) &
        (df['fecha'].dt.date <= f_fin)
    ]
else:
    df_filtrado = df[(df['modulo'].isin(modulos_sel)) & (df['estado_semaforo'].isin(estados_sel))]

# ==============================================================================
# IV. TARJETAS KPI (RESUMEN EJECUTIVO)
# ==============================================================================
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Evaluaciones", len(df_filtrado))
col2.metric("Infestación Promedio", f"{df_filtrado['aranita_hojas_infestadas'].mean():.2f} %" if len(df_filtrado)>0 else "0 %")
col3.metric("Temp. Promedio Aire", f"{df_filtrado['temperatura_oc'].mean():.2f} °C" if len(df_filtrado)>0 else "0 °C")
col4.metric("Alertas Críticas (Rojo)", len(df_filtrado[df_filtrado['estado_semaforo'] == 'ROJO']))

st.markdown("---")

# ==============================================================================
# V. TABLEROS DE CONTROL Y VISUALIZACIÓN GRÁFICA INTERACTIVA
# ==============================================================================
st.header("📊 Tableros de Control y Comportamiento Fitosanitario")

tab1, tab2, tab3 = st.tabs(["📌 Distribución por Módulo", "🌡️ Clima vs. Postura", "📈 Evolución Térmica (GDA)"])

with tab1:
    st.subheader("% de Hojas Infestadas por Módulo de Riego")
    fig1 = px.box(
        df_filtrado,
        x='modulo',
        y='aranita_hojas_infestadas',
        color='modulo',
        labels={'modulo': 'Módulo de Riego', 'aranita_hojas_infestadas': '% Hojas Infestadas'},
        title="Variabilidad del Daño Foliar por Módulo de Riego"
    )
    st.plotly_chart(fig1, use_container_width=True)

with tab2:
    st.subheader("Relación: Temperatura Máxima (°C) vs. Postura de Huevos")
    fig2 = px.scatter(
        df_filtrado,
        x='temperatura_maxima_oc',
        y='aranita_infestacion_postura',
        color='estado_semaforo',
        color_discrete_map={'ROJO': '#d32f2f', 'AMARILLO': '#fbc02d', 'VERDE': '#388e3c'},
        labels={'temperatura_maxima_oc': 'Temperatura Máxima (°C)', 'aranita_infestacion_postura': '% Postura de Huevos'},
        title="Impacto del Calor Extremo en la Ovipostura de Arañita Roja"
    )
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("Acumulado Térmico (GDA) vs. Infestación Foliar Promedio")
    df_mes = df_filtrado.groupby('mes').agg(
        gda=('grados_dia_acumulado_ano_oc', 'mean'),
        infestacion=('aranita_hojas_infestadas', 'mean')
    ).reset_index()

    fig3 = px.line(
        df_mes,
        x='mes',
        y=['gda', 'infestacion'],
        labels={'value': 'Valor Magnitud', 'variable': 'Indicador'},
        title="Tendencia Mensual de Acumulación Térmica e Infestación Foliar"
    )
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ==============================================================================
# VI. TABLA DINÁMICA DE INSPECCIÓN PRIORITARIA PARA CONTROL FITOSANITARIO
# ==============================================================================
st.header("🚨 Lista de Atención Prioritaria para Inspección y Control Fitosanitario")
st.caption("Filtrado automático de válvulas clasificadas en estado AMARILLO o ROJO ordenadas por severidad de infestación.")

df_prioridad = df_filtrado[df_filtrado['estado_semaforo'].isin(['AMARILLO', 'ROJO'])].sort_values(by='aranita_hojas_infestadas', ascending=False)

st.dataframe(
    df_prioridad[['fecha', 'modulo', 'valvula', 'aranita_hojas_infestadas', 'aranita_infestacion_postura', 'gda_diario_plaga', 'estado_semaforo']],
    use_container_width=True
)
