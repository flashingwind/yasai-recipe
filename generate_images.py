#!/usr/bin/env python3
"""
OpenAI DALL-E 3 で野菜画像を生成して docs/img/ に保存する。
ファイルが存在する場合はスキップ。
"""
import os
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

VEGGIES = {
    "キャベツ":     ("cabbage",     "cabbage, round green leafy head"),
    "だいこん":     ("daikon",      "daikon radish, long white root vegetable"),
    "はくさい":     ("hakusai",     "napa cabbage, chinese cabbage"),
    "レタス":       ("lettuce",     "lettuce, green leafy"),
    "きゅうり":     ("cucumber",    "cucumber, green"),
    "トマト":       ("tomato",      "tomato, red round"),
    "ほうれんそう": ("spinach",     "spinach, dark green leaves"),
    "ねぎ":         ("negi",        "Japanese green onion, long white and green"),
    "たまねぎ":     ("onion",       "onion, brown round"),
    "にんじん":     ("carrot",      "carrot, orange root vegetable"),
    "じゃがいも":   ("potato",      "potato, brown round"),
    "さつまいも":   ("satsumaimo",  "Japanese sweet potato, purple skin orange flesh"),
    "なす":         ("eggplant",    "eggplant, purple elongated"),
    "ピーマン":     ("pepper",      "green bell pepper"),
    "ブロッコリー": ("broccoli",    "broccoli, green florets"),
    "カリフラワー": ("cauliflower", "cauliflower, white florets"),
    "ごぼう":       ("gobou",       "burdock root, long brown root"),
    "れんこん":     ("renkon",      "lotus root, white with holes cross section"),
    "かぼちゃ":     ("kabocha",     "kabocha pumpkin, dark green Japanese squash"),
    "アスパラガス": ("asparagus",   "asparagus, green spears"),
    "えだまめ":     ("edamame",     "edamame, green soybeans in pods"),
    "かぶ":         ("kabu",        "turnip, white round with green top"),
    "こまつな":     ("komatsuna",   "komatsuna, Japanese mustard spinach"),
    "しょうが":     ("ginger",      "ginger root, beige knobby"),
    "にんにく":     ("garlic",      "garlic bulb, white"),
    "セロリ":       ("celery",      "celery, green stalks"),
    "チンゲンサイ": ("bokchoy",     "bok choy, green Chinese cabbage"),
    "みずな":       ("mizuna",      "mizuna, Japanese salad greens"),
}

OUT = os.path.join(os.path.dirname(__file__), "docs", "img")
os.makedirs(OUT, exist_ok=True)

client = OpenAI()

for name, (filename, description) in VEGGIES.items():
    path = os.path.join(OUT, f"{filename}.png")
    if os.path.exists(path):
        print(f"  skip {filename}.png")
        continue

    print(f"  生成中: {name} ({filename}.png)...")
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Simple clean illustration of {description}, white background, food icon style, no text, no shadows, flat design, square",
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url
        img_data = requests.get(url, timeout=30).content
        with open(path, "wb") as f:
            f.write(img_data)
        print(f"  ✓ {filename}.png ({len(img_data)//1024}KB)")
    except Exception as e:
        print(f"  ✗ {filename}: {e}")

print("完了")
