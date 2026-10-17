# 現行版と候補版の限定反証試行 — 2026-10-17

現行9e1823bと、レビューを具体的操作列による反証に置き換えた候補を比較。候補は指示2ファイル・計199文字の差分だけで、runtime/API/記録形式/必須担当数は同一。未使用3領域と小さな対照2件を各版2回、計20回実行した。

3実質課題＋2対照課題、2条件、各2反復、全20計画枠。以下の比較は現行 → 候補。機械可読な全原採点は [同名JSON](2026-10-17-refutation-trial.json)、測定した指示は [候補差分](2026-10-17-refutation-candidate.patch)。この差分は出荷技能へ適用していない。

**現行版を維持** — 今回の反証型レビューへの常時置換は採用せず、現行版を維持する。成果に残る見落とし・誤検出・人への不要な作業は改善を確認できず、候補は合計時間14.1%、総token26.2%、非cache入力14.7%が増えた。

## 品質と結果

品質は各実行の得点率を課題内で2反復平均し、その後で課題を等重みに平均します。異なる満点の生点数を加算しません。得点は成功確率・網羅率ではなく、未知の見落としがない証明でもありません。

表の品質点は凍結した独立原採点を維持しています。展示ZIPの比較H2は原文より強い要求を含み、字幕の引渡しW3は独立意見で判定が分かれました。原文に揃えれば両版とも100点相当です。これらを実証された残存欠落や品質低下とせず、下の欠落件数は原文照合の裁定を使用します。原採点・追加意見・裁定をすべて公開し、点数差から採否を決めていません。

| 課題群 | 凍結原採点（等重み） | 重大失敗 | 実際の誤検出 | 結果に関わる誤要求 |
| --- | --- | --- | --- | --- |
| 実質課題3件 | 97.50/100 → 95.42/100 | 0 → 0 | 0 → 0 | 0 → 0 |
| 対照課題2件 | 100.00/100 → 100.00/100 | 0 → 0 | 0 → 0 | 0 → 0 |
| 全5課題 | 98.50/100 → 97.25/100 | 0 → 0 | 0 → 0 | 0 → 0 |

| 課題群 | 検出 | 解決・妥当な限定 | 設定した欠落の残存 | 別の残存欠落 |
| --- | --- | --- | --- | --- |
| 実質課題3件 | 20 → 既知分 19（欠測1） | 20 → 20 | 0 → 0 | 0 → 0 |
| 対照課題2件 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| 全5課題 | 20 → 既知分 19（欠測1） | 20 → 20 | 0 → 0 | 0 → 0 |

検出と正しい解決は別。欠落件数は実行単位で、同じ欠落の2反復は2回数える。任意の留保や正しい対照反応は実際の誤検出ではない。

- cedar — 並行受付を壊さない予約処理: 両反復・両版で、同時受付・重複再送・容量と保存を扱い、実際の確認を行った。
- harbor — 公開してよい展示ZIPの生成: 両版のZIPは公開対象・図版対応・クレジットを満たす。短い代案比較には凍結基準と原文の要求の強さに解釈差がある。
- willow — 未知の字幕方式と運用の接続: 両版で音声入口・両言語・両参加者・出力を結ぶ提案をした。引渡しの具体性は原文を基準に裁定し、ライブ運用の成功とは扱わない。
- pebble — 既知の小さな末尾修正: 両版とも指定の末尾だけを変更し、用意されたテストを実行。
- meadow — 確定情報からの案内作成: 両版とも確定情報を維持し、追加の人の作業を要求しなかった。

## 全20実行

