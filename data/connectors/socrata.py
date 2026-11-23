"""Cliente mínimo para la API Socrata de datos.gov.co (SoQL), con caché en disco.

Opcional: exportar SOCRATA_APP_TOKEN para mayor cuota de peticiones.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.datos.gov.co/resource/{dataset}.json"
CACHE_DIR = Path(__file__).resolve().parents[1] / "raw" / "socrata"
PAGE = 50_000


def _get(url: str, retries: int = 4) -> list[dict]:
    headers = {"Accept": "application/json", "User-Agent": "integridad-politica-colombiana/0.1"}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=600) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as e:
            body = ""
            if isinstance(e, urllib.error.HTTPError):
                body = e.read().decode("utf-8", "replace")[:500]
                if 400 <= e.code < 500 and e.code != 429:
                    raise RuntimeError(f"Socrata {e.code}: {body}") from e
            if attempt == retries - 1:
                raise RuntimeError(f"Socrata falló tras {retries} intentos: {e} {body}") from e
            time.sleep(2 ** attempt * 3)
    return []


def query(dataset: str, *, select: str | None = None, where: str | None = None, group: str | None = None,
          order: str | None = None, refresh: bool = False, max_rows: int | None = None) -> list[dict]:
    """Run a SoQL query, paging through all results. Results are cached by query."""
    params = {k: v for k, v in {"$select": select, "$where": where, "$group": group}.items() if v}
    # Paging needs a deterministic order.
    params["$order"] = order or (group.split(",")[0] if group else ":id")
    key = hashlib.sha1(json.dumps([dataset, params, max_rows], sort_keys=True).encode()).hexdigest()[:16]
    cache = CACHE_DIR / f"{dataset}-{key}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))

    rows: list[dict] = []
    offset = 0
    while True:
        limit = PAGE if max_rows is None else min(PAGE, max_rows - len(rows))
        qs = urllib.parse.urlencode({**params, "$limit": limit, "$offset": offset})
        page = _get(BASE.format(dataset=dataset) + "?" + qs)
        rows.extend(page)
        offset += len(page)
        if len(page) < limit or (max_rows is not None and len(rows) >= max_rows):
            break

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows
