# 実行と再開

## 記録を使う範囲

この経路は、判断が重要な探索や複数回にまたがる作業向け。入口の短い経路で十分なら、記録作成のためだけに作業を広げない。記録を使う場合の厳密な項目は [record-format.md](record-format.md) を参照する。

原文は事後の要約に置き換えず、そのまま保存する。機密や持ち出し制約は元の依頼に従う。実行ファイルはローカルで管理する。

## 開始

以下の `CORE` はこの package の `outcome-harness` フォルダ、`RUN` は新しい実行ディレクトリに置き換える。コマンドはエージェントの利用可能な実行手段から呼ぶ。

```sh
python3 CORE/scripts/harness.py init RUN --brief FILE --goal '達成したい成果'
```

生成された `intent.json` に成果と受入条件、人の必須制約を記す。`record.json` には対象環境、原文に対応する要求、全体案、調査、実験を順に追加する。固定前に原文から読み直し、意図の取り違えを直す。目的はユーザーが望む結果のまま保ち、実現手段を目的にしない。

```sh
python3 CORE/scripts/harness.py seal RUN
```

`seal` は意図を固定する。以後、分解や導出要求、案は変更できるが、意図を書き換えたり再固定したりしない。人の判断で目的・必須制約を変更する場合は、新しい実行を作り、旧実行と変更理由を文章で参照する。

## 証拠と判断を進める

現在必要な工程だけを使い、検査のために毎回人の承認を求めない。

```sh
python3 CORE/scripts/harness.py check RUN --stage plan
python3 CORE/scripts/harness.py check RUN --stage decide
python3 CORE/scripts/harness.py check RUN --stage verify
```

- `plan`: 意図、要求の出所と対応、全体案の仕組み・要求網羅、記載済みの実験設計を確認する。
- `decide`: 調査、原文レビュー、成果への寄与、案の選択、条件付き判断も確認する。
- `verify`: 実在する実行証拠との整合、対象環境への適用、成果全体の実証も確認する。

未知は探索や条件付き採用では保持できる。満足したことには変換しない。既知の必須能力違反を採用判断で隠さない。検査が成功しても意味の抜けや最良案の証明にはならない。

測定前に `record.json` へ実験を設計してから、実際のコマンドを捕捉する。

```sh
python3 CORE/scripts/harness.py capture RUN --experiment V1 --timeout 30 -- COMMAND ARG
```

標準出力・標準エラー・終了状態が保存される。戻った locator と SHA-256 を使い、観測を読んで証拠の合否を自分で記す。捕捉器は意味上の合格を推定しない。資料の URL と捕捉した測定と推論の扱いは [outcome-verify](../../outcome-verify/SKILL.md) を参照する。

## 有限の探索と再開

各調査・実験で「何が分かれば判断が変わるか」、一回の時間・試行予算、終了条件を決める。費やした量で採用を正当化しない。予算終了時は、次のうち根拠がある一つを選ぶ。

- 十分な証拠で次へ進む。
- 重要な未知と解消条件を残して限定的に進む。
- 局所修正を止め、全体案・分解を再検討する。
- 外部条件や価値判断が必要なら、その具体的な不足を残す。

```sh
python3 CORE/scripts/harness.py next RUN
python3 CORE/scripts/harness.py checkpoint RUN
```

`next` の提案を原文と実物に照らして採否判断する。出力は自動実行や承認ではない。中断前は記録を更新して `checkpoint` を作り、残る問いと次の観測を短く記す。

再開時は `brief.md`、`intent.json` / lock、`record.json`、関連する最新の実物を読み、`next` と必要な段階の `check` を行う。環境・成果物が変わったら旧証拠の適用範囲を見直す。経緯をすべて再探索せず、未解決の問いから続ける。
