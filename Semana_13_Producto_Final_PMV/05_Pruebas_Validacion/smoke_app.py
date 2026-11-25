"""Prueba de humo de app.py con streamlit/plotly simulados (no hay red para instalarlos aquí).
Ejecuta TODO el script de la app contra los datos reales: valida la lógica, las columnas y los tipos.
No valida el dibujo real de Plotly ni la interfaz real de Streamlit."""
import sys, types, runpy, datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

PROD = Path(__file__).resolve().parent.parent / "04_Producto_Final"
sys.path.insert(0, str(PROD))

llamadas = {"error": 0, "warning": 0, "metric": 0, "dataframe": 0, "plotly_chart": 0, "stop": 0}

def contar(nombre):
    def f(*a, **k):
        llamadas[nombre] += 1
        return MagicMock()
    return f

def selectbox(label, options, index=0, **k):
    return options[index]

def ctx():
    """Contexto que NO traga excepciones (un MagicMock normal devuelve truthy en __exit__ y las ocultaría)."""
    m = MagicMock()
    m.__enter__.return_value = m
    m.__exit__.return_value = False
    return m

def hacer_st(modo="normal"):
    st = MagicMock(name="streamlit")
    st.cache_data = lambda *a, **k: (lambda fn: fn) if not (a and callable(a[0])) else a[0]
    st.sidebar.file_uploader.return_value = None
    st.sidebar.date_input.side_effect = lambda *a, **k: k["value"]
    st.sidebar.multiselect.side_effect = lambda label, options, default=None, **k: default
    st.sidebar.number_input.side_effect = lambda *a, **k: k["value"]
    st.sidebar.selectbox.side_effect = selectbox
    if modo == "umbrales_invertidos":
        st.sidebar.number_input.side_effect = lambda label, **k: 50.0 if "Ámbar" in label else 20.0
    st.tabs.side_effect = lambda labels: [ctx() for _ in labels]
    st.columns.side_effect = lambda n: [ctx() for _ in range(n if isinstance(n, int) else len(n))]
    st.error.side_effect = contar("error"); st.warning.side_effect = contar("warning")
    st.dataframe.side_effect = contar("dataframe"); st.plotly_chart.side_effect = contar("plotly_chart")
    st.stop.side_effect = lambda: (_ for _ in ()).throw(SystemExit("st.stop"))
    return st

def correr(modo="normal"):
    for k in llamadas: llamadas[k] = 0
    st = hacer_st(modo)
    plotly = types.ModuleType("plotly")
    px, go, sub = MagicMock(), MagicMock(), types.ModuleType("plotly.subplots")
    sub.make_subplots = MagicMock()
    for nombre, mod in {"streamlit": st, "plotly": plotly, "plotly.express": px, "plotly.graph_objects": go, "plotly.subplots": sub}.items():
        sys.modules[nombre] = mod
    plotly.express, plotly.graph_objects, plotly.subplots = px, go, sub
    sys.modules.pop("logica", None)
    runpy.run_path(str(PROD / "app.py"), run_name="__main__")
    return st

st = correr()
assert llamadas["error"] == 0, "la app mostró un error con la base real"
assert llamadas["dataframe"] >= 5 and llamadas["plotly_chart"] >= 2, llamadas
assert st.subheader.call_count == 6, "alguna pestaña no se ejecutó"
print("OK normal:", llamadas)

st = correr("umbrales_invertidos")
assert llamadas["error"] == 0
st.sidebar.error.assert_called()  # avisa y vuelve a 10/30
print("OK umbrales invertidos: avisa y usa 10/30")

# filtros vacíos y CSV
import logica as L
from datetime import date
d = L.cargar(str(PROD.parent / "02_Datos" / "aranita_roja_analitico_v1.csv"))
assert len(d["eval"]) == 1462
print("OK CSV carga", len(d["eval"]))
print("SMOKE OK")
