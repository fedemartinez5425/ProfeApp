# ProfeApp

App Streamlit para gestionar clases particulares (Federico Martínez). Lee y escribe un Google Sheet
("Clases Particulares") con una cuenta de servicio.

**Push a `main` = deploy a producción** (Streamlit Community Cloud, `github.com/fedemartinez5425/ProfeApp`).
Antes de cada push: skill `deploy-produccion`.

## Archivos
- `app.py`: UI (pestañas). `sheets.py`: acceso a Sheets (`leer`, `agregar`, `actualizar`, `borrar`).
  `logica.py`: lógica pura (parser, normalización, tarifas, métricas), sin Streamlit.
- Pestañas: Dashboard, Alumnos (alta y ficha), Registrar Clase, Historial (editable), Cobros y resúmenes
  (WhatsApp), Tarifas (aumentos, gráficos, IPC), Agenda, Análisis (proyección).
- `scripts/corregir_datos.py`: genera el Excel corregido. `tests/`: pytest + AppTest con Sheet falso.

## Correr local (Windows)
```bash
python -m venv .venv && .venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m streamlit run app.py      # necesita .streamlit/secrets.toml (gitignoreado)
.venv\Scripts\python -m pytest -q
```
`.streamlit/secrets.toml`: `app_password = "..."`, `[gcp_service_account]` (contenido de la clave JSON),
`[spreadsheet] name = "Clases Particulares"`.

## Esquema de las hojas
- **Clases**: `ID_Clase, Fecha, ID_Alumno, Alumno, Materia, Duración(h), PrecioHora, ¿Pagada?, Método, Total,`
  `MontoCobrado, HorasReales, Revisar, NotaRevision`. Ingresos = `MontoCobrado` (respaldo `Total`);
  horas = `HorasReales` (respaldo `Duración(h)`); `$/h efectivo` se calcula, no se guarda.
  `Total` se escribe igual a `MontoCobrado`. `Revisar` = `Sí` o vacío.
- **Alumnos**: `ID_Alumno, Nombre, Materia, Curso, Teléfono, Contacto, Día, Frecuencia, PrecioHora,`
  `Modalidad, FechaAlta, Estado, Observaciones`. `Estado` ∈ Activo | Pausado | Baja. `PrecioHora` = espejo
  de la tarifa vigente. `Día` = días separados por coma ("Lunes, Jueves").
- **Tarifas** (opcional): `ID_Tarifa, ID_Alumno, Desde, Tipo (Hora|Clase|Mensual), Monto, Nota`.
  Vigente = `Desde` más reciente ≤ fecha. Sin hoja → `Alumnos.PrecioHora`.
- **IPC** (opcional, la carga el usuario): `Mes (aaaa-mm), VariacionPct`.

## Reglas que no se negocian
1. Nunca leer, mostrar, copiar ni commitear `profeapp2-*.json` ni `*.xlsx` (hook en `.claude/hooks`).
2. Compatibilidad: la app funciona con el Sheet viejo (sin columnas/hojas nuevas, números como texto
   `"4000.0"`) y con el nuevo. Falta algo → valor por defecto + aviso, nunca romper. Ver skill `migrar-esquema-sheet`.
3. Prohibido `ws.clear()` o reescribir hojas. Alta = `append_row`; edición = celdas de la fila del ID;
   borrado = `delete_rows` de la fila buscada por ID justo antes.
4. El Sheet es la fuente de verdad. Cruzar siempre por `ID_Alumno` / `ID_Clase`, nunca por nombre.
5. Pantalla en formato argentino (`$ 10.000`, `2,5 h`, `dd/mm/aaaa`). En el Sheet: fechas ISO como texto y
   números reales, escritos con `value_input_option=RAW` (nunca `USER_ENTERED`: la planilla es es-AR).
6. Antes de cada push: tests, `py_compile`, smoke test, `git status` sin secretos y subagente `revisor-codigo`.
7. Commits chicos en español. Decisiones tomadas sin consultar → `CHANGELOG.md`.
8. Widgets: nada dentro de un `st.form` cuyo valor por defecto dependa de otro widget del form.

## Corrección de datos
Excel descargado del Sheet → `scripts/corregir_datos.py` → `Clases Particulares - corregido.xlsx`
(hoja `LEEME` con cada cambio) → auditoría con `data-auditor` → el usuario lo importa a mano
(Archivo → Importar). Ver skill `corregir-datos-excel`.
