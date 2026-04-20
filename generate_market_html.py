#!/usr/bin/env python3
import csv
import glob
from datetime import datetime

# 最新のmarket_data_*.csvを自動検出
def get_latest_csv():
    files = glob.glob("market_data_*.csv")
    if not files:
        print("CSVファイルが見つかりません")
        exit(1)
    files.sort(reverse=True)
    return files[0]

# HTML出力
def csv_to_html(csvfile, htmlfile):
    with open(csvfile, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames
    html = ["<html><head><meta charset='utf-8'><title>市場市況データ</title></head><body>"]
    html.append(f"<h1>市場市況データ ({csvfile})</h1>")
    html.append("<table border='1' cellspacing='0' cellpadding='4'>")
    html.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")
    for row in rows:
        html.append("<tr>" + "".join(f"<td>{row[h]}</td>" for h in headers) + "</tr>")
    html.append("</table></body></html>")
    with open(htmlfile, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print(f"HTML出力完了: {htmlfile}")

if __name__ == "__main__":
    csvfile = get_latest_csv()
    htmlfile = csvfile.replace('.csv', '.html')
    csv_to_html(csvfile, htmlfile)
