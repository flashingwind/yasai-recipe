#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import io
import sys
import csv
from datetime import datetime
import os
import hashlib
import json

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None
        print("pypdf または PyPDF2 が未インストールです。\n  pip install pypdf\nでインストールしてください。", file=sys.stderr)


def get_cache_path(url):
    os.makedirs('.cache', exist_ok=True)
    h = hashlib.sha256(url.encode()).hexdigest()
    return f'.cache/{h}.json'

def load_cache(url):
    path = get_cache_path(url)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_cache(url, data):
    path = get_cache_path(url)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def get_weekly_links(base_url):
    res = requests.get(base_url, timeout=30)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, 'html.parser')
    links = []
    seen = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if re.search(r'/documents/d/shijou/', href):
            if not href.startswith('http'):
                href = 'https://www.shijou.metro.tokyo.lg.jp' + href
            if href not in seen:
                seen.add(href)
                links.append(href)
    return links


def detect_content_type(url):
    """HEADリクエストでContent-Typeを確認する。失敗時はURLから推定。"""
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        ct = r.headers.get('content-type', '')
        if 'pdf' in ct:
            return 'pdf'
        if 'html' in ct:
            return 'html'
    except Exception:
        pass
    # URLから推定
    if url.lower().endswith('.pdf') or '-pdf' in url.lower():
        return 'pdf'
    return 'unknown'


