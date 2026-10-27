# Prompt para Claude Code — ProfeApp v3 (fases 1, 2 y 3)

> Cómo usarlo: abrí Claude Code en la carpeta `ProfeApp` y pegá todo lo que está debajo de la línea.
> Antes de pegarlo, completá la tabla de la sección 3 si sabés los datos reales. Si la dejás vacía, Claude Code te va a preguntar una sola vez.

---

Sos el desarrollador a cargo de ProfeApp, mi app de gestión de clases particulares. Es una app Streamlit de un solo archivo (`app.py`) desplegada en Streamlit Community Cloud desde la rama `main` de `github.com/fedemartinez5425/ProfeApp`. **Push a `main` = deploy a producción.** Lee y escribe en un Google Sheet ("Clases Particulares", hojas `Clases` y `Alumnos`) con una cuenta de servicio cuyas credenciales están en `st.secrets["gcp_service_account"]` y el nombre de la planilla en `st.secrets["spreadsheet"]["name"]`.

Tu trabajo es implementar las 3 fases de abajo **en la rama `main`, sin ramas de prueba**, y dejar la app en producción. Acepto que algo falle, pero tu estándar es que no falle: cada cambio tiene que ser compatible con los datos que hay hoy en producción y verificado con tests antes de cada push.

## 0. Reglas que no se negocian

1. **Nunca leas, muestres, copies ni commitees** `profeapp2-*.json` (clave de la cuenta de servicio) ni ningún `*.xlsx`. El primer commit es un `.gitignore` que los excluya. Antes de cada commit corré `git status` y verificá que no aparezcan.
2. **Compatibilidad hacia atrás obligatoria.** Yo copio los datos a Google Sheets a mano y puede pasar un rato entre tu push y mi copia. La app nueva tiene que funcionar con el Sheet **viejo** (sin columnas nuevas, sin hoja `Tarifas`, números guardados como texto `"4000.0"`) y con el **nuevo**. Si falta una columna u hoja: usar un valor por defecto y mostrar un aviso discreto, nunca romper.
3. **Nunca borrar y reescribir una hoja entera** (`ws.clear()` está prohibido). Alta = `append_row`. Edición = actualizar solo las celdas o filas de ese ID. Borrado = `delete_rows` de esa fila, buscada por ID justo antes de borrar.
4. **El Sheet es la fuente de verdad.** Cruzar siempre por `ID_Alumno` / `ID_Clase`, nunca por nombre.
5. Formato argentino en pantalla: `$ 10.000`, `2,5 h`, fechas `dd/mm/aaaa`. En el Sheet: fechas ISO `aaaa-mm-dd` como texto y números como números reales de Python (escritura con `value_input_option="RAW"`). **No uses `USER_ENTERED`**: la planilla tiene configuración regional es-AR y convertiría `1.5` en otra cosa.
6. Antes de **cada** push: tests en verde, `python -m py_compile app.py` sin errores, smoke test de la app levantada y revisión del diff por el subagente revisor (ver sección 5). Si algo falla, lo arreglás antes del push. No pushees con tests en rojo.
7. Commits chicos con mensajes en español, por lo menos uno por fase. Push al final de cada fase, no al final de todo.
8. No me hagas preguntas salvo las de la sección 3 (una sola vez, todas juntas) y la confirmación final de la sección 6. Para todo lo demás decidí vos con criterio y dejalo anotado en `CHANGELOG.md`.

## 1. Diagnóstico (ya verificado; no lo vuelvas a investigar desde cero)

**Bug principal: los aumentos de precio no se registran.** En la pestaña "Registrar Clase", el `st.selectbox` de alumno está **dentro** del `st.form`. El formulario se dibuja con el primer alumno de la lista. Si elijo otro alumno y escribo un precio nuevo, al enviar se vuelve a crear el `number_input` de precio con otro `value` por defecto (el de la ficha), así que Streamlit lo trata como otro widget y **descarta el precio tipeado**. Se guarda el de la ficha. Lo reproduje con `streamlit.testing.v1.AppTest`: pedí 2 h × $8.000 para un alumno con ficha de $6.000 y se guardó 2 h × $6.000. Las horas sí se respetan, y por eso yo inflaba horas para que el total diera lo que cobré. Encima no existe ninguna pantalla para editar el precio de un alumno.

Arreglo mínimo probado: sacar el selector de alumno fuera del form (`key="reg_alumno"`) y darle al precio `key=f"reg_precio_{id_alumno}"`.

**Otros bugs (los números de línea son del `app.py` actual):**

