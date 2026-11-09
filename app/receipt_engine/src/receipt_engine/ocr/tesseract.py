from io import BytesIO
from collections import defaultdict
from PIL import Image
import pypdfium2
import pytesseract
from ..models import OcrLine, OcrRequest, OcrResult, OcrProviderError


class TesseractProvider:
    name = "tesseract"

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout

    def extract(self, request: OcrRequest) -> OcrResult:
        pdf = None
        bitmap = None
        try:
            if request.mime_type == "application/pdf":
                pdf = pypdfium2.PdfDocument(request.content)
                bitmap = pdf[0].render(scale=300 / 72)
                image = bitmap.to_pil()
            else:
                image = Image.open(BytesIO(request.content))
            try:
                data = pytesseract.image_to_data(
                    image, lang="spa+eng", timeout=self.timeout, output_type=pytesseract.Output.DICT
                )
            finally:
                image.close()
        except (pytesseract.TesseractError, pytesseract.TesseractNotFoundError):
            raise OcrProviderError(False, "TESSERACT_UNAVAILABLE") from None
        except RuntimeError:
            raise OcrProviderError(True, "OCR_TIMEOUT") from None
        finally:
            if bitmap is not None:
                bitmap.close()
            if pdf is not None:
                pdf.close()
        groups: dict[tuple[int, int, int], list[tuple[str, float]]] = defaultdict(list)
        for i, text in enumerate(data["text"]):
            confidence = float(data["conf"][i])
            if text.strip() and confidence >= 0:
                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                groups[key].append((text, confidence / 100))
        return OcrResult(
            tuple(
                OcrLine(" ".join(t for t, _ in words), sum(c for _, c in words) / len(words))
                for words in groups.values()
            ),
            self.name,
        )
