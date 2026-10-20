"""Synthetic client personas. Every field is invented. Names do not identify anyone."""
from __future__ import annotations

from datetime import date, timedelta

from .checks import mx_ids

TODAY = date(2026, 10, 20)


def _person(nombres, a1, a2, dob, sex, state, street, number, colonia, cp, alcaldia,
            bank="980", plaza="180", account="01234567891", city="Ciudad de México") -> dict:
    d = date.fromisoformat(dob)
    curp = mx_ids.build_curp(a1, a2, nombres, d, sex, state, "A")
    rfc = mx_ids.build_rfc(a1, a2, nombres, d, "A1")
    clabe = mx_ids.build_clabe(bank, plaza, account)
    return {
        "nombres": nombres, "apellido1": a1, "apellido2": a2, "dob": dob, "sex": sex,
        "nationality": "MX", "country": "MX", "state": state, "curp": curp, "rfc": rfc,
        "email": f"{nombres.split()[0].lower()}.{a1.lower()}@correo-sintetico.mx",
        "phone": "+52 55 1000 0000",
        "address": {"calle": street, "numero": number, "colonia": colonia, "cp": cp,
                    "alcaldia": alcaldia, "ciudad": city, "pais": "MX"},
        "clabe": clabe, "bank_code": bank,
    }


# Live flow uses this unused persona so the overnight queue stays intact.
LIVE = {
    "id": "live",
    "label": "Rodrigo Iván Morales Trejo · medianoche en CDMX",
    "person": _person("Rodrigo Iván", "Morales", "Trejo", "1991-05-18", "H", "JC",
                      "Calle Marsella", "18", "Juárez", "06600", "Cuauhtémoc",
                      account="11223344556"),
    "occupation": "Diseñador industrial",
    "purpose": "Inversión a medio plazo de ahorros personales",
    "initial_amount": 45_000,
    "service": "asesoramiento",
    "route": "primer_ingreso",
}

