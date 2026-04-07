"""Unit tests for TDnet XBRL parser.

All fixtures are inline strings — no external sample files required.
"""
import io
import json
import zipfile
import tempfile
from pathlib import Path

import pytest

from src.xbrl_parser import (
    TDnetXBRLParser,
    _classify_context,
    _detect_accounting_standard,
    _detect_consolidation,
    _extract_pl,
    _extract_bs,
    _extract_cf,
    _extract_company_info,
    _normalize_numeric,
    _parse_ixbrl,
    _parse_qualitative_html,
    parse_xbrl,
)
from src.models import XBRLParseResult


# ---------------------------------------------------------------------------
# Minimal iXBRL fixture factories
# ---------------------------------------------------------------------------

def _make_ixbrl(extra_elements: str = "", extra_contexts: str = "") -> str:
    """Return a minimal valid iXBRL HTML string."""
    return f"""<!DOCTYPE html>
<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xmlns:jppfs_cor="http://xbrl.ifrs.org/taxonomy/2014-03-05/ifrs-full"
      xmlns:tse-ed-t="http://www.tse.or.jp/taxonomy/2013-08-31/tse-ed-t">
<head><title>Test</title></head>
<body>
<ix:header>
  <ix:hidden></ix:hidden>
  <ix:resources>
    <xbrli:context id="CurrentYearDuration">
      <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345-000</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2023-04-01</xbrli:startDate><xbrli:endDate>2024-03-31</xbrli:endDate></xbrli:period>
    </xbrli:context>
    <xbrli:context id="CurrentYearInstant">
      <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345-000</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:instant>2024-03-31</xbrli:instant></xbrli:period>
    </xbrli:context>
    <xbrli:context id="Prior1YearDuration">
      <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345-000</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2022-04-01</xbrli:startDate><xbrli:endDate>2023-03-31</xbrli:endDate></xbrli:period>
    </xbrli:context>
    <xbrli:context id="Prior1YearInstant">
      <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345-000</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:instant>2023-03-31</xbrli:instant></xbrli:period>
    </xbrli:context>
    <xbrli:context id="FilingDateInstant">
      <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345-000</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:instant>2024-05-10</xbrli:instant></xbrli:period>
    </xbrli:context>
    {extra_contexts}
    <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
  </ix:resources>
</ix:header>

<!-- Company info -->
<ix:nonNumeric name="tse-ed-t:CompanyNameCoverPage" contextRef="FilingDateInstant">テスト株式会社</ix:nonNumeric>
<ix:nonNumeric name="tse-ed-t:CurrentFiscalYearEndDateDEI" contextRef="FilingDateInstant">2024-03-31</ix:nonNumeric>
<ix:nonNumeric name="tse-ed-t:DocumentTypeDEI" contextRef="FilingDateInstant">決算短信</ix:nonNumeric>

<!-- PL -->
<ix:nonFraction name="tse-ed-t:NetSales" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6">100,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:NetSales" contextRef="Prior1YearDuration" unitRef="JPY" decimals="-6" scale="6">90,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:OperatingIncome" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6">10,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:OrdinaryIncome" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6">9,500</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:ProfitBeforeIncomeTaxes" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6">9,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:ProfitAttributableToOwnersOfParent" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6">6,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:BasicEarningsLossPerShare" contextRef="CurrentYearDuration" unitRef="JPY" decimals="2" scale="0">120.50</ix:nonFraction>

<!-- BS -->
<ix:nonFraction name="tse-ed-t:Assets" contextRef="CurrentYearInstant" unitRef="JPY" decimals="-6" scale="6">500,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:CurrentAssets" contextRef="CurrentYearInstant" unitRef="JPY" decimals="-6" scale="6">200,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:NoncurrentAssets" contextRef="CurrentYearInstant" unitRef="JPY" decimals="-6" scale="6">300,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:Liabilities" contextRef="CurrentYearInstant" unitRef="JPY" decimals="-6" scale="6">300,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:NetAssets" contextRef="CurrentYearInstant" unitRef="JPY" decimals="-6" scale="6">200,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:Assets" contextRef="Prior1YearInstant" unitRef="JPY" decimals="-6" scale="6">480,000</ix:nonFraction>

<!-- CF -->
<ix:nonFraction name="tse-ed-t:NetCashProvidedByUsedInOperatingActivities" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6">20,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:NetCashProvidedByUsedInInvestingActivities" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6" sign="-">10,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:NetCashProvidedByUsedInFinancingActivities" contextRef="CurrentYearDuration" unitRef="JPY" decimals="-6" scale="6" sign="-">5,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:CashAndCashEquivalents" contextRef="CurrentYearInstant" unitRef="JPY" decimals="-6" scale="6">50,000</ix:nonFraction>

{extra_elements}
</body>
</html>"""


