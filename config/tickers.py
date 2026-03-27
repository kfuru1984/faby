"""銘柄設定・グループ定義"""
from typing import TypedDict


class TickerInfo(TypedDict):
    name: str
    currency: str
    exchange: str


# 銘柄グループ定義
TICKER_GROUPS: dict[str, dict[str, TickerInfo]] = {
    "グローバルSPE/装置": {
        "ASML": {"name": "ASML", "currency": "USD", "exchange": "NASDAQ"},
        "AMAT": {"name": "アプライドマテリアルズ", "currency": "USD", "exchange": "NASDAQ"},
        "LRCX": {"name": "ラムリサーチ", "currency": "USD", "exchange": "NASDAQ"},
        "KLAC": {"name": "KLAコーポレーション", "currency": "USD", "exchange": "NASDAQ"},
    },
    "AI/GPU": {
        "NVDA": {"name": "NVIDIA", "currency": "USD", "exchange": "NASDAQ"},
        "AMD": {"name": "AMD", "currency": "USD", "exchange": "NASDAQ"},
        "TSM": {"name": "TSMC", "currency": "USD", "exchange": "NYSE"},
    },
    "日本株SPE": {
        "8035.T": {"name": "東京エレクトロン", "currency": "JPY", "exchange": "TSE"},
        "6857.T": {"name": "アドバンテスト", "currency": "JPY", "exchange": "TSE"},
        "6146.T": {"name": "ディスコ", "currency": "JPY", "exchange": "TSE"},
        "7735.T": {"name": "大日本スクリーン製造", "currency": "JPY", "exchange": "TSE"},
    },
    "日本株グロース": {
        "6367.T": {"name": "ダイキン工業", "currency": "JPY", "exchange": "TSE"},
        "6758.T": {"name": "ソニーグループ", "currency": "JPY", "exchange": "TSE"},
        "9984.T": {"name": "ソフトバンクグループ", "currency": "JPY", "exchange": "TSE"},
        "4063.T": {"name": "信越化学工業", "currency": "JPY", "exchange": "TSE"},
    },
}

# デフォルト選択グループ
DEFAULT_GROUP = "グローバルSPE/装置"
