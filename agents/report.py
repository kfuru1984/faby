"""レポートビルダー - Markdownレポートを生成してファイルに保存"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

IMPORTANCE_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "⚪",
}

SECTION_TITLES = {
    "macro": "マクロ経済",
    "geopolitical": "地政学リスク",
    "semiconductor": "半導体セクター",
    "watchlist": "ウォッチ銘柄",
}


class ReportBuilder:
    def __init__(self, config: dict[str, Any]):
        self.report_dir = config.get("output", {}).get("report_dir", "./output")
        os.makedirs(self.report_dir, exist_ok=True)

    def _importance_badge(self, importance: str) -> str:
        return IMPORTANCE_EMOJI.get(importance, "⚪")

    def _build_web_section(self, title: str, items: list[dict[str, Any]]) -> str:
        if not items:
            return f"## {title}\n\n情報なし\n\n"

        lines = [f"## {title}\n"]
        for item in items:
            badge = self._importance_badge(item.get("importance", "low"))
            item_title = item.get("title", "タイトルなし")
            summary = item.get("summary", "")
            source = item.get("source", "")
            url = item.get("url", "")

            lines.append(f"### {badge} {item_title}")
            if summary:
                lines.append(f"\n{summary}")
            meta_parts = []
            if source:
                meta_parts.append(f"出所: {source}")
            if url:
                meta_parts.append(f"[リンク]({url})")
            if meta_parts:
                lines.append(f"\n> {' | '.join(meta_parts)}")
            lines.append("")

        return "\n".join(lines) + "\n"

    def _build_watchlist_section(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "## ウォッチ銘柄\n\n情報なし\n\n"

        # 銘柄コードでグループ化
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            key = f"{item.get('stock_name', '')} ({item.get('stock_code', '')})"
            grouped.setdefault(key, []).append(item)

        lines = ["## ウォッチ銘柄\n"]
        for stock_key, stock_items in grouped.items():
            lines.append(f"### {stock_key}")
            for item in stock_items:
                badge = self._importance_badge(item.get("importance", "low"))
                item_title = item.get("title", "タイトルなし")
                summary = item.get("summary", "")
                url = item.get("url", "")
                lines.append(f"\n**{badge} {item_title}**")
                if summary:
                    lines.append(f"\n{summary}")
                if url:
                    lines.append(f"\n> [リンク]({url})")
            lines.append("")

        return "\n".join(lines) + "\n"

    def _build_rss_section(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "## RSSニュース\n\n情報なし\n\n"

        lines = ["## RSSニュース\n"]
        for item in items:
            pub = item.get("published_str", "日時不明")
            source = item.get("source", "")
            title = item.get("title", "タイトルなし")
            url = item.get("url", "")
            summary = item.get("summary", "")

            if url:
                lines.append(f"- **[{title}]({url})**")
            else:
                lines.append(f"- **{title}**")

            meta = f"  {pub}"
            if source:
                meta += f" | {source}"
            lines.append(meta)

            if summary:
                # summaryが長い場合は切り詰める
                short_summary = summary[:120] + "…" if len(summary) > 120 else summary
                lines.append(f"  {short_summary}")
            lines.append("")

        return "\n".join(lines) + "\n"

    def build(
        self,
        web_results: dict[str, list[dict[str, Any]]],
        rss_items: list[dict[str, Any]],
    ) -> str:
        """Markdownレポートを生成してファイルに保存、パスを返す"""
        now = datetime.now(JST)
        date_str = now.strftime("%Y年%m月%d日")
        time_str = now.strftime("%H:%M")
        filename = now.strftime("report_%Y%m%d_%H%M.md")
        filepath = os.path.join(self.report_dir, filename)

        sections = [
            f"# 日本株マーケットリサーチ - {date_str}\n",
            f"> レポート生成時刻: {date_str} {time_str} JST\n",
            "---\n",
            self._build_web_section("マクロ経済", web_results.get("macro", [])),
            "---\n",
            self._build_web_section("地政学リスク", web_results.get("geopolitical", [])),
            "---\n",
            self._build_web_section("半導体セクター", web_results.get("semiconductor", [])),
            "---\n",
            self._build_watchlist_section(web_results.get("watchlist", [])),
            "---\n",
            self._build_rss_section(rss_items),
        ]

        content = "\n".join(sections)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"[レポート] 保存完了: {filepath}")
        return filepath, content
