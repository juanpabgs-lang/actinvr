"""Build the overnight queue: nine synthetic files with generated documents."""
from __future__ import annotations

from datetime import date, timedelta

from . import cases, db, docsgen, documents, pipeline, settings
from .checks import mrz
from .personas import SEEDS
from .timeutil import iso, parse


def _already() -> bool:
    row = db.one("SELECT COUNT(*) AS n FROM cases WHERE seeded = 1")
    return bool(row and row["n"] >= len(SEEDS))


def populate(force: bool = False, summarize: bool = True) -> list[str]:
    settings.ensure_dirs()
    if _already() and not force:
        return [r["id"] for r in db.query("SELECT id FROM cases WHERE seeded = 1")]
    ids = []
    for spec in SEEDS:
        created = cases.create(spec, seeded=True, submitted_at=None)
        case_id = created["id"]
        person = spec["person"]
        submitted = parse(spec["submitted_cdmx"])
        expiry = date(2032, 6, 1)
        issued = date(2024, 6, 1)
        if spec.get("passport_expired"):
            expiry = date(2024, 1, 10)
            issued = date(2014, 1, 10)
        passport_person = dict(person)
        if spec.get("omit_second_surname_on_passport"):
            passport_person = dict(person, apellido2="")
        number = f"G{abs(hash(spec['seed'])) % 100000000:08d}"
        png = docsgen.passport_png(passport_person, number, issued, expiry)
        mrz_payload = {"mrz": mrz.build_td3(
            f"{passport_person['apellido1']} {passport_person.get('apellido2') or ''}".strip(),
            passport_person["nombres"], number, date.fromisoformat(person["dob"]),
            "F" if person.get("sex") == "M" else "M", expiry,
        )}
        analysis = documents.analyze("pasaporte", png, "pasaporte.png", person, today=date(2026, 10, 20),
                                     payload=mrz_payload)
        cases.add_document(case_id, "pasaporte", "pasaporte.png", "image/png", png, analysis,
                           sim_ts=iso(submitted))

        ine_png = docsgen.ine_png(person, f"ID{number[1:10]}", date(2030, 1, 1) if not spec.get("passport_expired") else date(2029, 1, 1))
        ine_lines = mrz.build_td1(
            f"{person['apellido1']} {person.get('apellido2') or ''}".strip(),
            person["nombres"], f"ID{number[1:10]}", date.fromisoformat(person["dob"]),
            "F" if person.get("sex") == "M" else "M", date(2030, 1, 1),
            optional1=(person.get("curp") or "")[:15],
        )
        ine_analysis = documents.analyze("ine", ine_png, "ine.png", person, today=date(2026, 10, 20),
                                         payload={"mrz": ine_lines})
        cases.add_document(case_id, "ine", "ine.png", "image/png", ine_png, ine_analysis,
                           sim_ts=iso(submitted))

        addr_date = date(2026, 8, 15)
        if spec.get("stale_address_first"):
            stale = docsgen.address_pdf(person, date(2025, 11, 2))
            stale_a = documents.analyze("domicilio", stale, "domicilio-2025.pdf", person, today=date(2026, 10, 20))
            cases.add_document(case_id, "domicilio", "domicilio-2025.pdf", "application/pdf", stale, stale_a,
                               sim_ts=iso(submitted))
            addr_date = date(2026, 9, 28)
            later = submitted + timedelta(hours=2)
        else:
            later = submitted
        addr = docsgen.address_pdf(person, addr_date)
        addr_a = documents.analyze("domicilio", addr, "domicilio.pdf", person, today=date(2026, 10, 20))
        cases.add_document(case_id, "domicilio", "domicilio.pdf", "application/pdf", addr, addr_a,
                           sim_ts=iso(later if spec.get("stale_address_first") else submitted))

        if spec.get("sof_kind") or spec["initial_amount"] >= 100_000:
            sof = docsgen.funds_pdf(person, spec.get("sof_kind") or "ahorro", spec["initial_amount"], date(2026, 7, 1))
            sof_a = documents.analyze("origen_fondos", sof, "origen.pdf", person, today=date(2026, 10, 20))
            cases.add_document(case_id, "origen_fondos", "origen.pdf", "application/pdf", sof, sof_a,
                               sim_ts=iso(submitted))

        extra = {
            "gdpr_ack": True, "ai_ack": True, "precontract_ack": True,
            "stage": "enviado", "sof_kind": spec.get("sof_kind"),
            "first_transfer": {"same_holder": True, "equivalent_country": True, "arrived": spec["route"] == "primer_ingreso",
                               "country": "MX", "simulated": True},
            "answers": spec.get("answers") or {},
            "product": spec.get("product"),
            "manuscript": spec.get("manuscript"),
            "crs": {"residence": "MX", "only_mx_es": True},
            "fatca": {"us_person": False},
        }
        if spec.get("route") == "video_id":
            extra["video_id"] = {"passed": True, "provider": "Proveedor de videoidentificación (simulado)",
                                 "authorization": "SEPBLAC autorización general (simulado)", "liveness": "superado (sintético)"}
        cases.save_data(case_id, extra, actor="sistema")
        cases.mark_submitted(case_id, submitted_at=iso(submitted))
        pipeline.run(case_id, summarize=summarize)
        if spec["seed"] not in {"pasaporte_caducado"}:
            rec = cases.load(case_id)
            rec["data"]["signature"] = {"signed_at": iso(submitted + timedelta(minutes=12)),
                                        "code_hash": "sintético", "simulated": True}
            cases.save_data(case_id, rec["data"], actor="sistema")
            pipeline.build_contract(case_id)
        ids.append(case_id)
    return ids
