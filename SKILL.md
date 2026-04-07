---
name: xbrl-parsing
description: TDnet 決算短信 XBRL ファイル（ZIP形式またはiXBRL .htm）を解析して財務三表（BS/PL/CF）と定性情報（経営成績の概要など）をJSONで抽出する。ユーザーがTDnet・XBRL・決算短信・財務諸表ファイルの解析・財務データ抽出を依頼したときに使用する。
---

# TDnet XBRL 解析スキル

TDnetの決算短信XBRLファイル（ZIP形式）から財務三表（BS/PL/CF）と定性情報を抽出する。

## TDnet XBRL の構造

TDnetのXBRLは **Inline XBRL（iXBRL）** 形式。ZIPを展開すると以下の構成:

```
XBRLData/
├── Attachment/
│   ├── *-ixbrl.htm     ← 財務諸表（HTMLに<ix:nonFraction>タグで数値が埋め込まれている）
│   ├── qualitative.htm ← 定性情報（プレーンHTML: 経営成績の概要、財政状態など）
│   ├── *-lab.xml       ← 日本語ラベルリンクベース
│   └── manifest.xml
└── Summary/
    └── *-ixbrl.htm     ← 決算短信サマリー（iXBRL）
```

**iXBRL 数値タグの例**:
```html
<ix:nonFraction name="tse-ed-t:NetSales" contextRef="CurrentYearDuration"
  unitRef="JPY" scale="6" decimals="-6">100,000</ix:nonFraction>
```
→ `100,000 × 10^6 = 100,000,000,000 円`

**コンテキストID の命名規則**:
- `CurrentYearDuration` — 当期（損益計算書・CF計算書）
- `CurrentYearInstant` — 当期末（貸借対照表）
- `Prior1YearDuration` / `Prior1YearInstant` — 前期
- `FilingDateInstant` — 提出日（会社名・期末日などのDEI情報）

---

## ワークフロー

作業項目をTodoリストで管理し、1つずつ実行する。

### 1. 入力ファイルの確認

ユーザーが指定したファイルパスを確認する:
- `.zip` → TDnet ZIPアーカイブ（最も一般的）
- `*-ixbrl.htm` → 個別iXBRLファイル
- ディレクトリ → 展開済みの XBRLData フォルダ

ファイルが存在することを確認する（Bashで `ls -lh <path>`）。

### 2. パーサーの実行

`/home/user/faby` ディレクトリにあるパーサーを使用する:

```bash
cd /home/user/faby
python3 -c "
import json, sys
sys.path.insert(0, 'src')
from xbrl_parser import parse_xbrl
result = parse_xbrl(sys.argv[1])
print(json.dumps(result, ensure_ascii=False, indent=2))
" "<ファイルパス>"
```

初回実行時は依存ライブラリをインストール:
```bash
cd /home/user/faby && pip install -r requirements.txt
```

### 3. 警告の確認と説明

`parse_warnings` フィールドを確認し、ユーザーに説明する:
- `"No income statement data found."` → PLデータが見つからない（財務諸表以外のファイルの可能性）
- `"No balance sheet data found."` → BSデータが見つからない
- `"Failed to parse qualitative.htm"` → 定性情報の解析失敗（財務数値は利用可能）

### 4. 財務三表の提示

JSON結果から財務三表をMarkdown表形式で整理して提示する:

**損益計算書（PL）**:
| 項目 | 当期 | 前期 |
|------|------|------|
| 売上高 | xxx百万円 | xxx百万円 |
| 営業利益 | xxx百万円 | xxx百万円 |
| 経常利益 | xxx百万円 | xxx百万円 |
| 当期純利益 | xxx百万円 | xxx百万円 |
| EPS | xxx円 | - |

**貸借対照表（BS）**・**キャッシュフロー計算書（CF）** も同様に表形式で提示する。

金額は `value / 1_000_000` で百万円単位に変換して表示すると読みやすい。

### 5. 定性情報の提示

`qualitative` フィールドが存在する場合:
- `overview_of_business_results` — 経営成績の概要
- `financial_condition` — 財政状態の概況
- `cash_flow_overview` — キャッシュ・フローの状況
- `forecast` — 業績予想
- `other_sections` — その他のセクション

