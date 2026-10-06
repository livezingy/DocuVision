"""P-030 X8 / P-031 X6 domain-consistency sentinel.

Asserts the doc-type registries stay fully aligned after the P-031 pico
wiring (7 == 7 == 7):
- classifier keywords == KIE supported set;
- the KIE supported set == the kie_configs registry keys.
"""

from pathlib import Path

import yaml

from app.services.document_type_classifier import _KEYWORDS
from app.services.kie.query_fields import KIE_SUPPORTED_DOC_TYPES

_SCRIPT_DIR = Path(__file__).resolve().parent
_REGISTRY = (
    _SCRIPT_DIR.parent
    / "app"
    / "services"
    / "kie"
    / "kie_configs"
    / "_registry.yaml"
)


def test_classifier_keywords_match_kie_supported_doc_types() -> None:
    assert set(_KEYWORDS.keys()) == set(KIE_SUPPORTED_DOC_TYPES)
    assert len(_KEYWORDS) == 7


def test_kie_supported_doc_types_match_registry() -> None:
    registry = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))
    registry_keys = set(registry["types"].keys())
    assert set(KIE_SUPPORTED_DOC_TYPES) == registry_keys
    assert "pico" in registry_keys
    assert "coi" in registry_keys
