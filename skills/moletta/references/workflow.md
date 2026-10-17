# 実行と再開

## 記録を使う範囲

重要な設計判断、不確かな実装、複数回にまたがる作業では記録を使う。明確で低リスクな小変更は、変更と相応の実物確認で完了できる。原文、操作履歴、出力の保存は案件の権限・保存方針に従う。

`CORE` は導入された `moletta` 技能の絶対パス、`RUN` は新しい実行ディレクトリ、`FILE` は実際のファイルへ置き換える。コマンドは主担当エージェントが実行する。記録の形式は [record-format.md](record-format.md) を参照する。

## 意図と計画

```sh
python3 CORE/scripts/moletta.py init RUN --brief FILE --goal '達成したい成果'
```

`brief.md` は原文のコピー、`intent.json` は成果・受入条件・人の必須制約である。意図を確認して埋め、封印する。

```sh
python3 CORE/scripts/moletta.py seal RUN
```

封印後の意図は編集しない。人が目的・必須制約を変える場合は、新しい実行を作り、変更理由と参照元を残す。

`plan.json` に要求、全体案、資料、実験、レビュー、判断、次の行動を記す。分解や方式は根拠に応じて更新できる。全案共通の要求と、方式固有の義務を分ける。案の `subject` には対象の実装・設定の識別子と版を記し、追跡すべきローカル入力を明示する。

`next_action` には問い、理由、時間予算、終了条件を一つ記す。実験を選ぶ場合はその ID を対応させる。

```sh
python3 CORE/scripts/moletta.py check RUN --stage plan
python3 CORE/scripts/moletta.py check RUN --stage decide
```

`plan` は計画の対応、`decide` は出典を使った調査・原文レビュー・案の選択条件も調べる。必要な段階だけ使う。出力は意味上の完了宣言ではない。

## コマンドを観測する

実験条件を計画に書いてから実行する。`capture` は実行前の条件を固定し、実際の出力と終了状態を保存する。シェルの解釈を介さず argv を渡す。

```sh
python3 CORE/scripts/moletta.py capture RUN --experiment V1 --timeout 30 --cwd PROJECT -- COMMAND ARG
```

`--cwd` を省略すると呼び出し元の作業ディレクトリを使う。タイムアウトでは POSIX のプロセス群を停止し、観測を残す。

## ホストの操作ツールを観測する

ブラウザー・画面・機器などは、ホストにあるツールで操作する。先に観測を開始する。

```sh
python3 CORE/scripts/moletta.py begin RUN --experiment V1
```

返された observation ID を保持し、実際に対象へ到達、操作、結果の観測を行う。そのツールの生の出力・操作履歴を UTF-8 ファイルへ保存し、必要な画像や結果ファイルを添付する。

```sh
python3 CORE/scripts/moletta.py record RUN --observation OBS --transcript TRACE --method '使用したツールと観測方法' --artifact IMAGE
```

`--artifact` は任意で複数回指定できる。実際の出力を説明文で置き換えず、取得できなかった観測を作らない。取り込みは `attested_native` として保存される。Moletta 自体が対象を操作したことや、そのファイルが本物のツール出力であることを認証する手順ではない。

取り込みの保存が失敗した場合は、取得済みの同じ履歴を使って `record` を再試行できる。対象の操作を自動で繰り返す手順ではない。コマンド取得の保存に失敗した場合も、実行済みの作用を確認してから次の行動を選ぶ。

## 観測を判定する

どちらの取得方法でも、観測と実物を読み、事前の基準に対して一回の判定を付ける。

```sh
python3 CORE/scripts/moletta.py assess RUN --observation OBS --result pass --reason '事前の合格条件と観測の対応'
```

判定は `pass / fail / inconclusive`。終了コード 0 を自動合格にはしない。失敗・不明を後から合格へ書き換えず、別の適用可能な合格観測で解消を明示する。

```sh
python3 CORE/scripts/moletta.py assess RUN --observation NEW_OBS --result pass --reason '再確認した結果' --resolves OLD_OBS
python3 CORE/scripts/moletta.py check RUN --stage verify
```

`verify` は選択案の対象環境で、全要求に合格観測があるかを調べる。さらに、成果ごとに、その成果へ対応する要求をすべて含む `end_to_end` の合格観測を必要とする。対象・実験・追跡入力が異なる観測は、現在の条件の根拠にしない。原文の欠落や観測の妥当性は別に読み直す。

## 有限の探索と再開

```sh
python3 CORE/scripts/moletta.py next RUN
python3 CORE/scripts/moletta.py checkpoint RUN
```

`next` は修正すべき不整合、選択した案に関係する未完了・未判定・未解消の観測、宣言した次の行動を示す。自動実行や権限の追加ではない。予算と終了条件に達したら、証拠に基づく継続、条件付き判断、構成の再検討、外部の不足の提示から選び、`next_action` を更新または null にする。

中断前は計画を更新して checkpoint を作る。再開時は原文、封印した意図、計画、観測を読み、対象や環境の変化を確認して `next` から続ける。一つの実行ディレクトリを複数担当で編集しない。