| 実行ID | 課題 | 反復 | 条件 | 状態 | 生得点 | 検出 / 解決 / 残存 | 重大 / 誤検出 / 誤要求 | 秒 | 総token | 観測 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cedar-current-1 | 並行受付を壊さない予約処理 | 1 | 現行 | 完了 | 100.00/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 82.374 | 230,551 | 両反復・両版で、同時受付・重複再送・容量と保存を扱い、実際の確認を行った。 |
| cedar-candidate-1 | 並行受付を壊さない予約処理 | 1 | 候補 | 完了 | 100.00/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 86.201 | 231,065 | 両反復・両版で、同時受付・重複再送・容量と保存を扱い、実際の確認を行った。 |
| cedar-current-2 | 並行受付を壊さない予約処理 | 2 | 現行 | 完了 | 100.00/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 98.208 | 300,402 | 両反復・両版で、同時受付・重複再送・容量と保存を扱い、実際の確認を行った。 |
| cedar-candidate-2 | 並行受付を壊さない予約処理 | 2 | 候補 | 完了 | 100.00/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 128.070 | 511,891 | 両反復・両版で、同時受付・重複再送・容量と保存を扱い、実際の確認を行った。 |
| harbor-current-1 | 公開してよい展示ZIPの生成 | 1 | 現行 | 完了 | 92.50/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 60.101 | 190,043 | 両版のZIPは公開対象・図版対応・クレジットを満たす。短い代案比較には凍結基準と原文の要求の強さに解釈差がある。 |
| harbor-candidate-1 | 公開してよい展示ZIPの生成 | 1 | 候補 | 完了 | 92.50/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 81.409 | 300,984 | 両版のZIPは公開対象・図版対応・クレジットを満たす。短い代案比較には凍結基準と原文の要求の強さに解釈差がある。 |
| harbor-current-2 | 公開してよい展示ZIPの生成 | 2 | 現行 | 完了 | 92.50/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 74.534 | 189,402 | 両版のZIPは公開対象・図版対応・クレジットを満たす。短い代案比較には凍結基準と原文の要求の強さに解釈差がある。 |
| harbor-candidate-2 | 公開してよい展示ZIPの生成 | 2 | 候補 | 完了 | 92.50/100.00 | 3 / 3 / 0 | 0 / 0 / 0 | 91.247 | 254,984 | 両版のZIPは公開対象・図版対応・クレジットを満たす。短い代案比較には凍結基準と原文の要求の強さに解釈差がある。 |
| willow-current-1 | 未知の字幕方式と運用の接続 | 1 | 現行 | 完了 | 100.00/100.00 | 4 / 4 / 0 | 0 / 0 / 0 | 32.443 | 80,083 | 両版で音声入口・両言語・両参加者・出力を結ぶ提案をした。引渡しの具体性は原文を基準に裁定し、ライブ運用の成功とは扱わない。 |
| willow-candidate-1 | 未知の字幕方式と運用の接続 | 1 | 候補 | 完了 | 100.00/100.00 | 既知分 3（欠測1） / 4 / 0 | 0 / 0 / 0 | 31.581 | 81,961 | 両版で音声入口・両言語・両参加者・出力を結ぶ提案をした。引渡しの具体性は原文を基準に裁定し、ライブ運用の成功とは扱わない。 |
| willow-current-2 | 未知の字幕方式と運用の接続 | 2 | 現行 | 完了 | 100.00/100.00 | 4 / 4 / 0 | 0 / 0 / 0 | 32.783 | 104,000 | 両版で音声入口・両言語・両参加者・出力を結ぶ提案をした。引渡しの具体性は原文を基準に裁定し、ライブ運用の成功とは扱わない。 |
| willow-candidate-2 | 未知の字幕方式と運用の接続 | 2 | 候補 | 完了 | 87.50/100.00 | 4 / 4 / 0 | 0 / 0 / 0 | 25.773 | 86,531 | 両版で音声入口・両言語・両参加者・出力を結ぶ提案をした。引渡しの具体性は原文を基準に裁定し、ライブ運用の成功とは扱わない。 |
| pebble-current-1 | 既知の小さな末尾修正 | 1 | 現行 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 18.595 | 115,239 | 両版とも指定の末尾だけを変更し、用意されたテストを実行。 |
| pebble-candidate-1 | 既知の小さな末尾修正 | 1 | 候補 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 20.000 | 96,472 | 両版とも指定の末尾だけを変更し、用意されたテストを実行。 |
| pebble-current-2 | 既知の小さな末尾修正 | 2 | 現行 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 20.275 | 96,882 | 両版とも指定の末尾だけを変更し、用意されたテストを実行。 |
| pebble-candidate-2 | 既知の小さな末尾修正 | 2 | 候補 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 19.480 | 115,008 | 両版とも指定の末尾だけを変更し、用意されたテストを実行。 |
| meadow-current-1 | 確定情報からの案内作成 | 1 | 現行 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 16.952 | 76,499 | 両版とも確定情報を維持し、追加の人の作業を要求しなかった。 |
| meadow-candidate-1 | 確定情報からの案内作成 | 1 | 候補 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 23.623 | 117,495 | 両版とも確定情報を維持し、追加の人の作業を要求しなかった。 |
| meadow-current-2 | 確定情報からの案内作成 | 2 | 現行 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 24.671 | 118,425 | 両版とも確定情報を維持し、追加の人の作業を要求しなかった。 |
| meadow-candidate-2 | 確定情報からの案内作成 | 2 | 候補 | 完了 | 100.00/100.00 | 0 / 0 / 0 | 0 / 0 / 0 | 18.382 | 97,861 | 両版とも確定情報を維持し、追加の人の作業を要求しなかった。 |

