"""Perfiles de Wikipedia en español para los senadores (resumen + enlace).

Wikipedia es fuente secundaria: se usa para el PERFIL (biografía, cargos), no como
prueba de escándalos. Para la bitácora de integridad se usan las referencias que el
artículo cita, agregadas a mano en data/eventos/eventos.json.

APIs:
  https://es.wikipedia.org/w/api.php?action=query&list=search   (buscar el artículo)
  https://es.wikipedia.org/api/rest_v1/page/summary/<título>     (resumen, foto, Wikidata)

Emparejamiento estricto para evitar homónimos: el título debe compartir el primer
apellido y al menos otra palabra del nombre oficial, y el resumen debe describir a
un político colombiano.

Salida: data/reference/wikipedia_senado.json
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .senado import norm_tokens

REF = Path(__file__).resolve().parents[1] / "reference"
OUT = REF / "wikipedia_senado.json"
API = "https://es.wikipedia.org/w/api.php"
SUMMARY = "https://es.wikipedia.org/api/rest_v1/page/summary/"
UA = {"User-Agent": "integridad-politica-colombiana/0.1 (investigacion civica; sin fines comerciales)"}
POLITICO = re.compile(r"senador|senadora|pol[ií]tic|congresista|representante|gobernador|alcalde|concejal|ministr", re.I)


def _get(url: str, tries: int = 6) -> dict:
    """GET with polite pacing; on 429 honour Retry-After (or back off) and retry."""
    import urllib.error
    for i in range(tries):
        try:
            time.sleep(1.0)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 15 * (i + 1)
            time.sleep(min(wait, 120))
    return {}


def buscar(nombre: str) -> dict | None:
    toks = norm_tokens(nombre)
    if len(toks) < 2:
        return None
    primer_apellido = toks[0]
    q = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": f"{nombre} Colombia",
                                "format": "json", "srlimit": 6})
    for hit in _get(f"{API}?{q}").get("query", {}).get("search", []):
        ttoks = set(norm_tokens(hit["title"]))
        if primer_apellido not in ttoks or len(ttoks & set(toks)) < 2:
            continue
        s = _get(SUMMARY + urllib.parse.quote(hit["title"].replace(" ", "_")))
        texto = f"{s.get('description', '')} {s.get('extract', '')}"
        if s.get("type") != "standard" or not POLITICO.search(texto) or "Colombia" not in texto and "colombian" not in texto.lower():
            continue
        return {
            "titulo": s.get("title"),
            "url": s.get("content_urls", {}).get("desktop", {}).get("page"),
            "descripcion": s.get("description"),
            "extracto": s.get("extract"),
            "wikidata": s.get("wikibase_item"),
            "foto": (s.get("thumbnail") or {}).get("source"),
            "editado": s.get("timestamp"),
        }
    return None


def build(roster_csv: Path | None = None) -> dict:
    roster_csv = roster_csv or REF / "senado_2026_2030.csv"
    with open(roster_csv, encoding="utf-8", newline="") as f:
        nombres = [r["nombre"] for r in csv.DictReader(f)]
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}   # resumable
    for n in nombres:
        if n in out:
            continue
        try:
            p = buscar(n)
        except Exception as e:  # network hiccup: keep going
            print(f"  ! {n}: {e}")
            p = None
        if p:
            out[n] = {**p, "consultado": dt.date.today().isoformat()}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wikipedia: {len(out)}/{len(nombres)} senadores con artículo emparejado -> {OUT}")
    return out


if __name__ == "__main__":
    build()
