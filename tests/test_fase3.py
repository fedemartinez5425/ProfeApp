from datetime import date

import pandas as pd

from conftest import HOY, dia, planilla_nueva, planilla_vieja
from logica import (agenda_semanal, cobros_pendientes, comparar_aumentos_ipc, dias_de_texto, filas_a_df,
                    inflacion_acumulada, link_whatsapp, normalizar_alumnos, normalizar_clases, normalizar_ipc,
                    normalizar_tarifas, promedio_mensual_historico, proyeccion_mensual, resumen_mensual,
                    telefono_whatsapp, texto_vs_inflacion)


def sin_errores(at):
    assert not at.exception, [e.value for e in at.exception]


IPC = normalizar_ipc(filas_a_df([['Mes', 'VariacionPct'], ['2026-01', '2,0'], ['2026-02', 2], ['2026-03', '3.0']]))


def test_inflacion_acumulada_compuesta_y_meses_faltantes():
    pct, faltan = inflacion_acumulada(IPC, '2026-01', '2026-04')
    assert round(pct, 4) == round((1.02 * 1.02 * 1.03 - 1) * 100, 4)
    assert faltan == []
    _, faltan = inflacion_acumulada(IPC, '2026-02', '2026-06')
    assert faltan == ['2026-04', '2026-05']


def test_aumento_contra_inflacion():
    tarifas = normalizar_tarifas(filas_a_df([
        ['ID_Tarifa', 'ID_Alumno', 'Desde', 'Tipo', 'Monto', 'Nota'],
        [1, 1, '2026-01-10', 'Hora', 10000, ''],
        [2, 1, '2026-04-01', 'Hora', 11000, ''],     # +10 % contra ~7,2 % de inflación
    ]))
    alumnos = normalizar_alumnos(filas_a_df([['ID_Alumno', 'Nombre'], [1, 'Ana']]))
    comp = comparar_aumentos_ipc(tarifas, IPC, alumnos)
    fila = comp.iloc[0]
    assert round(fila['Aumento %'], 6) == 10.0
    assert fila['Diferencia real %'] > 0
    assert texto_vs_inflacion(fila['Diferencia real %']).startswith("le ganaste a la inflación por 2,")
    assert texto_vs_inflacion(-3.21) == "le perdiste a la inflación por 3,2%"


def test_whatsapp():
    assert telefono_whatsapp('2645123029') == '2645123029'
    assert telefono_whatsapp('0264 15 4123456') == '2644123456'
    assert telefono_whatsapp('+54 9 264 512-3029') == '2645123029'
    assert telefono_whatsapp(2645123029.0) == '2645123029'
    assert telefono_whatsapp('') == '' and link_whatsapp('', 'x') is None
    assert link_whatsapp('2645123029', 'Hola 1').startswith('https://wa.me/5492645123029?text=Hola%201')


def _clases():
    return normalizar_clases(filas_a_df(planilla_nueva().hojas['Clases'].filas))


def test_resumen_mensual():
    df = normalizar_clases(filas_a_df([
        ['ID_Clase', 'Fecha', 'ID_Alumno', 'Alumno', 'Duración(h)', '¿Pagada?', 'Total'],
        [1, '2026-10-01', 1, 'Ana', 2, 'Sí', 10000],
        [2, '2026-10-08', 1, 'Ana', 1.5, 'No', 7500],
        [3, '2026-09-08', 1, 'Ana', 1.5, 'Sí', 7500],
    ]))
    texto = resumen_mensual(df, 1, 'Ana', 10, 2026)
    assert 'octubre 2026' in texto and '01/10/2026: 2 h · $ 10.000' in texto
    assert 'Total: 2 clases · 3,5 h · $ 17.500' in texto and 'Pendiente de pago: $ 7.500' in texto
    assert '08/09' not in texto


def test_cobros_pendientes_con_antiguedad():
    pend = cobros_pendientes(_clases(), HOY)
    assert pend['ID_Clase'].tolist() == [3] and pend.iloc[0]['Dias'] == 3


