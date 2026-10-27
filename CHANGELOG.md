# Changelog

## Fase 2 — que no haga falta tocar el Sheet
- `sheets.py`: `actualizar(hoja, id, cambios)` escribe solo las celdas de la fila de ese ID (buscada en el
  momento, error si el ID no existe o está repetido) y `borrar(hoja, id)` hace `delete_rows` de esa fila.
  Ambas con `RAW` e invalidando la caché. Las columnas que no existen en el Sheet se ignoran.
- Historial editable con `st.data_editor`: fecha, horas reales, monto cobrado, pagada, método, revisar y nota.
  Solo se guardan las filas cambiadas. Borrado de una clase con confirmación. Vista rápida "Pendientes de
  cobro" y "A revisar".
- Alumnos: edición de ficha (nombre, teléfono, contacto, estado, observaciones).
- Nueva pestaña **💲 Tarifas**: historial por alumno, tarifa vigente y **Aplicar aumento** (monto nuevo o %,
  a uno, varios o todos los activos, desde una fecha). Crea filas en `Tarifas` y actualiza `PrecioHora`.

### Decisiones tomadas sin consultar
- Registrar una clase de un alumno **Pausado** lo pasa a **Activo** automáticamente (avisa en el mensaje).
  Los de **Baja** no aparecen para registrar clases.
- Aumento por %: se calcula sobre la tarifa vigente el día anterior a "Desde" y se redondea a $ 100
  (se puede desactivar). El tipo de tarifa (Hora/Clase/Mensual) se conserva.
- Aumento con "Desde" futuro: se crea la fila en `Tarifas` pero no se toca `PrecioHora` hasta esa fecha
  (Registrar Clase ya usa la tarifa según la fecha de la clase).
- Sin hoja `Tarifas`, "Aplicar aumento" solo actualiza `PrecioHora` y avisa que no queda historial.
- En el Historial, editar horas escribe `HorasReales` (o `Duración(h)` si el Sheet es viejo); editar el
  monto escribe `MontoCobrado` y `Total`.
- Las vistas "Pendientes de cobro" y "A revisar" ignoran el filtro de mes/año para no esconder deudas viejas.

## Fase 1 — urgente

### Arreglos
- **Precios que no se registraban**: "Registrar Clase" ya no usa `st.form`. El alumno se elige afuera
  (`key="reg_alumno"`) y fecha, horas, tarifa y monto tienen keys estables por alumno (`reg_<campo>_<ID>`).
  Test de regresión: `tests/test_app.py::test_regresion_precio_de_alumno_que_no_es_el_primero`.
- Nuevo campo **Monto cobrado**, precargado con horas × tarifa vigente a la fecha y editable. Se guarda en
  `MontoCobrado` y en `Total`. El total se ve en vivo.
- Aviso de clase del mismo alumno en la misma fecha con confirmación, y protección contra doble clic.
- Se acabó `ws.clear()`: las altas usan `append_row` con `RAW` (capa `sheets.py`).
- Lectura con `UNFORMATTED_VALUE` y parser nuevo (`logica.parse_numero`): `"4000.0"`, `"10.000"`,
  `"10.000,50"`, `"2,5"`, `"1.5"` (horas), números reales y fechas como número de serie.
- Selector de año dinámico (años con datos + el actual, abre en el actual). El Historial filtra por mes y año.
- El Dashboard sin clases ya no corta la app (`st.stop()` eliminado).
- Métricas de ingresos con `MontoCobrado` (respaldo `Total`), horas con `HorasReales` (respaldo `Duración(h)`).
- Alumnos y gráficos cruzan por `ID_Alumno`.
- Login con `st.secrets["app_password"]`; si falta, usa la contraseña anterior y muestra un banner rojo.
- `requirements.txt` con versiones fijas; `use_container_width` → `width="stretch"`; sin `groupby().apply`.
- Precio por defecto de alumno nuevo = última tarifa cargada (antes $4.000 fijo).

- Revisión previa al push (revisor-codigo): la tarifa quedaba en $0 al volver a un alumno cuya tarifa se
  había tocado (Streamlit borra el valor del widget oculto); el monto $0 ahora pide confirmación; alta de
  alumno no se reporta como fallida si solo falla la tarifa; Historial y gráfico apilado cruzan por ID;
  `FechaAlta` se normaliza a ISO; hook de secretos más estricto y que falla cerrado.
- Nota: el commit `aa680ea` ("new fixes", hecho a mano) subió una versión intermedia de la fase 1 con el
  `requirements.txt` viejo; el commit de cierre de la fase 1 la completa.

### Decisiones tomadas sin consultar
- El aviso "Configurá app_password" se muestra solo después de entrar, no en la pantalla de login, para no
  avisarle a un visitante que está activa la contraseña de respaldo.
- Registrar Clase muestra alumnos `Activo` y `Pausado` (estos al final, marcados); `Baja` no aparece.
- Horas por defecto = las de la última clase del alumno (1,5 h si no tiene).
- Si la tarifa vigente es `Mensual`, el monto sugerido es $0 y hay que cargarlo a mano; si es `Clase`, el monto
  sugerido es la tarifa sin multiplicar por horas.
- Cambiar la fecha recalcula la tarifa vigente salvo que la hayas tocado a mano; un botón "↺" vuelve al cálculo.
- Doble clic: se ignora un segundo guardado idéntico (alumno, fecha, horas, monto) dentro de 30 segundos.
- Con el Sheet viejo, las columnas nuevas que no existen simplemente no se escriben (el monto queda en
  `Total` y las horas en `Duración(h)`); la app no agrega columnas al Sheet por su cuenta.
- Pendiente de cobro = toda clase cuyo `¿Pagada?` no sea "Sí".
- `requirements.txt` fija versiones probadas en Python 3.12 y 3.14 (pandas 3 y Streamlit 1.66 piden Python ≥ 3.11).

### Corrección de datos (Excel)
- `scripts/corregir_datos.py` genera `Clases Particulares - corregido.xlsx` (respuestas del 26/10/2026):
  - 7 → $14.000; 22 y 26 → $10.000; 25 → $13.000 (`Total` igualado a `MontoCobrado`).
  - 56, 58 ($20.000 confirmado), 66 y 67 (dos clases distintas): sin cambios.
  - 43, 63 y 64: `Revisar = Sí` con nota (sin confirmar).
  - Tarifas inferidas excluyendo las clases a revisar. Si la ficha coincide con una tarifa anterior del
    historial se considera desactualizada (César Rius $5.000 → $10.000; Ramiro Leiva $6.666 → $6.500).
  - Estado `Pausado` para quien no tuvo clases en los 60 días previos al 26/10/2026 (Octavio Narvaez queda Activo).
  - Hoja `IPC` vacía (solo encabezados) para que la cargues vos.
