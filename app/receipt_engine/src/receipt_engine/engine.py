import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from time import monotonic
from typing import Any, Callable
from .models import (
    DocumentInput,
    EngineSettings,
    ExtractionResult,
    OCRProvider,
    OcrRequest,
    OcrProviderError,
)
from .normalization import folded, money, nit, normalized_date
from .validation import DocumentError, DocumentValidator

logger = logging.getLogger(__name__)
SCALARS = (
    "merchant_name",
    "merchant_tax_id",
    "merchant_address",
    "customer_id",
    "document_number",
    "issue_date",
    "currency",
    "subtotal",
    "tax_amount",
    "discount",
    "total",
    "payment_method",
)
REQUIRED = ("merchant_name", "issue_date", "currency", "total")
AMOUNTS = ("subtotal", "tax_amount", "discount", "total")
STRUCTURED = {
    "merchant_name": "VENDOR_NAME",
    "merchant_tax_id": "VENDOR_TAX_ID",
    "document_number": "INVOICE_RECEIPT_ID",
    "issue_date": "INVOICE_RECEIPT_DATE",
    "currency": "CURRENCY",
    "subtotal": "SUBTOTAL",
    "tax_amount": "TAX",
    "discount": "DISCOUNT",
    "total": "TOTAL",
    "payment_method": "PAYMENT_METHOD",
}


