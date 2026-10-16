# hamio Recording 復旧CLIの独立比較

実在する `9uiLe/hamio` への機能追加を、同じ開始版から別々のDevinセッションで実装する1ペアの比較。小さなglob修正だったscope-guard比較より、CLI・Recording検証・ファイル公開・中断・文書を横断する題材を使う。既存不具合を発見したという主張ではない。

2026-10-16の[比較結果と限界](../../docs/hamio-recover-devin-comparison.md)、[機械可読結果](observations/2026-10-16/results.json)を公開した。返却patchと監査pointerも比較記録から参照できる。固定採点では両条件とも60/60・固定回帰114/114・native60/60。一方、追加テスト込みの補助検査でControlの既存TTYテスト1件が2回timeoutしたため、全検査が同じ結果だったとは扱わない。

## 事前固定

- 開始版: `59a675b4b02478fd75c230263f9ef92a385f069c`（master）。
- 共通課題: `common-prompt.txt` と `contract.md`。独立clone、製品patch・検証証拠の返却、commit/push/公開禁止を両条件へ指示する。
- Control: `control-prompt.txt`。追加Skill資料なし。
- Treatment: `treatment-prompt.txt`。固定版effectual-change Skillを読んで適用する指示とarchiveを追加する。両条件ともhamio自身の規約・project skillsは使用する。
- `protocol.json`: dispatch前の時刻、採点器・課題文hash、Skill tree/archive hash、固定runtime、正例・開始版の事前確認、採点・監査項目、限界。セッション情報は別の `dispatch.json` に記録し、protocolを後から書き換えない。

採点器と正例実装は子セッションへ渡さない。候補間でも成果物を共有しない。詳細な共通契約自体が判断を助けるため、この比較は「指示が何もないAgentに対するSkillの効果」ではない。

## 採点器

`acceptance.test.ts` は公開CLIを別processとして呼ぶ60項目。開始版のReaderだけを信頼できるoracleとして使用し、候補のReaderを合否判定に使わない。Recording状態、prefixの全Event、Runの状態、sourceの不変、既存出力の保持、0600、競合作成、中断後の後始末を確認する。390MiBの有効入力も実行する。

`grade.py` は以下を別々に記録する。

1. ソースCLIの固定60項目。
2. 開始版のtestsを重ねた既存全体検査（114テスト、lint・format・型検査・catalog）。
3. native executableのbuild。
4. native executableに対する同じ60項目。

ソースとnativeは同一要件の反復であり、120個の独立標本ではない。候補追加テストは固定回帰と分けて確認する。機能テストの数や候補固有テストの多さを、そのまま総合優劣へ変換しない。docs、bounded streaming、sync・公開順序、資源寿命、変更範囲、Skill読取りと検証証拠はprotocolの事前項目に沿ってcoordinatorが監査する（盲検ではない）。負荷試験1件だけでboundednessや性能保証を証明しない。

`reference.ts` は**採点器の正例確認専用**。凍結Readerで受理件数を得てから、再読取りしたprefixをWriterへ渡すadapterであり、比較する第三のAgent実装ではない。製品採用を推奨する実装でもない。事前確認では正例60/60、開始版14/60、固定回帰114/114となった。

## 再実行

Linux、Docker、hamio指定のNix環境を使う。開始版の独立cloneで依存を固定取得してから、Nix store closureと必要なhost loader/libraryでローカルimageを作る。Docker Hub imageには依存しない。`runtime.json` は今回実際に使用したclosure・image IDの記録であり、別hostで再構築したimageのbyte一致を保証しない。

```sh
./scripts/dev.sh bun run setup
```

上記はhamio clone内で実行する。次はeffectual-change clone内で、環境に合う絶対pathを引数へ渡す。

```sh
python3 evaluation/hamio-recover/build_image.py --help
python3 evaluation/hamio-recover/grade.py --help
python3 -m unittest discover -s evaluation/hamio-recover -p 'test_*.py' -v
```

`build_image.py` の `--baseline` は開始版clone、`--context` は未作成のbuild directory。`grade.py` の `--candidate` は開始版へ返却patchを適用したclone、`--baseline` は未変更の開始版clone、`--image` は構築したimage ID、`--output` は結果directory。依存は開始版node_modulesをreadonlyで使用する。依存変更がある候補は、まず変更の必要性と固定環境との差を監査する。

Dockerはnetworkなし、root filesystem・candidate・oracle・grader・依存はreadonly、UID65534、capabilityなし、no-new-privileges、PID256、CPU2。機能試験は512MiB、全体検査/buildは2GiB。入力fixtureはdisk上の専用書込みdirectoryへ置き、tmpfsに入力量が課金される混同を避ける。/usr/bin:/binだけを使用する既存のinstaller試験にも固定ツールを提供する。Gitのsafe.directory指定はreadonlyの `/candidate` に限定する。実行のdeadlineはhang防止用であり、製品の性能基準ではない。

CIはPythonによるrunner・固定hashのoffline検査だけを行う。CI成功をAgent比較の再実行と取り違えない。生ログはローカルに保持し、公開する結果は集計・安全なfailure名・証拠pointerに絞る。

## 解釈の範囲

1ペアからSkillの一般的な有効・無効を断定しない。macOS、全size/event上限の実測、power loss、他processによる入力同時変更は検証範囲外。正確なモデルsnapshotを確認できなければunknownと記録する。環境修正や中断がある場合、wall clockを効率改善の根拠にしない。採点結果を見て候補を修正しない。重大な採点器修正が必要なら固定比較の無効化・探索的結果への格下げを明記する。
