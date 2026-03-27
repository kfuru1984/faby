"""yfinance を使ったデータ取得・TTLキャッシュロジック"""
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=300)  # 5分キャッシュ
def fetch_snapshot(tickers: tuple[str, ...]) -> pd.DataFrame:
    """現在値・前日比・PER・時価総額を取得して DataFrame で返す。

    Args:
        tickers: ティッカーシンボルのタプル（キャッシュキーとして hashable が必要）

    Returns:
        columns: ticker, name, price, change_pct, pe_ratio, market_cap, currency
    """
    records: list[dict[str, Any]] = []
    for ticker_sym in tickers:
        try:
            t = yf.Ticker(ticker_sym)
            info = t.info
            records.append({
                "ticker": ticker_sym,
                "name": info.get("shortName", ticker_sym),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "change_pct": info.get("regularMarketChangePercent"),
                "pe_ratio": info.get("trailingPE"),
                "market_cap": info.get("marketCap"),
                "currency": info.get("currency", "USD"),
            })
        except Exception as e:  # noqa: BLE001
            records.append({
                "ticker": ticker_sym,
                "name": ticker_sym,
                "price": None,
                "change_pct": None,
                "pe_ratio": None,
                "market_cap": None,
                "currency": "USD",
                "error": str(e),
            })
    return pd.DataFrame(records)


@st.cache_data(ttl=300)  # 5分キャッシュ
def fetch_history(tickers: tuple[str, ...], days: int = 30) -> pd.DataFrame:
    """過去 N 日間の終値を取得し、始点を 100 に正規化して返す。

    Args:
        tickers: ティッカーシンボルのタプル
        days: 取得する日数（デフォルト30日）

    Returns:
        DatetimeIndex × ticker の DataFrame（正規化済み）
    """
    end = datetime.today()
    start = end - timedelta(days=days)
    try:
        raw = yf.download(
            list(tickers),
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )["Close"]
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(tickers[0])
        normalized = raw / raw.iloc[0] * 100
        return normalized
    except Exception:
        return pd.DataFrame()