class ReceiptExtractionEngine:
    def __init__(
        self,
        *,
        ocr_provider: OCRProvider,
        settings: EngineSettings | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.provider = ocr_provider
        self.settings = settings or EngineSettings()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def process(
        self, document: DocumentInput, *, include_debug_details: bool = False
    ) -> ExtractionResult:
        started = monotonic()
        result: dict[str, Any] = {
            "document_id": document.document_id,
            "document_type": "unknown",
            "status": "failed",
            "error": None,
            "extracted_data": {**dict.fromkeys(SCALARS), "line_items": []},
            "confidence": {"overall": None, "fields": {}},
            "validation": {"is_valid": True, "warnings": []},
            "metadata": {
                "page_count": 0,
                "mime_type": None,
                "provider": self.provider.name,
                "engine_version": "1.0.0",
                "processing_ms": 0,
            },
        }
        sources: dict[str, str] = {}
        warnings = result["validation"]["warnings"]

        def warn(code: str, field: str | None = None) -> None:
            item = {
                "code": code,
                "field": field,
                "message": code.replace("_", " ").capitalize() + ".",
            }
            if item not in warnings:
                warnings.append(item)

        def fail(code: str, reason: str, retryable: bool = False) -> None:
            result["error"] = {
                "code": code,
                "reason": reason,
                "retryable": retryable,
                "message": reason.replace("_", " ").capitalize() + ".",
            }
            result["status"] = "failed"
            result["validation"]["is_valid"] = code != "VALIDATION_FAILED"

        try:
            mime, pages = DocumentValidator(self.settings).validate(document)
        except DocumentError as exc:
            result["metadata"].update(mime_type=exc.mime_type, page_count=exc.pages)
            fail(exc.code, exc.reason)
            return self._finish(result, started)
        result["metadata"].update(mime_type=mime, page_count=pages)
        if document.declared_mime_type and document.declared_mime_type != mime:
            warn("MIME_TYPE_MISMATCH")
        logger.info(
            "event=document.validated document_id=%s mime_type=%s page_count=%s size_bucket=%s",
            document.document_id,
            mime,
            pages,
            "small"
            if len(document.content) <= 1048576
            else "medium"
            if len(document.content) <= 3145728
            else "large",
        )
        ocr_started = monotonic()
        try:
            ocr = self.provider.extract(OcrRequest(document.content, mime, pages))
        except OcrProviderError as exc:
            logger.warning(
                "event=ocr.failed document_id=%s exception_class=%s error_code=%s",
                document.document_id,
                type(exc).__name__,
                exc.code,
            )
            fail(
                "OCR_FAILED",
                "PROVIDER_TRANSIENT" if exc.transient else "PROVIDER_PERMANENT",
                exc.transient,
            )
            return self._finish(result, started)
        lines = [line for line in ocr.lines if line.text.strip()]
        logger.info(
            "event=ocr.completed document_id=%s provider=%s line_count=%s duration_ms=%s",
            document.document_id,
            self.provider.name,
            len(lines),
            int((monotonic() - ocr_started) * 1000),
        )
        if not lines:
            fail("EXTRACTION_FAILED", "NO_TEXT_DETECTED")
            return self._finish(result, started)
        candidates: dict[str, list[tuple[str, float]]] = {field: [] for field in SCALARS}
        raw = "\n".join(line.text for line in lines)
        text = folded(raw)
        result["document_type"] = (
            "invoice"
            if re.search(r"\b(FACTURA|INVOICE)\b", text)
            else "receipt"
            if re.search(r"\b(TIQUETE|RECIBO|RECEIPT|POS)\b", text)
            else "unknown"
        )
        if result["document_type"] == "unknown":
            warn("DOCUMENT_TYPE_UNKNOWN")
        for line in lines[: max(1, (len(lines) + 2) // 3)]:
            if not re.search(
                r"\b(FACTURA|INVOICE|RECIBO|RECEIPT|TIQUETE|NIT|FECHA|DATE|TOTAL)\b",
                folded(line.text),
            ):
                candidates["merchant_name"].append((line.text.strip(), line.confidence))
                break
        for line in lines:
            s = folded(line.text)
            for field, pattern in {
                "merchant_tax_id": r"\b(?:NIT|RUT|TAX ID)[:\s]+([\d.]+(?:[-\s]\d)?)",
                "document_number": r"(?:FACTURA\s*(?:NO\.?|N[°º])|INVOICE\s*#|NO\.|TIQUETE)\s*[:#]?\s*([A-Z0-9-]{1,30})",
                "issue_date": r"(?:FECHA|DATE|EMISION)\s*:?\s*(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{1,2}(?: DE)? [A-Z]+(?: DE)? \d{4})",
            }.items():
                match = re.search(pattern, s)
                if match:
                    candidates[field].append((match.group(1), line.confidence))
            for field, pattern in {
                "subtotal": r"\bSUBTOTAL\b",
                "tax_amount": r"\b(?:IVA|TAX)\b",
                "discount": r"\b(?:DESCUENTO|DISCOUNT)\b",
                "total": r"(?<!SUB)\bTOTAL\b",
            }.items():
                match = re.search(
                    pattern + r"\s*:?\s*(?:[A-Z]{3}\s*)?(?:COL\$|US\$|[$€])?\s*([-+]?\d[\d.,]*)", s
                )
                if match:
                    candidates[field].append((match.group(1), line.confidence))
            explicit = re.findall(r"\b(?:COP|USD|EUR|MXN|PEN|CLP|ARS)\b", s)
            for code in explicit:
                candidates["currency"].append((code, line.confidence))
            if not explicit:
                if "US$" in s:
                    candidates["currency"].append(("USD", line.confidence))
                elif "COL$" in s:
                    candidates["currency"].append(("COP", line.confidence))
                elif "€" in s:
                    candidates["currency"].append(("EUR", line.confidence))
                elif "$" in s:
                    candidates["currency"].append(
                        (self.settings.dollar_sign_currency, line.confidence)
                    )
                    warn("CURRENCY_INFERRED")
            for words, method in [
                (("EFECTIVO", "CASH"), "cash"),
                (("TARJETA CREDITO", "CREDIT CARD"), "credit_card"),
                (("TARJETA DEBITO", "DEBIT"), "debit_card"),
                (("TRANSFERENCIA", "PSE", "BANK TRANSFER"), "bank_transfer"),
                (("NEQUI", "DAVIPLATA", "WALLET"), "digital_wallet"),
            ]:
                if any(word in s for word in words):
                    candidates["payment_method"].append((method, line.confidence))
        data = result["extracted_data"]
        for field in SCALARS:
            if field in ("merchant_address", "customer_id"):
                continue
            structured = [
                (f.value, f.confidence)
                for f in ocr.structured_fields
                if f.type == STRUCTURED.get(field)
            ]

            def normalize(items: list[tuple[str, float]]) -> list[tuple[str, float, str]]:
                values: list[tuple[str, float, str]] = []
                for value, confidence in items:
                    flags: list[str] = []
                    normalized: str | None = value.strip()
                    if field in AMOUNTS:
                        normalized, flags = money(value)
                        if normalized and Decimal(normalized) < 0:
                            if field == "discount":
                                normalized = str(abs(Decimal(normalized)).quantize(Decimal(".01")))
                                flags.append("NEGATIVE_DISCOUNT_NORMALIZED")
                            elif field == "total":
                                fail("VALIDATION_FAILED", "NEGATIVE_TOTAL")
                                normalized = None
                            else:
                                normalized = None
                                flags.append("FIELD_INVALID")
                    elif field == "issue_date":
                        normalized, flags = normalized_date(value, self.clock().year)
                    elif field == "merchant_tax_id":
                        normalized, valid = nit(value)
                        if normalized and not valid:
                            flags.append("NIT_CHECK_DIGIT_MISMATCH")
                    elif field == "currency":
                        normalized = (
                            value.upper()
                            if value.upper() in self.settings.supported_currencies
                            else None
                        )
                    for flag in flags:
                        warn(flag, field)
                    if normalized:
                        values.append((normalized, max(0.0, min(1.0, confidence)), value))
                return values

            values = normalize(structured) if structured else []
            if not values:
                values = normalize(candidates[field])
            if (
                field == "total"
                and len(values) > 1
                and Decimal(values[-1][0]) == max(Decimal(v[0]) for v in values)
            ):
                values = [values[-1]]
            distinct = {value for value, _, _ in values}
            if len(distinct) > 1:
                warn("FIELD_AMBIGUOUS", field)
            elif values:
                data[field] = values[0][0]
                result["confidence"]["fields"][field] = round(min(v[1] for v in values), 2)
                sources[field] = values[0][2]
            elif field == "issue_date" and (candidates[field] or structured):
                fail("VALIDATION_FAILED", "INVALID_DATE")
            if data[field] is None and field in REQUIRED and len(distinct) <= 1:
                warn("FIELD_MISSING", field)
        for item in ocr.structured_line_items:
            entry: dict[str, Any] = {"description": item.description}
            for field in ("quantity", "unit_price", "line_total"):
                value = getattr(item, field)
                entry[field] = money(value)[0] if value is not None else None
            data["line_items"].append(entry)
            if all(entry[k] is not None for k in ("quantity", "unit_price", "line_total")):
                if abs(
                    Decimal(entry["quantity"]) * Decimal(entry["unit_price"])
                    - Decimal(entry["line_total"])
                ) > Decimal(".01"):
                    warn("LINE_ITEM_MISMATCH", str(len(data["line_items"]) - 1))
        if data["total"] is not None and data["subtotal"] is not None:
            expected = (
                Decimal(data["subtotal"])
                + Decimal(data["tax_amount"] or "0")
                - Decimal(data["discount"] or "0")
            )
            if abs(Decimal(data["total"]) - expected) > Decimal(".01"):
                warn("TOTAL_MISMATCH")
        if (
            data["line_items"]
            and data["subtotal"] is not None
            and all(i["line_total"] is not None for i in data["line_items"])
        ):
            if abs(
                sum(Decimal(i["line_total"]) for i in data["line_items"])
                - Decimal(data["subtotal"])
            ) > Decimal(".01"):
                warn("LINE_ITEMS_SUM_MISMATCH")
        if not result["error"]:
            result["status"] = (
                "completed" if all(data[f] is not None for f in REQUIRED) else "partial"
            )
            if all(data[f] is None for f in REQUIRED):
                fail("EXTRACTION_FAILED", "NO_REQUIRED_FIELDS_FOUND")
        conf = result["confidence"]["fields"]
        result["confidence"]["overall"] = round(sum(conf.values()) / len(conf), 2) if conf else None
        if include_debug_details:
            result["raw_text"] = raw
            result["validation"]["field_sources"] = sources
        return self._finish(result, started)

    @staticmethod
    def _finish(result: dict[str, Any], started: float) -> ExtractionResult:
        result["metadata"]["processing_ms"] = int((monotonic() - started) * 1000)
        logger.info(
            "event=extraction.completed document_id=%s status=%s error_code=%s warning_codes=%s duration_ms=%s",
            result["document_id"],
            result["status"],
            result["error"]["code"] if result["error"] else "NONE",
            ",".join(w["code"] for w in result["validation"]["warnings"]) or "NONE",
            result["metadata"]["processing_ms"],
        )
        return ExtractionResult(result)
