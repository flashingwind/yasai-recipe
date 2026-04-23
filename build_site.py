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
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "docs")
os.makedirs(DOCS, exist_ok=True)


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
    text = data.get("text", "")
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    json_str = m.group(1) if m else text.strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


# ── HTML生成 ──────────────────────────────────────────────────────────────────

def score_to_stars(score):
    full = score // 20
    empty = 5 - full
    return "★" * full + "☆" * empty


def wow_arrow(wow_str):
    if not wow_str:
        return "—"
    try:
        v = int(wow_str)
    except ValueError:
        return wow_str + "%"
    if v > 100:
        return f'<span class="up">▲{v}%</span>'
    if v < 100:
        return f'<span class="down">▼{v}%</span>'
    return f"―{v}%"


def render_ranking(recipe_data):
    if not recipe_data:
        return '<p class="no-data">レシピ・ランキングデータがありません。GitHub Actionsを実行してください。</p>'
    rows = ""
    for r in recipe_data.get("ranking", []):
        cls = {1: "gold", 2: "silver", 3: "bronze"}.get(r["rank"], "")
        rows += f"""
      <li>
        <div class="rank-num {cls}">{r['rank']}</div>
        <div class="rank-info">
          <div class="rank-item">{r['item']}</div>
          <div class="rank-reason">{r['reason']}</div>
        </div>
        <div class="rank-score">
          <span class="stars">{score_to_stars(r['score'])}</span><br>
          <small>{r['score']}点</small>
        </div>
      </li>"""
    return f'<ul class="ranking-list">{rows}</ul>'


def render_recipes(recipe_data):
    if not recipe_data:
        return ""
    cards = ""
    for recipe in recipe_data.get("recipes", []):
        ings = "".join(f"<span>{i}</span>" for i in recipe.get("ingredients", []))
        steps = "".join(f"<li>{s}</li>" for s in recipe.get("steps", []))
        cards += f"""
    <div class="recipe-card">
      <h3>{recipe['title']}</h3>
      <div class="recipe-meta">🕐 {recipe['time_min']}分 / {recipe['servings']}人分 — {recipe['item']}</div>
      <div class="recipe-ingredients">{ings}</div>
      <ol class="recipe-steps">{steps}</ol>
    </div>"""
    return f'<div class="recipes">{cards}</div>'


def render_table(items):
    if not items:
        return '<p class="no-data">市況データがありません。</p>'
    rows = ""
    for r in items:
        rows += f"""
      <tr>
        <td>{r['品目']}</td>
        <td>{r['入荷量t'] or '—'}</td>
        <td>{wow_arrow(r['前週比%'])}</td>
        <td>{r['前年比%'] + '%' if r['前年比%'] else '—'}</td>
        <td>{r['高値円'] or '—'}</td>
        <td>{r['中値円'] or '—'}</td>
        <td>{r['安値円'] or '—'}</td>
      </tr>"""
    return f"""
    <table>
      <thead>
        <tr><th>品目</th><th>入荷量(t)</th><th>前週比</th><th>前年比</th>
            <th>高値(円)</th><th>中値(円)</th><th>安値(円)</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>野菜市況・レシピ提案</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Helvetica Neue',Arial,'Hiragino Kaku Gothic ProN',sans-serif;
          background:#f5f5f0;color:#333}}
    header{{background:#2d6a4f;color:#fff;padding:16px 24px;
            display:flex;align-items:center;justify-content:space-between}}
    header h1{{font-size:1.3rem}}
    header .week{{font-size:.9rem;opacity:.8}}
    .container{{max-width:960px;margin:24px auto;padding:0 16px}}
    .section{{background:#fff;border-radius:8px;padding:20px;margin-bottom:20px;
              box-shadow:0 1px 4px rgba(0,0,0,.08)}}
    h2{{font-size:1.1rem;color:#2d6a4f;margin-bottom:14px;border-left:4px solid #2d6a4f;padding-left:10px}}
    .ranking-list{{list-style:none}}
    .ranking-list li{{display:flex;align-items:center;padding:10px 0;
                      border-bottom:1px solid #eee;gap:12px}}
    .ranking-list li:last-child{{border-bottom:none}}
    .rank-num{{font-size:1.5rem;font-weight:bold;color:#2d6a4f;width:36px;text-align:center}}
    .rank-num.gold{{color:#d4a017}}.rank-num.silver{{color:#888}}.rank-num.bronze{{color:#a0522d}}
    .rank-info{{flex:1}}
    .rank-item{{font-weight:bold;font-size:1rem}}
    .rank-reason{{font-size:.85rem;color:#666;margin-top:2px}}
    .stars{{color:#f4a261}}
    table{{width:100%;border-collapse:collapse;font-size:.88rem}}
    th{{background:#2d6a4f;color:#fff;padding:8px 10px;text-align:left}}
    td{{padding:7px 10px;border-bottom:1px solid #eee}}
    tr:hover td{{background:#f0f7f4}}
    .up{{color:#e63946}}.down{{color:#457b9d}}
    .recipes{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}}
    .recipe-card{{border:1px solid #e0e0e0;border-radius:8px;padding:16px}}
    .recipe-card h3{{font-size:1rem;color:#2d6a4f;margin-bottom:6px}}
    .recipe-meta{{font-size:.8rem;color:#888;margin-bottom:10px}}
    .recipe-ingredients span{{display:inline-block;background:#e9f5ee;border-radius:4px;
                              padding:2px 7px;margin:2px;font-size:.85rem}}
    .recipe-steps{{font-size:.85rem;padding-left:16px;color:#444;margin-top:8px}}
    .recipe-steps li{{margin-bottom:4px}}
    .no-data{{color:#999;font-size:.9rem;padding:12px 0}}
    footer{{text-align:center;padding:20px;font-size:.8rem;color:#aaa}}
  </style>
</head>
<body>
<header>
  <h1>🥬 野菜市況・レシピ提案</h1>
  <span class="week">{week}</span>
</header>
<div class="container">

  <div class="section">
    <h2>🏆 今週のおすすめランキング</h2>
    {market_comment_html}
    {ranking_html}
  </div>

  <div class="section">
    <h2>🍽️ 簡単レシピ</h2>
    {recipes_html}
  </div>

  <div class="section">
    <h2>📊 市況データ（{week}）</h2>
    {table_html}
  </div>

</div>
<footer>更新: {updated_at} | データ: 東京都中央卸売市場</footer>
</body>
</html>
"""


def build():
    items, week = load_market_data()
    recipe_data = load_recipe_cache(week) if week else None

    market_comment_html = ""
    if recipe_data and recipe_data.get("market_comment"):
        market_comment_html = f'<p style="font-size:.85rem;color:#555;margin-bottom:12px;">{recipe_data["market_comment"]}</p>'

    html = HTML_TEMPLATE.format(
        week=week or "データなし",
        market_comment_html=market_comment_html,
        ranking_html=render_ranking(recipe_data),
        recipes_html=render_recipes(recipe_data),
        table_html=render_table(items),
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M JST"),
    )

    out = os.path.join(DOCS, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"生成完了: {out}")


if __name__ == "__main__":
    build()
