"""TDnet XBRL / Inline XBRL parser.

Supports:
- TDnet 決算短信 ZIP archives (XBRLData/ layout)
- Individual iXBRL .htm files
- qualitative.htm for qualitative (text) information
- JP GAAP, IFRS, US GAAP accounting standards
"""
from __future__ import annotations

import re
import zipfile
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from .models import (
    BalanceSheetPeriod,
    CashFlowPeriod,
    IncomeStatementPeriod,
    QualitativeInfo,
    XBRLParseResult,
)


# ---------------------------------------------------------------------------
# Element name candidates per accounting standard
# ---------------------------------------------------------------------------

_PL_CANDIDATES: dict[str, dict[str, list[str]]] = {
    "jp_gaap": {
        "net_sales": ["NetSales", "OperatingRevenues", "NetSalesOfCompletedConstructionContracts",
                      "OrdinaryRevenues", "GrossOperatingRevenues"],
        "gross_profit": ["GrossProfit", "GrossProfitOnSales"],
        "operating_income": ["OperatingIncome", "OperatingProfit",
                             "OperatingIncomeOrLoss"],
        "ordinary_income": ["OrdinaryIncome", "OrdinaryProfit",
                            "OrdinaryIncomeOrLoss"],
        "profit_before_tax": ["ProfitBeforeIncomeTaxes",
                              "IncomeBeforeIncomeTaxes",
                              "IncomeLossBeforeIncomeTaxes"],
        "net_income": ["ProfitAttributableToOwnersOfParent",
                       "NetIncome", "Profit",
                       "ProfitLossAttributableToOwnersOfParent"],
        "earnings_per_share": ["BasicEarningsLossPerShare",
                               "BasicEarningsPerShare",
                               "EarningsPerShare"],
    },
    "ifrs": {
        "net_sales": ["RevenueIFRS", "Revenue", "SalesIFRS",
                      "RevenueFromContractsWithCustomersIFRS"],
        "gross_profit": ["GrossProfitIFRS", "GrossProfit"],
        "operating_income": ["OperatingProfitIFRS", "ProfitFromOperationsIFRS",
                             "OperatingProfit"],
        "ordinary_income": [],
        "profit_before_tax": ["ProfitBeforeIncomeTaxIFRS",
                              "ProfitBeforeIncomeTax"],
        "net_income": ["ProfitAttributableToOwnersOfParentIFRS",
                       "ProfitLossAttributableToOwnersOfParentIFRS"],
        "earnings_per_share": ["BasicEarningsLossPerShareIFRS",
                               "BasicEarningsPerShareIFRS"],
    },
    "us_gaap": {
        "net_sales": ["NetSalesUS", "Revenues", "SalesRevenueNet",
                      "RevenueFromContractWithCustomerExcludingAssessedTax"],
        "gross_profit": ["GrossProfitUS", "GrossProfit"],
        "operating_income": ["OperatingIncomeUS", "OperatingIncomeLoss"],
        "ordinary_income": [],
        "profit_before_tax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesUS"],
        "net_income": ["NetIncomeLossAttributableToParentUS",
                       "NetIncomeLoss"],
        "earnings_per_share": ["EarningsPerShareBasicUS",
                               "EarningsPerShareBasic"],
    },
}

_BS_CANDIDATES: dict[str, dict[str, list[str]]] = {
    "jp_gaap": {
        "total_assets": ["Assets", "TotalAssets"],
        "current_assets": ["CurrentAssets", "TotalCurrentAssets"],
        "noncurrent_assets": ["NoncurrentAssets", "TotalNoncurrentAssets",
                              "PropertyPlantAndEquipmentNet"],
        "total_liabilities": ["Liabilities", "TotalLiabilities"],
        "current_liabilities": ["CurrentLiabilities", "TotalCurrentLiabilities"],
        "noncurrent_liabilities": ["NoncurrentLiabilities", "TotalNoncurrentLiabilities"],
        "net_assets": ["NetAssets", "TotalNetAssets", "Equity",
                       "TotalEquity"],
    },
    "ifrs": {
        "total_assets": ["TotalAssetsIFRS", "Assets"],
        "current_assets": ["CurrentAssetsIFRS", "CurrentAssets"],
        "noncurrent_assets": ["NoncurrentAssetsIFRS", "NoncurrentAssets"],
        "total_liabilities": ["TotalLiabilitiesIFRS", "Liabilities"],
        "current_liabilities": ["CurrentLiabilitiesIFRS", "CurrentLiabilities"],
        "noncurrent_liabilities": ["NoncurrentLiabilitiesIFRS", "NoncurrentLiabilities"],
        "net_assets": ["TotalEquityIFRS", "Equity", "TotalEquityAttributableToOwnersOfParentIFRS"],
    },
    "us_gaap": {
        "total_assets": ["AssetsUS", "Assets"],
        "current_assets": ["AssetCurrentUS", "AssetsCurrent"],
        "noncurrent_assets": ["AssetsNoncurrentUS", "AssetsNoncurrent"],
        "total_liabilities": ["LiabilitiesUS", "Liabilities"],
        "current_liabilities": ["LiabilitiesCurrentUS", "LiabilitiesCurrent"],
        "noncurrent_liabilities": ["LiabilitiesNoncurrentUS", "LiabilitiesNoncurrent"],
        "net_assets": ["StockholdersEquityUS", "StockholdersEquity",
                       "LiabilitiesAndStockholdersEquity"],
    },
}