各テキストを見出しとともに提示する。長文の場合は冒頭100文字程度を要約する。

### 6. エラー時の診断

パーサーが完全に失敗した場合の診断手順:

```bash
# iXBRLファイル内のix:nonFractionタグを確認
python3 -c "
from bs4 import BeautifulSoup
import glob, os
files = glob.glob('<展開ディレクトリ>/**/*ixbrl.htm', recursive=True)
for f in files[:3]:
    soup = BeautifulSoup(open(f).read(), 'lxml')
    tags = soup.find_all(re.compile('ix:nonfraction', re.I))
    print(f'{f}: {len(tags)} numeric elements found')
    if tags:
        print('  Sample:', tags[0])
"
```

- タグが見つからない → EDINET形式（純粋なXBRL）の可能性。ファイル拡張子が `.xbrl` か確認。
- 要素名が異なる → 会社独自の拡張要素を使用。`name` 属性のローカル部分を確認して候補リストに追加。

### 7. 複数ファイルの比較（オプション）

複数のZIPファイル（例：四半期シリーズ）を比較する場合:

```python
import json, sys
sys.path.insert(0, '/home/user/faby/src')
from xbrl_parser import parse_xbrl

files = ["Q1.zip", "Q2.zip", "Q3.zip", "Q4.zip"]
results = {f: parse_xbrl(f) for f in files}

# 売上高の推移
for f, r in results.items():
    net_sales = r["income_statement"]["current_year"].get("net_sales")
    print(f"{f}: 売上高 = {net_sales / 1_000_000:,.0f}百万円" if net_sales else f"{f}: データなし")
```

---

## 出力JSONスキーマ

```json
{
  "company_name": "株式会社サンプル",
  "fiscal_year_end": "2024-03-31",
  "document_type": "決算短信",
  "accounting_standard": "jp_gaap",
  "consolidation": "consolidated",
  "income_statement": {
    "current_year": {
      "net_sales": 100000000000,
      "gross_profit": null,
      "operating_income": 10000000000,
      "ordinary_income": 9500000000,
      "profit_before_tax": 9000000000,
      "net_income": 6000000000,
      "earnings_per_share": 120.5
    },
    "prior_year": { "net_sales": 90000000000, "..." : "..." }
  },
  "balance_sheet": {
    "current_year": {
      "total_assets": 500000000000,
      "current_assets": 200000000000,
      "noncurrent_assets": 300000000000,
      "total_liabilities": 300000000000,
      "net_assets": 200000000000
    },
    "prior_year": { "..." : "..." }
  },
  "cash_flow": {
    "current_year": {
      "operating_cf": 20000000000,
      "investing_cf": -10000000000,
      "financing_cf": -5000000000,
      "ending_cash": 50000000000
    },
    "prior_year": { "..." : "..." }
  },
  "qualitative": {
    "overview_of_business_results": "当期の売上高は前期比10%増の...",
    "financial_condition": "当期末の総資産は...",
    "cash_flow_overview": "営業活動によるキャッシュ・フローは...",
    "forecast": "次期は売上高...",
    "other_sections": {
      "配当の状況": "1株当たり配当金は50円..."
    }
  },
  "parse_warnings": []
}
```

---

## 会計基準別の注意点

| 会計基準 | `accounting_standard` | 売上高要素名 | 主な違い |
|------|------|------|------|
| 日本基準 | `jp_gaap` | NetSales | 経常利益あり |
| IFRS | `ifrs` | RevenueIFRS | 経常利益なし、OCI項目あり |
| 米国基準 | `us_gaap` | NetSalesUS | 米国会計基準 |

IFRSの場合、`ordinary_income` は `null` になる（概念が存在しない）。

---

## ラップアップ

解析完了後、ユーザーへの最終メッセージには以下を含める:
- 会社名・決算期・会計基準・連結/単体の確認
- 財務三表の要約表
- 定性情報の主要セクション
- `parse_warnings` の内容（あれば）
- 追加分析の提案（営業利益率、ROE、前期比増減率など）
