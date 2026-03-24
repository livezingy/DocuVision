"""
Mapping Rule Data Models for Canonical Document Semantic Mapping

Provides dataclasses for loading, validating, and applying label→role mapping
rules. Rules are loaded from YAML config files which can be hot-reloaded at
runtime without restarting the service.

Usage:
    rule_set = MappingRuleSet.from_yaml_file("backend/config/semantic_mapping_base.yaml")
    semantic_role, rule_id = rule_set.apply("doc_title")      # -> ("Title", "R001")
    semantic_role, rule_id = rule_set.apply("text")            # -> ("Paragraph", "R012")
    semantic_role, rule_id = rule_set.apply("text",
                                             doc_type="invoice",
                                             content_text="Invoice No: 123")
                                                               # -> ("KeyValuePair", "R011")

YAML structure expected:
    config:
      mapping_version: "1.0.0"
      taxonomy_version: "azure-like-v1"
      default_role: "Paragraph"
      confidence_policy: ...
      storage: ...
    normalize:
      raw_label_alias: {title: doc_title, heading: paragraph_title, ...}
    rules:
      - id: R001
        enabled: true
        priority: 1000
        when: {raw_label_in: [...], doc_type_in: [...], text_regex_any: [...]}
        then: {semantic_role: Title, confidence_adjustment: 0.0}
    postprocess:
      merge_adjacent_blocks: {enabled: true}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


__all__ = [
    "RuleCondition",
    "RuleAction",
    "MappingRule",
    "ConfidencePolicy",
    "StoragePolicy",
    "TaxonomyConfig",
    "PostProcessConfig",
    "MappingRuleSet",
]


# ── Condition ─────────────────────────────────────────────────────────────────

@dataclass
class RuleCondition:
    """
    All conditions for a mapping rule ('when' clause in YAML).
    Multiple fields act as AND conditions — all that are set must be satisfied.
    """

    # Block's normalised raw_label must be in this list (empty = match all labels)
    raw_label_in: List[str] = field(default_factory=list)

    # Document type must be in this list (empty = match all doc types)
    doc_type_in: List[str] = field(default_factory=list)

    # Block's content_text must match at least ONE of these regexes (OR semantics)
    text_regex_any: List[str] = field(default_factory=list)

    # Block confidence must be STRICTLY BELOW this threshold
    confidence_lt: Optional[float] = None

    def matches(
        self,
        raw_label_norm: str,
        doc_type: str = "unknown",
        content_text: str = "",
        confidence: float = 1.0,
    ) -> bool:
        """
        Evaluate whether this condition is satisfied.

        Args:
            raw_label_norm: Alias-normalised raw label (lower-cased).
            doc_type:       Document type hint (e.g. 'invoice', 'unknown').
            content_text:   The block's text content.
            confidence:     Block detection confidence [0, 1].

        Returns:
            True only if ALL set conditions pass.
        """
        if self.raw_label_in and raw_label_norm not in self.raw_label_in:
            return False

        if self.doc_type_in and doc_type not in self.doc_type_in:
            return False

        if self.text_regex_any:
            if not any(
                re.search(pattern, content_text or "", re.IGNORECASE)
                for pattern in self.text_regex_any
            ):
                return False

        if self.confidence_lt is not None and confidence >= self.confidence_lt:
            return False

        return True

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuleCondition":
        return cls(
            raw_label_in=[str(v).lower() for v in d.get("raw_label_in", [])],
            doc_type_in=[str(v).lower() for v in d.get("doc_type_in", [])],
            text_regex_any=d.get("text_regex_any", []),
            confidence_lt=d.get("confidence_lt"),
        )


# ── Action ────────────────────────────────────────────────────────────────────

@dataclass
class RuleAction:
    """
    Actions applied when a rule matches ('then' clause in YAML).
    """

    semantic_role: str = "Unknown"
    "Target semantic role string (must be a SemanticRole value)."

    confidence_adjustment: float = 0.0
    "Delta added to block.confidence after mapping (use negative to demote)."

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuleAction":
        return cls(
            semantic_role=d.get("semantic_role", "Unknown"),
            confidence_adjustment=float(d.get("confidence_adjustment", 0.0)),
        )


# ── Single Rule ───────────────────────────────────────────────────────────────

@dataclass
class MappingRule:
    """
    A single mapping rule: priority-ordered condition → action pair.

    Higher priority rules are evaluated first. The first matching rule wins
    (no further rules are evaluated for that block).
    """

    rule_id: str
    enabled: bool
    priority: int
    condition: RuleCondition
    action: RuleAction

    def evaluate(
        self,
        raw_label_norm: str,
        doc_type: str = "unknown",
        content_text: str = "",
        confidence: float = 1.0,
    ) -> Optional[RuleAction]:
        """
        Returns the RuleAction if this rule matches the given block context.
        Returns None if disabled or condition not satisfied.
        """
        if not self.enabled:
            return None
        if self.condition.matches(raw_label_norm, doc_type, content_text, confidence):
            return self.action
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MappingRule":
        return cls(
            rule_id=data["id"],
            enabled=bool(data.get("enabled", True)),
            priority=int(data.get("priority", 0)),
            condition=RuleCondition.from_dict(data.get("when", {})),
            action=RuleAction.from_dict(data.get("then", {})),
        )


# ── Config sub-structures ─────────────────────────────────────────────────────

@dataclass
class ConfidencePolicy:
    """Confidence threshold configuration for block processing."""

    min_block_confidence: float = 0.0
    "Blocks below this threshold are still mapped but flagged as low-confidence."

    demote_if_below: float = 0.2
    "Blocks below this threshold have their semantic_role forced to Unknown."

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConfidencePolicy":
        return cls(
            min_block_confidence=float(d.get("min_block_confidence", 0.0)),
            demote_if_below=float(d.get("demote_if_below", 0.2)),
        )


@dataclass
class StoragePolicy:
    """Controls which diagnostic fields are persisted in the Canonical output."""

    keep_raw_role: bool = True
    "Persist block_type_raw alongside the mapped semantic_role."

    keep_rule_hit_trace: bool = True
    "Persist the rule_hit_id that produced the semantic_role."

    keep_mapping_version: bool = True
    "Persist the taxonomy_version on the CanonicalDocument."

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StoragePolicy":
        return cls(
            keep_raw_role=bool(d.get("keep_raw_role", True)),
            keep_rule_hit_trace=bool(d.get("keep_rule_hit_trace", True)),
            keep_mapping_version=bool(d.get("keep_mapping_version", True)),
        )


@dataclass
class TaxonomyConfig:
    """Top-level configuration block loaded from the mapping YAML."""

    mapping_version: str = "1.0.0"
    taxonomy_version: str = "azure-like-v1"
    default_role: str = "Paragraph"
    confidence_policy: ConfidencePolicy = field(default_factory=ConfidencePolicy)
    storage: StoragePolicy = field(default_factory=StoragePolicy)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaxonomyConfig":
        return cls(
            mapping_version=d.get("mapping_version", "1.0.0"),
            taxonomy_version=d.get("taxonomy_version", "azure-like-v1"),
            default_role=d.get("default_role", "Paragraph"),
            confidence_policy=ConfidencePolicy.from_dict(d.get("confidence_policy", {})),
            storage=StoragePolicy.from_dict(d.get("storage", {})),
        )


@dataclass
class PostProcessConfig:
    """Post-processing settings applied after all rules are evaluated."""

    merge_adjacent_blocks: bool = True
    "Merge consecutive blocks of the same semantic_role into a single block."

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PostProcessConfig":
        merge_cfg = d.get("merge_adjacent_blocks", {})
        if isinstance(merge_cfg, dict):
            enabled = bool(merge_cfg.get("enabled", True))
        else:
            enabled = bool(merge_cfg)
        return cls(merge_adjacent_blocks=enabled)


# ── Rule Set ──────────────────────────────────────────────────────────────────

@dataclass
class MappingRuleSet:
    """
    Complete rule set loaded from one or more mapping YAML files.

    Rules are sorted by priority (descending) on construction.
    Supports hot-reload: call from_yaml_file() again to get an updated instance
    without restarting the service.

    Typical loading:
        base = MappingRuleSet.from_yaml_file("backend/config/semantic_mapping_base.yaml")

    Batch re-mapping call (Phase 3 /remapping API):
        changed = canonical_doc.remap_semantics(rule_set, doc_type="invoice")
    """

    config: TaxonomyConfig
    raw_label_aliases: Dict[str, str]
    "Maps alias labels to canonical raw labels. All keys/values are lower-cased."

    rules: List[MappingRule]
    "All rules sorted by priority descending."

    postprocess: PostProcessConfig = field(default_factory=PostProcessConfig)

    # ── Label normalisation ───────────────────────────────────────────────────

    def normalize_label(self, raw_label: str) -> str:
        """
        Apply alias normalisation to a raw label.

        e.g.  "title"   → "doc_title"   (via alias)
              "heading" → "paragraph_title"
              "MyBlock" → "myblock"      (lower-cased, no alias)
        """
        normalized = raw_label.lower().strip()
        return self.raw_label_aliases.get(normalized, normalized)

    # ── Rule application ──────────────────────────────────────────────────────

    def apply(
        self,
        raw_label: str,
        doc_type: str = "unknown",
        content_text: str = "",
        confidence: float = 1.0,
    ) -> Tuple[str, Optional[str]]:
        """
        Find the first matching rule for a block and return the mapped role.

        Applies confidence demote policy before rule evaluation: blocks
        whose confidence is below `config.confidence_policy.demote_if_below`
        are directly mapped to "Unknown".

        Args:
            raw_label:    Original label from PaddleOCR/PPStructure.
            doc_type:     Document type hint (controls domain-specific rules).
            content_text: Block content (used for regex-based rules).
            confidence:   Block detection confidence.

        Returns:
            Tuple of (semantic_role_str, rule_id_that_matched).
            rule_id is None when the default_role fallback is used.
        """
        # Confidence demote (applied before alias normalisation)
        if confidence < self.config.confidence_policy.demote_if_below:
            return "Unknown", None

        normalized = self.normalize_label(raw_label)

        for rule in self.rules:  # sorted by priority desc
            action = rule.evaluate(normalized, doc_type, content_text, confidence)
            if action is not None:
                return action.semantic_role, rule.rule_id

        return self.config.default_role, None

    # ── Introspection ─────────────────────────────────────────────────────────

    def describe(self) -> Dict[str, Any]:
        """Return a summary dict for logging/debugging."""
        return {
            "taxonomy_version": self.config.taxonomy_version,
            "mapping_version": self.config.mapping_version,
            "rule_count": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules if r.enabled),
            "alias_count": len(self.raw_label_aliases),
            "default_role": self.config.default_role,
        }

    # ── Deserialization ───────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MappingRuleSet":
        """Build a MappingRuleSet from a parsed YAML/JSON dict."""
        config = TaxonomyConfig.from_dict(data.get("config", {}))

        # Build alias dict — all keys and values are lower-cased for safe lookup
        raw_aliases = data.get("normalize", {}).get("raw_label_alias", {})
        aliases: Dict[str, str] = {
            str(k).lower(): str(v).lower() for k, v in raw_aliases.items()
        }

        rules = sorted(
            [MappingRule.from_dict(r) for r in data.get("rules", [])],
            key=lambda r: r.priority,
            reverse=True,
        )

        postprocess = PostProcessConfig.from_dict(data.get("postprocess", {}))

        return cls(config=config, raw_label_aliases=aliases, rules=rules, postprocess=postprocess)

    @classmethod
    def from_yaml_file(cls, path: str) -> "MappingRuleSet":
        """
        Load a MappingRuleSet from a YAML file.

        Requires PyYAML (pyyaml>=6.0).
        Raises FileNotFoundError if path does not exist.
        Raises yaml.YAMLError on parse errors.

        This method is designed for hot-reload: call it again whenever the
        YAML file changes to get an updated rule set.
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to load mapping rules from YAML files. "
                "Install it with: pip install pyyaml>=6.0"
            ) from exc

        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        return cls.from_dict(data)

    @classmethod
    def from_yaml_string(cls, yaml_text: str) -> "MappingRuleSet":
        """Load a MappingRuleSet from a YAML string (useful for tests)."""
        try:
            import yaml
        except ImportError as exc:
            raise ImportError("PyYAML is required.") from exc
        return cls.from_dict(yaml.safe_load(yaml_text))
