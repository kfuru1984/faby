"""再利用可能な UI コンポーネント"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.tickers import TickerInfo


def _format_price(price: float | None, currency: str) -> str:
    """価格を通貨に応じたフォーマットで返す。"""
    if price is None:
        return "N/A"
    if currency == "JPY":
        return f"¥{price:,.0f}"
    return f"${price:,.2f}"


def _format_market_cap(market_cap: float | None) -> str:
    """時価総額を兆/億単位でフォーマットする。"""
    if market_cap is None:
        return "N/A"
    if market_cap >= 1e12:
        return f"{market_cap / 1e12:.1f}兆"
    if market_cap >= 1e8:
        return f"{market_cap / 1e8:.0f}億"
    return f"{market_cap:,.0f}"


def render_kpi_cards(
    snapshot_df: pd.DataFrame,
    group_tickers: dict[str, TickerInfo],
) -> None:
    """銘柄ごとに KPI カードを表示する。"""
    cols = st.columns(len(snapshot_df))
    for col, (_, row) in zip(cols, snapshot_df.iterrows()):
        ticker_info = group_tickers.get(row["ticker"], {})
        name = ticker_info.get("name", row["ticker"])
        currency = row.get("currency", "USD")
        price_str = _format_price(row["price"], currency)
        change_pct = row["change_pct"]
        delta_str = f"{change_pct:+.2f}%" if change_pct is not None else None
        with col:
            st.metric(
                label=f"{name}\n({row['ticker']})",
                value=price_str,
                delta=delta_str,
            )


def render_chart(history_df: pd.DataFrame, title: str) -> None:
    """正規化パフォーマンスチャートを表示する（100基点）。"""
    if history_df.empty:
        st.warning("チャートデータを取得できませんでした。")
        return

    fig = go.Figure()
    for col in history_df.columns:
        fig.add_trace(
            go.Scatter(
                x=history_df.index,
                y=history_df[col],
                mode="lines",
                name=col,
                hovertemplate="%{x}<br>%{y:.1f}<extra>%{fullData.name}</extra>",
            )
        )

    fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(
        title=f"{title} - 相対パフォーマンス（30日間、100基点）",
        xaxis_title="日付",
        yaxis_title="パフォーマンス（基点=100）",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_summary_table(
    snapshot_df: pd.DataFrame,
    group_tickers: dict[str, TickerInfo],
) -> None:
    """銘柄の詳細テーブルを表示する。"""
    rows = []
    for _, row in snapshot_df.iterrows():
        ticker_info = group_tickers.get(row["ticker"], {})
        currency = row.get("currency", "USD")
        rows.append({
            "銘柄": ticker_info.get("name", row["ticker"]),
            "ティッカー": row["ticker"],
            "取引所": ticker_info.get("exchange", "-"),
            "株価": _format_price(row["price"], currency),
            "前日比": f"{row['change_pct']:+.2f}%" if row["change_pct"] is not None else "N/A",
            "PER": f"{row['pe_ratio']:.1f}x" if row["pe_ratio"] is not None else "N/A",
            "時価総額": _format_market_cap(row["market_cap"]),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
