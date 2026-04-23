#!/usr/bin/env python3
"""
市況CSV + レシピJSONキャッシュ → docs/index.html を生成する。
GitHub Actions から呼ばれる静的サイトビルダー。
"""
import csv
import glob
import json
import os
import re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "docs")
os.makedirs(DOCS, exist_ok=True)

# 野菜名 → Unsplash 検索キーワード
VEGGIE_PHOTOS = {
    "キャベツ": "cabbage", "だいこん": "daikon radish", "はくさい": "napa cabbage",
    "レタス": "lettuce", "きゅうり": "cucumber", "トマト": "tomato",
    "ほうれんそう": "spinach", "ねぎ": "green onion", "たまねぎ": "onion",
    "にんじん": "carrot", "じゃがいも": "potato", "さつまいも": "sweet potato",
    "なす": "eggplant", "ピーマン": "bell pepper", "ブロッコリー": "broccoli",
    "カリフラワー": "cauliflower", "ごぼう": "burdock root", "れんこん": "lotus root",
    "かぼちゃ": "pumpkin", "アスパラガス": "asparagus", "さやえんどう": "pea",
    "そらまめ": "broad bean", "えだまめ": "edamame", "しょうが": "ginger",
    "にんにく": "garlic", "セロリ": "celery", "パセリ": "parsley",
    "みつば": "mitsuba", "しそ": "shiso", "チンゲンサイ": "bok choy",
    "もやし": "bean sprouts", "こまつな": "komatsuna", "みずな": "mizuna",
}

def veggie_img(name):
    kw = VEGGIE_PHOTOS.get(name, name)
    return f"https://source.unsplash.com/400x400/?{kw},vegetable,food"


# ── データ読込 ────────────────────────────────────────────────────────────────

def get_latest_csv():
    files = glob.glob(os.path.join(BASE, "market_data_*.csv"))
    return sorted(files, reverse=True)[0] if files else None


def load_market_data():
    csvfile = get_latest_csv()
    if not csvfile:
        return [], ""
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


def load_recipe_cache(week):
    safe = re.sub(r"[^\w]", "_", week)
    path = os.path.join(BASE, f".cache/recipe_{safe}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "ranking" in data:
        return data
    text = data.get("text", "")
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    json_str = m.group(1) if m else text.strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


# ── HTML部品 ──────────────────────────────────────────────────────────────────

def score_bar(score):
    pct = min(score, 100)
    color = "#52b788" if pct >= 70 else "#f4a261" if pct >= 50 else "#e76f51"
    return f'<div class="score-bar"><div class="score-fill" style="width:{pct}%;background:{color}"></div></div>'


def wow_badge(wow_str):
    if not wow_str:
        return ""
    try:
        v = int(wow_str)
    except ValueError:
        return ""
    if v > 100:
        return f'<span class="badge badge-up">↑{v}%</span>'
    if v < 100:
        return f'<span class="badge badge-down">↓{v}%</span>'
    return f'<span class="badge badge-flat">→{v}%</span>'


def render_ranking(recipe_data, items):
    if not recipe_data:
        return '<p class="no-data">データを取得中...</p>'
    item_map = {r["品目"].strip(): r for r in items}
    cards = ""
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}
    for r in recipe_data.get("ranking", []):
        name = r["item"]
        rank = r["rank"]
        score = r["score"]
        reason = r.get("reason", "")
        market = item_map.get(name, {})
        wow = wow_badge(market.get("前週比%", ""))
        img = veggie_img(name)
        m = medal.get(rank, f"#{rank}")
        cards += f"""
    <div class="rank-card">
      <div class="rank-img-wrap">
        <img class="rank-img" src="{img}" alt="{name}" loading="lazy" onerror="this.src='https://source.unsplash.com/400x400/?vegetable'">
        <span class="rank-medal">{m}</span>
        {wow}
      </div>
      <div class="rank-body">
        <div class="rank-name">{name}</div>
        <div class="rank-reason">{reason}</div>
        {score_bar(score)}
        <div class="rank-score-label">{score}点</div>
      </div>
    </div>"""
    return f'<div class="rank-grid">{cards}</div>'