SEEDS = [
    {
        "seed": "limpia",
        "pseudonym": "Ana Sofía Ramírez Soto",
        "person": _person("Ana Sofía", "Ramírez", "Soto", "1988-07-22", "M", "DF",
                          "Calle Durango", "45", "Roma Norte", "06700", "Cuauhtémoc"),
        "occupation": "Ingeniera de software", "purpose": "Inversión de ahorros",
        "initial_amount": 40_000, "service": "asesoramiento", "route": "primer_ingreso",
        "answers": {"horizon": "6-10", "capacity": "wait", "experience": "funds",
                    "knowledge": "related", "income": "salary", "share": "mid", "sustainability": "no"},
        "submitted_cdmx": "2026-10-20T00:18:00-06:00",
        "story": "Expediente limpio. Listo para aceptar.",
    },
    {
        "seed": "importe_alto",
        "pseudonym": "Diego Armando Cruz Villalobos",
        "person": _person("Diego Armando", "Cruz", "Villalobos", "1979-03-09", "H", "NL",
                          "Av. Constitución", "1020", "Centro", "64000", "Monterrey",
                          plaza="190", account="99887766554", city="Monterrey"),
        "occupation": "Empresario", "purpose": "Gestión de liquidez tras venta de un inmueble",
        "initial_amount": 250_000, "service": "gdc", "route": "primer_ingreso",
        "sof_kind": "venta",
        "answers": {"horizon": "6-10", "capacity": "wait", "experience": "funds",
                    "knowledge": "related", "income": "sale", "share": "mid", "sustainability": "yes"},
        "submitted_cdmx": "2026-10-20T01:05:00-06:00",
        "story": "Importe alto con origen documentado. Diligencia reforzada, no PEP.",
    },
    {
        "seed": "pep",
        "pseudonym": "Luis Alberto Ramos Delgado",
        "person": _person("Luis Alberto", "Ramos", "Delgado", "1966-11-02", "H", "GT",
                          "Calle Pedro Moreno", "8", "Jardines del Moral", "37160", "León",
                          plaza="200", account="55667788990", city="León"),
        "occupation": "Consultor", "purpose": "Inversión personal",
        "initial_amount": 80_000, "service": "asesoramiento", "route": "primer_ingreso",
        "is_pep": True, "pep_declared": True,
        "pep_role": "ex diputado federal (sintético), cese 31 ago 2024",
        "answers": {"horizon": "3-5", "capacity": "wait", "experience": "funds",
                    "knowledge": "related", "income": "salary", "share": "low", "sustainability": "no"},
        "submitted_cdmx": "2026-10-19T23:40:00-06:00",
        "story": "PEP declarado. Requiere autorización de dirección (art. 14.5.b).",
    },
    {
        "seed": "sanciones_descartada",
        "pseudonym": "Elena Vásquez Ríos",
        "person": _person("Elena", "Vásquez", "Ríos", "1994-02-17", "M", "JC",
                          "Calle López Cotilla", "210", "Americana", "44160", "Guadalajara",
                          plaza="170", account="12121212121", city="Guadalajara"),
        "occupation": "Médica", "purpose": "Inversión de nómina",
        "initial_amount": 35_000, "service": "asesoramiento", "route": "primer_ingreso",
        "answers": {"horizon": "6-10", "capacity": "wait", "experience": "funds",
                    "knowledge": "related", "income": "salary", "share": "low", "sustainability": "yes"},
        "submitted_cdmx": "2026-10-20T02:10:00-06:00",
        "story": "Mismo nombre que una entrada sintética de sanciones (1968). Descartada por fecha de nacimiento.",
    },
    {
        "seed": "domicilio_corregido",
        "pseudonym": "Mariana del Carmen Ortega Ruiz",
        "person": _person("Mariana del Carmen", "Ortega", "Ruiz", "1990-09-30", "M", "DF",
                          "Calle Amsterdam", "77", "Condesa", "06140", "Cuauhtémoc"),
        "occupation": "Abogada", "purpose": "Inversión",
        "initial_amount": 28_000, "service": "asesoramiento", "route": "primer_ingreso",
        "stale_address_first": True,
        "answers": {"horizon": "3-5", "capacity": "wait", "experience": "none",
                    "knowledge": "other", "income": "salary", "share": "mid", "sustainability": "no"},
        "submitted_cdmx": "2026-10-20T00:48:00-06:00",
        "story": "El primer comprobante tenía 11 meses. Lo sustituyó de madrugada.",
    },
    {
        "seed": "pasaporte_caducado",
        "pseudonym": "Jorge Luis Peña Aguilar",
        "person": _person("Jorge Luis", "Peña", "Aguilar", "1983-01-14", "H", "OC",
                          "Calle Macedonio Alcalá", "300", "Centro", "68000", "Oaxaca",
                          plaza="210", account="33445566778", city="Oaxaca"),
        "occupation": "Arquitecto", "purpose": "Inversión",
        "initial_amount": 22_000, "service": "asesoramiento", "route": "primer_ingreso",
        "passport_expired": True,
        "answers": {"horizon": "3-5", "capacity": "sell", "experience": "none",
                    "knowledge": "other", "income": "salary", "share": "mid", "sustainability": "no"},
        "submitted_cdmx": "2026-10-20T03:22:00-06:00",
        "story": "Pasaporte caducado. Solo aportó INE. Bloqueado (PBC-ID-02, PBC-ID-03).",
    },
    {
        "seed": "apellido_faltante",
        "pseudonym": "Sofía Natalia García López",
        "person": _person("Sofía Natalia", "García", "López", "1996-06-08", "M", "PL",
                          "Av. Juárez", "1408", "La Paz", "72160", "Puebla",
                          plaza="220", account="77889900112", city="Puebla"),
        "occupation": "Profesora", "purpose": "Inversión",
        "initial_amount": 18_000, "service": "asesoramiento", "route": "primer_ingreso",
        "omit_second_surname_on_passport": True,
        "answers": {"horizon": "10+", "capacity": "buy", "experience": "funds",
                    "knowledge": "related", "income": "salary", "share": "low", "sustainability": "yes"},
        "submitted_cdmx": "2026-10-20T01:44:00-06:00",
        "story": "El pasaporte omite el segundo apellido. Coincidencia parcial, no fuerza presencial.",
    },
    {
        "seed": "complejo_no_conveniente",
        "pseudonym": "Pablo Andrés Méndez Herrera",
        "person": _person("Pablo Andrés", "Méndez", "Herrera", "1987-12-21", "H", "MC",
                          "Calle de la Paz", "9", "San Ángel", "01000", "Álvaro Obregón"),
        "occupation": "Periodista", "purpose": "Operar por cuenta propia",
        "initial_amount": 15_000, "service": "rto", "route": "primer_ingreso",
        "product": {"name": "Opción sobre IBEX 35 (sintético)", "complex": True},
        "answers": {"horizon": "0-2", "capacity": "sell", "experience": "none",
                    "knowledge": "other", "income": "salary", "share": "high", "sustainability": "no"},
        "manuscript": True,
        "submitted_cdmx": "2026-10-20T04:05:00-06:00",
        "story": "RTO de producto complejo no conveniente. Expresión manuscrita recabada (art. 205.6).",
    },
    {
        "seed": "videoid",
        "pseudonym": "Valeria Isabel Núñez Castro",
        "person": _person("Valeria Isabel", "Núñez", "Castro", "1993-04-27", "M", "QR",
                          "Av. Tulum", "55", "Centro", "77500", "Cancún",
                          plaza="230", account="44556677889", city="Cancún"),
        "occupation": "Consultora", "purpose": "Inversión",
        "initial_amount": 52_000, "service": "asesoramiento", "route": "video_id",
        "answers": {"horizon": "6-10", "capacity": "wait", "experience": "funds",
                    "knowledge": "related", "income": "salary", "share": "mid", "sustainability": "no"},
        "submitted_cdmx": "2026-10-20T02:55:00-06:00",
        "story": "Vía videoidentificación simulada (art. 21.1.d). Sin captura de cámara.",
    },
]


def live_choices() -> list[dict]:
    return [{"id": LIVE["id"], "label": LIVE["label"]}] + [
        {"id": s["seed"], "label": s["pseudonym"] + " · " + s["story"]} for s in SEEDS
    ]
