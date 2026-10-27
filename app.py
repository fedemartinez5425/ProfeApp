import hmac
import time
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import sheets
from logica import (
    COLUMNAS_CLASES_NUEVAS, ESTADOS, MESES, METODOS,
    anios_disponibles, aplicar_nombres, clases_mismo_dia, columnas_faltantes,
    cambios_historial, filtrar_mes, format_currency, format_fecha, format_hours, format_pct,
    monto_sugerido, normalizar_alumnos, normalizar_clases, normalizar_tarifas, plan_aumento,
    precio_hora_por_mes, tabla_editable_clases, tarifa_vigente, ultima_tarifa_cargada,
    validar_cambios,
)

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
# LOGIN / SISTEMA CERRADO
# ─────────────────────────────────────────────
# Respaldo para no quedar afuera de producción mientras no exista el secret app_password.
PASSWORD_RESPALDO = "tu_contraseña_aqui"


def password_configurada():
    try:
        return st.secrets.get("app_password")
    except Exception:
        return None


PASSWORD_APP = password_configurada()
AVISO_PASSWORD = "🔴 Configurá app_password en Secrets (Streamlit Cloud → Settings → Secrets)."

if not st.session_state.get("autorizado", False):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown('<p class="section-header" style="text-align: center;">🔒 Acceso Restringido</p>', unsafe_allow_html=True)
        with st.form("login_form"):
            pwd = st.text_input("Contraseña de acceso", type="password")
            submit = st.form_submit_button("Ingresar", width="stretch")

            if submit:
                esperada = PASSWORD_APP or PASSWORD_RESPALDO
                if hmac.compare_digest(pwd.encode(), str(esperada).encode()):
                    st.session_state["autorizado"] = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
    st.stop()

MATERIAS = ["Matemática", "Física", "Economía", "Estadística", "Matemática Financiera"]

# ─────────────────────────────────────────────
# CONEXIÓN Y CARGA DE DATOS
# ─────────────────────────────────────────────
sheet = sheets.conectar()

if not sheet:
    st.error("❌ No se pudo conectar con Google Sheets. Verifica Streamlit Secrets.")
    st.stop()


def cargar_datos():
    """Lee las hojas y las normaliza. Funciona con el Sheet viejo y con el nuevo."""
    avisos = []
    raw_clases = sheets.leer(sheet, "Clases")
    raw_alumnos = sheets.leer(sheet, "Alumnos")
    raw_tarifas = sheets.leer(sheet, "Tarifas")

    if raw_clases is None:
        avisos.append("No existe la hoja **Clases**: se muestra todo vacío.")
        raw_clases = pd.DataFrame()
    elif not raw_clases.empty:
        faltan = columnas_faltantes(raw_clases, COLUMNAS_CLASES_NUEVAS)
        if faltan:
            avisos.append(f"La hoja **Clases** no tiene las columnas {', '.join(faltan)}: se usan "
                          "`Total` y `Duración(h)`. Importá el Excel corregido para agregarlas.")
    if raw_alumnos is None:
        avisos.append("No existe la hoja **Alumnos**.")
        raw_alumnos = pd.DataFrame()

    df_tarifas = None
    if raw_tarifas is None:
        avisos.append("No existe la hoja **Tarifas**: se usa el `PrecioHora` de cada ficha. Para crearla, "
                      "importá la hoja Tarifas del Excel corregido (Archivo → Importar → Subir → "
                      "*Insertar hojas nuevas*).")
    else:
        df_tarifas = normalizar_tarifas(raw_tarifas)

    df_alumnos = normalizar_alumnos(raw_alumnos)
    df_clases = aplicar_nombres(normalizar_clases(raw_clases), df_alumnos)
    return df_clases, df_alumnos, df_tarifas, avisos, list(raw_clases.columns)


df_clases, df_alumnos, df_tarifas, avisos, columnas_clases = cargar_datos()
hoy = date.today()


def nombre_alumno(id_alumno):
    fila = df_alumnos[df_alumnos['ID_Alumno'] == id_alumno]
    return fila.iloc[0]['Nombre'] if not fila.empty else f"Alumno #{id_alumno}"


def marcar(clave):
    st.session_state[clave] = True


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📚 ProfeApp")
    st.markdown("### Federico Luis Martínez")
    st.markdown("---")

    if not df_clases.empty:
        df_mes_sb = filtrar_mes(df_clases, hoy.month, hoy.year)
        st.markdown("**📅 Este mes**")
        st.markdown(f"💰 **{format_currency(df_mes_sb['Monto'].sum())}**")
        st.markdown(f"📚 {len(df_mes_sb)} clases · {format_hours(df_mes_sb['Horas'].sum())} dictadas")

        pendientes = df_clases[~df_clases['Pagada']]['Monto'].sum()
        if pendientes > 0:
            st.markdown("---")
            st.markdown("⚠️ **Pendiente de cobro:**")
            st.markdown(f"🔴 **{format_currency(pendientes)}**")

    st.markdown("---")
    st.markdown("**Materias:**")
    for m in MATERIAS:
        st.markdown(f"• {m}")
    st.markdown("**Niveles:** Secundaria · Universidad")
    st.markdown("---")
    st.caption("v2.1 · 2026")

if not PASSWORD_APP:
    st.error(AVISO_PASSWORD)
if avisos:
    with st.expander("⚠️ Avisos de la planilla", expanded=False):
        for a in avisos:
            st.markdown(f"- {a}")

tab1, tab2, tab3, tab4, tab_tarifas, tab5 = st.tabs([
    "📊 Dashboard",
    "👨‍🎓 Alumnos",
    "📝 Registrar Clase",
    "💰 Historial",
    "💲 Tarifas",
    "📈 Análisis"
])

