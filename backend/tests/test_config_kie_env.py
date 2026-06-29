"""Settings env alias for KIE model path (pydantic-settings v2)."""

from app.core.config import Settings


def test_settings_reads_docuvision_kie_model_id(monkeypatch):
    monkeypatch.setenv(
        "DOCUVISION_KIE_QWEN_MODEL_ID",
        "/home/aistudio/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct",
    )
    settings = Settings()
    assert settings.KIE_QWEN_MODEL_ID == (
        "/home/aistudio/.cache/modelscope/hub/models/Qwen/Qwen2___5-VL-3B-Instruct"
    )
