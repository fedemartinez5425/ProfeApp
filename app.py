import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="ProfeApp · Federico Martínez",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# CSS GLOBAL
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* Fuente y fondo general */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f2027, #203a43, #2c5364);
    color: white;
}
section[data-testid="stSidebar"] * { color: white !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2); }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: #f8f9fa;
    padding: 6px;
    border-radius: 12px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 500;
    color: #555;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #1a73e8 !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.12);
    font-weight: 600;
}

/* Métricas */
[data-testid="metric-container"] {
    background: white;
    border: 1px solid #e8eaed;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
[data-testid="metric-container"] label { color: #666 !important; font-size: 0.8rem !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700 !important; }

/* Cards custom */
.card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #e8eaed;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 12px;
}
.card-green  { border-left: 4px solid #34a853; }
.card-blue   { border-left: 4px solid #1a73e8; }
.card-orange { border-left: 4px solid #fbbc04; }
.card-red    { border-left: 4px solid #ea4335; }

/* Clase card en sidebar de registro */
.clase-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    border-left: 3px solid #1a73e8;
    font-size: 0.88rem;
    line-height: 1.6;
}

/* Botones */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

/* Headers de sección */
.section-header {
    font-size: 1.6rem;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 4px;
}
.section-sub {
    color: #888;
    font-size: 0.9rem;
    margin-bottom: 20px;
}

/* Alert de pendientes */
.alert-pending {
    background: #fff3e0;
    border: 1px solid #ffb300;
    border-radius: 10px;
    padding: 14px 18px;
    color: #e65100;
    font-weight: 500;
}

/* Formularios */
.stForm {
    background: white;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #e8eaed;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def parse_numeric(val):
    """Convierte valores con coma o punto decimal correctamente."""
    if pd.isna(val) or val == '':
        return 0.0
    s = str(val).strip()
    # Si tiene coma Y punto, el separador de miles es el primero
    if ',' in s and '.' in s:
        if s.index(',') < s.index('.'):
            s = s.replace(',', '')          # 1,234.56 → 1234.56
        else:
            s = s.replace('.', '').replace(',', '.')  # 1.234,56 → 1234.56
    elif ',' in s:
        s = s.replace(',', '.')            # 1,5 → 1.5
    try:
        return float(s)
    except ValueError:
        return 0.0

def format_currency(amount):
    try:
        amount = float(amount)
    except:
        amount = 0.0
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {formatted}"

def format_hours(h):
    try:
        h = float(h)
    except:
        h = 0.0
    return f"{h:.1f}h".replace(".", ",")

# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────
@st.cache_resource
def get_google_sheet():
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        spreadsheet_name = st.secrets["spreadsheet"]["name"]
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open(spreadsheet_name)
    except Exception as e:
        st.error(f"❌ Error al conectar con Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=30)
def load_data(_sheet, worksheet_name):
    try:
        ws = _sheet.worksheet(worksheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            df.columns = df.columns.str.strip()
            for col in ['Total', 'PrecioHora']:
                if col in df.columns:
                    df[col] = df[col].apply(parse_numeric)
            if 'Duración(h)' in df.columns:
                df['Duración(h)'] = df['Duración(h)'].apply(parse_numeric)
            for col in ['ID_Clase', 'ID_Alumno']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Error al cargar {worksheet_name}: {str(e)}")
        return pd.DataFrame()

def save_data(sheet, worksheet_name, df):
    try:
        ws = sheet.worksheet(worksheet_name)
        ws.clear()
        df_clean = df.fillna('').astype(str).replace('nan', '').replace('None', '')
        data = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        ws.update('A1', data)
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al guardar en {worksheet_name}: {str(e)}")
        return False

MATERIAS = ["Matemática", "Física", "Economía", "Estadística", "Matemática Financiera"]

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📚 ProfeApp")
    st.markdown("### Federico Luis Martínez")
    st.markdown("---")
    
    # Mini stats en sidebar
    sheet_sidebar = get_google_sheet()
    if sheet_sidebar:
        df_sb = load_data(sheet_sidebar, "Clases")
        if not df_sb.empty:
            df_sb['Fecha'] = pd.to_datetime(df_sb['Fecha'], errors='coerce')
            mes_now = datetime.now().month
            año_now = datetime.now().year
            df_mes_sb = df_sb[(df_sb['Fecha'].dt.month == mes_now) & (df_sb['Fecha'].dt.year == año_now)]
            
            st.markdown("**📅 Este mes**")
            st.markdown(f"💰 **{format_currency(df_mes_sb['Total'].sum())}**")
            st.markdown(f"📚 {len(df_mes_sb)} clases · {format_hours(df_mes_sb['Duración(h)'].sum())} dictadas")
            
            pendientes = df_sb[df_sb['¿Pagada?'] == 'No']['Total'].sum()
            if pendientes > 0:
                st.markdown("---")
                st.markdown(f"⚠️ **Pendiente de cobro:**")
                st.markdown(f"🔴 **{format_currency(pendientes)}**")
    
    st.markdown("---")
    st.markdown("**Materias:**")
    for m in MATERIAS:
        st.markdown(f"• {m}")
    st.markdown("**Niveles:** Secundaria · Universidad")
    st.markdown("---")
    st.caption("v2.0 · 2025")

# ─────────────────────────────────────────────
# CONEXIÓN PRINCIPAL
# ─────────────────────────────────────────────
sheet = get_google_sheet()

if not sheet:
    st.error("❌ No se pudo conectar con Google Sheets. Verifica Streamlit Secrets.")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard",
    "👨‍🎓 Alumnos",
    "📝 Registrar Clase",
    "💰 Historial",
    "📈 Análisis"
])

# ═══════════════════════════════════════════════
# TAB 1 · DASHBOARD
# ═══════════════════════════════════════════════
with tab1:
    st.markdown('<p class="section-header">📊 Panel de Control</p>', unsafe_allow_html=True)

    df_clases = load_data(sheet, "Clases")
    df_alumnos = load_data(sheet, "Alumnos")

    if df_clases.empty:
        st.info("No hay clases registradas aún. ¡Comenzá registrando tu primera clase!")
        st.stop()

    df_clases['Fecha'] = pd.to_datetime(df_clases['Fecha'], errors='coerce')

    meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    col1, col2 = st.columns([1, 1])
    with col1:
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1, key="dash_mes")
    with col2:
        año_sel = st.selectbox("Año", [2024, 2025, 2026], index=1, key="dash_año")

    mes_num = meses.index(mes_sel) + 1
    df_mes = df_clases[(df_clases['Fecha'].dt.month == mes_num) & (df_clases['Fecha'].dt.year == año_sel)]

    # ── KPIs ──
    ingresos_mes  = df_mes['Total'].sum()
    clases_mes    = len(df_mes)
    horas_mes     = df_mes['Duración(h)'].sum()
    promedio_hora = ingresos_mes / horas_mes if horas_mes > 0 else 0
    cobrado_mes   = df_mes[df_mes['¿Pagada?'] == 'Sí']['Total'].sum()
    pendiente_mes = df_mes[df_mes['¿Pagada?'] == 'No']['Total'].sum()

    # Mes anterior para delta
    mes_ant = mes_num - 1 if mes_num > 1 else 12
    año_ant = año_sel if mes_num > 1 else año_sel - 1
    df_ant  = df_clases[(df_clases['Fecha'].dt.month == mes_ant) & (df_clases['Fecha'].dt.year == año_ant)]
    ing_ant = df_ant['Total'].sum()
    delta_ing = ingresos_mes - ing_ant

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Ingresos del Mes", format_currency(ingresos_mes),
              delta=format_currency(delta_ing) if ing_ant > 0 else None,
              delta_color="normal")
    k2.metric("📚 Clases Dictadas", clases_mes)
    k3.metric("⏰ Horas Totales", format_hours(horas_mes))
    k4.metric("📊 $/hora promedio", format_currency(promedio_hora))

    st.markdown("")
    k5, k6 = st.columns(2)
    k5.metric("✅ Cobrado", format_currency(cobrado_mes))
    k6.metric("⏳ Pendiente de cobro", format_currency(pendiente_mes))

    if pendiente_mes > 0:
        st.markdown(f"""
        <div class="alert-pending">
            ⚠️ Tenés <b>{format_currency(pendiente_mes)}</b> pendientes de cobro este mes.
        </div>""", unsafe_allow_html=True)
        st.markdown("")

    st.markdown("---")

    # ── Gráficos ──
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 💵 Ingresos por Alumno")
        if not df_mes.empty:
            ing_alum = df_mes.groupby('Alumno')['Total'].sum().sort_values(ascending=True).reset_index()
            fig1 = px.bar(ing_alum, x='Total', y='Alumno', orientation='h',
                          color='Total', color_continuous_scale='Blues',
                          labels={'Total': 'Ingresos ($)', 'Alumno': ''})
            fig1.update_layout(showlegend=False, coloraxis_showscale=False,
                               plot_bgcolor='white', margin=dict(l=0, r=0, t=10, b=0),
                               height=280)
            fig1.update_traces(hovertemplate='%{y}<br>$ %{x:,.0f}')
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("Sin datos para este mes")

    with col2:
        st.markdown("#### 📚 Distribución por Materia")
        if not df_mes.empty:
            mat_data = df_mes.groupby('Materia').agg(
                Clases=('ID_Clase', 'count'),
                Ingresos=('Total', 'sum')
            ).reset_index()
            fig2 = px.pie(mat_data, values='Ingresos', names='Materia',
                          hole=0.5, color_discrete_sequence=px.colors.qualitative.Set2)
            fig2.update_traces(textposition='outside', textinfo='label+percent')
            fig2.update_layout(showlegend=False, margin=dict(l=20, r=20, t=10, b=10), height=280)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin datos para este mes")

    # ── Evolución mensual ──
    st.markdown("#### 📈 Evolución Mensual de Ingresos")
    df_clases['Mes_Period'] = df_clases['Fecha'].dt.to_period('M')
    evo = df_clases.groupby('Mes_Period').agg(
        Ingresos=('Total', 'sum'),
        Clases=('ID_Clase', 'count'),
        Horas=('Duración(h)', 'sum')
    ).reset_index()
    evo['Mes'] = evo['Mes_Period'].astype(str)

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=evo['Mes'], y=evo['Ingresos'],
        name='Ingresos', marker_color='#c2d8f5', opacity=0.7
    ))
    fig3.add_trace(go.Scatter(
        x=evo['Mes'], y=evo['Ingresos'],
        name='Tendencia', mode='lines+markers',
        line=dict(color='#1a73e8', width=3),
        marker=dict(size=8, color='#1a73e8')
    ))
    fig3.update_layout(
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(l=0, r=0, t=10, b=0), height=300,
        legend=dict(orientation='h', yanchor='bottom', y=1, xanchor='right', x=1),
        yaxis=dict(gridcolor='#f0f0f0'),
        xaxis=dict(gridcolor='#f0f0f0')
    )
    st.plotly_chart(fig3, use_container_width=True)

    # ── Horas por alumno (acumulado del mes) ──
    if not df_mes.empty:
        st.markdown("#### ⏰ Horas Dictadas por Alumno — " + mes_sel)
        horas_alum = df_mes.groupby('Alumno')['Duración(h)'].sum().reset_index()
        horas_alum.columns = ['Alumno', 'Horas']
        fig4 = px.bar(horas_alum, x='Alumno', y='Horas',
                      color='Alumno', color_discrete_sequence=px.colors.qualitative.Pastel,
                      labels={'Horas': 'Horas dictadas', 'Alumno': ''})
        fig4.update_layout(showlegend=False, plot_bgcolor='white',
                           margin=dict(l=0, r=0, t=10, b=0), height=250)
        st.plotly_chart(fig4, use_container_width=True)

# ═══════════════════════════════════════════════
# TAB 2 · ALUMNOS
# ═══════════════════════════════════════════════
with tab2:
    st.markdown('<p class="section-header">👨‍🎓 Gestión de Alumnos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Administrá tu cartera de alumnos</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        df_alum = load_data(sheet, "Alumnos")
        if not df_alum.empty:
            # Estadísticas rápidas por alumno
            df_cl_all = load_data(sheet, "Clases")
            if not df_cl_all.empty:
                resumen = df_cl_all.groupby('Alumno').agg(
                    Clases_Total=('ID_Clase', 'count'),
                    Horas_Total=('Duración(h)', 'sum'),
                    Facturado_Total=('Total', 'sum')
                ).reset_index()
                resumen.columns = ['Nombre', 'Clases', 'Horas', 'Facturado']
                df_alum_merged = df_alum.merge(resumen, on='Nombre', how='left')
                df_alum_merged['Facturado'] = df_alum_merged['Facturado'].fillna(0).apply(format_currency)
                df_alum_merged['Horas'] = df_alum_merged['Horas'].fillna(0).apply(format_hours)
                df_alum_merged['Clases'] = df_alum_merged['Clases'].fillna(0).astype(int)
                st.dataframe(df_alum_merged, use_container_width=True, height=420, hide_index=True)
            else:
                st.dataframe(df_alum, use_container_width=True, height=420, hide_index=True)
        else:
            st.info("No hay alumnos registrados aún →")

    with col2:
        st.markdown("#### ➕ Nuevo Alumno")
        with st.form("nuevo_alumno", clear_on_submit=True):
            nombre     = st.text_input("Nombre completo *")
            materia    = st.selectbox("Materia principal *", MATERIAS)
            curso      = st.selectbox("Nivel *", ["Secundaria", "Universidad"])
            telefono   = st.text_input("Teléfono")
            contacto   = st.text_input("Contacto / Responsable")
            precio_hora= st.number_input("Precio por hora ($) *", value=4000, step=500)
            modalidad  = st.selectbox("Modalidad *", ["Presencial", "Virtual", "Híbrida"])
            obs        = st.text_area("Observaciones", height=68)

            if st.form_submit_button("✅ Agregar Alumno", use_container_width=True):
                if not nombre.strip():
                    st.error("El nombre es obligatorio")
                else:
                    df_an = load_data(sheet, "Alumnos")
                    nid = int(df_an['ID_Alumno'].max()) + 1 if not df_an.empty else 1
                    nuevo = pd.DataFrame([{
                        'ID_Alumno': nid, 'Nombre': nombre.strip(), 'Materia': materia,
                        'Curso': curso, 'Teléfono': str(telefono) if telefono else '',
                        'Contacto': str(contacto) if contacto else '',
                        'Día': '', 'Frecuencia': '', 'PrecioHora': precio_hora,
                        'Modalidad': modalidad, 'FechaAlta': datetime.now().strftime('%Y-%m-%d'),
                        'Estado': 'Activo', 'Observaciones': str(obs) if obs else ''
                    }])
                    df_upd = pd.concat([df_an, nuevo], ignore_index=True)
                    if save_data(sheet, "Alumnos", df_upd):
                        st.success(f"✅ {nombre} agregado correctamente")
                        st.balloons()
                        st.rerun()

# ═══════════════════════════════════════════════
# TAB 3 · REGISTRAR CLASE
# ═══════════════════════════════════════════════
with tab3:
    st.markdown('<p class="section-header">📝 Registrar Nueva Clase</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Cargá los datos de tu clase de hoy</p>', unsafe_allow_html=True)

    df_activos = load_data(sheet, "Alumnos")
    if 'Estado' in df_activos.columns:
        df_activos = df_activos[df_activos['Estado'] == 'Activo']

    if df_activos.empty:
        st.warning("⚠️ No hay alumnos activos. Agregá uno en la pestaña 'Alumnos'.")
    else:
        col1, col2 = st.columns([1.5, 1])

        with col1:
            with st.form("nueva_clase", clear_on_submit=True):
                alumno_sel = st.selectbox("Alumno *", df_activos['Nombre'].tolist())
                ad = df_activos[df_activos['Nombre'] == alumno_sel].iloc[0]

                ca, cb = st.columns(2)
                with ca:
                    fecha = st.date_input("Fecha *", value=datetime.now())
                with cb:
                    mat_idx = MATERIAS.index(ad['Materia']) if ad['Materia'] in MATERIAS else 0
                    materia = st.selectbox("Materia *", MATERIAS, index=mat_idx)

                cc, cd = st.columns(2)
                with cc:
                    duracion = st.number_input("Duración (horas) *", min_value=0.5, max_value=8.0,
                                               value=1.5, step=0.5, format="%.1f")
                with cd:
                    precio_hora = st.number_input("Precio/hora ($) *", value=int(ad['PrecioHora']), step=500)

                ce, cf = st.columns(2)
                with ce:
                    pagada = st.selectbox("¿Pagada? *", ["Sí", "No"])
                with cf:
                    metodo = st.selectbox("Método", ["Transferencia", "Efectivo", "MercadoPago", "Otro"])

                total = round(duracion * precio_hora, 2)
                st.markdown(f"""
                <div class="card card-green" style="margin-top:8px;">
                    <span style="color:#555;font-size:0.85rem;">Total de la clase</span><br>
                    <span style="font-size:1.8rem;font-weight:700;color:#34a853;">{format_currency(total)}</span>
                    &nbsp;&nbsp;<span style="color:#888;font-size:0.85rem;">{format_hours(duracion)} × {format_currency(precio_hora)}/h</span>
                </div>
                """, unsafe_allow_html=True)

                if st.form_submit_button("✅ Registrar Clase", use_container_width=True):
                    df_cl = load_data(sheet, "Clases")
                    nid = int(df_cl['ID_Clase'].max()) + 1 if not df_cl.empty else 1
                    nueva = pd.DataFrame([{
                        'ID_Clase': nid,
                        'Fecha': fecha.strftime('%Y-%m-%d'),
                        'ID_Alumno': int(ad['ID_Alumno']),
                        'Alumno': alumno_sel,
                        'Materia': materia,
                        'Duración(h)': duracion,
                        'PrecioHora': precio_hora,
                        '¿Pagada?': pagada,
                        'Método': metodo,
                        'Total': total
                    }])
                    df_upd = pd.concat([df_cl, nueva], ignore_index=True)
                    if save_data(sheet, "Clases", df_upd):
                        st.success("✅ Clase registrada correctamente")
                        st.balloons()
                        st.rerun()

        with col2:
            st.markdown("#### 📋 Últimas 6 Clases")
            df_ult = load_data(sheet, "Clases")
            if not df_ult.empty:
                df_ult['Fecha'] = pd.to_datetime(df_ult['Fecha'], errors='coerce')
                for _, c in df_ult.sort_values('Fecha', ascending=False).head(6).iterrows():
                    fecha_str = c['Fecha'].strftime('%d/%m/%Y') if pd.notna(c['Fecha']) else '—'
                    icon = '✅' if c['¿Pagada?'] == 'Sí' else '⏳'
                    st.markdown(f"""
                    <div class="clase-card">
                        <b>{c['Alumno']}</b> · {c['Materia']}<br>
                        📅 {fecha_str} &nbsp; ⏰ {format_hours(c['Duración(h)'])}<br>
                        💰 {format_currency(c['Total'])} &nbsp; {icon} {c['¿Pagada?']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No hay clases aún")

# ═══════════════════════════════════════════════
# TAB 4 · HISTORIAL
# ═══════════════════════════════════════════════
with tab4:
    st.markdown('<p class="section-header">💰 Historial de Clases</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Buscá y filtrá todas tus clases</p>', unsafe_allow_html=True)

    df_hist = load_data(sheet, "Clases")

    if df_hist.empty:
        st.info("No hay clases registradas aún")
    else:
        df_hist['Fecha'] = pd.to_datetime(df_hist['Fecha'], errors='coerce')

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            f_alumno = st.multiselect("Alumno", sorted(df_hist['Alumno'].unique()))
        with col2:
            f_materia = st.multiselect("Materia", sorted(df_hist['Materia'].unique()))
        with col3:
            f_pago = st.selectbox("Estado de pago", ["Todas", "Pagadas", "Pendientes"])
        with col4:
            meses_disp = ['Todas'] + meses
            f_mes = st.selectbox("Mes", meses_disp)

        df_f = df_hist.copy()
        if f_alumno:  df_f = df_f[df_f['Alumno'].isin(f_alumno)]
        if f_materia: df_f = df_f[df_f['Materia'].isin(f_materia)]
        if f_pago == "Pagadas":   df_f = df_f[df_f['¿Pagada?'] == 'Sí']
        if f_pago == "Pendientes":df_f = df_f[df_f['¿Pagada?'] == 'No']
        if f_mes != 'Todas':
            df_f = df_f[df_f['Fecha'].dt.month == meses.index(f_mes) + 1]

        # Tabla
        df_disp = df_f.sort_values('Fecha', ascending=False).copy()
        df_disp['Fecha'] = df_disp['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_disp, use_container_width=True, height=380, hide_index=True)

        # Resumen
        st.markdown("---")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("📚 Clases",        len(df_f))
        r2.metric("💰 Facturado",     format_currency(df_f['Total'].sum()))
        r3.metric("✅ Cobrado",        format_currency(df_f[df_f['¿Pagada?']=='Sí']['Total'].sum()))
        r4.metric("⏳ Pendiente",      format_currency(df_f[df_f['¿Pagada?']=='No']['Total'].sum()))

# ═══════════════════════════════════════════════
# TAB 5 · ANÁLISIS
# ═══════════════════════════════════════════════
with tab5:
    st.markdown('<p class="section-header">📈 Análisis y Proyecciones</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Métricas avanzadas de tu actividad</p>', unsafe_allow_html=True)

    df_an = load_data(sheet, "Clases")
    df_al = load_data(sheet, "Alumnos")

    if df_an.empty:
        st.info("No hay suficientes datos. Comenzá registrando clases.")
    else:
        df_an['Fecha'] = pd.to_datetime(df_an['Fecha'], errors='coerce')
        df_an['Mes_Period'] = df_an['Fecha'].dt.to_period('M')

        # ── Bloque 1: rendimiento general ──
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🎯 Rendimiento por Alumno (acumulado)")
            ra = df_an.groupby('Alumno').agg(
                Clases=('ID_Clase', 'count'),
                Horas=('Duración(h)', 'sum'),
                Facturado=('Total', 'sum')
            ).reset_index().sort_values('Facturado', ascending=False)
            ra['Facturado_fmt'] = ra['Facturado'].apply(format_currency)
            ra['Horas_fmt']     = ra['Horas'].apply(format_hours)
            st.dataframe(
                ra[['Alumno', 'Clases', 'Horas_fmt', 'Facturado_fmt']].rename(
                    columns={'Horas_fmt': 'Horas', 'Facturado_fmt': 'Facturado'}
                ),
                use_container_width=True, hide_index=True
            )

        with col2:
            st.markdown("#### 📚 Rendimiento por Materia (acumulado)")
            rm = df_an.groupby('Materia').agg(
                Clases=('ID_Clase', 'count'),
                Horas=('Duración(h)', 'sum'),
                Facturado=('Total', 'sum')
            ).reset_index().sort_values('Facturado', ascending=False)
            rm['Facturado_fmt'] = rm['Facturado'].apply(format_currency)
            rm['Horas_fmt']     = rm['Horas'].apply(format_hours)
            st.dataframe(
                rm[['Materia', 'Clases', 'Horas_fmt', 'Facturado_fmt']].rename(
                    columns={'Horas_fmt': 'Horas', 'Facturado_fmt': 'Facturado'}
                ),
                use_container_width=True, hide_index=True
            )

        st.markdown("---")

        # ── Bloque 2: Ingreso mensual por alumno (stacked) ──
        st.markdown("#### 💹 Ingresos Mensuales por Alumno")
        pivot = df_an.groupby(['Mes_Period', 'Alumno'])['Total'].sum().reset_index()
        pivot['Mes'] = pivot['Mes_Period'].astype(str)
        fig_stack = px.bar(
            pivot, x='Mes', y='Total', color='Alumno',
            barmode='stack',
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={'Total': 'Ingresos ($)', 'Mes': 'Mes'}
        )
        fig_stack.update_layout(
            plot_bgcolor='white', height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation='h', yanchor='bottom', y=1, xanchor='right', x=1),
            yaxis=dict(gridcolor='#f0f0f0')
        )
        st.plotly_chart(fig_stack, use_container_width=True)

        # ── Bloque 3: Precio/hora promedio en el tiempo ──
        st.markdown("#### 💲 Evolución del Precio/Hora Promedio")
        ph_evo = df_an.groupby('Mes_Period').apply(
            lambda x: (x['Total'].sum() / x['Duración(h)'].sum()) if x['Duración(h)'].sum() > 0 else 0
        ).reset_index()
        ph_evo.columns = ['Mes_Period', 'Precio_Hora_Prom']
        ph_evo['Mes'] = ph_evo['Mes_Period'].astype(str)
        fig_ph = px.line(ph_evo, x='Mes', y='Precio_Hora_Prom', markers=True,
                         labels={'Precio_Hora_Prom': '$/hora promedio', 'Mes': 'Mes'})
        fig_ph.update_traces(line_color='#ea4335', marker=dict(size=9, color='#ea4335'))
        fig_ph.update_layout(plot_bgcolor='white', height=270,
                             margin=dict(l=0, r=0, t=10, b=0),
                             yaxis=dict(gridcolor='#f0f0f0'))
        st.plotly_chart(fig_ph, use_container_width=True)

        st.markdown("---")

        # ── Bloque 4: Proyección ──
        st.markdown("#### 💡 Proyección Mensual")
        total_alumnos = len(df_al[df_al['Estado'] == 'Activo']) if 'Estado' in df_al.columns else len(df_al)
        n_meses = max(df_an['Mes_Period'].nunique(), 1)
        ing_prom_mes = df_an.groupby('Mes_Period')['Total'].sum().mean()
        clases_prom  = len(df_an) / n_meses
        horas_prom   = df_an['Duración(h)'].sum() / n_meses

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("👨‍🎓 Alumnos Activos",       total_alumnos)
        p2.metric("📊 Clases promedio/mes",     f"{clases_prom:.0f}")
        p3.metric("⏰ Horas promedio/mes",       format_hours(horas_prom))
        p4.metric("💰 Ingreso proyectado/mes",  format_currency(ing_prom_mes))