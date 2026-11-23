"""Offline tests for connector logic (no network)."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import build  # noqa: E402
from data.connectors import congreso, dnp, secop, xlsx  # noqa: E402
from data.connectors.reference import nit_base  # noqa: E402


def tiny_xlsx(path, rows):
    shared, idx = [], {}

    def cell(r, c, v):
        ref = f"{chr(65 + c)}{r + 1}"
        if isinstance(v, str):
            if v not in idx:
                idx[v] = len(shared)
                shared.append(v)
            return f'<c r="{ref}" t="s"><v>{idx[v]}</v></c>'
        return f'<c r="{ref}"><v>{v}</v></c>'

    body = "".join(f'<row r="{i + 1}">' + "".join(cell(i, j, v) for j, v in enumerate(r) if v is not None) + "</row>"
                   for i, r in enumerate(rows))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rns}><sheets><sheet name="Hoja" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f"<sst {ns}>" + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData>{body}</sheetData></worksheet>")


class ConnectorTest(unittest.TestCase):
    def test_nit_base(self):
        self.assertEqual(nit_base("890981195:5"), "890981195")
        self.assertEqual(nit_base("800000681-8"), "800000681")
        self.assertIsNone(nit_base(None))

    def test_secop_nit_match_with_and_without_check_digit(self):
        nits = {"899999061": "11001"}
        self.assertEqual(secop._match("899999061", nits), "11001")
        self.assertEqual(secop._match("8999990619", nits), "11001")
        self.assertEqual(secop._match("800000681-8", {"800000681": "05001"}), "05001")
        self.assertIsNone(secop._match("123", nits))

    def test_dnp_codes_and_values(self):
        self.assertEqual(dnp._code("5001", "municipio"), "05001")
        self.assertEqual(dnp._code("05000", "departamento"), "05")
        self.assertEqual(dnp._code(5, "departamento"), "05")
        self.assertEqual(dnp._value("categoria", "E"), "Especial")
        self.assertEqual(dnp._value("categoria", "ESPECIAL"), "Especial")
        self.assertEqual(dnp._value("categoria", 6), "6")
        self.assertIsNone(dnp._value("idf", "n/d"))

    def test_periodo(self):
        self.assertEqual(build.periodo(2021), (2020, "2020-2023"))
        self.assertEqual(build.periodo(2024), (2024, "2024-2027"))
        self.assertEqual(build.periodo(2019), (2016, "2016-2019"))

    def test_xlsx_and_dnp_file_with_title_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.xlsx"
            tiny_xlsx(p, [["Título del anexo"], [], ["Codigo DANE", "Municipio", "Categoría Ley 617 ", "Nuevo IDF"],
                          ["05001", "MEDELLIN", "E", 78.5], ["5002", "ABEJORRAL", 6, 55.25]])
            self.assertEqual(xlsx.read_rows(p)[3], ["05001", "MEDELLIN", "E", 78.5])
            got = dnp.read_file({"id": "t", "path": str(p), "nivel": "municipio", "codigo": "Codigo DANE",
                                 "columnas": {"idf": "Nuevo IDF", "categoria": "Categoria Ley 617"}})
            self.assertEqual(got["05001"], {"idf": 78.5, "categoria": "Especial"})
            self.assertEqual(got["05002"]["categoria"], "6")

    def test_merge_credits_right_term_and_delta(self):
        ref = {"entidades": {"05001": {"tipo": "municipio", "nombre": "Medellín", "departamento": "Antioquia", "nit": "1"}}}
        dnp_data = {"2019": {"05001": {"mdm": 80.0}}, "2021": {"05001": {"mdm": 83.5, "grupo_dnp": "C"}},
                    "2020": {"05001": {"categoria": "Especial"}}}
        recs = build.merge([2021], ref, dnp_data, {2021: {"05001": {"contratacion_directa": 40.0, "_secop": {}}}})
        r = recs[0]
        self.assertEqual(r["periodo"], "2020-2023")
        self.assertAlmostEqual(r["metricas"]["mdm_delta"], 3.5)
        self.assertEqual(r["categoria"], "Especial")  # carried from nearest year
        self.assertEqual(r["grupo_dnp"], "C")
        self.assertEqual(r["tarjetas"], [])

    def test_parse_senado_directory_dedupes(self):
        entry = ('<div class="modazdirectory__result modazdirectory__layout-misc_off">'
                 '<img src="https://x/Fotos/a.jpg" alt="x" class="modazdirectory__image" />'
                 '<div> <h3>Pérez Gómez Ana</h3> <p>Partido Liberal</p> <p>Capitolio, Of. 1</p></div></div>')
        rows = congreso.parse_senado(entry * 2)
        self.assertEqual(rows, [{"nombre": "Pérez Gómez Ana", "partido": "Partido Liberal",
                                 "oficina": "Capitolio, Of. 1", "foto": "https://x/Fotos/a.jpg"}])


if __name__ == "__main__":
    unittest.main()
