"""Lógica pura de ProfeApp: parseo, normalización de hojas, tarifas y métricas.

No depende de Streamlit ni de Google Sheets, así se puede testear y reutilizar
desde scripts/corregir_datos.py.
"""
import math
import re
import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd

# ─────────────────────────────────────────────
# ESQUEMA
# ─────────────────────────────────────────────
COLUMNAS_CLASES_VIEJAS = ['ID_Clase', 'Fecha', 'ID_Alumno', 'Alumno', 'Materia', 'Duración(h)',
                          'PrecioHora', '¿Pagada?', 'Método', 'Total']
COLUMNAS_CLASES_NUEVAS = ['MontoCobrado', 'HorasReales', 'Revisar', 'NotaRevision']
COLUMNAS_CLASES = COLUMNAS_CLASES_VIEJAS + COLUMNAS_CLASES_NUEVAS

COLUMNAS_ALUMNOS = ['ID_Alumno', 'Nombre', 'Materia', 'Curso', 'Teléfono', 'Contacto', 'Día',
                    'Frecuencia', 'PrecioHora', 'Modalidad', 'FechaAlta', 'Estado', 'Observaciones']

COLUMNAS_TARIFAS = ['ID_Tarifa', 'ID_Alumno', 'Desde', 'Tipo', 'Monto', 'Nota']

COLUMNAS_IPC = ['Mes', 'VariacionPct']

ID_COLUMNA = {'Clases': 'ID_Clase', 'Alumnos': 'ID_Alumno', 'Tarifas': 'ID_Tarifa'}

ESTADOS = ['Activo', 'Pausado', 'Baja']
TIPOS_TARIFA = ['Hora', 'Clase', 'Mensual']
METODOS = ["Transferencia", "Efectivo", "MercadoPago", "Otro"]
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def normalizar_texto(s):
    """NFC + strip, para comparar encabezados con tildes de forma segura."""
    return unicodedata.normalize('NFC', str(s)).strip()


def sin_tildes(s):
    s = unicodedata.normalize('NFD', str(s))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower().strip()


# ─────────────────────────────────────────────
# PARSEO
# ─────────────────────────────────────────────
_MILES_PUNTO = re.compile(r'^-?\d{1,3}(\.\d{3})+$')


def parse_numero(val, tipo='dinero'):
    """Convierte lo que venga del Sheet a float. Devuelve None si está vacío o no es número.

    tipo='dinero': en "10.000" el punto es separador de miles; en "4000.0" (texto viejo) es decimal.
    tipo='horas': punto o coma son siempre decimales ("1.5", "2,5").
    """
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return None if (isinstance(val, float) and math.isnan(val)) else float(val)
    s = str(val).strip().replace('$', '').replace('\xa0', '').replace(' ', '')
    if not s or s.lower() in ('nan', 'none'):
        return None
    if ',' in s and '.' in s:
        dec = ',' if s.rfind(',') > s.rfind('.') else '.'
        miles = '.' if dec == ',' else ','
        s = s.replace(miles, '').replace(dec, '.')
    elif ',' in s:
        s = s.replace(',', '.')
    elif '.' in s and tipo == 'dinero' and _MILES_PUNTO.match(s):
        s = s.replace('.', '')
    try:
        return float(s)
    except ValueError:
        return None


def parse_fecha(val):
    """Fecha ISO en texto, dd/mm/aaaa o número de serie de Sheets → pd.Timestamp (o NaT)."""
    if val is None or val == '' or isinstance(val, bool):
        return pd.NaT
    if isinstance(val, (pd.Timestamp, datetime)):
        return pd.Timestamp(val).normalize()
    if isinstance(val, date):
        return pd.Timestamp(val)
    if isinstance(val, (int, float)):
        if isinstance(val, float) and math.isnan(val):
            return pd.NaT
        return pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(val))
    s = str(val).strip()
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}', s):
        return pd.to_datetime(s[:10], format='%Y-%m-%d', errors='coerce')
    if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', s):
        return pd.to_datetime(s, format='%d/%m/%Y', errors='coerce')
    return pd.NaT


def parse_id(val):
    n = parse_numero(val, tipo='horas')
    return int(n) if n is not None else 0


