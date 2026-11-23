"""Lector mínimo de .xlsx con la librería estándar (zipfile + XML).

Suficiente para las tablas planas que publican DNP / Contaduría. No evalúa
fórmulas: usa el último valor guardado en la celda.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def sheet_names(path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        return [s.get("name") for s in wb.find("m:sheets", NS)]


def read_rows(path, sheet: str | int = 0) -> list[list]:
    """Return the sheet as a list of rows (lists), padded with None."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = wb.find("m:sheets", NS)
        sh = sheets[sheet] if isinstance(sheet, int) else next(s for s in sheets if s.get("name") == sheet)
        rid = sh.get(REL_NS)
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target

        rows = []
        for row in ET.fromstring(z.read(target)).iter(f"{{{NS['m']}}}row"):
            out: list = []
            for c in row.findall("m:c", NS):
                idx = _col_index(c.get("r"))
                t = c.get("t")
                v = c.find("m:v", NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                elif v is None:
                    val = None
                elif t in ("str", "e"):
                    val = v.text
                elif t == "b":
                    val = v.text == "1"
                else:
                    try:
                        f = float(v.text)
                        val = int(f) if f.is_integer() else f
                    except (TypeError, ValueError):
                        val = v.text
                while len(out) < idx:
                    out.append(None)
                out.append(val)
            rows.append(out)
        width = max((len(r) for r in rows), default=0)
        return [r + [None] * (width - len(r)) for r in rows]
