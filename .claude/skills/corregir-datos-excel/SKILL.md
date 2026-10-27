---
name: corregir-datos-excel
description: Auditar y corregir los datos de ProfeApp con scripts/corregir_datos.py, registrar cada cambio en la hoja LEEME y dar instrucciones de importación a Google Sheets.
---

# Corregir datos vía Excel

Flujo: el usuario descarga el Sheet como `Clases Particulares.xlsx` (Archivo → Descargar → .xlsx) en la raíz
del repo → el script genera `Clases Particulares - corregido.xlsx` → el usuario lo importa a mano.
Ambos `.xlsx` están en `.gitignore`: **nunca** se commitean. El original no se modifica nunca.

1. Auditar: leer el original con openpyxl/pandas (con `logica.parse_numero`), buscar totales que no
   coinciden con horas × precio, duplicados alumno+fecha, precios "forzados" ($6.666), horas raras.
2. Preguntar al usuario **una sola vez, todo junto**, por los registros dudosos.
3. Cargar las decisiones en `CORRECCIONES`, `REVISAR` y `CONFIRMADOS` de `scripts/corregir_datos.py`.
   Lo que no se sepa: dejar el dato, `Revisar = Sí` y la descripción en `NotaRevision`.
4. Correr: `.venv\Scripts\python scripts\corregir_datos.py [--corte aaaa-mm-dd]`.
5. Auditar con el subagente `data-auditor`.
6. Instrucciones para el usuario (no técnico):
   - Antes de importar: Archivo → Hacer una copia (respaldo) y verificar que no se cargaron clases después
     de descargar el Excel (el último `ID_Clase` del Sheet tiene que ser el mismo que en el Excel).
   - Google Sheets → Archivo → Importar → Subir → elegir el Excel corregido → **"Reemplazar hoja de
     cálculo"**: reemplaza todas las hojas de una vez con los nombres exactos (`Clases`, `Alumnos`,
     `Tarifas`, `IPC`, `LEEME`) y mantiene el mismo archivo compartido con la cuenta de servicio.
     Alternativa hoja por hoja: "Reemplazar hoja actual" para `Clases`/`Alumnos` e "Insertar hojas
     nuevas" para `Tarifas`, `IPC` y `LEEME`.
   - **No copiar y pegar**: la configuración regional es-AR rompe los decimales.
   - Si aparece "Convertir texto en números, fechas y fórmulas", **desmarcarlo**.
   - Los nombres de hoja y encabezados tienen que quedar exactamente iguales.
   - Verificar en la app que el total del mes coincide con el bloque "Totales por mes" de `LEEME`.
