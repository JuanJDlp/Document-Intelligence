import ast
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import pytest
from pypdf import PdfWriter
from receipt_engine import (
    DocumentError,
    DocumentInput,
    DocumentValidator,
    EngineSettings,
    OcrLine,
    OcrResult,
    ReceiptExtractionEngine,
)
from receipt_engine.models import OcrProviderError, ProviderField, ProviderLineItem
from receipt_engine.normalization import money, nit, normalized_date
from conftest import FakeOcr


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.234.567,89", "1234567.89"),
        ("1,234,567.89", "1234567.89"),
        ("119.000", "119000.00"),
        ("119,5", "119.50"),
        ("1.234.567", "1234567.00"),
        ("0", "0.00"),
        ("bad", None),
    ],
)
def test_eng_nrm_01_money(raw, expected):
    assert money(raw)[0] == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("15/01/2026", "2026-01-15"),
        ("2026-01-15", "2026-01-15"),
        ("15 de enero de 2026", "2026-01-15"),
        ("15 Jan 2026", "2026-01-15"),
        ("31/02/2026", None),
        ("01/01/26", None),
        ("01/01/1999", None),
    ],
)
def test_eng_nrm_02_dates(raw, expected):
    assert normalized_date(raw, 2026)[0] == expected


def test_eng_nrm_04_nit():
    assert nit("900.123.456-8") == ("900123456-8", True)
    assert nit("900123456-7") == ("900123456-7", False)


@pytest.mark.parametrize(
    "data,reason",
    [
        (b"", "FILE_EMPTY"),
        (b"not a pdf", "UNSUPPORTED_SIGNATURE"),
        (b"%PDF-broken", "PDF_CORRUPTED"),
        (b"\x89PNG\r\n\x1a\nbad", "IMAGE_CORRUPTED"),
        (b"\xff\xd8\xffbad", "IMAGE_CORRUPTED"),
    ],
)
def test_eng_val_invalid(data, reason):
    with pytest.raises(DocumentError) as error:
        DocumentValidator().validate(DocumentInput("id", data))
    assert error.value.reason == reason


def test_eng_val_limits(image_bytes):
    with pytest.raises(DocumentError) as error:
        DocumentValidator(EngineSettings(max_document_bytes=10)).validate(
            DocumentInput("id", image_bytes)
        )
    assert error.value.reason == "FILE_TOO_LARGE"
    with pytest.raises(DocumentError) as error:
        DocumentValidator(EngineSettings(max_image_dimension=10)).validate(
            DocumentInput("id", image_bytes)
        )
    assert error.value.reason == "IMAGE_DIMENSIONS_EXCEEDED"


@pytest.mark.parametrize(
    "pages,encrypted,reason",
    [(0, False, "PDF_CORRUPTED"), (2, False, "PAGE_LIMIT_EXCEEDED"), (1, True, "PDF_ENCRYPTED")],
)
def test_eng_val_pdf(pages, encrypted, reason):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    if encrypted:
        writer.encrypt("synthetic-password")
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(DocumentError) as error:
        DocumentValidator().validate(DocumentInput("id", stream.getvalue()))
    assert error.value.reason == reason


def process(image_bytes, lines=None, provider=None, debug=False):
    engine = ReceiptExtractionEngine(
        ocr_provider=provider or FakeOcr(lines),
        clock=lambda: datetime(2026, 1, 16, tzinfo=timezone.utc),
    )
    return engine.process(
        DocumentInput("synthetic-id", image_bytes), include_debug_details=debug
    ).to_dict()


def test_eng_out_completed(image_bytes):
    result = process(image_bytes)
    assert result["status"] == "completed"
    assert result["extracted_data"]["total"] == "119000.00"
    assert result["extracted_data"]["subtotal"] == "100000.00"
    assert result["extracted_data"]["merchant_address"] is None
    assert result["confidence"]["overall"] == 0.9
    assert "raw_text" not in result
    assert "field_sources" not in result["validation"]


