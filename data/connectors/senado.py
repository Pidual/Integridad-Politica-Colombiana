"""Actividad de los senadores 2026–2030 desde fuentes oficiales del Senado.

1. leyes.senado.gov.co (Sección de Leyes) — API JSON usada por su propio buscador:
     POST api/search_pdly.php  legislatura=YYYY-YYYY  -> proyectos de ley (autor, estado)
     GET  api/get_detalle_pdly.php?id=N               -> HTML con ponentes 1er/2º debate
   Métricas: proyectos_autor, proyectos_ley, ponencias

2. secretariasenado.gov.co (Secretaría General) — documentos de cada plenaria:
     "P 0xx ... CONTROL POLITICO ... APELLIDO NOMBRE"   -> debates_control
     "P 0xx ... APROBADA ... APELLIDO NOMBRE"           -> proposiciones
     "IM 0xx ... APELLIDO NOMBRE"                       -> impedimentos (informativo)
   Se acredita al primer senador nombrado ("Y VARIOS H S" = coautores no listados).

Los nombres se emparejan con el listado oficial (data/reference/senado_2026_2030.csv)
por coincidencia de palabras, tolerando errores de digitación. Lo que no se empareja
se reporta en data/processed/senado_sin_emparejar.json para revisión manual.

No hay asistencia ni votaciones nominales en formato estructurado: solo en actas PDF
(Gaceta del Congreso). Quedan como métricas faltantes.
"""
from __future__ import annotations

import csv
import difflib
import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
RAW = DATA / "raw" / "senado"
ROSTER = DATA / "reference" / "senado_2026_2030.csv"
OUT = DATA / "processed" / "senado_2026_2027.json"
UNMATCHED = DATA / "processed" / "senado_sin_emparejar.json"

LEYES = "https://leyes.senado.gov.co/api"
SECRETARIA = "http://www.secretariasenado.gov.co"
PLENARIAS = "/cuatrienio-2026-2030/legislatura-2026-2027/plenarias-6"
MESES = ["julio-6", "agosto-6", "septiembre-6", "octubre-6", "noviembre-6", "diciembre-6",
         "febrero-6", "marzo-6", "abril-6", "mayo-6", "junio-6"]
UA = {"User-Agent": "Mozilla/5.0 (integridad-politica-colombiana)"}
STOP = {"DE", "LA", "DEL", "LOS", "LAS", "Y", "H", "S", "R", "HS", "HR", "DR", "DRA", "SEN"}


# ---------------------------------------------------------------- http + cache
def _http(url: str, data: dict | None = None, cache_key: str | None = None, refresh: bool = False) -> str:
    path = RAW / (cache_key or re.sub(r"[^A-Za-z0-9]+", "_", url)[-150:])
    if cache_key and path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    body = None
    headers = dict(UA)
    if data is not None:
        boundary = "----ipc" + str(int(time.time() * 1000))
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in data.items()]
        body = ("".join(parts) + f"--{boundary}--\r\n").encode("utf-8")
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=120) as r:
                text = r.read().decode("utf-8", "replace")
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    if cache_key:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    time.sleep(0.15)  # be polite
    return text


# ---------------------------------------------------------------- name matching
def norm_tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return [t for t in re.findall(r"[A-Z]+", s) if t not in STOP and len(t) > 1]