| 終了状態 | 現行 → 候補 |
| --- | --- |
| 実質課題3件・完了 | 6 → 6 |
| 実質課題3件・失敗 | 0 → 0 |
| 実質課題3件・timeout | 0 → 0 |
| 実質課題3件・中断 | 0 → 0 |
| 実質課題3件・未開始 | 0 → 0 |
| 対照課題2件・完了 | 4 → 4 |
| 対照課題2件・失敗 | 0 → 0 |
| 対照課題2件・timeout | 0 → 0 |
| 対照課題2件・中断 | 0 → 0 |
| 対照課題2件・未開始 | 0 → 0 |
| 全5課題・完了 | 10 → 10 |
| 全5課題・失敗 | 0 → 0 |
| 全5課題・timeout | 0 → 0 |
| 全5課題・中断 | 0 → 0 |
| 全5課題・未開始 | 0 → 0 |

失敗・timeout・中断・未開始を除外・置換していない。資源量で品質低下を相殺しない。

## 負担proxy

| 負担proxy | 実質3件 | 対照2件 | 全5件 |
| --- | --- | --- | --- |
| 不要な確認 | 0 → 0 | 0 → 0 | 0 → 0 |
| 不要な承認依頼 | 0 → 0 | 0 → 0 | 0 → 0 |
| 不要な手作業 | 0 → 0 | 0 → 0 | 0 → 0 |
| 正当な人の選択 | 0 → 0 | 0 → 0 | 0 → 0 |
| 内部記録の修正 | 0 → 0 | 0 → 0 | 0 → 0 |
| 通常のツール失敗 | 4 → 4 | 0 → 0 | 4 → 4 |
| 依頼外の作業 | 0 → 0 | 0 → 0 | 0 → 0 |

実際の人時間・認知負荷は未測定。正当な選択と不要な介入を分け、人の追加回答を仮定しない。

## 資源量

| 資源量 | 現行 → 候補 |
| --- | --- |
| 実質課題3件・wall秒 | 380.443 → 444.281 |
| 実質課題3件・入力 | 1,061,955 → 1,431,274 |
| 実質課題3件・うちcache入力 | 931,712 → 1,302,528 |
| 実質課題3件・非cache入力 | 130,243 → 128,746 |
| 実質課題3件・出力 | 32,526 → 36,142 |
| 実質課題3件・うちreasoning出力 | 14,254 → 15,814 |
| 実質課題3件・総token（入力＋出力） | 1,094,481 → 1,467,416 |
| 対照課題2件・wall秒 | 80.493 → 81.485 |
| 対照課題2件・入力 | 402,396 → 422,742 |
| 対照課題2件・うちcache入力 | 353,536 → 346,112 |
| 対照課題2件・非cache入力 | 48,860 → 76,630 |
| 対照課題2件・出力 | 4,649 → 4,094 |
| 対照課題2件・うちreasoning出力 | 1,473 → 1,107 |
| 対照課題2件・総token（入力＋出力） | 407,045 → 426,836 |
| 全5課題・wall秒 | 460.936 → 525.766 |
| 全5課題・入力 | 1,464,351 → 1,854,016 |
| 全5課題・うちcache入力 | 1,285,248 → 1,648,640 |
| 全5課題・非cache入力 | 179,103 → 205,376 |
| 全5課題・出力 | 37,175 → 40,236 |
| 全5課題・うちreasoning出力 | 15,727 → 16,921 |
| 全5課題・総token（入力＋出力） | 1,501,526 → 1,894,252 |