_CF_CANDIDATES: dict[str, dict[str, list[str]]] = {
    "jp_gaap": {
        "operating_cf": ["NetCashProvidedByUsedInOperatingActivities",
                         "CashFlowsFromOperatingActivities"],
        "investing_cf": ["NetCashProvidedByUsedInInvestingActivities",
                         "CashFlowsFromInvestingActivities"],
        "financing_cf": ["NetCashProvidedByUsedInFinancingActivities",
                         "CashFlowsFromFinancingActivities"],
        "ending_cash": ["CashAndCashEquivalents",
                        "CashAndCashEquivalentsAtEndOfPeriod",
                        "CashAndCashEquivalentsEndOfPeriod"],
    },
    "ifrs": {
        "operating_cf": ["CashFlowsFromUsedInOperatingActivitiesIFRS",
                         "NetCashProvidedByUsedInOperatingActivitiesIFRS"],
        "investing_cf": ["CashFlowsFromUsedInInvestingActivitiesIFRS",
                         "NetCashProvidedByUsedInInvestingActivitiesIFRS"],
        "financing_cf": ["CashFlowsFromUsedInFinancingActivitiesIFRS",
                         "NetCashProvidedByUsedInFinancingActivitiesIFRS"],
        "ending_cash": ["CashAndCashEquivalentsIFRS",
                        "CashAndCashEquivalentsAtEndOfReportingPeriodIFRS"],
    },
    "us_gaap": {
        "operating_cf": ["NetCashProvidedByUsedInOperatingActivitiesUS"],
        "investing_cf": ["NetCashProvidedByUsedInInvestingActivitiesUS"],
        "financing_cf": ["NetCashProvidedByUsedInFinancingActivitiesUS"],
        "ending_cash": ["CashAndCashEquivalentsAtCarryingValueUS",
                        "CashAndCashEquivalents"],
    },
}

# Context ID keyword patterns: (year_label, period_type)
_CONTEXT_PATTERNS = [
    (re.compile(r"CurrentYear.*Duration", re.I), ("current", "duration")),
    (re.compile(r"CurrentYear.*Instant", re.I), ("current", "instant")),
    (re.compile(r"Prior1Year.*Duration", re.I), ("prior1", "duration")),
    (re.compile(r"Prior1Year.*Instant", re.I), ("prior1", "instant")),
    (re.compile(r"FilingDate.*Instant", re.I), ("filing", "instant")),
]

# Heading keywords for qualitative.htm section detection
_QUALITATIVE_SECTION_MAP = [
    (["経営成績", "業績の概要", "経営成績等の概況", "当期の概況"],
     "overview_of_business_results"),
    (["財政状態", "財政状態の概況"],
     "financial_condition"),
    (["キャッシュ・フロー", "キャッシュフロー", "資金の状況"],
     "cash_flow_overview"),
    (["業績予想", "次期の見通し", "今後の見通し", "次期業績予想"],
     "forecast"),
]

# DEI element names for company info
_COMPANY_NAME_ELEMENTS = [
    "CompanyNameCoverPage", "FilerNameInJapaneseDEI", "EntityRegistrantNameJa",
    "CompanyName", "EntityRegistrantName",
]
_FISCAL_YEAR_END_ELEMENTS = [
    "CurrentFiscalYearEndDateDEI", "CurrentFiscalYearEndDate",
    "FiscalYearEndDateDEI",
]
_DOCUMENT_TYPE_ELEMENTS = [
    "DocumentTypeDEI", "TypeOfCurrentPeriodDEI", "DocumentType",
]


