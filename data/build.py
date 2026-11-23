"""Construye el dataset REAL de alcaldías y gobernaciones a partir de los conectores.

    python -m data.build --years 2020 2021 2024 2025
    python -m data.build --years 2025 --refresh     # ignora caché

Pasos:
  1. Referencia DIVIPOLA <-> NIT (CHIP)          data/reference/entidades.json
  2. DNP: MDM, MDD, IDF, categorías y grupos      data/processed/dnp.json
  3. SECOP II por año                             data/processed/secop_<año>.json
  4. Une todo por (entidad, año) -> data/real/politicos.json  (formato del motor)
  5. Calcula ratings -> web/data/ratings.js

Cada registro es el CARGO en una temporada (p. ej. "Alcaldía de Medellín, 2021").
El nombre del titular se agrega desde data/reference/mandatarios.csv si existe
(columnas: codigo,periodo,nombre,partido,fuente). Sin titular se muestra el cargo.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scoring"))

from data.connectors import dnp, reference, secop  # noqa: E402
import engine  # noqa: E402

MANDATARIOS = ROOT / "data" / "reference" / "mandatarios.csv"
OUT = ROOT / "data" / "real" / "politicos.json"

SECOP_METRICS = ("contratacion_directa", "oferente_unico", "prorrogas")


def periodo(year: int) -> tuple[int, str]:
    """Local terms in Colombia: 2016–2019, 2020–2023, 2024–2027…"""
    start = 2016 + 4 * ((year - 2016) // 4)
    return start, f"{start}-{start + 3}"


def nearest(dnp_data: dict, code: str, field: str, year: int):
    """Closest year's value (categories/groups change rarely); prefers earlier years on ties."""
    years = sorted((abs(int(y) - year), int(y)) for y in dnp_data if field in dnp_data[y].get(code, {}))
    return (dnp_data[str(years[0][1])][code][field], years[0][1]) if years else (None, None)


def load_roster() -> dict:
    if not MANDATARIOS.exists():
        return {}
    with open(MANDATARIOS, encoding="utf-8-sig", newline="") as f:
        return {(r["codigo"].zfill(5 if len(r["codigo"]) > 2 else 2), r["periodo"]): r for r in csv.DictReader(f)}


def merge(years: list[int], ref: dict, dnp_data: dict, secop_by_year: dict) -> list[dict]:
    roster = load_roster()
    records = []
    for code, ent in sorted(ref["entidades"].items()):
        rol = "alcalde" if ent["tipo"] == "municipio" else "gobernador"
        for y in years:
            start, per = periodo(y)
            d = dnp_data.get(str(y), {}).get(code, {})
            s = secop_by_year.get(y, {}).get(code, {})
            m: dict = {}
            fuentes: dict = {}

            if rol == "alcalde" and d.get("mdm") is not None:
                m["mdm"] = d["mdm"]
                fuentes["mdm"] = f"DNP MDM {y}"
                base = dnp_data.get(str(start - 1), {}).get(code, {}).get("mdm")
                if base is not None and y > start - 1:
                    m["mdm_delta"] = round(d["mdm"] - base, 3)
                    fuentes["mdm_delta"] = f"DNP MDM {y} − {start - 1}"
            if rol == "gobernador" and d.get("mdd") is not None:
                m["mdd"] = d["mdd"]
                fuentes["mdd"] = f"DNP MDD {y}"
            for k in ("idf", "ejecucion_inversion"):
                if d.get(k) is not None:
                    m[k] = d[k]
                    fuentes[k] = f"DNP IDF {y}"
            for k in SECOP_METRICS:
                if s.get(k) is not None:
                    m[k] = s[k]
                    fuentes[k] = f"SECOP II {y}"
            if not m:
                continue

            categoria, cat_y = nearest(dnp_data, code, "categoria", y)
            grupo, grp_y = nearest(dnp_data, code, "grupo_dnp", y) if rol == "alcalde" else (None, None)
            who = roster.get((code, per), {})
            cargo = f"Alcaldía de {ent['nombre']}" if rol == "alcalde" else f"Gobernación de {ent['nombre']}"
            records.append({
                "id": f"{code}-{y}",
                "codigo": code,
                "nombre": who.get("nombre") or cargo,
                "titular_identificado": bool(who.get("nombre")),
                "rol": rol,
                "entidad": cargo if who.get("nombre") else ent["nombre"],
                "departamento": ent["departamento"],
                "categoria": categoria,
                "grupo_dnp": grupo,
                "partido": who.get("partido") or "—",
                "periodo": per,
                "temporada": y,
                "metricas": m,
                "fuentes": {**fuentes,
                            **({"categoria": f"DNP IDF {cat_y}"} if cat_y else {}),
                            **({"grupo_dnp": f"DNP MDM {grp_y}"} if grp_y else {})},
                "secop": s.get("_secop"),
                "tarjetas": [],
            })
    return records


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", type=int, nargs="+", default=[2020, 2021, 2024, 2025])
    ap.add_argument("--refresh", action="store_true", help="vuelve a descargar todo (ignora caché)")
    ap.add_argument("--skip-secop", action="store_true")
    args = ap.parse_args(argv)

    ref = reference.build(args.refresh) if args.refresh or not reference.OUT.exists() else reference.load()
    dnp_data = dnp.build(args.refresh)
    secop_by_year = {}
    if not args.skip_secop:
        for y in args.years:
            secop_by_year[y] = secop.build(y, ref["entidades"], args.refresh)

    records = merge(args.years, ref, dnp_data, secop_by_year)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "demo": False,
        "aviso": ("Datos reales de fuentes públicas (DNP, SECOP II, Contaduría). Se califica el CARGO por temporada; "
                  "tarjetas disciplinarias aún no integradas."),
        "temporadas": args.years,
        "politicos": records,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(records)} registros -> {OUT}")

    engine.main(["--data", str(OUT)])


if __name__ == "__main__":
    main()
