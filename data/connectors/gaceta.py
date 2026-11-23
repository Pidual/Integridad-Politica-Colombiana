"""Gaceta del Congreso (Imprenta Nacional): listado, descarga y lectura de actas.

El sitio (svrpubindc.imprenta.gov.co/senado) es una app JSF/PrimeFaces sin API:
  1. Listado: POST AJAX a la tabla con _rows=N  -> (número, corporación, fecha)
  2. PDF:     GET index2.xhtml?ent=Senado&fec=DD-MM-AAAA&num=N (guarda la petición en sesión)
              + POST dldFile con pdfIr                         -> application/pdf
Las actas de plenaria traen la lista de asistencia y las votaciones nominales.
Se publican con semanas o meses de retraso respecto a la sesión.
"""
from __future__ import annotations

import datetime as dt
import html
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
RAW = DATA / "raw" / "gaceta"
INDEX = RAW / "indice.json"
BASE = "http://svrpubindc.imprenta.gov.co/senado/"
TABLE = "formResumen:dataTableResumen"


def _opener():
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", "Mozilla/5.0 (integridad-politica-colombiana)")]
    return op


def _viewstate(page: str, form: str) -> tuple[str, str]:
    vs = re.search(r'name="javax.faces.ViewState"[^>]*value="([^"]+)"', page).group(1)
    action = re.search(rf'<form id="{form}"[^>]*action="([^"]+)"', page).group(1)
    return vs, action


def listar(rows: int = 1000) -> list[dict]:
    """Latest `rows` gacetas: [{num, corporacion, fecha (ISO)}], newest first."""
    op = _opener()
    page = op.open(BASE + "index.xhtml", timeout=60).read().decode("utf-8", "replace")
    vs, action = _viewstate(page, "formResumen")
    data = {
        "javax.faces.partial.ajax": "true", "javax.faces.source": TABLE,
        "javax.faces.partial.execute": TABLE, "javax.faces.partial.render": TABLE,
        TABLE: TABLE, TABLE + "_pagination": "true", TABLE + "_first": "0", TABLE + "_rows": str(rows),
        TABLE + "_encodeFeature": "true", "formResumen": "formResumen", "javax.faces.ViewState": vs,
    }
    raw = op.open(urllib.parse.urljoin(BASE, action), data=urllib.parse.urlencode(data).encode(), timeout=300).read()
    text = raw.decode("utf-8", "replace")
    out = []
    for _, row in re.findall(r'<tr[^>]*data-ri="(\d+)"[^>]*>(.*?)</tr>', text, re.S):
        cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        d, m, y = cells[2].split("/")
        corp = "Senado" if cells[1].lower().startswith("senado") else "Camara"
        out.append({"num": int(cells[0]), "corporacion": corp, "fecha": f"{y}-{m}-{d}"})
    return out


def descargar(num: int, fecha: str, corporacion: str = "Senado", refresh: bool = False) -> Path | None:
    dest = RAW / "pdf" / f"gaceta_{num}.pdf"
    if dest.exists() and not refresh:
        return dest
    y, m, d = fecha.split("-")
    op = _opener()
    q = urllib.parse.urlencode({"ent": corporacion, "fec": f"{d}-{m}-{y}", "num": num})
    for attempt in range(3):
        try:
            page = op.open(BASE + "index2.xhtml?" + q, timeout=60).read().decode("utf-8", "replace")
            vs, action = _viewstate(page, "dldFile")
            body = urllib.parse.urlencode({"dldFile": "dldFile", "javax.faces.ViewState": vs, "pdfIr": "pdfIr"}).encode()
            r = op.open(urllib.parse.urljoin(BASE, action), data=body, timeout=300)
            content = r.read()
            if not r.headers.get("Content-Type", "").startswith("application/pdf"):
                return None
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            return dest
        except Exception:
            if attempt == 2:
                return None
            time.sleep(5 * (attempt + 1))
    return None


