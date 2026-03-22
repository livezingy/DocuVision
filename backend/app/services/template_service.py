"""
Template Service - Document Template Matching and Field Extraction
Supports preset templates (Invoice, Receipt, ID Card, etc.) and custom templates
"""

from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
from loguru import logger
import re
import json
import os
from datetime import datetime


class TemplateField:
    """Definition of a template field"""
    
    def __init__(
        self,
        name: str,
        label: str,
        field_type: str = "text",
        required: bool = False,
        patterns: Optional[List[str]] = None,
        validators: Optional[List[str]] = None,
        description: str = ""
    ):
        self.name = name
        self.label = label
        self.field_type = field_type  # text, number, date, money, email, phone, etc.
        self.required = required
        self.patterns = patterns or []
        self.validators = validators or []
        self.description = description
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "field_type": self.field_type,
            "required": self.required,
            "patterns": self.patterns,
            "validators": self.validators,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateField":
        return cls(
            name=data["name"],
            label=data["label"],
            field_type=data.get("field_type", "text"),
            required=data.get("required", False),
            patterns=data.get("patterns", []),
            validators=data.get("validators", []),
            description=data.get("description", "")
        )


class DocumentTemplate:
    """Document Template Definition"""
    
    def __init__(
        self,
        template_id: str,
        name: str,
        description: str,
        category: str,
        fields: List[TemplateField],
        keywords: Optional[List[str]] = None,
        layout_hints: Optional[Dict[str, Any]] = None,
        is_preset: bool = False
    ):
        self.template_id = template_id
        self.name = name
        self.description = description
        self.category = category
        self.fields = fields
        self.keywords = keywords or []
        self.layout_hints = layout_hints or {}
        self.is_preset = is_preset
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "fields": [f.to_dict() for f in self.fields],
            "keywords": self.keywords,
            "layout_hints": self.layout_hints,
            "is_preset": self.is_preset,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentTemplate":
        fields = [TemplateField.from_dict(f) for f in data.get("fields", [])]
        template = cls(
            template_id=data["template_id"],
            name=data["name"],
            description=data.get("description", ""),
            category=data.get("category", "custom"),
            fields=fields,
            keywords=data.get("keywords", []),
            layout_hints=data.get("layout_hints", {}),
            is_preset=data.get("is_preset", False)
        )
        if "created_at" in data:
            template.created_at = data["created_at"]
        return template


class FieldExtractor:
    """Field value extractor using patterns and rules"""
    
    # Common patterns for different field types
    PATTERNS = {
        "date": [
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}',
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}'
        ],
        "money": [
            r'[\$€£¥]\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*(?:dollars?|USD|EUR|GBP|CNY|RMB|元|美元)',
            r'(?:Total|Amount|Price|Cost|Fee)[\s:]*[\$€£¥]?\s*[\d,]+\.?\d*'
        ],
        "email": [
            r'[\w\.-]+@[\w\.-]+\.\w+'
        ],
        "phone": [
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\d{3,4}[-\s]?\d{7,8}',
            r'1[3-9]\d{9}'  # Chinese mobile
        ],
        "invoice_number": [
            r'(?:Invoice|INV|Bill)[\s#:No.]*([A-Z0-9-]+)',
            r'发票号[码]?[\s:：]*([A-Z0-9-]+)',
            r'(?:No|Number|#)[\s.:]*([A-Z0-9-]+)'
        ],
        "id_number": [
            r'\d{17}[\dXx]',  # Chinese ID
            r'[A-Z]{1,2}\d{6,9}',  # Passport style
            r'\d{3}-\d{2}-\d{4}'  # SSN style
        ],
        "percentage": [
            r'[\d.]+\s*%',
            r'[\d.]+\s*(?:percent|百分之)'
        ],
        "quantity": [
            r'\d+\s*(?:pcs|pieces|units|个|件|套)',
            r'(?:Qty|Quantity)[\s:]*\d+'
        ]
    }
    
    @classmethod
    def extract_by_pattern(cls, text: str, field_type: str, custom_patterns: List[str] = None) -> List[str]:
        """Extract values using patterns"""
        patterns = custom_patterns or cls.PATTERNS.get(field_type, [])
        
        results = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            results.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for r in results:
            if r not in seen:
                seen.add(r)
                unique_results.append(r)
        
        return unique_results
    
    @classmethod
    def extract_by_label(cls, text: str, label: str, context_words: int = 5) -> List[str]:
        """Extract value following a label"""
        # Pattern: label followed by separator and value
        patterns = [
            rf'{label}[\s:：]+([^\n]+)',
            rf'{label}[\s]*[=][\s]*([^\n]+)',
        ]
        
        results = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            results.extend([m.strip() for m in matches])
        
        return results
    
    @classmethod
    def extract_from_table(cls, tables: List[Dict], field_name: str, possible_labels: List[str]) -> Optional[str]:
        """Extract value from table data"""
        for table in tables:
            data = table.get("data", [])
            
            for row in data:
                for i, cell in enumerate(row):
                    cell_text = str(cell).lower().strip()
                    
                    for label in possible_labels:
                        if label.lower() in cell_text:
                            # Return next cell value
                            if i + 1 < len(row):
                                return str(row[i + 1]).strip()
        
        return None