def texto(val):
    """Texto limpio; los números enteros guardados como float (teléfonos) pierden el '.0'."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ''
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


# ─────────────────────────────────────────────
# FORMATO ARGENTINO
# ─────────────────────────────────────────────
def format_currency(amount, decimales=None):
    try:
        amount = float(amount)
        if math.isnan(amount):
            amount = 0.0
    except (TypeError, ValueError):
        amount = 0.0
    if decimales is None:
        decimales = 0 if round(amount, 2).is_integer() else 2
    s = f"{amount:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}"


def format_hours(h):
    try:
        h = float(h)
        if math.isnan(h):
            h = 0.0
    except (TypeError, ValueError):
        h = 0.0
    s = f"{h:.2f}".rstrip('0').rstrip('.')
    return f"{s.replace('.', ',')} h"


def format_fecha(f):
    if f is None or pd.isna(f):
        return '—'
    return pd.Timestamp(f).strftime('%d/%m/%Y')


def format_pct(p):
    return f"{p:+.1f}%".replace('.', ',')


# ─────────────────────────────────────────────
# NORMALIZACIÓN DE HOJAS
# ─────────────────────────────────────────────
def filas_a_df(valores):
    """Lista de listas (fila 0 = encabezados) → DataFrame con encabezados normalizados."""
    if not valores:
        return pd.DataFrame()
    headers = [normalizar_texto(h) for h in valores[0]]
    # Descarta columnas sin encabezado al final
    while headers and headers[-1] == '':
        headers.pop()
    filas = []
    for fila in valores[1:]:
        fila = list(fila[:len(headers)]) + [''] * (len(headers) - len(fila))
        if all(v in ('', None) for v in fila):
            continue
        filas.append(fila)
    return pd.DataFrame(filas, columns=headers)


def columnas_faltantes(df, esperadas):
    return [c for c in esperadas if c not in df.columns]


def normalizar_clases(df):
    """Agrega las columnas que falten y calcula Monto, Horas y $/h efectivo."""
    df = df.copy()
    for c in COLUMNAS_CLASES:
        if c not in df.columns:
            df[c] = ''
    df['ID_Clase'] = df['ID_Clase'].apply(parse_id)
    df['ID_Alumno'] = df['ID_Alumno'].apply(parse_id)
    df['Fecha'] = pd.to_datetime(df['Fecha'].apply(parse_fecha), errors='coerce')
    for c in ['PrecioHora', 'Total', 'MontoCobrado']:
        df[c] = pd.to_numeric(df[c].apply(parse_numero, tipo='dinero'), errors='coerce')
    for c in ['Duración(h)', 'HorasReales']:
        df[c] = pd.to_numeric(df[c].apply(parse_numero, tipo='horas'), errors='coerce')
    for c in ['Alumno', 'Materia', '¿Pagada?', 'Método', 'Revisar', 'NotaRevision']:
        df[c] = df[c].apply(texto)
    # Monto = lo cobrado (respaldo: Total); Horas = reales (respaldo: Duración)
    df['Monto'] = df['MontoCobrado'].fillna(df['Total']).fillna(0.0)
    df['Horas'] = df['HorasReales'].fillna(df['Duración(h)']).fillna(0.0)
    df['PorHora'] = (df['Monto'] / df['Horas'].where(df['Horas'] > 0)).fillna(0.0)
    df['Pagada'] = df['¿Pagada?'].str.strip().str.lower().isin(['sí', 'si'])
    df['ARevisar'] = df['Revisar'].str.strip().str.lower().isin(['sí', 'si'])
    return df


def normalizar_alumnos(df):
    df = df.copy()
    for c in COLUMNAS_ALUMNOS:
        if c not in df.columns:
            df[c] = ''
    df['ID_Alumno'] = df['ID_Alumno'].apply(parse_id)
    df['PrecioHora'] = pd.to_numeric(df['PrecioHora'].apply(parse_numero, tipo='dinero'),
                                     errors='coerce').fillna(0.0)
    alta_cruda = df['FechaAlta'].copy()
    for c in ['Nombre', 'Materia', 'Curso', 'Teléfono', 'Contacto', 'Día', 'Frecuencia',
              'Modalidad', 'FechaAlta', 'Estado', 'Observaciones']:
        df[c] = df[c].apply(texto)
    df.loc[df['Estado'] == '', 'Estado'] = 'Activo'
    # FechaAlta puede venir como texto ISO, dd/mm/aaaa o número de serie: se normaliza a ISO
    alta = alta_cruda.apply(parse_fecha)
    df['FechaAlta'] = [f.date().isoformat() if not pd.isna(f) else t for f, t in zip(alta, df['FechaAlta'])]
    return df


def normalizar_tarifas(df):
    df = df.copy()
    for c in COLUMNAS_TARIFAS:
        if c not in df.columns:
            df[c] = ''
    df['ID_Tarifa'] = df['ID_Tarifa'].apply(parse_id)
    df['ID_Alumno'] = df['ID_Alumno'].apply(parse_id)
    df['Desde'] = pd.to_datetime(df['Desde'].apply(parse_fecha), errors='coerce')
    df['Monto'] = pd.to_numeric(df['Monto'].apply(parse_numero, tipo='dinero'), errors='coerce')
    df['Tipo'] = df['Tipo'].apply(texto).replace('', 'Hora')
    df['Nota'] = df['Nota'].apply(texto)
    return df[df['Desde'].notna() & df['Monto'].notna()]


def nombres_por_id(df_alumnos):
    if df_alumnos is None or df_alumnos.empty:
        return {}
    return dict(zip(df_alumnos['ID_Alumno'], df_alumnos['Nombre']))


def aplicar_nombres(df_clases, df_alumnos):
    """El nombre que se muestra sale de la ficha (cruce por ID); si no está, el de la clase."""
    df = df_clases.copy()
    nombres = nombres_por_id(df_alumnos)
    df['Alumno'] = [nombres.get(i) or n for i, n in zip(df['ID_Alumno'], df['Alumno'])]
    return df


# ─────────────────────────────────────────────
# TARIFAS
# ─────────────────────────────────────────────
def tarifa_vigente(id_alumno, fecha, df_tarifas, df_alumnos):
    """Devuelve (monto, tipo, origen). La vigente es la de Desde más reciente ≤ fecha.

    Si no hay hoja Tarifas o no hay tarifa a esa fecha, usa Alumnos.PrecioHora.
    """
    fecha = pd.Timestamp(fecha).normalize()
    if df_tarifas is not None and not df_tarifas.empty:
        t = df_tarifas[(df_tarifas['ID_Alumno'] == id_alumno) & (df_tarifas['Desde'] <= fecha)]
        if not t.empty:
            fila = t.sort_values(['Desde', 'ID_Tarifa']).iloc[-1]
            return float(fila['Monto']), fila['Tipo'] or 'Hora', 'Tarifas'
    if df_alumnos is not None and not df_alumnos.empty:
        a = df_alumnos[df_alumnos['ID_Alumno'] == id_alumno]
        if not a.empty:
            return float(a.iloc[0]['PrecioHora']), 'Hora', 'Ficha'
    return 0.0, 'Hora', 'Ninguna'


def monto_sugerido(horas, tarifa, tipo):
    if tipo == 'Clase':
        return float(tarifa)
    if tipo == 'Mensual':
        return 0.0
    return round(float(horas) * float(tarifa), 2)


def ultima_tarifa_cargada(df_tarifas, df_alumnos, por_defecto=7500.0):
    """Precio por defecto para un alumno nuevo: la última tarifa por hora cargada."""
    if df_tarifas is not None and not df_tarifas.empty:
        t = df_tarifas[df_tarifas['Tipo'] == 'Hora']
        if not t.empty:
            return float(t.sort_values(['Desde', 'ID_Tarifa']).iloc[-1]['Monto'])
    if df_alumnos is not None and not df_alumnos.empty:
        a = df_alumnos[df_alumnos['PrecioHora'] > 0].sort_values(['FechaAlta', 'ID_Alumno'])
        if not a.empty:
            return float(a.iloc[-1]['PrecioHora'])
    return por_defecto


def nuevo_monto_aumento(actual, modo, valor, redondear_a=100):
    """modo 'monto': valor es el monto nuevo; modo 'pct': aumenta valor % (redondeado)."""
    if modo == 'monto':
        return float(valor)
    nuevo = float(actual) * (1 + float(valor) / 100)
    if redondear_a:
        nuevo = round(nuevo / redondear_a) * redondear_a
    return float(nuevo)


# ─────────────────────────────────────────────
# CLASES
# ─────────────────────────────────────────────
def clases_mismo_dia(df_clases, id_alumno, fecha):
    if df_clases is None or df_clases.empty:
        return df_clases
    fecha = pd.Timestamp(fecha).normalize()
    return df_clases[(df_clases['ID_Alumno'] == id_alumno) & (df_clases['Fecha'] == fecha)]


def siguiente_id(ids):
    ids = [i for i in ids if i]
    return (max(ids) + 1) if ids else 1


def anios_disponibles(df_clases, hoy=None):
    hoy = hoy or date.today()
    anios = set()
    if df_clases is not None and not df_clases.empty:
        anios = set(int(a) for a in df_clases['Fecha'].dropna().dt.year.unique())
    anios.add(hoy.year)
    return sorted(anios)


def filtrar_mes(df, mes, anio):
    return df[(df['Fecha'].dt.month == mes) & (df['Fecha'].dt.year == anio)]


def precio_hora_por_mes(df_clases):
    """$/hora promedio por mes = monto total / horas totales (sin groupby().apply)."""
    if df_clases.empty:
        return pd.DataFrame(columns=['Mes', 'PorHora'])
    g = (df_clases.dropna(subset=['Fecha'])
         .assign(Mes=lambda d: d['Fecha'].dt.to_period('M').astype(str))
         .groupby('Mes', as_index=False)[['Monto', 'Horas']].sum())
    g['PorHora'] = (g['Monto'] / g['Horas'].where(g['Horas'] > 0)).fillna(0.0)
    return g[['Mes', 'PorHora']]


# ─────────────────────────────────────────────
# EDICIÓN DEL HISTORIAL
# ─────────────────────────────────────────────
def tabla_editable_clases(df_clases):
    """DataFrame para st.data_editor, indexado por ID_Clase."""
    return pd.DataFrame({
        'ID': df_clases['ID_Clase'].astype(int),
        'Fecha': pd.Series([f.date() if not pd.isna(f) else None for f in df_clases['Fecha']],
                           index=df_clases.index, dtype='object'),
        'Alumno': df_clases['Alumno'],
        'Materia': df_clases['Materia'],
        'Horas': df_clases['Horas'].astype(float),
        'Monto': df_clases['Monto'].astype(float),
        '$/h': df_clases['PorHora'].astype(float),
        'Pagada': df_clases['Pagada'].astype(bool),
        'Método': df_clases['Método'],
        'Revisar': df_clases['ARevisar'].astype(bool),
        'Nota': df_clases['NotaRevision'],
    }).set_index('ID')


def _distinto(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            a, b = float(a), float(b)
        except (TypeError, ValueError):
            return a != b
        if math.isnan(a) and math.isnan(b):
            return False
        return abs(a - b) > 1e-9
    if pd.isna(a) and pd.isna(b):
        return False
    return a != b


def cambios_historial(original, editado, columnas_sheet):
    """{ID_Clase: {columna_del_sheet: valor}} solo con las celdas que cambiaron.

    Horas → HorasReales (o Duración(h) si el Sheet es viejo). Monto → MontoCobrado y Total.
    """
    columnas_sheet = set(columnas_sheet)
    col_horas = 'HorasReales' if 'HorasReales' in columnas_sheet else 'Duración(h)'
    resultado = {}
    for id_clase, fila in editado.iterrows():
        if id_clase not in original.index:
            continue
        orig = original.loc[id_clase]
        cambios = {}
        if _distinto(orig['Fecha'], fila['Fecha']) and not pd.isna(fila['Fecha']):
            cambios['Fecha'] = pd.Timestamp(fila['Fecha']).date().isoformat()
        if _distinto(orig['Horas'], fila['Horas']) and not pd.isna(fila['Horas']):
            cambios[col_horas] = float(fila['Horas'])
        if _distinto(orig['Monto'], fila['Monto']) and not pd.isna(fila['Monto']):
            cambios['MontoCobrado'] = cambios['Total'] = float(fila['Monto'])
        if _distinto(bool(orig['Pagada']), bool(fila['Pagada'])):
            cambios['¿Pagada?'] = 'Sí' if fila['Pagada'] else 'No'
        if _distinto(texto(orig['Método']), texto(fila['Método'])):
            cambios['Método'] = texto(fila['Método'])
        if _distinto(bool(orig['Revisar']), bool(fila['Revisar'])):
            cambios['Revisar'] = 'Sí' if fila['Revisar'] else ''
        if _distinto(texto(orig['Nota']), texto(fila['Nota'])):
            cambios['NotaRevision'] = texto(fila['Nota'])
        if cambios:
            resultado[int(id_clase)] = cambios
    return resultado


def validar_cambios(cambios):
    """Lista de errores (horas ≤ 0, montos negativos)."""
    errores = []
    for id_clase, c in cambios.items():
        for col in ('HorasReales', 'Duración(h)'):
            if col in c and c[col] <= 0:
                errores.append(f"Clase #{id_clase}: las horas tienen que ser mayores a 0")
        if 'MontoCobrado' in c and c['MontoCobrado'] < 0:
            errores.append(f"Clase #{id_clase}: el monto no puede ser negativo")
    return errores


# ─────────────────────────────────────────────
# AUMENTOS
# ─────────────────────────────────────────────
def plan_aumento(ids, modo, valor, desde, df_tarifas, df_alumnos, redondear_a=100):
    """Tabla con la tarifa actual (vigente el día anterior a `desde`) y la nueva de cada alumno."""
    desde = pd.Timestamp(desde).normalize()
    nombres = nombres_por_id(df_alumnos)
    filas = []
    for id_alumno in ids:
        actual, tipo, _ = tarifa_vigente(id_alumno, desde - pd.Timedelta(days=1), df_tarifas, df_alumnos)
        nuevo = nuevo_monto_aumento(actual, modo, valor, redondear_a)
        filas.append({
            'ID_Alumno': int(id_alumno), 'Alumno': nombres.get(id_alumno, f"#{id_alumno}"), 'Tipo': tipo,
            'Actual': actual, 'Nuevo': nuevo,
            'Variación %': ((nuevo / actual - 1) * 100) if actual else None,
        })
    return pd.DataFrame(filas, columns=['ID_Alumno', 'Alumno', 'Tipo', 'Actual', 'Nuevo', 'Variación %'])
