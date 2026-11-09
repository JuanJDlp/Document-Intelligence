import json
import sys
from receipt_engine import DocumentInput, ReceiptExtractionEngine
from receipt_engine.ocr.tesseract import TesseractProvider

if __name__ == "__main__":
    content = sys.stdin.buffer.read(5242881)
    engine = ReceiptExtractionEngine(ocr_provider=TesseractProvider())
    result = engine.process(DocumentInput(sys.argv[2], content, sys.argv[1]))
    sys.stdout.write(json.dumps(result.to_dict()))
