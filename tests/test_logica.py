from datetime import date

import pandas as pd
import pytest

from logica import (
    clases_mismo_dia, filas_a_df, format_currency, format_hours, normalizar_alumnos,
    normalizar_clases, normalizar_tarifas, parse_fecha, parse_numero, tarifa_vigente,
)


@pytest.mark.parametrize('valor, esperado', [
    ("4000.0", 4000.0),       # texto viejo de la app v2
    (4000, 4000.0),           # número real
    (4000.0, 4000.0),
    ("10.000", 10000.0),      # punto = miles en dinero
    ("10.000,50", 10000.5),   # formato argentino completo
    ("$ 15.000", 15000.0),
    ("1.234.567", 1234567.0),
    ("6666.0", 6666.0),
    ("", None),
    (None, None),
    ("abc", None),
])
def test_parse_dinero(valor, esperado):
    assert parse_numero(valor, tipo='dinero') == esperado


@pytest.mark.parametrize('valor, esperado', [
    ("2,5", 2.5),
    ("1.5", 1.5),             # en horas el punto es decimal
    ("2.0", 2.0),
    (1.5, 1.5),
    ("3", 3.0),
])
def test_parse_horas(valor, esperado):
    assert parse_numero(valor, tipo='horas') == esperado


def test_parse_fecha_texto_y_serial():
    assert parse_fecha("2026-10-01") == pd.Timestamp(2026, 10, 1)
    assert parse_fecha("01/10/2026") == pd.Timestamp(2026, 10, 1)
    assert parse_fecha(46296) == pd.Timestamp(2026, 10, 1)   # número de serie de Sheets
    assert pd.isna(parse_fecha(""))


def test_formato_argentino():
    assert format_currency(10000) == "$ 10.000"
    assert format_currency(10000.5) == "$ 10.000,50"
    assert format_hours(2.5) == "2,5 h"
    assert format_hours(2) == "2 h"


def _clases(filas, encabezados):
    return normalizar_clases(filas_a_df([encabezados] + filas))


def test_monto_y_horas_con_respaldo():
    viejo = _clases([['1', '2026-10-01', '1', 'A', 'M', '2.5', '4000.0', 'Sí', 'T', '10000.0']],
                    ['ID_Clase', 'Fecha', 'ID_Alumno', 'Alumno', 'Materia', 'Duración(h)', 'PrecioHora',
                     '¿Pagada?', 'Método', 'Total'])
    assert viejo.iloc[0]['Monto'] == 10000 and viejo.iloc[0]['Horas'] == 2.5
    nuevo = _clases([[1, '2026-10-01', 1, 'A', 'M', 2.5, 4000, 'Sí', 'T', 10000, 9000, 2, 'Sí', 'x']],
                    ['ID_Clase', 'Fecha', 'ID_Alumno', 'Alumno', 'Materia', 'Duración(h)', 'PrecioHora',
                     '¿Pagada?', 'Método', 'Total', 'MontoCobrado', 'HorasReales', 'Revisar', 'NotaRevision'])
    fila = nuevo.iloc[0]
    assert fila['Monto'] == 9000 and fila['Horas'] == 2 and fila['PorHora'] == 4500
    assert bool(fila['ARevisar'])


def test_tarifa_vigente_por_fecha_y_respaldo():
    alumnos = normalizar_alumnos(filas_a_df([['ID_Alumno', 'Nombre', 'PrecioHora'], [1, 'A', 5000],
                                             [2, 'B', '7.500']]))
    tarifas = normalizar_tarifas(filas_a_df([
        ['ID_Tarifa', 'ID_Alumno', 'Desde', 'Tipo', 'Monto', 'Nota'],
        [1, 1, '2026-01-01', 'Hora', 4000, ''],
        [2, 1, '2026-07-01', 'Hora', 6000, ''],
    ]))
    assert tarifa_vigente(1, date(2026, 6, 30), tarifas, alumnos)[:2] == (4000, 'Hora')
    assert tarifa_vigente(1, date(2026, 7, 1), tarifas, alumnos)[:2] == (6000, 'Hora')
    # sin tarifa a esa fecha o sin hoja → ficha
    assert tarifa_vigente(1, date(2025, 1, 1), tarifas, alumnos)[0] == 5000
    assert tarifa_vigente(2, date(2026, 7, 1), None, alumnos) == (7500, 'Hora', 'Ficha')


def test_deteccion_duplicados():
    df = _clases([['1', '2026-10-13', '1', 'A', 'M', '2.5', '4000', 'Sí', 'T', '10000'],
                  ['2', '2026-10-13', '2', 'B', 'M', '2', '4000', 'Sí', 'T', '8000']],
                 ['ID_Clase', 'Fecha', 'ID_Alumno', 'Alumno', 'Materia', 'Duración(h)', 'PrecioHora',
                  '¿Pagada?', 'Método', 'Total'])
    assert len(clases_mismo_dia(df, 1, date(2026, 10, 13))) == 1
    assert len(clases_mismo_dia(df, 1, date(2026, 10, 14))) == 0
    assert len(clases_mismo_dia(df, 3, date(2026, 10, 13))) == 0
