"""
Unit tests for backend/app/models/mapping_rules.py

Run from the project root:
    cd backend
    python -m pytest tests/test_mapping_rules.py -v

Or directly on the cloud runner:
    pytest backend/tests/test_mapping_rules.py -v
"""
import sys
import os

# Allow imports from backend/app without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ─────────────────────────────────────────────────────────────────────────────

MINIMAL_YAML = """
config:
  mapping_version: "1.0.0"
  taxonomy_version: "azure-like-v1"
  default_role: "Paragraph"
  confidence_policy:
    min_block_confidence: 0.0
    demote_if_below: 0.2
  storage:
    keep_raw_role: true
    keep_rule_hit_trace: true
    keep_mapping_version: true

normalize:
  raw_label_alias:
    title: doc_title
    heading: paragraph_title
    text: text
    paragraph: text
    header: header
    footer: footer
    table: table
    figure: figure
    image: figure
    figure_title: figure_title
    table_title: table_title
    formula: formula
    equation: formula
    reference: reference
    footnote: footnote

rules:
  - id: R001
    enabled: true
    priority: 1000
    when:
      raw_label_in: [doc_title]
    then:
      semantic_role: Title

  - id: R002
    enabled: true
    priority: 950
    when:
      raw_label_in: [paragraph_title]
    then:
      semantic_role: SectionHeading

  - id: R003
    enabled: true
    priority: 900
    when:
      raw_label_in: [header]
    then:
      semantic_role: PageHeader

  - id: R004
    enabled: true
    priority: 900
    when:
      raw_label_in: [footer]
    then:
      semantic_role: PageFooter

  - id: R005
    enabled: true
    priority: 900
    when:
      raw_label_in: [table]
    then:
      semantic_role: Table

  - id: R006
    enabled: true
    priority: 900
    when:
      raw_label_in: [figure]
    then:
      semantic_role: Figure

  - id: R007
    enabled: true
    priority: 850
    when:
      raw_label_in: [figure_title, table_title]
    then:
      semantic_role: Caption

  - id: R008
    enabled: true
    priority: 850
    when:
      raw_label_in: [formula]
    then:
      semantic_role: Formula

  - id: R009
    enabled: true
    priority: 800
    when:
      raw_label_in: [reference]
    then:
      semantic_role: Reference

  - id: R010
    enabled: true
    priority: 800
    when:
      raw_label_in: [footnote]
    then:
      semantic_role: Footnote

  - id: R011
    enabled: true
    priority: 700
    when:
      raw_label_in: [text]
      doc_type_in: [invoice, receipt, contract]
      text_regex_any:
        - "(?i)invoice\\\\s*no|发票号|单据号|合同编号|receipt\\\\s*no"
        - "(?i)total|subtotal|tax|amount\\\\s*due|合计|税额|价税合计"
    then:
      semantic_role: KeyValuePair

  - id: R012
    enabled: true
    priority: 100
    when:
      raw_label_in: [text]
    then:
      semantic_role: Paragraph

postprocess:
  merge_adjacent_blocks:
    enabled: true
"""


@pytest.fixture()
def rule_set():
    """Return a MappingRuleSet loaded from the inline MINIMAL_YAML."""
    return MappingRuleSet.from_yaml_string(MINIMAL_YAML)


