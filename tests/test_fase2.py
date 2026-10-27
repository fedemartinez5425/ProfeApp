from datetime import timedelta

import pytest

import sheets
from conftest import HOY, dia, planilla_nueva, planilla_vieja
from logica import (cambios_historial, filas_a_df, normalizar_alumnos, normalizar_clases,
                    normalizar_tarifas, plan_aumento, tabla_editable_clases, validar_cambios)


def sin_errores(at):
    assert not at.exception, [e.value for e in at.exception]


def fila(planilla, hoja, col_id, id_):
    return next(r for r in planilla.hojas[hoja].registros() if r[col_id] in (id_, str(id_)))


# ── Capa de datos ──
@pytest.mark.parametrize('fabrica', [planilla_vieja, planilla_nueva])
def test_actualizar_solo_toca_las_celdas_de_ese_id(fabrica):
    planilla = fabrica()
    antes = [list(f) for f in planilla.hojas['Clases'].filas]
    ignoradas = sheets.actualizar(planilla, 'Clases', 2, {'Total': 13000, 'MontoCobrado': 13000})
    despues = planilla.hojas['Clases'].filas
    distintas = [(i, j) for i, (a, b) in enumerate(zip(antes, despues)) for j, (x, y) in enumerate(zip(a, b)) if x != y]
    assert all(i == 2 for i, _ in distintas)          # solo la fila del ID 2 (fila 3 del Sheet)
    assert fila(planilla, 'Clases', 'ID_Clase', 2)['Total'] == 13000
    assert ignoradas == (['MontoCobrado'] if fabrica is planilla_vieja else [])


def test_borrar_busca_por_id_y_no_por_posicion():
    planilla = planilla_nueva()
    ws = planilla.hojas['Clases']
    ws.filas[1], ws.filas[3] = ws.filas[3], ws.filas[1]   # desordenar
    sheets.borrar(planilla, 'Clases', 1)
    assert [r['ID_Clase'] for r in ws.registros()] == [3, 2]
    with pytest.raises(KeyError):
        sheets.borrar(planilla, 'Clases', 99)


def test_id_repetido_no_se_toca():
    planilla = planilla_nueva()
    planilla.hojas['Clases'].filas.append(list(planilla.hojas['Clases'].filas[1]))
    with pytest.raises(ValueError):
        sheets.actualizar(planilla, 'Clases', 1, {'Total': 1})


# ── Diferencias del editor ──
def _df(planilla):
    return normalizar_clases(filas_a_df(planilla.hojas['Clases'].filas))


def test_cambios_historial_sheet_nuevo_y_viejo():
    df = _df(planilla_nueva())
    original = tabla_editable_clases(df)
    editado = original.copy()
    editado.loc[2, 'Monto'] = 14000.0
    editado.loc[3, 'Pagada'] = True
    editado.loc[3, 'Horas'] = 2.5
    cambios = cambios_historial(original, editado, list(planilla_nueva().hojas['Clases'].filas[0]))
    assert cambios == {2: {'MontoCobrado': 14000.0, 'Total': 14000.0},
                       3: {'HorasReales': 2.5, '¿Pagada?': 'Sí'}}
    viejo = cambios_historial(original, editado, list(planilla_vieja().hojas['Clases'].filas[0]))
    assert viejo[3] == {'Duración(h)': 2.5, '¿Pagada?': 'Sí'}
    assert cambios_historial(original, original.copy(), []) == {}


def test_validar_cambios():
    assert validar_cambios({1: {'HorasReales': 0.0}})
    assert validar_cambios({1: {'MontoCobrado': -5.0, 'Total': -5.0}})
    assert not validar_cambios({1: {'MontoCobrado': 0.0, 'Total': 0.0}})


def test_plan_aumento_pct_y_monto():
    p = planilla_nueva()
    alumnos = normalizar_alumnos(filas_a_df(p.hojas['Alumnos'].filas))
    tarifas = normalizar_tarifas(filas_a_df(p.hojas['Tarifas'].filas))
    plan = plan_aumento([1, 2], 'pct', 12.5, HOY, tarifas, alumnos)
    assert plan['Nuevo'].tolist() == [4500.0, 6800.0]     # 4000 × 1,125 = 4500; 6000 × 1,125 = 6750 → 6800
    plan = plan_aumento([2], 'monto', 9000, HOY, tarifas, alumnos)
    assert plan.iloc[0]['Actual'] == 6000 and plan.iloc[0]['Nuevo'] == 9000