cache入力はinputの内数、reasoning出力はoutputの内数。総token=input+output。人時間とUSDはnull。不完全な量は報告分であり、確定差・請求額削減率へ換算しない。

## 実行・採点と限界

```json
{
  "model": "gpt-6-sol",
  "effort": "high",
  "host": "Codex CLI 0.163.0（実行パッケージを固定）",
  "entry": "moletta の単一入口。追加の読取・レビュー段階を強制しない",
  "sampling": "5課題×2版×fresh thread 2反復。反復2で版の順序を逆転",
  "execution": "workspace-write / 承認never / ユーザー設定無視 / login shell無効 / shellのlogin引数省略",
  "temporary": "全コマンドにtask-local .scratchへのTMPDIR/TMP/TEMP/TMPPREFIX exportを共通指示。開始前に実動作を確認",
  "limits": "240秒/実行、硬いtoken上限なし。依存ダウンロード・外部調査・委譲・機器操作・モデル変更なし",
  "usage_scope": "各solver実行だけ。準備・採点・報告・実験者の作業費は含まない"
}
```

課題作成者は候補・過去課題を読まない独立文脈。実行前に課題・基準・採否方針・両版を固定。3担当が20結果を匿名のX/Yで採点し、操作記録とbyte一致の成果物を参照。解釈が争点のH2/W3だけ別の独立文脈で原文と照合し、裁定と全原採点を保存。品質に時間やtokenを混ぜない。

- 新規5課題・2条件・各2反復の限定試行です。統計的有意差や広い分野への一般化は示しません。
- 比較単位は通常の入口を含む技能パッケージ全体です。特定の一文やreviewerだけの因果効果を分離しません。
- 警告数、review文字数、テスト数やreviewer数から改善を推定しません。検出と正しい解決を分けます。
- 人の負担は根拠付きの観測proxyです。人時間・認知負荷・USD実費は測定していません。
- Claude、実機性能、無制限のweb探索、本番信頼性、OSが強制する読取隔離についての結論ではありません。
- 入口全文は20/20のnative出力で確認。レビュー参照全文は候補5/10、現行0/10で確認。候補のcedar反復1と対照課題では全文を観測していない。
- これは普通の入口でのroutingを含むパッケージ比較であり、一つの句や独立reviewerの因果効果の分離試験ではない。参照読取も内容の理解・遵守を保証しない。
- 明示した一時領域プロローグは指示であり、OSの読み取り隔離ではない。記録されたコマンドと成果物の範囲を監査した。
- CLIは固定したが、モデル提供側・ホスト負荷は統制していない。各実行の経過時間はCLI開始から終了までで、準備・採点の時間やtokenを含まない。
- 採点用の原本ファイルはbyte一致とmodeを保存。操作ログは匿名化処理を経ており、内容由来の方法・パス等によって盲検性が弱まる可能性がある。
- 本比較前の事前確認1回でheredocの一時ファイル失敗とログ形式の取込不足を検出。元記録を残し、両版共通のインフラを補正して再確認後、20本番は再試行なし。
- installed sourceは20/20でbyteとmodeを維持。記録されたコマンドから範囲外のデータ読取・外部操作は検出しなかったが、全アクセスをOSで隔離したとは主張しない。
- 各課題・各版2回の小規模観測で、統計的な有意差・同等性・今後の全案件への一般化を示さない。
- 未知技術の探索は架空サービスの確定資料棚で、自由なlive web調査ではない。実機・モバイル性能・Claudeの実行は対象外。
- 検出明記が1件不明でも、選択した経路がその欠落を回避していれば未解決とは数えない。分岐に依存する欠落は未採用案へ不要な実装を要求しない。
- 人の負担は質問・承認・手作業などの観測proxy。実際の人時間・認知負荷・USDは未測定。
- 公開要約とhashは完全な生ログ再現セットではなく、推論の正しさや独立性をhashだけで証明しない。
- 比較課題H2は原文より強い要件を含み、引渡しW3にも判定差があった。凍結品質点は原採点を維持するが、その差を候補の優劣や実際の成果未達の根拠に使わない。原文の最小要求に揃える感度確認では、両版とも全20結果が満点相当となり、見落とし改善の結論は変わらない。
- この裁定は採点の解釈差を公開するためであり、新たに結果に合わせた基準で再試行したものではない。評価基準自体の妥当性にも限界が残る。