@pytest.fixture()
def base_rule_set():
    """Load the actual semantic_mapping_base.yaml from the project config dir."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "config", "semantic_mapping_base.yaml"
    )
    config_path = os.path.normpath(config_path)
    if not os.path.exists(config_path):
        pytest.skip(f"Config file not found: {config_path}")
    return MappingRuleSet.from_yaml_file(config_path)


# ─────────────────────────────────────────────────────────────────────────────
# 1. RuleCondition.matches()
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleCondition:
    def test_empty_condition_matches_anything(self):
        cond = RuleCondition()
        assert cond.matches("anything", doc_type="invoice", content_text="hello")

    def test_raw_label_in_match(self):
        cond = RuleCondition(raw_label_in=["doc_title"])
        assert cond.matches("doc_title")

    def test_raw_label_in_no_match(self):
        cond = RuleCondition(raw_label_in=["doc_title"])
        assert not cond.matches("text")

    def test_doc_type_in_match(self):
        cond = RuleCondition(raw_label_in=["text"], doc_type_in=["invoice"])
        assert cond.matches("text", doc_type="invoice")

    def test_doc_type_in_no_match(self):
        cond = RuleCondition(raw_label_in=["text"], doc_type_in=["invoice"])
        assert not cond.matches("text", doc_type="unknown")

    def test_text_regex_any_match(self):
        cond = RuleCondition(text_regex_any=["(?i)invoice\\s*no"])
        assert cond.matches("text", content_text="Invoice No: 12345")

    def test_text_regex_any_no_match(self):
        cond = RuleCondition(text_regex_any=["(?i)invoice\\s*no"])
        assert not cond.matches("text", content_text="random text")

    def test_confidence_lt_triggers(self):
        cond = RuleCondition(confidence_lt=0.5)
        assert cond.matches("text", confidence=0.3)

    def test_confidence_lt_not_triggered(self):
        cond = RuleCondition(confidence_lt=0.5)
        assert not cond.matches("text", confidence=0.6)

    def test_all_conditions_must_pass(self):
        cond = RuleCondition(
            raw_label_in=["text"],
            doc_type_in=["invoice"],
            text_regex_any=["(?i)total"],
        )
        # All conditions met
        assert cond.matches("text", doc_type="invoice", content_text="Total: 100")
        # Only label + doc_type, missing text
        assert not cond.matches("text", doc_type="invoice", content_text="nothing here")
        # Only label matches
        assert not cond.matches("text", doc_type="unknown", content_text="Total: 100")


# ─────────────────────────────────────────────────────────────────────────────
# 2. MappingRuleSet – YAML loading
# ─────────────────────────────────────────────────────────────────────────────

class TestMappingRuleSetLoading:
    def test_from_yaml_string_loads_rules(self, rule_set):
        assert len(rule_set.rules) == 12

    def test_rules_sorted_by_priority_descending(self, rule_set):
        priorities = [r.priority for r in rule_set.rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_config_fields(self, rule_set):
        assert rule_set.config.mapping_version == "1.0.0"
        assert rule_set.config.taxonomy_version == "azure-like-v1"
        assert rule_set.config.default_role == "Paragraph"

    def test_confidence_policy_loaded(self, rule_set):
        assert rule_set.config.confidence_policy.demote_if_below == pytest.approx(0.2)

    def test_alias_dict_populated(self, rule_set):
        assert "title" in rule_set.raw_label_aliases
        assert "heading" in rule_set.raw_label_aliases

    def test_aliases_are_lowercased(self, rule_set):
        for k, v in rule_set.raw_label_aliases.items():
            assert k == k.lower()
            assert v == v.lower()

    def test_postprocess_loaded(self, rule_set):
        assert rule_set.postprocess.merge_adjacent_blocks is True

    def test_from_yaml_file_base_config(self, base_rule_set):
        """Smoke test: base YAML file parses correctly and has expected rules."""
        desc = base_rule_set.describe()
        assert desc["rule_count"] >= 12
        assert desc["alias_count"] >= 20
        assert desc["taxonomy_version"] == "azure-like-v1"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Label normalisation
# ─────────────────────────────────────────────────────────────────────────────

class TestLabelNormalisation:
    def test_alias_title_to_doc_title(self, rule_set):
        assert rule_set.normalize_label("title") == "doc_title"

    def test_alias_heading_to_paragraph_title(self, rule_set):
        assert rule_set.normalize_label("heading") == "paragraph_title"

    def test_alias_paragraph_to_text(self, rule_set):
        assert rule_set.normalize_label("paragraph") == "text"

    def test_alias_image_to_figure(self, rule_set):
        assert rule_set.normalize_label("image") == "figure"

    def test_alias_equation_to_formula(self, rule_set):
        assert rule_set.normalize_label("equation") == "formula"

    def test_unknown_label_returns_lowercased_input(self, rule_set):
        assert rule_set.normalize_label("MyCustomBlock") == "mycustomblock"

    def test_already_canonical_label_unchanged(self, rule_set):
        assert rule_set.normalize_label("doc_title") == "doc_title"

    def test_uppercase_input_normalised(self, rule_set):
        assert rule_set.normalize_label("TITLE") == "doc_title"


# ─────────────────────────────────────────────────────────────────────────────
# 4. MappingRuleSet.apply() – rule matching
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleSetApply:
    def test_title_label_maps_to_Title(self, rule_set):
        role, rule_id = rule_set.apply("title")
        assert role == "Title"
        assert rule_id == "R001"

    def test_doc_title_label_maps_to_Title(self, rule_set):
        role, rule_id = rule_set.apply("doc_title")
        assert role == "Title"
        assert rule_id == "R001"

    def test_heading_maps_to_SectionHeading(self, rule_set):
        role, rule_id = rule_set.apply("heading")
        assert role == "SectionHeading"
        assert rule_id == "R002"

    def test_header_maps_to_PageHeader(self, rule_set):
        role, rule_id = rule_set.apply("header")
        assert role == "PageHeader"
        assert rule_id == "R003"

    def test_footer_maps_to_PageFooter(self, rule_set):
        role, rule_id = rule_set.apply("footer")
        assert role == "PageFooter"
        assert rule_id == "R004"

    def test_table_maps_to_Table(self, rule_set):
        role, rule_id = rule_set.apply("table")
        assert role == "Table"
        assert rule_id == "R005"

    def test_figure_maps_to_Figure(self, rule_set):
        role, rule_id = rule_set.apply("figure")
        assert role == "Figure"
        assert rule_id == "R006"

    def test_image_alias_maps_to_Figure(self, rule_set):
        role, rule_id = rule_set.apply("image")
        assert role == "Figure"
        assert rule_id == "R006"

    def test_figure_title_maps_to_Caption(self, rule_set):
        role, rule_id = rule_set.apply("figure_title")
        assert role == "Caption"
        assert rule_id == "R007"

    def test_table_title_maps_to_Caption(self, rule_set):
        role, rule_id = rule_set.apply("table_title")
        assert role == "Caption"
        assert rule_id == "R007"

    def test_formula_maps_to_Formula(self, rule_set):
        role, rule_id = rule_set.apply("formula")
        assert role == "Formula"
        assert rule_id == "R008"

    def test_equation_alias_maps_to_Formula(self, rule_set):
        role, rule_id = rule_set.apply("equation")
        assert role == "Formula"
        assert rule_id == "R008"

    def test_reference_maps_to_Reference(self, rule_set):
        role, rule_id = rule_set.apply("reference")
        assert role == "Reference"
        assert rule_id == "R009"

    def test_footnote_maps_to_Footnote(self, rule_set):
        role, rule_id = rule_set.apply("footnote")
        assert role == "Footnote"
        assert rule_id == "R010"

    def test_plain_text_maps_to_Paragraph(self, rule_set):
        role, rule_id = rule_set.apply("text")
        assert role == "Paragraph"
        assert rule_id == "R012"

    def test_paragraph_alias_maps_to_Paragraph(self, rule_set):
        role, rule_id = rule_set.apply("paragraph")
        assert role == "Paragraph"
        assert rule_id == "R012"

    def test_unknown_label_falls_back_to_default_role(self, rule_set):
        role, rule_id = rule_set.apply("banana")
        assert role == "Paragraph"   # default_role
        assert rule_id is None

    # ── Domain-specific R011 (invoice / KeyValuePair) ─────────────────────────

    def test_invoice_total_maps_to_KeyValuePair(self, rule_set):
        role, rule_id = rule_set.apply(
            "text",
            doc_type="invoice",
            content_text="Total: $1,200.00",
        )
        assert role == "KeyValuePair"
        assert rule_id == "R011"

    def test_receipt_tax_maps_to_KeyValuePair(self, rule_set):
        role, rule_id = rule_set.apply(
            "text",
            doc_type="receipt",
            content_text="Tax amount due: $50",
        )
        assert role == "KeyValuePair"
        assert rule_id == "R011"

    def test_invoice_no_regex(self, rule_set):
        role, _ = rule_set.apply(
            "text", doc_type="invoice", content_text="Invoice No: INV-2026-001"
        )
        assert role == "KeyValuePair"

    def test_invoice_without_matching_text_stays_Paragraph(self, rule_set):
        role, rule_id = rule_set.apply(
            "text",
            doc_type="invoice",
            content_text="Lorem ipsum dolor sit amet",
        )
        # R011 not triggered → falls through to R012 (Paragraph)
        assert role == "Paragraph"
        assert rule_id == "R012"

    def test_text_in_unknown_doc_type_stays_Paragraph(self, rule_set):
        role, _ = rule_set.apply(
            "text",
            doc_type="unknown",
            content_text="Total: $1,200.00",
        )
        # R011 requires doc_type_in: [invoice, receipt, contract]
        assert role == "Paragraph"

    # ── Confidence demotion ────────────────────────────────────────────────────

    def test_low_confidence_demoted_to_Unknown(self, rule_set):
        # confidence=0.1 < demote_if_below=0.2
        role, rule_id = rule_set.apply("title", confidence=0.1)
        assert role == "Unknown"
        assert rule_id is None

    def test_confidence_exactly_at_threshold_not_demoted(self, rule_set):
        # confidence=0.2 is NOT strictly less than 0.2 → rule fires normally
        role, rule_id = rule_set.apply("title", confidence=0.2)
        assert role == "Title"
        assert rule_id == "R001"

    def test_high_confidence_normal_mapping(self, rule_set):
        role, _ = rule_set.apply("table", confidence=0.95)
        assert role == "Table"


# ─────────────────────────────────────────────────────────────────────────────
# 5. MappingRuleSet.describe()
# ─────────────────────────────────────────────────────────────────────────────

class TestDescribe:
    def test_describe_returns_expected_keys(self, rule_set):
        info = rule_set.describe()
        assert "rule_count" in info
        assert "enabled_rules" in info
        assert "alias_count" in info
        assert "taxonomy_version" in info
        assert "mapping_version" in info

    def test_describe_counts_are_correct(self, rule_set):
        info = rule_set.describe()
        assert info["rule_count"] == 12
        assert info["enabled_rules"] == 12

    def test_describe_versions(self, rule_set):
        info = rule_set.describe()
        assert info["taxonomy_version"] == "azure-like-v1"
        assert info["mapping_version"] == "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Disabled rules are skipped
# ─────────────────────────────────────────────────────────────────────────────

class TestDisabledRules:
    def test_disabled_rule_skipped(self):
        yaml_text = """
