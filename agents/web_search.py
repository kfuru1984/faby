"""Web検索エージェント - Claude web_search ツールを使用して日本株関連ニュースを収集"""

import json
import logging
from datetime import date
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

SEARCH_CATEGORIES = {
    "macro": "マクロ経済",
    "geopolitical": "地政学リスク",
    "semiconductor": "半導体",
    "watchlist": "ウォッチ銘柄",
}


class WebSearchAgent:
    def __init__(self, config: dict[str, Any]):
        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 環境変数から自動取得
        self.model = "claude-sonnet-4-20250514"
        self.config = config
        self.max_results = config.get("output", {}).get("max_web_results", 5)

    def _build_search_prompt(self, category: str, query: str) -> str:
        today = date.today().strftime("%Y年%m月%d日")
        return (
            f"以下のトピックについて、{today}時点の最新情報を日本語で検索・収集してください。\n\n"
            f"カテゴリ: {SEARCH_CATEGORIES.get(category, category)}\n"
            f"検索クエリ: {query}\n\n"
            f"結果は必ず以下のJSON形式のみで返してください（他のテキストは不要）:\n"
            f'{{"items": [{{'
            f'"title": "記事タイトル", '
            f'"summary": "100文字程度の要約", '
            f'"source": "情報源名", '
            f'"url": "URL", '
            f'"importance": "high|medium|low"'
            f"}}]}}\n\n"
            f"重要度の基準:\n"
            f"- high: 市場に大きな影響を与える可能性がある\n"
            f"- medium: 注目すべき動向\n"
            f"- low: 参考情報\n\n"
            f"最大{self.max_results}件の結果を返してください。"
        )

    def _search_single(self, category: str, query: str) -> dict[str, Any]:
        """単一クエリの検索を実行"""
        prompt = self._build_search_prompt(category, query)
        logger.info(f"[Web検索] カテゴリ: {category} / クエリ: {query}")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )

            # テキストブロックからJSON抽出
            result_text = ""
            for block in response.content:
                if block.type == "text":
                    result_text += block.text

            # JSONパース
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(result_text[start:end])
                return {"category": category, "query": query, "items": data.get("items", [])}

        except json.JSONDecodeError as e:
            logger.warning(f"[Web検索] JSONパースエラー ({category}): {e}")
        except anthropic.APIError as e:
            logger.error(f"[Web検索] API エラー ({category}): {e}")

        return {"category": category, "query": query, "items": []}

    def search_category(self, category: str) -> list[dict[str, Any]]:
        """カテゴリ別の検索を実行"""
        topics = self.config.get("search_topics", {}).get(category, [])
        results = []
        for query in topics:
            result = self._search_single(category, query)
            results.extend(result.get("items", []))
        return results

    def search_watchlist(self) -> list[dict[str, Any]]:
        """ウォッチリスト銘柄の個別検索"""
        watchlist = self.config.get("watchlist", [])
        today = date.today().strftime("%Y年%m月%d日")
        results = []

        for stock in watchlist:
            name = stock.get("name", "")
            code = stock.get("code", "")
            query = f"{name} {code} ニュース {today}"
            result = self._search_single("watchlist", query)
            items = result.get("items", [])
            # 銘柄情報を付与
            for item in items:
                item["stock_code"] = code
                item["stock_name"] = name
            results.extend(items)

        return results

    async def run(self) -> dict[str, list[dict[str, Any]]]:
        """全カテゴリの検索を実行して結果を返す"""
        logger.info("[Web検索] 検索開始")
        results = {
            "macro": self.search_category("macro"),
            "geopolitical": self.search_category("geopolitical"),
            "semiconductor": self.search_category("semiconductor"),
            "watchlist": self.search_watchlist(),
        }
        total = sum(len(v) for v in results.values())
        logger.info(f"[Web検索] 完了 - 合計{total}件取得")
        return results
