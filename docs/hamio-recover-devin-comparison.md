# hamio Recording復旧CLIの独立Devin比較（2026-10-16）

## 結論

実在する `9uiLe/hamio` へのRecording復旧CLI追加を、Skillなし／ありの独立したDevinセッションで比較した。**事前固定の機能・回帰・native検査では、両条件とも全項目に成功し、差は観測されなかった。** 一方、候補追加テスト込みの補助検査ではControlの既存TTYテスト1件が2回タイムアウトした。全検査が同じ結果だったという結論ではない。

Skill一般の有効性については **INCONCLUSIVE**。1ペアで、詳細な共通契約と既存の開発規約が両条件を支援している。補助検査の差も含め、Skillの因果効果や勝者を断定しない。Skill本文は変更していない。候補は評価資料であり、hamioへの採用・リリースを意味しない。

## 課題と開始条件

前回の[scope-guard比較](scope-guard-devin-comparison.md)より大きな題材として、ユーザーがhamioを選択した。既存不具合の修正ではなく、既存製品への機能追加である。

- 公開入口: `hamio presentation recover --input RECORDING --output RECORDING`。
- 既存Readerが受理したEvent prefixのみを別のcanonical Recordingへ救出する。StateからEventを合成せず、不正位置以降を探索せず、Runの業務結果を補完しない。
- 入力不変、既存出力の上書き禁止、同directoryのtemporaryへのwrite/sync/close後の排他的公開、0600、中断・I/O失敗時の片付け、bounded streaming、既存CLI・Recordingとの互換性を要求する。
- 開始版: [hamio `59a675b`](https://github.com/9uiLe/hamio/commit/59a675b4b02478fd75c230263f9ef92a385f069c)。両条件とも新規cloneのdetached HEADで実装したと報告し、親側でも同SHAへpatchを適用した。
- [事前登録 `377774b`](https://github.com/9uiLe/effectual-change/commit/377774b3dc9b790536333dced45b6e33c0edf0a9)をdispatch前にpush。[契約・prompt・採点器](../evaluation/hamio-recover/README.md)、[protocol](../evaluation/hamio-recover/protocol.json)、[dispatch](../evaluation/hamio-recover/dispatch.json)を固定した。結果閲覧後に候補・採点器は修正していない。

| 条件 | セッション | 追加資料 |
| --- | --- | --- |
| Control | [594be8d0](https://app.devin.ai/sessions/594be8d0d4664c109be3343af368ed33) | 共通課題・契約のみ。effectual-change archiveなし |
| Treatment | [f26ebe02](https://app.devin.ai/sessions/f26ebe02c0bc45efabbf2a97ff95a030) | 同じ課題・契約と固定Skill archive、読取り・適用・証拠記録の指示 |

Treatmentのarchive SHA-256は `460a648cc802bb62d8398415502e9ec8fe165246d123a27e1dedb9dda4dcdfd0`。Skill treeは `e8b9c88a5fc0fcb9743985d32df25d8f5dd3aae6`。両セッションは同じ親modeを継承し、arm固有のoverrideはない。正確なmodel snapshotは独立に観測できず、**unknown**とする。

## 固定採点の結果

親側が返却patchを変更せず適用し、同じ固定Docker image、ネットワークなし・readonly mount・非rootの環境で採点した。開始版のReaderをoracle、開始版のtestsを固定回帰として使用し、候補自身の判定だけを信頼しない。

| 事前固定の検査 | 開始版の事前確認 | Control | Treatment |
| --- | ---: | ---: | ---: |
| ソースCLIの共通受入 | 14/60 | **60/60** | **60/60** |
| 固定の既存回帰 | 114/114 | **114/114** | **114/114** |
| lint・format・typecheck・Catalog | 成功 | **成功** | **成功** |
| native build | 成功 | **成功** | **成功** |
| native CLIの同じ受入 | 14/60 | **60/60** | **60/60** |

正例adapterの事前確認は60/60。ソースとnativeは同じ60要件の反復であり、120個の独立標本ではない。390MiBの有効入力、通常fileのstreaming中断、競合作成、symlink/hardlinkを含む上書き禁止、破損UTF-8・JSON・状態遷移、全Event prefixの保持も共通受入に含む。

固定環境はLinux x86_64、Bun 1.4.2、Node 24.20.0、Nix 2.35.3。image IDは `sha256:f7bbf17a2429835504b49be6459545291bd1500e132c47cfc4e341583282faa1`。機能試験512MiB、全体検査/build 2GiB、CPU2。詳細なclosureと再実行手順は[runtime](../evaluation/hamio-recover/runtime.json)と[runner README](../evaluation/hamio-recover/README.md)にある。別hostでのimage再構築のbyte一致は保証しない。

## 補助検査と未解決の差

固定回帰は追加テストを含まないため、親側で候補自身の全testsを含む `bun run check` も実行した。同じimage・2GiB・CPU2・ネットワークなしを使用したが、これは候補ごとに内容・件数が異なる**補助観測**であり、共通採点へ後付けで加重しない。

| 親側・候補追加テスト込み | Control | Treatment |
| --- | --- | --- |
| 初回 | 198 pass / 1 fail、exit 1 | 181 pass / 0 fail、exit 0 |
| 両条件を直列で再確認 | 198 pass / 1 fail、exit 1 | 181 pass / 0 fail、exit 0 |

Controlで失敗したのは既存 `tests/interaction.test.ts` の `real TTY routes UI to stderr, returns answers to stdout and masks secrets`（5000ms timeout）。初回はTreatmentの固定採点と実行が重なっていたため、候補・image・上限を変えず両条件を直列でも確認した。結果は変わらなかった。両条件の固定114件では同じTTYテストも成功している。原因は候補コード・追加テストとの干渉・Bun/PTY timing等へ分離できておらず、環境起因とも製品のTTY回帰とも断定しない。失敗を削除したり、timeoutを延長したり、候補を修正したりしていない。Controlの子は全体199件成功と報告したが、親側の追加テスト込み全体検査では再現できなかった。

Treatmentの子側の全体検査は175 pass / 6 failだった。共通の「commit/push禁止」を一時Git fixtureにも適用するwrapperを置き、既存hooks 5件・release source identity 1件のローカルcommit/pushを遮断したためで、子自身も完了扱いしていない。Controlはこれらを通常のローカルfixture検査として実行した。共通指示が製品repositoryだけを対象とするのか、一時fixtureも含むのかを明示していなかった点は**比較手順の曖昧さ**である。親側では両候補に同じ通常の検査を適用し、これら6件は成功した。子側の6 failを製品回帰やSkillの害とは扱わない。

## 変更と証拠の監査

事前登録した監査項目に沿ってcoordinatorが確認した。盲検・独立judgeによる監査ではない。根拠は下記の返却patch、[集計](../evaluation/hamio-recover/observations/2026-10-16/results.json)、[監査pointer](../evaluation/hamio-recover/observations/2026-10-16/audit.json)。

| 観点 | Control | Treatment |
| --- | --- | --- |
| 変更範囲 | 12 files、+915/-14 | 8 files、+696/-12 |
| Event受理 | 既存ReaderのdecoderとSession.accept後にawait可能なsink | 同じ既存Readerのheader/Event observerをawait |
| 書込み | 既存RecordingWriterへ所有済みfileとSignalを渡す入口を追加 | Writerは変更せず、救出用moduleでcanonical encode・上限・fileを管理 |
| 公開・資源寿命 | 同directoryのwx/0600、write→sync→close→link、finallyで片付け | 同じ公開順序・排他的link、finallyでclose/unlink |
| 分類・互換性 | RunとRecordingを分離。固定回帰成功 | 同左 |
| テスト・文書 | 新規救出2 test filesとnative検査、公開文書3 files | 新規救出1 test file、公開文書3 files |
| 依存・検査設定 | 依存・lockfile・検査設定の変更なし | 同左 |

両方とも全入力・Event履歴の配列化をせず、受理済みEventを順にawaitして保存する構造だった。390MiB試験の成功と合わせてbounded streamingの根拠とするが、全入力に対する形式的証明や一般的な性能保証ではない。I/O故障・中断の追加テストもあるが、fault injectionと実disk full・power lossは同一ではない。ファイル数・行数・候補固有テスト件数から、小さい方が優秀、または多い方が高品質とは採点しない。

Treatmentではchecksum確認、`SKILL.md`、`references/decision-loop.md`、`assets/change-decision.md`の読取りを実行traceで確認した。既存Reader再利用、安全な損失境界、公開前の検証、未確認事項の分離に結び付けた意思決定記録がある。Skillを読んだ証拠と、その判断がSkillなしでは生じなかったという証拠は別である。ControlもReader再利用・安全な公開・失敗試験を行っている。

Controlの可視traceで `effectual-change` を検索した結果は、開始時のrepo setup情報と親directoryの一覧のみで、Skill本文を開いた操作は見つからなかった。両子は開始時に今回の具体的解法・他試行を含まないと自己申告した。ただしsnapshotにはeffectual-change等のcloneが存在し、両VMから物理的に利用不能だったわけではない。共有メモリ・常設規約・hamio自身のskillsもあるため、完全な情報隔離や「関連原則を何も知らないControl」とは主張しない。

## 成果物と再確認

- [機械可読結果](../evaluation/hamio-recover/observations/2026-10-16/results.json)：固定採点、補助検査の両試行、patch hash、子証跡原本のhash。
- [Control patch](../evaluation/hamio-recover/observations/2026-10-16/control.patch)：SHA-256 `082e56192530124a9795a9a987c4728b51e2d338995510cb0f7af7dc3ac1cd7e`。
- [Treatment patch](../evaluation/hamio-recover/observations/2026-10-16/treatment.patch)：SHA-256 `4c5ea275916107d1a37cf1c562b84e2a17363b3ab12b77256819fe2dc4e709a3`。

各patchを開始版の別cloneへ `git apply --check` 後に適用し、[runner](../evaluation/hamio-recover/README.md#再実行)へ渡す。生ログ・子証跡原本・auth付きattachment URLは公開しない。原本は子セッション側、公開版は集計と必要なpointerに限定する。このrepoのCIはrunner/hash等のoffline検査であり、Devin試行・Docker内の製品採点を毎回再実行するものではない。

## 解釈上の限界

- 1ペア・非盲検で、正確なmodel snapshotはunknown。記述的比較であり一般的な因果推論ではない。
- 共通契約が詳細で、既存規約・project skillsも両条件を助ける。今回測ったのは追加archiveと適用指示の差である。
- 固定60項目では両候補が上限に達した。8〜12 filesを横断する実装になったが、変更規模が大きいだけでSkill差を検出できるとは限らない。
- 補助検査のTTY timeoutと、一時Git操作の権限解釈の差が残る。全検査成功・同じ作業経路・同じ検証完了度とは扱わない。
- macOS/arm64、全size/event上限、実disk full、他filesystem、OS crash/power loss、同時変更入力のsnapshot保証は未検証。通常fileの中断をFIFO等の即時中断保証へ一般化しない。
- 子の環境構築、実行の重なり、tool variabilityがあるため、wall clock/ACUを効率の優劣に使わない。

**この試行の記録はIssue #3の追加資料であり、有効性の実証完了やIssueを閉じる根拠ではない。**
