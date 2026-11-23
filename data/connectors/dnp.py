"""Resultados DNP: MDM (municipios), MDD (departamentos), IDF (ambos).

El DNP no expone API para los años recientes, así que se combinan:
  - API datos.gov.co (MDM 2016–2020, dataset nkjx-rsq7)
  - Archivos Excel publicados por el DNP, declarados en data/sources/dnp.json

Salida: data/processed/dnp.json  ->  {anio: {codigo: {metrica: valor}}}
  codigo = DIVIPOLA de 5 dígitos (municipio) o 2 dígitos (departamento).
"""
from __future__ import annotations

import json
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

from . import socrata, xlsx

DATA = Path(__file__).resolve().parents[1]
SOURCES = DATA / "sources" / "dnp.json"
RAW = DATA / "raw" / "dnp"
OUT = DATA / "processed" / "dnp.json"

CATEGORIAS = {"E": "Especial", "ESPECIAL": "Especial", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
              "PRIMERA": "1", "SEGUNDA": "2", "TERCERA": "3", "CUARTA": "4", "QUINTA": "5", "SEXTA": "6"}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("*", " ").split())


def _code(raw, nivel: str) -> str | None:
    digits = "".join(ch for ch in str(raw if raw is not None else "") if ch.isdigit())
    if not digits:
        return None
    if nivel == "municipio":
        return digits.zfill(5) if len(digits) <= 5 else None
    d = digits.zfill(2)
    return d[:2] if len(d) in (2, 5) else None  # '05' o '05000'


def _value(metric: str, v):
    if v is None or v == "":
        return None
    if metric == "categoria":
        return CATEGORIAS.get(str(v).strip().upper().removesuffix(".0"))
    if metric == "grupo_dnp":
        return str(v).strip().upper()
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def _fetch(spec: dict, refresh: bool) -> Path:
    if spec.get("path"):
        return DATA / spec["path"]
    dest = RAW / (spec["url"].rsplit("/", 1)[-1].replace("%20", "_").replace("%", ""))
    if refresh or not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(spec["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            dest.write_bytes(r.read())
    return dest


def read_file(spec: dict, refresh: bool = False) -> dict[str, dict]:
    path = _fetch(spec, refresh)
    if path.suffix.lower() == ".csv":
        import csv
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = [list(r) for r in csv.reader(f)]
    else:
        rows = xlsx.read_rows(path, spec.get("hoja", 0))

    want_code = _norm(spec["codigo"])
    hdr_i = next((i for i, r in enumerate(rows[:30]) if any(_norm(c) == want_code for c in r if c is not None)), None)
    if hdr_i is None:
        raise ValueError(f"{spec['id']}: no encuentro la columna '{spec['codigo']}' en {path.name}")
    header = [_norm(c) if c is not None else "" for c in rows[hdr_i]]

    def col(name):
        n = _norm(name)
        for i, h in enumerate(header):
            if h == n:
                return i
        for i, h in enumerate(header):  # tolerate suffixes like '*' or trailing text
            if h.startswith(n):
                return i
        raise ValueError(f"{spec['id']}: columna '{name}' no encontrada. Encabezados: {rows[hdr_i]}")

    ci = col(spec["codigo"])
    cols = {m: col(h) for m, h in spec["columnas"].items()}
    out = {}
    for r in rows[hdr_i + 1:]:
        code = _code(r[ci] if ci < len(r) else None, spec["nivel"])
        if not code:
            continue
        vals = {m: _value(m, r[i] if i < len(r) else None) for m, i in cols.items()}
        if any(v is not None for v in vals.values()):
            out[code] = vals
    return out


def build(refresh: bool = False) -> dict:
    cfg = json.loads(SOURCES.read_text(encoding="utf-8"))
    data: dict[int, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))

    api = cfg["api"]["mdm_historico"]
    rows = socrata.query(api["dataset"], select="codigo_entidad,anio,dato", where="codigo_variable='8'", refresh=refresh)
    for r in rows:
        y = int(r["anio"])
        if y in api["anios"] and r.get("dato") not in (None, ""):
            data[y][str(r["codigo_entidad"]).zfill(5)]["mdm"] = round(float(r["dato"]), 3)

    for spec in cfg["archivos"]:
        try:
            got = read_file(spec, refresh)
        except Exception as e:  # keep going; report clearly
            print(f"  ! {spec['id']}: {e}")
            continue
        for code, vals in got.items():
            for k, v in vals.items():
                if v is not None:
                    data[spec["anio"]][code][k] = v
        print(f"  {spec['id']}: {len(got)} entidades")

    out = {str(y): dict(v) for y, v in sorted(data.items())}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"DNP: años {', '.join(out)} -> {OUT}")
    return out
