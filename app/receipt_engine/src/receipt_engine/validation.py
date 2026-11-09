from io import BytesIO
import warnings
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from .models import DocumentInput, EngineSettings


class DocumentError(Exception):
    def __init__(
        self, code: str, reason: str, mime_type: str | None = None, pages: int = 0
    ) -> None:
        self.code, self.reason, self.mime_type, self.pages = code, reason, mime_type, pages
        super().__init__(reason)


class DocumentValidator:
    def __init__(self, settings: EngineSettings | None = None) -> None:
        self.settings = settings or EngineSettings()

    def validate(self, document: DocumentInput) -> tuple[str, int]:
        data = document.content
        if not data:
            raise DocumentError("INVALID_DOCUMENT", "FILE_EMPTY")
        if len(data) > self.settings.max_document_bytes:
            raise DocumentError("INVALID_DOCUMENT", "FILE_TOO_LARGE")
        if data.startswith(b"%PDF-"):
            try:
                pdf = PdfReader(BytesIO(data), strict=True)
                if pdf.is_encrypted:
                    raise DocumentError("INVALID_DOCUMENT", "PDF_ENCRYPTED", "application/pdf")
                pages = len(pdf.pages)
            except DocumentError:
                raise
            except (PdfReadError, ValueError, KeyError, TypeError, OSError):
                raise DocumentError(
                    "INVALID_DOCUMENT", "PDF_CORRUPTED", "application/pdf"
                ) from None
            if pages == 0:
                raise DocumentError("INVALID_DOCUMENT", "PDF_CORRUPTED", "application/pdf")
            if pages > self.settings.max_pdf_pages:
                raise DocumentError(
                    "INVALID_DOCUMENT", "PAGE_LIMIT_EXCEEDED", "application/pdf", pages
                )
            return "application/pdf", pages
        mime = (
            "image/png"
            if data.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/jpeg"
            if data.startswith(b"\xff\xd8\xff")
            else None
        )
        if mime is None:
            raise DocumentError("UNSUPPORTED_FORMAT", "UNSUPPORTED_SIGNATURE")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    if max(image.size) > self.settings.max_image_dimension:
                        raise DocumentError("INVALID_DOCUMENT", "IMAGE_DIMENSIONS_EXCEEDED", mime)
                    image.verify()
        except DocumentError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise DocumentError("INVALID_DOCUMENT", "IMAGE_DIMENSIONS_EXCEEDED", mime) from None
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
            raise DocumentError("INVALID_DOCUMENT", "IMAGE_CORRUPTED", mime) from None
        return mime, 1