# ---------------------------------------------------------------------------
# Value normalisation
# ---------------------------------------------------------------------------

def _normalize_numeric(tag) -> Optional[int | float]:
    """Extract and scale a numeric value from an ix:nonFraction tag."""
    nil = tag.get("xsi:nil") or tag.get("{http://www.w3.org/2001/XMLSchema-instance}nil")
    if nil and nil.lower() == "true":
        return None
    text = tag.get_text(strip=True).replace(",", "").replace("\u3000", "").strip()
    if not text or text == "-":
        return None
    try:
        scale_str = tag.get("scale", "0")
        scale = int(scale_str) if scale_str else 0
        sign = tag.get("sign", "")
        # Try integer first, then float
        try:
            val: int | float = int(text)
        except ValueError:
            val = float(text)
        val = val * (10 ** scale)
        if sign == "-":
            val = -val
        # Return int when the result is a whole number and not EPS-like
        if isinstance(val, float) and val == int(val) and abs(val) < 1e15:
            return int(val)
        return val
    except (ValueError, OverflowError):
        return None


def _local_name(full_name: str) -> str:
    """Return the local part after ':' in a prefixed name like 'tse-ed-t:NetSales'."""
    return full_name.split(":")[-1] if ":" in full_name else full_name


# ---------------------------------------------------------------------------
# iXBRL file parsing
# ---------------------------------------------------------------------------

def _parse_ixbrl(htm_path: Path) -> tuple[dict, dict]:
    """Parse an iXBRL .htm file.

    Returns:
        elements: dict mapping (local_name, context_ref) -> value
        contexts: dict mapping context_id -> {type, start, end, instant, segment}
    """
    with open(htm_path, encoding="utf-8", errors="replace") as fh:
        soup = BeautifulSoup(fh, "lxml")

    contexts: dict = {}
    elements: dict = {}

    # --- Parse contexts from ix:resources / xbrli:context ---
    for ctx in soup.find_all(["xbrli:context", "context"]):
        ctx_id = ctx.get("id", "")
        info: dict = {"id": ctx_id, "segment": None}

        period = ctx.find(["xbrli:period", "period"])
        if period:
            instant_tag = period.find(["xbrli:instant", "instant"])
            start_tag = period.find(["xbrli:startdate", "startdate"])
            end_tag = period.find(["xbrli:enddate", "enddate"])
            if instant_tag:
                info["type"] = "instant"
                info["instant"] = instant_tag.get_text(strip=True)
            elif start_tag and end_tag:
                info["type"] = "duration"
                info["start"] = start_tag.get_text(strip=True)
                info["end"] = end_tag.get_text(strip=True)

        segment = ctx.find(["xbrli:segment", "segment"])
        if segment:
            member = segment.find(True)
            if member:
                info["segment"] = member.get_text(strip=True)

        contexts[ctx_id] = info

    # --- Parse ix:nonFraction (numeric values) ---
    for tag in soup.find_all(re.compile(r"ix:nonfraction", re.I)):
        name = tag.get("name", "")
        ctx_ref = tag.get("contextref", "")
        val = _normalize_numeric(tag)
        local = _local_name(name)
        if local:
            key = (local, ctx_ref)
            if key not in elements or val is not None:
                elements[key] = val

    # --- Parse ix:nonNumeric (text values) ---
    for tag in soup.find_all(re.compile(r"ix:nonnumeric", re.I)):
        name = tag.get("name", "")
        ctx_ref = tag.get("contextref", "")
        local = _local_name(name)
        text = tag.get_text(separator=" ", strip=True)
        if local:
            key = (local, ctx_ref)
            if key not in elements:
                elements[key] = text or None

    return elements, contexts


# ---------------------------------------------------------------------------
# Context classification
# ---------------------------------------------------------------------------

def _classify_context(ctx_id: str, ctx_info: dict) -> tuple[str, str]:
    """Classify a context into (year, period_type).

    year: 'current' | 'prior1' | 'filing' | 'unknown'
    period_type: 'duration' | 'instant' | 'unknown'
    """
    for pattern, result in _CONTEXT_PATTERNS:
        if pattern.search(ctx_id):
            return result

    # Date-based fallback
    period_type = ctx_info.get("type", "unknown")
    return ("unknown", period_type)


