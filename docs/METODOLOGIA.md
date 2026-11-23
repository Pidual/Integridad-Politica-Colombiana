# Methodology — rating politicians like footballers

The idea: copy what makes WhoScored ratings useful (one comparable number per player,
built from many stats, measured against players in the **same position and league**)
and apply it to Colombian public officials, adding the integrity layer that
integrityindex.us focuses on.

## 1. The football mapping

| Football (WhoScored)            | Here                                                                                  |
|---------------------------------|---------------------------------------------------------------------------------------|
| Position (GK, DF, MF, FW)       | **Role**: alcalde, gobernador, senador, representante (more later: ministros, concejales, diputados) |
| League                          | **Peer group**. Mayors are grouped by DNP *grupo de capacidades* (Ciudades, G1–G5: the DNP's own grouping for comparing municipalities with similar starting conditions). If that's missing, the Ley 617 category is used (Especial–1, 2–3, 4–6). Others share one league. |
| Match / season rating 1–10      | **Season rating** (one per calendar year), 1–10, **6.0 = average of the peer group** |
| Stat categories (Summary, Defensive, Offensive, Passing) | **Categories**: Gestión, Fiscal, Contratación, Ciudadanía (executives); Producción legislativa, Control político, Asistencia y voto, Transparencia (legislators) |
| Goals / assists                 | Bills that became law / ponencias (legislators); outcome improvements (executives)   |
| Minutes played                  | **Data coverage**. Under 50% of weighted metrics → no rating ("N/D")                |
| Yellow / red cards              | Sanctions **already final (en firme)** — see §4                                       |
| VAR review                      | Open investigation: shown, **does not subtract** (presunción de inocencia)            |
| Strengths / weaknesses          | Metrics at ≥ P80 / ≤ P20 versus peers                                                  |
| Team of the week                | "Equipo de la temporada": top ratings per role/league                                 |

The key design rule: **you are only compared with people who play the same game.**
A mayor of a category‑6 municipality with tiny budget is not compared with the mayor of
a capital city, the same way a Liga BetPlay player is not compared directly with a
Premier League player.

## 2. Computing the rating

For each season, role and league:

1. **Normalize each metric** with a robust z‑score: `z = (x − median) / (1.4826 · MAD)`,
   flipped for "lower is better" metrics (e.g. % direct contracting), capped at ±3 so a
   single outlier stat can't dominate.
2. **Category score** = weighted mean of the metric z's in that category.
3. **Composite** = weighted mean of category scores (weights in `scoring/config.json`).
4. **Shrinkage** (small sample protection): `composite · n / (n + 2)`, where `n` is the
   number of metrics available. Someone with 3 metrics can't look like a superstar.
5. **Scale**: `rating = 6.0 + 1.5 · composite`, clipped to [1, 10].
6. **Cards**: subtract penalties, apply caps.

Leagues with fewer than 8 members fall back to comparing against the whole role.

### Level vs. improvement ("xG thinking")
Rich cities score higher on levels (IDF, MDM) almost automatically. To reward *the
manager* and not *the club budget*, executives are also measured on **change during
their term** (`mdm_delta`, `homicidios_delta`, `saber11_delta`). Next step: a regression
of expected outcomes given population, rurality, budget and starting baseline, and rate
the residual — the political equivalent of goals minus xG.

## 3. Metrics and sources

All metrics, weights, directions and sources live in `scoring/config.json`. Main sources:

| Source | What it gives | Access |
|---|---|---|
| DNP – Medición de Desempeño Municipal (MDM), Índice de Desempeño Fiscal (IDF), TerriData | Management and fiscal performance by municipality/department | datos.gov.co, terridata.dnp.gov.co |
| SECOP I / II (Colombia Compra Eficiente) | Contracts: direct contracting share, single bidder, additions | datos.gov.co Socrata API |
| CHIP / FUT (Contaduría) | Budget execution | chip.gov.co |
| Función Pública – FURAG/MIPG, Aplicativo Ley 2013 | Institutional performance, asset & conflict-of-interest declarations | funcionpublica.gov.co |
| Procuraduría – SIRI | Disciplinary sanctions (cards) | certificado de antecedentes / SIRI |
| Contraloría – Boletín de responsables fiscales | Fiscal liability (cards) | contraloria.gov.co |
| Consejo de Estado | Pérdida de investidura (cards) | relatoría |
| CNE – Cuentas Claras | Campaign finance reporting | cnecuentasclaras.gov.co |
| Congreso Visible (Uniandes), Gaceta del Congreso, Senado/Cámara | Bills, ponencias, debates, attendance, roll-call votes | congresovisible.uniandes.edu.co |
| Policía Nacional, Medicina Legal, ICFES, MinSalud | Outcomes: homicides, Saber 11, vaccination | datos.gov.co |
| Invamer / CNC polls | Approval ("fan rating") — only large cities | published reports |
| Colombiacheck, La Silla Vacía | Fact-checked false claims | websites |

## 4. Cards and fairness rules

| Card | Trigger (must be **en firme**) | Effect |
|---|---|---|
| 🟨 Amarilla | Amonestación or disciplinary fine, fiscal finding with incidence, CNE sanction | −0.3 each |
| 🟥 Roja | Destitución / inhabilidad, fallo de responsabilidad fiscal, pérdida de investidura, final criminal conviction | −1.5 and rating capped at 4.5 |
| VAR | Open process, no final decision | shown, **0 penalty** |

Non‑negotiables for credibility (and legal safety):

- Every number links to a public source; every card cites the decision.
- Open investigations never reduce a score.
- Methodology and weights are public and versioned (`config.version`); every rating
  is reproducible from raw data with `python scoring/engine.py`.
- Officials get a right of reply / correction channel before publication.
- Bill counts are weighted low; laws passed weigh 3×, so spamming bills doesn't pay.

## 5. Roadmap

1. ✅ **Data connectors** (`data/connectors/`): SECOP I/II, DNP MDM/MDD/IDF, and a
   DIVIPOLA↔NIT reference table. See `docs/DATOS.md`. Pending: DNP files for 2022+, plus
   homicides (Policía), Saber 11 (ICFES) and vaccination (MinSalud), all of which have
   datos.gov.co APIs.
2. Official roster: Registraduría results 2023 (local) and 2022 (Congress) → IDs for
   every mayor, governor, senator and representative.
3. Procuraduría / Contraloría cards, with manual verification.
4. Congreso Visible scraper for legislators.
5. Quarterly "match ratings" + season average, form charts, head-to-head comparison.
6. Expected-performance model (xG analogue) for executives.
7. Extra roles: ministros, concejales of capitals, diputados.
