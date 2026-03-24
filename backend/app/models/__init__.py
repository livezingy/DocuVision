"""
DocuVision – Data Models Package

Exports:
  layout_result      — Legacy LayoutElement / LayoutAnalysisResult (existing)
  semantic_roles     — SemanticRole enum (Phase 1)
  mapping_rules      — MappingRuleSet and rule dataclasses (Phase 1)
  canonical_document — CanonicalDocument contract (Phase 1)
"""

from app.models.layout_result import (
    LayoutAnalysisResult,
    LayoutBbox,
    LayoutElement,
    LayoutElementType,
)
from app.models.semantic_roles import SemanticRole
from app.models.mapping_rules import (
    ConfidencePolicy,
    MappingRule,
    MappingRuleSet,
    PostProcessConfig,
    RuleAction,
    RuleCondition,
    StoragePolicy,
    TaxonomyConfig,
)
from app.models.canonical_document import (
    CANONICAL_SCHEMA_VERSION,
    CANONICAL_TAXONOMY_VERSION,
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalTable,
    ImageMeta,
    OcrLine,
    SourceRefs,
    VisualizationRefs,
    bbox_to_polygon,
    normalize_bbox,
    normalize_polygon,
)

__all__ = [
    # Legacy models
    "LayoutAnalysisResult",
    "LayoutBbox",
    "LayoutElement",
    "LayoutElementType",
    # Phase 1 – Semantic roles
    "SemanticRole",
    # Phase 1 – Mapping rules
    "ConfidencePolicy",
    "MappingRule",
    "MappingRuleSet",
    "PostProcessConfig",
    "RuleAction",
    "RuleCondition",
    "StoragePolicy",
    "TaxonomyConfig",
    # Phase 1 – Canonical document
    "CANONICAL_SCHEMA_VERSION",
    "CANONICAL_TAXONOMY_VERSION",
    "CanonicalBlock",
    "CanonicalDocument",
    "CanonicalPage",
    "CanonicalTable",
    "ImageMeta",
    "OcrLine",
    "SourceRefs",
    "VisualizationRefs",
    "bbox_to_polygon",
    "normalize_bbox",
    "normalize_polygon",
]
