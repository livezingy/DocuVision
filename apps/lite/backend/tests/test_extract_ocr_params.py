"""Tests for Lite /extract/ocr route pass-through of languages/pages_spec/max_pages."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _image_bytes() -> bytes:
    from PIL import Image
    from io import BytesIO

    buf = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_extract_ocr_passes_through_languages_pages_max_pages():
    img = _image_bytes()
    with patch("app.api.routes_extract.extract_ocr_from_image") as mock_ocr:
        mock_ocr.return_value = {"text_blocks": []}

        response = client.post(
            "/api/v1/lite/extract/ocr",
            files={"file": ("a.png", img, "image/png")},
            data={
                "languages": "chi_sim,eng",
                "pages_spec": "1",
                "max_pages": 5,
            },
        )

    assert response.status_code == 200, response.text
    assert mock_ocr.called
    kwargs = mock_ocr.call_args.kwargs
    assert kwargs["languages"] == ["chi_sim", "eng"]
    assert kwargs["pages_spec"] == "1"
    assert kwargs["max_pages"] == 5


def test_extract_ocr_defaults_languages_none_when_omitted():
    img = _image_bytes()
    with patch("app.api.routes_extract.extract_ocr_from_image") as mock_ocr:
        mock_ocr.return_value = {"text_blocks": []}

        response = client.post(
            "/api/v1/lite/extract/ocr",
            files={"file": ("a.png", img, "image/png")},
        )

    assert response.status_code == 200, response.text
    kwargs = mock_ocr.call_args.kwargs
    assert kwargs["languages"] is None
    assert kwargs["pages_spec"] is None
    assert kwargs["max_pages"] == 10
