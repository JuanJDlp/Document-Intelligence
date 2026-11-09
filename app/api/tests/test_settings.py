"""API configuration is validated once without disclosing values."""

import pytest
from api.settings import ApiSettings


@pytest.mark.parametrize("value", ["not-an-integer", "0", "5242881"])
def test_api_ops_reject_invalid_upload_limit(monkeypatch, value):
    monkeypatch.setenv("DOCUPROCESS_MAX_UPLOAD_BYTES", value)
    with pytest.raises(RuntimeError) as error:
        ApiSettings.from_environment(require_aws=False)
    assert str(error.value) == "Invalid configuration: DOCUPROCESS_MAX_UPLOAD_BYTES"


def test_api_ops_required_environment(monkeypatch):
    monkeypatch.delenv("DOCUPROCESS_AWS_REGION", raising=False)
    with pytest.raises(RuntimeError, match="Missing configuration: DOCUPROCESS_AWS_REGION"):
        ApiSettings.from_environment()
