"""
Semantic Role Definitions for Canonical Document Contract

Defines the Azure-like semantic taxonomy for document block roles.
Roles are assigned by the SemanticMapper based on configurable YAML rules
(backend/config/semantic_mapping_base.yaml).

Taxonomy version: azure-like-v1
"""

from enum import Enum
from typing import List, Optional


__all__ = ["SemanticRole"]


class SemanticRole(str, Enum):
    """
    Semantic roles for document blocks, aligned with Azure Document Intelligence
    and extended for domain-specific use cases.

    Intended usage:
        block.semantic_role = SemanticRole.TITLE.value   # stores "Title"
        SemanticRole.from_str("title")                   # -> SemanticRole.TITLE

    The enum inherits from str so instances serialise to plain strings in JSON
    without custom encoder logic.
    """

    # ── Structural roles ──────────────────────────────────────────────────────
    TITLE = "Title"
    "Document-level title (maps from doc_title, title labels)."

    SECTION_HEADING = "SectionHeading"
    "Section or chapter heading (maps from paragraph_title, heading labels)."

    PARAGRAPH = "Paragraph"
    "Generic body text block. Default fallback role."

    # ── Layout / navigational roles ───────────────────────────────────────────
    PAGE_HEADER = "PageHeader"
    "Running header region at the top of a page."

    PAGE_FOOTER = "PageFooter"
    "Running footer region at the bottom of a page."

    # ── Content-type roles ────────────────────────────────────────────────────
    TABLE = "Table"
    "Tabular data block, including the table HTML representation."

    FIGURE = "Figure"
    "Image, chart, diagram, or other visual element."

    CAPTION = "Caption"
    "Figure caption or table caption text."

    FORMULA = "Formula"
    "Mathematical or chemical formula."

    FOOTNOTE = "Footnote"
    "Footnote text, typically at the bottom of a page."

    REFERENCE = "Reference"
    "Bibliographic reference or citation block."

    # ── Domain-specific roles (invoice / receipt / contract) ──────────────────
    KEY_VALUE_PAIR = "KeyValuePair"
    "Key-value pair pattern, e.g. 'Invoice No: 12345', 'Total: $99.00'."

    # ── Fallback ──────────────────────────────────────────────────────────────
    UNKNOWN = "Unknown"
    "Role could not be determined from available rules."

    # ── Helpers ───────────────────────────────────────────────────────────────

    @classmethod
    def values(cls) -> List[str]:
        """Return a list of all role string values."""
        return [r.value for r in cls]

    @classmethod
    def from_str(cls, value: str, default: Optional["SemanticRole"] = None) -> "SemanticRole":
        """
        Case-insensitive lookup by value string.

        Args:
            value:   String to look up (e.g. "title", "Table", "PARAGRAPH").
            default: Returned when no match found. Defaults to SemanticRole.UNKNOWN.

        Returns:
            Matching SemanticRole enum member.
        """
        normalized = value.strip().lower()
        for role in cls:
            if role.value.lower() == normalized:
                return role
        return default if default is not None else cls.UNKNOWN

    @classmethod
    def structural_roles(cls) -> List["SemanticRole"]:
        """Roles that represent document structure hierarchy."""
        return [cls.TITLE, cls.SECTION_HEADING, cls.PARAGRAPH]

    @classmethod
    def layout_roles(cls) -> List["SemanticRole"]:
        """Roles that represent page-layout positions."""
        return [cls.PAGE_HEADER, cls.PAGE_FOOTER]

    @classmethod
    def content_roles(cls) -> List["SemanticRole"]:
        """Roles that represent content types."""
        return [cls.TABLE, cls.FIGURE, cls.CAPTION, cls.FORMULA, cls.FOOTNOTE, cls.REFERENCE]

    @classmethod
    def domain_roles(cls) -> List["SemanticRole"]:
        """Roles used for domain-specific document types."""
        return [cls.KEY_VALUE_PAIR]

    def is_text_like(self) -> bool:
        """Return True if this role produces inline-readable text content."""
        return self in (
            self.TITLE,
            self.SECTION_HEADING,
            self.PARAGRAPH,
            self.CAPTION,
            self.FOOTNOTE,
            self.REFERENCE,
            self.KEY_VALUE_PAIR,
        )