# ---------------------------------------------------------------------------
# Financial data extraction helpers
# ---------------------------------------------------------------------------

def _find_value(elements: dict, candidates: list[str],
                year: str, period_type: str,
                contexts: dict) -> Optional[int | float]:
    """Search elements dict for the first matching candidate element."""
    # Build a set of context IDs matching the desired (year, period_type)
    matching_ctxs = {
        ctx_id for ctx_id, info in contexts.items()
        if _classify_context(ctx_id, info) == (year, period_type)
    }

    for name in candidates:
        for ctx_id in matching_ctxs:
            val = elements.get((name, ctx_id))
            if val is not None:
                return val
    return None


def _extract_pl(elements: dict, contexts: dict,
                standard: str) -> dict:
    cands = _PL_CANDIDATES.get(standard, _PL_CANDIDATES["jp_gaap"])
    result = {}
    for year_label, out_key in (("current", "current_year"), ("prior1", "prior_year")):
        period: dict[str, Optional[int | float]] = {}
        for field, names in cands.items():
            period[field] = _find_value(elements, names, year_label, "duration", contexts)
        result[out_key] = {k: v for k, v in period.items()}
    return result


def _extract_bs(elements: dict, contexts: dict,
                standard: str) -> dict:
    cands = _BS_CANDIDATES.get(standard, _BS_CANDIDATES["jp_gaap"])
    result = {}
    for year_label, out_key in (("current", "current_year"), ("prior1", "prior_year")):
        period: dict[str, Optional[int]] = {}
        for field, names in cands.items():
            period[field] = _find_value(elements, names, year_label, "instant", contexts)
        result[out_key] = {k: v for k, v in period.items()}
    return result


def _extract_cf(elements: dict, contexts: dict,
                standard: str) -> dict:
    cands = _CF_CANDIDATES.get(standard, _CF_CANDIDATES["jp_gaap"])
    result = {}
    for year_label, out_key in (("current", "current_year"), ("prior1", "prior_year")):
        period: dict[str, Optional[int]] = {}
        for field, names in cands.items():
            # ending_cash is a balance (instant); try instant first, then duration
            if field == "ending_cash":
                val = _find_value(elements, names, year_label, "instant", contexts)
                if val is None:
                    val = _find_value(elements, names, year_label, "duration", contexts)
            else:
                val = _find_value(elements, names, year_label, "duration", contexts)
            period[field] = val
        result[out_key] = {k: v for k, v in period.items()}
    return result


# ---------------------------------------------------------------------------
# Accounting standard detection
# ---------------------------------------------------------------------------

def _detect_accounting_standard(elements: dict) -> str:
    """Infer accounting standard from element names present."""
    all_names = {local for (local, _) in elements}
    ifrs_markers = {"RevenueIFRS", "ProfitAttributableToOwnersOfParentIFRS",
                    "TotalAssetsIFRS", "CashFlowsFromUsedInOperatingActivitiesIFRS"}
    us_markers = {"NetSalesUS", "NetIncomeLossAttributableToParentUS",
                  "AssetsUS", "NetCashProvidedByUsedInOperatingActivitiesUS"}

    if all_names & ifrs_markers:
        return "ifrs"
    if all_names & us_markers:
        return "us_gaap"
    return "jp_gaap"


# ---------------------------------------------------------------------------
# Consolidation detection
# ---------------------------------------------------------------------------

def _detect_consolidation(contexts: dict) -> str:
    """Infer consolidation from context segment information."""
    for ctx_id, info in contexts.items():
        seg = (info.get("segment") or "").lower()
        if "nonconsolidated" in seg or "non_consolidated" in seg or "単体" in seg:
            return "nonconsolidated"
        if "consolidated" in ctx_id.lower() and "non" not in ctx_id.lower():
            return "consolidated"
    return "consolidated"


# ---------------------------------------------------------------------------
# Company info extraction
# ---------------------------------------------------------------------------

def _extract_company_info(elements: dict) -> dict:
    info: dict = {}
    all_ctx = {ctx for (_, ctx) in elements}

    def get_first(names: list[str]) -> Optional[str]:
        for name in names:
            for ctx in all_ctx:
                val = elements.get((name, ctx))
                if val and isinstance(val, str):
                    return val
        return None

    info["company_name"] = get_first(_COMPANY_NAME_ELEMENTS)
    info["fiscal_year_end"] = get_first(_FISCAL_YEAR_END_ELEMENTS)
    info["document_type"] = get_first(_DOCUMENT_TYPE_ELEMENTS)
    return info