| # | Dónde | Problema |
|---|---|---|
| 1 | `save_data` l.229 | `ws.clear()` + reescribir todo: si falla a mitad de camino se pierde la hoja |
| 2 | Tabs Alumnos/Historial | No se puede editar ni borrar clases o alumnos, ni marcar una clase como pagada, ni dar de baja |
| 3 | Registrar Clase | Un doble clic duplica la clase; no hay control de duplicados |
| 4 | Dashboard l.318 | Año `[2024,2025,2026]` con `index=1`: siempre abre en 2025 (vacío) |
| 5 | Registrar Clase l.539 | La tarjeta de Total está dentro del form y no se actualiza en vivo |
| 6 | `save_data` l.233 | Todo se guarda como texto (`"4000.0"`) |
| 7 | `parse_numeric` l.156 | `"10.000"` se lee como 10 (en dinero, el punto es separador de miles) |
| 8 | Historial l.617 | El filtro de mes ignora el año |
| 9 | Dashboard l.306 | `st.stop()` sin clases corta toda la app, incluida la pestaña Alumnos |
| 10 | Alumnos l.456 y gráficos | Merge por nombre en lugar de ID |
| 11 | Análisis l.723 | "Alumnos activos" cuenta todos los que dicen "Activo"; la proyección ignora los meses sin clases |
| 12 | `requirements.txt` | Sin versiones fijas; `use_container_width` está deprecado; `groupby().apply` da aviso en pandas 3 |
| 13 | Alumnos l.474 | Precio por defecto de alumno nuevo: $4.000 (mis tarifas actuales van de $7.500 a $10.000) |
| 14 | Login l.146 | Contraseña fija en el código (`"tu_contraseña_aqui"`) |

Además, `get_all_records()` lee valores **formateados**. Usá `value_render_option="UNFORMATTED_VALUE"` y un parser que acepte números reales, texto viejo `"4000.0"`, `"10.000"` y `"10.000,50"`, distinguiendo columnas de dinero (punto = miles) y de horas (punto o coma = decimal).

## 2. Modelo de datos nuevo

El dato que manda pasa a ser **lo que cobré**, no horas × precio.

**Hoja `Clases`** — conservar todas las columnas actuales en el mismo orden y agregar al final:
- `MontoCobrado` (número): lo que efectivamente cobré. Es la base de todas las métricas de ingresos.
- `HorasReales` (número): horas reales. Si está vacía, usar `Duración(h)`.
- `Revisar` (`Sí` / vacío) y `NotaRevision` (texto): para registros dudosos.
- `Total` se sigue escribiendo, con el mismo valor que `MontoCobrado`, por compatibilidad. Si `MontoCobrado` está vacío (Sheet viejo), usar `Total`.
- `$/hora efectivo` = `MontoCobrado / HorasReales`, siempre calculado y nunca guardado.

**Hoja `Tarifas`** (nueva): `ID_Tarifa, ID_Alumno, Desde (aaaa-mm-dd), Tipo (Hora|Clase|Mensual), Monto, Nota`. La tarifa vigente de un alumno a una fecha es la de `Desde` más reciente ≤ esa fecha. Si la hoja no existe, la app usa `Alumnos.PrecioHora` y muestra un aviso con instrucciones para crearla.

**Hoja `Alumnos`**: igual que hoy. `Estado` acepta `Activo | Pausado | Baja`. `PrecioHora` queda como espejo de la tarifa vigente (la app lo actualiza al aplicar un aumento).

**Hoja `IPC`** (opcional, fase 3): `Mes (aaaa-mm), VariacionPct`. La cargo yo a mano; no llames a APIs externas.

## 3. Corrección de datos (Excel)

En la carpeta hay una copia del Sheet: `Clases Particulares.xlsx`. **No modifiques el original.** Generá `Clases Particulares - corregido.xlsx` (ignorado por git) con:

1. `Clases` con las columnas nuevas. Regla general: `MontoCobrado = Total` (los montos son reales; lo que yo distorsionaba eran las horas o el precio por hora) y `HorasReales = Duración(h)`, salvo en los registros de esta tabla.
2. Registros dudosos. Si mi columna de respuesta está completa, aplicala. Si está vacía, **preguntame una sola vez, todos juntos al empezar**. Si te respondo "no sé" o no respondo, dejá `MontoCobrado = Total`, `HorasReales = Duración(h)`, `Revisar = Sí` y la descripción en `NotaRevision`.

| ID_Clase | Cargado hoy | Sospecha | Mi respuesta (horas reales / monto real / borrar) |
|---|---|---|---|
| 58 | 2 h × $4.000, Total $20.000 | El total no coincide (debería ser $8.000) | |
| 66 y 67 | 2,5 h × $4.000 = $10.000, mismo alumno y fecha | Duplicado por doble envío | |
| 56 | 3 h × $6.666, Total $20.000 | Precio forzado; el total no coincide ($19.998) | |
| 63 | 2,5 h × $4.000 = $10.000 | Probable 2 h × $5.000 | |
| 64 | 2,5 h × $4.000 = $10.000 | Ficha $6.000; $4.000 es el precio que el formulario mostraba por defecto | |
| 43 | 1 h × $10.000 | Probable 2 h × $5.000 | |
| 7 | 3 h × $4.667 = $14.001 | Monto real $14.000 | |
| 26 | 1,5 h × $6.666 = $9.999 | Monto real $10.000 | |
| 22 | 1,5 h × $6.666 = $9.999 | Monto real $10.000 | |
| 25 | 2 h × $6.666 = $13.332 | ¿$13.333 o $13.000? | |

