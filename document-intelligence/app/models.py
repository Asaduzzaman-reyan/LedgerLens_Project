from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Item(BaseModel):
    model_config = ConfigDict(extra='forbid')
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    @field_validator('quantity', 'unit_price', 'amount')
    @classmethod
    def finite(cls, value):
        if value is not None and not value.is_finite():
            raise ValueError('Amounts must be finite')
        return value

class Invoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    invoice_number: str | None = None
    invoice_date: str | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None
    line_items: list[Item] = Field(default_factory=list, max_length=10000)
    evidence: dict[str, str] = Field(default_factory=dict)
    uncertain_fields: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    method: str = 'rules'
    @field_validator('subtotal', 'tax', 'total')
    @classmethod
    def finite(cls, value):
        if value is not None and not value.is_finite():
            raise ValueError('Amounts must be finite')
        return value

FIELDS = ['invoice_number','invoice_date','supplier_name','customer_name','subtotal','tax','total','currency']

class Correction(BaseModel):
    version: int
    invoices: list[Invoice] = Field(min_length=1, max_length=1500)
    reason: str = Field(min_length=3, max_length=500)

class CompareRequest(BaseModel):
    document_ids: list[str] = Field(min_length=2, max_length=10)