@pytest.mark.parametrize(
    "lines,status,reason",
    [
        (["SYNTHETIC MARKET", "RECIBO", "TOTAL: COP 12"], "partial", None),
        ([], "failed", "NO_TEXT_DETECTED"),
        (["FACTURA"], "failed", "NO_REQUIRED_FIELDS_FOUND"),
        (["SYNTHETIC MARKET", "RECIBO", "TOTAL: COP -1"], "failed", "NEGATIVE_TOTAL"),
        (
            ["SYNTHETIC MARKET", "RECIBO", "FECHA: 31/02/2026", "TOTAL: COP 1"],
            "failed",
            "INVALID_DATE",
        ),
    ],
)
def test_eng_sts_outcomes(image_bytes, lines, status, reason):
    result = process(image_bytes, lines)
    assert result["status"] == status
    assert (result["error"] or {}).get("reason") == reason


def test_eng_ext_ambiguity_and_total_rule(image_bytes):
    result = process(
        image_bytes,
        [
            "SYNTHETIC MARKET",
            "FECHA: 15/01/2026",
            "FECHA: 16/01/2026",
            "TOTAL: COP 50",
            "TOTAL: COP 40",
        ],
    )
    assert result["extracted_data"]["issue_date"] is None
    assert result["extracted_data"]["total"] is None
    assert any(w["code"] == "FIELD_AMBIGUOUS" for w in result["validation"]["warnings"])
    assert (
        process(image_bytes, ["SYNTHETIC MARKET", "TOTAL: COP 40", "TOTAL: COP 50"])[
            "extracted_data"
        ]["total"]
        == "50.00"
    )


def test_eng_chk_warnings_and_debug(image_bytes):
    result = process(
        image_bytes,
        [
            "SYNTHETIC MARKET",
            "NIT 900123456-7",
            "FECHA: 01/02/2026",
            "SUBTOTAL: $100",
            "DESCUENTO: -10",
            "TOTAL: $200",
        ],
        debug=True,
    )
    codes = {w["code"] for w in result["validation"]["warnings"]}
    assert {
        "CURRENCY_INFERRED",
        "DATE_FORMAT_ASSUMED",
        "NIT_CHECK_DIGIT_MISMATCH",
        "TOTAL_MISMATCH",
        "NEGATIVE_DISCOUNT_NORMALIZED",
    } <= codes
    assert result["validation"]["is_valid"] is True
    assert "raw_text" in result
    assert result["extracted_data"]["discount"] == "10.00"


def test_eng_ext_structured_fields_and_items(image_bytes):
    class Structured(FakeOcr):
        def extract(self, request):
            return OcrResult(
                (OcrLine("SYNTHETIC MARKET", 0.8),),
                self.name,
                (ProviderField("TOTAL", "12", 0.95), ProviderField("CURRENCY", "COP", 0.9)),
                (ProviderLineItem("Synthetic", "2", "4", "10"),),
            )

    result = process(image_bytes, provider=Structured())
    assert result["extracted_data"]["total"] == "12.00"
    assert any(w["code"] == "LINE_ITEM_MISMATCH" for w in result["validation"]["warnings"])


@pytest.mark.parametrize("transient", [True, False])
def test_eng_prov_failure(image_bytes, transient):
    class Failed(FakeOcr):
        def extract(self, request):
            raise OcrProviderError(transient, "PRIVATE", "sensitive content")

    result = process(image_bytes, provider=Failed())
    assert result["error"]["code"] == "OCR_FAILED"
    assert result["error"]["retryable"] is transient


def test_eng_scope_boundaries():
    root = Path(__file__).parents[1] / "src" / "receipt_engine"
    banned = {"boto3", "botocore", "fastapi", "sqlalchemy", "pymysql", "worker", "api"}
    for file in root.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in banned for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or "").split(".")[0] not in banned


def test_eng_log_privacy(image_bytes, caplog):
    with caplog.at_level("INFO"):
        process(image_bytes)
    for private in ("SYNTHETIC MARKET", "119000", "900123456", "INV-001"):
        assert private not in caplog.text


@pytest.mark.ocr
def test_eng_prov_real_ocr():
    from receipt_engine.ocr.tesseract import TesseractProvider

    root = Path(__file__).resolve().parents[3]
    for name in ("receipt.png", "receipt.jpeg", "receipt.pdf"):
        content = (root / "samples/receipts" / name).read_bytes()
        result = (
            ReceiptExtractionEngine(ocr_provider=TesseractProvider())
            .process(DocumentInput("real-ocr-synthetic", content))
            .to_dict()
        )
        assert result["status"] == "completed", result["error"]
        assert result["extracted_data"]["total"] == "119000.00"
