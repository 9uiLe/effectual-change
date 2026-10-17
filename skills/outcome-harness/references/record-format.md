# 実行記録の形式

Python 3.11 以上と標準ライブラリを使う。以下の構造検査は、内容の真偽、要求抽出の完全性、判断の最適性を証明しない。原文からの再構成と実物の確認はエージェントの責務である。

## ファイルの責務

| ファイル | 内容 |
| --- | --- |
| `brief.md` | 利用者の元の依頼。要約に置換しない |
| `intent.json` | 人のゴール、合格条件、必須制約。`seal` 後の変更を検出する |
| `intent.lock.json` | 意図の固定時のダイジェスト。内容が変わった状態では再固定できない |
| `record.json` | 更新可能な分解、全体案、調査、実験、証拠、レビュー、判断 |
| `artifacts/` | 実行時のコマンド、実験条件、標準出力、標準エラー、終了状態 |
| `snapshots/` | 再開と振り返りのためのチェックポイント |

全 JSON の `schema_version` は `1`。`init` は元の依頼をバイト単位で保存し、`record.json` に `run_id` と `brief_sha256` を記す。`seal` は人の意図を正しく解釈したという承認ではない。原文の読み直し後にエージェントが記録を固定する操作である。

人がゴールや制約を変更したときは、新しい実行を作って旧実行と変更理由を参照する。実装方法、導出した要求、全体構成は同じ実行の中でも変更できる。古い判断や否定的結果を消して整合させず、変更前に `checkpoint` を残す。

## intent.json

```json
{
  "schema_version": 1,
  "outcomes": [{"id": "O1", "statement": "達成したい結果", "acceptance": "観測可能な合格条件"}],
  "constraints": [{"id": "C1", "text": "人が指定した必須条件"}]
}
```

ゴールを「選んだ技術を使うこと」に読み替えない。優先順位や閾値が未指定なら、根拠なく決定せず、必要なときに最小の質問をする。

## record.json の項目

`init` の生成物を更新する。ID は各配列で一意。`target_environment` は最終的に確認する環境の記述であり、測定環境と文字列一致するだけで実質的な適用性が保証されるわけではない。版、規模、権限、依存先など結果を左右する条件を含めて記述する。

| 配列 | 各項目の必須フィールド |
| --- | --- |
| `requirements` | `id`, `origin`, `source_quote`, `outcome_ids`, `constraint_ids`, `criterion` |
| `options` | `id`, `mechanism`, `outcome_contribution`, `tradeoffs`, `coverage` |
| `research` | `question`, `sources`, `finding`, `applicability` |
| `experiments` | `id`, `option_id`, `outcome_ids`, `requirement_ids`, `question`, `scope`, `environment`, `pass_criterion`, `fail_criterion`, `retained_conditions`, `omitted_conditions`, `negative_control` |
| `evidence` | `id`, `kind`, `claim`, `outcome_ids`, `requirement_ids`。種類別の項目は下記 |

`origin` は `explicit` / `derived`。明示要求の `source_quote` は原文の実際の部分文字列にする。全制約・成果が少なくとも一つの要求へ対応する必要がある。これは意味上の網羅性の検査にはならない。

`coverage` は全要求に一行ずつ置く。行の形は次のとおり。

```json
{"requirement_id": "R1", "mechanism": "この能力を実現する具体的手段", "status": "unknown", "evidence_ids": []}
```

`status` は `supported` / `unknown` / `violated`。不明は探索や条件付き採用で残せる。`supported` にはその案・要求へ適用する資料か測定が必要で、推論だけでは裏付けにならない。要求の分解を変更したら、対応する coverage と実験を更新する。

`sources` は実際に読んだ HTTPS URL または記録した `source` 証拠 ID の配列。ローカルの一次資料も source として扱える。候補を選んだ理由、調べた別方式、その除外理由を `finding` / `applicability` に短く残す。一案しか成立しない場合は、架空の比較案を追加しない。

`scope` は `unit` / `integration` / `end_to_end`。実験の説明欄は文字列。省略しない場合も `omitted_conditions` にその旨を書く。`negative_control` には失敗を見分ける対照か、対象外である具体的理由を書く。

