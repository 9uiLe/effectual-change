---
name: outcome-verify
description: 成果物や試作品を実際に動かし、要求と目的への到達を証拠付きで検証する。局所試験を全体成功と混同しない確認、実験結果の適用範囲の判定、完了判断に使う。
---

# Outcome Verify

[workflow.md](../outcome-harness/references/workflow.md) の実行・記録と [record-format.md](../outcome-harness/references/record-format.md) の実験・証拠項目を読む。

## 実行前

- 原文と意図を読み直し、何を観測すればどの要求・成果が満たされるか確認する。実装をなぞるだけの試験より、利用者に見える振る舞いを試す。
- 実験の合否条件、対象案、成果・要求、範囲、環境、保持・省略条件、否定対照を先に記す。危険な操作や外部変更は元の権限に従う。検証の名目で権限を広げない。
- `unit` は部分、`integration` は接続、`end_to_end` は成功までの全体経路。別環境の成功を対象環境の成功と同一視しない。

## 実物と証拠

1. 利用可能なコマンドで検証を実行し、共有 runtime の `capture` で標準出力・標準エラー・終了状態を保存する。表示された artifact locator と SHA-256 を正確に使う。想定出力を測定結果として書かない。
2. 得られた出力と実物を見て、事前条件に照らし `pass / fail / inconclusive` を付ける。終了コード 0 は自動合格ではない。画像、画面、文書などはその実物の確認も含め、必要な追加証拠を保存する。
3. `evidence` を `source / measurement / inference` に分ける。測定は実験との対応、実行 ID、実在する捕捉ファイルとハッシュ、対象案、成果・要求、範囲・環境を一致させる。推論を実測へ格上げしない。
4. 失敗・不明も残し、条件不足、方式の限界、実装不備を区別する。否定対照が同じ成功を返すなら、試験が能力を識別しているか再検討する。

捕捉は実行記録の存在と整合性を支える。画面の意味、測定器の妥当性、期待した作用との因果関係まで自動で保証しない。

## 到達を判定する

`verified` には、選んだ案の全要求に対する合格の実測と、対象環境で全成果を覆う `end_to_end` の証拠が必要。単体試験の集合だけでは代用しない。未解決の critical / material 指摘がある場合も到達扱いにしない。

`check --stage verify` で構造と証拠を確認したうえで、原文からの意味上の抜けを再確認する。必要なら [delegation.md](../outcome-harness/references/delegation.md) の原文レビューを使う。対象環境で試せなければ、その限界と次の確認を示して `provisional` または `selected` にとどめる。

全体試験に失敗したときは、同じ実装の修正だけに閉じず [outcome-explore](../outcome-explore/SKILL.md) / [outcome-compare](../outcome-compare/SKILL.md) で分解・全体案を再検討する。最後に、達成したこと、証拠、残る条件、次の行動を伝える。
