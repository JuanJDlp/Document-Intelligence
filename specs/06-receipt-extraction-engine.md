# 06 — Receipt Extraction Engine

Implementation: `app/receipt_engine/` (Python package `receipt_engine`, Python 3.12).

This spec is the normative version of the engine requirements. It started from an AI-generated draft that was explicitly **not** treated as truth. Section 13 lists every change we made to the draft and why. Where the draft and this spec differ, this spec wins.

## 1. Purpose and boundaries

- **ENG-SCOPE-01** (active) The engine receives the bytes of one document and returns a structured, validated, normalized result. It is a pure library.
- **ENG-SCOPE-02** (active) The engine MUST NOT import `boto3`, `botocore`, `fastapi`, `sqlalchemy`, `pymysql`, or any module that performs network I/O by itself. The OCR provider is injected.
- **ENG-SCOPE-03** (active) The engine MUST NOT schedule jobs, write to a database, publish notifications, read from S3, or authenticate users. Those are the worker's and API's responsibilities (`ARC-RULE-01`).
- **ENG-SCOPE-04** (active) The engine MUST be deterministic for the same input and the same provider output (no randomness, no reliance on the current time except through an injected clock).
- **ENG-SCOPE-05** (active) Document types in scope: `receipt` and `invoice`. Anything else is `unknown` and still processed if it is a readable document with recognizable financial fields.

## 2. Public interface

```python
@dataclass(frozen=True)
class DocumentInput:
    document_id: str              # UUID string, used for correlation only
    content: bytes                # raw file bytes
    declared_mime_type: str | None
    filename: str | None          # used only for extension hints and warnings; never logged

class ReceiptExtractionEngine:
    def __init__(self, *, ocr_provider: OCRProvider, settings: EngineSettings,
                 clock: Callable[[], datetime]) -> None: ...

    def process(self, document: DocumentInput, *, include_debug_details: bool = False) -> ExtractionResult: ...
```

- **ENG-API-01** (active) `process` MUST return an `ExtractionResult` for every expected outcome. It MUST NOT raise for document problems, provider failures, or extraction problems. Those are represented in the result (`ENG-ERR-*`).
- **ENG-API-02** (active) `DocumentInput` is the only input type. There is no S3 key, no URL, and no file path in the engine API.
- **ENG-API-03** (active) `include_debug_details=False` by default. When `True`, the result includes `raw_text` and per-field `source_text` (`ENG-OUT-04`). The worker MUST NOT set it to `True` (`WRK-PER-05`).
- **ENG-API-04** (active) Unexpected programming errors (bugs) are NOT caught by the engine. They propagate to the caller, which treats them as retryable worker errors (`WRK-PRC-06`).

## 3. Pipeline

Stages run in order. A stage failure with an error code stops the pipeline and produces a `failed` result. Warnings never stop the pipeline.

1. **Validate document** (`ENG-VAL-*`) — size, emptiness, signature, PDF/image integrity, page limit.
2. **OCR** (`ENG-PROV-*`) — provider call with line-level text and confidence.
3. **Extract fields** (`ENG-EXT-*`) — candidates, semantic mapping.
4. **Normalize** (`ENG-NRM-*`) — dates, money, currency, identifiers.
5. **Validate result** (`ENG-CHK-*`) — required fields, arithmetic, plausibility.
6. **Compose result** (`ENG-OUT-*`, `ENG-STS-*`) — status, confidence, warnings.

## 4. Stage 1 — Document validation (`DocumentValidator`)

