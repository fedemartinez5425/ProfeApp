"""Capa de acceso a Google Sheets.

Reglas:
- Las columnas se mapean por nombre de encabezado, nunca por posición fija.
- Escritura siempre con value_input_option=RAW (la planilla es es-AR).
- Nunca se borra ni reescribe una hoja entera: alta = append_row, edición = celdas de la fila
  del ID, borrado = delete_rows de la fila buscada por ID justo antes.
- Después de cada escritura se invalida la caché de lectura.
"""
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.cell import Cell
from gspread.utils import ValueInputOption, ValueRenderOption

from logica import ID_COLUMNA, filas_a_df, normalizar_texto, parse_id

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


@st.cache_resource
def _abrir_planilla():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    spreadsheet_name = st.secrets["spreadsheet"]["name"]
    creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open(spreadsheet_name)


def conectar():
    """Abre la planilla. Devuelve None si falla (sin cachear el error, así reintenta)."""
    try:
        return _abrir_planilla()
    except Exception as e:
        st.error(f"❌ Error al conectar con Google Sheets: {e}")
        return None


def _hoja(sheet, hoja):
    return sheet.worksheet(hoja)


@st.cache_data(ttl=30, show_spinner=False)
def leer(_sheet, hoja):
    """DataFrame crudo (valores sin formato) de la hoja, o None si la hoja no existe."""
    try:
        ws = _hoja(_sheet, hoja)
    except gspread.exceptions.WorksheetNotFound:
        return None
    valores = ws.get_values(value_render_option=ValueRenderOption.unformatted)
    return filas_a_df(valores)


def invalidar_cache():
    leer.clear()


def _encabezados(ws):
    return [normalizar_texto(h) for h in ws.row_values(1)]


def _a_celda(valor):
    """Convierte tipos de numpy/pandas a tipos nativos serializables."""
    if valor is None:
        return ''
    if hasattr(valor, 'item'):
        valor = valor.item()
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor


def agregar(sheet, hoja, fila):
    """Agrega una fila al final. Las claves que no existen como encabezado se ignoran.

    Si la hoja tiene columna ID y la fila no trae ID, se asigna max(ID)+1 leído en el momento.
    Devuelve (id_asignado, columnas_ignoradas).
    """
    ws = _hoja(sheet, hoja)
    headers = _encabezados(ws)
    col_id = ID_COLUMNA.get(hoja)
    fila = dict(fila)
    if col_id and col_id in headers and not fila.get(col_id):
        ids = ws.col_values(headers.index(col_id) + 1,
                            value_render_option=ValueRenderOption.unformatted)[1:]
        fila[col_id] = max([parse_id(i) for i in ids] + [0]) + 1
    valores = [_a_celda(fila.get(h, '')) for h in headers]
    ws.append_row(valores, value_input_option=ValueInputOption.raw, table_range='A1')
    invalidar_cache()
    ignoradas = [k for k in fila if k not in headers]
    return fila.get(col_id), ignoradas


def _fila_de_id(ws, headers, hoja, id_):
    """Número de fila (1-based) del ID, buscado en el momento. Error si no está o está repetido."""
    col_id = ID_COLUMNA[hoja]
    if col_id not in headers:
        raise KeyError(f"La hoja {hoja} no tiene la columna {col_id}")
    ids = ws.col_values(headers.index(col_id) + 1, value_render_option=ValueRenderOption.unformatted)
    filas = [i for i, v in enumerate(ids, start=1) if i > 1 and parse_id(v) == int(id_)]
    if not filas:
        raise KeyError(f"No existe {col_id} = {id_} en {hoja}")
    if len(filas) > 1:
        raise ValueError(f"{col_id} = {id_} está repetido en {hoja} (filas {filas}); corregilo en el Sheet")
    return filas[0]


def actualizar(sheet, hoja, id_, cambios):
    """Actualiza solo las celdas indicadas de la fila de ese ID. Devuelve las columnas ignoradas."""
    ws = _hoja(sheet, hoja)
    headers = _encabezados(ws)
    fila = _fila_de_id(ws, headers, hoja, id_)
    celdas = [Cell(fila, headers.index(c) + 1, _a_celda(v)) for c, v in cambios.items() if c in headers]
    if celdas:
        ws.update_cells(celdas, value_input_option=ValueInputOption.raw)
        invalidar_cache()
    return [c for c in cambios if c not in headers]


def borrar(sheet, hoja, id_):
    """Borra la fila de ese ID (buscada justo antes de borrar)."""
    ws = _hoja(sheet, hoja)
    fila = _fila_de_id(ws, _encabezados(ws), hoja, id_)
    ws.delete_rows(fila)
    invalidar_cache()
