"""Japan Equity Research Agent - メインエントリーポイント"""

import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from agents import GmailSender, ReportBuilder, RSSAgent, WebSearchAgent

# ロギング設定（日本語）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        logger.error(f"設定ファイルが見つかりません: {path}")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main() -> None:
    now = datetime.now(JST)
    logger.info(f"=== Japan Equity Research Agent 起動 ({now.strftime('%Y-%m-%d %H:%M JST')}) ===")

    # 設定読み込み
    config = load_config()
    logger.info("設定ファイルを読み込みました")

    # エージェント初期化
    web_agent = WebSearchAgent(config)
    rss_agent = RSSAgent(config)
    report_builder = ReportBuilder(config)
    gmail_sender = GmailSender()

    # Web検索とRSS取得を並列実行
    logger.info("Web検索・RSS取得を並列実行中...")
    web_task = asyncio.create_task(web_agent.run())
    rss_task = asyncio.create_task(rss_agent.run())

    web_results, rss_items = await asyncio.gather(web_task, rss_task)

    logger.info(
        f"データ収集完了 - Web: {sum(len(v) for v in web_results.values())}件 / RSS: {len(rss_items)}件"
    )

    # レポート生成
    logger.info("レポートを生成中...")
    filepath, content = report_builder.build(web_results, rss_items)
    logger.info(f"レポート生成完了: {filepath}")

    # Gmail送信
    date_label = now.strftime("%Y/%m/%d")
    subject = f"【日本株リサーチ】{date_label} マーケットレポート"
    logger.info("Gmailでレポートを送信中...")
    gmail_sender.send(subject, content)

    logger.info("=== 全処理完了 ===")


if __name__ == "__main__":
    asyncio.run(main())