- **ENG-VAL-01** (active) Accepted types are identified by **magic bytes**, not extension: PDF (`%PDF-` at offset 0), PNG (`\x89PNG\r\n\x1a\n`), JPEG (`\xFF\xD8\xFF`). Any other signature → `UNSUPPORTED_FORMAT` (reason `UNSUPPORTED_SIGNATURE`).
- **ENG-VAL-02** (active) Maximum size is `settings.max_document_bytes`, default `5_242_880` (5 MiB). Empty content (0 bytes) → `INVALID_DOCUMENT` (reason `FILE_EMPTY`). Larger → `INVALID_DOCUMENT` (reason `FILE_TOO_LARGE`). The API uses the same limit (`API-DOC-02`).
- **ENG-VAL-03** (active) PDF: must parse with `pypdf`. Failure → `INVALID_DOCUMENT` (reason `PDF_CORRUPTED`). Encrypted PDFs → `INVALID_DOCUMENT` (reason `PDF_ENCRYPTED`) — we do not attempt to decrypt.
- **ENG-VAL-04** (active) PDF page limit: exactly **1 page** is accepted. More than 1 page → `INVALID_DOCUMENT` (reason `PAGE_LIMIT_EXCEEDED`), `metadata.page_count` is set to the real count. Rationale: the synchronous Textract API handles one page; asynchronous Textract requires a service role we cannot create (`CON-IAM-04`, `ADR-012`). The limit is `settings.max_pdf_pages`, default `1`.
- **ENG-VAL-05** (active) PDF with zero pages → `INVALID_DOCUMENT` (reason `PDF_CORRUPTED`).
- **ENG-VAL-06** (active) Images: must decode with Pillow (`Image.open` + `verify`). Failure → `INVALID_DOCUMENT` (reason `IMAGE_CORRUPTED`). Width or height above `settings.max_image_dimension`, default `10000` px → `INVALID_DOCUMENT` (reason `IMAGE_DIMENSIONS_EXCEEDED`).
- **ENG-VAL-07** (active) If `declared_mime_type` is present and differs from the sniffed type, add warning `MIME_TYPE_MISMATCH` and use the sniffed type. The mismatch does not fail the document.
- **ENG-VAL-08** (active) Validation MUST NOT trust `filename` extensions for type decisions. The extension is used only to produce `MIME_TYPE_MISMATCH` diagnostics.
- **ENG-VAL-09** (active) Validation produces `metadata.mime_type` and `metadata.page_count` (`1` for images).

## 5. Stage 2 — OCR provider (`OCRProvider`)

### 5.1 Interface

- **ENG-PROV-01** (active) The engine depends on this protocol only:
  ```python
  class OCRProvider(Protocol):
      name: str                       # e.g. "textract", "tesseract"
      def extract(self, request: OcrRequest) -> OcrResult: ...

  @dataclass(frozen=True)
  class OcrRequest:
      content: bytes
      mime_type: str                  # validated, sniffed type
      page_count: int

  @dataclass(frozen=True)
  class OcrLine:
      text: str
      confidence: float               # 0.0 to 1.0, provider-reported, never estimated
      page: int                       # 1-based

  @dataclass(frozen=True)
  class OcrResult:
      lines: tuple[OcrLine, ...]
      provider_name: str
      structured_fields: tuple[ProviderField, ...] = ()   # optional key/value hints from the provider
      structured_line_items: tuple[ProviderLineItem, ...] = ()
  ```
- **ENG-PROV-02** (active) Textract is **not used** in v1: the instance role has no Textract permission (`ADR-012`). No AWS OCR adapter exists in v1. Adding one requires a new ADR and verified permissions.
- **ENG-PROV-03** (active) Provider errors are raised as `OcrProviderError(transient: bool, code: str, detail: str)`. The engine converts them into `OCR_FAILED` results with `retryable = transient` (`ENG-ERR-03`).
  - **Transient** examples: throttling, service unavailable, timeouts, network errors.
  - **Permanent** examples: access denied, invalid parameter, unsupported document, validation exception from the service.
