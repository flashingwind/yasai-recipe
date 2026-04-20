#!/usr/bin/env python3
"""
最新市況データをもとに Claude API でおすすめランクとレシピを生成する。
"""
import csv
import glob
import os
import re
import sys

# .envファイルがあれば読み込む
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

import anthropic

# ── CSV読込 ──────────────────────────────────────────────────────────────────

def get_latest_csv():
    files = glob.glob("market_data_*.csv")
    if not files:
        print("CSVファイルが見つかりません。先に scrape_market_comment.py を実行してください。")
        sys.exit(1)
    return sorted(files, reverse=True)[0]


def load_latest_week(csvfile):
    with open(csvfile, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # 半角数字の週に絞り込み（旧形式の全角週を除外）
    valid = [r for r in rows if re.match(r"\d{4}年", r["週"])]
    if not valid:
        return [], ""
    latest_week = sorted(set(r["週"] for r in valid), reverse=True)[0]
    items = [r for r in valid if r["週"] == latest_week]
    # 品目名で重複除去（同一品目が複数ページで取れる場合）
    seen, unique = set(), []
    for r in items:
        name = r["品目"].strip()
        if name and name != "総入荷量" and name not in seen:
            seen.add(name)
            unique.append(r)
    return unique, latest_week


# ── プロンプト構築 ──────────────────────────────────────────────────────────

def build_market_summary(items):
    lines = []
    for r in items:
        vol = r["入荷量t"] or "不明"
        wow = r["前週比%"] or "不明"
        price = r["中値円"] or "不明"
        lines.append(f"- {r['品目']}: 入荷量{vol}t  前週比{wow}%  中値{price}円")
    return "\n".join(lines)


def build_comment(items):
    # コメントは品目ごとに同一なので最初の1件から取得
    for r in items:
        if r.get("コメント"):
            # 最初の段落だけ（長すぎるため）
            text = r["コメント"].strip()
            return text[:600] + ("…" if len(text) > 600 else "")
    return ""


# ── LLMキャッシュ ────────────────────────────────────────────────────────────

def _recipe_cache_path(week):
    os.makedirs(".cache", exist_ok=True)
    safe = re.sub(r"[^\w]", "_", week)
    return f".cache/recipe_{safe}.json"

def load_recipe_cache(week):
    path = _recipe_cache_path(week)
    if os.path.exists(path):
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None

def save_recipe_cache(week, text):
    import json
    path = _recipe_cache_path(week)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"week": week, "text": text}, f, ensure_ascii=False)


# ── Claude API呼び出し ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
あなたは青果市場の専門家であり、料理研究家です。
東京都中央卸売市場の週間市況データをもとに、消費者向けに
「今週お買い得な果実のおすすめランク」と「簡単レシピ」を提案してください。

出力は以下のJSON形式で返してください（コードブロック不要、純粋なJSONのみ）:
{
  "week": "週の表示",
  "ranking": [
    {
      "rank": 1,
      "item": "品目名",
      "reason": "おすすめ理由（価格・入荷量・旬の観点から50字以内）",
      "score": 85
    }
  ],
  "recipes": [
    {
      "item": "品目名",
      "title": "レシピ名",
      "time_min": 15,
      "servings": 2,
      "ingredients": ["材料1", "材料2"],
      "steps": ["手順1", "手順2", "手順3"]
    }
  ],
  "market_comment": "今週の市況を一言でまとめたコメント（100字以内）"
}

おすすめランクは上位5品目、レシピは上位3品目について各1品提案してください。
スコア(score)は100点満点で、低価格・入荷量多・旬の組み合わせで評価してください。"""


def generate(items, week):
    cached = load_recipe_cache(week)
    if cached:
        print(f"キャッシュヒット: {week}")
        return cached["text"], None

    summary = build_market_summary(items)
    comment = build_comment(items)

    user_message = f"""\
## {week} 果実市況データ

### 品目別データ（品目: 入荷量/前週比/中値）
{summary}

### 概況コメント
{comment}

上記データをもとに、おすすめランクとレシピを生成してください。
中値が空欄の品目は価格不明として扱い、入荷量・前週比・旬で評価してください。"""

    client = anthropic.Anthropic()

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        print("生成中...", flush=True)
        response = stream.get_final_message()

    text = next(
        (b.text for b in response.content if b.type == "text"), ""
    )
    save_recipe_cache(week, text)
    return text, response.usage


# ── 出力 ────────────────────────────────────────────────────────────────────

def print_result(text, week):
    import json

    # JSON抽出（```json ... ``` ブロックに包まれている場合も対応）
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    json_str = m.group(1) if m else text.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        print("⚠️ JSON解析エラー。生テキストを出力します。")
        print(text)
        return

    print(f"\n{'='*60}")
    print(f"🍊 {data.get('week', week)} おすすめ果実ランキング")
    print(f"{'='*60}")
    print(f"📢 市況: {data.get('market_comment', '')}\n")

    print("【おすすめランキング TOP5】")
    for r in data.get("ranking", []):
        bar = "★" * (r["score"] // 20) + "☆" * (5 - r["score"] // 20)
        print(f"  {r['rank']}位 {r['item']:12s} {bar} ({r['score']}点)")
        print(f"       {r['reason']}")
    print()

    print("【簡単レシピ】")
    for recipe in data.get("recipes", []):
        print(f"\n  🍽️  {recipe['title']} ({recipe['item']})")
        print(f"      調理時間: {recipe['time_min']}分 / {recipe['servings']}人分")
        print(f"      材料: {', '.join(recipe['ingredients'])}")
        print("      作り方:")
        for i, step in enumerate(recipe["steps"], 1):
            print(f"        {i}. {step}")

    # JSONファイルにも保存
    import datetime
    outfile = f"recipes_{datetime.date.today().strftime('%Y%m%d')}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSONを保存: {outfile}")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    csvfile = get_latest_csv()
    print(f"CSVファイル: {csvfile}")

    items, week = load_latest_week(csvfile)
    if not items:
        print("有効な市況データが見つかりません。")
        sys.exit(1)

    print(f"週: {week}  品目数: {len(items)}")

    text, usage = generate(items, week)

    if usage:
        print(f"トークン使用: input={usage.input_tokens} output={usage.output_tokens} "
              f"cache_read={usage.cache_read_input_tokens}")

    print_result(text, week)