def texto(pdf: Path, max_pages: int | None = None) -> str:
    import pypdf  # see requirements.txt
    reader = pypdf.PdfReader(str(pdf))
    pages = reader.pages if max_pages is None else reader.pages[:max_pages]
    return "\n".join((p.extract_text() or "") for p in pages)


SECCIONES = ["ACTAS DE PLENARIA", "ACTAS DE COMISIÓN", "ACTAS DE COMISION", "PROYECTOS DE LEY", "PONENCIAS",
             "INFORMES DE PONENCIA", "INFORMES DE CONCILIACIÓN", "NOTAS ACLARATORIAS", "OBJECIONES", "TEXTOS",
             "CONCEPTOS", "CARTAS DE COMENTARIOS", "CONSTANCIAS", "INFORMES", "PROPOSICIONES"]
ACTA_NUM = re.compile(r"ACTA\s+(?:DE\s+PLENARIA\s+)?N[ÚU]MERO\s+(\d+)", re.I)


def clasificar(pdf: Path) -> dict:
    """Read the first two pages: section of the gaceta and, for records, the acta number and session date."""
    head = texto(pdf, 2)
    flat = " ".join(head.split()).upper()
    seccion = next((s for s in SECCIONES if s in flat[:400]), None) or next((s for s in SECCIONES if s in flat), None)
    es_acta = bool(seccion and seccion.startswith("ACTAS")) or bool(re.search(r"\bACTA\s+(DE\s+PLENARIA\s+)?N[ÚU]MERO", flat))
    plenaria = es_acta and ("PLENARIA" in flat[:3000]) and not re.search(r"COMISI[ÓO]N\s+(PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA|S[ÉE]PTIMA|LEGAL|ACCIDENTAL)", flat[:1500])
    m = ACTA_NUM.search(flat)
    fecha_sesion = None
    fm = re.search(r"(\d{1,2})\s+DE\s+(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\s+DE\s+(\d{4})", flat[flat.find("ACTA"):] if "ACTA" in flat else "")
    if fm:
        fecha_sesion = " ".join(fm.groups())
    return {"seccion": seccion, "es_acta": es_acta, "acta_plenaria": int(m.group(1)) if (m and plenaria) else None,
            "acta_num": int(m.group(1)) if m else None, "fecha_sesion": fecha_sesion, "titulo": flat[:300]}


def indexar(desde: str, rows: int = 1000, limit: int | None = None) -> list[dict]:
    """Download Senate gacetas since `desde` (ISO date) and classify them. Cached and resumable."""
    idx = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    items = [g for g in listar(rows) if g["corporacion"] == "Senado" and g["fecha"] >= desde]
    if limit:
        items = items[:limit]
    for n, g in enumerate(items, 1):
        key = str(g["num"])
        if key in idx and idx[key].get("clasificada") and "seccion" in idx[key]:
            continue
        pdf = descargar(g["num"], g["fecha"])
        if not pdf:
            idx[key] = {**g, "clasificada": False, "error": "descarga"}
            continue
        try:
            info = clasificar(pdf)
        except Exception as e:  # damaged PDF
            info = {"acta_plenaria": None, "error": str(e)[:200]}
        idx[key] = {**g, **info, "clasificada": True}
        if not info.get("es_acta"):
            pdf.unlink(missing_ok=True)  # keep disk small: only records (actas) are kept
        if n % 10 == 0:
            INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {n}/{len(items)} gacetas revisadas", flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    actas = [v for v in idx.values() if v.get("es_acta")]
    plen = [v for v in actas if v.get("acta_plenaria")]
    print(f"Gaceta: {len(idx)} gacetas del Senado revisadas desde {desde}; {len(actas)} actas "
          f"({len(plen)} de plenaria)", flush=True)
    return actas


if __name__ == "__main__":
    import sys
    desde = sys.argv[1] if len(sys.argv) > 1 else "2026-07-20"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    indexar(desde, limit=limit)
