# Claude Code Project Guide

## 📌 Project Overview

**yasai-recipe** は、東京中央卸売市場の果実市況データを自動取得し、Claude API でレシピを生成して静的サイトで公開するシステムです。

## 🔄 Architecture

```
GitHub Actions (毎週金曜 9:00 JST)
  ↓
1. scrape_market_comment.py (市況データ取得)
  ↓
2. recommend_recipes.py (Claude API でレシピ生成)
  ↓
3. build_site.py (静的サイト生成)
  ↓
4. Git push → GitHub Pages デプロイ (yasai.2-b.jp)
```

## 📂 Key Files

| File | Purpose |
|------|---------|
| `.github/workflows/update.yml` | GitHub Actions ワークフロー定義 |
| `scrape_market_comment.py` | 市況データスクレイピング |
| `recommend_recipes.py` | Claude API でレシピ・ランキング生成 |
| `build_site.py` | `docs/index.html` 生成 |
| `app.py` | Flask ローカルサーバー (オプション) |
| `docs/index.html` | 生成された静的サイト |
| `.cache/` | レシピ JSON キャッシュ (週単位) |
| `.env` | API キー (`.gitignore` に含まれる) |

## 🔐 Secrets & Environment

GitHub Actions に必要な秘密変数：
- `ANTHROPIC_API_KEY`: Claude API キー

ローカル開発用 `.env`:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

## 🧠 Claude API Integration

`recommend_recipes.py` では以下を実装：

- **Model**: `claude-opus-4-7` (最新モデル)
- **Caching**: 同じ週のデータに対する API 呼び出しを最小化
  - `.cache/recipe_{week}.json` に保存
  - ワークフロー実行時にキャッシュを復元
- **Streaming**: `stream=True` で長い応答に対応
- **Thinking**: `thinking: {type: "adaptive"}` で複雑な推論に対応

## 🔄 Workflow Triggers

| Trigger | Schedule | Behavior |
|---------|----------|----------|
| `schedule` | 毎週金曜 9:00 JST | 自動実行 |
| `workflow_dispatch` | Manual | GitHub Actions から手動実行 |

## 📊 Data Flow

### Input: 市況データ

東京中央卸売市場 PDF から取得：
- 品目（品名）
- 入荷量（t）
- 前週比（%）
- 前年比（%）
- 高値・中値・安値（円）

### Processing: Claude API

```
市況データ (CSV)
  ↓
system_prompt (マーケティング的な評価基準)
  ↓
Claude API (ランキング + レシピ生成)
  ↓
JSON キャッシュ (.cache/recipe_{week}.json)
  ↓
HTML レンダリング (docs/index.html)
```

### Output: 静的サイト

- おすすめ果実ランキング (1-5位)
- 各果実の簡単レシピ
- 市況データテーブル
- 更新日時

## 🛠️ Development Tips

### ローカルテスト

```bash
# 1. 市況データを取得
python scrape_market_comment.py

# 2. レシピを生成 (キャッシュがあれば使用)
python recommend_recipes.py

# 3. サイトをビルド
python build_site.py

# 4. ローカルサーバーで確認
python app.py
# http://localhost:5000
```

### キャッシュをクリア

```bash
rm -rf .cache/
```

### ワークフローを手動実行

```bash
gh workflow run update.yml --repo flashingwind/yasai-recipe
```

## 📝 Common Tasks

### ランキング条件を変更する

`recommend_recipes.py` の `system_prompt` を編集：

```python
system_prompt = """
あなたは青果マーケティングのプロです。
入荷量、相場動向、季節性を考慮して、
消費者にとっておすすめの果実をランキングしてください。
...
"""
```

### スケジュールを変更する

`.github/workflows/update.yml` の `cron` 値を編集：

```yaml
on:
  schedule:
    - cron: "0 9 * * 1"  # 毎週月曜日 9:00 UTC
```

### API モデルを変更する

`recommend_recipes.py` で：

```python
response = client.messages.create(
    model="claude-opus-4-6",  # または claude-sonnet-4-6
    ...
)
```

## ⚠️ Known Issues & Limitations

1. **Cloudflare Pages**: 現在は GitHub Pages を使用 (yasai.2-b.jp にカスタムドメイン設定済み)
2. **Cache 復元**: GitHub Actions のキャッシュは 7 日で自動削除される
3. **API 呼び出し**: 同じ週のデータでも新規実行時には API を呼ぶ (キャッシュキーは `market-cache-${github.run_id}`)

## 🔍 Monitoring

### ワークフロー実行を確認

```bash
gh run list --repo flashingwind/yasai-recipe --limit 5
gh run view <RUN_ID> --repo flashingwind/yasai-recipe --log
```

### サイトの動作確認

- https://yasai.2-b.jp にアクセス
- 最新の市況データとレシピが表示されるか確認

## 📞 Support

- GitHub Issues でバグ報告・機能提案
- GitHub Discussions で質問