3. Hoja `Tarifas` armada a partir del historial: para cada alumno, una fila por cada cambio de $/hora efectivo, con `Desde` igual a la fecha de la primera clase a ese precio. Más una fila con la tarifa actual de la ficha cuando no coincida con el historial. Marcá con `Nota = "inferida"` las filas deducidas.
4. `Alumnos`: `Estado = Pausado` para quienes no tienen clases en los últimos 60 días al 26/10/2026, y `Activo` para el resto. Octavio Narvaez (ID 14) queda `Activo` porque es alta reciente. Actualizá `PrecioHora` a la tarifa vigente.
5. Todas las celdas numéricas como **números reales** (no texto) y las fechas como texto ISO.
6. Una hoja `LEEME` con el detalle de cada cambio hecho a los datos (ID, columna, antes → después, motivo).
7. Script reproducible `scripts/corregir_datos.py` que genere el Excel corregido a partir del original. Corré el script y validalo con un subagente `data-auditor` (sección 5).

## 4. Fases

### Fase 1 — urgente
- [ ] `.gitignore` (`*.json`, `*.xlsx`, `.streamlit/secrets.toml`, `__pycache__/`, `.venv/`) y verificar que la clave no esté trackeada.
- [ ] Formulario "Registrar Clase": selector de alumno fuera del form. Fecha, horas, tarifa y monto con keys estables por alumno, y el total en vivo (fuera del form o sin form, con un botón de guardado y protección contra doble envío vía `st.session_state`).
- [ ] Campo **Monto cobrado** precargado con horas × tarifa vigente a la fecha, que se puede pisar. Se guarda en `MontoCobrado` y en `Total`.
- [ ] Aviso si ya existe una clase del mismo alumno en la misma fecha, con confirmación para guardar igual.
- [ ] Selector de año dinámico (años presentes en los datos más el actual; por defecto, el actual). El filtro de mes del Historial también filtra por año.
- [ ] Login: `st.secrets.get("app_password")`. Si el secret no existe, usar la contraseña actual como respaldo y mostrar un banner rojo "Configurá app_password en Secrets", así no me quedo afuera de producción.
- [ ] Sacar el `st.stop()` del Dashboard sin datos.
- [ ] Parser numérico nuevo y lectura con `UNFORMATTED_VALUE`.
- [ ] Todas las métricas de ingresos usan `MontoCobrado` (con respaldo en `Total`) y las de horas usan `HorasReales` (con respaldo en `Duración(h)`).
- [ ] `requirements.txt` con versiones fijas que hayas instalado y probado localmente; reemplazar `use_container_width` y el `groupby().apply` deprecado.
- [ ] Generar el Excel corregido (sección 3).
- [ ] Tests (sección 5), commit y push.

### Fase 2 — que no haga falta tocar el Sheet
- [ ] Capa de datos `sheets.py` con funciones `leer(hoja)`, `agregar(hoja, fila_dict)`, `actualizar(hoja, id, cambios_dict)` y `borrar(hoja, id)`. Las columnas se mapean por nombre de encabezado (nunca por posición fija), así que funciona con hojas viejas y nuevas. Escritura `RAW`. Invalida la caché después de cada escritura.
- [ ] Historial: edición con `st.data_editor` de las columnas editables (fecha, horas reales, monto, pagada, método, revisar). Al guardar, solo se actualizan las filas cambiadas. Borrado con confirmación. Filtro rápido "Pendientes de cobro" y "A revisar".
- [ ] Alumnos: editar ficha (teléfono, contacto, estado, observaciones). Nuevo alumno con precio por defecto igual al de la última tarifa cargada.
- [ ] Tarifas: ver el historial por alumno y el botón **"Aplicar aumento"** (monto nuevo o %, a uno, varios o todos los activos, desde una fecha). Crea filas en `Tarifas` y actualiza `Alumnos.PrecioHora`.
- [ ] Todo cruce por ID.
- [ ] Tests, commit y push.

