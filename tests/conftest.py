import sys
from datetime import date, timedelta
from pathlib import Path

import gspread
import pytest
import streamlit as st
from google.oauth2.service_account import Credentials
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_gspread import FakeClient, FakeSpreadsheet  # noqa: E402

HOY = date.today()


def dia(n):
    """Fecha ISO de hace n días."""
    return (HOY - timedelta(days=n)).isoformat()


ENC_ALUMNOS = ['ID_Alumno', 'Nombre', 'Materia', 'Curso', 'Teléfono', 'Contacto', 'Día', 'Frecuencia',
               'PrecioHora', 'Modalidad', 'FechaAlta', 'Estado', 'Observaciones']
ENC_CLASES_VIEJO = ['ID_Clase', 'Fecha', 'ID_Alumno', 'Alumno', 'Materia', 'Duración(h)', 'PrecioHora',
                    '¿Pagada?', 'Método', 'Total']
ENC_CLASES_NUEVO = ENC_CLASES_VIEJO + ['MontoCobrado', 'HorasReales', 'Revisar', 'NotaRevision']
ENC_TARIFAS = ['ID_Tarifa', 'ID_Alumno', 'Desde', 'Tipo', 'Monto', 'Nota']


def planilla_vieja():
    """Como el Sheet de producción hoy: todo texto, sin columnas nuevas ni hoja Tarifas."""
    return FakeSpreadsheet({
        'Clases': [
            ENC_CLASES_VIEJO,
            ['1', dia(40), '1', 'Ana Pérez', 'Matemática', '1.5', '4000.0', 'Sí', 'Transferencia', '6000.0'],
            ['2', dia(10), '2', 'Bruno Díaz', 'Física', '2.0', '6000.0', 'Sí', 'Efectivo', '12000.0'],
            ['3', dia(3), '1', 'Ana Pérez', 'Matemática', '2.5', '4000.0', 'No', 'Transferencia', '10000.0'],
        ],
        'Alumnos': [
            ENC_ALUMNOS,
            ['1', 'Ana Pérez', 'Matemática', 'Secundaria', '2645000001', 'Madre', '', '', '4000.0',
             'Presencial', dia(60), 'Activo', ''],
            ['2', 'Bruno Díaz', 'Física', 'Universidad', '', '', '', '', '6000.0',
             'Presencial', dia(30), 'Activo', ''],
            ['3', 'Carla Gómez', 'Matemática', 'Secundaria', '', '', '', '', '7500.0',
             'Presencial', dia(90), 'Pausado', ''],
            ['4', 'Darío Luna', 'Matemática', 'Secundaria', '', '', '', '', '5000.0',
             'Presencial', dia(200), 'Baja', ''],
        ],
    })


def planilla_nueva():
    """Como queda después de importar el Excel corregido: números reales, columnas y hojas nuevas."""
    return FakeSpreadsheet({
        'Clases': [
            ENC_CLASES_NUEVO,
            [1, dia(40), 1, 'Ana Pérez', 'Matemática', 1.5, 4000, 'Sí', 'Transferencia', 6000, 6000, 1.5, '', ''],
            [2, dia(10), 2, 'Bruno Díaz', 'Física', 2, 6000, 'Sí', 'Efectivo', 12000, 12000, 2, '', ''],
            [3, dia(3), 1, 'Ana Pérez', 'Matemática', 2.5, 4000, 'No', 'Transferencia', 10000, 9000, 2,
             'Sí', 'dudosa'],
        ],
        'Alumnos': [
            ENC_ALUMNOS,
            [1, 'Ana Pérez', 'Matemática', 'Secundaria', 2645000001, 'Madre', 'Lunes, Jueves', 'Semanal', 4000,
             'Presencial', dia(60), 'Activo', ''],
            [2, 'Bruno Díaz', 'Física', 'Universidad', '', '', 'Martes', 'Semanal', 6000,
             'Presencial', dia(30), 'Activo', ''],
            [3, 'Carla Gómez', 'Matemática', 'Secundaria', '', '', '', '', 7500,
             'Presencial', dia(90), 'Pausado', ''],
            [4, 'Darío Luna', 'Matemática', 'Secundaria', '', '', '', '', 5000,
             'Presencial', dia(200), 'Baja', ''],
        ],
        'Tarifas': [
            ENC_TARIFAS,
            [1, 1, dia(60), 'Hora', 4000, 'inferida'],
            [2, 2, dia(30), 'Hora', 6000, 'inferida'],
            [3, 3, dia(90), 'Hora', 7500, 'inferida'],
            [4, 4, dia(200), 'Hora', 5000, 'inferida'],
        ],
        'IPC': [['Mes', 'VariacionPct']],
    })


@pytest.fixture(autouse=True)
def limpiar_caches():
    st.cache_data.clear()
    st.cache_resource.clear()
    yield
    st.cache_data.clear()
    st.cache_resource.clear()


@pytest.fixture
def abrir_app(monkeypatch):
    """abrir_app(planilla) → AppTest ya corrido, logueado y conectado a la planilla falsa."""

    def _abrir(planilla, password=True):
        monkeypatch.setattr(gspread, 'authorize', lambda creds: FakeClient(planilla))
        monkeypatch.setattr(Credentials, 'from_service_account_info',
                            classmethod(lambda cls, info, scopes=None: object()))
        at = AppTest.from_file(str(RAIZ / 'app.py'), default_timeout=60)
        at.secrets['gcp_service_account'] = {'type': 'service_account'}
        at.secrets['spreadsheet'] = {'name': 'Clases Particulares'}
        if password:
            at.secrets['app_password'] = 'secreta'
        at.session_state['autorizado'] = True
        at.run()
        return at

    return _abrir