def _make_qualitative_html() -> str:
    return """<!DOCTYPE html>
<html><body>
<h2>1. 経営成績の概要</h2>
<p>当期の売上高は前期比10%増の100億円となりました。</p>
<p>営業利益も増加し10億円となりました。</p>
<h2>2. 財政状態の概況</h2>
<p>総資産は500億円となりました。</p>
<h2>3. キャッシュ・フローの状況</h2>
<p>営業活動によるキャッシュ・フローは20億円の収入となりました。</p>
<h2>4. 業績予想</h2>
<p>次期は売上高110億円を見込んでいます。</p>
<h2>5. その他の情報</h2>
<p>配当は1株当たり50円を予定しています。</p>
</body></html>"""


# ---------------------------------------------------------------------------
# Helper: write fixture to temp file
# ---------------------------------------------------------------------------

def _write_temp_html(content: str, suffix=".htm") -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=suffix, delete=False
    )
    f.write(content)
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# TestValueNormalization
# ---------------------------------------------------------------------------

class TestValueNormalization:
    def _make_tag(self, text, scale="0", sign="", nil=None):
        import re as _re
        from bs4 import BeautifulSoup
        attrs = f'name="foo:Bar" contextRef="ctx" scale="{scale}"'
        if sign:
            attrs += f' sign="{sign}"'
        if nil:
            attrs += f' xsi:nil="{nil}"'
        html = f'<ix:nonFraction {attrs}>{text}</ix:nonFraction>'
        soup = BeautifulSoup(html, "lxml")
        return soup.find(_re.compile(r"ix:nonfraction", _re.I))

    def test_basic_integer(self):
        tag = self._make_tag("1,234", scale="0")
        assert _normalize_numeric(tag) == 1234

    def test_scale_6_millions_to_yen(self):
        tag = self._make_tag("100,000", scale="6")
        assert _normalize_numeric(tag) == 100_000_000_000

    def test_negative_sign(self):
        tag = self._make_tag("10,000", scale="6", sign="-")
        assert _normalize_numeric(tag) == -10_000_000_000

    def test_nil_returns_none(self):
        tag = self._make_tag("", nil="true")
        assert _normalize_numeric(tag) is None

    def test_empty_text_returns_none(self):
        tag = self._make_tag("-")
        assert _normalize_numeric(tag) is None

    def test_float_value(self):
        tag = self._make_tag("120.50", scale="0")
        assert _normalize_numeric(tag) == 120.50

    def test_large_value(self):
        tag = self._make_tag("9,999,999", scale="6")
        assert _normalize_numeric(tag) == 9_999_999_000_000


# ---------------------------------------------------------------------------
# TestContextClassification
# ---------------------------------------------------------------------------

class TestContextClassification:
    def test_current_year_duration(self):
        assert _classify_context("CurrentYearDuration", {"type": "duration"}) == ("current", "duration")

    def test_current_year_instant(self):
        assert _classify_context("CurrentYearInstant", {"type": "instant"}) == ("current", "instant")

    def test_prior1_year_duration(self):
        assert _classify_context("Prior1YearDuration", {"type": "duration"}) == ("prior1", "duration")

    def test_prior1_year_instant(self):
        assert _classify_context("Prior1YearInstant", {"type": "instant"}) == ("prior1", "instant")

    def test_filing_date_instant(self):
        year, ptype = _classify_context("FilingDateInstant", {"type": "instant"})
        assert year == "filing"
        assert ptype == "instant"

    def test_unknown_context(self):
        year, ptype = _classify_context("SomeRandomContext", {"type": "duration"})
        assert year == "unknown"