# ── App ──
@pytest.mark.parametrize('fabrica', [planilla_nueva, planilla_vieja], ids=['con_tarifas', 'sin_tarifas'])
def test_aplicar_aumento_y_la_clase_siguiente_lo_usa(abrir_app, fabrica):
    planilla = fabrica()
    at = abrir_app(planilla)
    at.radio(key="aum_alcance").set_value("Elegir alumnos").run()
    at.multiselect(key="aum_alumnos").select(2).run()
    at.radio(key="aum_modo").set_value("Monto nuevo").run()
    at.number_input(key="aum_monto").set_value(9000.0).run()
    at.checkbox(key="aum_ok_0").check().run()
    at.button(key="aum_aplicar").click().run()
    sin_errores(at)
    assert fila(planilla, 'Alumnos', 'ID_Alumno', 2)['PrecioHora'] == 9000
    if 'Tarifas' in planilla.hojas:
        nueva = planilla.hojas['Tarifas'].registros()[-1]
        assert (nueva['ID_Tarifa'], nueva['ID_Alumno'], nueva['Monto'], nueva['Desde']) == (5, 2, 9000, HOY.isoformat())
    # La clase siguiente de ese alumno toma la tarifa nueva
    at.selectbox(key="reg_alumno").set_value(2).run()
    assert at.number_input(key="reg_tarifa_2").value == 9000.0
    at.number_input(key="reg_horas_2").set_value(2.0).run()
    at.button(key="reg_guardar").click().run()
    nueva_clase = planilla.hojas['Clases'].registros()[-1]
    assert nueva_clase['PrecioHora'] == 9000 and nueva_clase['Total'] == 18000


def test_aumento_futuro_no_cambia_la_tarifa_de_hoy(abrir_app):
    planilla = planilla_nueva()
    at = abrir_app(planilla)
    at.radio(key="aum_alcance").set_value("Elegir alumnos").run()
    at.multiselect(key="aum_alumnos").select(1).run()
    at.date_input(key="aum_desde").set_value(HOY + timedelta(days=10)).run()
    at.checkbox(key="aum_ok_0").check().run()
    at.button(key="aum_aplicar").click().run()
    sin_errores(at)
    assert fila(planilla, 'Alumnos', 'ID_Alumno', 1)['PrecioHora'] == 4000     # ficha intacta
    assert planilla.hojas['Tarifas'].registros()[-1]['Monto'] == 4400           # +10 %
    assert at.number_input(key="reg_tarifa_1").value == 4000.0


def test_editar_ficha(abrir_app):
    planilla = planilla_nueva()
    at = abrir_app(planilla)
    at.selectbox(key="ficha_alumno").set_value(2).run()
    at.text_input(key="ficha_tel_2").input("2645999999")
    at.selectbox(key="ficha_estado_2").set_value("Baja")
    next(b for b in at.button if b.label == "💾 Guardar ficha").click().run()
    sin_errores(at)
    r = fila(planilla, 'Alumnos', 'ID_Alumno', 2)
    assert r['Teléfono'] == '2645999999' and r['Estado'] == 'Baja' and r['Nombre'] == 'Bruno Díaz'
    # Baja: ya no aparece para registrar clases
    assert 2 not in at.selectbox(key="reg_alumno").options and '2' not in at.selectbox(key="reg_alumno").options


def test_clase_de_alumno_pausado_lo_reactiva(abrir_app):
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    at.selectbox(key="reg_alumno").set_value(3).run()      # Carla, Pausado
    at.button(key="reg_guardar").click().run()
    sin_errores(at)
    assert fila(planilla, 'Alumnos', 'ID_Alumno', 3)['Estado'] == 'Activo'
    assert any('volvió a Activo' in s.value for s in at.success)


def test_borrar_clase_con_confirmacion(abrir_app):
    planilla = planilla_nueva()
    at = abrir_app(planilla)
    at.radio(key="hist_vista").set_value("A revisar").run()   # solo la clase 3
    assert at.button(key="hist_borrar").disabled
    at.checkbox(key="hist_borrar_ok_3").check().run()
    at.button(key="hist_borrar").click().run()
    sin_errores(at)
    assert [r['ID_Clase'] for r in planilla.hojas['Clases'].registros()] == [1, 2]


def test_ids_repetidos_o_vacios_no_rompen_el_historial(abrir_app):
    planilla = planilla_nueva()
    ws = planilla.hojas['Clases']
    ws.filas.append(list(ws.filas[1]))                       # ID 1 repetido
    ws.filas.append([''] + list(ws.filas[2][1:]))            # sin ID
    at = abrir_app(planilla)
    sin_errores(at)
    assert any('vacío o repetido' in w.value for w in at.warning)
    assert 1 not in at.selectbox(key="hist_borrar_id").options


def test_aumento_mensual_no_pisa_precio_hora(abrir_app):
    planilla = planilla_nueva()
    planilla.hojas['Tarifas'].filas.append([5, 2, dia(1), 'Mensual', 30000, ''])
    at = abrir_app(planilla)
    at.radio(key="aum_alcance").set_value("Elegir alumnos").run()
    at.multiselect(key="aum_alumnos").select(2).run()
    at.checkbox(key="aum_ok_0").check().run()
    at.button(key="aum_aplicar").click().run()
    sin_errores(at)
    assert planilla.hojas['Tarifas'].registros()[-1]['Monto'] == 33000
    assert fila(planilla, 'Alumnos', 'ID_Alumno', 2)['PrecioHora'] == 6000


def test_aumento_futuro_sin_hoja_tarifas_se_bloquea(abrir_app):
    at = abrir_app(planilla_vieja())
    at.date_input(key="aum_desde").set_value(HOY + timedelta(days=5)).run()
    at.checkbox(key="aum_ok_0").check().run()
    assert at.button(key="aum_aplicar").disabled
