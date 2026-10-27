---
name: migrar-esquema-sheet
description: Cómo agregar una columna u hoja al Google Sheet de ProfeApp sin romper la app en producción con el Sheet viejo.
---

# Migrar el esquema del Sheet de forma compatible

El usuario copia los datos a mano: entre el push y la importación la app corre con el Sheet **viejo**.

Reglas:
1. **Columnas nuevas solo al final** de la hoja. Nunca renombrar, reordenar ni borrar columnas existentes.
2. **Hojas nuevas**: la app tiene que funcionar si no existen (`sheets.leer` devuelve `None`) y mostrar un
   aviso en el expander "⚠️ Avisos de la planilla" con instrucciones para crearla.
3. **Lectura con valor por defecto**: agregar la columna a `COLUMNAS_*` en `logica.py` y darle default en
   `normalizar_*`. Si reemplaza a otra, usar respaldo (ej.: `MontoCobrado` → `Total`).
4. **Escritura**: `sheets.agregar/actualizar` ignoran las claves que no son encabezado, así que se puede
   escribir siempre el dict completo. Si una columna nueva reemplaza a una vieja, escribir ambas.
5. Tipos: números como números de Python, fechas como texto ISO, `value_input_option` RAW.
6. Actualizar `scripts/corregir_datos.py` para que el Excel corregido traiga la columna/hoja, volver a
   generarlo y auditarlo con el subagente `data-auditor`.
7. Actualizar la sección "Esquema de las hojas" de `CLAUDE.md` y `CHANGELOG.md`.
8. Tests: la planilla vieja de `tests/conftest.py` **no** se toca (representa producción);
   la nueva sí incluye la columna. Correr ambos casos.
