# faby

日本株・グローバル株式市場のデータ可視化・分析ダッシュボード。

## 概要

[claude_project](https://github.com/kfuru1984/claude_project) の日本株グロース銘柄・半導体サプライチェーン分析と連携した株式市場ダッシュボード。
yfinance からリアルタイムデータを取得し、Streamlit でインタラクティブに可視化する。

## 機能

- **リアルタイム株価表示**: 日本株（TSE）・米国株（NASDAQ/NYSE）の現在値・前日比
- **パフォーマンスチャート**: 30日間の相対パフォーマンス比較（100基点に正規化）
- **KPIカード**: 株価・前日比・PER・時価総額を一覧表示
- **銘柄グループ選択**: セクター別（半導体SPE、AI/GPU、日本株等）に銘柄をフィルタリング
- **自動キャッシュ**: 5分間のTTLキャッシュでAPI呼び出し回数を最小化

## セットアップ

### 必要環境
- Python 3.11+

### インストール

```bash
pip install -r requirements.txt
```

### 起動

```bash
streamlit run app.py
```

ブラウザが自動的に `http://localhost:8501` を開きます。

## プロジェクト構成

```
faby/
├── app.py                  # Streamlit エントリーポイント
├── requirements.txt        # Python 依存パッケージ
├── CLAUDE.md              # プロジェクトルール・開発ガイドライン
├── config/
│   └── tickers.py         # 銘柄設定・グループ定義
├── data/
│   └── fetcher.py         # データ取得・キャッシュロジック
└── ui/
    ├── layout.py          # ページ構造・サイドバー
    └── components.py      # 再利用可能な UI コンポーネント
```

## 関連リポジトリ

- [claude_project](https://github.com/kfuru1984/claude_project): 日本株グロース銘柄・半導体マルチエージェント分析システム
