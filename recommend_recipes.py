#!/usr/bin/env python3
"""
市況データをもとにランキングとレシピを生成する。
- ランキング: 統計ルール（ranking_rules.json）で計算（API呼び出しなし）
- コメント・レシピ: Claude API で生成（週ごとキャッシュ）
"""
import csv
import glob
import json
import os
import re
import sys

_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

import anthropic

# ── ランキングルール ────────────────────────────────────────────────────────

def load_ranking_rules():
    try:
        with open("ranking_rules.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ ranking_rules.json が見つかりません。")
        print("先に generate_ranking_rules.py を実行してください。")
        sys.exit(1)


def calculate_score(item, rules, max_values):
    """統計ルールでスコアを計算"""
    try:
        vol = float(item["入荷量t"] or 0)
        wow = float(item["前週比%"] or 100)
        yoy = float(item["前年比%"] or 100)
        price = float(item["中値円"] or max_values["price"])
    except (ValueError, KeyError):
        return 0

    # 豊富さ
    richness = (vol / max_values["vol"]) * 100 if max_values["vol"] > 0 else 0

    # トレンド
    trend = max(min((wow - 50) / 150 * 100, 100), 0)

    # 旬度
    seasonality = 100 - min(abs(yoy - 100) * 0.8, 100)

    # 手頃さ
    affordability = (1 - price / max_values["price"]) * 100 if max_values["price"] > 0 else 0

    # 総合スコア（価格優先、次に旬・流通量）
    score = (
        0.50 * affordability +
        0.30 * seasonality +
        0.15 * richness +
        0.05 * trend
    )
    return int(score)


# ── CSV読込 ──────────────────────────────────────────────────────────────────

def get_latest_csv():
    files = glob.glob("market_data_*.csv")
    if not files:
        print("CSVファイルが見つかりません。先に scrape_market_comment.py を実行してください。")
        sys.exit(1)
    return sorted(files, reverse=True)[0]