class TemplateService:
    """
    Template Service for document field extraction
    
    Features:
    - Preset templates (Invoice, Receipt, ID Card, Business Card)
    - Custom template creation
    - Pattern-based field extraction
    - Template matching and scoring
    """
    
    def __init__(self, templates_dir: str = "./templates"):
        self.templates_dir = templates_dir
        self.templates: Dict[str, DocumentTemplate] = {}
        self._load_preset_templates()
        self._load_custom_templates()
    
    def _load_preset_templates(self):
        """Load preset document templates - Enhanced with Azure DI standard fields"""
        
        # Invoice Template - Azure DI Prebuilt Model Compatible
        invoice_template = DocumentTemplate(
            template_id="invoice",
            name="Invoice",
            description="Extract invoice information compatible with Azure Document Intelligence Invoice model",
            category="financial",
            fields=[
                # Core Invoice Fields (Azure DI Standard)
                TemplateField("invoice_id", "Invoice ID", "invoice_number", True,
                             patterns=[
                                 r'(?:Invoice|INV|Bill|Invoice\s*No\.?)[\s#:：]*([A-Z0-9-]+)',
                                 r'发票号[码]?[\s:：]*([A-Z0-9-]+)',
                                 r'(?:No\.?|Number|#)[\s.:：]*([A-Z0-9-]+)',
                                 r'INV[\s-]*([A-Z0-9-]+)'
                             ],
                             description="Unique invoice identifier"),
                TemplateField("invoice_date", "Invoice Date", "date", True,
                             patterns=[
                                 r'(?:Invoice\s*Date|Date|Date\s*of\s*Invoice)[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'发票日期[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
                             ],
                             description="Date when invoice was issued"),
                TemplateField("due_date", "Due Date", "date", False,
                             patterns=[
                                 r'(?:Due\s*Date|Payment\s*Due|Due\s*By)[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'到期日[期]?[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'付款期限[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)'
                             ],
                             description="Date when payment is due"),
                
                # Vendor Information (Seller)
                TemplateField("vendor_name", "Vendor Name", "text", False,
                             patterns=[
                                 r'(?:Vendor|Seller|From|Bill\s*From|Supplier)[\s:：]*([^\n]+)',
                                 r'供应商[\s:：]*([^\n]+)',
                                 r'销售方[\s:：]*([^\n]+)'
                             ],
                             description="Name of the vendor/seller"),
                TemplateField("vendor_address", "Vendor Address", "text", False,
                             patterns=[
                                 r'(?:Vendor\s*Address|Seller\s*Address|From\s*Address)[\s:：]*([^\n]+)',
                                 r'供应商地址[\s:：]*([^\n]+)'
                             ],
                             description="Vendor physical address"),
                TemplateField("vendor_address_recipient", "Vendor Address Recipient", "text", False,
                             description="Recipient name at vendor address"),
                TemplateField("vendor_tax_id", "Vendor Tax ID", "text", False,
                             patterns=[
                                 r'(?:Tax\s*ID|VAT\s*No|Tax\s*Number|EIN)[\s:：]*([A-Z0-9-]+)',
                                 r'税号[\s:：]*([A-Z0-9-]+)',
                                 r'统一社会信用代码[\s:：]*([A-Z0-9]+)'
                             ],
                             description="Vendor tax identification number"),
                
                # Customer Information (Buyer)
                TemplateField("customer_name", "Customer Name", "text", False,
                             patterns=[
                                 r'(?:Customer|Buyer|Bill\s*To|Ship\s*To|Client)[\s:：]*([^\n]+)',
                                 r'客户[\s:：]*([^\n]+)',
                                 r'购买方[\s:：]*([^\n]+)'
                             ],
                             description="Name of the customer/buyer"),
                TemplateField("customer_address", "Customer Address", "text", False,
                             patterns=[
                                 r'(?:Customer\s*Address|Buyer\s*Address|Bill\s*To\s*Address)[\s:：]*([^\n]+)',
                                 r'客户地址[\s:：]*([^\n]+)'
                             ],
                             description="Customer physical address"),
                TemplateField("customer_address_recipient", "Customer Address Recipient", "text", False,
                             description="Recipient name at customer address"),
                TemplateField("customer_tax_id", "Customer Tax ID", "text", False,
                             patterns=[
                                 r'(?:Customer\s*Tax\s*ID|Buyer\s*Tax\s*ID)[\s:：]*([A-Z0-9-]+)',
                                 r'客户税号[\s:：]*([A-Z0-9-]+)'
                             ],
                             description="Customer tax identification number"),
                
                # Financial Fields
                TemplateField("subtotal", "Subtotal", "money", False,
                             patterns=[
                                 r'(?:Subtotal|Sub\s*Total|小计)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'(?:Subtotal|小计)[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Subtotal amount before tax"),
                TemplateField("total_tax", "Total Tax", "money", False,
                             patterns=[
                                 r'(?:Total\s*Tax|Tax\s*Total|Tax\s*Amount|税额)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'税额[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Total tax amount"),
                TemplateField("invoice_total", "Invoice Total", "money", True,
                             patterns=[
                                 r'(?:Total|Invoice\s*Total|Amount\s*Due|Grand\s*Total|总计)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'总计[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?',
                                 r'应付总额[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Total amount due"),
                TemplateField("amount_due", "Amount Due", "money", False,
                             patterns=[
                                 r'(?:Amount\s*Due|Due\s*Amount|Balance\s*Due)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'应付金额[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Amount currently due"),
                TemplateField("previous_unpaid_balance", "Previous Unpaid Balance", "money", False,
                             description="Previous unpaid balance"),
                
                # Additional Fields
                TemplateField("remittance_address", "Remittance Address", "text", False,
                             description="Address for remittance/payment"),
                TemplateField("billing_address", "Billing Address", "text", False,
                             description="Billing address"),
                TemplateField("shipping_address", "Shipping Address", "text", False,
                             description="Shipping/delivery address"),
                TemplateField("purchase_order", "Purchase Order", "text", False,
                             patterns=[
                                 r'(?:PO|P\.O\.|Purchase\s*Order)[\s#:：]*([A-Z0-9-]+)',
                                 r'采购订单[\s:：]*([A-Z0-9-]+)'
                             ],
                             description="Purchase order number"),
                TemplateField("currency", "Currency", "text", False,
                             patterns=[
                                 r'[\$€£¥]|USD|EUR|GBP|CNY|RMB|JPY'
                             ],
                             description="Currency code"),
            ],
            keywords=["invoice", "bill", "invoice number", "invoice date", "total", "amount", "due", 
                     "payment", "tax", "vendor", "customer", "发票", "账单", "发票号", "发票日期"],
            layout_hints={
                "vendor_section": "top_left",
                "customer_section": "top_right",
                "items_section": "middle",
                "totals_section": "bottom_right"
            },
            is_preset=True
        )
        self.templates["invoice"] = invoice_template
        
        # Receipt Template - Azure DI Prebuilt Model Compatible
        receipt_template = DocumentTemplate(
            template_id="receipt",
            name="Receipt",
            description="Extract receipt information compatible with Azure Document Intelligence Receipt model",
            category="financial",
            fields=[
                # Merchant Information
                TemplateField("merchant_name", "Merchant Name", "text", True,
                             patterns=[
                                 r'(?:Merchant|Store|Business|Company)[\s:：]*([^\n]+)',
                                 r'商户[\s:：]*([^\n]+)',
                                 r'商店[\s:：]*([^\n]+)'
                             ],
                             description="Name of the merchant/store"),
                TemplateField("merchant_address", "Merchant Address", "text", False,
                             patterns=[
                                 r'(?:Address|Location)[\s:：]*([^\n]+)',
                                 r'地址[\s:：]*([^\n]+)'
                             ],
                             description="Merchant physical address"),
                TemplateField("merchant_phone_number", "Merchant Phone Number", "phone", False,
                             patterns=[
                                 r'(?:Phone|Tel|Contact)[\s:：]*([+\d\s\-()]+)',
                                 r'电话[\s:：]*([+\d\s\-()]+)',
                                 r'联系电话[\s:：]*([+\d\s\-()]+)'
                             ],
                             description="Merchant contact phone number"),
                
                # Transaction Information
                TemplateField("transaction_date", "Transaction Date", "date", True,
                             patterns=[
                                 r'(?:Date|Transaction\s*Date|Purchase\s*Date)[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'日期[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
                             ],
                             description="Date of the transaction"),
                TemplateField("transaction_time", "Transaction Time", "text", False,
                             patterns=[
                                 r'(?:Time|Transaction\s*Time)[\s:：]*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)',
                                 r'时间[\s:：]*(\d{1,2}:\d{2}(?::\d{2})?)',
                                 r'(\d{1,2}:\d{2}(?::\d{2})?)'
                             ],
                             description="Time of the transaction"),
                
                # Financial Fields
                TemplateField("subtotal", "Subtotal", "money", False,
                             patterns=[
                                 r'(?:Subtotal|Sub\s*Total|小计)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'小计[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Subtotal amount before tax"),
                TemplateField("tax", "Tax", "money", False,
                             patterns=[
                                 r'(?:Tax|Sales\s*Tax|VAT|税额)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'税额[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?',
                                 r'税[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Tax amount"),
                TemplateField("total", "Total", "money", True,
                             patterns=[
                                 r'(?:Total|Amount|Grand\s*Total|总计)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'总计[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?',
                                 r'合计[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Total amount"),
                TemplateField("tip", "Tip", "money", False,
                             patterns=[
                                 r'(?:Tip|Gratuity|小费)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'小费[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Tip amount"),
                
                # Payment Information
                TemplateField("payment_method", "Payment Method", "text", False,
                             patterns=[
                                 r'(?:Payment\s*Method|Paid\s*By|Payment)[\s:：]*([^\n]+)',
                                 r'支付方式[\s:：]*([^\n]+)',
                                 r'(?:Cash|Card|Credit|Debit|Check|Check|支付宝|微信|Alipay|WeChat)'
                             ],
                             description="Payment method used"),
                TemplateField("card_type", "Card Type", "text", False,
                             patterns=[
                                 r'(?:Visa|MasterCard|American\s*Express|Amex|Discover|银联|UnionPay)'
                             ],
                             description="Type of card used"),
                TemplateField("card_last_four", "Card Last 4 Digits", "text", False,
                             patterns=[
                                 r'(?:Card|Card\s*#|Card\s*Number)[\s:：]*.*?(\d{4})',
                                 r'卡号.*?(\d{4})',
                                 r'\*\*\*\*\s*(\d{4})'
                             ],
                             description="Last 4 digits of payment card"),
                TemplateField("change", "Change", "money", False,
                             patterns=[
                                 r'(?:Change|Change\s*Due|找零)[\s:：]*[\$€£¥]?\s*([\d,]+\.?\d*)',
                                 r'找零[\s:：]*([\d,]+\.?\d*)\s*(?:元|USD|EUR|GBP)?'
                             ],
                             description="Change amount returned"),
                
                # Additional Fields
                TemplateField("receipt_number", "Receipt Number", "text", False,
                             patterns=[
                                 r'(?:Receipt\s*#|Receipt\s*No|Receipt\s*Number|Receipt\s*ID)[\s:：]*([A-Z0-9-]+)',
                                 r'收据号[\s:：]*([A-Z0-9-]+)'
                             ],
                             description="Receipt identifier"),
                TemplateField("transaction_id", "Transaction ID", "text", False,
                             patterns=[
                                 r'(?:Transaction\s*ID|Txn\s*ID|Transaction\s*#)[\s:：]*([A-Z0-9-]+)',
                                 r'交易号[\s:：]*([A-Z0-9-]+)'
                             ],
                             description="Transaction identifier"),
            ],
            keywords=["receipt", "total", "subtotal", "tax", "cash", "card", "change", "merchant", 
                     "transaction", "payment", "收据", "小票", "总计", "支付"],
            layout_hints={
                "merchant_section": "top",
                "items_section": "middle",
                "totals_section": "bottom",
                "payment_section": "bottom"
            },
            is_preset=True
        )
        self.templates["receipt"] = receipt_template
        
        # ID Document Template - Azure DI Prebuilt Model Compatible
        id_card_template = DocumentTemplate(
            template_id="id_document",
            name="ID Document",
            description="Extract identity document information compatible with Azure Document Intelligence ID Document model",
            category="identity",
            fields=[
                # Document Type
                TemplateField("document_type", "Document Type", "text", False,
                             patterns=[
                                 r'(?:Passport|Driver\'?s?\s*License|ID\s*Card|Identity\s*Card|National\s*ID)',
                                 r'(?:护照|身份证|驾照|驾驶证|居民身份证)'
                             ],
                             description="Type of identity document"),
                
                # Personal Information
                TemplateField("first_name", "First Name", "text", False,
                             patterns=[
                                 r'(?:First\s*Name|Given\s*Name|名)[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'名[\s:：]*([A-Za-z\u4e00-\u9fff]+)'
                             ],
                             description="First/given name"),
                TemplateField("last_name", "Last Name", "text", False,
                             patterns=[
                                 r'(?:Last\s*Name|Family\s*Name|Surname|姓)[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'姓[\s:：]*([A-Za-z\u4e00-\u9fff]+)'
                             ],
                             description="Last/family name"),
                TemplateField("full_name", "Full Name", "text", True,
                             patterns=[
                                 r'(?:Full\s*Name|Name|姓名)[\s:：]*([A-Za-z\s\u4e00-\u9fff]+)',
                                 r'姓名[\s:：]*([A-Za-z\s\u4e00-\u9fff]+)',
                                 r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Western name pattern
                                 r'([\u4e00-\u9fff]{2,4})'  # Chinese name pattern
                             ],
                             description="Full name of the person"),
                TemplateField("date_of_birth", "Date of Birth", "date", True,
                             patterns=[
                                 r'(?:Date\s*of\s*Birth|DOB|Birth\s*Date|出生日期|生日)[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'出生日期[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})'
                             ],
                             description="Date of birth"),
                TemplateField("sex", "Sex", "text", False,
                             patterns=[
                                 r'(?:Sex|Gender|性别)[\s:：]*(?:M|F|Male|Female|男|女)',
                                 r'性别[\s:：]*(男|女)',
                                 r'(?:M|F|Male|Female)'
                             ],
                             description="Sex/Gender"),
                
                # Address Information
                TemplateField("address", "Address", "text", False,
                             patterns=[
                                 r'(?:Address|Residence|住址|地址)[\s:：]*([^\n]+)',
                                 r'住址[\s:：]*([^\n]+)',
                                 r'地址[\s:：]*([^\n]+)'
                             ],
                             description="Residential address"),
                TemplateField("country_region", "Country/Region", "text", False,
                             patterns=[
                                 r'(?:Country|Nationality|Country\s*Region|国家|国籍)[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'国家[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'国籍[\s:：]*([A-Za-z\u4e00-\u9fff]+)'
                             ],
                             description="Country or region"),
                TemplateField("region", "Region", "text", False,
                             patterns=[
                                 r'(?:Region|State|Province|省|州)[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'省[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'州[\s:：]*([A-Za-z\u4e00-\u9fff]+)'
                             ],
                             description="Region/State/Province"),
                TemplateField("nationality", "Nationality", "text", False,
                             patterns=[
                                 r'(?:Nationality|国籍)[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'国籍[\s:：]*([A-Za-z\u4e00-\u9fff]+)'
                             ],
                             description="Nationality"),
                
                # Document Information
                TemplateField("document_number", "Document Number", "id_number", True,
                             patterns=[
                                 r'(?:Document\s*Number|ID\s*Number|Passport\s*No|License\s*Number|证件号码|身份证号)[\s:：]*([A-Z0-9-]+)',
                                 r'身份证号[\s:：]*([\dXx]{15,18})',
                                 r'证件号码[\s:：]*([A-Z0-9-]+)',
                                 r'(\d{17}[\dXx])',  # Chinese ID
                                 r'([A-Z]{1,2}\d{6,9})',  # Passport style
                                 r'(\d{3}-\d{2}-\d{4})'  # SSN style
                             ],
                             description="Document identification number"),
                TemplateField("date_of_expiration", "Date of Expiration", "date", False,
                             patterns=[
                                 r'(?:Expiration\s*Date|Expiry\s*Date|Valid\s*Until|到期日期|有效期至)[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'到期日期[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'有效期至[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)'
                             ],
                             description="Document expiration date"),
                TemplateField("date_of_issue", "Date of Issue", "date", False,
                             patterns=[
                                 r'(?:Issue\s*Date|Date\s*of\s*Issue|Issued\s*Date|签发日期)[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
                                 r'签发日期[\s:：]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)'
                             ],
                             description="Date when document was issued"),
                TemplateField("issuing_authority", "Issuing Authority", "text", False,
                             patterns=[
                                 r'(?:Issuing\s*Authority|Issued\s*By|Authority|签发机关)[\s:：]*([^\n]+)',
                                 r'签发机关[\s:：]*([^\n]+)'
                             ],
                             description="Authority that issued the document"),
                TemplateField("issuing_country", "Issuing Country", "text", False,
                             patterns=[
                                 r'(?:Issuing\s*Country|Country\s*of\s*Issue|签发国家)[\s:：]*([A-Za-z\u4e00-\u9fff]+)',
                                 r'签发国家[\s:：]*([A-Za-z\u4e00-\u9fff]+)'
                             ],
                             description="Country that issued the document"),
                
                # Additional Fields
                TemplateField("personal_number", "Personal Number", "text", False,
                             patterns=[
                                 r'(?:Personal\s*Number|Personal\s*ID|个人编号)[\s:：]*([A-Z0-9-]+)',
                                 r'个人编号[\s:：]*([A-Z0-9-]+)'
                             ],
                             description="Personal identification number"),
                TemplateField("place_of_birth", "Place of Birth", "text", False,
                             patterns=[
                                 r'(?:Place\s*of\s*Birth|Birth\s*Place|出生地)[\s:：]*([^\n]+)',
                                 r'出生地[\s:：]*([^\n]+)'
                             ],
                             description="Place of birth"),
            ],
            keywords=["id", "identity", "card", "passport", "license", "document", "name", "birth", 
                     "address", "number", "身份证", "护照", "驾照", "证件"],
            layout_hints={
                "photo_section": "left",
                "personal_info_section": "right",
                "document_info_section": "bottom"
            },
            is_preset=True
        )
        self.templates["id_document"] = id_card_template
        # Keep backward compatibility
        self.templates["id_card"] = id_card_template
        
        # Business Card Template
        business_card_template = DocumentTemplate(
            template_id="business_card",
            name="Business Card",
            description="Extract contact information from business cards",
            category="contact",
            fields=[
                TemplateField("name", "Name", "text", True),
                TemplateField("title", "Job Title", "text", False),
                TemplateField("company", "Company", "text", False),
                TemplateField("email", "Email", "email", False),
                TemplateField("phone", "Phone", "phone", False),
                TemplateField("mobile", "Mobile", "phone", False),
                TemplateField("fax", "Fax", "phone", False),
                TemplateField("website", "Website", "text", False),
                TemplateField("address", "Address", "text", False),
            ],
            keywords=["email", "phone", "tel", "fax", "mobile", "www", "http"],
            is_preset=True
        )
        self.templates["business_card"] = business_card_template
        
        # Contract Template
        contract_template = DocumentTemplate(
            template_id="contract",
            name="Contract",
            description="Extract key information from contracts",
            category="legal",
            fields=[
                TemplateField("contract_number", "Contract Number", "text", False),
                TemplateField("contract_date", "Contract Date", "date", True),
                TemplateField("effective_date", "Effective Date", "date", False),
                TemplateField("expiry_date", "Expiry Date", "date", False),
                TemplateField("party_a", "Party A", "text", True),
                TemplateField("party_b", "Party B", "text", True),
                TemplateField("contract_value", "Contract Value", "money", False),
                TemplateField("payment_terms", "Payment Terms", "text", False),
            ],
            keywords=["contract", "agreement", "party", "terms", "conditions", "effective"],
            is_preset=True
        )
        self.templates["contract"] = contract_template
        
        logger.info(f"Loaded {len(self.templates)} preset templates")
    
    def _load_custom_templates(self):
        """Load custom templates from file system"""
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            return
        
        for filename in os.listdir(self.templates_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.templates_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        template = DocumentTemplate.from_dict(data)
                        self.templates[template.template_id] = template
                        logger.info(f"Loaded custom template: {template.name}")
                except Exception as e:
                    logger.error(f"Failed to load template {filename}: {e}")
    
    def get_template(self, template_id: str) -> Optional[DocumentTemplate]:
        """Get template by ID"""
        return self.templates.get(template_id)
    
    def list_templates(self, category: str = None) -> List[Dict[str, Any]]:
        """List all available templates"""
        templates = []
        for template in self.templates.values():
            if category is None or template.category == category:
                templates.append({
                    "template_id": template.template_id,
                    "name": template.name,
                    "description": template.description,
                    "category": template.category,
                    "field_count": len(template.fields),
                    "is_preset": template.is_preset
                })
        return templates
    
    def create_template(self, template_data: Dict[str, Any]) -> DocumentTemplate:
        """Create a new custom template"""
        template = DocumentTemplate.from_dict(template_data)
        template.is_preset = False
        
        # Save to file
        filepath = os.path.join(self.templates_dir, f"{template.template_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
        
        self.templates[template.template_id] = template
        logger.info(f"Created custom template: {template.name}")
        
        return template
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a custom template"""
        template = self.templates.get(template_id)
        if not template:
            return False
        
        if template.is_preset:
            raise ValueError("Cannot delete preset templates")
        
        # Remove file
        filepath = os.path.join(self.templates_dir, f"{template_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        
        del self.templates[template_id]
        return True
    
    def match_template(self, text: str, tables: List[Dict] = None) -> List[Tuple[str, float]]:
        """
        Match document against templates and return ranked matches
        
        Returns list of (template_id, score) tuples sorted by score
        """
        text_lower = text.lower()
        scores = []
        
        for template_id, template in self.templates.items():
            score = 0.0
            
            # Keyword matching
            keyword_matches = sum(1 for kw in template.keywords if kw.lower() in text_lower)
            if template.keywords:
                score += (keyword_matches / len(template.keywords)) * 0.5
            
            # Field pattern matching
            field_matches = 0
            for field in template.fields:
                values = FieldExtractor.extract_by_pattern(text, field.field_type, field.patterns)
                if values:
                    field_matches += 1
            
            if template.fields:
                score += (field_matches / len(template.fields)) * 0.5
            
            scores.append((template_id, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores
    
    async def extract_fields(
        self,
        template_id: str,
        text: str,
        text_blocks: List[Dict] = None,
        tables: List[Dict] = None,
        layout_elements: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract field values from document using template
        
        Args:
            template_id: Template ID
            text: Full document text
            text_blocks: OCR text blocks with position info
            tables: Extracted tables
            layout_elements: Layout analysis results
        
        Returns:
            Dictionary with extracted fields and confidence scores
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        extracted = {
            "template_id": template_id,
            "template_name": template.name,
            "fields": {},
            "confidence": 0.0,
            "missing_required": []
        }
        
        tables = tables or []
        text_blocks = text_blocks or []
        layout_elements = layout_elements or []
        
        for field in template.fields:
            field_result = await self._extract_field(
                field, text, tables, text_blocks, layout_elements
            )
            extracted["fields"][field.name] = field_result
            
            if field.required and not field_result.get("value"):
                extracted["missing_required"].append(field.name)
        
        # Calculate overall confidence
        total_fields = len(template.fields)
        extracted_count = sum(1 for f in extracted["fields"].values() if f.get("value"))
        required_count = sum(1 for f in template.fields if f.required)
        required_extracted = required_count - len(extracted["missing_required"])
        
        if total_fields > 0:
            extracted["confidence"] = round(
                (extracted_count / total_fields * 0.5) + 
                (required_extracted / max(required_count, 1) * 0.5),
                4
            )
        
        return extracted
    
    async def _extract_field(
        self,
        field: TemplateField,
        text: str,
        tables: List[Dict],
        text_blocks: List[Dict] = None,
        layout_elements: List[Dict] = None
    ) -> Dict[str, Any]:
        """Extract a single field value with enhanced logic"""
        result = {
            "field_name": field.name,
            "label": field.label,
            "value": None,
            "confidence": 0.0,
            "source": None,
            "all_values": []
        }
        
        # Strategy 1: Try custom patterns first (highest priority)
        if field.patterns:
            values = FieldExtractor.extract_by_pattern(text, field.field_type, field.patterns)
            if values:
                # Clean and validate values
                cleaned_values = [self._clean_value(v, field.field_type) for v in values]
                cleaned_values = [v for v in cleaned_values if v]
                
                if cleaned_values:
                    result["value"] = cleaned_values[0]
                    result["all_values"] = cleaned_values
                    result["confidence"] = 0.85  # Higher confidence for custom patterns
                    result["source"] = "pattern"
                    return result
        
        # Strategy 2: Try label-based extraction with context
        label_variations = [
            field.label,
            field.name.replace("_", " ").title(),
            field.name.replace("_", " "),
            field.name
        ]
        
        for label in label_variations:
            label_values = FieldExtractor.extract_by_label(text, label)
            if label_values:
                cleaned_values = [self._clean_value(v, field.field_type) for v in label_values]
                cleaned_values = [v for v in cleaned_values if v]
                
                if cleaned_values:
                    result["value"] = cleaned_values[0]
                    result["all_values"] = cleaned_values
                    result["confidence"] = 0.75
                    result["source"] = "label"
                    return result
        
        # Strategy 3: Try table extraction
        possible_labels = label_variations + [
            field.name.replace("_", ""),
            field.name.upper(),
            field.name.lower()
        ]
        table_value = FieldExtractor.extract_from_table(tables, field.name, possible_labels)
        if table_value:
            cleaned_value = self._clean_value(table_value, field.field_type)
            if cleaned_value:
                result["value"] = cleaned_value
                result["confidence"] = 0.80
                result["source"] = "table"
                return result
        
        # Strategy 4: Try type-based extraction (fallback)
        if field.field_type in FieldExtractor.PATTERNS:
            type_values = FieldExtractor.extract_by_pattern(text, field.field_type, None)
            if type_values:
                cleaned_values = [self._clean_value(v, field.field_type) for v in type_values]
                cleaned_values = [v for v in cleaned_values if v]
                
                if cleaned_values:
                    result["value"] = cleaned_values[0]
                    result["all_values"] = cleaned_values
                    result["confidence"] = 0.5  # Lower confidence for generic extraction
                    result["source"] = "type_fallback"
                    return result
        
        return result
    
    def _clean_value(self, value: str, field_type: str) -> Optional[str]:
        """Clean and validate extracted value"""
        if not value:
            return None
        
        value = value.strip()
        
        # Remove common prefixes/suffixes
        value = re.sub(r'^[\s:：\-_]+|[\s:：\-_]+$', '', value)
        
        # Type-specific cleaning
        if field_type == "money":
            # Remove currency symbols but keep the number
            value = re.sub(r'^[\$€£¥]\s*', '', value)
            value = re.sub(r'\s*(?:dollars?|USD|EUR|GBP|CNY|RMB|元|美元)$', '', value, flags=re.IGNORECASE)
        
        elif field_type == "date":
            # Normalize date formats
            value = re.sub(r'年|月|日', '-', value)
            value = re.sub(r'[-/]+', '-', value)
        
        elif field_type == "phone":
            # Remove common phone prefixes
            value = re.sub(r'^(?:Tel|Phone|Mobile|电话|手机)[\s:：]*', '', value, flags=re.IGNORECASE)
            value = re.sub(r'[^\d+\-()\s]', '', value)
        
        elif field_type == "email":
            # Ensure valid email format
            if '@' not in value:
                return None
        
        # Final validation - ensure value is not empty
        if not value or len(value) < 1:
            return None
        
        return value
    
    async def auto_extract(
        self,
        text: str,
        text_blocks: List[Dict] = None,
        tables: List[Dict] = None,
        top_templates: int = 3
    ) -> Dict[str, Any]:
        """
        Automatically detect best template and extract fields
        
        Args:
            text: Document text
            text_blocks: OCR text blocks
            tables: Extracted tables
            top_templates: Number of top matching templates to try
        
        Returns:
            Best extraction result
        """
        # Match templates
        matches = self.match_template(text, tables)
        
        if not matches or matches[0][1] < 0.1:
            return {
                "success": False,
                "message": "No matching template found",
                "matches": matches[:top_templates]
            }
        
        # Try top matching templates
        best_result = None
        best_confidence = 0.0
        
        for template_id, match_score in matches[:top_templates]:
            if match_score < 0.1:
                break
            
            try:
                result = await self.extract_fields(template_id, text, text_blocks, tables)
                
                if result["confidence"] > best_confidence:
                    best_confidence = result["confidence"]
                    best_result = result
                    best_result["match_score"] = match_score
            except Exception as e:
                logger.warning(f"Template {template_id} extraction failed: {e}")
        
        if best_result:
            return {
                "success": True,
                "result": best_result,
                "matches": matches[:top_templates]
            }
        
        return {
            "success": False,
            "message": "Field extraction failed for all templates",
            "matches": matches[:top_templates]
        }

