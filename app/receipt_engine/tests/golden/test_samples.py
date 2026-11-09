"""ENG-TST-03: independent expectations with deterministic provider recordings."""

import json
from pathlib import Path
from datetime import datetime, timezone
import pytest
from receipt_engine import DocumentInput, OcrLine, OcrResult, ReceiptExtractionEngine
from receipt_engine.models import ProviderLineItem

SAMPLES = Path(__file__).resolve().parents[4] / "samples/receipts"


class RecordedProvider:
    name = "synthetic-fixture"

    def __init__(self, recording):
        self.recording = recording

    def extract(self, request):
        return OcrResult(
            tuple(OcrLine(**line) for line in self.recording["lines"]),
            self.name,
            structured_line_items=tuple(
                ProviderLineItem(**item) for item in self.recording["structured_line_items"]
            ),
        )


@pytest.mark.parametrize(
    "expected_file", sorted(SAMPLES.glob("*.expected.json")), ids=lambda p: p.name
)
def test_eng_tst_03_golden(expected_file):
    name = expected_file.name.removesuffix(".expected.json")
    recording = json.loads((SAMPLES / (name + ".ocr.json")).read_text())
    expected = json.loads(expected_file.read_text())
    result = (
        ReceiptExtractionEngine(
            ocr_provider=RecordedProvider(recording),
            clock=lambda: datetime(2026, 1, 16, tzinfo=timezone.utc),
        )
        .process(DocumentInput("golden-synthetic", (SAMPLES / name).read_bytes()))
        .to_dict()
    )
    assert result["status"] == expected["status"]
    assert (result["error"] or {}).get("reason") == expected.get("reason")
    for key, value in expected.get("fields", {}).items():
        assert result["extracted_data"][key] == value
    assert set(expected.get("warnings", [])) <= {
        warning["code"] for warning in result["validation"]["warnings"]
    }
    if "line_items" in expected:
        assert result["extracted_data"]["line_items"] == expected["line_items"]
