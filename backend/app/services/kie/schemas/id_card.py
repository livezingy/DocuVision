"""ID card (身份证 / 证件) UIE schema。"""

ID_CARD_SCHEMA = [
    "Name|姓名|Name|Full Name",
    "IdNumber|证件号码|身份证号|ID Number|ID No",
    "DateOfBirth|出生日期|Date of Birth|DOB",
    {
        "Address|住址|Address": [
            "Street|街道|Street",
            "City|城市|City",
        ]
    },
    "ExpirationDate|有效期|Expiration Date|Expiry Date",
    "IssuingAuthority|签发机关|Issuing Authority",
]
