# scope-guard: 独立Devin比較の採点器

実在する `9uiLe/plugins` の `src/**/allowed.ts` が `src/notallowed.ts` を誤許容する課題を扱う。[製品修正](https://github.com/9uiLe/plugins/pull/129)の再実装を独立セッションへ依頼し、Skillなし／ありの候補を親側で採点する。Codex CLI用ランナーやClaude CodeのSkill自動起動試験ではない。

## 固定条件

- 開始版: `48bcdc16a5480921cf95f3b9fa380ca43f676dbc` (`9uiLe/plugins`)
- TreatmentのSkill版: `2a1680b8da3042ace32f52dc06330acb17da7a03` (`9uiLe/effectual-change`)
- 各条件1回。別VM・別会話、親と同じモードを指定して作成。実際のモデルスナップショット一致までは保証できない。
- [共通課題](common-prompt.txt)、[Controlの全文](control-prompt.txt)、[Treatmentの全文](treatment-prompt.txt)を保存した。ControlへSkill本文を渡さず、Treatmentだけに固定版Skillを添付する。一方の候補・採点結果をもう一方へ渡さない。
- [protocol.json](protocol.json)はdispatch前に作成した開始SHA・Skill版・実行順・採点器とpromptのSHA256を保持する。採点器は候補回収後も変更しない。
- 具体的な解答・修正後テストの注入が判明した試行は停止する。一般規約や過去PR題名だけの注入も記録し、完全に無知なControlとは主張しない。

## 採点と隔離

[grade.mjs](grade.mjs)は43ケースを候補の外で固定する。0階層・多階層、近接ファイル名、拡張子違い、別ディレクトリ、単独の `*` / `**`、相対・絶対パス、glob union、opt-in、fail-open、重複抑制、`agent_id`、`NotebookEdit`、実stdin/stdoutを検証する。

[grade.py](grade.py)はheld-out採点と開始版から固定した回帰テストを別々に実行する。候補が追加・変更したテストは固定回帰テストを置換できない。コンテナはネットワークなし・read-only・非root・全capability削除・no-new-privileges。候補と採点器はread-only、書き込み可能領域は `/tmp` のtmpfsのみ。CPU・メモリ・プロセス数・実行時間の制限は実行保護用であり、Skillの成績閾値ではない。

これはコンテナ内実行の制限であって、敵対的コードから採点器を隠す機密境界ではない。候補はimport先の同一Nodeプロセスで動く。差分は実行前に許可範囲と採点器への干渉の有無をレビューする。Docker起動失敗、タイムアウト、JSON破損はAgentの機能失敗と混同せず、評価基盤エラーとして調べる。

事前確認では開始版が33/43・固定回帰65/65、既知修正版が43/43・固定回帰65/65。最初のローカルイメージではbash/jq不足による固定回帰3件の環境エラーがあり、両条件の実装開始前に修正・再確認した。

## 再実行

Docker、Python 3.10以降、Nodeとbash・jq・catを含むローカルイメージが必要。今回Docker Hubは429のため、既存Linuxランタイムとその動的ライブラリを `FROM scratch` にコピーしたイメージを使用した。イメージIDはprotocol、コピー元のハッシュは [runtime-files.json](runtime-files.json) に記録する。イメージ自体は配布せず、別ホストで同一イメージIDを取得できるとは保証しない。別イメージでの実行は環境を変えた追試として記録する。

以下はこのリポジトリのルートから実行する。`PLUGINS_REPO` は開始版を含むローカルGitリポジトリ、`PATCH` はレビュー済み候補差分の絶対パス、`IMAGE` は用意したローカルイメージIDに設定する。新規の作業用ディレクトリを使い、候補差分をホスト上で実行しない。

~~~bash
BASE=48bcdc16a5480921cf95f3b9fa380ca43f676dbc
mkdir candidate frozen
git -C "$PLUGINS_REPO" archive "$BASE" plugins/model-strategy | tar -x -C candidate
git -C "$PLUGINS_REPO" archive "$BASE" plugins/model-strategy/tests | tar -x -C frozen
git -C candidate apply --check "$PATCH"
git -C candidate apply "$PATCH"
python3 evaluation/scope-guard/grade.py --image "$IMAGE" --candidate "$PWD/candidate/plugins/model-strategy" --frozen-tests "$PWD/frozen/plugins/model-strategy/tests" --output result.json
~~~

オフラインrunnerテストはDockerもAgentも起動しない。CIの成功は独立比較の実施証拠とは区別する。

~~~bash
python3 -m unittest discover -s evaluation/scope-guard -p 'test_*.py' -v
~~~

## 解釈の制限

実装者から独立した実行・固定テストではあるが、採点器の設計者は既知修正版を知っている親Agentであり、盲検の第三者レビューではない。課題文自体が負例と維持条件を詳しく指定するため、両条件を助ける。小さな既知不具合・単一ペアでの差なしも、Skillの有効性・無効性の証明にはしない。中断・再開を含むため所要時間による効率比較はしない。トークン費用、追加負担、保守性、従来Skill O／現行Nの差は別の検証が必要。