def test_proyeccion_y_promedio_con_meses_vacios():
    df = normalizar_clases(filas_a_df([
        ['ID_Clase', 'Fecha', 'ID_Alumno', 'Alumno', 'Duración(h)', 'Total'],
        [1, '2026-06-15', 1, 'Ana', 2, 10000],     # junio: 10.000; julio y agosto: 0
        [2, '2026-09-01', 1, 'Ana', 2, 10000],
        [3, '2026-09-08', 1, 'Ana', 2, 10000],
        [4, '2026-09-15', 1, 'Ana', 2, 10000],
        [5, '2026-09-22', 1, 'Ana', 2, 10000],
        [6, '2026-01-10', 2, 'Beto', 2, 8000],    # no está activo en los últimos 30 días
    ]))
    prom, n = promedio_mensual_historico(df, date(2026, 10, 5))
    assert n == 9 and round(prom) == round((8000 + 10000 + 40000) / 9)
    proy = proyeccion_mensual(df, date(2026, 9, 28))
    assert proy['ID_Alumno'].tolist() == [1]
    assert 0 < proy.iloc[0]['ClasesSemana'] < 1          # 5 clases en 90 días
    assert proy.iloc[0]['MontoClase'] == 10000


def test_agenda():
    assert dias_de_texto('lunes y Miercoles') == ['Lunes', 'Miércoles']
    alumnos = normalizar_alumnos(filas_a_df(planilla_nueva().hojas['Alumnos'].filas))
    agenda = agenda_semanal(alumnos)
    assert [x[1] for x in agenda['Lunes']] == ['Ana Pérez'] and [x[1] for x in agenda['Martes']] == ['Bruno Díaz']


# ── App ──
def test_app_con_ipc_cargado(abrir_app):
    planilla = planilla_nueva()
    planilla.hojas['IPC'].filas += [[dia(70)[:7], 3.5], [dia(40)[:7], '2,5'], [HOY.strftime('%Y-%m'), 2]]
    planilla.hojas['Tarifas'].filas.append([5, 2, dia(1), 'Hora', 7000, 'aumento'])
    at = abrir_app(planilla)
    sin_errores(at)
    assert any('v3.0 · 2026' in c.value for c in at.sidebar.caption)


def test_marcar_pagadas_desde_cobros(abrir_app):
    planilla = planilla_nueva()
    at = abrir_app(planilla)
    assert at.selectbox(key="cob_alumno").value == 1
    at.checkbox(key="cob_ok_0_1").check().run()
    at.button(key="cob_guardar").click().run()
    sin_errores(at)
    fila = next(r for r in planilla.hojas['Clases'].registros() if r['ID_Clase'] == 3)
    assert fila['¿Pagada?'] == 'Sí' and fila['Método'] == 'Transferencia'


def test_resumen_whatsapp_en_la_app(abrir_app):
    at = abrir_app(planilla_nueva())
    at.selectbox(key="wa_alumno").set_value(1).run()     # Ana tiene teléfono
    assert any('wa.me/5492645000001' in b.url for b in at.get('link_button'))
    assert any('Hola!' in c.value for c in at.code)


def test_editar_dias_de_la_ficha(abrir_app):
    planilla = planilla_vieja()
    at = abrir_app(planilla)
    at.selectbox(key="ficha_alumno").set_value(2).run()
    at.multiselect(key="ficha_dias_2").select('Lunes').select('Jueves')
    at.selectbox(key="ficha_frec_2").set_value('2 veces por semana')
    next(b for b in at.button if b.label == "💾 Guardar ficha").click().run()
    sin_errores(at)
    fila = next(r for r in planilla.hojas['Alumnos'].registros() if r['ID_Alumno'] == '2')
    assert fila['Día'] == 'Lunes, Jueves' and fila['Frecuencia'] == '2 veces por semana'


def test_cobros_con_fecha_vacia_no_rompe(abrir_app):
    planilla = planilla_vieja()
    planilla.hojas['Clases'].filas.append(['4', '', '2', 'Bruno Díaz', 'Física', '1', '6000', 'No', '', '6000'])
    at = abrir_app(planilla)
    sin_errores(at)
    pend = cobros_pendientes(normalizar_clases(filas_a_df(planilla.hojas['Clases'].filas)), HOY)
    assert pend['ID_Clase'].tolist() == [3, 4]          # la sin fecha va al final


def test_tarifa_recargada_igual_no_acorta_el_periodo():
    tarifas = normalizar_tarifas(filas_a_df([
        ['ID_Tarifa', 'ID_Alumno', 'Desde', 'Tipo', 'Monto', 'Nota'],
        [1, 1, '2026-01-05', 'Hora', 1000, ''],
        [2, 1, '2026-02-05', 'Hora', 1000, ''],
        [3, 1, '2026-04-05', 'Hora', 1500, ''],
    ]))
    comp = comparar_aumentos_ipc(tarifas, IPC, normalizar_alumnos(filas_a_df([['ID_Alumno', 'Nombre'], [1, 'A']])))
    assert len(comp) == 1 and comp.iloc[0]['Desde anterior'] == pd.Timestamp('2026-01-05')