# ---------------------------------------------------------------------------
# TestAccountingStandardDetection
# ---------------------------------------------------------------------------

class TestAccountingStandardDetection:
    def test_jp_gaap_default(self):
        elements = {("NetSales", "ctx"): 1000, ("OperatingIncome", "ctx"): 100}
        assert _detect_accounting_standard(elements) == "jp_gaap"

    def test_ifrs_detection(self):
        elements = {("RevenueIFRS", "ctx"): 1000, ("TotalAssetsIFRS", "ctx"): 5000}
        assert _detect_accounting_standard(elements) == "ifrs"

    def test_us_gaap_detection(self):
        elements = {("NetSalesUS", "ctx"): 1000, ("AssetsUS", "ctx"): 5000}
        assert _detect_accounting_standard(elements) == "us_gaap"


# ---------------------------------------------------------------------------
# TestPLExtraction
# ---------------------------------------------------------------------------

class TestPLExtraction:
    def setup_method(self):
        self.htm = _write_temp_html(_make_ixbrl())
        self.elements, self.contexts = _parse_ixbrl(self.htm)

    def teardown_method(self):
        self.htm.unlink(missing_ok=True)

    def test_current_year_net_sales(self):
        pl = _extract_pl(self.elements, self.contexts, "jp_gaap")
        # scale=6, value=100,000 → 100,000 * 10^6 = 100,000,000,000
        assert pl["current_year"]["net_sales"] == 100_000_000_000

    def test_prior_year_net_sales(self):
        pl = _extract_pl(self.elements, self.contexts, "jp_gaap")
        assert pl["prior_year"]["net_sales"] == 90_000_000_000

    def test_operating_income(self):
        pl = _extract_pl(self.elements, self.contexts, "jp_gaap")
        assert pl["current_year"]["operating_income"] == 10_000_000_000

    def test_net_income(self):
        pl = _extract_pl(self.elements, self.contexts, "jp_gaap")
        assert pl["current_year"]["net_income"] == 6_000_000_000

    def test_eps_float(self):
        pl = _extract_pl(self.elements, self.contexts, "jp_gaap")
        assert pl["current_year"]["earnings_per_share"] == 120.50


# ---------------------------------------------------------------------------
# TestBSExtraction
# ---------------------------------------------------------------------------

class TestBSExtraction:
    def setup_method(self):
        self.htm = _write_temp_html(_make_ixbrl())
        self.elements, self.contexts = _parse_ixbrl(self.htm)

    def teardown_method(self):
        self.htm.unlink(missing_ok=True)

    def test_total_assets_current_year(self):
        bs = _extract_bs(self.elements, self.contexts, "jp_gaap")
        assert bs["current_year"]["total_assets"] == 500_000_000_000

    def test_net_assets(self):
        bs = _extract_bs(self.elements, self.contexts, "jp_gaap")
        assert bs["current_year"]["net_assets"] == 200_000_000_000

    def test_prior_year_assets(self):
        bs = _extract_bs(self.elements, self.contexts, "jp_gaap")
        assert bs["prior_year"]["total_assets"] == 480_000_000_000


# ---------------------------------------------------------------------------
# TestCFExtraction
# ---------------------------------------------------------------------------

