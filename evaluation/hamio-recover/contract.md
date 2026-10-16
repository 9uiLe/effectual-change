# hamio Recording 復旧CLI — 共通受け入れ契約

実在する `9uiLe/hamio` の既存 Recording v1 を扱う機能追加であり、既存不具合の修正という主張ではない。開始版は `59a675b4b02478fd75c230263f9ef92a385f069c`（default branch は master）。既存の HTML Report は accepted prefix を表示できる。本課題は、その Event 列を別の有効な Recording へ救出する公開CLIを追加する。

## 公開入口

`hamio presentation recover --input RECORDING --output RECORDING`

両引数は必須のローカル file path。標準入出力を示す `-`、重複・未知の option、値不足は `INVALID_ARGUMENT` / exit 2。既存の help と capabilities に機能を反映する。capabilities の既存 field を維持し、`recording.recover: true` を追加する。

## 救出する内容

- 元ファイルは変更しない。Recording v1 / Presentation Protocol v2 / PresentationSession の既存検証に従い、受理済みの完全な Event 行だけを、元の順序と意味で保存する。Stateから Event を合成しない。
- LF のない最終 fragment を捨て、途中の不正な JSON、UTF-8、shape、version、seq、runId、状態遷移で停止する。不正部分を飛ばして後続を探さない。CRLF、空行、trailer 後の bytes も既存契約に従って分類する。
- 不完全・不正・未知の header は復旧対象とせず、exit 2 で失敗し、最終出力を作らない。有効な header のみの入力は0 Eventの partial として救出できる。
- 出力は既存 Reader が読める canonical Recording v1。header、受理済み Event、count/lastSeqが一致する trailer を持つ。入力 complete は出力 complete、入力 partial / invalid は出力 partial。終端 Run Result があっても、不完全な入力の Recording status を complete に昇格しない。
- Run の running / succeeded / failed / cancelled と Recording の complete / partial / invalid を独立に保つ。終了 Event、時刻、環境、業務結果を補わない。
- 不正な raw 行、未受理の文字列、実行環境の情報を出力ファイルや応答へ含めない。受理済み Event の自由文の自動秘匿は本課題の範囲外。

## 応答

救出成功は exit 0、stdout は1行の JSON、`protocolVersion: 2`、`status: "ok"`。以下の意味を持つ field を返す。

- `runId`, `runState`: 救出した prefix の既存 runSummary と同じ。Run未開始なら両方 null。
- `sourceRecording`: `{recordingVersion: 1, status, eventCount, lastRecordedSeq}`。status は元入力の complete / partial / invalid。不正入力では `issue: {line, code}` を含め、既存 Reader の安全な位置と安定 code に一致させる。
- `recording`: `{recordingVersion: 1, status, eventCount, lastRecordedSeq}`。新出力の status は complete / partial、seq は0 Eventなら null。

失敗は既存と同じ `status: "error", error: {code, message}`。既存出力の衝突・不正引数は exit 2、入出力障害は `IO_ERROR` / exit 7、中断は `INTERRUPTED` / exit 130。未知・不正 header は既存 Protocol の code、exit 2。診断や人向け出力で機械応答を混ぜない。新機能に関係しない応答は変更しない。

## ファイル安全性と資源寿命

- 出力は同じdirectory内で完全に write / sync / close してから排他的に公開する。元ファイルと同じ path、既存 file、symlink、hardlink、競合する作成に対して上書きしない。途中の出力を final path に公開しない。
- 新しい通常ファイルはmacOS/Linux上でmode0600。失敗・中断時は descriptor と一時ファイルを片付け、既存ファイルを保持する。入力が読めない、出力directoryがない、書込み不能の場合を含む。
- 既存の Recording / frame / Session 上限を維持する。全入力や Event 全履歴を保持せず、Stateと有界なframe処理でストリーミングする。入力量はstatic document上限とは独立。中断可能なI/Oでは既存のsignalを伝播する。
- OS crash / power lossへの追加耐久性、入力を他processが同時変更する場合のsnapshot保証、業務の再実行・追記再開、Report UIの変更、配布releaseは範囲外。

## 互換性・完了条件

既存 static / live / report / form、公開 protocol / recording version、制限・検査設定を維持する。Readerに変更があっても既存の読取り結果を保つ。依存追加が不要なら既存手段を使うが、内部の構造や関数名は指定しない。利用者向けの正本とCLI利用手順を更新し、対象テスト・型検査・lint・format・既存全体検査・buildを実行し、実行できないものは明記する。