- **ENG-PROV-04** (active) Provider call timeout is `settings.ocr_timeout_seconds`, default `60`. Timeout → transient `OcrProviderError`.
- **ENG-PROV-05** (active) `TesseractProvider` lives in `app/receipt_engine/src/receipt_engine/ocr/tesseract.py` (no AWS). It is the only OCR provider in v1 (`ADR-012`). PDFs are rasterized with `pypdfium2` at 300 DPI; images are used directly; text is read with `pytesseract` using language `spa+eng`. It returns lines with confidence from Tesseract's per-word confidence averaged per line, divided by 100. It MUST NOT produce `structured_fields`.
- **ENG-PROV-06** (active) Provider selection is by configuration: `settings.ocr_provider` (only `tesseract` in v1). The engine constructor receives the instance; the engine never chooses a provider by itself.
- **ENG-PROV-07** (active) The engine MUST NOT fabricate OCR lines. If the provider returns no lines, the result is `EXTRACTION_FAILED` with reason `NO_TEXT_DETECTED` (`ENG-ERR-*`).

### 5.2 Provider contract tests

- **ENG-PROV-08** (active) A fake provider implementing `OCRProvider` is used by all engine unit tests. Tests MUST NOT call a real OCR service.

## 6. Stage 3 — Field extraction (`ReceiptExtractor`)

The extractor maps provider output to semantic fields. Every field has a list of candidates. The extractor picks the best candidate by the rules below and records the source lines used.

- **ENG-EXT-01** (active) **Structured-first rule.** If `structured_fields` contains a field of the matching type, it is preferred over text heuristics. Text heuristics are used when there is no structured candidate or when the structured value fails normalization.
- **ENG-EXT-02** (active) **Multiple candidates.** If several candidates for one field disagree after normalization, the extractor MUST NOT guess. It sets the field to `null`, adds warning `FIELD_AMBIGUOUS` with the field name, and the field counts as missing.
- **ENG-EXT-03** (active) Document type (`document_type`): `invoice` if the text contains `FACTURA` or `INVOICE` (case-insensitive, accent-insensitive); otherwise `receipt` if it contains `TIQUETE`, `RECIBO`, `RECEIPT`, or `POS`; otherwise `unknown` with warning `DOCUMENT_TYPE_UNKNOWN`.
- **ENG-EXT-04** (active) Merchant name (`merchant_name`): structured `VENDOR_NAME` first; otherwise the first non-empty line of the top third of the page that is not a generic keyword line. If still unknown → `null`.
- **ENG-EXT-05** (active) Merchant tax ID (`merchant_tax_id`): a line containing `NIT`, `RUT`, or `TAX ID`, followed by a number in one of the forms in `ENG-NRM-04`.
- **ENG-EXT-06** (active) Document number (`document_number`): a line containing `FACTURA No`, `FACTURA N°`, `INVOICE #`, `NO.`, `TIQUETE`, or structured `INVOICE_RECEIPT_ID`. The value is the alphanumeric token following the keyword (`[A-Za-z0-9-]{1,30}`).
- **ENG-EXT-07** (active) Issue date (`issue_date`): structured `INVOICE_RECEIPT_DATE` first; otherwise the first date-like token that appears near the words `FECHA`, `DATE`, or `EMISIÓN`. If none → `null`.
- **ENG-EXT-08** (active) Currency (`currency`): see `ENG-NRM-03`.
- **ENG-EXT-09** (active) Amounts (`subtotal`, `tax_amount`, `discount`, `total`): structured `SUBTOTAL`, `TAX`, `DISCOUNT`, `TOTAL` first; otherwise the amount on the line that contains the keyword (`SUBTOTAL`, `IVA`/`TAX`, `DESCUENTO`/`DISCOUNT`, `TOTAL`). For `total`, when several `TOTAL` lines exist, the last one in reading order is preferred **only if** it is the largest of the candidates; otherwise `FIELD_AMBIGUOUS`. The keyword `SUBTOTAL` MUST NOT be matched as `TOTAL`.
- **ENG-EXT-10** (active) Payment method (`payment_method`): keyword map (`ENG-NRM-06`). Missing → `null`.
- **ENG-EXT-11** (active) Line items (`line_items`): taken from `structured_line_items` when available. Each item has `description`, `quantity`, `unit_price`, `line_total`. Missing components are `null`. Text-based line item parsing is **not** required in v1; when no structured items exist, `line_items` is `[]`.
- **ENG-EXT-12** (active) Optional fields `merchant_address` and `customer_id` are always present in the output with value `null` in v1 (`ADR-029`). They are not extracted in v1.
- **ENG-EXT-13** (active) Each extracted scalar carries the confidence of the OCR line(s) it came from (`ENG-OUT-06`). Structured fields carry the provider's confidence.

