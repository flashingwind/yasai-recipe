# 🥬 野菜市況・レシピ提案

東京中央卸売市場の野菜市況データを自動取得し、Claude API でレシピ・ランキングを生成して静的サイトとしてホストするシステムです。

## 🌐 サイト

https://yasai.2-b.jp

## 📋 概要

毎週金曜日 9:00 JST に自動実行されるワークフローで：

1. **市況データ取得** (`scrape_market_comment.py`)
   - 東京都中央卸売市場の果実取扱い PDF から最新の市況データを取得
   - CSV ファイルとして保存

2. **レシピ・ランキング生成** (`recommend_recipes.py`)
   - Claude API で入荷量・相場に基づくおすすめ果実ランキングを生成
   - 各果実に合った簡単レシピを提案
   - キャッシュにより無駄な API 呼び出しを削減

3. **静的サイトビルド** (`build_site.py`)
   - CSV + レシピキャッシュから `docs/index.html` を生成
   - ランキング、レシピ、市況データテーブルを表示

4. **GitHub Pages デプロイ**
   - `docs/` フォルダから自動デプロイ
   - カスタムドメイン `yasai.2-b.jp` で公開

## 🏗️ プロジェクト構造

```
.
├── scrape_market_comment.py    # 市況データスクレイピング
├── recommend_recipes.py        # Claude API でレシピ生成
├── build_site.py               # 静的サイト生成
├── app.py                       # Flask ローカルサーバー (オプション)
├── .github/workflows/
│   └── update.yml              # GitHub Actions 自動実行ワークフロー
├── docs/
│   └── index.html              # 生成された静的サイト
├── .cache/                      # レシピ JSON キャッシュ
├── market_data_*.csv           # 取得した市況データ
└── recipes_*.json              # レシピ JSON
```

## 🚀 セットアップ

### 必要な環境

- Python 3.11+
- Anthropic API キー (Claude API 使用)
- GitHub アカウント

### インストール

```bash
# 依存パッケージをインストール
pip install requests beautifulsoup4 pypdf anthropic flask

# .env に API キーを設定
echo "ANTHROPIC_API_KEY=sk-ant-api03-..." > .env
```

### ローカル実行

```bash
# 市況データを取得
python scrape_market_comment.py

# レシピを生成
python recommend_recipes.py

# サイトをビルド
python build_site.py

# ローカルサーバーで確認 (オプション)
python app.py
# http://localhost:5000 でアクセス
```

## 📊 GitHub Actions ワークフロー

`.github/workflows/update.yml` で定義：

- **スケジュール**: 毎週金曜日 9:00 JST (`0 0 * * 5`)
- **手動実行**: GitHub Actions タブから手動実行可能 (`workflow_dispatch`)

ワークフローは以下を実行：
1. Python 3.11 をセットアップ
2. 依存パッケージをインストール
3. `.cache/` ディレクトリをキャッシュから復元 (API 呼び出し削減)
4. `scrape_market_comment.py` を実行
5. `recommend_recipes.py` を実行 (環境変数 `ANTHROPIC_API_KEY` で認証)
6. `build_site.py` を実行
7. 生成ファイルをコミット・プッシュ

## 🔄 Claude API キャッシング

`recommend_recipes.py` では、同じ週のデータに対する Claude API 呼び出しを最小化するため：

- `.cache/recipe_{week}.json` にキャッシュを保存
- ワークフロー実行時にキャッシュを復元
- 同じ週のデータに対する 2 回目以降の実行では API を呼ばない

## 🛠️ カスタマイズ

### ランキング条件を変更する

`recommend_recipes.py` の `system_prompt` を編集して、ランキングの条件を変更できます。

### スケジュールを変更する

`.github/workflows/update.yml` の `cron` 値を編集：
- `"0 0 * * 5"` → 毎週金曜日 00:00 UTC (09:00 JST)
- `"0 9 * * 1"` → 毎週月曜日 09:00 UTC (18:00 JST)

## 📝 ファイル説明

### scrape_market_comment.py

東京中央卸売市場の果実取扱い PDF から市況データを抽出。

**処理**:
- 過去のすべての週の PDF URL を列挙
- Content-Type で PDF/HTML を判定してダウンロード
- テキスト抽出と正規表現で「品目」「入荷量」「前週比」などをパース
- CSV ファイルに出力

**出力**: `market_data_{timestamp}.csv`

### recommend_recipes.py

Claude API を使用してランキングとレシピを生成。

**処理**:
- 最新の市況 CSV を読み込み
- `.cache/recipe_{week}.json` でキャッシュを確認
- キャッシュがなければ Claude API を呼び出し
- LLM キャッシング機能でトークンコストを削減
- JSON をファイルに保存

**出力**: `.cache/recipe_{week}.json`, `recipes_{timestamp}.json`

### build_site.py

市況 CSV + レシピキャッシュから静的 HTML を生成。

**処理**:
- 最新の market_data_*.csv を読み込み
- `.cache/recipe_{week}.json` を読み込み
- HTML テンプレートに埋め込み
- `docs/index.html` に出力

**出力**: `docs/index.html`

### app.py

Flask ローカルサーバー (オプション)。

**機能**:
- `/` でサイトを表示
- `/api/market` で市況データ JSON を返す
- `/api/recipes` でレシピ JSON を返す
- `/update` で SSE ストリーミング経由でリアルタイムに更新を実行

## 🔐 セキュリティ

- `.env` は `.gitignore` に含まれているため、API キーがリポジトリに含まれません
- GitHub Actions の秘密変数で `ANTHROPIC_API_KEY` を管理
- `market_data_*.csv` と `recipes_*.json` はリポジトリに含まれます (個人情報なし)

## 📄 ライセンス

MIT License

## 🤝 貢献

改善提案やバグ報告は Issues で受け付けています。
