"""RSSエージェント - feedparser で複数フィードを並列取得"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import feedparser

logger = logging.getLogger(__name__)


class RSSAgent:
    def __init__(self, config: dict[str, Any]):
        self.feeds = config.get("rss_feeds", [])
        self.max_items = config.get("output", {}).get("max_items_per_feed", 10)

    def _fetch_feed(self, feed: dict[str, str]) -> list[dict[str, Any]]:
        """単一フィードを取得してアイテムリストを返す"""
        name = feed.get("name", "")
        url = feed.get("url", "")
        logger.info(f"[RSS] 取得中: {name}")

        try:
            parsed = feedparser.parse(url)
            items = []
            for entry in parsed.entries[: self.max_items]:
                # 公開日時の取得
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                items.append(
                    {
                        "title": getattr(entry, "title", "タイトルなし"),
                        "summary": getattr(entry, "summary", ""),
                        "url": getattr(entry, "link", ""),
                        "source": name,
                        "published": published,
                        "published_str": published.strftime("%Y-%m-%d %H:%M") if published else "日時不明",
                    }
                )
            logger.info(f"[RSS] {name}: {len(items)}件取得")
            return items
        except Exception as e:
            logger.error(f"[RSS] {name} 取得エラー: {e}")
            return []

    async def run(self) -> list[dict[str, Any]]:
        """全フィードを並列取得して公開日時降順でソート"""
        logger.info(f"[RSS] {len(self.feeds)}フィードの取得開始")

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=min(len(self.feeds), 8)) as executor:
            tasks = [
                loop.run_in_executor(executor, self._fetch_feed, feed) for feed in self.feeds
            ]
            results = await asyncio.gather(*tasks)

        # フラット化して公開日時降順ソート
        all_items: list[dict[str, Any]] = []
        for items in results:
            all_items.extend(items)

        all_items.sort(
            key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        logger.info(f"[RSS] 完了 - 合計{len(all_items)}件取得")
        return all_items
