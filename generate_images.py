#!/usr/bin/env python3
"""
市況データに登場した野菜の画像を DALL-E 3 で生成して docs/img/ に保存する。
ファイルが存在する場合はスキップ。
"""
import csv
import glob
import os
import re
import requests

_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from openai import OpenAI

# 野菜名 → (ファイル名, 英語説明)
VEGGIE_MAP = {
    "いんげん":         ("ingen",       "green beans, fresh"),
    "うめ":             ("ume",          "Japanese ume plum, green"),
    "えだまめ":         ("edamame",      "edamame, green soybeans in pods"),
    "かぶ":             ("kabu",         "Japanese turnip, white round with green leaves"),
    "かぼちゃ":         ("kabocha",      "kabocha pumpkin, dark green Japanese squash"),
    "きゅうり":         ("cucumber",     "cucumber, fresh green"),
    "こまつな":         ("komatsuna",    "komatsuna Japanese mustard spinach, dark green leaves"),
    "ごぼう":           ("gobou",        "burdock root, long brown root vegetable"),
    "さつまいも":       ("satsumaimo",   "Japanese sweet potato, purple skin"),
    "さといも":         ("satoimo",      "taro root, small round brown"),
    "さやえんどう":     ("sayaendo",     "snow peas, flat green pods"),
    "しゅんぎく":       ("shungiku",     "chrysanthemum greens, bright green leaves"),
    "じゃがいも":       ("potato",       "potato, brown round"),
    "そらまめ":         ("soramame",     "broad beans, large green pods"),
    "たけのこ":         ("takenoko",     "bamboo shoots, pale yellow cone shape"),
    "たまねぎ":         ("onion",        "onion, brown papery skin round"),
    "だいこん":         ("daikon",       "daikon radish, long white root"),
    "とうもろこし":     ("corn",         "corn on the cob, yellow kernels with green husk"),
    "なす":             ("eggplant",     "Japanese eggplant, dark purple elongated"),
    "なのはな":         ("nanohana",     "rapeseed flowers, bright yellow blooms"),
    "なましいたけ":     ("shiitake",     "fresh shiitake mushroom, brown cap"),
    "にら":             ("nira",         "garlic chives, flat long green leaves"),
    "にんじん":         ("carrot",       "carrot, bright orange root"),
    "ねぎ":             ("negi",         "Japanese long onion, white and green stalk"),
    "はくさい":         ("hakusai",      "napa cabbage, pale green layered leaves"),
    "ふき":             ("fuki",         "butterbur, thick green stalks Japanese vegetable"),
    "ほうれんそう":     ("spinach",      "spinach, dark green leaves"),
    "まつたけ":         ("matsutake",    "matsutake mushroom, brown aromatic"),
    "みずな":           ("mizuna",       "mizuna Japanese salad greens, feathery leaves"),
    "れんこん":         ("renkon",       "lotus root, white with holes cross section"),
    "アスパラガス":     ("asparagus",    "asparagus, fresh green spears"),
    "オクラ":           ("okra",         "okra, green ridged pods"),
    "キャベツ":         ("cabbage",      "cabbage, round green head"),
    "スナップ実えんどう": ("snapendo",   "snap peas, plump green pods"),
    "セルリー":         ("celery",       "celery, pale green crunchy stalks"),
    "トマト":           ("tomato",       "tomato, bright red round"),
    "ピーマン":         ("pepper",       "green bell pepper, glossy"),
    "ブロッコリー":     ("broccoli",     "broccoli, dark green florets"),
    "ミニトマト":       ("minitomato",   "cherry tomatoes, small red round cluster"),
    "レイシ":           ("lychee",       "lychee fruit, pink bumpy skin"),
    "レイシにがうり":   ("goya",         "bitter melon goya, green bumpy surface"),
    "レタス":           ("lettuce",      "lettuce, light green crispy leaves"),
}


def collect_veggies_from_csv():
    """CSVから実際に登場した品目のみを返す"""
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "market_data_*.csv")), reverse=True)
    names = set()
    for f in files:
        for row in csv.DictReader(open(f, encoding="utf-8")):
            name = row.get("品目", "").strip()
            if name and name != "総入荷量" and re.match(r"\d{4}年", row.get("週", "")):
                names.add(name)
    return names


OUT = os.path.join(os.path.dirname(__file__), "docs", "img")
os.makedirs(OUT, exist_ok=True)

client = OpenAI()

veggies = collect_veggies_from_csv()
targets = {k: v for k, v in VEGGIE_MAP.items() if k in veggies}
print(f"対象品目: {len(targets)}品目")

for name, (filename, description) in targets.items():
    path = os.path.join(OUT, f"{filename}.png")
    svg_path = os.path.join(OUT, f"{filename}.svg")
    if os.path.exists(path) or os.path.exists(svg_path):
        print(f"  skip {filename} (already exists)")
        continue

    print(f"  生成中: {name}...", flush=True)
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=(
                f"Simple clean illustration of {description}. "
                "White background, flat design, food illustration style, "
                "vibrant colors, no text, no shadows, no people, square format."
            ),
            size="1024x1024",
            quality="standard",
            n=1,
        )
        img_data = requests.get(response.data[0].url, timeout=30).content
        with open(path, "wb") as f:
            f.write(img_data)
        print(f"  ✓ {filename}.png ({len(img_data)//1024}KB)")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

print("完了")
