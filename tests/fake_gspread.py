"""Google Sheet falso en memoria con la parte de la API de gspread que usa la app."""
import gspread


class ClearProhibido(AssertionError):
    pass


class FakeWorksheet:
    def __init__(self, titulo, filas):
        self.title = titulo
        self.filas = [list(f) for f in filas]
        self.llamadas = []

    # ── lectura ──
    def get_values(self, range_name=None, value_render_option=None, **kwargs):
        self.llamadas.append(('get_values', value_render_option))
        ancho = max((len(f) for f in self.filas), default=0)
        return [list(f) + [''] * (ancho - len(f)) for f in self.filas]

    def row_values(self, fila, **kwargs):
        return list(self.filas[fila - 1]) if fila <= len(self.filas) else []

    def col_values(self, col, value_render_option=None):
        return [f[col - 1] if col <= len(f) else '' for f in self.filas]

    # ── escritura ──
    def append_row(self, values, value_input_option=None, table_range=None, **kwargs):
        self.llamadas.append(('append_row', str(value_input_option)))
        assert 'USER_ENTERED' not in str(value_input_option).upper()
        self.filas.append(list(values))

    def update_cells(self, cells, value_input_option=None):
        self.llamadas.append(('update_cells', str(value_input_option)))
        assert 'USER_ENTERED' not in str(value_input_option).upper()
        for c in cells:
            fila = self.filas[c.row - 1]
            while len(fila) < c.col:
                fila.append('')
            fila[c.col - 1] = c.value

    def delete_rows(self, start_index, end_index=None):
        self.llamadas.append(('delete_rows', start_index))
        assert start_index > 1, "no se puede borrar el encabezado"
        del self.filas[start_index - 1:(end_index or start_index)]

    def clear(self):
        raise ClearProhibido("ws.clear() está prohibido")

    def update(self, *args, **kwargs):
        raise AssertionError("ws.update() masivo no se usa: escribir por celdas o append_row")

    # ── helpers de test ──
    def registros(self):
        enc = self.filas[0]
        return [dict(zip(enc, f + [''] * (len(enc) - len(f)))) for f in self.filas[1:]]


class FakeSpreadsheet:
    def __init__(self, hojas):
        self.hojas = {t: FakeWorksheet(t, f) for t, f in hojas.items()}

    def worksheet(self, titulo):
        if titulo not in self.hojas:
            raise gspread.exceptions.WorksheetNotFound(titulo)
        return self.hojas[titulo]

    def worksheets(self):
        return list(self.hojas.values())


class FakeClient:
    def __init__(self, planilla):
        self.planilla = planilla

    def open(self, nombre):
        return self.planilla
