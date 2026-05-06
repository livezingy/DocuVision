"""Receipt (小票 / 收据) UIE schema。"""

RECEIPT_SCHEMA = [
    "MerchantName|商户名称|店铺名|Merchant|Merchant Name",
    "TransactionDate|交易日期|日期|Date",
    "TransactionTime|交易时间|时间|Time",
    "Total|总计|合计|Total|Total Amount",
    "TotalTax|税额|Tax",
    {
        "Items|商品": [
            "Description|品名|Description|Item",
            "Quantity|数量|Quantity",
            "Price|价格|Price|Unit Price",
        ]
    },
    "PaymentMethod|支付方式|Payment Method",
]
