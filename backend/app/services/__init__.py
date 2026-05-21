# Services package — avoid eager imports here (ocr/layout/table pull in Paddle).
# Import concrete modules directly, e.g. `from app.services.ocr_service import OCRService`.

__all__: list[str] = []