## 調整担当が供給した判断

**現行版を維持** — 今回の反証型レビューへの常時置換は採用せず、現行版を維持する。成果に残る見落とし・誤検出・人への不要な作業は改善を確認できず、候補は合計時間14.1%、総token26.2%、非cache入力14.7%が増えた。

- 3領域の重要リスクは両版とも解消または依頼範囲内で限定された。候補のUSBリスク明記1件は不明だが、採用した会議音声の経路が回避しており、残存する成果上の欠落の差にはならない。
- 誤検出・結果に関わる誤要求・不要な質問・再承認・手作業は両版0。通常のツール失敗は各4件で復旧し、人の介入へ転嫁していない。
- 現行460.936秒/1,501,526tokenに対し候補525.766秒/1,894,252token。cedar反復2とharbor両反復で候補の時間・総tokenが増えた。willowは候補が速く、対照2件では合計時間がほぼ同じで、すべての課題で悪化したとは言わない。
- 凍結原採点は98.50→97.25/100だが、差は引渡しの表現の解釈に依存する。原文に揃える感度確認では両版100相当。減点を候補の実証された品質低下や追加要件として採否に利用しない。
- 事前に定めた、複数領域での有用な見落とし減少を確認できず、今回観測した追加資源を正当化できない。考え方の普遍的な無効性ではなく、この2ファイル置換を通常入口へ導入する判断だけを見送る。
- 候補は計測用差分として残し、技能・runtime・必須チェック項目へ追加しない。同じ5課題へ合わせて再調整・再試行しない。次の仮説を扱う場合は候補と独立した新しい課題が必要。

供給者: coordinator。描画器は採用判断を計算していない。

## 実ソースと凍結hash

manifest等のファイルhashは実ファイルと照合済み。パッケージhashは供給された方式と共に記載。

