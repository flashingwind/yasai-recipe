#!/usr/bin/env python3
"""
市況・レシピ提案 Webアプリ
"""
import csv
import glob
import json
import os
import re
import subprocess
import sys
import threading

from flask import Flask, Response, jsonify, render_template, stream_with_context

# .env読み込み
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

app = Flask(__name__)

# ── データ読込ユーティリティ ──────────────────────────────────────────────────

def get_latest_csv():
    files = glob.glob(os.path.join(os.path.dirname(__file__), "market_data_*.csv"))
    if not files:
        return None
    return sorted(files, reverse=True)[0]


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
    path = os.path.join(os.path.dirname(__file__), f".cache/recipe_{safe}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        text = data.get("text", "")
        # JSON抽出
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        json_str = m.group(1) if m else text.strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None


# ── ルート ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    items, week = load_market_data()
    recipe_data = load_recipe_cache(week) if week else None
    has_csv = get_latest_csv() is not None
    return render_template(
        "index.html",
        week=week,
        items=items,
        recipe_data=recipe_data,
        has_csv=has_csv,
    )


@app.route("/api/market")
def api_market():
    items, week = load_market_data()
    return jsonify({"week": week, "items": items})


@app.route("/api/recipes")
def api_recipes():
    _, week = load_market_data()
    if not week:
        return jsonify({"error": "データなし"}), 404
    data = load_recipe_cache(week)
    if data:
        return jsonify(data)
    return jsonify({"error": "レシピ未生成"}), 404


# ── SSEストリーミング更新 ──────────────────────────────────────────────────────

_update_lock = threading.Lock()
_update_running = False


def _run_update():
    """scrape → recommend を順に実行しSSEイベントを yield する"""
    global _update_running
    base = os.path.dirname(os.path.abspath(__file__))

    steps = [
        ("市況データ取得中...", [sys.executable, "scrape_market_comment.py"]),
        ("レシピ生成中...",     [sys.executable, "recommend_recipes.py"]),
    ]

    for label, cmd in steps:
        yield f"data: {json.dumps({'status': label})}\n\n"
        proc = subprocess.Popen(
            cmd, cwd=base,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                yield f"data: {json.dumps({'log': line})}\n\n"
        proc.wait()
        if proc.returncode != 0:
            yield f"data: {json.dumps({'error': f'{label} 失敗 (code {proc.returncode})'})}\n\n"
            _update_running = False
            return

    yield f"data: {json.dumps({'done': True})}\n\n"
    _update_running = False


@app.route("/update")
def update():
    global _update_running
    if not _update_lock.acquire(blocking=False):
        return Response("data: {\"error\": \"更新中です\"}\n\n", mimetype="text/event-stream")
    _update_running = True

    def generate():
        try:
            yield from _run_update()
        finally:
            try:
                _update_lock.release()
            except RuntimeError:
                pass

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
