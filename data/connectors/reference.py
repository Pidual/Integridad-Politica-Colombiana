"""Tabla de referencia de entidades territoriales: DIVIPOLA <-> NIT.

Fuentes:
  - DIVIPOLA (DANE) en datos.gov.co: gdxc-w37w  -> códigos y nombres oficiales.
  - Registro de entidades CHIP (Contaduría): 5c7g-ptic -> NIT de cada municipio
    y departamento. Su id_entidad codifica el DIVIPOLA:
        departamento: 11 DD DD 000      (p. ej. 110505000 = Antioquia)
        municipio:    21 NN MMMMM       (p. ej. 210205002 = Abejorral, 05002)

Salida: data/reference/entidades.json
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from . import socrata

OUT = Path(__file__).resolve().parents[1] / "reference" / "entidades.json"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return " ".join(s.replace(".", " ").replace(",", " ").split())


def nit_base(nit: str | None) -> str | None:
    """'890981195:5' -> '890981195'. Keeps only the 9-digit base."""
    if not nit:
        return None
    digits = "".join(ch for ch in str(nit).split(":")[0].split("-")[0] if ch.isdigit())
    return digits or None


def build(refresh: bool = False) -> dict:
    divipola = socrata.query("gdxc-w37w", select="cod_dpto,dpto,cod_mpio,nom_mpio,tipo_municipio", refresh=refresh)
    mpios = {r["cod_mpio"]: r for r in divipola}
    dptos = {r["cod_dpto"]: r["dpto"] for r in divipola}

    chip = socrata.query(
        "5c7g-ptic",
        select="id_entidad,razon_social,nit,a_o,periodo",
        where="(id_entidad between 210000000 and 219999999) or (id_entidad between 110000000 and 119999999)",
        order="a_o DESC,id_entidad",
        refresh=refresh,
    )

    entidades: dict[str, dict] = {}
    for r in chip:  # ordered newest first -> first seen wins
        cid = str(r["id_entidad"]).zfill(9)
        if cid.startswith("21"):
            code, tipo = cid[-5:], "municipio"
            if code not in mpios:
                continue
            nombre, depto = mpios[code]["nom_mpio"], mpios[code]["dpto"]
        elif cid.startswith("11") and cid.endswith("000"):
            code, tipo = cid[2:4], "departamento"
            if code not in dptos or code == "11":  # Bogotá is a district, handled as municipio
                continue
            nombre, depto = dptos[code], dptos[code]
        else:
            continue
        if code in entidades:
            continue
        entidades[code] = {
            "codigo": code, "tipo": tipo, "nombre": nombre.title(), "departamento": depto.title(),
            "nit": nit_base(r["nit"]), "chip_id": cid, "razon_social_chip": r["razon_social"],
        }

    missing = sorted(set(mpios) - set(entidades))
    out = {"entidades": entidades, "sin_nit": missing}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_m = sum(1 for e in entidades.values() if e["tipo"] == "municipio")
    n_d = len(entidades) - n_m
    print(f"referencia: {n_m} municipios, {n_d} departamentos con NIT; {len(missing)} municipios sin NIT -> {OUT}")
    return out


def load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))