## 実行と証拠

実験を先に記録し、利用を許されたコマンドを `capture` で実行する。既定の実行場所は呼び出し側の作業ディレクトリ。`--cwd DIR` で変更できる。シェル文字列の評価はしない。

```sh
python3 CORE/scripts/harness.py capture RUN --experiment V1 --timeout 30 --cwd PROJECT -- python3 check_behavior.py
```

終了コード 0 でも verdict は `unassessed`。観測を事前の合格条件と照合し、次の測定行を記録する。

```json
{
  "id": "E1", "kind": "measurement", "claim": "実際に確認したこと",
  "option_id": "P1", "experiment_id": "V1",
  "outcome_ids": ["O1"], "requirement_ids": ["R1"],
  "scope": "end_to_end", "environment": "対象条件の記述",
  "locator": "artifacts/capture-生成されたID.json", "sha256": "captureが返した値",
  "result": "pass"
}
```

`result` は `pass` / `fail` / `inconclusive`。`locator` は実行内の `artifacts/` 配下の相対パス。ダイジェスト、実行ID、実験ID、実行時の実験内容・意図・対象案の仕組み・要求定義が一致する必要がある。実行後に環境、判定基準、構成や要求定義を書き換えた場合は、新しい実験として測り直す。タイムアウトは失敗・判断不能の観測として保持でき、成功の根拠には使えない。

`source` は HTTPS の `locator`、`claim`、対応 ID を持つ。ローカルの一次資料は `artifacts/` 内のスナップショットへの `locator` と `sha256` でもよい。コマンドで資料を読み取った capture を source として参照することもできるが、それは動作の実測にはならない。`inference` は推論として残せるが、測定済みの証拠には数えない。

構成や分解を作り直し、過去の要求・実験が適用外になった場合は、変更前の `checkpoint` に旧記録を保持し、理由とスナップショットの場所を現判断に記す。現在の記録には現在の案に適用する要求・実験・証拠を置く。同じ構成に適用する不利な結果を、適用外という名目で取り除かない。

失敗や判断不能の測定は保持する。修正後の適用可能な成功測定で解消した場合、旧証拠に `superseded_by: "新証拠ID"` を付ける。異なる、より後の実行であることと、案、環境、範囲、要求・成果への適用を照合する。同じ観測に別のIDと成功判定を付けても失敗は解消しない。判定自体が誤っていた場合は、元の記録を残したチェックポイントと理由付きの訂正を行い、重要な採用判断には必要に応じて測り直す。

コマンド以外の GUI 動画や外部装置記録は、現版の構造検査で測定として直接取り込めない。観測を読み取る、プロジェクト固有の検証コマンドを用意するか、検証未完了と報告する。ファイルのハッシュは改変検出であり、内容の真正性や行動の意味を保証しない。

## レビューと判断

`review`:

```json
{"mode": "self_review", "raw_brief_read": true, "findings": []}
```

`mode` は `pending` / `independent_context` / `self_review`。異なる文脈の同じモデルを別モデルの独立検証とは呼ばない。指摘は `id`, `severity` (`critical` / `material` / `minor`), `issue`, `disposition` (`open` / `accepted` / `rejected` / `deferred`), `reason` を持つ。`accepted` は指摘を受け入れて解消したことを表し、`reason` に解消内容を書く。重要な未解消・先送り指摘は採用準備・完了の判断を止める。

`decision` は `status` (`exploring` / `provisional` / `selected` / `verified` / `rejected`), `option_id`, `rationale`, `conditions`（文字列配列）, `reconsider_when` を持つ。既知の必須能力違反は採用しない。未確認の能力を持つ案の採用は、具体的条件付きの `provisional` に限る。

`verify` は、選択した案の全要求に対象環境の成功測定、さらに成果全体に `end_to_end` の成功測定を要求する。構造上の準備が整っても、原文の意味、観測の十分性、全体案の優劣は別に判断する。`verified` と表示するだけで検査が省略されることはない。