def extract_text_from_pdf_url(url):
    if PdfReader is None:
        return ""
    res = requests.get(url, timeout=60)
    reader = PdfReader(io.BytesIO(res.content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_pdf_text(text, url):
    """
    東京都中央卸売市場 週間市況PDF の構造に合わせて品目・価格・入荷量・コメントを抽出する。

    品目行フォーマット例:
      あまなつかん 48 82 90せり 熊本 10
      品目名 [入荷量t] [前週比%] [前年比%] せり/相対 産地 ...
    価格行フォーマット例:
      相対 熊本 10 3,240 1,647 1,296 90 61
    概況コメントは「概況」ラベル以降の長文行。
    """
    # 週情報（全角スペース区切り・全角数字形式にも対応）
    week = ""
    # 全角数字を半角に変換してから検索
    normalized = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    m = re.search(r'(\d{4})[\s\u3000]*年[\s\u3000]*(\d{1,2})[\s\u3000]*月[\s\u3000]*第[\s\u3000]*(\d)[\s\u3000]*週', normalized)
    if m:
        week = f"{m.group(1)}年{m.group(2)}月第{m.group(3)}週"
    # URLから補完（week_kajitsu_k2024031 → 2024年3月第1週）
    if not week:
        mu = re.search(r'k(\d{4})(\d{2})(\d)', url)
        if mu:
            week = f"{mu.group(1)}年{int(mu.group(2))}月第{mu.group(3)}週"

    items = []
    comment_lines = []
    in_comment = False

    # 「相対」「せり」で始まる価格行（品目行と誤認識しないようスキップ用）
    price_line_prefix = re.compile(r'^(相対|せり)')
    # 品目名行: 行頭が漢字/ひらがな/カタカナ（相対・せり以外）で始まり 数字3つが続く
    item_pattern = re.compile(
        r'^([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF][^\d\n]*?)\s+'  # 品目名
        r'(\d[\d,]*)\s+'   # 入荷量t
        r'(\d[\d,]*)\s+'   # 前週比%
        r'(\d[\d,]*)'      # 前年比%
    )
    # 価格行: 「相対 産地 単位 高値 中値 安値 ...」カンマ区切り数字3つ以上
    price_pattern = re.compile(
        r'(?:相対|せり)\S*\s+\S+\s+[\d.]+\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    )

    current_item = None
    lines = text.split('\n')
    for line in lines:
        line = line.strip()

        # 概況コメント検出
        if '概況' in line or in_comment:
            in_comment = True
            clean = re.sub(r'^概況.*?（[^）]*）', '', line).strip()
            if len(clean) > 20:
                comment_lines.append(clean)
            continue

        # 価格行を先に判定してスキップ（品目行パターンより優先）
        if price_line_prefix.match(line):
            if current_item:
                pm = price_pattern.match(line)
                if pm and not current_item["price_mid"]:
                    current_item["price_high"] = pm.group(1).replace(',', '')
                    current_item["price_mid"] = pm.group(2).replace(',', '')
                    current_item["price_low"] = pm.group(3).replace(',', '')
            continue

        # 品目行マッチ
        m = item_pattern.match(line)
        if m:
            name = m.group(1).strip()
            if name in ('総入荷量',):
                continue
            volume = m.group(2).replace(',', '')
            prev_week_ratio = m.group(3)
            prev_year_ratio = m.group(4)
            current_item = {
                "week": week,
                "name": name,
                "volume_t": volume,
                "prev_week_pct": prev_week_ratio,
                "prev_year_pct": prev_year_ratio,
                "price_high": "",
                "price_mid": "",
                "price_low": "",
            }
            items.append(current_item)

    comment = "\n".join(comment_lines).strip()
    return {"items": items, "comment": comment}


def extract_data_from_pdf(url):
    cached = load_cache(url)
    if cached:
        return cached
    if PdfReader is None:
        return {"items": [], "comment": "PDFライブラリ未インストール"}
    try:
        text = extract_text_from_pdf_url(url)
        result = parse_pdf_text(text, url)
        save_cache(url, result)
        return result
    except Exception as e:
        return {"items": [], "comment": f"PDF抽出エラー: {e}"}


def extract_data_from_html(url):
    cached = load_cache(url)
    if cached:
        return cached
    res = requests.get(url, timeout=30)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, 'html.parser')

    week = ""
    for tag in soup.find_all(['h1', 'h2', 'title']):
        m = re.search(r'\d{4}年\d{1,2}月第\d週', tag.get_text())
        if m:
            week = m.group(0)
            break

    items = []
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cols = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cols) >= 3:
                name = cols[0]
                price = next((c for c in cols[1:] if re.search(r'^\d[\d,]+$', c)), "")
                volume = next((c for c in cols[1:] if re.search(r'^\d+$', c) and c != price), "")
                if name and re.search(r'[\u3040-\u30FF\u4E00-\u9FFF]', name):
                    items.append({
                        "week": week, "name": name,
                        "volume_t": volume, "prev_week_pct": "", "prev_year_pct": "",
                        "price_high": price, "price_mid": "", "price_low": "",
                    })

    comments = []
    for tag in soup.find_all(['p', 'div']):
        txt = tag.get_text(strip=True)
        if len(txt) > 80 and any(k in txt for k in ['概況', '市況', '入荷', '前週']):
            comments.append(txt)
    comment = comments[0] if comments else ""

    result = {"items": items, "comment": comment}
    save_cache(url, result)
    return result


def extract_data(url):
    """Content-TypeでPDF/HTMLを判定して適切なパーサーを呼ぶ。"""
    ct = detect_content_type(url)
    if ct == 'pdf':
        return extract_data_from_pdf(url)
    elif ct == 'html':
        return extract_data_from_html(url)
    else:
        # 実際にGETしてContent-Typeで再判定
        try:
            res = requests.get(url, timeout=30, stream=True)
            content_type = res.headers.get('content-type', '')
            res.close()
            if 'pdf' in content_type:
                return extract_data_from_pdf(url)
            else:
                return extract_data_from_html(url)
        except Exception as e:
            return {"items": [], "comment": f"取得エラー: {e}"}


if __name__ == "__main__":
    base_url = "https://www.shijou.metro.tokyo.lg.jp/torihiki/week/kajitsu"
    week_links = get_weekly_links(base_url)
    print(f"週リンク数: {len(week_links)}")
    all_rows = []
    total = len(week_links)
    for idx, link in enumerate(week_links, 1):
        print(f"[{idx}/{total}] {link}", flush=True)
        data = extract_data(link)
        comment = data.get("comment", "")
        items = data.get("items", [])
        if not items:
            print(f"  -> 品目なし (コメント: {comment[:40]})")
        for item in items:
            row = {
                "週": item.get("week", ""),
                "品目": item.get("name", ""),
                "入荷量t": item.get("volume_t", ""),
                "前週比%": item.get("prev_week_pct", ""),
                "前年比%": item.get("prev_year_pct", ""),
                "高値円": item.get("price_high", ""),
                "中値円": item.get("price_mid", ""),
                "安値円": item.get("price_low", ""),
                "コメント": comment,
                "URL": link,
            }
            all_rows.append(row)

    dt = datetime.now().strftime("%Y%m%d_%H%M%S")
    outname = f"market_data_{dt}.csv"
    fieldnames = ["週", "品目", "入荷量t", "前週比%", "前年比%", "高値円", "中値円", "安値円", "コメント", "URL"]
    with open(outname, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    print(f"\nCSV出力完了: {outname} ({len(all_rows)}行)")
