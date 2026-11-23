# Integridad Política Colombiana

WhoScored‑style ratings for Colombian politicians: alcaldes, gobernadores, senadores and
representantes get a **1–10 season rating** computed from public data and compared only
against peers in the same role and "league" (municipal category), with yellow/red cards
for final sanctions.

## Quick start

**Real data** (alcaldías and gobernaciones, from datos.gov.co + DNP; see `docs/DATOS.md`):

```bash
python -m data.build --years 2020 2021 2024 2025   # downloads, merges, rates -> web/data/ratings.js
```

**Demo data** (fictional: made-up names and places, including senators and representatives):

```bash
python scoring/generate_sample.py && python scoring/engine.py
```

Then open `web/index.html` in a browser (no server needed). Tests: `python -m unittest discover -s tests`.

## Layout

```
scoring/config.json        roles, leagues, categories, metrics, weights, sources, cards
scoring/engine.py          rating engine (stdlib only)
scoring/generate_sample.py fictional demo data
data/connectors/           datos.gov.co (Socrata), SECOP I/II, DNP, DIVIPOLA↔NIT reference
data/sources/dnp.json      list of DNP result files (add new years here)
data/build.py              real-data pipeline
data/reference/            entity reference table (+ optional mandatarios.csv roster)
data/processed/            per-source outputs; data/real/ = engine input
data/sample/               fictional demo input
web/                       static site: tables by role, stat tabs, profile panel
docs/METODOLOGIA.md        full methodology and data sources
docs/DATOS.md              data pipeline, metric definitions, known gaps
tests/                     engine tests
```

## Input record

```json
{
  "id": "alcalde-001", "nombre": "…", "rol": "alcalde", "entidad": "…",
  "departamento": "…", "categoria": "1", "partido": "…", "periodo": "2024-2027",
  "temporada": 2025,
  "metricas": { "mdm": 61.2, "idf": 70.4, "contratacion_directa": 38.0, "...": null },
  "tarjetas": [{ "tipo": "amarilla", "descripcion": "…", "fuente": "Procuraduría – SIRI", "estado": "en_firme" }]
}
```

Missing metrics are `null` (they lower coverage, they don't count as zero).
Adding a role or metric is a config change only.

## Publicar (GitHub Pages, gratis)

1. Revisar la bitácora de integridad: `python data/eventos/revisar.py` lista los pendientes;
   `--ver ID` muestra un evento y sus fuentes; `--aprobar ID --por "Nombre"` lo aprueba.
2. Construir la versión pública (solo eventos aprobados):
   `python -m data.build --years 2020 2021 2024 2025 --solo-revisados`
3. `git push` a `main`: el flujo `.github/workflows/pages.yml` publica `web/` en
   https://pidual.github.io/Integridad-Politica-Colombiana/

`data/eventos/eventos.json` está en `.gitignore` mientras contenga eventos sin revisar
(el repositorio es público). Las solicitudes de rectificación llegan como Issues
(plantilla `.github/ISSUE_TEMPLATE/rectificacion.yml`).
