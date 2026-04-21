#!/usr/bin/env python3
"""
Claude API で統計的なランキングルールを一度だけ生成する。
生成されたルールは ranking_rules.py に固定化される。
"""
import json
import os
import sys

_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

import anthropic

client = anthropic.Anthropic()

system_prompt = """あなたは青果マーケティングと統計分析のプロです。
消費者にとって「おすすめの果実」を評価するための数学的ルールを設計してください。

以下のデータポイントを使用して、0～100点のスコアを計算する公式を提案してください：
- 入荷量（t）: 豊富さ（消費者が手に入れやすい）
- 前週比（%）: トレンド（供給が増えているか）
- 前年比（%）: 季節性（この時期が旬か）
- 価格（円）: 手頃さ（高いほど買いにくい）

回答は JSON フォーマットで、以下の構造にしてください：
{
  "description": "ルールの説明",
  "factors": [
    {
      "name": "因子名",
      "source": "データポイント",
      "weight": 重み係数,
      "formula": "計算式（max_XXX は全品目の最大値）",
      "notes": "注記"
    }
  ],
  "final_score_formula": "最終スコア計算式",
  "example": "具体例"
}
"""

user_message = """現在の市況データに基づいて、消費者にとって最適な果実をランキングするための統計的ルールを生成してください。

考慮すべきポイント：
1. 供給が豊富だと消費者は手に入れやすい（入荷量）
2. 供給が増えているのは人気がある可能性（前週比）
3. この季節が旬なら美味しさが保証される（前年比）
4. 安いほど家計に優しい（価格）

これらを統計的に組み合わせたランキング公式を設計してください。"""

print("Claude API でランキングルールを生成中...\n")

response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1500,
    system=system_prompt,
    messages=[
        {"role": "user", "content": user_message}
    ]
)

result_text = response.content[0].text
print(result_text)
print("\n" + "="*60)

# JSON部分を抽出
json_match = result_text.find('{')
json_end = result_text.rfind('}') + 1
if json_match >= 0 and json_end > json_match:
    json_str = result_text[json_match:json_end]
    try:
        rules = json.loads(json_str)
        with open("ranking_rules.json", "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        print("\n✅ ルールを ranking_rules.json に保存しました。")
    except json.JSONDecodeError:
        print("\n❌ JSON パースエラー")
        sys.exit(1)
else:
    print("\n❌ JSON が見つかりません")
    sys.exit(1)
