import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Gestión - Profesor Particular",
    page_icon="📚",
    layout="wide"
)

# Función para conectar con Google Sheets
@st.cache_resource
def get_google_sheet():
    try:
        # Obtener credenciales desde secrets
        credentials_dict = dict(st.secrets["gcp_service_account"])
        spreadsheet_name = st.secrets["spreadsheet"]["name"]
        
        # Configurar scopes
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Crear credenciales
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=scopes
        )
        
        # Autorizar cliente
        client = gspread.authorize(credentials)
        
        # Abrir spreadsheet
        sheet = client.open(spreadsheet_name)
        
        return sheet
    except Exception as e:
        st.error(f"❌ Error al conectar con Google Sheets: {str(e)}")
        st.info("Verifica tu configuración en Streamlit Secrets")
        return None

# Función para cargar datos desde Google Sheets
@st.cache_data(ttl=30)
def load_data(_sheet, worksheet_name):
    try:
        worksheet = _sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Validar y limpiar columnas
        if not df.empty:
            # Limpiar nombres de columnas
            df.columns = df.columns.str.strip()
            
            # Convertir valores numéricos si es necesario
            if 'Total' in df.columns:
                df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
            if 'PrecioHora' in df.columns:
                df['PrecioHora'] = pd.to_numeric(df['PrecioHora'], errors='coerce').fillna(0)
            if 'Duración(h)' in df.columns:
                df['Duración(h)'] = pd.to_numeric(df['Duración(h)'], errors='coerce').fillna(0)
            if 'ID_Clase' in df.columns:
                df['ID_Clase'] = pd.to_numeric(df['ID_Clase'], errors='coerce').fillna(0).astype(int)
            if 'ID_Alumno' in df.columns:
                df['ID_Alumno'] = pd.to_numeric(df['ID_Alumno'], errors='coerce').fillna(0).astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error al cargar {worksheet_name}: {str(e)}")
        return pd.DataFrame()

# Función para guardar datos en Google Sheets
def save_data(sheet, worksheet_name, df):
    try:
        worksheet = sheet.worksheet(worksheet_name)
        worksheet.clear()
        
        # Convertir DataFrame a lista de listas
        data = [df.columns.values.tolist()] + df.values.tolist()
        worksheet.update('A1', data)
        
        # Limpiar cache
        load_data.clear()
        
        return True
    except Exception as e:
        st.error(f"Error al guardar en {worksheet_name}: {str(e)}")
        return False

# Función para formatear moneda
def format_currency(amount):
    return f"$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("# 📚 Profesor Particular")
    st.markdown("### Federico Luis Martínez")
    st.markdown("---")
    st.markdown("**Materias:**")
    st.markdown("• Matemática")
    st.markdown("• Física")
    st.markdown("• Economía")
    st.markdown("• Estadística")
    st.markdown("• Matemática Financiera")
    st.markdown("---")
    st.markdown("**Niveles:**")
    st.markdown("• Secundaria")
    st.markdown("• Universidad")

# Conectar con Google Sheets
sheet = get_google_sheet()

