"""Tests for KIE schema templates."""

from app.services.kie.schema_templates import list_templates, load_template


def test_list_templates_includes_bank_statement() -> None:
    names = list_templates()
    assert "bank_statement" in names


def test_load_bank_statement_template() -> None:
    schema = load_template("bank_statement")
    assert schema is not None
    assert schema.get("name") == "bank_statement"
    assert isinstance(schema.get("fields"), list)