def load_all_weeks(csvfile):
    """全週データを {週: {品目: row}} で返す"""
    with open(csvfile, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    valid = [r for r in rows if re.match(r"\d{4}年", r["週"])]
    weeks = {}
    for r in valid:
        w = r["週"]
        name = r["品目"].strip()
        if name and name != "総入荷量":
            weeks.setdefault(w, {})[name] = r
    return weeks


def load_latest_week(csvfile):
    with open(csvfile, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    valid = [r for r in rows if re.match(r"\d{4}年", r["週"])]
    if not valid:
        return [], ""
    latest_week = sorted(set(r["週"] for r in valid), reverse=True)[0]
    items = [r for r in valid if r["週"] == latest_week]
    seen, unique = set(), []
    for r in items:
        name = r["品目"].strip()
        if name and name != "総入荷量" and name not in seen:
            seen.add(name)
            unique.append(r)
    return unique, latest_week


# 品目ごとの小売乗率（葉物・根菜・果菜で異なる）
RETAIL_MULTIPLIER = {
    "default": 2.5,
    "キャベツ": 2.0, "だいこん": 2.0, "はくさい": 2.0, "ごぼう": 2.2,
    "ほうれんそう": 2.8, "こまつな": 2.8, "みずな": 2.8, "しそ": 3.0,
    "トマト": 2.5, "きゅうり": 2.5, "なす": 2.5, "ピーマン": 2.8,
    "レタス": 2.5, "ブロッコリー": 2.5, "カリフラワー": 2.5,
    "たまねぎ": 2.0, "じゃがいも": 2.0, "さつまいも": 2.2, "にんじん": 2.0,
}

def estimate_retail_price(name, prev_week_data):
    """1週間前の卸値から今週のスーパー推定価格を計算（100g単位）"""
    row = prev_week_data.get(name)
    if not row:
        return None
    try:
        mid = float(row["中値円"] or 0)
        if mid <= 0:
            return None
    except (ValueError, TypeError):
        return None
    multiplier = RETAIL_MULTIPLIER.get(name, RETAIL_MULTIPLIER["default"])
    # 卸値は1kg単位 → 100g単価に変換
    per_100g = (mid * multiplier) / 10
    # 10円単位に丸める
    return round(per_100g / 10) * 10


def calculate_score_with_retail(item, rules, max_values):
    """推定小売価格があればそれを優先してスコア計算"""
    try:
        vol = float(item["入荷量t"] or 0)
        wow = float(item["前週比%"] or 100)
        yoy = float(item["前年比%"] or 100)
        retail = item.get("推定小売円_100g")
    except (ValueError, KeyError):
        return 0

    # 豊富さ
    richness = (vol / max_values["vol"]) * 100 if max_values["vol"] > 0 else 0

    # トレンド
    trend = max(min((wow - 50) / 150 * 100, 100), 0)

    # 旬度
    seasonality = 100 - min(abs(yoy - 100) * 0.8, 100)

    # 手頃さ：推定小売価格があれば優先
    if retail and max_values.get("retail_price", 0) > 0:
        affordability = (1 - retail / max_values["retail_price"]) * 100
    else:
        price = float(item["中値円"] or max_values["price"])
        affordability = (1 - price / max_values["price"]) * 100 if max_values["price"] > 0 else 0

    score = (
        0.50 * affordability +
        0.30 * seasonality +
        0.15 * richness +
        0.05 * trend
    )
    return int(max(0, min(100, score)))


def calc_max_values(items):
    """各カテゴリの最大値を計算"""
    max_vol = 1
    max_price = 1
    for r in items:
        try:
            vol = float(r["入荷量t"] or 0)
            price = float(r["中値円"] or 0)
            max_vol = max(max_vol, vol)
            max_price = max(max_price, price)
        except (ValueError, TypeError):
            pass
    return {"vol": max_vol, "price": max_price}


# ── プロンプト ──────────────────────────────────────────────────────────────

def build_market_summary(items):
    lines = []
    for r in items:
        vol = r["入荷量t"] or "不明"
        wow = r["前週比%"] or "不明"
        price = r["中値円"] or "不明"
        lines.append(f"- {r['品目']}: 入荷量{vol}t  前週比{wow}%  中値{price}円")
    return "\n".join(lines)


def build_comment(items):
    for r in items:
        if r.get("コメント"):
            text = r["コメント"].strip()
            return text[:400] + ("…" if len(text) > 400 else "")
    return ""


# ── キャッシュ ──────────────────────────────────────────────────────────────

def _cache_path(week):
    os.makedirs(".cache", exist_ok=True)
    safe = re.sub(r"[^\w]", "_", week)
    return f".cache/recipe_{safe}.json"


def load_cache(week):
    path = _cache_path(week)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_cache(week, data):
    path = _cache_path(week)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── LLM呼び出し ──────────────────────────────────────────────────────────────

def generate_recipe_and_comment(market_summary, top_items, market_comment):
    """Claude API でレシピとコメントを生成（キャッシュ可能）"""
    client = anthropic.Anthropic()

    system_prompt = """あなたは野菜料理のプロです。
野菜の市況データをもとに、消費者向けのコメントと簡単レシピを生成します。"""

    items_str = "\n".join(f"- {name}: {score}点（{price}）" for name, score, price in top_items)

    user_message = f"""以下は今週のおすすめ野菜トップ5です（スーパー推定価格付き）：

{items_str}

市況コメント（参考）：
{market_comment or "特にコメントなし"}

この情報をもとに、以下の JSON を生成してください：
{{
  "market_comment": "消費者向けの簡潔な市況説明（1～2文、価格と旬に言及）",
  "recipes": [
    {{
      "title": "レシピ名",
      "item": "対象野菜",
      "time_min": 調理時間分,
      "servings": "○人分",
      "ingredients": ["材料1", "材料2"],
      "steps": ["手順1", "手順2"]
    }}
  ]
}}

レシピは上位3品目分（簡潔に）を生成してください。"""

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    text = response.content[0].text
    json_match = text.find('{')
    json_end = text.rfind('}') + 1
    if json_match >= 0 and json_end > json_match:
        try:
            return json.loads(text[json_match:json_end])
        except json.JSONDecodeError:
            return {"market_comment": "レシピ生成エラー", "recipes": []}
    return {"market_comment": "レシピ生成エラー", "recipes": []}


# ── メイン ──────────────────────────────────────────────────────────────────

def main():
    rules = load_ranking_rules()
    csvfile = get_latest_csv()
    items, week = load_latest_week(csvfile)

    if not items or not week:
        print("❌ 市況データが見つかりません。")
        sys.exit(1)

    print(f"CSVファイル: {csvfile}")
    print(f"週: {week}  品目数: {len(items)}")

    # 前週データを取得（1週間ディレイで小売価格推定に使用）
    all_weeks = load_all_weeks(csvfile)
    sorted_weeks = sorted(all_weeks.keys(), reverse=True)
    prev_week_data = all_weeks[sorted_weeks[1]] if len(sorted_weeks) >= 2 else {}

    # キャッシュを確認
    cached = load_cache(week)
    if cached:
        print("✓ キャッシュから読み込みました（API呼び出しなし）")
        result = {
            "week": week,
            "ranking": cached.get("ranking", []),
            "market_comment": cached.get("market_comment", ""),
            "recipes": cached.get("recipes", [])
        }
    else:
        # 各品目に推定小売価格を付与
        for item in items:
            name = item["品目"].strip()
            retail = estimate_retail_price(name, prev_week_data)
            item["推定小売円_100g"] = retail

        # 推定価格ベースで max_price を再計算
        max_values = calc_max_values(items)
        # 推定価格がある品目はそれを価格スコアに使用
        retail_prices = [i["推定小売円_100g"] for i in items if i.get("推定小売円_100g")]
        if retail_prices:
            max_values["retail_price"] = max(retail_prices)

        print("計算中...")
        scores = []
        for item in items:
            score = calculate_score_with_retail(item, rules, max_values)
            scores.append((item["品目"], score, item))

        scores.sort(key=lambda x: x[1], reverse=True)
        ranking = []
        for i, (name, score, r) in enumerate(scores[:5]):
            retail = r.get("推定小売円_100g")
            retail_str = f"約{retail}円/100g" if retail else "価格調査中"
            ranking.append({
                "rank": i + 1,
                "item": name,
                "score": score,
                "retail_price": retail,
                "reason": f"スーパー目安 {retail_str}、入荷量{r['入荷量t']}t"
            })

        # Claude API でレシピ・コメント生成
        print("レシピ・コメント生成中...")
        top_items = [
            (name, score, f"約{r.get('推定小売円_100g')}円/100g" if r.get('推定小売円_100g') else "")
            for name, score, r in scores[:3]
        ]
        items_str_with_price = "\n".join(
            f"- {name}: {score}点（{price}）" for name, score, price in top_items
        )
        market_comment = build_comment(items)
        recipe_data = generate_recipe_and_comment("", top_items, market_comment)

        result = {
            "week": week,
            "ranking": ranking,
            "market_comment": recipe_data.get("market_comment", ""),
            "recipes": recipe_data.get("recipes", [])
        }

        # キャッシュに保存
        save_cache(week, result)
        print("✓ キャッシュに保存しました。")

    # 出力
    print("\n" + "=" * 60)
    print(f"🍊 {week} おすすめ果実ランキング")
    print("=" * 60)
    print(f"📢 市況: {result['market_comment']}\n")
    print("【おすすめランキング】")
    for r in result["ranking"]:
        stars = "★" * (r["score"] // 20) + "☆" * (5 - r["score"] // 20)
        print(f"  {r['rank']}位 {r['item']:10s} {stars} ({r['score']}点)")

    # レシピ出力
    if result["recipes"]:
        print("\n【簡単レシピ】")
        for recipe in result["recipes"]:
            print(f"\n  🍽️  {recipe['title']} ({recipe['item']})")
            print(f"      調理時間: {recipe['time_min']}分 / {recipe['servings']}")

    # JSON 保存
    out_path = f"recipes_{week.replace('年', '').replace('第', '').replace('週', '')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✓ JSON出力: {out_path}")

    # トークン使用量表示
    print(f"✓ API呼び出し: キャッシュからの読み込み" if cached else "✓ API呼び出し: 新規生成")


if __name__ == "__main__":
    main()
