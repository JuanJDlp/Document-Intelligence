from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class DocumentInput:
    document_id: str
    content: bytes
    declared_mime_type: str | None = None
    filename: str | None = None


@dataclass(frozen=True)
class EngineSettings:
    max_document_bytes: int = 5242880
    max_pdf_pages: int = 1
    max_image_dimension: int = 10000
    ocr_timeout_seconds: int = 60
    default_locale: str = "es-CO"
    dollar_sign_currency: str = "COP"
    supported_currencies: tuple[str, ...] = ("COP", "USD", "EUR", "MXN", "PEN", "CLP", "ARS")
    ocr_provider: str = "tesseract"


@dataclass(frozen=True)
class OcrRequest:
    content: bytes
    mime_type: str
    page_count: int


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    page: int = 1


@dataclass(frozen=True)
class ProviderField:
    type: str
    value: str
    confidence: float


@dataclass(frozen=True)
class ProviderLineItem:
    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    line_total: str | None = None


@dataclass(frozen=True)
class OcrResult:
    lines: tuple[OcrLine, ...]
    provider_name: str
    structured_fields: tuple[ProviderField, ...] = ()
    structured_line_items: tuple[ProviderLineItem, ...] = ()


class OCRProvider(Protocol):
    name: str

    def extract(self, request: OcrRequest) -> OcrResult: ...


class OcrProviderError(Exception):
    def __init__(self, transient: bool, code: str, detail: str = "") -> None:
        self.transient = transient
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExtractionResult:
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.payload
