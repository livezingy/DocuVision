"""字段值类型化转换器。

将字段文本按 Azure 字段语义转为 valueDate / valueNumber /
valueCurrency / valueAddress 等结构化值。失败统一返回 None，绝不编造。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app.services.kie.azure_schema import AddressValue, CurrencyValue

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%b-%Y",
    "%Y年%m月%d日",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%m/%d/%Y",
]

# 处理无前导 0 的日 / 月，例如 "19/2/2024"、"3/12/2024"
_DATE_SLASH_NO_PAD = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_DATE_DASH_NO_PAD = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")

_CURRENCY_SYMBOLS = {
    "£": "GBP",
    "$": "USD",
    "¥": "CNY",
    "€": "EUR",
    "￥": "CNY",
}
_CURRENCY_TEXT = re.compile(r"\b(GBP|USD|EUR|CNY|JPY|HKD|AUD|CAD)\b", re.IGNORECASE)
_NUMBER = re.compile(r"-?\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")


class ValueTyper:
    """字段值类型化静态方法集合。"""

    @staticmethod
    def to_date(content: str) -> Optional[str]:
        """日期归一化为 ISO 8601 (yyyy-mm-dd)。识别失败返回 None。"""
        if not content:
            return None
        s = content.strip()

        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                continue

        # 无前导 0 的日/月：默认按 d/m/y 解析（与 Azure 英国样本 19/2/2024 一致）
        m = _DATE_SLASH_NO_PAD.match(s) or _DATE_DASH_NO_PAD.match(s)
        if m:
            d, mo, y = m.groups()
            try:
                return datetime(int(y), int(mo), int(d)).date().isoformat()
            except ValueError:
                pass

        # 弱兜底：纯数字 yyyymmdd
        if re.fullmatch(r"\d{8}", s):
            try:
                return datetime.strptime(s, "%Y%m%d").date().isoformat()
            except ValueError:
                pass
        return None

    @staticmethod
    def to_number(content: str) -> Optional[float]:
        """从文本中抽出第一个数字（支持千分位、中文逗号）。"""
        if not content:
            return None
        m = _NUMBER.search(content)
        if not m:
            return None
        try:
            return float(m.group(0).replace(",", "").replace("，", ""))
        except ValueError:
            return None

    @staticmethod
    def to_currency(content: str) -> Optional[CurrencyValue]:
        """识别金额 + 币种，币种识别失败 currencyCode 留 None。"""
        if not content:
            return None
        amount = ValueTyper.to_number(content)
        if amount is None:
            return None

        code: Optional[str] = None
        for sym, c in _CURRENCY_SYMBOLS.items():
            if sym in content:
                code = c
                break
        if not code:
            text_match = _CURRENCY_TEXT.search(content)
            if text_match:
                code = text_match.group(1).upper()
        return CurrencyValue(amount=amount, currencyCode=code)

    @staticmethod
    def to_address(content: str) -> Optional[AddressValue]:
        """粗粒度地址切分。

        houseNumber / road / postalCode 等细子字段不在 Phase 1 范围内，
        统一保留为 None，避免编造。
        """
        if not content:
            return None
        parts = [p.strip() for p in re.split(r"[\n,]+", content) if p.strip()]
        if not parts:
            return None

        addr = AddressValue(
            streetAddress="\n".join(parts[:-1]) if len(parts) > 1 else parts[0]
        )
        tail = parts[-1]
        if re.search(r"(United Kingdom|United States|UK|USA|中国|China)", tail, re.IGNORECASE):
            addr.countryRegion = tail
            if len(parts) >= 2:
                addr.city = parts[-2]
        return addr


# 字段类型推断表（key = Azure 主名）
FIELD_TYPE_MAP = {
    # invoice
    "InvoiceId": "string",
    "InvoiceDate": "date",
    "DueDate": "date",
    "VendorName": "string",
    "VendorTaxId": "string",
    "CustomerName": "string",
    "CustomerId": "string",
    "CustomerAddress": "address",
    "PurchaseOrder": "string",
    "SubTotal": "currency",
    "TotalTax": "currency",
    "InvoiceTotal": "currency",
    "Description": "string",
    "Quantity": "number",
    "UnitPrice": "currency",
    "Amount": "currency",
    "TaxRate": "string",
    "Tax": "currency",
    "IBAN": "string",
    "SWIFT": "string",
    "AccountNumber": "string",
    # id_card
    "Name": "string",
    "IdNumber": "string",
    "DateOfBirth": "date",
    "Address": "address",
    "ExpirationDate": "date",
    "IssuingAuthority": "string",
    # receipt
    "MerchantName": "string",
    "TransactionDate": "date",
    "TransactionTime": "string",
    "Total": "currency",
    "Price": "currency",
    "PaymentMethod": "string",
}
