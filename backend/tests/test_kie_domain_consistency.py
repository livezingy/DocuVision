"""P-030 X8 domain-consistency sentinel (coi stage).

Asserts the three coi-domain registries stay aligned after the P-030b wiring:
- classifier keywords and the KIE supported set are equal (6 == 6);
- the KIE supported set is contained in the kie_configs registry.

The registry is a superset on purpose: ``pico`` is already registered but its
pipeline wiring belongs to P-031, so full equality (7 == 7 == 7) is deferred
to the P-031 sentinel.
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
    assert len(_KEYWORDS) == 6


def test_kie_supported_doc_types_subset_of_registry() -> None:
    registry = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))
    registry_keys = set(registry["types"].keys())
    assert set(KIE_SUPPORTED_DOC_TYPES) <= registry_keys
    # Superset guard: pico stays registered without being wired (P-031 scope).
    assert "pico" in registry_keys
    assert "coi" in registry_keys