class Matcher:
    """Match free-text mentions to roster names by shared (fuzzy) tokens."""

    def __init__(self, roster: list[dict]):
        self.people = [(r["nombre"], set(norm_tokens(r["nombre"]))) for r in roster]

    @staticmethod
    def _hit(tok: str, cand: set[str]) -> bool:
        if tok in cand:
            return True
        if len(tok) < 4:
            return False
        need = 0.84 if len(tok) >= 6 else 0.75  # 'JONH' ~ 'JOHN', 'ZUELTA' ~ 'ZULETA'
        return any(difflib.SequenceMatcher(None, tok, c).ratio() >= need for c in cand if len(c) >= 4)

    def match(self, text: str) -> str | None:
        toks = norm_tokens(text)
        if len(toks) < 2:
            return None
        scored = []
        for name, ptoks in self.people:
            hits = sum(1 for t in ptoks if self._hit(t, set(toks)))
            if hits >= 2:
                scored.append((hits, name))
        if not scored:
            return None
        scored.sort(reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None  # ambiguous
        return scored[0][1]


def load_roster() -> list[dict]:
    with open(ROSTER, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- leyes.senado.gov.co
def split_people(field: str) -> list[str]:
    field = re.sub(r"\b(H\.?\s?S\.?|H\.?\s?R\.?|HONORABLES?|SENADOR(A|ES)?|COORDINADOR(ES)?|PONENTES?)\s*:?", ",", field, flags=re.I)
    field = re.sub(r"\by otras firmas.*$", "", field, flags=re.I)
    return [p.strip(" .;") for p in re.split(r",|;|\by\b(?=\s+[A-ZÁÉÍÓÚÑ])| - ", field) if len(p.strip(" .;")) > 4]


def detalle_campos(page: str) -> dict:
    page = re.sub(r"<span id='short[^']*'>.*?</span>", "", page, flags=re.S)
    cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
             for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", page, re.S)]
    out = {}
    for k, v in zip(cells, cells[1:]):
        k = k.rstrip(":").strip()
        if k and k not in out:
            out[k] = v.replace("Ver menos", "").strip()
    return out


def proyectos(legislatura: str, refresh: bool) -> list[dict]:
    raw = _http(f"{LEYES}/search_pdly.php", {"legislatura": legislatura},
                cache_key=f"pdly_{legislatura}.json", refresh=refresh)
    data = json.loads(raw)
    if not data.get("success"):
        raise RuntimeError(f"leyes.senado.gov.co: {data.get('message')}")
    rows = data["data"]
    for r in rows:
        det = _http(f"{LEYES}/get_detalle_pdly.php?id={r['id']}", cache_key=f"pdly_det_{r['id']}.html", refresh=refresh)
        r["_detalle"] = detalle_campos(det)
    return rows


# ---------------------------------------------------------------- secretariasenado.gov.co
def _links(page: str, prefix: str) -> list[tuple[str, str]]:
    out = []
    for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", txt)).split())
        if href.startswith(prefix) and t and t != "folder" and (href, t) not in out:
            out.append((href, t))
    return out


def documentos_plenaria(refresh: bool) -> list[dict]:
    docs = []
    for mes in MESES:
        try:
            page = _http(f"{SECRETARIA}{PLENARIAS}/{mes}", cache_key=f"sec_{mes}.html", refresh=True)
        except Exception:
            continue
        depth = PLENARIAS.count("/") + 2
        for href, dia in _links(page, f"{PLENARIAS}/{mes}/"):
            if href.endswith("/file") or href.count("/") != depth:
                continue
            key = "sec_" + href.rsplit("/", 1)[-1] + ".html"
            dpage = _http(SECRETARIA + href, cache_key=key, refresh=refresh)
            for dh, titulo in _links(dpage, href + "/"):
                if dh.endswith("/file"):
                    docs.append({"sesion": dia, "titulo": titulo, "url": SECRETARIA + dh})
    return docs


def nombres_en_titulo(titulo: str) -> list[str]:
    """Candidate name chunks, in order, from a plenary document title.

    'P-003-ARTS ... APROBADAS-CORREA ANTONIO Y VARIOS H S'       -> ['CORREA ANTONIO']
    'IM-001-NEGADOS PL 047 DE 2025 SENADO-BAUTE GONZALO Y ARANA SELMEN' -> ['BAUTE GONZALO', 'ARANA SELMEN']
    'P 013 ... DEL ARROZ BARRERA JOSUE ALIRIO Y H R CASTELLANOS'  -> ['... BARRERA JOSUE ALIRIO']
    """
    t = titulo.upper()
    t = re.sub(r"\s+Y\s+VARIOS.*$", "", t)
    t = re.sub(r"\s+Y\s+H\s?\.?\s?R\b.*$", "", t)        # '... Y H R X' = coautor de Cámara
    t = re.sub(r"\bH\s?\.?\s?S\b\.?", " ", t)
    if "-" in t:                                       # formato con guiones: el nombre va al final
        t = t.rsplit("-", 1)[-1]
    parts = [p.split() for p in re.split(r"\s+Y\s+", t) if p.strip()]
    if not parts:
        return []
    # Last tokens of each ' Y '-separated chunk ('AGUA Y BIODIVERSIDAD ... OCAMPO ALEJANDRO' works too).
    return [" ".join(p[-5:]) for p in parts if p]


TIPO = re.compile(r"^\s*(P|CT|IM|INF|IN|RE)[\s-]+\d", re.I)


# ---------------------------------------------------------------- build
def build(refresh: bool = False, legislatura: str = "2026-2027") -> dict:
    roster = load_roster()
    m = Matcher(roster)
    stats: dict[str, Counter] = defaultdict(Counter)
    sin: Counter = Counter()

    pdly = proyectos(legislatura, refresh)
    for r in pdly:
        autores = {m.match(p) for p in split_people(r.get("autor") or "")} - {None}
        for p in split_people(r.get("autor") or ""):
            if not m.match(p) and re.search(r"H\.?\s?S", r.get("autor") or ""):
                sin["autor: " + p] += 1
        estado = (r.get("estado") or "").upper()
        for a in autores:
            stats[a]["proyectos_autor"] += 1
            if re.search(r"SANCIONAD|LEY DE LA REP|CONVERTID", estado):
                stats[a]["proyectos_ley"] += 1
        det = r["_detalle"]
        ponentes = set()
        for k in ("Ponente Primer Debate", "Ponente segundo debate"):
            for p in split_people(det.get(k, "")):
                who = m.match(p)
                if who:
                    ponentes.add(who)
        for p in ponentes:
            stats[p]["ponencias"] += 1

    docs = documentos_plenaria(refresh)
    for d in docs:
        tm = TIPO.match(d["titulo"])
        if not tm:
            continue
        tipo, titulo = tm.group(1).upper(), d["titulo"].upper()
        if tipo not in ("P", "IM"):
            continue
        found = [w for w in (m.match(c) for c in nombres_en_titulo(titulo)) if w]
        if not found:
            sin[f"{tipo}: {d['titulo'][:90]}"] += 1
            continue
        who = found[0]                       # el primero nombrado = proponente
        if tipo == "IM":
            for w in dict.fromkeys(found):   # cada senador nombrado declaró el impedimento
                stats[w]["impedimentos"] += 1
        elif "CONTROL POLITICO" in titulo:
            stats[who]["debates_control"] += 1
        elif re.search(r"APROBAD", titulo):
            stats[who]["proposiciones"] += 1

    out = {}
    for r in roster:
        s = stats.get(r["nombre"], Counter())
        out[r["nombre"]] = {
            "proyectos_autor": s["proyectos_autor"], "proyectos_ley": s["proyectos_ley"], "ponencias": s["ponencias"],
            "debates_control": s["debates_control"], "proposiciones": s["proposiciones"],
            "_impedimentos": s["impedimentos"],
        }
    meta = {"legislatura": legislatura, "proyectos": len(pdly), "documentos_plenaria": len(docs),
            "sesiones": len({d["sesion"] for d in docs})}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": meta, "senadores": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    UNMATCHED.write_text(json.dumps(sin.most_common(), ensure_ascii=False, indent=1), encoding="utf-8")
    active = sum(1 for v in out.values() if any(v[k] for k in ("proyectos_autor", "ponencias", "debates_control", "proposiciones")))
    print(f"Senado {legislatura}: {meta['proyectos']} proyectos, {meta['documentos_plenaria']} documentos de "
          f"{meta['sesiones']} plenarias; {active}/{len(out)} senadores con actividad; "
          f"{sum(sin.values())} menciones sin emparejar -> {OUT}")
    return {"meta": meta, "senadores": out}


if __name__ == "__main__":
    build()
