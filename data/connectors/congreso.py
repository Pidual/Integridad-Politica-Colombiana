"""Congreso: listados oficiales de senadores y representantes.

Senado 2026–2030: directorio A–Z de senado.gov.co (no hay dataset abierto actualizado;
  el de datos.gov.co, sjwx-dr6n, es del período 2018–2022).
Cámara 2026–2027: datos.gov.co 5pt5-nxdp.

Salida: data/reference/senado_2026_2030.csv, data/reference/camara_2026_2030.csv
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import re
import urllib.request
from pathlib import Path

from . import socrata

REF = Path(__file__).resolve().parents[1] / "reference"
SENADO_URL = "https://www.senado.gov.co/index.php/el-senado/senadores?lastletter=Todos"

_ENTRY = re.compile(
    r'<div class="modazdirectory__result[^"]*">\s*<img src="([^"]*)"[^>]*>\s*<div>\s*<h3>(.*?)</h3>\s*<p>(.*?)</p>\s*<p>(.*?)</p>',
    re.S,
)


def _clean(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def parse_senado(page: str) -> list[dict]:
    """Parse the A–Z directory. The page lists each senator twice (layout), so dedupe by name."""
    out: dict[str, dict] = {}
    for img, nombre, partido, oficina in _ENTRY.findall(page):
        n = _clean(nombre)
        if n and n not in out:
            out[n] = {"nombre": n, "partido": _clean(partido), "oficina": _clean(oficina), "foto": img}
    return sorted(out.values(), key=lambda r: r["nombre"])


def fetch_senado() -> list[dict]:
    req = urllib.request.Request(SENADO_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        page = r.read().decode("utf-8", "replace")
    rows = parse_senado(page)
    if len(rows) < 90:
        raise RuntimeError(f"Directorio del Senado incompleto ({len(rows)} registros); ¿cambió el HTML?")
    return rows


def fetch_camara(refresh: bool = False) -> list[dict]:
    # The published columns are shifted by one: '_' holds the name, 'apelidos_y_nombre' the
    # circunscripción, 'partido_o_movimiento' the party and 'circunscripcion' the e-mail.
    rows = socrata.query("5pt5-nxdp", refresh=refresh)
    out: dict[str, dict] = {}
    for r in rows:
        nombre = " ".join((r.get("_") or "").split())
        if not nombre or nombre in out:
            continue
        out[nombre] = {"nombre": nombre, "partido": (r.get("partido_o_movimiento") or "").strip(),
                       "circunscripcion": (r.get("apelidos_y_nombre") or "").strip().title(),
                       "correo": (r.get("circunscripcion") or "").strip()}
    return sorted(out.values(), key=lambda r: r["nombre"])


def _write(path: Path, rows: list[dict], fuente: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) + ["fuente", "consultado"]
    today = dt.date.today().isoformat()
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "fuente": fuente, "consultado": today})


def build(refresh: bool = False) -> dict:
    sen = fetch_senado()
    _write(REF / "senado_2026_2030.csv", sen, SENADO_URL)
    print(f"Senado 2026–2030: {len(sen)} senadores -> {REF / 'senado_2026_2030.csv'}")
    cam = fetch_camara(refresh)
    _write(REF / "camara_2026_2030.csv", cam, "datos.gov.co 5pt5-nxdp")
    print(f"Cámara 2026–2030: {len(cam)} representantes -> {REF / 'camara_2026_2030.csv'}")
    return {"senado": sen, "camara": cam}


if __name__ == "__main__":
    build()