## 7. Stage 4 — Normalization (`Normalizer`)

- **ENG-NRM-01** (active) **Money.** All amounts are `Decimal`. Parsing rules, with `settings.default_locale = "es-CO"` (`ADR-017`):
  - If both `.` and `,` appear, the **rightmost** separator is the decimal separator; the other is thousands. Examples: `1.234.567,89` → `1234567.89`; `1,234,567.89` → `1234567.89`.
  - If only one kind of separator appears and it appears more than once, it is a thousands separator. `1.234.567` → `1234567`.
  - If only one separator appears once and is followed by exactly three digits, it is a thousands separator under `es-CO` and a warning `AMBIGUOUS_AMOUNT_FORMAT` is added. `119.000` → `119000`.
  - If followed by one or two digits, it is the decimal separator. `119,5` → `119.5`.
  - Currency symbols and spaces are removed before parsing. Negative sign accepted only at the start of the token, and only for `discount` (stored as magnitude; a negative discount produces warning `NEGATIVE_DISCOUNT_NORMALIZED`).
  - Output is quantized to two decimals with `ROUND_HALF_UP`, serialized as a string (`"119000.00"`).
  - Values that cannot be parsed → `null` and warning `FIELD_INVALID` with the field name.
- **ENG-NRM-02** (active) **Dates.** Output is `YYYY-MM-DD`. Accepted input forms: `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`, `D de <month> de YYYY`, `D <mon> YYYY` (Spanish or English three-letter month). Two-digit years are not accepted (`FIELD_INVALID`). Day-first is the default (`es-CO`); if the date is ambiguous and the default was used, warning `DATE_FORMAT_ASSUMED`. The date MUST be a real calendar date and the year MUST be between `2000` and the current year plus one (`ENG-CHK-05`). Otherwise `FIELD_INVALID`.
- **ENG-NRM-03** (active) **Currency.** Output is an ISO 4217 code from the allowlist in `settings.supported_currencies` (default: `COP, USD, EUR, MXN, PEN, CLP, ARS`).
  - An explicit code in the text (`COP`, `USD`, …) → that code.
  - `COL$` → `COP`. `US$` → `USD`. `€` → `EUR`.
  - A bare `$` → `settings.dollar_sign_currency` (default `COP`, `ADR-016`) with warning `CURRENCY_INFERRED`.
  - No currency found → `null` and warning `FIELD_MISSING` for `currency`.
  - Codes outside the allowlist → `null` with `FIELD_INVALID`.
- **ENG-NRM-04** (active) **Merchant tax ID (NIT).** Accepted input forms: `900123456-7`, `900.123.456-7`, `900123456 7`, `NIT 900123456-7`. Output: `<digits>-<check digit>` (digits without separators). Length of the base number 6 to 10 digits. The check digit is validated with the DIAN modulus-11 algorithm (weights `3,7,13,17,19,23,29,37,41,43,47,53,59,67,71` applied right-to-left over the base number; `r = sum mod 11`; check digit = `r` if `r ∈ {0,1}` else `11 − r`). A mismatch keeps the value and adds warning `NIT_CHECK_DIGIT_MISMATCH` (`ENG-CHK-07`). Tests use values computed with this algorithm, not the example in the draft.
- **ENG-NRM-05** (active) **Missing values** are always `null`. Never `""`, never `0` for a missing amount, never a placeholder string.
- **ENG-NRM-06** (active) **Payment method enum:** `cash`, `credit_card`, `debit_card`, `bank_transfer`, `digital_wallet`, `other`, or `null`. Keyword map (case and accent insensitive): `EFECTIVO`/`CASH` → `cash`; `TARJETA CREDITO`/`CREDIT CARD` → `credit_card`; `TARJETA DEBITO`/`DEBIT` → `debit_card`; `TRANSFERENCIA`/`PSE`/`BANK TRANSFER` → `bank_transfer`; `NEQUI`/`DAVIPLATA`/`WALLET` → `digital_wallet`. Any other recognized method word → `other`.
- **ENG-NRM-07** (active) **Original values.** When normalization changes or drops a value, the original text is kept in the internal field record. It is returned only with `include_debug_details=True` (`ENG-OUT-04`).
- **ENG-NRM-08** (active) **Unicode.** Text is NFC-normalized and matching is case- and accent-insensitive before keyword checks.

