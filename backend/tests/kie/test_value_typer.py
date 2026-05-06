"""ValueTyper 单测：覆盖 Azure 标准样本中所有日期/币种格式。"""

import pytest

from app.services.kie.azure_schema import AddressValue, CurrencyValue
from app.services.kie.value_typer import ValueTyper


class TestToDate:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2024-02-19", "2024-02-19"),
            ("19/2/2024", "2024-02-19"),
            ("19/02/2024", "2024-02-19"),
            ("2024/02/19", "2024-02-19"),
            ("19-Feb-2024", "2024-02-19"),
            ("19 Feb 2024", "2024-02-19"),
            ("19 February 2024", "2024-02-19"),
            ("2024年2月19日", "2024-02-19"),
            ("2024.02.19", "2024-02-19"),
            ("19.02.2024", "2024-02-19"),
            ("20240219", "2024-02-19"),
        ],
    )
    def test_normalizes_to_iso(self, raw, expected):
        assert ValueTyper.to_date(raw) == expected

    @pytest.mark.parametrize("bad", ["", None, "not-a-date", "2024/13/45"])
    def test_returns_none_for_invalid(self, bad):
        assert ValueTyper.to_date(bad) is None


class TestToNumber:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("180.00", 180.0),
            ("100", 100.0),
            ("1,024.50", 1024.5),
            ("1，024.50", 1024.5),  # 中文逗号
            ("Total: 180.00 GBP", 180.0),
            ("-12.5", -12.5),
        ],
    )
    def test_extracts_first_number(self, raw, expected):
        assert ValueTyper.to_number(raw) == expected

    def test_returns_none_for_empty(self):
        assert ValueTyper.to_number("") is None
        assert ValueTyper.to_number("no digits here") is None


class TestToCurrency:
    @pytest.mark.parametrize(
        "raw,amount,code",
        [
            ("180.00 GBP", 180.0, "GBP"),
            ("GBP 180.00", 180.0, "GBP"),
            ("£100", 100.0, "GBP"),
            ("$1,024.50", 1024.5, "USD"),
            ("¥250", 250.0, "CNY"),
            ("€99.99", 99.99, "EUR"),
            ("180.00", 180.0, None),  # 无币种符号
        ],
    )
    def test_currency_value(self, raw, amount, code):
        cv = ValueTyper.to_currency(raw)
        assert isinstance(cv, CurrencyValue)
        assert cv.amount == amount
        assert cv.currencyCode == code

    def test_returns_none_when_no_amount(self):
        assert ValueTyper.to_currency("GBP only") is None
        assert ValueTyper.to_currency("") is None


class TestToAddress:
    def test_basic_split(self):
        addr = ValueTyper.to_address("PO Box 1, 2 Kingdom Street, London, United Kingdom")
        assert isinstance(addr, AddressValue)
        assert addr.streetAddress is not None
        assert "United Kingdom" in (addr.countryRegion or "")
        assert addr.city == "London"

    def test_returns_none_for_empty(self):
        assert ValueTyper.to_address("") is None
        assert ValueTyper.to_address("   ") is None

    def test_no_country_keeps_country_none(self):
        addr = ValueTyper.to_address("123 Main St")
        assert isinstance(addr, AddressValue)
        assert addr.countryRegion is None
