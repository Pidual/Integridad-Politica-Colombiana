"""Genera datos FICTICIOS de demostración.

Nombres, municipios, departamentos y partidos son inventados a propósito:
nunca se deben asociar cifras inventadas a personas reales.
Reemplazar por los conectores de data/ cuando existan datos reales.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rng = random.Random(2026)

NOMBRES = ["Andrés", "Camila", "Juan", "Valentina", "Carlos", "Laura", "Diego", "Mariana", "Felipe", "Daniela",
           "Santiago", "Paula", "Jorge", "Natalia", "Luis", "Catalina", "Mateo", "Juliana", "Sergio", "Ana"]
APELLIDOS = ["Restrepo", "Gómez", "Ospina", "Cárdenas", "Rincón", "Mejía", "Quintero", "Salazar", "Arango", "Vélez",
             "Patiño", "Londoño", "Bermúdez", "Cifuentes", "Montoya", "Zuluaga", "Ibarra", "Escobar", "Duarte", "Pineda"]
PARTIDOS = ["Partido Cóndor", "Movimiento Ceiba", "Alianza Orquídea", "Partido Río", "Frente Andino", "Coalición Llanura"]
DEPTOS = [f"Depto. Ficticio {i:02d}" for i in range(1, 15)]


def nombre():
    return f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)} (DEMO)"


def noisy(base, skill, spread, noise, lo=None, hi=None, nd=1):
    v = base + skill * spread + rng.gauss(0, noise)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return round(v, nd)


def maybe(v, p_missing=0.08):
    return None if rng.random() < p_missing else v


def cards(skill):
    out = []
    if rng.random() < 0.10 - 0.04 * skill:
        out.append({"tipo": "amarilla", "descripcion": "Multa disciplinaria en firme (demo)", "fuente": "Procuraduría – SIRI", "estado": "en_firme"})
    if rng.random() < 0.03 - 0.02 * skill:
        out.append({"tipo": "roja", "descripcion": "Inhabilidad en firme (demo)", "fuente": "Procuraduría – SIRI", "estado": "en_firme"})
    if rng.random() < 0.12:
        out.append({"tipo": "investigacion", "descripcion": "Indagación preliminar abierta (demo)", "fuente": "Procuraduría", "estado": "abierto"})
    return out


def ejecutivo(rol, i, categoria=None):
    s = rng.gauss(0, 1)
    rich = {"Especial": 1.2, "1": 0.9, "2": 0.5, "3": 0.3, "4": 0.0, "5": -0.3, "6": -0.6}.get(categoria, 0.3)
    m = {
        "plan_desarrollo": noisy(62, s, 10, 8, 10, 100),
        "homicidios_delta": noisy(0, -s, 3, 4),
        "saber11_delta": noisy(0, s, 3, 3),
        "idf": noisy(62 + 6 * rich, s, 5, 5, 20, 95),
        "ejecucion_inversion": noisy(72, s, 8, 7, 20, 100),
        "contratacion_directa": noisy(45, -s, 10, 10, 2, 98),
        "oferente_unico": noisy(35, -s, 9, 9, 0, 100),
        "prorrogas": noisy(15, -s, 5, 5, 0, 80),
        "indice_desempeno_inst": noisy(65 + 4 * rich, s, 6, 6, 20, 100),
        "ley2013": rng.random() < 0.75 + 0.1 * s,
    }
    if rol == "alcalde":
        m["mdm"] = noisy(50 + 8 * rich, s, 6, 6, 10, 90)
        m["mdm_delta"] = noisy(0.5, s, 2.5, 2.5)
        m["aprobacion"] = noisy(50, s, 12, 10, 5, 95) if categoria in ("Especial", "1") else None
        entidad = f"Municipio Ficticio {i:03d}"
    else:
        m["cobertura_vacunacion"] = noisy(86, s, 4, 4, 40, 100)
        m["regalias_ejecucion"] = noisy(60, s, 12, 10, 0, 100)
        m["aprobacion"] = noisy(48, s, 12, 10, 5, 95)
        entidad = DEPTOS[i % len(DEPTOS)]
    m = {k: maybe(v) for k, v in m.items()}
    return {
        "id": f"{rol}-{i:03d}", "nombre": nombre(), "rol": rol, "entidad": entidad,
        "departamento": DEPTOS[i % len(DEPTOS)] if rol == "alcalde" else entidad,
        "categoria": categoria, "partido": rng.choice(PARTIDOS), "periodo": "2024-2027",
        "temporada": 2025, "metricas": m, "tarjetas": cards(s),
    }


def legislador(rol, i):
    s = rng.gauss(0, 1)
    m = {
        "proyectos_autor": max(0, round(rng.gauss(10 + 4 * s, 4))),
        "proyectos_ley": max(0, round(rng.gauss(1.2 + 1.0 * s, 1))),
        "ponencias": max(0, round(rng.gauss(8 + 3 * s, 3))),
        "debates_control": max(0, round(rng.gauss(3 + 1.5 * s, 2))),
        "proposiciones": max(0, round(rng.gauss(5 + 2 * s, 2))),
        "asistencia": noisy(88, s, 5, 4, 30, 100),
        "participacion_votos": noisy(80, s, 7, 6, 20, 100),
        "ley2013": rng.random() < 0.8 + 0.1 * s,
        "impedimentos_declarados": noisy(70, s, 12, 12, 0, 100),
        "cuentas_claras_oportuno": rng.random() < 0.85 + 0.05 * s,
        "chequeos_falsos": max(0, round(rng.gauss(1 - 0.8 * s, 1.2))),
    }
    m = {k: maybe(v, 0.05) for k, v in m.items()}
    return {
        "id": f"{rol}-{i:03d}", "nombre": nombre(), "rol": rol,
        "entidad": "Senado de la República" if rol == "senador" else "Cámara de Representantes",
        "departamento": "Nacional" if rol == "senador" else DEPTOS[i % len(DEPTOS)],
        "categoria": None, "partido": rng.choice(PARTIDOS), "periodo": "2022-2026",
        "temporada": 2025, "metricas": m, "tarjetas": cards(s),
    }


def main():
    pols = []
    cats = ["Especial"] * 4 + ["1"] * 10 + ["2"] * 8 + ["3"] * 8 + ["4"] * 10 + ["5"] * 10 + ["6"] * 20
    for i, c in enumerate(cats, 1):
        pols.append(ejecutivo("alcalde", i, c))
    for i in range(1, 15):
        pols.append(ejecutivo("gobernador", i))
    for i in range(1, 41):
        pols.append(legislador("senador", i))
    for i in range(1, 51):
        pols.append(legislador("representante", i))

    out = ROOT / "data" / "sample" / "politicos.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "demo": True,
        "aviso": "Datos FICTICIOS generados para demostración. No corresponden a ninguna persona real.",
        "temporada": 2025,
        "politicos": pols,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(pols)} políticos ficticios -> {out}")


if __name__ == "__main__":
    main()
