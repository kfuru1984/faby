"""ページ構造・サイドバーのレイアウト定義"""
import streamlit as st

from config.tickers import DEFAULT_GROUP, TICKER_GROUPS
from data.fetcher import fetch_history, fetch_snapshot
from ui.components import render_chart, render_kpi_cards, render_summary_table


def render_layout() -> None:
    """メインレイアウトを描画する。"""
    # サイドバー
    with st.sidebar:
        st.title("faby 📈")
        st.caption("株式市場ダッシュボード")
        st.divider()

        selected_group = st.selectbox(
            "銘柄グループ",
            options=list(TICKER_GROUPS.keys()),
            index=list(TICKER_GROUPS.keys()).index(DEFAULT_GROUP),
        )

        st.divider()
        if st.button("🔄 データ更新", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption("※ データは5分ごとに自動更新されます")

    # メインエリア
    group_tickers = TICKER_GROUPS[selected_group]
    tickers_tuple = tuple(group_tickers.keys())

    st.header(f"{selected_group}")

    with st.spinner("データ取得中..."):
        snapshot_df = fetch_snapshot(tickers_tuple)
        history_df = fetch_history(tickers_tuple)

    # KPI カード
    render_kpi_cards(snapshot_df, group_tickers)

    st.divider()

    # タブ: チャート / テーブル
    tab_chart, tab_table = st.tabs(["📊 パフォーマンスチャート", "📋 詳細テーブル"])

    with tab_chart:
        render_chart(history_df, selected_group)

    with tab_table:
        render_summary_table(snapshot_df, group_tickers)
