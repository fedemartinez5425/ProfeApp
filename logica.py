"""Lógica pura de ProfeApp: parseo, normalización de hojas, tarifas y métricas.

No depende de Streamlit ni de Google Sheets, así se puede testear y reutilizar
desde scripts/corregir_datos.py.
"""
import math
import re
import unicodedata
from datetime import date, datetime
from urllib.parse import quote

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


def format_dias(d):
    return '—' if d is None or pd.isna(d) else f"{int(d)} días"


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


# ─────────────────────────────────────────────
# IPC E INFLACIÓN
# ─────────────────────────────────────────────
def parse_mes(val):
    """'2026-10', '2026-10-01', '10/2026', fecha o número de serie → 'aaaa-mm' (o '')."""
    if val is None or val == '':
        return ''
    s = str(val).strip()
    m = re.match(r'^(\d{4})-(\d{1,2})$', s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m = re.match(r'^(\d{1,2})/(\d{4})$', s)
    if m:
        return f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"
    f = parse_fecha(val)
    return '' if pd.isna(f) else f.strftime('%Y-%m')


def normalizar_ipc(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=['Mes', 'VariacionPct'])
    df = df.copy()
    for c in COLUMNAS_IPC:
        if c not in df.columns:
            df[c] = ''
    df['Mes'] = df['Mes'].apply(parse_mes)
    df['VariacionPct'] = pd.to_numeric(df['VariacionPct'].apply(parse_numero, tipo='horas'), errors='coerce')
    df = df[(df['Mes'] != '') & df['VariacionPct'].notna()]
    return df.drop_duplicates('Mes', keep='last').sort_values('Mes')[['Mes', 'VariacionPct']]


def meses_entre(desde_mes, hasta_mes):
    """Meses 'aaaa-mm' desde desde_mes (incluido) hasta hasta_mes (excluido)."""
    p, fin = pd.Period(desde_mes, 'M'), pd.Period(hasta_mes, 'M')
    out = []
    while p < fin:
        out.append(str(p))
        p += 1
    return out


def inflacion_acumulada(df_ipc, desde_mes, hasta_mes):
    """(% acumulado, meses sin dato) para los meses en que rigió la tarifa anterior."""
    meses = meses_entre(desde_mes, hasta_mes)
    tabla = dict(zip(df_ipc['Mes'], df_ipc['VariacionPct'])) if df_ipc is not None else {}
    factor, faltan = 1.0, []
    for m in meses:
        if m in tabla:
            factor *= 1 + tabla[m] / 100
        else:
            faltan.append(m)
    return (factor - 1) * 100, faltan


def comparar_aumentos_ipc(df_tarifas, df_ipc, df_alumnos):
    """Cada aumento (tarifa vs. la anterior del mismo alumno y tipo) contra la inflación del período."""
    columnas = ['ID_Alumno', 'Alumno', 'Desde anterior', 'Desde', 'Anterior', 'Nueva', 'Aumento %',
                'Inflación %', 'Diferencia real %', 'Meses sin IPC']
    if df_tarifas is None or df_tarifas.empty:
        return pd.DataFrame(columns=columnas)
    nombres = nombres_por_id(df_alumnos)
    filas = []
    for (id_alumno, tipo), t in df_tarifas.sort_values(['Desde', 'ID_Tarifa']).groupby(['ID_Alumno', 'Tipo']):
        previa = None
        for _, r in t.iterrows():
            if previa is not None and previa['Monto'] > 0 and r['Monto'] != previa['Monto']:
                aumento = (r['Monto'] / previa['Monto'] - 1) * 100
                inflacion, faltan = inflacion_acumulada(df_ipc, previa['Desde'].strftime('%Y-%m'),
                                                        r['Desde'].strftime('%Y-%m'))
                filas.append({
                    'ID_Alumno': id_alumno, 'Alumno': nombres.get(id_alumno, f"#{id_alumno}"),
                    'Desde anterior': previa['Desde'], 'Desde': r['Desde'],
                    'Anterior': previa['Monto'], 'Nueva': r['Monto'], 'Aumento %': aumento,
                    'Inflación %': inflacion,
                    'Diferencia real %': ((1 + aumento / 100) / (1 + inflacion / 100) - 1) * 100,
                    'Meses sin IPC': ', '.join(faltan),
                })
            # Una tarifa recargada con el mismo monto no corta el período de la anterior
            if previa is None or r['Monto'] != previa['Monto']:
                previa = r
    return pd.DataFrame(filas, columns=columnas)


def texto_vs_inflacion(diferencia_real):
    if diferencia_real is None or pd.isna(diferencia_real):
        return '—'
    if abs(diferencia_real) < 0.05:
        return "empataste con la inflación"
    verbo = "le ganaste" if diferencia_real > 0 else "le perdiste"
    return f"{verbo} a la inflación por {abs(diferencia_real):.1f}%".replace('.', ',')


# ─────────────────────────────────────────────
# RESUMEN PARA WHATSAPP
# ─────────────────────────────────────────────
def resumen_mensual(df_clases, id_alumno, nombre, mes, anio):
    """Texto listo para mandar por WhatsApp con las clases del mes de un alumno."""
    d = filtrar_mes(df_clases[df_clases['ID_Alumno'] == id_alumno], mes, anio).sort_values(['Fecha', 'ID_Clase'])
    titulo = f"Hola! Te paso el resumen de clases de {nombre} de {MESES[mes - 1].lower()} {anio}:"
    if d.empty:
        return titulo + "\n\nNo hubo clases este mes."
    lineas = [titulo, ""]
    for _, c in d.iterrows():
        estado = "" if c['Pagada'] else " (pendiente)"
        lineas.append(f"• {format_fecha(c['Fecha'])}: {format_hours(c['Horas'])} · {format_currency(c['Monto'])}{estado}")
    total, pendiente = d['Monto'].sum(), d[~d['Pagada']]['Monto'].sum()
    lineas += ["", f"Total: {len(d)} clase{'s' if len(d) != 1 else ''} · {format_hours(d['Horas'].sum())} · "
               f"{format_currency(total)}"]
    if pendiente > 0:
        lineas.append(f"Pendiente de pago: {format_currency(pendiente)}")
    lineas += ["", "¡Gracias!"]
    return "\n".join(lineas)


def telefono_whatsapp(telefono):
    """Número argentino para wa.me sin el 549 (área + número, 10 dígitos), o '' si no sirve."""
    dig = re.sub(r'\D', '', texto(telefono))
    if dig.startswith('549'):
        dig = dig[3:]
    elif dig.startswith('54'):
        dig = dig[2:]
    dig = dig.lstrip('0')
    # 0264 15 4123456 → 264 4123456
    m = re.match(r'^(\d{2,4})15(\d{6,8})$', dig)
    if m and len(m.group(1) + m.group(2)) == 10:
        dig = m.group(1) + m.group(2)
    return dig if len(dig) == 10 else ''


def link_whatsapp(telefono, mensaje):
    numero = telefono_whatsapp(telefono)
    if not numero:
        return None
    return f"https://wa.me/549{numero}?text={quote(mensaje)}"


# ─────────────────────────────────────────────
# COBROS PENDIENTES
# ─────────────────────────────────────────────
def cobros_pendientes(df_clases, hoy):
    """Clases no pagadas con antigüedad en días, más vieja primero."""
    if df_clases is None or df_clases.empty:
        return pd.DataFrame(columns=['ID_Clase', 'ID_Alumno', 'Alumno', 'Fecha', 'Horas', 'Monto', 'Dias'])
    p = df_clases[~df_clases['Pagada']].copy()
    # Sin fecha → antigüedad desconocida (NaN, se muestra "—"); clases futuras → 0 días
    p['Dias'] = (pd.Timestamp(hoy) - p['Fecha']).dt.days.clip(lower=0)
    return p.sort_values(['Fecha', 'ID_Clase'], na_position='last')[['ID_Clase', 'ID_Alumno', 'Alumno', 'Fecha', 'Horas', 'Monto', 'Dias']]


def pendientes_por_alumno(pend):
    if pend.empty:
        return pd.DataFrame(columns=['ID_Alumno', 'Alumno', 'Clases', 'Monto', 'MasVieja'])
    return (pend.groupby('ID_Alumno', as_index=False)
            .agg(Alumno=('Alumno', 'last'), Clases=('ID_Clase', 'count'), Monto=('Monto', 'sum'),
                 MasVieja=('Dias', 'max'))
            .sort_values('MasVieja', ascending=False))


# ─────────────────────────────────────────────
# PROYECCIÓN
# ─────────────────────────────────────────────
def promedio_mensual_historico(df_clases, hoy):
    """Ingreso promedio por mes desde el primer mes con clases hasta el último mes completo, con ceros."""
    d = df_clases.dropna(subset=['Fecha']) if df_clases is not None else pd.DataFrame()
    if d.empty:
        return 0.0, 0
    primero = d['Fecha'].min().to_period('M')
    ultimo = pd.Timestamp(hoy).to_period('M') - 1
    if ultimo < primero:
        return 0.0, 0
    meses = pd.period_range(primero, ultimo, freq='M')
    por_mes = d.groupby(d['Fecha'].dt.to_period('M'))['Monto'].sum().reindex(meses, fill_value=0)
    return float(por_mes.mean()), len(meses)


def proyeccion_mensual(df_clases, hoy, dias_activo=30, dias_base=90):
    """Proyección por alumno: activos = con clases en los últimos `dias_activo` días.

    Frecuencia = clases por semana en los últimos `dias_base` días (o desde su primera clase si es más
    reciente, mínimo 4 semanas); monto = promedio por clase en esa ventana.
    """
    columnas = ['ID_Alumno', 'Alumno', 'ClasesSemana', 'MontoClase', 'Mensual']
    d = df_clases.dropna(subset=['Fecha']) if df_clases is not None else pd.DataFrame()
    if d.empty:
        return pd.DataFrame(columns=columnas)
    hoy = pd.Timestamp(hoy).normalize()
    d = d[d['Fecha'] <= hoy].sort_values(['Fecha', 'ID_Clase'])
    activos = d[d['Fecha'] > hoy - pd.Timedelta(days=dias_activo)]['ID_Alumno'].unique()
    filas = []
    for id_alumno in activos:
        da = d[d['ID_Alumno'] == id_alumno]
        inicio = max(hoy - pd.Timedelta(days=dias_base), da['Fecha'].min())
        ventana = da[(da['Fecha'] >= inicio) & (da['Fecha'] <= hoy)]
        semanas = max((hoy - inicio).days + 1, 28) / 7
        por_semana = len(ventana) / semanas
        monto_clase = float(ventana['Monto'].mean()) if not ventana.empty else 0.0
        filas.append({'ID_Alumno': id_alumno, 'Alumno': da['Alumno'].iloc[-1], 'ClasesSemana': por_semana,
                      'MontoClase': monto_clase, 'Mensual': por_semana * 52 / 12 * monto_clase})
    return pd.DataFrame(filas, columns=columnas).sort_values('Mensual', ascending=False)


# ─────────────────────────────────────────────
# AGENDA
# ─────────────────────────────────────────────
FRECUENCIAS = ['', 'Semanal', '2 veces por semana', '3 veces por semana', 'Quincenal', 'Mensual', 'Ocasional']


def dias_de_texto(valor):
    """'Lunes, Jueves' / 'lunes y jueves' / 'Miercoles' → ['Lunes', 'Jueves'] (en orden de la semana)."""
    t = sin_tildes(valor)
    return [d for d in DIAS_SEMANA if sin_tildes(d) in t]


def agenda_semanal(df_alumnos):
    """{día: [(ID_Alumno, Nombre, Frecuencia, Materia)]} con los alumnos Activos que tienen Día cargado."""
    agenda = {d: [] for d in DIAS_SEMANA}
    if df_alumnos is None or df_alumnos.empty:
        return agenda
    for _, a in df_alumnos[df_alumnos['Estado'] == 'Activo'].sort_values('Nombre').iterrows():
        for d in dias_de_texto(a['Día']):
            agenda[d].append((a['ID_Alumno'], a['Nombre'], a['Frecuencia'], a['Materia']))
    return agenda