## 8. Stage 5 — Result validation (`ReceiptValidator`)

### 8.1 Required and optional fields

- **ENG-CHK-01** (active) **Required fields** for status `completed`: `merchant_name`, `issue_date`, `currency`, `total`.
- **ENG-CHK-02** (active) **Optional fields**: `merchant_tax_id`, `document_number`, `subtotal`, `tax_amount`, `discount`, `payment_method`, `line_items`. Missing optional fields produce no warning except when needed for a check (for example `FIELD_MISSING` for `merchant_tax_id` is NOT added in v1 to avoid noise).
- **ENG-CHK-03** (active) A missing or ambiguous **required** field produces warning `FIELD_MISSING` or `FIELD_AMBIGUOUS` with the field name and prevents status `completed` (`ENG-STS-02`).

### 8.2 Value checks

- **ENG-CHK-04** (active) `total` MUST be `>= 0`. A negative total → the field is set to `null`, error `VALIDATION_FAILED` with reason `NEGATIVE_TOTAL` (`ENG-ERR-*`).
- **ENG-CHK-05** (active) `issue_date` MUST be a valid calendar date within `[2000-01-01, current_year + 1]` using the injected clock. An invalid date that was present in the text → field `null`, `FIELD_INVALID`, and error `VALIDATION_FAILED` with reason `INVALID_DATE`.
- **ENG-CHK-06** (active) Every monetary field MUST be a valid `Decimal` string with two decimals. Invalid values are set to `null` (`FIELD_INVALID`). Invalid monetary values alone do NOT produce `VALIDATION_FAILED`; only negative totals and invalid dates do (`ENG-CHK-04`, `ENG-CHK-05`). This keeps the result usable.
- **ENG-CHK-07** (active) `merchant_tax_id` check digit mismatch → warning `NIT_CHECK_DIGIT_MISMATCH`; value kept.

### 8.3 Arithmetic checks

- **ENG-CHK-08** (active) Totals check: if `total` and `subtotal` are present, then `total` MUST equal `subtotal + tax_amount − discount` within a tolerance of `0.01`. `tax_amount` and `discount` default to `0.00` for this check only when they are missing. Mismatch → warning `TOTAL_MISMATCH` (both values kept).
- **ENG-CHK-09** (active) Line item check: for each item with `quantity`, `unit_price`, and `line_total` all present, `quantity × unit_price` MUST equal `line_total` within `0.01`. Mismatch → warning `LINE_ITEM_MISMATCH` with the item index.
- **ENG-CHK-10** (active) Line items sum check: if all items have `line_total` and `subtotal` is present, the sum of `line_total` MUST equal `subtotal` within `0.01`. Mismatch → warning `LINE_ITEMS_SUM_MISMATCH`. Worker persistence may additionally add LINE_ITEMS_TRUNCATED (WRK-PER-04).
- **ENG-CHK-11** (active) Arithmetic checks never change values. They only add warnings.

### 8.4 Validation outcome

- **ENG-CHK-12** (active) `validation.is_valid` is `false` if and only if the result has error `VALIDATION_FAILED`. Warnings never set `is_valid = false` (`ADR-014`).