```json
{
  "source_packages": {
    "current": {
      "source_revision": "9e1823b9e12dc8bdb3f5549182f317ade858cd56",
      "package_manifest_artifact_id": "package-current",
      "frozen_package_sha256": "171c6f6bd091d3ea313ebc3a3c9f5fe278697656bb4ec15d74c11ebddd130a56",
      "package_hash_method": "凍結したskillsディレクトリのtarアーカイブ全体のSHA-256。個別ファイルのbyte/hashとmodeは別のmanifestで照合する。"
    },
    "candidate": {
      "source_revision": "9e1823b-plus-frozen-two-file-candidate",
      "package_manifest_artifact_id": "package-candidate",
      "frozen_package_sha256": "5a2878c9819c4d1727da1c0fa2d290e3ca61bea39e6518748088182cc345ebf2",
      "package_hash_method": "凍結したskillsディレクトリのtarアーカイブ全体のSHA-256。個別ファイルのbyte/hashとmodeは別のmanifestで照合する。"
    }
  },
  "artifacts": [
    {
      "id": "package-current",
      "role": "current_package_manifest",
      "path": "work/refutation-trial-2/private/source-manifest-current.json",
      "sha256": "67c39b8c84a12e5e3ece4ee4a92f6264b1dca0376190fc458d61258cac6b39ca"
    },
    {
      "id": "package-candidate",
      "role": "candidate_package_manifest",
      "path": "work/refutation-trial-2/private/source-manifest-candidate.json",
      "sha256": "5d69527f0b998569659c0bda961ed5515189ebcf75aaaec329e70ec4bacd4f3e"
    },
    {
      "id": "candidate-change",
      "role": "candidate_change_manifest",
      "path": "work/refutation-trial-2/candidate-manifest.json",
      "sha256": "74238214606742c53e98dd2e9e6e46f2e1d2da428c240903ab253665b566ee73"
    },
    {
      "id": "design-freeze",
      "role": "design_freeze",
      "path": "work/refutation-trial-2/design-freeze.json",
      "sha256": "413c801d641ad79b0465f52288f8658c4fad42fac83dcbe2f0c6909d84e5804c"
    },
    {
      "id": "policy",
      "role": "decision_policy",
      "path": "work/refutation-trial-2/decision-policy.md",
      "sha256": "8a6e7db470dcb0978153878a0695473adfa837e74ed396a7c32ce3812177c02c"
    },
    {
      "id": "suite",
      "role": "case_manifest",
      "path": "work/refutation-trial-2/fresh-suite/suite-manifest.json",
      "sha256": "a04cce17198d62ee3459398c3dda50fb6d755eb4e44cd6f1a09bea46d62ba99a"
    },
    {
      "id": "rubrics",
      "role": "rubric_manifest",
      "path": "work/refutation-trial-2/fresh-suite/evaluator/frozen-index.json",
      "sha256": "c46ff0c8487246618102f16b5e59777a0790bbd3b8500714c7b361c6d66eb9d3"
    },
    {
      "id": "protocol",
      "role": "execution_manifest",
      "path": "work/refutation-trial-2/private/protocol.json",
      "sha256": "529b0d0701367881b6376a1fb9fed4188d1880fd16c038ddbfe8c90c0a576513"
    },
    {
      "id": "execution-raw-manifest",
      "role": "execution_manifest",
      "path": "work/refutation-trial-2/private/raw-record-manifest.json",
      "sha256": "0713e81a78963617f6eff3e96b5147e27217fa1ef9ed4c375fbb1e6e9345c11c"
    },
    {
      "id": "resources",
      "role": "execution_manifest",
      "path": "work/refutation-trial-2/private/normalized-resources.json",
      "sha256": "c3b237b0f8bd6a86f7afba5819ee12e59eb934444a36233e8aa46c199e1f42c8"
    },
    {
      "id": "boundary",
      "role": "boundary_audit",
      "path": "work/refutation-trial-2/private/boundary-audit.json",
      "sha256": "cf66b2c47fe59a82f11d070943dedd143d152362bf5d95d03ec55742e0f74aa9"
    },
    {
      "id": "grade-contract",
      "role": "grading_evidence",
      "path": "work/refutation-trial-2/grading-contract.txt",
      "sha256": "ca9c9bdb920b919e1de0a23e2ae647e0c6ed5bef2cae8a17ff0e1ab0706e9ead"
    },
    {
      "id": "exact-evidence-policy",
      "role": "boundary_audit",
      "path": "work/refutation-trial-2/supplement-policy.json",
      "sha256": "eba77da0921c520ea09eb09f05d596c11019c1e2fdade1cec42c368731a566f4"
    },
    {
      "id": "exact-evidence-index",
      "role": "boundary_audit",
      "path": "work/refutation-trial-2/private/exact-file-transform-index.json",
      "sha256": "8f516db96d978ba2e75925f620913c8f463782866ba17561baff49ac2d91b845"
    },
    {
      "id": "grader-packet-manifest",
      "role": "grading_evidence",
      "path": "work/refutation-trial-2/private/faithful-grader-manifest.json",
      "sha256": "304dbedbee47dc04b25b15f811e7ee0af7e96d1b6f85569a97da7745e0a647a9"
    },
    {
      "id": "scope-adjudication",
      "role": "grading_evidence",
      "path": "work/refutation-trial-2/private/scope-adjudication.json",
      "sha256": "7791813dda6ae9571c7826706dfec39fba1c190b4989f4e238ff936c61d500a1"
    },
    {
      "id": "scope-opinions",
      "role": "grading_evidence",
      "path": "work/refutation-trial-2/private/grades/scope-interpretation.json",
      "sha256": "7b3ff2d9d88054cd9ea03e43e733a8ebd628852d19ff2aa9b0828b4214857f4b"
    },
    {
      "id": "infra-amendment",
      "role": "boundary_audit",
      "path": "work/refutation-trial-2/infrastructure/amendment-v2.json",
      "sha256": "13401c38fa70f915a9ea2155d500a4e31b99c8289fadf38b26660d02fb2488f0"
    },
    {
      "id": "grade-cedar-pebble",
      "role": "grading_evidence",
      "path": "work/refutation-trial-2/private/grades/cedar-pebble.json",
      "sha256": "12cfcc37a30cebc52bab2f5b4afb8c3ddcc6f4fda43935258cca14107e16a8c7"
    },
    {
      "id": "grade-harbor-meadow",
      "role": "grading_evidence",
      "path": "work/refutation-trial-2/private/grades/harbor-meadow.json",
      "sha256": "3c8d2ce69bfaa8b19813ae7c69efb36b2a60a0c31dc0ca53dd7285f4a39311b5"
    },
    {
      "id": "grade-willow",
      "role": "grading_evidence",
      "path": "work/refutation-trial-2/private/grades/willow.json",
      "sha256": "2b5379d37e3d06a8b0f39b6e0527918118dd847b698acc45df03e876d211a952"
    }
  ],
  "notes_ja": [
    "全20枠・両反復・原採点・明示した裁定を保持。凍結資料のhashは改変検出のためで、意味の妥当性の自動認定ではない。"
  ]
}
```

