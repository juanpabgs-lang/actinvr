"""MiFID II classification, suitability (Alterna profiles) and appropriateness."""
from __future__ import annotations

PROFILES = {
    "conservador": {
        "label": "Conservador",
        "equity": (0, 20),
        "mixed": (30, 50),
        "fixed_income": (70, 100),
        "volatility": 4,
        "text": "Buscas preservar lo que tienes. Aceptas pérdidas muy bajas a corto plazo. La renta fija queda entre el 70 y el 100 por ciento; los mixtos, entre el 30 y el 50. Volatilidad máxima del 4 por ciento.",
    },
    "moderado": {
        "label": "Moderado",
        "equity": (0, 30),
        "fixed_income": (70, 100),
        "volatility": 8,
        "text": "Buscas estabilidad y aceptas pérdidas limitadas. La renta variable queda entre el 0 y el 30 por ciento; la renta fija, entre el 70 y el 100. Volatilidad máxima del 8 por ciento.",
    },
    "equilibrado": {
        "label": "Equilibrado",
        "equity": (30, 70),
        "fixed_income": (50, 70),
        "volatility": 12,
        "text": "Buscas crecer y aceptas pérdidas a medio plazo. Renta variable entre el 30 y el 70 por ciento; renta fija entre el 50 y el 70. Volatilidad máxima del 12 por ciento.",
    },
    "agresivo": {
        "label": "Agresivo",
        "equity": (70, 100),
        "fixed_income": (0, 30),
        "volatility": 20,
        "text": "Buscas la mayor rentabilidad y aceptas un riesgo alto. La cartera puede ir al 100 por ciento en renta variable. Volatilidad máxima del 20 por ciento.",
    },
}

MANUSCRIPT_NOT_CONVENIENT = "este producto es complejo y se considera no conveniente para mí"
MANUSCRIPT_NOT_ASSESSED = "este es un producto complejo y por falta de información no ha podido ser evaluado como conveniente para mí"

QUESTIONS = [
    {"id": "horizon", "text": "¿En cuántos años piensas usar este dinero?",
     "options": [("0-2", "Menos de 2 años", 0), ("3-5", "De 3 a 5 años", 1), ("6-10", "De 6 a 10 años", 2), ("10+", "Más de 10 años", 3)]},
    {"id": "capacity", "text": "Si la cuenta bajara un 20 por ciento en un año, ¿qué harías?",
     "options": [("sell", "La cerraría", 0), ("wait", "Esperaría a recuperar", 2), ("buy", "Añadiría dinero", 3)]},
    {"id": "experience", "text": "¿Qué has usado antes?",
     "options": [("none", "Nada, o solo una cuenta de ahorro", 0), ("funds", "Fondos o acciones", 2), ("complex", "Derivados u otros productos complejos", 3)]},
    {"id": "knowledge", "text": "¿Qué estudiaste o a qué te dedicas?",
     "options": [("other", "Otra cosa", 0), ("related", "Algo cercano a finanzas o empresa", 1), ("finance", "Finanzas, economía o inversión", 2)]},
    {"id": "income", "text": "¿De dónde sale el dinero que vas a invertir?",
     "options": [("salary", "Nómina o honorarios", 1), ("sale", "Venta de un bien o de un negocio", 2), ("inheritance", "Herencia o donación", 1), ("other", "Otra fuente", 1)]},
    {"id": "share", "text": "¿Qué parte de lo que tienes va a esta cuenta?",
     "options": [("low", "Menos de un cuarto", 3), ("mid", "Entre un cuarto y la mitad", 2), ("high", "Más de la mitad", 0)]},
    {"id": "sustainability", "text": "¿Quieres que la sostenibilidad cuente en las recomendaciones?",
     "options": [("yes", "Sí", None), ("no", "No tengo preferencia", None)]},
]


def classify(requested: str | None = None) -> dict:
    return {
        "category": "minorista",
        "requested": requested,
        "note": "Clasificación por defecto (Ley 6/2023 art. 193). El cliente puede solicitar tratamiento como profesional (art. 195).",
    }


def _points(answers: dict) -> tuple[int, int]:
    total, answered = 0, 0
    for q in QUESTIONS:
        if q["id"] == "sustainability":
            continue
        raw = answers.get(q["id"])
        for value, _label, pts in q["options"]:
            if value == raw and pts is not None:
                total += pts
                answered += 1
    return total, answered


def profile_from_points(points: int) -> str:
    if points <= 5:
        return "conservador"
    if points <= 9:
        return "moderado"
    if points <= 13:
        return "equilibrado"
    return "agresivo"


def suitability(answers: dict) -> dict:
    points, answered = _points(answers)
    complete = answered == 6 and answers.get("sustainability") in {"yes", "no"}
    key = profile_from_points(points) if complete else None
    profile = dict(PROFILES[key], id=key) if key else None
    return {
        "complete": complete,
        "points": points,
        "answered": answered,
        "profile": key,
        "profile_detail": profile,
        "sustainability": answers.get("sustainability") == "yes" if answers.get("sustainability") else None,
        "answers": answers,
        "declaration": (
            f"Perfil {profile['label']}. {profile['text']} "
            f"{'Con' if answers.get('sustainability') == 'yes' else 'Sin'} preferencias de sostenibilidad."
            if profile else None
        ),
    }


def appropriateness(answers: dict, product: dict) -> dict:
    complex_ = bool(product.get("complex"))
    experience = answers.get("experience")
    knowledge = answers.get("knowledge")
    if experience is None and knowledge is None:
        convenient, reason = None, "falta_informacion"
    elif complex_ and experience != "complex" and knowledge != "finance":
        convenient, reason = False, "no_conveniente"
    else:
        convenient, reason = True, "conveniente"
    manuscript = None
    if complex_ and convenient is False:
        manuscript = MANUSCRIPT_NOT_CONVENIENT
    elif complex_ and convenient is None:
        manuscript = MANUSCRIPT_NOT_ASSESSED
    return {
        "done": experience is not None or knowledge is not None or reason == "falta_informacion",
        "complex": complex_,
        "product": product.get("name"),
        "convenient": convenient,
        "reason": reason,
        "manuscript_required": manuscript,
        "manuscript": answers.get("manuscript") if answers.get("manuscript") == manuscript else None,
        "warning": (
            f"Producto complejo: {product.get('name')}. "
            + ("No se considera conveniente." if convenient is False else "No ha podido evaluarse por falta de información.")
            if complex_ and convenient is not True else None
        ),
    }
