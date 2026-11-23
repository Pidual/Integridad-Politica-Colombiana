"""Convierte un aporte ciudadano (Issue "Aportar evidencia") en un BORRADOR de evento.

    python data/eventos/importar_issue.py 12            # Issue #12 del repositorio
    python data/eventos/importar_issue.py 12 --repo Pidual/Integridad-Politica-Colombiana

El borrador entra a data/eventos/eventos.json con revisado=false y con crédito al
ciudadano (salvo que pidiera anonimato). Antes de aprobarlo, el equipo debe:
  1. abrir las fuentes y confirmar el hecho,
  2. ajustar nivel (1–3) o tipo_positivo (P1–P3), estado, título y resumen neutral,
  3. aprobar:  python data/eventos/revisar.py --aprobar ID --por "Nombre"
"""
import argparse
import datetime as dt
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

PATH = Path(__file__).with_name("eventos.json")

ETAPA_A_ESTADO = {
    "investigación periodística": ("sin_proceso", 3),
    "indagación preliminar": ("preliminar", 3),
    "investigación formal": ("abierto", 2),
    "acusación o juicio": ("abierto", 2),
    "condena o sanción de primera instancia": ("condena_no_firme", 2),
    "decisión en firme": ("en_firme", 1),
    "archivado": ("archivado", 2),
}


def slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:50]


def parse_form(body: str) -> dict:
    """GitHub issue forms render as '### Label' + blank line + value."""
    out, key = {}, None
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.*)", line)
        if m:
            key = m.group(1).strip()
            out[key] = ""
        elif key is not None:
            out[key] = (out[key] + "\n" + line).strip()
    return {k: ("" if v == "_No response_" else v) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("numero", type=int)
    ap.add_argument("--repo", default="Pidual/Integridad-Politica-Colombiana")
    a = ap.parse_args()

    url = f"https://api.github.com/repos/{a.repo}/issues/{a.numero}"
    req = urllib.request.Request(url, headers={"User-Agent": "integridad-politica-colombiana", "Accept": "application/vnd.github+json"})
    issue = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    f = parse_form(issue.get("body", ""))

    persona = f.get("Persona", "").strip()
    sentido = f.get("¿El hecho es a favor o en contra?", "")
    etapa = f.get("Estado o etapa, si lo sabes", "").lower()
    fuentes = [u for u in re.findall(r"https?://\S+", f.get("Fuentes (enlaces)", ""))]
    if not persona or not fuentes:
        raise SystemExit("El aporte no tiene persona o fuentes con enlace: no se puede importar.")

    positivo = sentido.lower().startswith("a favor")
    estado, nivel = "sin_proceso", 3
    for k, v in ETAPA_A_ESTADO.items():
        if k in etapa:
            estado, nivel = v
    anonimo = "anónimo" in f.get("Crédito", "").lower()
    user = issue.get("user", {}) or {}

    ev = {
        "id": f"aporte-{a.numero}-{slug(persona)}",
        "persona": persona,
        "rol": "senador",  # ajustar si es alcalde o gobernador
        "fecha": f.get("Fecha del hecho", "")[:10],
        "estado": "verificado" if positivo else estado,
        "titulo": (issue.get("title", "").replace("Evidencia:", "").strip() or "Aporte ciudadano") + " (titular por redactar)",
        "resumen": f.get("¿Qué pasó?", ""),
        "fuentes": [{"medio": urllib.request.urlparse(u).netloc, "url": u} for u in fuentes],
        "aportado_por": None if anonimo else {"usuario": "@" + user.get("login", ""), "url": issue.get("html_url")},
        "origen": {"issue": a.numero, "url": issue.get("html_url"), "importado": dt.date.today().isoformat()},
        "revisado": False,
    }
    if anonimo:
        ev["aportado_por"] = {"usuario": "un ciudadano anónimo"}
    if positivo:
        ev.update({"positivo": True, "tipo_positivo": "P3" if "reconoc" in etapa or "premio" in etapa else "P2"})
    else:
        ev["nivel"] = nivel

    db = json.loads(PATH.read_text(encoding="utf-8"))
    if any(e["id"] == ev["id"] for e in db["eventos"]):
        raise SystemExit(f"Ya existe {ev['id']}")
    db["eventos"].append(ev)
    PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Borrador creado: {ev['id']}  ({'a favor' if positivo else 'en contra'}, revisar nivel/estado/título)")
    print(f"Ver:      python data/eventos/revisar.py --ver {ev['id']}")
    print(f"Aprobar:  python data/eventos/revisar.py --aprobar {ev['id']} --por \"Tu nombre\"")


if __name__ == "__main__":
    main()
