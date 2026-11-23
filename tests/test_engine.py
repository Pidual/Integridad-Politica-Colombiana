import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scoring"))
import engine  # noqa: E402

CONFIG = json.loads((ROOT / "scoring" / "config.json").read_text(encoding="utf-8"))


def senators(n=12):
    out = []
    for i in range(n):
        out.append({
            "id": f"s{i}", "nombre": f"S{i}", "rol": "senador", "temporada": 2025, "tarjetas": [],
            "metricas": {
                "proyectos_autor": 5 + i, "proyectos_ley": i % 4, "ponencias": 4 + i, "debates_control": i % 5,
                "proposiciones": 3 + i % 3, "asistencia": 80 + i, "participacion_votos": 70 + i,
                "ley2013": i % 2 == 0, "impedimentos_declarados": 50 + 3 * i,
                "cuentas_claras_oportuno": True, "chequeos_falsos": 6 - i % 6,
            },
        })
    return out


def by_id(out):
    return {p["id"]: p for p in out["politicos"]}


class EngineTest(unittest.TestCase):
    def test_average_is_near_baseline(self):
        out = engine.compute(senators(), CONFIG)
        ratings = [p["rating_rendimiento"] for p in out["politicos"]]
        self.assertAlmostEqual(sum(ratings) / len(ratings), CONFIG["rating"]["baseline"], delta=0.6)
        self.assertTrue(all(1 <= r <= 10 for r in ratings))

    def test_lower_is_better_metric(self):
        out = by_id(engine.compute(senators(), CONFIG))
        # s0 has the most false claims (6), s5 the fewest (1)
        self.assertLess(out["s0"]["metricas"]["chequeos_falsos"]["percentil"], out["s5"]["metricas"]["chequeos_falsos"]["percentil"])

    def test_red_card_penalizes_and_caps(self):
        recs = senators()
        recs[11]["tarjetas"] = [{"tipo": "roja"}]
        p = by_id(engine.compute(recs, CONFIG))["s11"]
        self.assertLessEqual(p["rating_rendimiento"], CONFIG["cards"]["roja"]["rating_cap"])
        self.assertLess(p["rating_rendimiento"], p["rating_sin_tarjetas"])

    def test_open_investigation_does_not_penalize(self):
        base = by_id(engine.compute(senators(), CONFIG))["s3"]["rating_rendimiento"]
        recs = senators()
        recs[3]["tarjetas"] = [{"tipo": "investigacion"}]
        self.assertEqual(by_id(engine.compute(recs, CONFIG))["s3"]["rating_rendimiento"], base)

    def test_low_coverage_is_not_rated(self):
        recs = senators()
        recs[0]["metricas"] = {"asistencia": 99}
        p = by_id(engine.compute(recs, CONFIG))["s0"]
        self.assertIsNone(p["rating_rendimiento"])
        self.assertLess(p["cobertura"], CONFIG["rating"]["min_coverage"])

    def test_small_league_falls_back_to_role(self):
        recs = []
        for i, cat in enumerate(["Especial"] * 3 + ["6"] * 10):
            recs.append({"id": f"a{i}", "nombre": "x", "rol": "alcalde", "categoria": cat, "temporada": 2025,
                         "tarjetas": [], "metricas": {"mdm": 40 + i, "idf": 50 + i, "contratacion_directa": 60 - i,
                                                      "oferente_unico": 40 - i, "plan_desarrollo": 50 + i}})
        out = by_id(engine.compute(copy.deepcopy(recs), CONFIG))
        self.assertEqual(out["a0"]["liga"], "Cat. Especial–1")
        self.assertEqual(out["a0"]["grupo_pares"], 13)  # liga de 3 < min_peer_group -> rol completo
        self.assertEqual(out["a5"]["grupo_pares"], 10)

    def test_dnp_group_takes_precedence_over_category(self):
        rec = {"rol": "alcalde", "categoria": "6", "grupo_dnp": "G2"}
        self.assertEqual(engine.league_of(rec, CONFIG["roles"]["alcalde"]), "G2 · Media-alta")
        rec = {"rol": "alcalde", "categoria": "6"}
        self.assertEqual(engine.league_of(rec, CONFIG["roles"]["alcalde"]), "Cat. 4–6")

    def test_senate_headline_is_integrity(self):
        recs = senators()
        recs[0]["eventos"] = [{"nivel": 2, "estado": "abierto"}, {"nivel": 3, "estado": "preliminar"},
                              {"nivel": 2, "estado": "archivado"}, {"nivel": 2, "estado": "condena_no_firme"}]
        out = by_id(engine.compute(recs, CONFIG))
        cfg = CONFIG["integridad"]
        expected = cfg["base"] - cfg["niveles"]["2"]["resta"] - cfg["niveles"]["3"]["resta"] - cfg["resta_por_estado"]["condena_no_firme"]
        self.assertAlmostEqual(out["s0"]["rating"], expected)
        self.assertEqual(out["s1"]["rating"], cfg["base"])          # no events -> base
        self.assertEqual(out["s0"]["integridad"]["n_eventos"], 4)
        self.assertEqual(out["s0"]["rank_rol"], len(recs))            # lowest integrity ranks last

    def test_integrity_floor(self):
        evs = [{"nivel": 1, "estado": "en_firme"}] * 5
        self.assertEqual(engine.integrity_score(evs, CONFIG["integridad"])["nota"], CONFIG["integridad"]["min"])

    def test_positive_events_add_but_are_capped(self):
        cfg = CONFIG["integridad"]
        evs = [{"positivo": True, "tipo_positivo": "P2", "estado": "verificado"}] * 5
        r = engine.integrity_score(evs, cfg)
        self.assertEqual(r["suma_total"], cfg["tope_positivos"])
        self.assertEqual(r["nota"], min(cfg["max"], cfg["base"] + cfg["tope_positivos"]))
        mixed = engine.integrity_score([{"positivo": True, "tipo_positivo": "P1", "estado": "verificado"},
                                        {"nivel": 2, "estado": "abierto"}], cfg)
        self.assertAlmostEqual(mixed["nota"], cfg["base"] + cfg["positivos"]["P1"]["suma"] - cfg["niveles"]["2"]["resta"])


if __name__ == "__main__":
    unittest.main()
