"""Data models for TDnet XBRL parsed results."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IncomeStatementPeriod:
    net_sales: Optional[int] = None
    gross_profit: Optional[int] = None
    operating_income: Optional[int] = None
    ordinary_income: Optional[int] = None
    profit_before_tax: Optional[int] = None
    net_income: Optional[int] = None
    earnings_per_share: Optional[float] = None


@dataclass
class BalanceSheetPeriod:
    total_assets: Optional[int] = None
    current_assets: Optional[int] = None
    noncurrent_assets: Optional[int] = None
    total_liabilities: Optional[int] = None
    current_liabilities: Optional[int] = None
    noncurrent_liabilities: Optional[int] = None
    net_assets: Optional[int] = None


@dataclass
class CashFlowPeriod:
    operating_cf: Optional[int] = None
    investing_cf: Optional[int] = None
    financing_cf: Optional[int] = None
    ending_cash: Optional[int] = None


@dataclass
class QualitativeInfo:
    """Qualitative (text) information extracted from qualitative.htm and TextBlock elements."""
    overview_of_business_results: Optional[str] = None
    financial_condition: Optional[str] = None
    cash_flow_overview: Optional[str] = None
    forecast: Optional[str] = None
    other_sections: dict = field(default_factory=dict)


@dataclass
class FinancialStatements:
    current_year: Optional[object] = None
    prior_year: Optional[object] = None


@dataclass
class XBRLParseResult:
    company_name: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    document_type: Optional[str] = None
    accounting_standard: str = "jp_gaap"
    consolidation: str = "consolidated"
    income_statement: dict = field(default_factory=dict)
    balance_sheet: dict = field(default_factory=dict)
    cash_flow: dict = field(default_factory=dict)
    qualitative: Optional[QualitativeInfo] = None
    parse_warnings: list = field(default_factory=list)
