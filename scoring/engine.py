"""Motor de calificación — "rating tipo WhoScored" para políticos colombianos.

Pipeline por temporada (año):
  1. Agrupar a cada político con sus pares: mismo rol (posición) y misma liga
     (p. ej. alcaldes del mismo grupo de capacidades DNP, o categoría Ley 617).
  2. Para cada métrica, calcular un z-score robusto (mediana/MAD) dentro del grupo
     de pares, orientado para que "más alto = mejor", y recortado a ±z_cap.
  3. Promediar z por categoría (pesos por métrica) y luego entre categorías
     (pesos por categoría). Métricas faltantes se ignoran y se registra la cobertura.
  4. Encoger hacia el promedio cuando hay pocas métricas (como exigir minutos jugados).
  5. Mapear a 1–10: rating = baseline + scale * z_compuesto  (promedio = 6.0).
  6. Restar tarjetas en firme (amarilla/roja). Procesos abiertos no restan.

Solo usa la librería estándar.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def robust_z(values: list[float]) -> tuple[float, float]:
    """Return (center, spread) using median/MAD, falling back to stdev."""
    center = statistics.median(values)
    mad = statistics.median([abs(v - center) for v in values]) * 1.4826
    if mad > 1e-9:
        return center, mad
    if len(values) > 1:
        sd = statistics.pstdev(values)
        if sd > 1e-9:
            return statistics.mean(values), sd
    return center, 0.0


def percentile_rank(value: float, values: list[float], direction: int) -> float:
    """Share of peers this politician beats (0–100), respecting direction."""
    if direction < 0:
        value, values = -value, [-v for v in values]
    below = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return 100.0 * (below + 0.5 * equal) / len(values)


def to_number(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def league_of(record: dict, role_cfg: dict) -> str:
    """First league field with a known value wins (e.g. DNP capacity group, then Ley 617)."""
    fields = role_cfg.get("league_field")
    if not fields:
        return "Única"
    if isinstance(fields, str):  # legacy: single field with a flat mapping
        return role_cfg.get("leagues", {}).get(str(record.get(fields, "")), "Sin liga")
    for f in fields:
        league = role_cfg.get("leagues", {}).get(f, {}).get(str(record.get(f, "")))
        if league:
            return league
    return "Sin liga"


def compute(records: list[dict], config: dict) -> dict:
    rc = config["rating"]
    roles = config["roles"]

    # --- 1. peer groups -------------------------------------------------
    groups: dict[tuple, list[dict]] = defaultdict(list)
    role_groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        if r["rol"] not in roles:
            continue
        r["_liga"] = league_of(r, roles[r["rol"]])
        groups[(r["rol"], r["_liga"], r["temporada"])].append(r)
        role_groups[(r["rol"], r["temporada"])].append(r)

    def peers_for(r):
        g = groups[(r["rol"], r["_liga"], r["temporada"])]
        # Liga muy pequeña -> comparar contra todo el rol (evita z inestables).
        return g if len(g) >= rc["min_peer_group"] else role_groups[(r["rol"], r["temporada"])]

    # --- 2. metric stats per peer group (cached) ------------------------
    stats_cache: dict[tuple, dict] = {}

    def metric_stats(peers, metric):
        ck = (id(peers), metric)
        if ck not in stats_cache:
            vals = [x for x in (to_number(p["metricas"].get(metric)) for p in peers) if x is not None]
            stats_cache[ck] = {"values": vals, "cs": robust_z(vals) if len(vals) >= 3 else None}
        return stats_cache[ck]

    results = []
    for r in records:
        if r["rol"] not in roles:
            continue
        role = roles[r["rol"]]
        peers = peers_for(r)
        metrics_out = {}
        cat_acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
        total_w = sum(m["weight"] * role["categories"][m["category"]]["weight"] for m in role["metrics"].values())
        covered_w = 0.0

        for mkey, m in role["metrics"].items():
            val = to_number(r["metricas"].get(mkey))
            entry = {"valor": r["metricas"].get(mkey), "z": None, "percentil": None}
            st = metric_stats(peers, mkey)
            if val is not None and st["cs"] is not None:
                center, spread = st["cs"]
                z = 0.0 if spread == 0 else (val - center) / spread * m["direction"]
                z = clamp(z, -rc["z_cap"], rc["z_cap"])
                entry["z"] = round(z, 3)
                entry["percentil"] = round(percentile_rank(val, st["values"], m["direction"]), 1)
                cat_acc[m["category"]].append((z, m["weight"]))
                covered_w += m["weight"] * role["categories"][m["category"]]["weight"]
            metrics_out[mkey] = entry

        # --- 3. category and composite z --------------------------------
        categories_out = {}
        comp_num = comp_den = 0.0
        for ckey, c in role["categories"].items():
            items = cat_acc.get(ckey, [])
            if not items:
                categories_out[ckey] = {"z": None, "rating": None}
                continue
            cz = sum(z * w for z, w in items) / sum(w for _, w in items)
            categories_out[ckey] = {
                "z": round(cz, 3),
                "rating": round(clamp(rc["baseline"] + rc["scale"] * cz, rc["min"], rc["max"]), 2),
            }
            comp_num += cz * c["weight"]
            comp_den += c["weight"]

        coverage = covered_w / total_w if total_w else 0.0
        n_metrics = sum(len(v) for v in cat_acc.values())

        # --- 4–6. shrink, scale, cards ---------------------------------
        rating = raw = None
        penalty = 0.0
        cap = rc["max"]
        for card in r.get("tarjetas", []):
            ccfg = config["cards"].get(card.get("tipo"))
            if not ccfg:
                continue
            penalty += ccfg["penalty"]
            cap = min(cap, ccfg.get("rating_cap", rc["max"]))

        if comp_den and coverage >= rc["min_coverage"]:
            composite = comp_num / comp_den
            shrunk = composite * n_metrics / (n_metrics + rc["shrinkage_k"])
            raw = clamp(rc["baseline"] + rc["scale"] * shrunk, rc["min"], rc["max"])
            rating = clamp(min(raw - penalty, cap), rc["min"], rc["max"])

        ranked = [(k, v) for k, v in metrics_out.items() if v["percentil"] is not None]
        fortalezas = [k for k, v in sorted(ranked, key=lambda kv: -kv[1]["percentil"]) if v["percentil"] >= rc["strength_percentile"]][:4]
        debilidades = [k for k, v in sorted(ranked, key=lambda kv: kv[1]["percentil"]) if v["percentil"] <= rc["weakness_percentile"]][:4]

        results.append({
            "id": r["id"],
            "nombre": r["nombre"],
            "rol": r["rol"],
            "entidad": r.get("entidad"),
            "departamento": r.get("departamento"),
            "partido": r.get("partido"),
            "categoria": r.get("categoria"),
            "liga": r["_liga"],
            "temporada": r["temporada"],
            "grupo_pares": len(peers),
            "rating": None if rating is None else round(rating, 2),
            "rating_sin_tarjetas": None if raw is None else round(raw, 2),
            "penalizacion": round(penalty, 2),
            "cobertura": round(coverage, 3),
            "categorias": categories_out,
            "metricas": metrics_out,
            "tarjetas": r.get("tarjetas", []),
            "fortalezas": fortalezas,
            "debilidades": debilidades,
            # passthrough metadata (present in real data)
            **{k: r[k] for k in ("periodo", "grupo_dnp", "fuentes", "secop", "titular_identificado") if k in r},
        })

    # --- rankings --------------------------------------------------------
    for scope in (("rol", "temporada"), ("rol", "liga", "temporada")):
        buckets = defaultdict(list)
        for x in results:
            if x["rating"] is not None:
                buckets[tuple(x[k] for k in scope)].append(x)
        name = "rank_rol" if len(scope) == 2 else "rank_liga"
        for b in buckets.values():
            b.sort(key=lambda x: -x["rating"])
            for i, x in enumerate(b, 1):
                x[name] = i

    return {
        "config": {
            "version": config["version"],
            "rating": rc,
            "cards": config["cards"],
            "roles": {
                k: {
                    "label": v["label"],
                    "position": v["position"],
                    "categories": v["categories"],
                    "metrics": {mk: {kk: mv[kk] for kk in ("label", "category", "direction", "unit", "source")} for mk, mv in v["metrics"].items()},
                }
                for k, v in roles.items()
            },
        },
        "politicos": results,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Calcula ratings de políticos.")
    ap.add_argument("--data", default=str(ROOT / "data" / "sample" / "politicos.json"))
    ap.add_argument("--config", default=str(ROOT / "scoring" / "config.json"))
    ap.add_argument("--out", default=str(ROOT / "web" / "data" / "ratings.js"))
    args = ap.parse_args(argv)

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    out = compute(payload["politicos"], config)
    out["meta"] = {k: v for k, v in payload.items() if k != "politicos"}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(out, ensure_ascii=False, indent=1)
    # .js (no .json) para que web/index.html abra directo con file:// sin servidor.
    out_path.write_text(f"window.RATINGS = {body};\n", encoding="utf-8")
    out_path.with_suffix(".json").write_text(body, encoding="utf-8")
    rated = sum(1 for p in out["politicos"] if p["rating"] is not None)
    print(f"{rated}/{len(out['politicos'])} políticos calificados -> {out_path}")


if __name__ == "__main__":
    main()