入力SHA-256: `1fc6bb0819eeaac1ed0365075e89432832068b3f77fc4189ec1aaacc7503e178`

描画器SHA-256: `d399e1946a06b37fe1b47e0794f561331f13b2e0cd07a3393c5c564d67b671ff`

## 原採点・裁定・接触と境界

各graderの判断は保持する。以下の要約元指定は、独立した原採点を上書きしない。

<details>
<summary>harbor-current-1</summary>

harbor-meadow: 92.50/100.00 (H1=satisfied, H2=partial, H3=satisfied, H4=satisfied, H5=satisfied, H6=satisfied)

裁定: 原文は別の作り方との短い比較を求めるが、凍結H2は成立する二方式を要求する。独立した追加照合では全4応答が原文の最小要求を満たした。強い採点項目に対する減点を、成果に残る見落としとは扱わない。

要約元: `coordinator`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>harbor-candidate-1</summary>

harbor-meadow: 92.50/100.00 (H1=satisfied, H2=partial, H3=satisfied, H4=satisfied, H5=satisfied, H6=satisfied)

裁定: 原文は別の作り方との短い比較を求めるが、凍結H2は成立する二方式を要求する。独立した追加照合では全4応答が原文の最小要求を満たした。強い採点項目に対する減点を、成果に残る見落としとは扱わない。

要約元: `coordinator`。入口全文の出力を確認。レビュー参照全文の出力も確認。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>harbor-candidate-2</summary>

harbor-meadow: 92.50/100.00 (H1=satisfied, H2=partial, H3=satisfied, H4=satisfied, H5=satisfied, H6=satisfied)

裁定: 原文は別の作り方との短い比較を求めるが、凍結H2は成立する二方式を要求する。独立した追加照合では全4応答が原文の最小要求を満たした。強い採点項目に対する減点を、成果に残る見落としとは扱わない。

要約元: `coordinator`。入口全文の出力を確認。レビュー参照全文の出力も確認。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>harbor-current-2</summary>

harbor-meadow: 92.50/100.00 (H1=satisfied, H2=partial, H3=satisfied, H4=satisfied, H5=satisfied, H6=satisfied)

