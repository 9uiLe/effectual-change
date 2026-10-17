# 行動評価と改善

Moletta の改善は、実際の成果、見落とし、根拠の範囲、作業負担で判断します。記録数、案の数、自信のある文章、構造テストの成功は、判断改善の測定値ではありません。

## コーパスと責務

`evaluation/cases/` は元の依頼、`evaluation/artifacts/` は架空の製品資料や編集対象、`evaluation/rubrics/` は評価者専用の基準です。実在製品の仕様を表す資料ではありません。評価器はエージェントを起動せず、自然言語の採点も行いません。

| 公開ケース | 分類 | 観察する成果 |
| --- | --- | --- |
| `arrival-action-verification` | regression | 人の逐次操作なしの到達・変更操作・保存結果の照合 |
| `whole-system-throughput` | regression | 部品速度から全工程の完了へ比較単位を保つ |
| `unfamiliar-change-mechanism` | regression | 未知の方式と適用条件を資料から調べる |
| `prototype-environment-gap` | regression | 試作条件と実証対象の違いを判断へ反映する |
| `simple-label-edit` | regression | 小変更を完了し、過剰な工程を課さない |
| `crash-consistent-catalog` | transfer | 別分野で中断・復旧・全体整合性を扱う |

公開ケースは作成者も読めるため、未見の holdout ではありません。改善の昇格判断には、独立した評価者が新しく作成し、候補の調整に使っていない非公開 holdout が必要です。公開コーパスだけで回帰比較はできますが、昇格条件は満たせません。比較可能な行動評価結果は本リポジトリには含みません。

## CLI

Python 3.11 以上、標準ライブラリのみ。公開入口は `evaluation/evaluate.py` です。

```sh
python3 evaluation/evaluate.py validate
python3 evaluation/evaluate.py list
python3 evaluation/evaluate.py prepare arrival-action-verification --dest /absolute/path/to/new-packet
```

`prepare` は新しいパケットを作り、内容のダイジェストを返します。依頼と許可された原資料だけを含め、rubric・分類・評価メモを渡しません。path traversal と symlink を拒否します。

パケットはアクセス制御ではありません。実行者には新しい文脈と、パケット・対象技能・隔離した作業場所だけを与えます。採点基準や期待する見落としを伝えず、ファイルと会話の境界は実行環境で制限します。境界を指示だけで指定した実行を、厳密に隔離された評価とは報告しません。

## 同条件で実行する

基準版と候補版には同じ依頼、モデル、effort、ツール、初期環境、制御プロンプト、時間・token・turn 上限を与えます。技能 revision と arm の表示名だけを変えます。cache、並列度、実行順序などに差がある場合は限界として記録します。

実行ごとに全ツール履歴、失敗を含む最終応答、編集した成果物、利用量の出所を保存します。下位エージェント分も集計します。取得できない費用は null とし、0 と推定しません。評価者は実行を修正したり、片方だけ追加のヒントを与えたりしません。

## 独立して採点する

実行していない評価者が、原文と資料、rubric、実際の履歴と成果物を読みます。可能なら arm を伏せ、順序を変えます。重要な判定で異論があれば、根拠と異論を残して独立に再判定します。

```sh
python3 evaluation/evaluate.py template --arm baseline --output /absolute/path/to/baseline/verdict.json
python3 evaluation/evaluate.py template --arm candidate --output /absolute/path/to/candidate/verdict.json
```

テンプレートは未完成で、記入するまで有効な結果にはなりません。

| 項目 | 必須内容 |
| --- | --- |
| `evaluation_id` | 両 arm で同一の評価 ID |
| `configuration` | label、skill_revision、model、effort、tools、environment_id、control_prompt_sha256、budget |
| `budget` | max_tokens、max_seconds、max_turns |
| `judge` | id、independent_of_solver: true、タイムゾーン付き judged_at |
| ケースのハッシュ | packet_sha256、rubric_sha256 |
| `artifacts` | 保存したファイルの path、sha256、role |
| `metrics` | wall_seconds、solver_turns、input_tokens、output_tokens、cost_usd |
| `complete_transcript` | 完全な履歴を保存したという宣言 true |
| rubric の判定 | 全 criterion の met / partial / missed、全 critical failure の occurred |
| `process_assessment` | 不要な手順が成果達成を妨げたかと根拠 |

保存ファイルは verdict の親ディレクトリ内に置き、正規化した相対パスで参照します。絶対パス、上位への参照、symlink は拒否します。`role` は `transcript / result / usage`。transcript と usage は必須です。各判定は登録済みファイル、location、具体的 observation を参照します。

独立性、履歴の完全性、観測の説明、利用量の真実性は人の責任です。ツールは宣言の形式とファイルの整合性を調べるだけで、その真偽を証明しません。

## 比較と昇格条件

```sh
python3 evaluation/evaluate.py grade --baseline /absolute/path/to/baseline/verdict.json --candidate /absolute/path/to/candidate/verdict.json --output /absolute/path/to/report.json
```

各 criterion を重み付きで 1 / 0.5 / 0 に換算し、ケースごとに 100 点へ正規化します。ケース間は等重みです。重大失敗は平均点とは別に扱います。結果にはケース別の差、重大失敗、過剰手順、時間・turn・token・費用を含めます。費用に未知があれば総額は null とし、既知分の小計を示します。

次の場合は昇格を止めます。

- 条件の不一致、凍結したケースの不足、実行予算超過。
- 候補の重大失敗、ケースごとの点数悪化、新しい過剰手順。
- 独立採点による平均点の改善がない。
- fresh holdout がない、または調整への利用・初回露出について必要な宣言を満たさない。

満たした場合も `eligible_for_review` とし、自動反映しません。実費、時間、判断の不確実性を合わせて採用を決めます。

## 非公開 holdout

評価者は `cases/`・`artifacts/`・`rubrics/` を含む凍結コーパスを別の場所に作り、回帰ケースと新しい `split: holdout` のケースを入れます。CLI の `--suite` はサブコマンドの前に指定します。

```sh
python3 evaluation/evaluate.py --suite /absolute/path/to/private-suite validate
python3 evaluation/evaluate.py --suite /absolute/path/to/private-suite template --arm baseline --output /absolute/path/to/baseline/verdict.json
```

同じ suite を準備・テンプレート・採点に使います。holdout の判定行には `holdout_exposure` の `not_used_for_candidate_tuning` と `solver_first_exposure_in_this_run` を記入します。両 arm とも true が必要です。これは宣言であり、未見性の機械的な証明ではありません。holdout を使って候補を直した場合は、新しい非公開ケースを作ります。

## 限定して育てる

実際の失敗を保存し、原因仮説と適用条件を限定して小さい候補を作ります。回帰例だけでなく、小変更への過剰適用と未使用分野を確認します。変動が大きい課題では実行順序を均衡させて複数回比較し、成功例だけを選びません。効果が支持された範囲だけを採用します。