# ---------------------------------------------------------------------------
# Text block extraction from iXBRL
# ---------------------------------------------------------------------------

_TEXT_BLOCK_SUFFIXES = ["TextBlock"]
_TEXT_BLOCK_CONTEXT_PRIORITY = [
    re.compile(r"FilingDateInstant", re.I),
    re.compile(r"CurrentYear.*Duration", re.I),
    re.compile(r"CurrentYear.*Instant", re.I),
]


def _extract_text_blocks(elements: dict) -> dict[str, str]:
    """Extract *TextBlock elements from iXBRL and return {local_name: plain_text}."""
    result: dict[str, str] = {}
    text_block_keys = [
        (local, ctx) for (local, ctx) in elements
        if local.endswith("TextBlock")
    ]
    for local, ctx in text_block_keys:
        val = elements.get((local, ctx))
        if not val or not isinstance(val, str):
            continue
        # Strip HTML
        text = BeautifulSoup(val, "lxml").get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if local not in result:
            result[local] = text
    return result


# ---------------------------------------------------------------------------
# qualitative.htm parsing
# ---------------------------------------------------------------------------

def _parse_qualitative_html(htm_path: Path) -> QualitativeInfo:
    """Parse qualitative.htm and extract text sections by heading."""
    with open(htm_path, encoding="utf-8", errors="replace") as fh:
        soup = BeautifulSoup(fh, "lxml")

    # Remove script/style tags
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Collect all headings and their following text
    sections: dict[str, str] = {}
    current_heading: Optional[str] = None
    buffer: list[str] = []

    def flush():
        nonlocal current_heading, buffer
        if current_heading and buffer:
            text = "\n".join(buffer).strip()
            if text:
                sections[current_heading] = text
        buffer = []

    for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "div", "td"]):
        tag_name = elem.name
        if tag_name in ("h1", "h2", "h3", "h4"):
            flush()
            current_heading = elem.get_text(strip=True)
        else:
            text = elem.get_text(separator=" ", strip=True)
            if text:
                buffer.append(text)

    flush()

    def match_section(keywords: list[str]) -> Optional[str]:
        for heading, text in sections.items():
            for kw in keywords:
                if kw in heading:
                    return text
        return None

    other: dict[str, str] = {}
    mapped_headings: set[str] = set()

    # Map known sections
    result = QualitativeInfo()
    for keywords, attr in _QUALITATIVE_SECTION_MAP:
        matched = None
        for heading, text in sections.items():
            for kw in keywords:
                if kw in heading:
                    matched = (heading, text)
                    break
            if matched:
                break
        if matched:
            setattr(result, attr, matched[1])
            mapped_headings.add(matched[0])

    # Remaining sections → other_sections
    for heading, text in sections.items():
        if heading not in mapped_headings and text:
            other[heading] = text

    result.other_sections = other
    return result


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class TDnetXBRLParser:
    """Parse a TDnet 決算短信 XBRL ZIP or individual iXBRL file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._warnings: list[str] = []

    def parse(self) -> XBRLParseResult:
        path = self.path
        tmp_dir = None

        try:
            if path.suffix.lower() == ".zip":
                tmp_dir = tempfile.mkdtemp(prefix="tdnet_xbrl_")
                with zipfile.ZipFile(path) as zf:
                    zf.extractall(tmp_dir)
                root_dir = Path(tmp_dir)
            elif path.is_dir():
                root_dir = path
            else:
                # Single iXBRL file
                return self._parse_single_ixbrl(path)

            return self._parse_directory(root_dir)

        finally:
            if tmp_dir:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _parse_single_ixbrl(self, htm_path: Path) -> XBRLParseResult:
        elements, contexts = _parse_ixbrl(htm_path)
        return self._build_result(elements, contexts, qualitative_path=None)

    def _parse_directory(self, root_dir: Path) -> XBRLParseResult:
        # Find all iXBRL files (prefer Attachment/, fall back to whole tree)
        attachment_dir = root_dir / "XBRLData" / "Attachment"
        if not attachment_dir.exists():
            attachment_dir = root_dir

        ixbrl_files = sorted(attachment_dir.rglob("*ixbrl.htm"))
        if not ixbrl_files:
            # Broader search
            ixbrl_files = sorted(root_dir.rglob("*ixbrl.htm"))
        if not ixbrl_files:
            # Any .htm file that is not qualitative.htm
            ixbrl_files = [
                f for f in root_dir.rglob("*.htm")
                if f.name.lower() != "qualitative.htm"
            ]

        if not ixbrl_files:
            self._warnings.append("No iXBRL files found in archive.")
            return XBRLParseResult(parse_warnings=self._warnings)

        # Merge elements from all iXBRL files
        all_elements: dict = {}
        all_contexts: dict = {}
        for f in ixbrl_files:
            try:
                elems, ctxs = _parse_ixbrl(f)
                all_elements.update(elems)
                all_contexts.update(ctxs)
            except Exception as exc:
                self._warnings.append(f"Failed to parse {f.name}: {exc}")

        # Find qualitative.htm
        qual_path: Optional[Path] = None
        for candidate in attachment_dir.rglob("qualitative.htm"):
            qual_path = candidate
            break

        return self._build_result(all_elements, all_contexts, qual_path)

    def _build_result(self, elements: dict, contexts: dict,
                      qualitative_path: Optional[Path]) -> XBRLParseResult:
        standard = _detect_accounting_standard(elements)
        consolidation = _detect_consolidation(contexts)
        company_info = _extract_company_info(elements)

        pl = _extract_pl(elements, contexts, standard)
        bs = _extract_bs(elements, contexts, standard)
        cf = _extract_cf(elements, contexts, standard)

        if not any(v for period in pl.values() for v in period.values()):
            self._warnings.append("No income statement data found.")
        if not any(v for period in bs.values() for v in period.values()):
            self._warnings.append("No balance sheet data found.")

        # Qualitative info
        qualitative: Optional[QualitativeInfo] = None
        if qualitative_path and qualitative_path.exists():
            try:
                qualitative = _parse_qualitative_html(qualitative_path)
            except Exception as exc:
                self._warnings.append(f"Failed to parse qualitative.htm: {exc}")

        # Merge TextBlock elements into qualitative if not already set
        text_blocks = _extract_text_blocks(elements)
        if text_blocks:
            if qualitative is None:
                qualitative = QualitativeInfo()
            # Map known TextBlock element names to qualitative fields
            _TEXT_BLOCK_MAPPING = {
                "overview_of_business_results": [
                    "ExplanationAboutBusinessResultsTextBlock",
                    "OverviewOfBusinessResultsTextBlock",
                ],
                "financial_condition": [
                    "ExplanationAboutFinancialPositionTextBlock",
                    "FinancialPositionTextBlock",
                ],
                "cash_flow_overview": [
                    "ExplanationAboutCashFlowsTextBlock",
                    "CashFlowsTextBlock",
                ],
                "forecast": [
                    "ExplanationAboutOutlookTextBlock",
                    "ForecastForNextFiscalYearTextBlock",
                ],
            }
            for attr, names in _TEXT_BLOCK_MAPPING.items():
                if getattr(qualitative, attr) is None:
                    for name in names:
                        if name in text_blocks:
                            setattr(qualitative, attr, text_blocks[name])
                            break
            # Remaining blocks go to other_sections
            mapped = {n for names in _TEXT_BLOCK_MAPPING.values() for n in names}
            for name, text in text_blocks.items():
                if name not in mapped and name not in (qualitative.other_sections or {}):
                    qualitative.other_sections[name] = text

        return XBRLParseResult(
            company_name=company_info.get("company_name"),
            fiscal_year_end=company_info.get("fiscal_year_end"),
            document_type=company_info.get("document_type"),
            accounting_standard=standard,
            consolidation=consolidation,
            income_statement=pl,
            balance_sheet=bs,
            cash_flow=cf,
            qualitative=qualitative,
            parse_warnings=self._warnings,
        )


# ---------------------------------------------------------------------------
# Public convenience function
# ---------------------------------------------------------------------------

def parse_xbrl(path: str) -> dict:
    """Parse a TDnet XBRL file/ZIP and return a JSON-serializable dict.

    Args:
        path: Path to a TDnet ZIP archive, extracted directory, or iXBRL .htm file.

    Returns:
        dict with keys: company_name, fiscal_year_end, document_type,
        accounting_standard, consolidation, income_statement, balance_sheet,
        cash_flow, qualitative, parse_warnings.
    """
    result = TDnetXBRLParser(path).parse()
    return asdict(result)
