"""Data models shared across the pipeline."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal
    amount: Decimal


class Invoice(BaseModel):
    """The structured record DocFlow extracts from a messy document."""

    supplier_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = Field(default=None, description="ISO 4217 code, e.g. GBP")
    subtotal: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = Field(default=None, description="Percentage, e.g. 20 for 20%")
    vat_amount: Optional[Decimal] = None
    total: Optional[Decimal] = None
    line_items: list[LineItem] = Field(default_factory=list)


FIELDS = [
    "supplier_name", "invoice_number", "invoice_date", "due_date", "currency",
    "subtotal", "vat_rate", "vat_amount", "total",
]


class Severity(str, Enum):
    ERROR = "error"      # the record is wrong or unusable without a human
    WARNING = "warning"  # suspicious, worth a look


class Issue(BaseModel):
    code: str
    severity: Severity
    message: str
    field: Optional[str] = None


class Usage(BaseModel):
    """Token and cost accounting for one document (AI FinOps)."""

    model: str = "rules-baseline"
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


class Decision(str, Enum):
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class ExtractionResult(BaseModel):
    document_name: str
    extractor: str
    invoice: Invoice
    issues: list[Issue] = Field(default_factory=list)
    injection_detected: bool = False
    field_confidence: dict[str, str] = Field(default_factory=dict)
    file_sha256: Optional[str] = None
    repair_attempts: int = 0
    decision: Decision = Decision.NEEDS_REVIEW
    usage: Usage = Field(default_factory=Usage)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]
