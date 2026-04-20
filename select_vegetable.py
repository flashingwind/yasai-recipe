#!/usr/bin/env python3
import csv
import glob
import os

# 最新のmarket_data_*.csvを自動検出
def get_latest_csv():
    files = glob.glob("market_data_*.csv")
    if not files:
        print("CSVファイルが見つかりません")
        exit(1)
    files.sort(reverse=True)
    return files[0]

# ユニークな野菜名リストを抽出
def get_vegetable_list(csvfile):
    names = set()
    with open(csvfile, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["品目"].strip()
            if name:
                names.add(name)
    return sorted(list(names))

# 選択した野菜の全データを表示
def show_vegetable_data(csvfile, veg_name):
    with open(csvfile, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["品目"].strip() == veg_name:
                print(f"週: {row['週']}  価格: {row['価格']}  流通量: {row['流通量']}\nコメント: {row['コメント']}\nURL: {row['URL']}\n---")

if __name__ == "__main__":
    csvfile = get_latest_csv()
    vegs = get_vegetable_list(csvfile)
    print("野菜を選択してください:")
    for i, v in enumerate(vegs):
        print(f"{i+1}: {v}")
    idx = int(input("番号を入力: ")) - 1
    if 0 <= idx < len(vegs):
        print(f"\n--- {vegs[idx]} のデータ ---")
        show_vegetable_data(csvfile, vegs[idx])
    else:
        print("不正な番号です")