裁定: 原文は別の作り方との短い比較を求めるが、凍結H2は成立する二方式を要求する。独立した追加照合では全4応答が原文の最小要求を満たした。強い採点項目に対する減点を、成果に残る見落としとは扱わない。

要約元: `coordinator`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>pebble-candidate-1</summary>

cedar-pebble: 100.00/100.00 (P1=satisfied, P2=satisfied, P3=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>pebble-current-1</summary>

cedar-pebble: 100.00/100.00 (P1=satisfied, P2=satisfied, P3=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>pebble-current-2</summary>

cedar-pebble: 100.00/100.00 (P1=satisfied, P2=satisfied, P3=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>pebble-candidate-2</summary>

cedar-pebble: 100.00/100.00 (P1=satisfied, P2=satisfied, P3=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>cedar-candidate-1</summary>

cedar-pebble: 100.00/100.00 (C1=satisfied, C2=satisfied, C3=satisfied, C4=satisfied, C5=satisfied, C6=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>cedar-current-1</summary>

cedar-pebble: 100.00/100.00 (C1=satisfied, C2=satisfied, C3=satisfied, C4=satisfied, C5=satisfied, C6=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>cedar-current-2</summary>

cedar-pebble: 100.00/100.00 (C1=satisfied, C2=satisfied, C3=satisfied, C4=satisfied, C5=satisfied, C6=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>cedar-candidate-2</summary>

cedar-pebble: 100.00/100.00 (C1=satisfied, C2=satisfied, C3=satisfied, C4=satisfied, C5=satisfied, C6=satisfied)

要約元: `grader:cedar-pebble`。入口全文の出力を確認。レビュー参照全文の出力も確認。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>willow-current-1</summary>

willow: 100.00/100.00 (W1=satisfied, W2=satisfied, W3=satisfied, W4=satisfied, W5=satisfied)

要約元: `grader:willow`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>willow-candidate-1</summary>

willow: 100.00/100.00 (W1=satisfied, W2=satisfied, W3=satisfied, W4=satisfied, W5=satisfied)

要約元: `grader:willow`。入口全文の出力を確認。レビュー参照全文の出力も確認。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>willow-candidate-2</summary>

willow: 87.50/100.00 (W1=satisfied, W2=satisfied, W3=partial, W4=satisfied, W5=satisfied)

裁定: 応答はexportを事務局への翌日12時の引渡しへ明示的に接続している。別立ての引渡し担当者・手順まで必須かは原文にもW3にも明示されず、追加の独立照合はmetと判断。解釈が争点のため実証された残存見落としには数えない。

要約元: `coordinator`。入口全文の出力を確認。レビュー参照全文の出力も確認。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>willow-current-2</summary>

willow: 100.00/100.00 (W1=satisfied, W2=satisfied, W3=satisfied, W4=satisfied, W5=satisfied)

要約元: `grader:willow`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>meadow-candidate-1</summary>

harbor-meadow: 100.00/100.00 (M1=satisfied, M2=satisfied, M3=satisfied)

要約元: `grader:harbor-meadow`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>meadow-current-1</summary>

harbor-meadow: 100.00/100.00 (M1=satisfied, M2=satisfied, M3=satisfied)

要約元: `grader:harbor-meadow`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>meadow-current-2</summary>

harbor-meadow: 100.00/100.00 (M1=satisfied, M2=satisfied, M3=satisfied)

要約元: `grader:harbor-meadow`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

<details>
<summary>meadow-candidate-2</summary>

harbor-meadow: 100.00/100.00 (M1=satisfied, M2=satisfied, M3=satisfied)

要約元: `grader:harbor-meadow`。入口全文の出力を確認。レビュー参照全文の出力は観測されず。読取は理解・遵守の証明ではない。

原採点・証拠・裁定の全文は同名JSONの `data.runs` に保持する。

</details>

外部リソース・ブラウザーを使わず、HTML構造とローカルリンクを静的検査した。視覚確認を実施したとは扱わない。以前の報告書は保持している。
