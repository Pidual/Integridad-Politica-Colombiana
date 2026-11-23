"""Mandatarios elegidos (Registraduría) -> data/reference/mandatarios.csv

Dataset datos.gov.co h236-q58p "Programas de gobierno elegidos gobernadores y alcaldes":
elecciones de 2019 (mandato 2020–2023), 1.100 alcaldes y 32 gobernadores.

Se empareja por nombre de departamento + municipio contra DIVIPOLA.
Ojo: es quien GANÓ la elección; no refleja suspensiones, destituciones ni
alcaldes encargados durante el mandato.
"""
from __future__ import annotations

import csv
import re
import json
from pathlib import Path

from . import socrata
from .reference import norm

REF = Path(__file__).resolve().parents[1] / "reference"
OUT = REF / "mandatarios.csv"

ALIAS = {  # Registraduría name -> DIVIPOLA name (normalized), where they differ
    "BOGOTA D C": "BOGOTA D C", "SAN ANDRES": "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA",
    "NORTE DE SAN": "NORTE DE SANTANDER", "VALLE": "VALLE DEL CAUCA",
}


def _title(name: str) -> str:
    """'QUINTERO CALLE DANIEL' -> 'Quintero Calle Daniel' (same order as the Senate roster)."""
    small = {"de", "del", "la", "las", "los", "y"}
    return " ".join(w.lower() if w.lower() in small and i else w.capitalize() for i, w in enumerate(name.split()))


def build(refresh: bool = False) -> int:
    ents = json.loads((REF / "entidades.json").read_text(encoding="utf-8"))["entidades"]
    by_name: dict[tuple[str, str], str] = {}
    deptos: dict[str, str] = {}
    for code, e in ents.items():
        d = norm(e["departamento"])
        if e["tipo"] == "municipio":
            by_name[(d, norm(e["nombre"]))] = code
        else:
            deptos[d] = code

    def find_depto(d: str) -> str | None:
        d = ALIAS.get(d, d)
        if d in deptos:
            return deptos[d]
        hits = [k for k in deptos if k.startswith(d) or d.startswith(k)]
        return deptos[hits[0]] if len(hits) == 1 else None

    def find_mpio(d: str, m: str) -> str | None:
        d = ALIAS.get(d, d)
        cands = {k: v for k, v in by_name.items() if k[0] == d or k[0].startswith(d) or d.startswith(k[0])}
        if (d, m) in cands:
            return cands[(d, m)]
        # 'LOPEZ (MICAY)' -> 'LOPEZ'; 'YONDO-CASABE' -> 'YONDO'
        variants = {m, re.sub(r"\s*\(.*?\)", "", m).strip(), m.split("-")[0].strip(), m.split(" ")[0]}
        for v in [x for x in variants if x]:
            for rule in (lambda mm: mm == v,
                         lambda mm: mm.replace(" ", "") == v.replace(" ", ""),
                         lambda mm: mm.endswith(" " + v),               # 'SANTUARIO' -> 'EL SANTUARIO', 'TUMACO' -> 'SAN ANDRES DE TUMACO'
                         lambda mm: mm.startswith(v + " ") or v.startswith(mm + " ")):
                hits = {code for (dd, mm), code in cands.items() if rule(mm)}
                if len(hits) == 1:
                    return hits.pop()
        return None

    rows = socrata.query("h236-q58p", select="corporacion,nombre_del_elegido,departamento,municipio,agrupacion_politica,a_o",
                         refresh=refresh)
    out, missing = [], []
    for r in rows:
        y = int(r["a_o"])
        periodo = f"{y + 1}-{y + 4}"
        d, m = norm(r.get("departamento", "")), norm(r.get("municipio", ""))
        if r["corporacion"].upper().startswith("GOBERN"):
            code = find_depto(d)
        else:
            code = "11001" if d.startswith("BOGOTA") else find_mpio(d, m)
        if not code:
            missing.append(f"{r['corporacion']} {r.get('departamento')} / {r.get('municipio')}")
            continue
        out.append({"codigo": code, "periodo": periodo, "nombre": _title(r["nombre_del_elegido"]),
                    "partido": (r.get("agrupacion_politica") or "").strip().title(),
                    "fuente": f"Registraduría – elegidos {y} (datos.gov.co h236-q58p)"})

    REF.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["codigo", "periodo", "nombre", "partido", "fuente"])
        w.writeheader()
        w.writerows(sorted(out, key=lambda r: (r["periodo"], r["codigo"])))
    print(f"Mandatarios: {len(out)} emparejados, {len(missing)} sin emparejar -> {OUT}")
    for x in missing[:15]:
        print("   sin emparejar:", x)
    return len(out)


if __name__ == "__main__":
    build()
