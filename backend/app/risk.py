"""Transparent AML risk scorecard.

Weights are examples. Alterna and Finreg own the production calibration; the
scorecard shows every factor so a reviewer can disagree with a line, not a black box.
"""
from __future__ import annotations

WEIGHTS = {
    "residencia_mexico": (8, "Residencia en México (tercer país equivalente)"),
    "canal_no_presencial": (10, "Canal no presencial"),
    "importe_alto": (15, "Importe inicial ≥ 100.000 EUR"),
    "pep": (25, "Persona con responsabilidad pública (art. 14)"),
    "candidato_sanciones": (20, "Candidato en lista de sanciones, pendiente de descarte"),
    "hit_confirmado": (80, "Coincidencia confirmada en lista de sanciones"),
    "origen_fondos_doc": (-8, "Origen de fondos documentado"),
    "primer_ingreso_propio": (-6, "Primer ingreso desde cuenta propia en país equivalente"),
    "actividad_comprobada": (-4, "Actividad profesional documentada"),
}

HIGH = 40
STANDARD = 15


def score(snapshot: dict) -> dict:
    factors = []

    def add(key: str, applies: bool) -> None:
        if applies:
            points, label = WEIGHTS[key]
            factors.append({"id": key, "label": label, "points": points})

    add("residencia_mexico", (snapshot.get("person") or {}).get("country") == "MX")
    add("canal_no_presencial", snapshot.get("route") in {"primer_ingreso", "video_id", "qeas"})
    add("importe_alto", float(snapshot.get("initial_amount") or 0) >= 100_000)
    add("pep", bool(snapshot.get("is_pep") or snapshot.get("pep_hit")))
    screening = snapshot.get("screening") or {}
    add("hit_confirmado", bool(screening.get("confirmed_hit")))
    add("candidato_sanciones", bool(screening.get("candidates")) and not screening.get("confirmed_hit"))
    add("origen_fondos_doc", bool((snapshot.get("source_of_funds") or {}).get("documented")))
    xfer = snapshot.get("first_transfer") or {}
    add("primer_ingreso_propio", bool(xfer.get("same_holder") and xfer.get("equivalent_country")))
    add("actividad_comprobada", bool(snapshot.get("occupation_documented")))

    total = max(0, sum(f["points"] for f in factors))
    if screening.get("confirmed_hit") or total >= HIGH:
        level, regime = "alto", "reforzada"
    elif total >= STANDARD:
        level, regime = "medio", "normal"
    else:
        level, regime = "bajo", "normal"

    measures = ["Identificación formal", "Titular real", "Propósito e índole", "Contrastación de listas"]
    if regime == "reforzada":
        measures += [
            "Comprobar la actividad declarada (RD 304/2014 art. 10.2 y 20.1)",
            "Documentar el origen de los fondos (art. 20.1.c)",
            "Seguimiento reforzado (art. 20.1.g)",
        ]
    if snapshot.get("is_pep") or snapshot.get("pep_hit"):
        measures += [
            "Autorización del inmediato nivel directivo (Ley 10/2010 art. 14.5.b)",
            "Origen del patrimonio y de los fondos (art. 14.5.c)",
            "Seguimiento reforzado permanente; 2 años después del cese (art. 14.9)",
        ]

    approval = "direccion" if (snapshot.get("is_pep") or snapshot.get("pep_hit") or level == "alto") else "cumplimiento"
    review_months = 6 if regime == "reforzada" else 12
    return {
        "score": total,
        "level": level,
        "regime": regime,
        "factors": factors,
        "measures": measures,
        "approval_level": approval,
        "review_months": review_months,
        "weights_note": WEIGHTS and "[Pesos de ejemplo. Calibración: Alterna / Finreg.]",
        "thresholds": {"medio": STANDARD, "alto": HIGH},
    }
