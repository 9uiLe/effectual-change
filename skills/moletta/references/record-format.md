# 実行記録の契約

Python 3.11 以上。公開 CLI は `scripts/moletta.py`。JSON を標準出力へ返し、不正な入力や拒否した操作は診断を返す。`check` の終了コードは準備条件を満たす場合 0、満たさない場合 1。不正な記録も `INVALID_RUN` の検査結果として 1 を返す。操作の拒否・失敗とコマンド引数の誤りは 2 を返す。

## 所有と状態

| ファイル | 所有者・用途 |
| --- | --- |
| `brief.md` | 保存した原文。封印後は変更しない |
| `intent.json` | 成果・受入条件・必須制約。封印まで編集する |
| `seal.json` | runtime が保存する実行 ID と原文・意図のダイジェスト |
| `plan.json` | エージェントが更新する要求、案、資料、実験、判断、次の行動 |
| `journal.json` | runtime が保存する観測開始・完了・判定の順序付き履歴 |
| `artifacts/` | 観測の出力・添付物、ローカルに保存した出典 |
| `checkpoints/` | 意図・計画と履歴の prefix ダイジェストを含む保存点 |

`init` は既存ディレクトリを拒否する。`seal` は同一内容に対してだけ再実行できる。観測は開始→完了→判定と進み、完了・判定はそれぞれ一回。コマンド取得とホストの出力取り込みは、同じ履歴へ保存する。

構造上の準備状況は計画と履歴から導出する。準備状況の検査結果と判定の応答には `semantic_review_required: true` を含める。

## JSON 入力

`schema_version` は 1。以下の項目は null の場合も省略しない。未知のキー、不正な型、各配列での重複した ID・リンクは拒否する。`init` が生成するテンプレートを、判断に必要な内容で埋める。

```json
{
  "schema_version": 1,
  "outcomes": [{"id": "O1", "statement": "達成したい結果", "acceptance": "観測可能な合格条件"}],
  "constraints": [{"id": "C1", "text": "人が指定した必須制約"}]
}
```

`plan.json` の最上位:

| 項目 | 内容 |
| --- | --- |
| `schema_version` | 1 |
| `target_environment` | 実証対象の環境を識別する文字列 |
| `requirements` | `{id, origin, source_quote, outcome_ids, constraint_ids, criterion}` の配列 |
| `options` | `{id, architecture, contribution, tradeoffs, subject, coverage}` の配列 |
| `notes` | `{id, kind, claim, locator, sha256, outcome_ids, requirement_ids, option_ids}` の配列 |
| `research` | `{question, source_ids, finding, applicability}` の配列 |
| `experiments` | 下記の実験の配列 |
| `review` | 下記のレビュー |
| `decision` | 下記の判断 |
| `next_action` | null または `{kind, question, rationale, timebox_minutes, stop_condition, experiment_id}` |

### 要求、案、出典

- `origin` は `explicit / derived`。明示要求の `source_quote` は原文に存在する文字列、導出要求では null。全案共通の能力を記し、方式固有の実装上の義務を必須要求へ昇格させない。
- `subject` は `{identity, revision, files}`。識別子と版を文字列で記し、入力ファイルをパスの配列で列挙する。相対パスは RUN 基準。runtime は宣言したファイルの SHA-256 を観測開始時と照合する。外部の版と列挙範囲は申告であり、未追跡の依存を自動検出しない。
- `coverage` は `{requirement_id, mechanism, status, evidence_ids}` の配列。全要求の仕組みを説明し、`status` は `supported / unknown / violated`。根拠 ID は対応する note または完了・判定済みの observation を参照する。
- note の `kind` は `source / inference`。source は HTTPS URL と `sha256: null`、または `artifacts/` 内の実在する保存ファイルと SHA-256 を使う。inference は locator・sha256 とも null。推論だけでは supported の証拠にしない。
- `research.source_ids` は source の note を参照し、問い、実際に分かったこと、適用条件を記す。

### 実験とレビュー

実験の全項目は `{id, option_id, outcome_ids, requirement_ids, question, scope, environment, pass_criterion, fail_criterion, retained_conditions, omitted_conditions, negative_control}`。`scope` は `unit / integration / end_to_end`。合否・保持条件・省く条件・否定対照を実行前に定義する。対照が不適用なら理由を記す。

`review` は `{mode, raw_brief_read, findings}`。mode は `pending / independent_context / self_review`、raw_brief_read は boolean。指摘は `{id, severity, issue, disposition, reason}`。severity は `critical / material / minor`、disposition は `open / accepted / rejected / deferred`。reason は未判断なら null、判断した場合は根拠を記す。重要な未解決指摘を採用の確定に残さない。

### 判断と次の行動

`decision` は `{status, option_id, rationale, conditions, reconsider_when}`。status は `exploring / provisional / selected / rejected`、option_id は対象 ID または null。条件は文字列の配列。理由と再考のきっかけを記す。条件付き採用は解消条件を必要とする。

`next_action.kind` は `explore / experiment / review / decide`。時間予算は正の整数の分数。実験を行う場合は experiment_id を指定し、それ以外は null。次の問い、選ぶ理由、終了条件を記す。

## 観測の適用範囲

開始時に、封印した意図、実験、対象案と仕組み、要求、宣言した対象ファイルを保存する。条件・対象・追跡入力が変わった観測を、現在の成功の根拠にはしない。

取得元は `direct_command / attested_native`。直接実行は argv・作業場所・出力・終了状態を保存する。取り込みは実際の UTF-8 操作履歴と任意の添付物、観測方法を保存する。取得元の真正性は認証しない。実行不能や timeout は合格判定にできない。

`assess` は合否と理由を追記する。失敗・不明の解消には、後続の別の合格観測を `--resolves` で対応付ける。同じ案・環境・範囲で、元の要求定義と成果を覆うことを確認する。修正に伴う対象の版の変更は認める。完了していない観測や未判定の観測も確認対象とする。

`verify` は選択案について、対象環境の合格観測が全要求を覆うことを求める。成果ごとに、その成果に対応するすべての要求を含む `end_to_end` の合格観測も必要とする。到達だけの全体観測と、変更操作の単体観測を寄せ集めて、一連の成功とは扱わない。未選択案の失敗は選択案の成功を妨げない。

## 整合性と限界

保存操作は POSIX の advisory lock で直列化し、journal をチェックサム付きで置き換える。書き込み中のプロセスが停止するとロックは自動解放される。`.write.lock` ファイルは削除しない。添付物の変更・欠落や、checkpoint に保存した履歴の書き換え・切り詰めを検出する。これはローカルファイルの誤編集を扱う仕組みであり、利用者が全記録とチェックサムを意図的に書き換えることを防ぐサービスではない。

型や整合性を満たしても、要求の意味上の網羅性、観測方法の妥当性、全体最適は証明できない。原文と観測を読む判断を併用する。
