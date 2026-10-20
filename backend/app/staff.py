"""Synthetic staff. There is no login: the desk picks a role, and that is labelled as a demo control."""

STAFF = [
    {"id": "ana.reyes", "name": "Ana Reyes", "role": "analista",
     "title": "Analista de onboarding", "note": "SINTÉTICO"},
    {"id": "pablo.ortiz", "name": "Pablo Ortiz", "role": "cumplimiento",
     "title": "Responsable de cumplimiento", "note": "SINTÉTICO"},
    {"id": "lucia.mendez", "name": "Lucía Méndez", "role": "direccion",
     "title": "Directora de la mesa", "note": "SINTÉTICO"},
    {"id": "inspector.cnmv", "name": "Inspector (solo lectura)", "role": "inspector",
     "title": "Acceso de inspección", "note": "SINTÉTICO · no es un inspector real"},
]

ROLES = {s["id"]: s for s in STAFF}

# Who may take which decision.
CAN = {
    "analista": {"recomendar", "pedir_mas"},
    "cumplimiento": {"recomendar", "pedir_mas", "aceptar", "rechazar"},
    "direccion": {"recomendar", "pedir_mas", "aceptar", "rechazar"},
    "inspector": set(),
}


def get(staff_id: str) -> dict:
    if staff_id not in ROLES:
        raise KeyError(staff_id)
    return ROLES[staff_id]


def can_accept(role: str, required: str) -> bool:
    if role == "inspector":
        return False
    if required == "direccion":
        return role == "direccion"
    if required == "cumplimiento":
        return role in {"cumplimiento", "direccion"}
    return False