if sheet:
    # Crear pestañas
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "👨‍🎓 Alumnos",
        "📝 Registrar Clase",
        "💰 Historial de Clases",
        "📈 Análisis"
    ])
    
    # TAB 1: DASHBOARD
    with tab1:
        st.markdown('<p class="main-header">📊 Panel de Control</p>', unsafe_allow_html=True)
        
        # Cargar datos
        df_clases = load_data(sheet, "Clases")
        df_alumnos = load_data(sheet, "Alumnos")
        
        if not df_clases.empty:
            # Convertir fecha a datetime
            df_clases['Fecha'] = pd.to_datetime(df_clases['Fecha'], errors='coerce')
            
            # Filtros de fecha
            col1, col2 = st.columns(2)
            with col1:
                mes_actual = datetime.now().month
                año_actual = datetime.now().year
                meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                mes_seleccionado = st.selectbox("Mes", meses, index=mes_actual-1)
            with col2:
                año_seleccionado = st.selectbox("Año", [2024, 2025, 2026], index=1)
            
            # Filtrar datos por mes
            mes_num = meses.index(mes_seleccionado) + 1
            df_mes = df_clases[(df_clases['Fecha'].dt.month == mes_num) & 
                               (df_clases['Fecha'].dt.year == año_seleccionado)]
            
            # KPIs principales
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                ingresos_mes = df_mes['Total'].sum()
                st.metric("💰 Ingresos del Mes", format_currency(ingresos_mes))
            
            with col2:
                clases_mes = len(df_mes)
                st.metric("📚 Clases Dictadas", clases_mes)
            
            with col3:
                horas_mes = df_mes['Duración(h)'].sum()
                st.metric("⏰ Horas Totales", f"{horas_mes:.1f}h")
            
            with col4:
                if clases_mes > 0:
                    promedio_clase = ingresos_mes / clases_mes
                else:
                    promedio_clase = 0
                st.metric("📊 Promedio por Clase", format_currency(promedio_clase))
            
            st.markdown("---")
            
            # Gráficos
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("💵 Ingresos por Alumno")
                if not df_mes.empty:
                    ingresos_alumno = df_mes.groupby('Alumno')['Total'].sum().sort_values(ascending=True)
                    fig1 = px.bar(
                        x=ingresos_alumno.values,
                        y=ingresos_alumno.index,
                        orientation='h',
                        labels={'x': 'Ingresos ($)', 'y': 'Alumno'}
                    )
                    fig1.update_traces(marker_color='#1f77b4')
                    st.plotly_chart(fig1, use_container_width=True)
                else:
                    st.info("No hay datos para este mes")
            
            with col2:
                st.subheader("📚 Clases por Materia")
                if not df_mes.empty:
                    clases_materia = df_mes['Materia'].value_counts()
                    fig2 = px.pie(
                        values=clases_materia.values,
                        names=clases_materia.index,
                        hole=0.4
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No hay datos para este mes")
            
            # Evolución mensual
            st.subheader("📈 Evolución de Ingresos")
            df_clases['Mes'] = df_clases['Fecha'].dt.to_period('M')
            ingresos_mensuales = df_clases.groupby('Mes')['Total'].sum().reset_index()
            ingresos_mensuales['Mes'] = ingresos_mensuales['Mes'].astype(str)
            
            fig3 = px.line(
                ingresos_mensuales,
                x='Mes',
                y='Total',
                markers=True,
                labels={'Total': 'Ingresos ($)', 'Mes': 'Mes'}
            )
            fig3.update_traces(line_color='#1f77b4', marker=dict(size=10))
            st.plotly_chart(fig3, use_container_width=True)
            
            # Clases pendientes de pago
            clases_pendientes = df_clases[df_clases['¿Pagada?'] == 'No']
            if not clases_pendientes.empty:
                st.warning(f"⚠️ Tienes {len(clases_pendientes)} clases pendientes de pago")
                total_pendiente = clases_pendientes['Total'].sum()
                st.error(f"Total pendiente: {format_currency(total_pendiente)}")
        else:
            st.info("No hay clases registradas aún. ¡Comienza registrando tu primera clase!")
    
    # TAB 2: ALUMNOS
    with tab2:
        st.markdown('<p class="main-header">👨‍🎓 Gestión de Alumnos</p>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Lista de Alumnos")
            df_alumnos_display = load_data(sheet, "Alumnos")
            if not df_alumnos_display.empty:
                st.dataframe(df_alumnos_display, use_container_width=True, height=400)
            else:
                st.info("No hay alumnos registrados. Agrega tu primer alumno →")
        
        with col2:
            st.subheader("➕ Agregar Nuevo Alumno")
            
            with st.form("nuevo_alumno", clear_on_submit=True):
                nombre = st.text_input("Nombre completo*")
                materia = st.selectbox("Materia*", ["Matemática", "Física", "Economía", "Estadística", "Matemática Financiera"])
                curso = st.selectbox("Nivel*", ["Secundaria", "Universidad"])
                telefono = st.text_input("Teléfono")
                contacto = st.text_input("Contacto (responsable)")
                precio_hora = st.number_input("Precio por hora ($)*", value=5000, step=500)
                modalidad = st.selectbox("Modalidad*", ["Presencial", "Virtual", "Híbrida"])
                
                submitted = st.form_submit_button("✅ Agregar Alumno", use_container_width=True)
                
                if submitted:
                    if not nombre:
                        st.error("El nombre es obligatorio")
                    else:
                        df_alumnos_new = load_data(sheet, "Alumnos")
                        nuevo_id = int(df_alumnos_new['ID_Alumno'].max()) + 1 if not df_alumnos_new.empty else 1
                        
                        nuevo_alumno = pd.DataFrame([{
                            'ID_Alumno': nuevo_id,
                            'Nombre': nombre,
                            'Materia': materia,
                            'Curso': curso,
                            'Teléfono': telefono,
                            'Contacto': contacto,
                            'Día': '',
                            'Frecuencia': '',
                            'PrecioHora': precio_hora,
                            'Modalidad': modalidad,
                            'FechaAlta': datetime.now().strftime('%Y-%m-%d'),
                            'Estado': 'Activo'
                        }])
                        
                        df_alumnos_updated = pd.concat([df_alumnos_new, nuevo_alumno], ignore_index=True)
                        
                        if save_data(sheet, "Alumnos", df_alumnos_updated):
                            st.success(f"✅ Alumno {nombre} agregado correctamente")
                            st.balloons()
                            st.rerun()
    
    # TAB 3: REGISTRAR CLASE
    with tab3:
        st.markdown('<p class="main-header">📝 Registrar Nueva Clase</p>', unsafe_allow_html=True)
        
        df_alumnos_activos = load_data(sheet, "Alumnos")
        
        # Verificar si existe la columna Estado
        if 'Estado' in df_alumnos_activos.columns:
            df_alumnos_activos = df_alumnos_activos[df_alumnos_activos['Estado'] == 'Activo']
        
        if not df_alumnos_activos.empty:
            col1, col2 = st.columns([1.5, 1])
            
            with col1:
                with st.form("nueva_clase", clear_on_submit=True):
                    st.subheader("Datos de la Clase")
                    
                    alumno_seleccionado = st.selectbox(
                        "Alumno*",
                        df_alumnos_activos['Nombre'].tolist()
                    )
                    
                    # Obtener datos del alumno
                    alumno_data = df_alumnos_activos[df_alumnos_activos['Nombre'] == alumno_seleccionado].iloc[0]
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        fecha = st.date_input("Fecha de la clase*", value=datetime.now())
                    with col_b:
                        materia = st.selectbox(
                            "Materia*",
                            ["Matemática", "Física", "Economía", "Estadística"],
                            index=["Matemática", "Física", "Economía", "Estadística"].index(alumno_data['Materia']) 
                            if alumno_data['Materia'] in ["Matemática", "Física", "Economía", "Estadística"] else 0
                        )
                    
                    col_c, col_d = st.columns(2)
                    with col_c:
                        duracion = st.number_input("Duración (horas)*", min_value=0.5, max_value=8.0, value=1.5, step=0.5)
                    with col_d:
                        precio_hora = st.number_input("Precio por hora ($)*", value=int(alumno_data['PrecioHora']), step=500)
                    
                    col_e, col_f = st.columns(2)
                    with col_e:
                        pagada = st.selectbox("¿Pagada?*", ["Sí", "No"])
                    with col_f:
                        metodo = st.selectbox("Método de pago", ["Transferencia", "Efectivo", "MercadoPago", "Otro"])
                    
                    total = duracion * precio_hora
                    st.success(f"💰 Total de la clase: **{format_currency(total)}**")
                    
                    submitted = st.form_submit_button("✅ Registrar Clase", use_container_width=True)
                    
                    if submitted:
                        df_clases_new = load_data(sheet, "Clases")
                        nuevo_id = int(df_clases_new['ID_Clase'].max()) + 1 if not df_clases_new.empty else 1
                        
                        nueva_clase = pd.DataFrame([{
                            'ID_Clase': nuevo_id,
                            'Fecha': fecha.strftime('%Y-%m-%d'),
                            'ID_Alumno': int(alumno_data['ID_Alumno']),
                            'Alumno': alumno_seleccionado,
                            'Materia': materia,
                            'Duración(h)': duracion,
                            'PrecioHora': precio_hora,
                            '¿Pagada?': pagada,
                            'Método': metodo,
                            'Total': total
                        }])
                        
                        df_clases_updated = pd.concat([df_clases_new, nueva_clase], ignore_index=True)
                        
                        if save_data(sheet, "Clases", df_clases_updated):
                            st.success(f"✅ Clase registrada correctamente")
                            st.balloons()
                            st.rerun()
            
            with col2:
                st.subheader("📋 Últimas Clases")
                df_ultimas = load_data(sheet, "Clases")
                if not df_ultimas.empty:
                    df_ultimas['Fecha'] = pd.to_datetime(df_ultimas['Fecha'], errors='coerce')
                    df_ultimas_sorted = df_ultimas.sort_values('Fecha', ascending=False).head(5)
                    
                    for _, clase in df_ultimas_sorted.iterrows():
                        fecha_str = clase['Fecha'].strftime('%d/%m/%Y') if pd.notna(clase['Fecha']) else 'Sin fecha'
                        with st.container():
                            st.markdown(f"""
                            <div style='background-color: #f0f2f6; padding: 0.8rem; border-radius: 0.5rem; margin-bottom: 0.5rem;'>
                                <b>{clase['Alumno']}</b> - {clase['Materia']}<br>
                                📅 {fecha_str} | ⏰ {clase['Duración(h)']}h<br>
                                💰 {format_currency(clase['Total'])} | {'✅ Pagada' if clase['¿Pagada?'] == 'Sí' else '⏳ Pendiente'}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("No hay clases registradas aún")
        else:
            st.warning("⚠️ No hay alumnos activos. Agrega un alumno primero en la pestaña 'Alumnos'.")
    
    # TAB 4: HISTORIAL
    with tab4:
        st.markdown('<p class="main-header">💰 Historial de Clases</p>', unsafe_allow_html=True)
        
        df_clases_hist = load_data(sheet, "Clases")
        
        if not df_clases_hist.empty:
            df_clases_hist['Fecha'] = pd.to_datetime(df_clases_hist['Fecha'], errors='coerce')
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            with col1:
                filtro_alumno = st.multiselect(
                    "Filtrar por alumno",
                    df_clases_hist['Alumno'].unique()
                )
            with col2:
                filtro_materia = st.multiselect(
                    "Filtrar por materia",
                    df_clases_hist['Materia'].unique()
                )
            with col3:
                filtro_pago = st.selectbox(
                    "Estado de pago",
                    ["Todas", "Pagadas", "Pendientes"]
                )
            
            # Aplicar filtros
            df_filtrado = df_clases_hist.copy()
            if filtro_alumno:
                df_filtrado = df_filtrado[df_filtrado['Alumno'].isin(filtro_alumno)]
            if filtro_materia:
                df_filtrado = df_filtrado[df_filtrado['Materia'].isin(filtro_materia)]
            if filtro_pago == "Pagadas":
                df_filtrado = df_filtrado[df_filtrado['¿Pagada?'] == 'Sí']
            elif filtro_pago == "Pendientes":
                df_filtrado = df_filtrado[df_filtrado['¿Pagada?'] == 'No']
            
            # Mostrar tabla
            df_display = df_filtrado.sort_values('Fecha', ascending=False)
            df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')
            st.dataframe(
                df_display,
                use_container_width=True,
                height=400
            )
            
            # Resumen
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📚 Total de clases", len(df_filtrado))
            with col2:
                st.metric("💰 Total facturado", format_currency(df_filtrado['Total'].sum()))
            with col3:
                pendiente = df_filtrado[df_filtrado['¿Pagada?'] == 'No']['Total'].sum()
                st.metric("⏳ Pendiente de cobro", format_currency(pendiente))
            with col4:
                cobrado = df_filtrado[df_filtrado['¿Pagada?'] == 'Sí']['Total'].sum()
                st.metric("✅ Cobrado", format_currency(cobrado))
        else:
            st.info("No hay clases registradas aún")
    
    # TAB 5: ANÁLISIS
    with tab5:
        st.markdown('<p class="main-header">📈 Análisis y Proyecciones</p>', unsafe_allow_html=True)
        
        df_clases_analysis = load_data(sheet, "Clases")
        df_alumnos_analysis = load_data(sheet, "Alumnos")
        
        if not df_clases_analysis.empty:
            df_clases_analysis['Fecha'] = pd.to_datetime(df_clases_analysis['Fecha'], errors='coerce')
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🎯 Rendimiento por Alumno")
                resumen_alumno = df_clases_analysis.groupby('Alumno').agg({
                    'ID_Clase': 'count',
                    'Duración(h)': 'sum',
                    'Total': 'sum'
                }).reset_index()
                resumen_alumno.columns = ['Alumno', 'Clases', 'Horas', 'Facturado']
                resumen_alumno['Facturado'] = resumen_alumno['Facturado'].apply(lambda x: format_currency(x))
                st.dataframe(resumen_alumno, use_container_width=True, hide_index=True)
            
            with col2:
                st.subheader("📚 Rendimiento por Materia")
                resumen_materia = df_clases_analysis.groupby('Materia').agg({
                    'ID_Clase': 'count',
                    'Duración(h)': 'sum',
                    'Total': 'sum'
                }).reset_index()
                resumen_materia.columns = ['Materia', 'Clases', 'Horas', 'Facturado']
                resumen_materia['Facturado'] = resumen_materia['Facturado'].apply(lambda x: format_currency(x))
                st.dataframe(resumen_materia, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            st.subheader("💡 Proyección Mensual")
            st.info("Basado en el promedio de los últimos meses")
            
            # Calcular proyección
            if 'Estado' in df_alumnos_analysis.columns:
                total_alumnos = len(df_alumnos_analysis[df_alumnos_analysis['Estado'] == 'Activo'])
            else:
                total_alumnos = len(df_alumnos_analysis)
                
            ingreso_promedio_clase = df_clases_analysis['Total'].mean()
            clases_promedio_mes = len(df_clases_analysis) / max(df_clases_analysis['Fecha'].dt.to_period('M').nunique(), 1)
            
            proyeccion_mes = clases_promedio_mes * ingreso_promedio_clase
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("👨‍🎓 Alumnos Activos", total_alumnos)
            with col2:
                st.metric("📊 Clases promedio/mes", f"{clases_promedio_mes:.0f}")
            with col3:
                st.metric("💰 Proyección mensual", format_currency(proyeccion_mes))
        else:
            st.info("No hay suficientes datos para análisis. Comienza registrando clases.")

else:
    st.error("❌ No se pudo conectar con Google Sheets. Verifica tu configuración de Streamlit Secrets.")
    st.markdown("""
    ### 🔧 Configuración necesaria:
    
    1. Ve a tu app en Streamlit Cloud
    2. Click en "Settings" → "Secrets"
    3. Agrega tu configuración (ver instrucciones completas)
    """)