# pstack再調査とP1採用の設計判断

## 結論と位置づけ

[Issue #12](https://github.com/9uiLe/effectual-change/issues/12)のP1候補を、**既存の意思決定ループに組み込む条件付きの技法**として試験的に採用する。5原則、行動選択、探索停止条件、担当者の権限境界は変更しない。新しいSkill、固定工程、外部CLI、Hook、サブエージェントは追加しない。

これは原典と現行Skillの差分に基づく設計判断であり、**改善効果を実証した採用ではない**。実務での追加負担に見合うかというIssue #12の受け入れ条件は未達のまま。以下の比較で、維持・縮小・撤回を判断する。

## 再調査した資料

2026-10-16に確認した原版は、Lauren TanによるCursor公式の[pstack](https://github.com/cursor/plugins/tree/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack)。Issue #12の参照版 `99743e9c151c8537cbbf1f98bb38f34ef3368453` から今回の `f713f14203cd6420cec13cd7c55c32d598dbab68` までの[比較](https://github.com/cursor/plugins/compare/99743e9c151c8537cbbf1f98bb38f34ef3368453...f713f14203cd6420cec13cd7c55c32d598dbab68)では、`pstack/` 内に差分はなかった。Git Trees APIでも、両版の `pstack` ツリーSHAが `0d5fd349cbc77d054eed60f0e8cdfbea86321ff9` で一致することを確認した。

| 原版の一次資料 | 確認した機構 | 今回の適用範囲 |
| --- | --- | --- |
| [how](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/how/SKILL.md) / [why](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/why/SKILL.md) / [epistemics](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/why/references/epistemics.md) | 動作の説明と歴史的な理由の調査を分け、意図の直接的な記述と推測を区別する。`why` は広い並列調査を既定とする。 | 背景が今の設計判断を変えるときだけ履歴を調べる。全情報源の探索や独自の確信度ラベルは採用しない。 |
| [blast-radius](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/blast-radius/SKILL.md) | 参照元一覧に留まらず、データ形式・副作用など差分外への経路を追い、安全性が依存する事実を実コードで検証する。 | 重要な回帰リスクに限り、維持対象・影響経路・安全性の仮説・反証する検証をつなぐ。網羅調査や複数モデルのレビューは義務化しない。 |
| [prove-it-works](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/principle-prove-it-works/SKILL.md) / [bug-fix](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/poteto-mode/playbooks/bug-fix.md) / [perf-issue](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/poteto-mode/playbooks/perf-issue.md) / [benchmark-checklist](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/benchmark-checklist/SKILL.md) | 実物の確認、同じ対象での不具合再確認、測定条件・誤差・処理の実行の確認を重視する。 | 受け入れ条件に応じて検証を選び、対象・操作・結果を結びつける。原版の委譲・モデル指定・固定実行回数は持ち込まない。 |

補助資料の[移植版README](https://github.com/michael-denyer/pstack-claude/blob/1dba27e50e8f18f146bb80f137f0690f8d773c2e/README.md)と[差分宣言](https://github.com/michael-denyer/pstack-claude/blob/1dba27e50e8f18f146bb80f137f0690f8d773c2e/tools/forks.json)も確認した。移植版には各実行環境向けのHook・モデル設定や、人間の判断の引用に関する独自方針がある。これらを原版の仕様とは扱わず、今回の依存にもしない。

原版の文章・コードは移植せず、機構の比較から独自に記述する。著作物を複製・改変する場合は、別途[原版のMITライセンス](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/LICENSE)の条件を満たす必要がある。

## 現行との差分と配置

現行Skillには既に、事実と推測の区別、影響範囲、回帰検証、実行していないテストを成功としない規則がある。禁止事項を言い換えて増やすのではなく、**どの根拠を、いつ、どう確かめるか**を具体化する。

| 判断 | 現行に不足している接続 | 実装先 |
| --- | --- | --- |
| 現在の動作と過去の意図 | 意図を調べる条件、当時の理由が今も有効かの確認 | [意思決定ループ](../skills/effectual-change/references/decision-loop.md)の調査方針。既存の4ラベルで扱う。 |
| 変更境界と安全性 | 影響経路から安全性の仮説を選び、それを否定できる検証へつなぐ方法 | 同資料の変更境界の具体化。[任意テンプレート](../skills/effectual-change/assets/change-decision.md)の既存欄に補う。 |
| 受け入れ条件と検証結果 | バグ・性能・UIで異なる検証対象と、結果が支える主張の範囲 | 同資料の対象別検証。[SKILL.md](../skills/effectual-change/SKILL.md)から条件付き技法へ誘導し、任意テンプレートの検証欄を具体化する。 |

軽微な変更に履歴調査・性能測定・UI操作を一律に課さない。新しい記録形式は作らず、詳細資料もインストール対象のSkillディレクトリ内で自己完結させる。この設計文書は配布Skillの必読資料にはしない。

### 見送る案

- **評価ツールだけを追加してSkillを変えない：** [実行証拠監査器](../evaluation/trace-evidence/audit.py)は既にあるが、設計時に選ぶ根拠と検証対象は決めない。今回はその接続を試す。監査器の拡張はしない。
- **全playbook・独立Skill・自動ルーティング：** 状態に応じて次の行動を選ぶ既存の構造に重複し、実行環境依存と保守範囲を増やす。
- **必須の意思決定ログ・振り返り・ルール自動追加：** P2として保留。既存の任意テンプレートを使い、単発の失敗を根拠に規則を増やさない。
- **何もせず追加観察だけを続ける：** 効果の実証には必要だが、今回は実装依頼を受け、現行との差分を検証可能な小さな候補として用意する。仮説を実装したことと効果を確認したことは分ける。

## 観察との関係・未検証事項

[Issue #17の実務試行](https://github.com/9uiLe/effectual-change/issues/17#issuecomment-6212932032)では、許可すべき入力に近い負例の見落としと、イベントで裏付けられない修正後テスト実行の報告があった。これは検証すべき問題の手掛かりであり、**P1の追加で防げることを示す証拠ではない**。独立レビュー後の修正・成功をAgentの成果に算入しない。歴史的意図の調査や性能検証の有効性も、この事例からは判断できない。

### 実務での比較方法

比較対象は「Skillなし／あり」ではなく、**従来Skill O／この最小差分を含むSkill N**とする。既存の[plugin-catalog評価](../evaluation/plugin-catalog/README.md)は機能8ケースの採点であり、今回の判断の質をそのまま測れるとは扱わない。

Oは[実装前のコミット](https://github.com/9uiLe/effectual-change/tree/4f5edab5bb7e632b5227d4a8dacaa44eefe676ab/skills/effectual-change)を基準とし、Nはこの差分を含むコミットを試行前に固定する。製品側の開始コミットとSkill側の版は別々に記録する。

1. 実在する変更課題を選び、開始コミット・モデル・変更要求・利用可能ツールをそろえた別セッションでO/Nを実行する。O/NのSkillコミットを固定し、管理者設定等の露出差と実行順序も記録する。片側の結果・独立レビューを他方へ渡さない。
2. 課題の受け入れ条件と重要な維持対象を、比較前に権限者の要件・関連Issue等から確定する。必要な履歴上の根拠、負例、測定条件を独立レビューで確認し、Agentに採点用の答えを渡さない。架空の事例ファイルは作らない。
3. 採点者は可能な範囲でO/Nを伏せ、下表を実行記録と初回差分から評価する。差分が本当に検証対象だったか、報告と結果が一致するかを確認し、後からの修正は別に記録する。
4. 成果と負担を併記し、単独試行・同点・交絡が残る比較はINCONCLUSIVEとする。小さな変更で不要な履歴探索や記録が増えた場合も悪化として扱う。異なる実務課題で繰り返し観測してから、維持・縮小・撤回を判断する。許容負担の閾値は事前に担当者と決め、結果を見てAIが発明しない。

| 観点 | 記録・照合するもの |
| --- | --- |
| 意図と仕様の区別 | 根拠のない意図・仕様の断定、必要な背景を見逃した設計判断、不要な履歴探索の有無 |
| 安全性 | 初回差分の受け入れ達成・回帰、重要な安全性の仮説と負例が検証されたか |
| 検証の適合性 | 要求と同じ対象・条件で確かめたか、実行記録で支持されない成功報告の有無、未検証範囲の明示 |
| 負担と追跡性 | 所要時間・トークン（取得可能な範囲）、調査・実験・質問回数、重要な判断から根拠へ遡れるか。モデル・キャッシュ・実行順序等の交絡も併記 |

生ログ・認証情報・非公開のコードや会話は公開しない。監査器の出力も公開前に確認する。

### この実装で確認できる範囲

既存のオフラインテストで、Skillの共通形式・自己完結性・導入手順・評価ツールの回帰を確認する。文書リンクの検査対象にはこの設計文書も含める。これらは**配布構造の検証**であり、指示が理解されること、判断が改善すること、追加負担が許容されることを保証しない。Codex / Claude Codeの新たな実機比較は別途必要で、Issue #12をこの実装だけで完了扱いにしない。