### Fase 3 — potenciar
- [ ] Pestaña "Tarifas y aumentos": $/hora efectivo y $/clase por alumno en el tiempo. Si existe la hoja `IPC`, comparar cada aumento con la inflación acumulada desde el aumento anterior ("le ganaste / le perdiste a la inflación por X%").
- [ ] Resumen mensual por alumno listo para WhatsApp: texto con clases, horas y total del mes, botón para copiar y link `https://wa.me/549<teléfono>` cuando haya teléfono.
- [ ] Panel de cobros pendientes con antigüedad en días.
- [ ] Proyección basada en los alumnos activos de los últimos 30 días y su frecuencia real, contando los meses sin clases.
- [ ] Agenda semanal con `Día` y `Frecuencia` de Alumnos (editables desde la ficha).
- [ ] Sidebar con la versión real (`v3.0 · 2026`) y la fecha del último deploy.
- [ ] Tests, commit y push.

## 5. Infraestructura de Claude Code que tenés que crear

**`CLAUDE.md`** (en la raíz, conciso, en español): qué es la app, que push a `main` es producción, cómo correr local (`streamlit run app.py` con `.streamlit/secrets.toml` local y gitignoreado), cómo correr tests, el esquema de las hojas, las reglas de la sección 0 y el flujo de corrección de datos por Excel → importación manual a Sheets.

**Skills** en `.claude/skills/<nombre>/SKILL.md`:
- `deploy-produccion`: checklist previo al push (tests, py_compile, smoke test con `streamlit run` headless y un request HTTP a `localhost:8501`, `git status` sin secretos, revisión del subagente revisor, push, avisarme qué secret o paso manual hace falta).
- `migrar-esquema-sheet`: cómo agregar una columna u hoja de forma compatible (agregar al final, valor por defecto en lectura, nunca renombrar ni reordenar, actualizar el Excel corregido y la sección de esquema de `CLAUDE.md`).
- `corregir-datos-excel`: cómo auditar y corregir el Excel con `scripts/corregir_datos.py`, registrar los cambios en `LEEME` y darme las instrucciones de importación.

**Subagentes** en `.claude/agents/<nombre>.md` (con `description`, `tools` mínimos y modelo):
- `revisor-codigo`: solo lectura. Revisa el diff contra las reglas de la sección 0 (sobre todo compatibilidad con el Sheet viejo, `ws.clear`, secretos y keys de widgets dentro de forms) y devuelve hallazgos ordenados por gravedad. Se usa antes de cada push.
- `data-auditor`: solo lectura más Python. Valida el Excel corregido: `MontoCobrado` presente, sin duplicados no explicados, horas > 0, tarifas consistentes, tipos numéricos reales y totales por mes antes y después (que solo cambien donde lo indica `LEEME`).
- `tester-streamlit`: escribe y corre tests con `streamlit.testing.v1.AppTest`.

**Hooks** en `.claude/settings.json`: un `PreToolUse` sobre `Bash` que bloquee `git add` y `git commit` si hay en stage un `*.json` con `private_key` o un `*.xlsx`. Además, `permissions.deny` de lectura para `profeapp2-*.json`.

**Tests** en `tests/`, con pytest y un Google Sheet falso en memoria (mockear `gspread.authorize` y `Credentials.from_service_account_info`; inyectar `secrets` y `session_state["autorizado"]=True` en `AppTest`). Como mínimo:
- Regresión del bug principal: elegir un alumno que no sea el primero, cargar un precio distinto al de la ficha y guardar. Lo guardado tiene que ser lo cargado.
- El monto cobrado pisado a mano se guarda tal cual.
- La app abre sin errores con el Sheet **viejo** (sin columnas nuevas, sin `Tarifas`, todo como texto) y con el **nuevo**.
- Ninguna escritura llama a `clear()`.
- Parser: `"4000.0"`, `4000`, `"10.000"`, `"10.000,50"`, `"2,5"` y `"1.5"` (horas).
- Aplicar un aumento crea la tarifa y la clase siguiente la usa.
- Detección de duplicados.

Python y dependencias en un `.venv` local. Estamos en Windows: usá rutas y comandos compatibles.

## 6. Cierre

Al final, antes del último push, mostrame en un solo mensaje:
1. Qué hiciste por fase y los hashes de commit.
2. **Pasos manuales en orden**, explicados para alguien no técnico:
   - Agregar `app_password` en Streamlit Cloud → Settings → Secrets.
   - Importar el Excel corregido a Google Sheets: Archivo → Importar → Subir → por cada hoja, "Reemplazar hoja actual" (o "Insertar hojas nuevas" para `Tarifas`, `IPC` y `LEEME`). **No copiar y pegar**, porque la configuración regional puede romper los decimales. Los nombres de hoja y los encabezados tienen que quedar exactamente iguales.
   - Verificar en la app que el total de octubre coincida con el del `LEEME`.
3. Los registros que quedaron con `Revisar = Sí`.
4. Cualquier decisión que hayas tomado sin consultarme.

Pedime confirmación solo para el push final de la fase 3. Las fases 1 y 2 pushealas apenas pasen los tests.
