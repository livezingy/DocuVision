"""Invoice (发票) UIE schema，对齐 Azure prebuilt-invoice 字段。

字段命名约定：'AzureName|中文别名|英文别名1|英文别名2'。
嵌套字段（Items / PaymentDetails / CustomerAddress）使用 dict + 子 schema。
"""

INVOICE_SCHEMA = [
    "InvoiceId|发票号码|发票号|Invoice No|Invoice Number",
    "InvoiceDate|开票日期|发票日期|Invoice Date",
    "DueDate|到期日|付款到期日|Payment Due|Due Date",
    "VendorName|供应商|开票方|Vendor|Vendor Name",
    "VendorTaxId|供应商税号|VAT Registration No|Tax ID",
    "CustomerName|客户名称|购方|Customer Name|Bill To",
    "CustomerId|客户编号|Customer ID",
    {
        "CustomerAddress|客户地址|Bill To Address": [
            "Street|街道|Address",
            "City|城市|City",
            "PostalCode|邮编|Postal Code|ZIP",
            "Country|国家|Country",
        ]
    },
    "PurchaseOrder|采购订单号|Purchase Order|PO Number",
    "SubTotal|小计|Sub Total",
    "TotalTax|总税额|VAT|Tax",
    "InvoiceTotal|应付总额|总金额|Total|Amount Due",
    {
        "Items|商品行|发票明细": [
            "Description|品名|描述|Description|Item",
            "Quantity|数量|Qty|Quantity",
            "UnitPrice|单价|Unit Price",
            "Amount|金额|Amount",
            "TaxRate|税率|Tax Rate|VAT %",
            "Tax|税额|VAT Amount",
        ]
    },
    {
        "PaymentDetails|付款信息": [
            "IBAN|国际银行账号",
            "SWIFT|SWIFT 代码|SWIFT Code",
            "AccountNumber|账户号码|Account No",
        ]
    },
]