## 9. Status semantics

- **ENG-STS-01** (active) The `status` field has exactly three values: `completed`, `partial`, `failed`.
- **ENG-STS-02** (active) `completed`: no error, and all required fields (`ENG-CHK-01`) are present and valid.
- **ENG-STS-03** (active) `partial`: no error, at least one required field is present, and at least one required field is missing or ambiguous. This is the `PARTIAL_EXTRACTION` case. The `error` field is `null`; the reason is conveyed by warnings `FIELD_MISSING`/`FIELD_AMBIGUOUS`. The worker maps this to job status `PARTIAL`.
- **ENG-STS-04** (active) `failed`: an error is set (`ENG-ERR-*`). `extracted_data` values are all `null` except the fields that were valid (for example `VALIDATION_FAILED` keeps valid optional fields).
- **ENG-STS-05** (active) If no required field could be extracted at all from successful OCR text, the result is `failed` with error `EXTRACTION_FAILED` and reason `NO_REQUIRED_FIELDS_FOUND`. This avoids returning an empty "partial" result that is not useful.

## 10. Errors

- **ENG-ERR-01** (active) Error codes (closed set): `UNSUPPORTED_FORMAT`, `INVALID_DOCUMENT`, `OCR_FAILED`, `EXTRACTION_FAILED`, `VALIDATION_FAILED`.
- **ENG-ERR-02** (active) Error object: `{ "code", "message", "retryable", "reason" }`. `message` is English, fixed per reason, and never contains document content. `reason` is an UPPER_SNAKE_CASE code from the table below.
- **ENG-ERR-03** (active) `retryable` rules:
  - `OCR_FAILED` with transient provider error → `retryable: true` (reason `PROVIDER_TRANSIENT`).
  - `OCR_FAILED` with permanent provider error → `retryable: false` (reason `PROVIDER_PERMANENT`).
  - All `INVALID_DOCUMENT`, `UNSUPPORTED_FORMAT`, `VALIDATION_FAILED`, and `EXTRACTION_FAILED` → `retryable: false`.
- **ENG-ERR-04** (active) Reason codes table:

  | Error code | Reason | Retryable |
  |---|---|---|
  | `UNSUPPORTED_FORMAT` | `UNSUPPORTED_SIGNATURE` | false |
  | `INVALID_DOCUMENT` | `FILE_EMPTY`, `FILE_TOO_LARGE`, `PDF_CORRUPTED`, `PDF_ENCRYPTED`, `PAGE_LIMIT_EXCEEDED`, `IMAGE_CORRUPTED`, `IMAGE_DIMENSIONS_EXCEEDED` | false |
  | `OCR_FAILED` | `PROVIDER_TRANSIENT` | true |
  | `OCR_FAILED` | `PROVIDER_PERMANENT` | false |
  | `EXTRACTION_FAILED` | `NO_TEXT_DETECTED`, `NO_REQUIRED_FIELDS_FOUND` | false |
  | `VALIDATION_FAILED` | `NEGATIVE_TOTAL`, `INVALID_DATE` | false |

- **ENG-ERR-05** (active) The engine MUST NOT silently return fabricated or incomplete financial values. Every value in `extracted_data` is either traceable to OCR text or structured fields, or it is `null`.

## 11. Output contract

- **ENG-OUT-01** (active) The result is serialized as JSON with this shape (all keys always present):
  ```json
  {
    "document_id": "5f0c2d6e-…",
    "document_type": "invoice",
    "status": "completed",
    "error": null,
    "extracted_data": {
      "merchant_name": "Example Store",
      "merchant_tax_id": "900123456-7",
      "merchant_address": null,
      "customer_id": null,
      "document_number": "INV-00123",
      "issue_date": "2026-11-03",
      "currency": "COP",
      "subtotal": "100000.00",
      "tax_amount": "19000.00",
      "discount": "0.00",
      "total": "119000.00",
      "payment_method": "credit_card",
      "line_items": []
    },
    "confidence": {
      "overall": 0.94,
      "fields": { "merchant_name": 0.98, "issue_date": 0.99, "total": 0.97 }
    },
    "validation": { "is_valid": true, "warnings": [] },
    "metadata": {
      "page_count": 1,
      "mime_type": "application/pdf",
      "provider": "tesseract",
      "engine_version": "1.0.0",
      "processing_ms": 1840
    }
  }
  ```
  The example values are illustrative; real values come only from OCR (`ENG-OUT-07`).