class TestCFExtraction:
    def setup_method(self):
        self.htm = _write_temp_html(_make_ixbrl())
        self.elements, self.contexts = _parse_ixbrl(self.htm)

    def teardown_method(self):
        self.htm.unlink(missing_ok=True)

    def test_operating_cf(self):
        cf = _extract_cf(self.elements, self.contexts, "jp_gaap")
        assert cf["current_year"]["operating_cf"] == 20_000_000_000

    def test_investing_cf_negative(self):
        cf = _extract_cf(self.elements, self.contexts, "jp_gaap")
        assert cf["current_year"]["investing_cf"] == -10_000_000_000

    def test_financing_cf_negative(self):
        cf = _extract_cf(self.elements, self.contexts, "jp_gaap")
        assert cf["current_year"]["financing_cf"] == -5_000_000_000

    def test_ending_cash_from_instant_context(self):
        cf = _extract_cf(self.elements, self.contexts, "jp_gaap")
        # CashAndCashEquivalents is in CurrentYearInstant context
        assert cf["current_year"]["ending_cash"] == 50_000_000_000


# ---------------------------------------------------------------------------
# TestQualitativeParsing
# ---------------------------------------------------------------------------

class TestQualitativeParsing:
    def setup_method(self):
        self.htm = _write_temp_html(_make_qualitative_html())

    def teardown_method(self):
        self.htm.unlink(missing_ok=True)

    def test_overview_extracted(self):
        result = _parse_qualitative_html(self.htm)
        assert result.overview_of_business_results is not None
        assert "100億円" in result.overview_of_business_results

    def test_financial_condition_extracted(self):
        result = _parse_qualitative_html(self.htm)
        assert result.financial_condition is not None
        assert "500億円" in result.financial_condition

    def test_cash_flow_extracted(self):
        result = _parse_qualitative_html(self.htm)
        assert result.cash_flow_overview is not None
        assert "20億円" in result.cash_flow_overview

    def test_forecast_extracted(self):
        result = _parse_qualitative_html(self.htm)
        assert result.forecast is not None
        assert "110億円" in result.forecast

    def test_other_sections(self):
        result = _parse_qualitative_html(self.htm)
        assert len(result.other_sections) > 0


# ---------------------------------------------------------------------------
# TestZIPHandling
# ---------------------------------------------------------------------------

class TestZIPHandling:
    def _make_zip(self) -> Path:
        """Create an in-memory ZIP archive mimicking TDnet structure."""
        ixbrl_content = _make_ixbrl().encode("utf-8")
        qual_content = _make_qualitative_html().encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("XBRLData/Attachment/E12345-20240331-ixbrl.htm", ixbrl_content)
            zf.writestr("XBRLData/Attachment/qualitative.htm", qual_content)
        buf.seek(0)

        f = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        f.write(buf.read())
        f.close()
        return Path(f.name)

    def test_zip_parses_financials(self):
        zip_path = self._make_zip()
        try:
            result = parse_xbrl(str(zip_path))
            assert result["income_statement"]["current_year"]["net_sales"] == 100_000_000_000
            assert result["balance_sheet"]["current_year"]["total_assets"] == 500_000_000_000
        finally:
            zip_path.unlink(missing_ok=True)

    def test_zip_parses_qualitative(self):
        zip_path = self._make_zip()
        try:
            result = parse_xbrl(str(zip_path))
            assert result["qualitative"] is not None
            assert result["qualitative"]["overview_of_business_results"] is not None
        finally:
            zip_path.unlink(missing_ok=True)

    def test_zip_result_is_json_serializable(self):
        zip_path = self._make_zip()
        try:
            result = parse_xbrl(str(zip_path))
            json_str = json.dumps(result, ensure_ascii=False)
            assert len(json_str) > 0
        finally:
            zip_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# TestCompanyInfo
# ---------------------------------------------------------------------------