def render_recipes(recipe_data):
    if not recipe_data:
        return ""
    cards = ""
    for recipe in recipe_data.get("recipes", []):
        ings = "".join(f"<span class='ing'>{i}</span>" for i in recipe.get("ingredients", []))
        steps = "".join(f"<li>{s}</li>" for s in recipe.get("steps", []))
        img = veggie_img(recipe.get("item", ""))
        cards += f"""
    <div class="recipe-card">
      <div class="recipe-img-wrap">
        <img class="recipe-img" src="{img}" alt="{recipe['title']}" loading="lazy" onerror="this.src='https://source.unsplash.com/600x400/?cooking,vegetable'">
        <div class="recipe-time-badge">🕐 {recipe['time_min']}分</div>
      </div>
      <div class="recipe-body">
        <div class="recipe-tag">{recipe['item']}</div>
        <h3 class="recipe-title">{recipe['title']}</h3>
        <div class="recipe-serving">👥 {recipe['servings']}</div>
        <div class="recipe-ings">{ings}</div>
        <ol class="recipe-steps">{steps}</ol>
      </div>
    </div>"""
    return f'<div class="recipe-grid">{cards}</div>'


def render_market_grid(items, recipe_data):
    if not items:
        return '<p class="no-data">市況データがありません。</p>'
    # レシピで使用している野菜名を収集
    used = set()
    if recipe_data:
        for r in recipe_data.get("ranking", []):
            used.add(r.get("item", ""))
        for r in recipe_data.get("recipes", []):
            used.add(r.get("item", ""))
    # 使用分だけ絞り込み（なければ全件）
    filtered = [r for r in items if r["品目"].strip() in used] if used else items
    cards = ""
    for r in filtered:
        wow = r.get("前週比%", "")
        badge = wow_badge(wow)
        price = r.get("中値円", "") or "—"
        vol = r.get("入荷量t", "") or "—"
        img = veggie_img(r["品目"])
        cards += f"""
    <div class="market-card">
      <img class="market-img" src="{img}" alt="{r['品目']}" loading="lazy" onerror="this.src='https://source.unsplash.com/400x400/?vegetable'">
      <div class="market-body">
        <div class="market-name">{r['品目']}{badge}</div>
        <div class="market-stats">
          <span>📦 {vol}t</span>
          <span>💴 {price}円</span>
        </div>
      </div>
    </div>"""
    return f'<div class="market-grid">{cards}</div>'


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🥬 やさいのき — 今週のおすすめ野菜</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap" rel="stylesheet">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Noto Sans JP',sans-serif;background:#fafaf7;color:#222}}

    /* ヘッダー */
    header{{background:linear-gradient(135deg,#2d6a4f,#52b788);color:#fff;
            padding:20px 24px;text-align:center}}
    .header-logo{{font-size:2rem;font-weight:900;letter-spacing:-.5px}}
    .header-sub{{font-size:.85rem;opacity:.85;margin-top:4px}}
    .week-pill{{display:inline-block;background:rgba(255,255,255,.2);
                border-radius:20px;padding:4px 14px;font-size:.8rem;margin-top:8px}}

    /* コンテナ */
    .container{{max-width:1000px;margin:0 auto;padding:20px 16px}}

    /* セクション */
    .section{{margin-bottom:36px}}
    .section-title{{font-size:1.2rem;font-weight:900;color:#2d6a4f;
                    margin-bottom:16px;display:flex;align-items:center;gap:8px}}
    .section-title::after{{content:'';flex:1;height:2px;background:linear-gradient(to right,#52b788,transparent)}}

    /* 市況コメント */
    .comment-box{{background:linear-gradient(135deg,#e9f5ee,#f0faf4);
                  border-left:4px solid #52b788;border-radius:0 12px 12px 0;
                  padding:14px 18px;font-size:.9rem;color:#444;margin-bottom:20px;line-height:1.7}}

    /* ランキング */
    .rank-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px}}
    .rank-card{{background:#fff;border-radius:16px;overflow:hidden;
                box-shadow:0 2px 12px rgba(0,0,0,.08);transition:transform .2s}}
    .rank-card:hover{{transform:translateY(-4px)}}
    .rank-img-wrap{{position:relative}}
    .rank-img{{width:100%;aspect-ratio:1;object-fit:cover}}
    .rank-medal{{position:absolute;top:8px;left:8px;font-size:1.6rem;
                 filter:drop-shadow(0 1px 2px rgba(0,0,0,.4))}}
    .rank-body{{padding:12px}}
    .rank-name{{font-weight:700;font-size:1rem;margin-bottom:4px}}
    .rank-reason{{font-size:.75rem;color:#888;margin-bottom:8px;line-height:1.5}}
    .score-bar{{background:#eee;border-radius:4px;height:6px;margin-bottom:4px}}
    .score-fill{{height:6px;border-radius:4px;transition:width .6s ease}}
    .rank-score-label{{font-size:.75rem;color:#aaa;text-align:right}}

    /* バッジ */
    .badge{{display:inline-block;border-radius:12px;padding:2px 8px;font-size:.72rem;
            font-weight:700;position:absolute;top:8px;right:8px}}
    .badge-up{{background:#ffebe9;color:#e63946}}
    .badge-down{{background:#e9f0ff;color:#457b9d}}
    .badge-flat{{background:#f0f0f0;color:#888}}

    /* レシピ */
    .recipe-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}}
    .recipe-card{{background:#fff;border-radius:16px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(0,0,0,.08);transition:transform .2s}}
    .recipe-card:hover{{transform:translateY(-4px)}}
    .recipe-img-wrap{{position:relative}}
    .recipe-img{{width:100%;height:180px;object-fit:cover}}
    .recipe-time-badge{{position:absolute;bottom:10px;right:10px;
                        background:rgba(0,0,0,.55);color:#fff;border-radius:12px;
                        padding:4px 10px;font-size:.78rem;backdrop-filter:blur(4px)}}
    .recipe-body{{padding:16px}}
    .recipe-tag{{display:inline-block;background:#e9f5ee;color:#2d6a4f;
                 border-radius:20px;padding:2px 10px;font-size:.75rem;font-weight:700;margin-bottom:8px}}
    .recipe-title{{font-size:1rem;font-weight:700;margin-bottom:4px}}
    .recipe-serving{{font-size:.78rem;color:#aaa;margin-bottom:10px}}
    .recipe-ings{{margin-bottom:10px}}
    .ing{{display:inline-block;background:#f5f5f0;border-radius:6px;
          padding:2px 8px;margin:2px;font-size:.78rem;color:#555}}
    .recipe-steps{{font-size:.82rem;padding-left:18px;color:#555;line-height:1.8}}
    .recipe-steps li{{margin-bottom:4px}}

    /* 市況グリッド */
    .market-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px}}
    .market-card{{background:#fff;border-radius:14px;overflow:hidden;
                  box-shadow:0 2px 8px rgba(0,0,0,.07);transition:transform .2s}}
    .market-card:hover{{transform:translateY(-3px)}}
    .market-img{{width:100%;aspect-ratio:1;object-fit:cover}}
    .market-body{{padding:10px}}
    .market-name{{font-size:.85rem;font-weight:700;margin-bottom:6px;
                  display:flex;align-items:center;gap:4px;flex-wrap:wrap}}
    .market-stats{{font-size:.75rem;color:#888;display:flex;flex-direction:column;gap:2px}}

    .no-data{{color:#aaa;font-size:.9rem;padding:20px 0;text-align:center}}
    footer{{text-align:center;padding:32px 16px;font-size:.78rem;color:#bbb}}
    footer a{{color:#52b788;text-decoration:none}}
  </style>
</head>
<body>
<header>
  <div class="header-logo">🥬 やさいのき</div>
  <div class="header-sub">東京中央卸売市場の市況から、今週買うべき野菜をお届け</div>
  <div class="week-pill">{week}</div>
</header>

<div class="container">

  <div class="section">
    <div class="section-title">🏆 今週のおすすめランキング</div>
    {market_comment_html}
    {ranking_html}
  </div>

  <div class="section">
    <div class="section-title">🍳 今週の簡単レシピ</div>
    {recipes_html}
  </div>

  <div class="section">
    <div class="section-title">📦 今週の市況一覧</div>
    {market_grid_html}
  </div>

</div>
<footer>
  更新: {updated_at} &nbsp;|&nbsp;
  データ: <a href="https://www.shijou.metro.tokyo.lg.jp/" target="_blank">東京都中央卸売市場</a>
</footer>
</body>
</html>
"""


def build():
    items, week = load_market_data()
    recipe_data = load_recipe_cache(week) if week else None

    market_comment_html = ""
    if recipe_data and recipe_data.get("market_comment"):
        market_comment_html = f'<div class="comment-box">{recipe_data["market_comment"]}</div>'

    html = HTML_TEMPLATE.format(
        week=week or "データなし",
        market_comment_html=market_comment_html,
        ranking_html=render_ranking(recipe_data, items),
        recipes_html=render_recipes(recipe_data),
        market_grid_html=render_market_grid(items, recipe_data),
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M JST"),
    )

    out = os.path.join(DOCS, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"生成完了: {out}")


if __name__ == "__main__":
    build()
