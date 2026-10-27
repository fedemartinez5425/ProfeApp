from datetime import date

import pytest

from conftest import HOY, dia, planilla_nueva, planilla_vieja


def sin_errores(at):
    assert not at.exception, [e.value for e in at.exception]


def ultima_clase(planilla):
    return planilla.hojas['Clases'].registros()[-1]


@pytest.mark.parametrize('fabrica', [planilla_vieja, planilla_nueva], ids=['sheet_viejo', 'sheet_nuevo'])
def test_abre_sin_errores(abrir_app, fabrica):
    at = abrir_app(fabrica())
    sin_errores(at)
    assert len(at.tabs) >= 5


def test_aviso_formato_viejo(abrir_app):
    at = abrir_app(planilla_vieja())
    textos = " ".join(m.value for m in at.markdown)
    assert 'MontoCobrado' in textos and 'Tarifas' in textos


def test_abre_con_planilla_vacia(abrir_app):
    from fake_gspread import FakeSpreadsheet
    from conftest import ENC_ALUMNOS, ENC_CLASES_VIEJO
    at = abrir_app(FakeSpreadsheet({'Clases': [ENC_CLASES_VIEJO], 'Alumnos': [ENC_ALUMNOS]}))
    sin_errores(at)
    # La pestaña Alumnos sigue funcionando aunque no haya clases (antes st.stop() cortaba todo)
    assert any(b.label == "✅ Agregar Alumno" for b in at.button)


def test_regresion_precio_de_alumno_que_no_es_el_primero(abrir_app):
    """Bug v2: se guardaba el precio de la ficha en lugar del tipeado."""
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    assert at.selectbox(key="reg_alumno").value == 1        # el primero es Ana
    at.selectbox(key="reg_alumno").set_value(2).run()       # Bruno, ficha $6.000
    at.number_input(key="reg_tarifa_2").set_value(8000.0).run()
    at.number_input(key="reg_horas_2").set_value(2.0).run()
    assert at.number_input(key="reg_monto_2").value == 16000.0   # total en vivo
    at.button(key="reg_guardar").click().run()
    sin_errores(at)
    fila = ultima_clase(planilla)
    assert fila['ID_Alumno'] == 2 and fila['Alumno'] == 'Bruno Díaz'
    assert fila['PrecioHora'] == 8000 and fila['Duración(h)'] == 2 and fila['Total'] == 16000
    assert fila['ID_Clase'] == 4


def test_monto_pisado_a_mano_se_guarda_tal_cual(abrir_app):
    planilla = planilla_nueva()
    at = abrir_app(planilla)
    at.selectbox(key="reg_alumno").set_value(2).run()
    at.number_input(key="reg_horas_2").set_value(2.0).run()
    at.number_input(key="reg_monto_2").set_value(15000.0).run()
    at.number_input(key="reg_horas_2").set_value(2.5).run()     # cambiar horas no pisa el monto manual
    assert at.number_input(key="reg_monto_2").value == 15000.0
    at.button(key="reg_guardar").click().run()
    sin_errores(at)
    fila = ultima_clase(planilla)
    assert fila['MontoCobrado'] == 15000 and fila['Total'] == 15000
    assert fila['HorasReales'] == 2.5 and fila['PrecioHora'] == 6000
    assert isinstance(fila['MontoCobrado'], (int, float))        # número real, no texto
    assert fila['Fecha'] == HOY.isoformat()


def test_escrituras_sin_clear_y_raw(abrir_app):
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    at.button(key="reg_guardar").click().run()
    sin_errores(at)
    llamadas = [l for ws in planilla.hojas.values() for l in ws.llamadas]
    escrituras = [l for l in llamadas if l[0] != 'get_values']
    assert escrituras and all('RAW' in l[1].upper() for l in escrituras if l[0] == 'append_row')
    # Sheet viejo: la fila nueva respeta sus 10 columnas
    assert len(planilla.hojas['Clases'].filas[-1]) == 10


def test_duplicado_pide_confirmacion(abrir_app):
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    # Ana ya tiene una clase hace 3 días
    at.date_input(key="reg_fecha_1").set_value(date.fromisoformat(dia(3))).run()
    assert any('Ya hay 1 clase' in w.value for w in at.warning)
    assert at.button(key="reg_guardar").disabled
    at.checkbox(key="reg_dup_ok_1").check().run()
    at.button(key="reg_guardar").click().run()
    sin_errores(at)
    assert len(planilla.hojas['Clases'].filas) == 5


def test_doble_clic_no_duplica(abrir_app):
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    at.number_input(key="reg_horas_1").set_value(1.0).run()
    at.button(key="reg_guardar").click().run()
    n = len(planilla.hojas['Clases'].filas)
    # Segundo envío idéntico (doble clic): no se guarda otra vez
    at.date_input(key="reg_fecha_1").set_value(HOY).run()
    at.number_input(key="reg_horas_1").set_value(1.0).run()
    at.checkbox(key="reg_dup_ok_1").check().run()
    at.button(key="reg_guardar").click().run()
    assert len(planilla.hojas['Clases'].filas) == n


def test_selector_de_anio_dinamico(abrir_app):
    at = abrir_app(planilla_vieja())
    sel = at.selectbox(key="dash_año")
    assert sel.value == HOY.year
    assert HOY.year in sel.options or str(HOY.year) in sel.options


def test_login_con_secret_y_respaldo(abrir_app):
    at = abrir_app(planilla_vieja(), password=False)
    # Sin app_password: banner rojo visible aun estando logueado
    assert any('app_password' in e.value for e in at.error)


def test_volver_a_un_alumno_no_deja_la_tarifa_en_cero(abrir_app):
    """Revisor: al cambiar de alumno Streamlit borra el valor del widget pero no el flag 'manual'."""
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    at.selectbox(key="reg_alumno").set_value(2).run()
    at.number_input(key="reg_tarifa_2").set_value(8000.0).run()
    at.number_input(key="reg_monto_2").set_value(15000.0).run()
    at.selectbox(key="reg_alumno").set_value(1).run()
    at.selectbox(key="reg_alumno").set_value(2).run()
    assert at.number_input(key="reg_tarifa_2").value == 6000.0
    assert at.number_input(key="reg_monto_2").value > 0


def test_monto_cero_pide_confirmacion(abrir_app):
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    at.number_input(key="reg_monto_1").set_value(0.0).run()
    assert at.button(key="reg_guardar").disabled
    at.checkbox(key="reg_cero_ok_1").check().run()
    assert not at.button(key="reg_guardar").disabled


def test_fecha_alta_como_numero_de_serie():
    from logica import filas_a_df, normalizar_alumnos
    df = normalizar_alumnos(filas_a_df([['ID_Alumno', 'Nombre', 'FechaAlta'], [1, 'A', 46296], [2, 'B', '2026-01-02']]))
    assert df['FechaAlta'].tolist() == ['2026-10-01', '2026-01-02']
