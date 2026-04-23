#!/usr/bin/env python3
"""
野菜画像をダウンロードして docs/img/ に保存する。
一度だけ実行すれば OK（ファイルがあればスキップ）。
"""
import os
import requests

IMGS = {
    "キャベツ":     ("cabbage.jpg",      "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Cabbage_and_cross_section_on_white.jpg/400px-Cabbage_and_cross_section_on_white.jpg"),
    "だいこん":     ("daikon.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Daikon_Radish.jpg/400px-Daikon_Radish.jpg"),
    "はくさい":     ("hakusai.jpg",       "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Napa_Cabbage.jpg/400px-Napa_Cabbage.jpg"),
    "レタス":       ("lettuce.jpg",       "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Lactuca_sativa_Lollo_Bionda_and_Lollo_Rossa.jpg/400px-Lactuca_sativa_Lollo_Bionda_and_Lollo_Rossa.jpg"),
    "きゅうり":     ("cucumber.jpg",      "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/Cucumbers_-_whole_and_slice.jpg/400px-Cucumbers_-_whole_and_slice.jpg"),
    "トマト":       ("tomato.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Tomato_je.jpg/400px-Tomato_je.jpg"),
    "ほうれんそう": ("spinach.jpg",       "https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/Spinach_leaves.jpg/400px-Spinach_leaves.jpg"),
    "ねぎ":         ("negi.jpg",          "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Allium_fistulosum_4.jpg/400px-Allium_fistulosum_4.jpg"),
    "たまねぎ":     ("onion.jpg",         "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Onions.jpg/400px-Onions.jpg"),
    "にんじん":     ("carrot.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Vegetable-Carrot-Bundle-wStalks.jpg/400px-Vegetable-Carrot-Bundle-wStalks.jpg"),
    "じゃがいも":   ("potato.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Potato_and_cross_section.jpg/400px-Potato_and_cross_section.jpg"),
    "さつまいも":   ("satsumaimo.jpg",    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Ipomoea_batatas_006.jpg/400px-Ipomoea_batatas_006.jpg"),
    "なす":         ("eggplant.jpg",      "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Eggplant_je.jpg/400px-Eggplant_je.jpg"),
    "ピーマン":     ("pepper.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Capsicum_annuum_-_Bell_peppers.jpg/400px-Capsicum_annuum_-_Bell_peppers.jpg"),
    "ブロッコリー": ("broccoli.jpg",      "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Fresh_broccoli_DSC00862.jpg/400px-Fresh_broccoli_DSC00862.jpg"),
    "カリフラワー": ("cauliflower.jpg",   "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/Cauliflower_DSC03991_white_background.JPG/400px-Cauliflower_DSC03991_white_background.JPG"),
    "ごぼう":       ("gobou.jpg",         "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Arctium_lappa_roots.jpg/400px-Arctium_lappa_roots.jpg"),
    "れんこん":     ("renkon.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Renkon.jpg/400px-Renkon.jpg"),
    "かぼちゃ":     ("kabocha.jpg",       "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Cucurbita_pepo_Potimarron_p1040998.jpg/400px-Cucurbita_pepo_Potimarron_p1040998.jpg"),
    "アスパラガス": ("asparagus.jpg",     "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/White-and-green-asparagus.jpg/400px-White-and-green-asparagus.jpg"),
    "えだまめ":     ("edamame.jpg",       "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Edamame.jpg/400px-Edamame.jpg"),
    "かぶ":         ("kabu.jpg",          "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Turnip_2622027.jpg/400px-Turnip_2622027.jpg"),
    "こまつな":     ("komatsuna.jpg",     "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Komatsuna.jpg/400px-Komatsuna.jpg"),
    "しょうが":     ("ginger.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Zingiber_officinale.jpg/400px-Zingiber_officinale.jpg"),
    "にんにく":     ("garlic.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Garlic_3.jpg/400px-Garlic_3.jpg"),
    "セロリ":       ("celery.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Celery_cross_section.jpg/400px-Celery_cross_section.jpg"),
    "チンゲンサイ": ("bokchoy.jpg",       "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Bok_choy_by_ayustety_in_Tokyo.jpg/400px-Bok_choy_by_ayustety_in_Tokyo.jpg"),
    "みずな":       ("mizuna.jpg",        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Mizuna.jpg/400px-Mizuna.jpg"),
    "_fallback":    ("fallback.jpg",      "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Salad_Garden_at_Gardenology.jpg/400px-Salad_Garden_at_Gardenology.jpg"),
}

OUT = os.path.join(os.path.dirname(__file__), "docs", "img")
os.makedirs(OUT, exist_ok=True)

headers = {"User-Agent": "yasai-recipe/1.0"}
for name, (filename, url) in IMGS.items():
    path = os.path.join(OUT, filename)
    if os.path.exists(path):
        print(f"  skip {filename}")
        continue
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"  ✓ {filename} ({len(r.content)//1024}KB)")
    except Exception as e:
        print(f"  ✗ {filename}: {e}")

print("完了")