class TestCompanyInfo:
    def setup_method(self):
        self.htm = _write_temp_html(_make_ixbrl())
        self.elements, _ = _parse_ixbrl(self.htm)

    def teardown_method(self):
        self.htm.unlink(missing_ok=True)

    def test_company_name(self):
        info = _extract_company_info(self.elements)
        assert info["company_name"] == "テスト株式会社"

    def test_fiscal_year_end(self):
        info = _extract_company_info(self.elements)
        assert info["fiscal_year_end"] == "2024-03-31"

    def test_document_type(self):
        info = _extract_company_info(self.elements)
        assert info["document_type"] == "決算短信"


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_ifrs_elements_recognized(self):
        ifrs_extra = """
<ix:nonFraction name="tse-ed-t:RevenueIFRS" contextRef="CurrentYearDuration" unitRef="JPY" scale="6">50,000</ix:nonFraction>
<ix:nonFraction name="tse-ed-t:TotalAssetsIFRS" contextRef="CurrentYearInstant" unitRef="JPY" scale="6">800,000</ix:nonFraction>
"""
        htm = _write_temp_html(_make_ixbrl(extra_elements=ifrs_extra))
        try:
            elements, contexts = _parse_ixbrl(htm)
            std = _detect_accounting_standard(elements)
            assert std == "ifrs"
            pl = _extract_pl(elements, contexts, std)
            assert pl["current_year"]["net_sales"] == 50_000_000_000
        finally:
            htm.unlink(missing_ok=True)

    def test_nil_value_returns_none(self):
        nil_extra = """
<ix:nonFraction name="tse-ed-t:GrossProfit" contextRef="CurrentYearDuration"
  unitRef="JPY" scale="6" xsi:nil="true"></ix:nonFraction>
"""
        htm = _write_temp_html(_make_ixbrl(extra_elements=nil_extra))
        try:
            elements, contexts = _parse_ixbrl(htm)
            pl = _extract_pl(elements, contexts, "jp_gaap")
            assert pl["current_year"]["gross_profit"] is None
        finally:
            htm.unlink(missing_ok=True)

    def test_nonconsolidated_detection(self):
        extra_ctx = """
<xbrli:context id="CurrentYearNonConsolidatedDuration">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E12345-000</xbrli:identifier>
    <xbrli:segment>
      <xbrldi:explicitMember dimension="jpcrp_cor:ConsolidatedOrNonConsolidatedAxis">jpcrp_cor:NonConsolidatedMember</xbrldi:explicitMember>
    </xbrli:segment>
  </xbrli:entity>
  <xbrli:period><xbrli:startDate>2023-04-01</xbrli:startDate><xbrli:endDate>2024-03-31</xbrli:endDate></xbrli:period>
</xbrli:context>
"""
        htm = _write_temp_html(_make_ixbrl(extra_contexts=extra_ctx))
        try:
            _, contexts = _parse_ixbrl(htm)
            consolidation = _detect_consolidation(contexts)
            assert consolidation == "nonconsolidated"
        finally:
            htm.unlink(missing_ok=True)

    def test_missing_cf_no_crash(self):
        """Parsing a file with no CF data should return None fields, not raise."""
        htm = _write_temp_html(_make_ixbrl())
        try:
            elements, contexts = _parse_ixbrl(htm)
            # Remove CF elements
            cf_keys = [k for k in elements if "CashFlow" in k[0] or "Cash" in k[0]]
            for k in cf_keys:
                del elements[k]
            cf = _extract_cf(elements, contexts, "jp_gaap")
            # Should not raise; values may be None
            assert isinstance(cf, dict)
        finally:
            htm.unlink(missing_ok=True)

    def test_large_monetary_value(self):
        large_extra = """
<ix:nonFraction name="tse-ed-t:NetSales" contextRef="CurrentYearDuration" unitRef="JPY" scale="6">9,999,999</ix:nonFraction>
"""
        htm = _write_temp_html(_make_ixbrl(extra_elements=large_extra))
        try:
            elements, contexts = _parse_ixbrl(htm)
            pl = _extract_pl(elements, contexts, "jp_gaap")
            assert pl["current_year"]["net_sales"] == 9_999_999_000_000
        finally:
            htm.unlink(missing_ok=True)

    def test_parse_result_has_no_warnings_for_valid_data(self):
        zip_path = TestZIPHandling()._make_zip()
        try:
            result = parse_xbrl(str(zip_path))
            assert result["parse_warnings"] == []
        finally:
            zip_path.unlink(missing_ok=True)