config:
  default_role: Paragraph
normalize:
  raw_label_alias: {}
rules:
  - id: X001
    enabled: false
    priority: 1000
    when:
      raw_label_in: [doc_title]
    then:
      semantic_role: Title
  - id: X002
    enabled: true
    priority: 100
    when:
      raw_label_in: [doc_title]
    then:
      semantic_role: SectionHeading
"""
        rs = MappingRuleSet.from_yaml_string(yaml_text)
        role, rule_id = rs.apply("doc_title")
        # X001 disabled → X002 fires
        assert role == "SectionHeading"
        assert rule_id == "X002"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Base YAML file smoke tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBaseYamlSmoke:
    def test_base_yaml_title_mapping(self, base_rule_set):
        role, rid = base_rule_set.apply("title")
        assert role == "Title"
        assert rid == "R001"

    def test_base_yaml_paragraph_alias(self, base_rule_set):
        role, _ = base_rule_set.apply("paragraph")
        assert role == "Paragraph"

    def test_base_yaml_equation_alias(self, base_rule_set):
        role, _ = base_rule_set.apply("equation")
        assert role == "Formula"

    def test_base_yaml_number_alias(self, base_rule_set):
        """'number' should alias to 'footer' → PageFooter."""
        role, _ = base_rule_set.apply("number")
        assert role == "PageFooter"

    def test_base_yaml_header_image_alias(self, base_rule_set):
        """'header_image' should alias to 'header' → PageHeader."""
        role, _ = base_rule_set.apply("header_image")
        assert role == "PageHeader"

    def test_base_yaml_doc_index_alias(self, base_rule_set):
        """'doc_index' should alias to 'reference' → Reference."""
        role, _ = base_rule_set.apply("doc_index")
        assert role == "Reference"

    def test_base_yaml_chinese_invoice_kv(self, base_rule_set):
        role, _ = base_rule_set.apply(
            "text", doc_type="invoice", content_text="价税合计: ¥12,800"
        )
        assert role == "KeyValuePair"

    def test_base_yaml_contract_kv(self, base_rule_set):
        role, _ = base_rule_set.apply(
            "text", doc_type="contract", content_text="合同编号: CT-2026-001"
        )
        assert role == "KeyValuePair"