- **ENG-OUT-02** (active) Money fields are strings with two decimals. Dates are `YYYY-MM-DD`. Timestamps are not in the result; `processing_ms` is the only time value.
- **ENG-OUT-03** (active) `line_items` entries: `{ "description": str|null, "quantity": str|null, "unit_price": str|null, "line_total": str|null }`. Quantities are decimal strings.
- **ENG-OUT-04** (active) With `include_debug_details=True` only, the result also contains `raw_text` (concatenated lines in reading order) and, inside `validation`, a `field_sources` object mapping field names to source text. Without the flag, these keys are absent (not `null`).
- **ENG-OUT-05** (active) `warnings` entries: `{ "code": str, "field": str|null, "message": str }`. Warning codes are a closed set: `MIME_TYPE_MISMATCH`, `AMBIGUOUS_AMOUNT_FORMAT`, `DATE_FORMAT_ASSUMED`, `CURRENCY_INFERRED`, `FIELD_MISSING`, `FIELD_AMBIGUOUS`, `FIELD_INVALID`, `NEGATIVE_DISCOUNT_NORMALIZED`, `DOCUMENT_TYPE_UNKNOWN`, `NIT_CHECK_DIGIT_MISMATCH`, `TOTAL_MISMATCH`, `LINE_ITEM_MISMATCH`, `LINE_ITEMS_SUM_MISMATCH`. Worker persistence may additionally add LINE_ITEMS_TRUNCATED (WRK-PER-04).
- **ENG-OUT-06** (active) `confidence.fields` contains an entry only for non-null extracted scalar fields. Values are floats in `[0.0, 1.0]` rounded to two decimals. A field's confidence is the minimum confidence of the OCR lines or structured fields it was derived from. Normalization does not change confidence.
- **ENG-OUT-07** (active) `confidence.overall` is the arithmetic mean of `confidence.fields` values, rounded to two decimals; `null` when there are no fields. It is never a model guess.
- **ENG-OUT-08** (active) `metadata.provider` is the OCR provider `name`. `metadata.engine_version` comes from the package version. `processing_ms` is measured with a monotonic clock.

## 12. Configuration and logging

- **ENG-CFG-01** (active) `EngineSettings` fields and defaults: `max_document_bytes=5242880`, `max_pdf_pages=1`, `max_image_dimension=10000`, `ocr_timeout_seconds=60`, `default_locale="es-CO"`, `dollar_sign_currency="COP"`, `supported_currencies=("COP","USD","EUR","MXN","PEN","CLP","ARS")`, `ocr_provider="tesseract"` (informational; the instance is injected).
- **ENG-LOG-01** (active) The engine logs with the `logging` module at these points only: `document.validated` (type, page count, size bucket), `ocr.completed` (provider, line count, duration), `extraction.completed` (status, error code, warning codes, duration). Each log line includes `document_id`.
- **ENG-LOG-02** (active) The engine MUST NOT log: raw text, line text, field values, amounts, NIT, names, dates, currency values, file names, or byte contents.
- **ENG-LOG-03** (active) Exceptions raised by providers are logged with their class and code only (never their payloads).

## 13. Changes made to the AI-generated draft

