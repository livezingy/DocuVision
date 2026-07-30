"""Tests for KIE schema templates."""

import pytest

from app.services.kie.schema_templates import (
    list_templates,
    load_template,
    save_template,
)


def test_list_templates_includes_bank_statement() -> None:
    names = list_templates()
    assert "bank_statement" in names


def test_load_bank_statement_template() -> None:
    schema = load_template("bank_statement")
    assert schema is not None
    assert schema.get("name") == "bank_statement"
    assert isinstance(schema.get("fields"), list)


@pytest.mark.parametrize(
    "bad_id",
    ["../escape", "..\\escape", "/abs/path", "a/b", "a\\b", "..", ".", "", "  "],
)
def test_load_template_rejects_path_traversal(bad_id) -> None:
    # Path-traversal / unsafe ids must return None (load) instead of reading
    # outside the template directory.
    assert load_template(bad_id) is None


def test_save_template_rejects_path_traversal() -> None:
    with pytest.raises(ValueError):
        save_template("../evil", {"name": "evil"})


def test_save_template_rejects_empty_id() -> None:
    with pytest.raises(ValueError):
        save_template("   ", {"name": "x"})