# ═══════════════════════════════════════════════
# TAB 1 · DASHBOARD
# ═══════════════════════════════════════════════
with tab1:
    st.markdown('<p class="section-header">📊 Panel de Control</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        mes_sel = st.selectbox("Mes", MESES, index=hoy.month - 1, key="dash_mes")
    with col2:
        anios = anios_disponibles(df_clases, hoy)
        año_sel = st.selectbox("Año", anios, index=anios.index(hoy.year), key="dash_año")

    if df_clases.empty:
        st.info("No hay clases registradas aún. ¡Comenzá registrando tu primera clase!")
    else:
        mes_num = MESES.index(mes_sel) + 1
        df_mes = filtrar_mes(df_clases, mes_num, año_sel)

        # ── KPIs ──
        ingresos_mes  = df_mes['Monto'].sum()
        clases_mes    = len(df_mes)
        horas_mes     = df_mes['Horas'].sum()
        promedio_hora = ingresos_mes / horas_mes if horas_mes > 0 else 0
        cobrado_mes   = df_mes[df_mes['Pagada']]['Monto'].sum()
        pendiente_mes = df_mes[~df_mes['Pagada']]['Monto'].sum()

        # Mes anterior para delta
        mes_ant = mes_num - 1 if mes_num > 1 else 12
        año_ant = año_sel if mes_num > 1 else año_sel - 1
        ing_ant = filtrar_mes(df_clases, mes_ant, año_ant)['Monto'].sum()
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
                ing_alum = (df_mes.groupby('ID_Alumno', as_index=False)
                            .agg(Alumno=('Alumno', 'last'), Total=('Monto', 'sum'))
                            .sort_values('Total', ascending=True))
                fig1 = px.bar(ing_alum, x='Total', y='Alumno', orientation='h',
                              color='Total', color_continuous_scale='Blues',
                              labels={'Total': 'Ingresos ($)', 'Alumno': ''})
                fig1.update_layout(showlegend=False, coloraxis_showscale=False,
                                   plot_bgcolor='white', margin=dict(l=0, r=0, t=10, b=0),
                                   height=280)
                fig1.update_traces(hovertemplate='%{y}<br>$ %{x:,.0f}')
                st.plotly_chart(fig1, width="stretch")
            else:
                st.info("Sin datos para este mes")

        with col2:
            st.markdown("#### 📚 Distribución por Materia")
            if not df_mes.empty:
                mat_data = df_mes.groupby('Materia').agg(
                    Clases=('ID_Clase', 'count'),
                    Ingresos=('Monto', 'sum')
                ).reset_index()
                fig2 = px.pie(mat_data, values='Ingresos', names='Materia',
                              hole=0.5, color_discrete_sequence=px.colors.qualitative.Set2)
                fig2.update_traces(textposition='outside', textinfo='label+percent')
                fig2.update_layout(showlegend=False, margin=dict(l=20, r=20, t=10, b=10), height=280)
                st.plotly_chart(fig2, width="stretch")
            else:
                st.info("Sin datos para este mes")

        # ── Evolución mensual ──
        st.markdown("#### 📈 Evolución Mensual de Ingresos")
        evo = (df_clases.dropna(subset=['Fecha'])
               .assign(Mes=lambda d: d['Fecha'].dt.to_period('M').astype(str))
               .groupby('Mes', as_index=False)
               .agg(Ingresos=('Monto', 'sum'), Clases=('ID_Clase', 'count'), Horas=('Horas', 'sum')))

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
        st.plotly_chart(fig3, width="stretch")

        # ── Horas por alumno (acumulado del mes) ──
        if not df_mes.empty:
            st.markdown("#### ⏰ Horas Dictadas por Alumno — " + mes_sel)
            horas_alum = (df_mes.groupby('ID_Alumno', as_index=False)
                          .agg(Alumno=('Alumno', 'last'), Horas=('Horas', 'sum')))
            fig4 = px.bar(horas_alum, x='Alumno', y='Horas',
                          color='Alumno', color_discrete_sequence=px.colors.qualitative.Pastel,
                          labels={'Horas': 'Horas dictadas', 'Alumno': ''})
            fig4.update_layout(showlegend=False, plot_bgcolor='white',
                               margin=dict(l=0, r=0, t=10, b=0), height=250)
            st.plotly_chart(fig4, width="stretch")

# ═══════════════════════════════════════════════
# TAB 2 · ALUMNOS
# ═══════════════════════════════════════════════
with tab2:
    st.markdown('<p class="section-header">👨‍🎓 Gestión de Alumnos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Administrá tu cartera de alumnos</p>', unsafe_allow_html=True)

    if st.session_state.get("flash_alumno"):
        st.success(st.session_state.pop("flash_alumno"))

    col1, col2 = st.columns([2, 1])

    with col1:
        if not df_alumnos.empty:
            vista = df_alumnos.copy()
            if not df_clases.empty:
                resumen = df_clases.groupby('ID_Alumno', as_index=False).agg(
                    Clases=('ID_Clase', 'count'),
                    Horas=('Horas', 'sum'),
                    Facturado=('Monto', 'sum')
                )
                vista = vista.merge(resumen, on='ID_Alumno', how='left')
            else:
                vista[['Clases', 'Horas', 'Facturado']] = 0
            vista['Facturado'] = vista['Facturado'].fillna(0).apply(format_currency)
            vista['Horas'] = vista['Horas'].fillna(0).apply(format_hours)
            vista['Clases'] = vista['Clases'].fillna(0).astype(int)
            vista['PrecioHora'] = vista['PrecioHora'].apply(format_currency)
            st.dataframe(vista, width="stretch", height=420, hide_index=True)
        else:
            st.info("No hay alumnos registrados aún →")

        if not df_alumnos.empty:
            st.markdown("#### ✏️ Editar ficha")
            ids_ficha = df_alumnos.sort_values('Nombre')['ID_Alumno'].tolist()
            id_f = st.selectbox("Alumno", ids_ficha, format_func=nombre_alumno, key="ficha_alumno")
            af = df_alumnos[df_alumnos['ID_Alumno'] == id_f].iloc[0]
            with st.form(f"ficha_{id_f}"):
                c1, c2 = st.columns(2)
                with c1:
                    f_nombre = st.text_input("Nombre", value=af['Nombre'], key=f"ficha_nombre_{id_f}")
                    f_tel = st.text_input("Teléfono", value=af['Teléfono'], key=f"ficha_tel_{id_f}")
                with c2:
                    f_estado = st.selectbox("Estado", ESTADOS, key=f"ficha_estado_{id_f}",
                                            index=ESTADOS.index(af['Estado']) if af['Estado'] in ESTADOS else 0)
                    f_contacto = st.text_input("Contacto / Responsable", value=af['Contacto'],
                                               key=f"ficha_contacto_{id_f}")
                f_obs = st.text_area("Observaciones", value=af['Observaciones'], height=68, key=f"ficha_obs_{id_f}")

                if st.form_submit_button("💾 Guardar ficha", width="stretch"):
                    nuevos = {'Nombre': f_nombre.strip(), 'Teléfono': f_tel.strip(), 'Estado': f_estado,
                              'Contacto': f_contacto.strip(), 'Observaciones': f_obs.strip()}
                    cambios = {c: v for c, v in nuevos.items() if v != af[c]}
                    if not nuevos['Nombre']:
                        st.error("El nombre es obligatorio")
                    elif not cambios:
                        st.info("No hay cambios para guardar.")
                    else:
                        try:
                            ignoradas = sheets.actualizar(sheet, "Alumnos", id_f, cambios)
                        except Exception as e:
                            st.error(f"No se pudo guardar la ficha: {e}")
                        else:
                            guardadas = [c for c in cambios if c not in ignoradas]
                            msg = f"✅ Ficha de {nuevos['Nombre']} actualizada: {', '.join(guardadas) or 'nada'}"
                            if ignoradas:
                                msg += f" · ⚠️ El Sheet no tiene las columnas {', '.join(ignoradas)}: no se guardaron"
                            st.session_state["flash_alumno"] = msg
                            st.rerun()

    with col2:
        st.markdown("#### ➕ Nuevo Alumno")
        precio_def = ultima_tarifa_cargada(df_tarifas, df_alumnos)
        with st.form("nuevo_alumno", clear_on_submit=True):
            nombre     = st.text_input("Nombre completo *")
            materia    = st.selectbox("Materia principal *", MATERIAS)
            curso      = st.selectbox("Nivel *", ["Secundaria", "Universidad"])
            telefono   = st.text_input("Teléfono")
            contacto   = st.text_input("Contacto / Responsable")
            precio_hora= st.number_input("Precio por hora ($) *", min_value=0.0,
                                         value=float(precio_def), step=500.0, format="%.0f")
            modalidad  = st.selectbox("Modalidad *", ["Presencial", "Virtual", "Híbrida"])
            obs        = st.text_area("Observaciones", height=68)

            if st.form_submit_button("✅ Agregar Alumno", width="stretch"):
                if not nombre.strip():
                    st.error("El nombre es obligatorio")
                else:
                    alta = hoy.isoformat()
                    try:
                        nid, _ = sheets.agregar(sheet, "Alumnos", {
                            'Nombre': nombre.strip(), 'Materia': materia,
                            'Curso': curso, 'Teléfono': telefono.strip(),
                            'Contacto': contacto.strip(),
                            'Día': '', 'Frecuencia': '', 'PrecioHora': float(precio_hora),
                            'Modalidad': modalidad, 'FechaAlta': alta,
                            'Estado': 'Activo', 'Observaciones': obs.strip()
                        })
                    except Exception as e:
                        st.error(f"No se pudo guardar el alumno: {e}")
                    else:
                        mensaje = f"✅ {nombre.strip()} agregado correctamente (#{nid})"
                        if df_tarifas is not None:
                            try:
                                sheets.agregar(sheet, "Tarifas", {
                                    'ID_Alumno': nid, 'Desde': alta, 'Tipo': 'Hora',
                                    'Monto': float(precio_hora), 'Nota': 'alta'
                                })
                            except Exception as e:
                                mensaje += (f". ⚠️ No se pudo crear su tarifa ({e}); se usa el precio de la "
                                            "ficha. No lo vuelvas a agregar.")
                        st.session_state["flash_alumno"] = mensaje
                        st.rerun()

# ═══════════════════════════════════════════════
# TAB 3 · REGISTRAR CLASE
# ═══════════════════════════════════════════════
# Sin st.form: así el total se actualiza en vivo y cada widget tiene una key estable
# por alumno (el bug de v2 era que el precio tipeado se descartaba al cambiar de alumno).
with tab3:
    st.markdown('<p class="section-header">📝 Registrar Nueva Clase</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Cargá los datos de tu clase de hoy</p>', unsafe_allow_html=True)

    ss = st.session_state
    if ss.get("flash_clase"):
        st.success(ss.pop("flash_clase"))

    # Limpieza diferida de los campos del alumno recién guardado (antes de crear los widgets)
    reset_id = ss.pop("reg_reset", None)
    if reset_id is not None:
        for n in ["fecha", "horas", "tarifa", "tarifa_manual", "monto", "monto_manual", "dup_ok", "cero_ok"]:
            ss.pop(f"reg_{n}_{reset_id}", None)

    df_sel = df_alumnos[df_alumnos['Estado'] != 'Baja'].copy() if not df_alumnos.empty else df_alumnos
    if df_sel.empty:
        st.warning("⚠️ No hay alumnos activos. Agregá uno en la pestaña 'Alumnos'.")
    else:
        df_sel['_orden'] = (df_sel['Estado'] != 'Activo').astype(int)
        df_sel = df_sel.sort_values(['_orden', 'Nombre'])
        ids_sel = df_sel['ID_Alumno'].tolist()
        etiquetas = {r['ID_Alumno']: r['Nombre'] + ('' if r['Estado'] == 'Activo' else f" ({r['Estado'].lower()})")
                     for _, r in df_sel.iterrows()}
        if ss.get("reg_alumno") not in ids_sel:
            ss.pop("reg_alumno", None)

        col1, col2 = st.columns([1.5, 1])

        with col1:
            id_al = st.selectbox("Alumno *", ids_sel, format_func=lambda i: etiquetas[i], key="reg_alumno")
            ad = df_sel[df_sel['ID_Alumno'] == id_al].iloc[0]

            def k(nombre):
                return f"reg_{nombre}_{id_al}"

            ca, cb = st.columns(2)
            with ca:
                fecha = st.date_input("Fecha *", value=hoy, format="DD/MM/YYYY", key=k("fecha"))
            with cb:
                mat_idx = MATERIAS.index(ad['Materia']) if ad['Materia'] in MATERIAS else 0
                materia = st.selectbox("Materia *", MATERIAS, index=mat_idx, key=k("materia"))

            tarifa_v, tipo_v, origen_v = tarifa_vigente(id_al, fecha, df_tarifas, df_alumnos)
            clases_al = df_clases[df_clases['ID_Alumno'] == id_al] if not df_clases.empty else df_clases
            if k("horas") not in ss:
                ultimas = clases_al.sort_values(['Fecha', 'ID_Clase'])['Horas'] if not clases_al.empty else []
                ultima = float(ultimas.iloc[-1]) if len(ultimas) else 0.0
                ss[k("horas")] = min(max(ultima, 0.25), 12.0) if ultima > 0 else 1.5
            # Streamlit borra el valor de un widget que no se dibujó (al cambiar de alumno), pero no
            # los flags "manual": si el valor ya no está, se vuelve al cálculo automático.
            if not ss.get(k("tarifa_manual")) or k("tarifa") not in ss:
                ss[k("tarifa_manual")] = False
                ss[k("tarifa")] = float(tarifa_v)

            unidad = {'Hora': 'hora', 'Clase': 'clase', 'Mensual': 'mes'}.get(tipo_v, 'hora')
            cc, cd = st.columns(2)
            with cc:
                horas = st.number_input("Horas *", min_value=0.25, max_value=12.0, step=0.25,
                                        format="%.2f", key=k("horas"))
            with cd:
                tarifa = st.number_input(f"Tarifa ($/{unidad}) *", min_value=0.0, step=500.0,
                                         format="%.0f", key=k("tarifa"),
                                         on_change=marcar, args=(k("tarifa_manual"),))
            st.caption(f"Tarifa vigente al {format_fecha(fecha)}: {format_currency(tarifa_v)}/{unidad} "
                       f"(origen: {origen_v.lower()})")

            sugerido = monto_sugerido(horas, tarifa, tipo_v)
            if not ss.get(k("monto_manual")) or k("monto") not in ss:
                ss[k("monto_manual")] = False
                ss[k("monto")] = float(sugerido)
            monto = st.number_input("Monto cobrado ($) *", min_value=0.0, step=500.0, format="%.0f",
                                    key=k("monto"), on_change=marcar, args=(k("monto_manual"),),
                                    help="Se precarga con horas × tarifa. Si cobraste otra cosa, pisalo.")
            if ss.get(k("monto_manual")) or ss.get(k("tarifa_manual")):
                def _recalcular(claves=(k("monto_manual"), k("tarifa_manual"))):
                    for c in claves:
                        ss[c] = False
                st.button("↺ Volver a tarifa vigente y horas × tarifa", on_click=_recalcular, key=k("recalc"))

            ce, cf = st.columns(2)
            with ce:
                pagada = st.selectbox("¿Pagada? *", ["Sí", "No"], key=k("pagada"))
            with cf:
                metodo = st.selectbox("Método", METODOS, key=k("metodo"))

            por_hora = monto / horas if horas > 0 else 0
            detalle = f"{format_hours(horas)} · {format_currency(por_hora)}/h efectivo"
            if tipo_v == 'Mensual':
                detalle += " · tarifa mensual: cargá el monto que corresponda"
            st.markdown(f"""
            <div class="card card-green" style="margin-top:8px;">
                <span style="color:#555;font-size:0.85rem;">Monto cobrado</span><br>
                <span style="font-size:1.8rem;font-weight:700;color:#34a853;">{format_currency(monto)}</span>
                &nbsp;&nbsp;<span style="color:#888;font-size:0.85rem;">{detalle}</span>
            </div>
            """, unsafe_allow_html=True)

            dups = clases_mismo_dia(df_clases, id_al, fecha)
            confirmado = True
            if dups is not None and not dups.empty:
                lista = ", ".join(f"#{r['ID_Clase']} ({format_hours(r['Horas'])}, {format_currency(r['Monto'])})"
                                  for _, r in dups.iterrows())
                st.warning(f"⚠️ Ya hay {len(dups)} clase(s) de {ad['Nombre']} el {format_fecha(fecha)}: {lista}.")
                confirmado = st.checkbox("Es otra clase, guardar igual", key=k("dup_ok"))
            if monto <= 0:
                st.warning("⚠️ El monto cobrado es $ 0." + (" Con tarifa mensual, cargá el abono en la clase que "
                           "corresponda." if tipo_v == 'Mensual' else " Si de verdad no cobraste, confirmalo."))
                confirmado = st.checkbox("Guardar con monto $ 0", key=k("cero_ok")) and confirmado

            if st.button("✅ Registrar Clase", type="primary", width="stretch",
                         disabled=not confirmado, key="reg_guardar"):
                firma = (int(id_al), fecha.isoformat(), float(horas), float(monto))
                previo = ss.get("reg_ultimo_guardado")
                if previo and previo[0] == firma and time.time() - previo[1] < 30:
                    st.info("Esa clase ya se guardó recién (se ignoró el doble clic).")
                else:
                    ss["reg_ultimo_guardado"] = (firma, time.time())
                    try:
                        nid, _ = sheets.agregar(sheet, "Clases", {
                            'Fecha': fecha.isoformat(),
                            'ID_Alumno': int(id_al),
                            'Alumno': ad['Nombre'],
                            'Materia': materia,
                            'Duración(h)': float(horas),
                            'PrecioHora': float(tarifa),
                            '¿Pagada?': pagada,
                            'Método': metodo,
                            'Total': float(monto),
                            'MontoCobrado': float(monto),
                            'HorasReales': float(horas),
                            'Revisar': '',
                            'NotaRevision': '',
                        })
                    except Exception as e:
                        ss.pop("reg_ultimo_guardado", None)
                        st.error(f"No se pudo guardar la clase: {e}")
                    else:
                        ss["flash_clase"] = (f"✅ Clase #{nid} registrada: {ad['Nombre']}, {format_fecha(fecha)}, "
                                             f"{format_hours(horas)}, {format_currency(monto)}")
                        if ad['Estado'] == 'Pausado':
                            try:
                                sheets.actualizar(sheet, "Alumnos", id_al, {'Estado': 'Activo'})
                                ss["flash_clase"] += f" · {ad['Nombre']} volvió a Activo"
                            except Exception as e:
                                ss["flash_clase"] += f" · ⚠️ no se pudo pasar a Activo ({e})"
                        ss["reg_reset"] = id_al
                        st.rerun()

        with col2:
            st.markdown("#### 📋 Últimas 6 Clases")
            if not df_clases.empty:
                for _, c in df_clases.sort_values(['Fecha', 'ID_Clase'], ascending=False).head(6).iterrows():
                    icon = '✅' if c['Pagada'] else '⏳'
                    st.markdown(f"""
                    <div class="clase-card">
                        <b>{c['Alumno']}</b> · {c['Materia']}<br>
                        📅 {format_fecha(c['Fecha'])} &nbsp; ⏰ {format_hours(c['Horas'])}<br>
                        💰 {format_currency(c['Monto'])} &nbsp; {icon} {c['¿Pagada?']}
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

    if df_clases.empty:
        st.info("No hay clases registradas aún")
    else:
        if st.session_state.get("flash_hist"):
            st.success(st.session_state.pop("flash_hist"))

        vista_rapida = st.radio("Vista rápida", ["Todas", "Pagadas", "Pendientes de cobro", "A revisar"],
                                horizontal=True, key="hist_vista")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            ids_hist = sorted(df_clases['ID_Alumno'].unique().tolist(), key=lambda i: nombre_alumno(i).lower())
            f_alumno = st.multiselect("Alumno", ids_hist, format_func=nombre_alumno, key="hist_alumnos")
        with col2:
            f_materia = st.multiselect("Materia", sorted(df_clases['Materia'].unique()), key="hist_materias")
        with col3:
            f_mes = st.selectbox("Mes", ['Todos'] + MESES, key="hist_mes")
        with col4:
            anios_h = anios_disponibles(df_clases, hoy)
            f_anio = st.selectbox("Año", ['Todos'] + anios_h, index=1 + anios_h.index(hoy.year), key="hist_anio")

        df_f = df_clases.copy()
        if f_alumno:  df_f = df_f[df_f['ID_Alumno'].isin(f_alumno)]
        if f_materia: df_f = df_f[df_f['Materia'].isin(f_materia)]
        if vista_rapida == "Pagadas":             df_f = df_f[df_f['Pagada']]
        if vista_rapida == "Pendientes de cobro": df_f = df_f[~df_f['Pagada']]
        if vista_rapida == "A revisar":           df_f = df_f[df_f['ARevisar']]
        # Los filtros rápidos de pendientes y revisión miran todos los meses
        if vista_rapida in ("Todas", "Pagadas"):
            if f_anio != 'Todos':
                df_f = df_f[df_f['Fecha'].dt.year == f_anio]
            if f_mes != 'Todos':
                df_f = df_f[df_f['Fecha'].dt.month == MESES.index(f_mes) + 1]
        else:
            st.caption("Esta vista muestra todos los meses y años.")

        # Tabla editable: solo se escriben las celdas que cambian, fila por fila (por ID_Clase)
        df_f = df_f.sort_values(['Fecha', 'ID_Clase'], ascending=False)
        # Filas con ID vacío o repetido no se pueden editar ni borrar con seguridad: se muestran aparte
        id_malo = df_f['ID_Clase'].duplicated(keep=False) | (df_f['ID_Clase'] == 0)
        if id_malo.any():
            st.warning("⚠️ Estas filas del Sheet tienen `ID_Clase` vacío o repetido. No se pueden editar ni borrar "
                       "desde la app hasta que les pongas un ID único en el Sheet:")
            st.dataframe(df_f[id_malo][['ID_Clase', 'Fecha', 'Alumno', 'Horas', 'Monto']], hide_index=True)
        df_ed = df_f[~id_malo]
        original = tabla_editable_clases(df_ed)
        metodos = sorted(set(METODOS) | set(original['Método'].dropna()) - {''})
        version = st.session_state.get("hist_version", 0)
        # La key incluye las filas mostradas: si cambia el filtro, las ediciones sin guardar no saltan de fila
        firma_filas = abs(hash(tuple(sorted(original.index)))) % 10**8
        sin_revision = [c for c, col in (('Revisar', 'Revisar'), ('Nota', 'NotaRevision'))
                        if col not in columnas_clases]
        editado = st.data_editor(
            original, key=f"hist_editor_{version}_{firma_filas}", height=380, width="stretch",
            disabled=['Alumno', 'Materia', '$/h'] + sin_revision,
            column_config={
                'Fecha': st.column_config.DateColumn('Fecha', format='DD/MM/YYYY', required=True),
                'Horas': st.column_config.NumberColumn('Horas reales', min_value=0.25, step=0.25, format='%.2f'),
                'Monto': st.column_config.NumberColumn('Monto cobrado', min_value=0, step=500, format='localized'),
                '$/h': st.column_config.NumberColumn('$/h efectivo', format='localized'),
                'Pagada': st.column_config.CheckboxColumn('¿Pagada?'),
                'Método': st.column_config.SelectboxColumn('Método', options=metodos),
                'Revisar': st.column_config.CheckboxColumn('Revisar'),
                'Nota': st.column_config.TextColumn('Nota de revisión'),
            },
        )
        cambios = cambios_historial(original, editado, columnas_clases)
        if cambios:
            errores = validar_cambios(cambios)
            for e in errores:
                st.error(e)
            g1, g2 = st.columns([1, 1])
            if g1.button(f"💾 Guardar cambios ({len(cambios)} clase{'s' if len(cambios) > 1 else ''})",
                         type="primary", disabled=bool(errores), key="hist_guardar"):
                hechos, fallas = [], []
                for id_clase, c in cambios.items():
                    try:
                        sheets.actualizar(sheet, "Clases", id_clase, c)
                        hechos.append(id_clase)
                    except Exception as e:
                        fallas.append(f"#{id_clase}: {e}")
                msg = f"✅ Guardadas {len(hechos)} clase(s): " + ", ".join(f"#{i}" for i in hechos)
                if fallas:
                    # Sin cambiar la versión: las ediciones que fallaron siguen en pantalla para reintentar
                    msg += " · ⚠️ Fallaron: " + "; ".join(fallas)
                else:
                    st.session_state["hist_version"] = version + 1
                st.session_state["flash_hist"] = msg
                st.rerun()
            if g2.button("↺ Descartar cambios", key="hist_descartar"):
                st.session_state["hist_version"] = version + 1
                st.rerun()

        # Resumen
        st.markdown("---")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("📚 Clases",        len(df_f))
        r2.metric("💰 Facturado",     format_currency(df_f['Monto'].sum()))
        r3.metric("✅ Cobrado",        format_currency(df_f[df_f['Pagada']]['Monto'].sum()))
        r4.metric("⏳ Pendiente",      format_currency(df_f[~df_f['Pagada']]['Monto'].sum()))

        # Borrado de una clase, con confirmación
        with st.expander("🗑️ Borrar una clase"):
            ids_borrar = df_ed['ID_Clase'].tolist()
            if st.session_state.get("hist_borrar_id") not in ids_borrar:
                st.session_state.pop("hist_borrar_id", None)
            if not ids_borrar:
                st.info("No hay clases en el filtro actual.")
            else:
                filas_b = df_ed.set_index('ID_Clase')
                id_b = st.selectbox(
                    "Clase", ids_borrar, key="hist_borrar_id",
                    format_func=lambda i: (f"#{i} · {format_fecha(filas_b.loc[i, 'Fecha'])} · "
                                           f"{filas_b.loc[i, 'Alumno']} · {format_hours(filas_b.loc[i, 'Horas'])} · "
                                           f"{format_currency(filas_b.loc[i, 'Monto'])}"))
                ok_b = st.checkbox(f"Sí, borrar la clase #{id_b} del Sheet (no se puede deshacer)",
                                   key=f"hist_borrar_ok_{id_b}")
                if st.button("🗑️ Borrar", disabled=not ok_b, key="hist_borrar"):
                    try:
                        sheets.borrar(sheet, "Clases", id_b)
                    except Exception as e:
                        st.error(f"No se pudo borrar: {e}")
                    else:
                        st.session_state["hist_version"] = version + 1
                        st.session_state["flash_hist"] = f"🗑️ Clase #{id_b} borrada"
                        st.rerun()

# ═══════════════════════════════════════════════
# TAB · TARIFAS
# ═══════════════════════════════════════════════
with tab_tarifas:
    st.markdown('<p class="section-header">💲 Tarifas y aumentos</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Historial de precios por alumno y aumentos</p>', unsafe_allow_html=True)

    if st.session_state.get("flash_tarifas"):
        st.success(st.session_state.pop("flash_tarifas"))
    if df_tarifas is None:
        st.warning("No existe la hoja **Tarifas**: los aumentos solo actualizan el `PrecioHora` de la ficha y no "
                   "queda historial. Para crearla, importá la hoja Tarifas del Excel corregido.")

    if df_alumnos.empty:
        st.info("No hay alumnos registrados aún.")
    else:
        ids_tar = df_alumnos[df_alumnos['Estado'] != 'Baja'].sort_values('Nombre')['ID_Alumno'].tolist()
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("#### 📜 Historial por alumno")
            id_t = st.selectbox("Alumno", df_alumnos.sort_values('Nombre')['ID_Alumno'].tolist(),
                                format_func=nombre_alumno, key="tar_alumno")
            vig, tipo_vig, origen_vig = tarifa_vigente(id_t, hoy, df_tarifas, df_alumnos)
            st.metric(f"Tarifa vigente hoy (origen: {origen_vig.lower()})",
                      f"{format_currency(vig)} / {tipo_vig.lower()}")
            if df_tarifas is not None:
                h = df_tarifas[df_tarifas['ID_Alumno'] == id_t].sort_values(['Desde', 'ID_Tarifa'], ascending=False)
                if h.empty:
                    st.info("Sin tarifas cargadas: se usa el precio de la ficha.")
                else:
                    st.dataframe(pd.DataFrame({
                        'Desde': h['Desde'].apply(format_fecha),
                        'Tipo': h['Tipo'],
                        'Monto': h['Monto'].apply(format_currency),
                        'Nota': h['Nota'],
                    }), width="stretch", hide_index=True)

        with col2:
            st.markdown("#### 📈 Aplicar aumento")
            alcance = st.radio("A quién", ["Todos los activos", "Elegir alumnos"], horizontal=True, key="aum_alcance")
            if alcance == "Elegir alumnos":
                ids_aum = st.multiselect("Alumnos", ids_tar, format_func=nombre_alumno, key="aum_alumnos")
            else:
                ids_aum = df_alumnos[df_alumnos['Estado'] == 'Activo']['ID_Alumno'].tolist()
            modo = st.radio("Cómo", ["Porcentaje", "Monto nuevo"], horizontal=True, key="aum_modo")
            if modo == "Porcentaje":
                valor = st.number_input("Aumento (%)", min_value=-50.0, max_value=500.0, value=10.0, step=1.0,
                                        key="aum_pct")
                redondear = st.checkbox("Redondear a $ 100", value=True, key="aum_redondear")
            else:
                valor = st.number_input("Monto nuevo ($)", min_value=0.0, step=500.0, format="%.0f", key="aum_monto",
                                        value=float(ultima_tarifa_cargada(df_tarifas, df_alumnos)))
                redondear = False
            desde = st.date_input("Desde", value=hoy, format="DD/MM/YYYY", key="aum_desde")
            nota = st.text_input("Nota", value="aumento", key="aum_nota")

            plan = plan_aumento(ids_aum, 'pct' if modo == "Porcentaje" else 'monto', valor, desde,
                                df_tarifas, df_alumnos, 100 if redondear else 0)
            if plan.empty:
                st.info("Elegí al menos un alumno.")
            else:
                st.dataframe(pd.DataFrame({
                    'Alumno': plan['Alumno'],
                    'Actual': plan['Actual'].apply(format_currency),
                    'Nuevo': plan['Nuevo'].apply(format_currency),
                    'Variación': plan['Variación %'].apply(lambda v: format_pct(v) if pd.notna(v) else '—'),
                    'Tipo': plan['Tipo'],
                }), width="stretch", hide_index=True)
                if desde > hoy:
                    st.caption("Empieza a regir en el futuro: hasta esa fecha se sigue usando la tarifa actual, y el "
                               "`PrecioHora` de la ficha no se toca.")
                sin_donde_guardar = df_tarifas is None and desde > hoy
                if sin_donde_guardar:
                    st.error("Sin hoja Tarifas no se puede programar un aumento a futuro: elegí una fecha de hoy "
                             "o anterior, o creá la hoja Tarifas.")
                version_aum = st.session_state.get("aum_version", 0)
                ok_aum = st.checkbox(f"Confirmo el aumento para {len(plan)} alumno(s) desde {format_fecha(desde)}",
                                     key=f"aum_ok_{version_aum}")
                if st.button("✅ Aplicar aumento", type="primary", disabled=not ok_aum or sin_donde_guardar,
                             key="aum_aplicar"):
                    firma = (tuple(plan['ID_Alumno']), tuple(plan['Nuevo']), desde.isoformat())
                    previo = st.session_state.get("aum_ultimo")
                    if previo and previo[0] == firma and time.time() - previo[1] < 30:
                        st.info("Ese aumento ya se aplicó recién (se ignoró el doble clic).")
                    else:
                        hechos, fallas, avisos_aum = [], [], []
                        for _, r in plan.iterrows():
                            if df_tarifas is not None:
                                try:
                                    sheets.agregar(sheet, "Tarifas", {
                                        'ID_Alumno': int(r['ID_Alumno']), 'Desde': desde.isoformat(),
                                        'Tipo': r['Tipo'], 'Monto': float(r['Nuevo']), 'Nota': nota.strip(),
                                    })
                                except Exception as e:
                                    fallas.append(f"{r['Alumno']}: no se creó la tarifa ({e})")
                                    continue
                            # PrecioHora es precio por hora: no se pisa con una cuota por clase o mensual
                            if desde <= hoy and r['Tipo'] == 'Hora':
                                try:
                                    sheets.actualizar(sheet, "Alumnos", int(r['ID_Alumno']),
                                                      {'PrecioHora': float(r['Nuevo'])})
                                except Exception as e:
                                    avisos_aum.append(f"{r['Alumno']}: tarifa creada pero no se actualizó la "
                                                      f"ficha ({e}); no lo vuelvas a aplicar")
                            hechos.append(r['Alumno'])
                        if hechos:
                            st.session_state["aum_ultimo"] = (firma, time.time())
                        st.session_state["aum_version"] = version_aum + 1
                        msg = f"✅ Aumento aplicado a {len(hechos)} alumno(s): {', '.join(hechos)}"
                        if avisos_aum:
                            msg += " · ⚠️ " + "; ".join(avisos_aum)
                        if fallas:
                            msg += " · ⚠️ Fallaron: " + "; ".join(fallas)
                        st.session_state["flash_tarifas"] = msg
                        st.rerun()

# ═══════════════════════════════════════════════
# TAB 5 · ANÁLISIS
# ═══════════════════════════════════════════════
with tab5:
    st.markdown('<p class="section-header">📈 Análisis y Proyecciones</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Métricas avanzadas de tu actividad</p>', unsafe_allow_html=True)

    df_an = df_clases.dropna(subset=['Fecha']) if not df_clases.empty else df_clases

    if df_an.empty:
        st.info("No hay suficientes datos. Comenzá registrando clases.")
    else:
        df_an = df_an.assign(Mes=df_an['Fecha'].dt.to_period('M').astype(str))

        # ── Bloque 1: rendimiento general ──
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 🎯 Rendimiento por Alumno (acumulado)")
            ra = df_an.groupby('ID_Alumno', as_index=False).agg(
                Alumno=('Alumno', 'last'),
                Clases=('ID_Clase', 'count'),
                Horas=('Horas', 'sum'),
                Facturado=('Monto', 'sum')
            ).sort_values('Facturado', ascending=False)
            ra['Facturado_fmt'] = ra['Facturado'].apply(format_currency)
            ra['Horas_fmt']     = ra['Horas'].apply(format_hours)
            st.dataframe(
                ra[['Alumno', 'Clases', 'Horas_fmt', 'Facturado_fmt']].rename(
                    columns={'Horas_fmt': 'Horas', 'Facturado_fmt': 'Facturado'}
                ),
                width="stretch", hide_index=True
            )

        with col2:
            st.markdown("#### 📚 Rendimiento por Materia (acumulado)")
            rm = df_an.groupby('Materia', as_index=False).agg(
                Clases=('ID_Clase', 'count'),
                Horas=('Horas', 'sum'),
                Facturado=('Monto', 'sum')
            ).sort_values('Facturado', ascending=False)
            rm['Facturado_fmt'] = rm['Facturado'].apply(format_currency)
            rm['Horas_fmt']     = rm['Horas'].apply(format_hours)
            st.dataframe(
                rm[['Materia', 'Clases', 'Horas_fmt', 'Facturado_fmt']].rename(
                    columns={'Horas_fmt': 'Horas', 'Facturado_fmt': 'Facturado'}
                ),
                width="stretch", hide_index=True
            )

        st.markdown("---")

        # ── Bloque 2: Ingreso mensual por alumno (stacked) ──
        st.markdown("#### 💹 Ingresos Mensuales por Alumno")
        pivot = (df_an.groupby(['Mes', 'ID_Alumno'], as_index=False)
                 .agg(Alumno=('Alumno', 'last'), Monto=('Monto', 'sum')))
        fig_stack = px.bar(
            pivot, x='Mes', y='Monto', color='Alumno',
            barmode='stack',
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={'Monto': 'Ingresos ($)', 'Mes': 'Mes'}
        )
        fig_stack.update_layout(
            plot_bgcolor='white', height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation='h', yanchor='bottom', y=1, xanchor='right', x=1),
            yaxis=dict(gridcolor='#f0f0f0')
        )
        st.plotly_chart(fig_stack, width="stretch")

        # ── Bloque 3: Precio/hora promedio en el tiempo ──
        st.markdown("#### 💲 Evolución del Precio/Hora Promedio")
        ph_evo = precio_hora_por_mes(df_an)
        fig_ph = px.line(ph_evo, x='Mes', y='PorHora', markers=True,
                         labels={'PorHora': '$/hora promedio', 'Mes': 'Mes'})
        fig_ph.update_traces(line_color='#ea4335', marker=dict(size=9, color='#ea4335'))
        fig_ph.update_layout(plot_bgcolor='white', height=270,
                             margin=dict(l=0, r=0, t=10, b=0),
                             yaxis=dict(gridcolor='#f0f0f0'))
        st.plotly_chart(fig_ph, width="stretch")

        st.markdown("---")

        # ── Bloque 4: Proyección ──
        st.markdown("#### 💡 Proyección Mensual")
        total_alumnos = int((df_alumnos['Estado'] == 'Activo').sum()) if not df_alumnos.empty else 0
        n_meses = max(df_an['Mes'].nunique(), 1)
        ing_prom_mes = df_an.groupby('Mes')['Monto'].sum().mean()
        clases_prom  = len(df_an) / n_meses
        horas_prom   = df_an['Horas'].sum() / n_meses

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("👨‍🎓 Alumnos Activos",       total_alumnos)
        p2.metric("📊 Clases promedio/mes",     f"{clases_prom:.0f}")
        p3.metric("⏰ Horas promedio/mes",       format_hours(horas_prom))
        p4.metric("💰 Ingreso proyectado/mes",  format_currency(ing_prom_mes))
