"""Métricas de contratación desde SECOP II (datos.gov.co), agregadas en el servidor.

Por entidad territorial (NIT de la alcaldía / gobernación) y año:
  contratacion_directa  % del valor contratado por "Contratación directa"
  oferente_unico        % de procesos competitivos adjudicados con ≤ 1 oferta
  prorrogas             % de contratos con días adicionados (prórrogas)

Datasets:
  jbjy-vk9h  SECOP II - Contratos Electrónicos
  p6dx-8zbt  SECOP II - Procesos de Contratación
  f789-7hwg  SECOP I  - Procesos de Compra Pública (muchos municipios pequeños aún lo usan)

oferente_unico solo usa SECOP II: SECOP I no publica el número de ofertas de forma fiable.

Notas:
  - El NIT del municipio/departamento agrupa a todas sus secretarías (administración
    central). Se excluyen concejos, personerías, contralorías y asambleas que a veces
    comparten NIT.
  - Se suman contratos de SECOP I y SECOP II; aun así se exige un volumen mínimo
    de contratos para publicar la métrica.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import socrata
from .reference import nit_base

OUT_DIR = Path(__file__).resolve().parents[1] / "processed"

CONTRATOS = "jbjy-vk9h"
PROCESOS = "p6dx-8zbt"
SECOP1 = "f789-7hwg"

COMPETITIVAS = [
    "Licitación pública", "Licitación pública Obra Publica", "Selección Abreviada de Menor Cuantía",
    "Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes", "Selección abreviada subasta inversa",
    "Concurso de méritos abierto", "Mínima cuantía",
]
EXCLUIR = re.compile(r"CONCEJO|PERSONER|CONTRALOR|ASAMBLEA", re.I)
MIN_CONTRATOS = 30
MIN_PROCESOS = 10
MAX_VALOR = 1e14  # descarta errores de digitación absurdos


def _year_range(field: str, year: int) -> str:
    return f"{field} between '{year}-01-01T00:00:00' and '{year}-12-31T23:59:59'"


def _match(nit_raw: str, nits: dict[str, str]) -> str | None:
    """SECOP mezcla NIT con y sin dígito de verificación."""
    n = "".join(ch for ch in str(nit_raw) if ch.isdigit())
    if n in nits:
        return nits[n]
    if len(n) == 10 and n[:9] in nits:
        return nits[n[:9]]
    return None


def build(year: int, entidades: dict, refresh: bool = False) -> dict:
    nits = {e["nit"]: code for code, e in entidades.items() if e.get("nit")}

    contratos = socrata.query(
        CONTRATOS,
        select=("nit_entidad,nombre_entidad,modalidad_de_contratacion,count(*) as n,"
                "sum(valor_del_contrato) as valor,sum(case(dias_adicionados>0,1,true,0)) as prorrogados"),
        where=f"{_year_range('fecha_de_firma', year)} and valor_del_contrato < {MAX_VALOR:.0f}",
        group="nit_entidad,nombre_entidad,modalidad_de_contratacion",
        refresh=refresh,
    )
    secop1 = socrata.query(
        SECOP1,
        select=("nit_de_la_entidad,nombre_entidad,modalidad_de_contratacion,count(*) as n,"
                "sum(cuantia_contrato) as valor,"
                "sum(case(tiempo_adiciones_en_dias>0 or tiempo_adiciones_en_meses>0,1,true,0)) as prorrogados"),
        where=f"{_year_range('fecha_de_firma_del_contrato', year)} and cuantia_contrato < {MAX_VALOR:.0f}",
        group="nit_de_la_entidad,nombre_entidad,modalidad_de_contratacion",
        refresh=refresh,
    )
    contratos = contratos + [
        {"nit_entidad": r["nit_de_la_entidad"], "nombre_entidad": r.get("nombre_entidad"),
         "modalidad_de_contratacion": r.get("modalidad_de_contratacion") or "", "n": r["n"],
         "valor": r.get("valor"), "prorrogados": r.get("prorrogados"), "_origen": "secop1"}
        for r in secop1
    ]
    competitivas = " or ".join(f"modalidad_de_contratacion='{m}'" for m in COMPETITIVAS)
    procesos = socrata.query(
        PROCESOS,
        select=("nit_entidad,entidad,count(*) as n,"
                "sum(case(respuestas_al_procedimiento<=1,1,true,0)) as unico"),
        where=f"{_year_range('fecha_de_publicacion_del', year)} and adjudicado='Si' and ({competitivas})",
        group="nit_entidad,entidad",
        refresh=refresh,
    )

    acc = defaultdict(lambda: {"n": 0, "valor": 0.0, "valor_directa": 0.0, "prorrogados": 0,
                               "procesos": 0, "unico": 0, "n_secop1": 0, "nombres": set()})
    for r in contratos:
        code = _match(r["nit_entidad"], nits)
        if not code or EXCLUIR.search(r.get("nombre_entidad") or ""):
            continue
        a = acc[code]
        n, valor = int(r["n"]), float(r.get("valor") or 0)
        a["n"] += n
        a["valor"] += valor
        a["prorrogados"] += int(r.get("prorrogados") or 0)
        if r.get("_origen") == "secop1":
            a["n_secop1"] += n
        # SECOP II: "Contratación directa"; SECOP I: "Contratación Directa (Ley 1150 de 2007)".
        # "Contratación Directa (con ofertas)" sí recibe ofertas, por eso no cuenta.
        if r["modalidad_de_contratacion"] in ("Contratación directa", "Contratación Directa (Ley 1150 de 2007)"):
            a["valor_directa"] += valor
        a["nombres"].add(r.get("nombre_entidad"))
    for r in procesos:
        code = _match(r["nit_entidad"], nits)
        if not code or EXCLUIR.search(r.get("entidad") or ""):
            continue
        acc[code]["procesos"] += int(r["n"])
        acc[code]["unico"] += int(r["unico"])

    out = {}
    for code, a in acc.items():
        ok_c = a["n"] >= MIN_CONTRATOS and a["valor"] > 0
        ok_p = a["procesos"] >= MIN_PROCESOS
        out[code] = {
            "contratacion_directa": round(100 * a["valor_directa"] / a["valor"], 2) if ok_c else None,
            "prorrogas": round(100 * a["prorrogados"] / a["n"], 2) if ok_c else None,
            "oferente_unico": round(100 * a["unico"] / a["procesos"], 2) if ok_p else None,
            "_secop": {"contratos": a["n"], "contratos_secop1": a["n_secop1"], "valor_total": round(a["valor"]), "procesos_competitivos": a["procesos"],
                       "entidades_secop": sorted(x for x in a["nombres"] if x)[:10]},
        }

    path = OUT_DIR / f"secop_{year}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    with_metric = sum(1 for v in out.values() if v["contratacion_directa"] is not None)
    print(f"SECOP {year}: {len(out)} entidades emparejadas, {with_metric} con volumen suficiente -> {path}")
    return out