| Draft said | This spec says | Reason |
|---|---|---|
| Engine retrieves the document from S3 (Stage 1) | Engine receives bytes (`ENG-API-02`) | Keeps the engine AWS-free (`ENG-SCOPE-02`). S3 is the worker's job. |
| `status` values `completed` only, error codes separate | Status is `completed`/`partial`/`failed`; `PARTIAL_EXTRACTION` is a status (`ENG-STS-03`) | Draft had two overlapping concepts. |
| Textract "may" be used | Tesseract only in v1 (`ADR-012`). Textract is denied for the instance role. Single-page PDF limit kept (`ENG-VAL-04`). | Verified with the lab role policies. |
| No size or page limits | 5 MiB, 1 page for PDF, 10000 px images (`ENG-VAL-02/04/06`) | Draft asked for "reasonable" limits; these make them testable. |
| Confidence source unspecified | Provider confidence only; min over sources; mean for overall (`ENG-OUT-06/07`) | Draft required confidence "from the provider", never fabricated. |
| Currency from `$` unspecified | Bare `$` → COP with `CURRENCY_INFERRED` (`ENG-NRM-03`) | Product targets Colombia; the inference is visible in warnings. |
| Date format unspecified | es-CO day-first with `DATE_FORMAT_ASSUMED` (`ENG-NRM-02`) | Colombian receipts use `DD/MM/YYYY`. |
| "Preserve original text" without a rule | Only with `include_debug_details=True`, never persisted (`ENG-NRM-07`, `WRK-PER-05`) | Draft also forbade logging receipt contents; persisting raw text conflicts with that. |
| Payment method enum shown as `credit_card` | Closed enum with keyword map (`ENG-NRM-06`) | Needs a fixed contract. |
| Optional fields "must not fail" | Optional fields are `null` and never fail a result (`ENG-CHK-02`, `ENG-STS-*`) | Draft rule made explicit. |
| `merchant_address`, `customer_id` listed as optional | Present as `null` in v1 (`ENG-EXT-12`, `ADR-029`) | Stable contract, extraction deferred. |
| NIT example `900123456-7` | Check digit validated with DIAN algorithm; tests use computed values (`ENG-NRM-04`) | The example's check digit is not verified. |
| Date/total validity as "checks" | Explicit rules (`ENG-CHK-04/05/06`) | Testability. |

## 14. Samples and tests

- **ENG-TST-01** (active) `samples/receipts/` contains synthetic documents only. Each sample has an expected JSON file `<name>.expected.json` with the expected stable contract projection (excluding timing and provider variability) of the engine when run with the recorded provider output `<name>.ocr.json`. Expected outputs are written by hand from the sample content, never generated from the engine itself.
- **ENG-TST-02** (active) Unit tests cover each requirement group: `VAL` (every error reason), `PROV` (fake transient vs permanent), `EXT` (structured-first, ambiguity), `NRM` (money formats incl. `1.234.567,89`, `119.000`, `119,5`; dates; currency; NIT check digit), `CHK` (each warning code), `STS` (each status), `OUT` (shape, absent debug keys), `LOG` (no sensitive content in captured logs).
- **ENG-TST-03** (active) A golden test runs the full engine on each sample with its recorded OCR output and compares the documented projection to `expected.json`.
- **ENG-TST-04** (active) A test asserts that `receipt_engine` imports no AWS or web module (`TST-CON-02`).
- **ENG-TST-05** (active) Tests run without network access and without AWS credentials.

## 15. Definition of done for the engine (from the course brief)

Mapped to course section 10:

1. Processes a valid PDF or image receipt → `ENG-VAL-*` + golden tests.
2. Extracts and normalizes the main financial fields → `ENG-EXT-*`, `ENG-NRM-*`.
3. Returns the agreed JSON contract → `ENG-OUT-*`.
4. Handles missing fields and errors predictably → `ENG-STS-*`, `ENG-ERR-*`, `ENG-CHK-*`.
5. Unit tests for normalization, validation, and error handling → `ENG-TST-02`.
6. Invoked by the worker without depending on API, DynamoDB, or SNS → `ENG-SCOPE-*`, `ENG-TST-04`.
7. The worker persists output and completes the flow → `WRK-*`, `TST-E2E-*`.
