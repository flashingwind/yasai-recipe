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
from datetime import datetime

import requests

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
    # 固定ファイル名、なければタイムスタンプ付きの旧ファイルを探す
    if os.path.exists("market_data.csv"):
        return "market_data.csv"
    files = glob.glob("market_data_*.csv")
    if not files:
        print("CSVファイルが見つかりません。先に scrape_market_comment.py を実行してください。")
        sys.exit(1)
    return sorted(files, reverse=True)[0]


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


def calculate_score_with_retail(item, rules, max_values):
    """スコア計算。価格は日報補正済み卸値 > 週報中値の順で使用。"""
    try:
        vol = float(item["入荷量t"] or 0)
        wow = float(item["前週比%"] or 100)
        yoy = float(item["前年比%"] or 100)
        corrected = item.get("補正価格円")
    except (ValueError, KeyError):
        return 0

    richness = (vol / max_values["vol"]) * 100 if max_values["vol"] > 0 else 0
    trend = max(min((wow - 50) / 150 * 100, 100), 0)
    seasonality = 100 - min(abs(yoy - 100) * 0.8, 100)

    # 手頃さ: 日報補正価格 > 週報中値
    if corrected and max_values.get("corrected_price", 0) > 0:
        affordability = (1 - corrected / max_values["corrected_price"]) * 100
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
    max_vol = 1
    max_price = 1
    max_corrected = 0
    for r in items:
        try:
            max_vol = max(max_vol, float(r["入荷量t"] or 0))
            max_price = max(max_price, float(r["中値円"] or 0))
            if r.get("補正価格円"):
                max_corrected = max(max_corrected, r["補正価格円"])
        except (ValueError, TypeError):
            pass
    result = {"vol": max_vol, "price": max_price}
    if max_corrected > 0:
        result["corrected_price"] = max_corrected
    return result


# ── 日報取得・価格補正 ────────────────────────────────────────────────────────

PRICE_ELASTICITY = 0.3  # 数量1%増 → 価格0.3%下落と仮定

def fetch_daily_volumes(date=None):
    """市場日報CSVから当日の野菜卸売数量を {品目名: kg} で返す。取得失敗時は {}。"""
    if date is None:
        date = datetime.now()
    ym = date.strftime("%Y%m")
    ymd = date.strftime("%Y%m%d")
    url = f"https://www.shijou-nippo.metro.tokyo.lg.jp/SN/{ym}/{ymd}/Sei/Sei_K0.csv"
    try:
        r = requests.get(url, timeout=15)
        r.encoding = r.apparent_encoding
    except Exception as e:
        print(f"⚠ 日報取得失敗: {e}")
        return {}

    result = {}
    in_veggie = False
    for line in r.text.splitlines():
        if "野菜（単位" in line:
            in_veggie = True
            continue
        if "果実（単位" in line or "花き（単位" in line:
            break
        if not in_veggie:
            continue
        parts = line.split(",")
        name = parts[0].strip()
        if not name or name == "品名":
            continue
        try:
            vol_kg = float(parts[1].replace("－", "0").replace(",", "") or 0)
            if vol_kg > 0:
                result[name] = vol_kg
        except (IndexError, ValueError):
            pass
    return result


def apply_daily_price_correction(items, daily_vols):
    """週報の品目リストに日報の数量増減から推定価格補正を付与する。

    weekly_daily_vol = 週報入荷量(t) * 1000 / 7  （週平均の1日量）
    volume_ratio     = daily_vol / weekly_daily_vol
    price_factor     = volume_ratio ^ (-PRICE_ELASTICITY)
    補正後価格       = 週報中値 * price_factor
    """
    for item in items:
        name = item["品目"].strip()
        daily_kg = daily_vols.get(name)
        if daily_kg is None:
            continue
        try:
            weekly_t = float(item["入荷量t"] or 0)
            base_price = float(item["中値円"] or 0)
        except (ValueError, TypeError):
            continue
        if weekly_t <= 0 or base_price <= 0:
            continue
        weekly_daily_kg = weekly_t * 1000 / 7
        volume_ratio = daily_kg / weekly_daily_kg
        price_factor = volume_ratio ** (-PRICE_ELASTICITY)
        item["補正価格円"] = base_price * price_factor
        item["日報数量kg"] = daily_kg
        item["日量比"] = round(volume_ratio, 3)
    return items


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

市況コメント（参考・東京都中央卸売市場）：
{market_comment or "特にコメントなし"}

この情報をもとに、以下の JSON を生成してください：
{{
  "market_comment": "消費者向けの簡潔な市況説明（1～2文、価格と旬に言及）",
  "ranking_comments": {{
    "野菜名": "その野菜のおすすめ理由（1文、価格・旬・食べ方のヒントを含む）"
  }},
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

ranking_comments はランキング全品目分を生成してください。
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

    # 日報から当日数量を取得し、週報との比較で価格を補正（毎日実行）
    print("日報データ取得中...")
    daily_vols = fetch_daily_volumes()
    if daily_vols:
        print(f"  日報品目数: {len(daily_vols)}")
        apply_daily_price_correction(items, daily_vols)
    else:
        print("  日報データなし（週報のみでスコア計算）")

    max_values = calc_max_values(items)

    # ランキングは毎日再計算（日報補正が日ごとに変わるため）
    print("ランキング計算中...")
    scores = []
    for item in items:
        score = calculate_score_with_retail(item, rules, max_values)
        scores.append((item["品目"], score, item))
    scores.sort(key=lambda x: x[1], reverse=True)

    ranking = []
    for i, (name, score, r) in enumerate(scores[:5]):
        ratio = r.get("日量比")
        ratio_str = f"、本日入荷量 週平均比{ratio:.0%}" if ratio else ""
        ranking.append({
            "rank": i + 1,
            "item": name,
            "score": score,
            "retail_price": None,
            "reason": f"入荷量{r['入荷量t']}t{ratio_str}"
        })

    # コメント・レシピはキャッシュから（週単位）、なければAPI生成
    cached = load_cache(week)
    if cached:
        print("✓ コメント・レシピをキャッシュから読み込みました（API呼び出しなし）")
        ranking_comments = cached.get("ranking_comments", {})
        market_comment_text = cached.get("market_comment", "")
        recipes = cached.get("recipes", [])
    else:
        print("レシピ・コメント生成中...")
        top_items = [(name, score, "") for name, score, r in scores[:3]]
        market_comment = build_comment(items)
        recipe_data = generate_recipe_and_comment("", top_items, market_comment)
        ranking_comments = recipe_data.get("ranking_comments", {})
        market_comment_text = recipe_data.get("market_comment", "")
        recipes = recipe_data.get("recipes", [])
        save_cache(week, {
            "week": week,
            "ranking_comments": ranking_comments,
            "market_comment": market_comment_text,
            "recipes": recipes,
        })
        print("✓ キャッシュに保存しました。")

    for entry in ranking:
        entry["comment"] = ranking_comments.get(entry["item"], "")

    result = {
        "week": week,
        "ranking": ranking,
        "market_comment": market_comment_text,
        "recipes": recipes,
    }

    # 日次ランキング結果をファイルに書き出す（build_site.py が読む）
    today_str = datetime.now().strftime("%Y%m%d")
    result_path = f"daily_result_{today_str}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✓ 日次結果出力: {result_path}")

    # 出力
    print("\n" + "=" * 60)
    print(f"🥬 {week} おすすめ野菜ランキング")
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
