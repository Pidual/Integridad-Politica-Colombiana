# Data pipeline (real data)

```bash
python -m data.build --years 2020 2021 2024 2025   # first run ~10–15 min, then cached
python -m data.build --years 2025 --refresh        # re-download (ignore cache)
```

Output: `data/real/politicos.json` (engine input) and `web/data/ratings.js` (site).
Raw API responses are cached in `data/raw/` (git-ignored).

## What gets rated

The unit is **the office in a season**: "Alcaldía de Medellín, 2021". Data from a year is
credited to whoever held office that year (local terms: 2016–19, 2020–23, 2024–27). The
person's name is attached from `data/reference/mandatarios.csv` when available:

```csv
codigo,periodo,nombre,partido,fuente
05001,2024-2027,<nombre del alcalde>,<partido>,Registraduría – resultados 2023
```

Until the roster is loaded, the site shows the office name ("Alcaldía de X").

## Connectors

| Module | Source | Access | What it produces |
|---|---|---|---|
| `reference.py` | DANE DIVIPOLA (`gdxc-w37w`) + Contaduría CHIP registry (`5c7g-ptic`) | datos.gov.co API | DIVIPOLA ↔ NIT for 1,096 municipalities and 32 departments |
| `secop.py` | SECOP II contracts (`jbjy-vk9h`), SECOP II processes (`p6dx-8zbt`), SECOP I (`f789-7hwg`) | datos.gov.co API, aggregated server-side | `contratacion_directa`, `oferente_unico`, `prorrogas` |
| `dnp.py` | DNP MDM 2016–2020 (`nkjx-rsq7`) + Excel files listed in `data/sources/dnp.json` | API + file download | `mdm`, `mdm_delta`, `mdd`, `idf`, `ejecucion_inversion`, Ley 617 `categoria`, DNP `grupo_dnp` |

### Key design decisions

- **Join key is the NIT, not the name.** A municipality's NIT covers all its
  secretarías (e.g. Bogotá 899999061 covers the Secretaría General and Bomberos).
  Decentralized bodies (ESE hospitals, sports institutes, housing funds) have their
  own NIT and are excluded. Concejos, personerías and contralorías that share the NIT
  are removed by name.
- CHIP's `id_entidad` contains the DIVIPOLA code: `21NN` + 5-digit municipal code;
  `11DD` + `DD000` for departments.
- **Minimum volume:** at least 30 contracts to publish contracting metrics and at least 10
  competitive processes for `oferente_unico`.
- **Leagues:** a municipality is placed by its DNP *grupo de capacidades*
  (C, G1–G5), which the DNP designed for fair comparison. If that's missing, the Ley 617
  category is used. Values from the nearest available year are carried forward.

## Metric definitions

| Metric | Definition |
|---|---|
| `contratacion_directa` | value signed under "Contratación directa" ÷ total value signed in the year (SECOP I+II). "Contratación directa (con ofertas)" is not counted. |
| `oferente_unico` | awarded competitive processes (licitación, selección abreviada, concurso de méritos, mínima cuantía) with ≤ 1 response ÷ all awarded competitive processes (SECOP II only) |
| `prorrogas` | contracts with days added ÷ contracts signed |
| `mdm` / `mdd` | DNP Municipal / Departmental Performance Measurement, 0–100 |
| `mdm_delta` | MDM in the year minus MDM of the last year before the term began |
| `idf` | DNP Fiscal Performance Index (new methodology) |
| `ejecucion_inversion` | "Capacidad de ejecución de inversión" from the IDF annex |

## Known gaps (as of Nov 2026)

- **DNP results after 2021 have no public API.** IDF 2021–2025 can only be queried in
  the CIFFIT viewer (a Blazor app with no data endpoint), and MDM/MDD files for 2022+
  aren't linked from DNP's site. To add them, export or download the file, save it to
  `data/raw/dnp/`, and add an entry with `"path"` to `data/sources/dnp.json`.
  Until then, 2024–2025 offices only have contracting metrics, so they show category
  scores but no overall rating (coverage below 50%).
- No public bidder count in SECOP I, so `oferente_unico` covers SECOP II only.
- SECOP II "Adiciones" (`cb9c-h8sn`) has no amounts and no entity NIT. The value of
  additions needs a contract-level join (planned).
- 26 DIVIPOLA areas have no municipal NIT in CHIP (mostly non-municipalized areas in
  Amazonas, Guainía and Vaupés).
- Cards (Procuraduría/Contraloría sanctions) aren't connected yet. Real records show
  no cards rather than invented ones.
