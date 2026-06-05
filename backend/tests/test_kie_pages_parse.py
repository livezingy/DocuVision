"""Phase A tests for KIE page selection (no GPU)."""

from app.services.kie.kie_pages import (
    parse_pages_spec,
    resolve_kie_pages,
    validate_kie_pages_for_non_pdf,
)


def test_parse_pages_default_empty_is_page_one() -> None:
    assert parse_pages_spec(None, 5) == [1]
    assert parse_pages_spec("", 5) == [1]


def test_parse_pages_all() -> None:
    assert parse_pages_spec("all", 4) == [1, 2, 3, 4]


def test_parse_pages_range() -> None:
    assert parse_pages_spec("2-4", 6) == [2, 3, 4]


def test_resolve_kie_pages_truncates() -> None:
    pages, truncated = resolve_kie_pages("all", 10, max_pages=3)
    assert pages == [1, 2, 3]
    assert truncated is True


def test_validate_kie_pages_non_pdf() -> None:
    assert validate_kie_pages_for_non_pdf(None, False) is None
    assert validate_kie_pages_for_non_pdf("all", False) is not None
    assert validate_kie_pages_for_non_pdf("all", True) is None
    assert validate_kie_pages_for_non_pdf("all", False, enable_kie=False) is None
