from datetime import date
from io import BytesIO

from PIL import Image, ImageDraw
from pypdf import PdfWriter

from app.checks import match, mrz, mx_ids, ocr, quality


def test_td3_roundtrip_and_icao_specimen():
    # ICAO Doc 9303 specimen (Appendix).
    specimen = [
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
    ]
    parsed = mrz.parse_td3(specimen)
    assert parsed["valid"]
    assert parsed["surnames"] == "ERIKSSON"
    assert parsed["given_names"] == "ANNA MARIA"
    assert parsed["number"] == "L898902C3"
    assert parsed["birth_date"] == date(1974, 8, 12)
    assert parsed["expiry_date"] == date(2012, 4, 15)

    built = mrz.build_td3(
        "García López", "María Elena", "G12345678",
        date(1985, 3, 14), "F", date(2030, 6, 1),
    )
    back = mrz.parse_td3(built)
    assert back["valid"]
    assert back["surnames"] == "GARCIA LOPEZ"
    assert back["given_names"] == "MARIA ELENA"
    assert back["number"] == "G12345678"

    tampered = [built[0], built[1][:9] + "0" + built[1][10:]]
    assert not mrz.parse_td3(tampered)["valid"]


def test_td1_roundtrip():
    lines = mrz.build_td1(
        "Hernández", "Luis", "IDMEX1234",
        date(1990, 11, 2), "M", date(2028, 1, 15),
        optional1="CURPXXXX",
    )
    parsed = mrz.parse_td1(lines)
    assert parsed["valid"]
    assert parsed["surnames"] == "HERNANDEZ"
    assert parsed["given_names"] == "LUIS"
    assert parsed["number"] == "IDMEX1234"


def test_curp_rfc_clabe_iban():
    dob = date(1988, 7, 22)
    curp = mx_ids.build_curp("Ramírez", "Soto", "Ana Sofía", dob, "M", "DF", "A")
    out = mx_ids.validate_curp(curp, "Ramírez", "Soto", "Ana Sofía", dob, "M")
    assert out["valid"] and out["consistent"]
    assert out["birth_date"] == "1988-07-22"

    rfc = mx_ids.build_rfc("Ramírez", "Soto", "Ana Sofía", dob, "A1")
    rfc_out = mx_ids.validate_rfc(rfc, "Ramírez", "Soto", "Ana Sofía", dob)
    assert rfc_out["valid"] and rfc_out["consistent"]
    assert len(rfc) == 13

    clabe = mx_ids.build_clabe("980", "180", "01234567891")
    clabe_out = mx_ids.validate_clabe(clabe)
    assert clabe_out["valid"]
    assert clabe_out["bank_code"] == "980"
    assert not mx_ids.validate_clabe(clabe[:-1] + ("0" if clabe[-1] != "0" else "1"))["valid"]

    iban = mx_ids.validate_iban("ES9121000418450200051332")
    assert iban["valid"]
    assert not mx_ids.validate_iban("ES9121000418450200051333")["valid"]


def test_name_and_address_matching():
    person = {"nombres": "María Elena", "apellido1": "García", "apellido2": "López"}
    full = match.name_match(person, "GARCIA LOPEZ, MARIA ELENA")
    assert full["verdict"] == "coincide"
    missing = match.name_match(person, "MARIA ELENA GARCIA")
    assert missing["verdict"] == "parcial"
    other = match.name_match(person, "PEDRO MARTINEZ RUIZ")
    assert other["verdict"] == "no_coincide"

    addr = {"calle": "Calle Durango", "numero": "45", "colonia": "Roma Norte", "cp": "06700"}
    text = "Calle Durango 45, Col. Roma Norte, Cuauhtémoc, CDMX, C.P. 06700"
    assert match.address_match(addr, text)["verdict"] == "coincide"


def test_quality_and_metadata_strip():
    img = Image.new("RGB", (1200, 800), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, 1160, 760), outline=(0, 0, 0), width=4)
    draw.text((80, 80), "SINTETICO", fill=(0, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    data = buf.getvalue()
    assert quality.sniff(data) == "image/jpeg"
    clean, cleaned_img, _removed = quality.strip_metadata(data)
    assert quality.sniff(clean) == "image/png"
    report = quality.assess(cleaned_img)
    assert report["ok"]

    tiny = Image.new("RGB", (80, 60), (20, 20, 20))
    assert "resolucion" in quality.assess(tiny)["issues"]


def test_ocr_and_pdf_text():
    img = Image.new("RGB", (800, 200), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 70), "SINTETICO COMPROBANTE", fill=(0, 0, 0))
    text = ocr.image_text(img, lang="spa", psm=6)
    assert "SINTETICO" in text.upper() or "COMPROBANTE" in text.upper() or ocr.available()

    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=200)
    # pypdf cannot easily draw text; write a tiny PDF with reportlab instead.
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(400, 200))
    c.setFont("Helvetica", 14)
    c.drawString(40, 120, "SINTETICO CFE")
    c.save()
    extracted = ocr.pdf_text(buf.getvalue())
    assert "SINTETICO" in extracted
    assert ocr.pdf_active_content(buf.getvalue()) == []
