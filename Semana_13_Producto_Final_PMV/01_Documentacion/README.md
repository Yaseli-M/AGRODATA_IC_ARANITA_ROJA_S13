# Monitoreo de arañita roja (*Oligonychus punicae*) en palto Hass
Fundo Loma Verde S.A.C. (Supe, Barranca) · Proyecto Productivo IB · Equipo AgroData IC (sección B)

**Decisión que apoya:** priorizar qué módulos revisar o intervenir según la infestación observada en campo (% de hojas infestadas por evaluación).
**Alcance del módulo I:** descriptivo y funcional. No predice. El machine learning queda como extensión del módulo 3.

## Arquitectura
SQLite (`02_Datos/aranita_roja_bd_v1.sqlite`) → Pandas (`04_Producto_Final/logica.py`) → Plotly → Streamlit (`04_Producto_Final/app.py`)

## Cómo ejecutarlo
```bash
cd Proyecto_AgroDataIC/04_Producto_Final
pip install -r requirements.txt
streamlit run app.py
# si el puerto está ocupado:  streamlit run app.py --server.port 8505
```
- Hay que ejecutarlo **desde la carpeta `04_Producto_Final`**: la app busca la base en `../02_Datos/`.
- Si Streamlit pide un correo, pulsa Enter.
- También acepta otra base `.sqlite` o el CSV analítico (`aranita_roja_analitico_v1.csv`) desde la barra lateral.

## Qué muestra (secciones que pidió la docente)
1. **Carga de registros:** calidad de los datos (qué entra y qué se excluye, y por qué).
2. **Indicadores:** media, mediana, % de evaluaciones en ámbar/rojo, distribución, medidas por módulo.
3. **Análisis temporal:** infestación por fecha frente a temperatura y humedad; comparación por módulo y mes; explicación en texto del periodo.
4. **Consulta:** filtros por periodo, módulo y unidad (módulo-válvula) con descarga en CSV.
5. **Semáforo por módulo:** regla if/else configurable (ámbar ≥ 10 %, rojo ≥ 30 %, ventana de 14 días, mínimo 5 evaluaciones).

## Datos
- 1,494 evaluaciones en la base; 1,462 aceptadas y 32 observadas (30 duplicados lógicos corregidos + 2 atípicos de postura). Las observadas se conservan para trazabilidad y no entran al análisis.
- 50 fechas de evaluación (2026-03-02 a 2026-08-28); clima diario de 183 días (2026-03-01 a 2026-08-30).
- Una válvula se identifica por **módulo + válvula**: el mismo número se repite en varios módulos.

## Limitaciones (decirlas antes de que las pregunten)
- Un solo ciclo de 6 meses.
- Umbrales 10 % / 30 % **provisionales** (≈ percentiles 68 y 90 de la distribución propia); falta validarlos con el Ing. Kiyoshi.
- Tbase = 10.34 °C y K = 163.93 GDA vienen de la literatura, sin validar en campo. El grado-día es solo contexto y no activa el semáforo.
- Relación GDA–infestación débil (Spearman ρ = 0.25, p = 0.08, n = 50 fechas). No se afirma causalidad.
- El módulo 1 tiene solo 9 evaluaciones; casi siempre sale "Datos insuficientes".
- El clima termina el 30 de agosto.

## Pruebas
`05_Pruebas_Validacion/test_logica.py` (lógica con la base real) y `smoke_app.py` (ejecuta la app con Streamlit/Plotly simulados).
```bash
cd 05_Pruebas_Validacion && python3 test_logica.py && python3 smoke_app.py
```
