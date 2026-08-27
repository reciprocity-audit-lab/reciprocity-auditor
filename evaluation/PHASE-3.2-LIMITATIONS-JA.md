# Phase 3.2 制約

- この集約は、指定された3結果ZIPと記録済みの検証情報だけを対象にした。
- `reported_result` は各ZIP内の既存検証記録 `PASS` の取り込みであり、再採点ではない。
- rubricの読み取り・比較、意味的な横断評価、生成JSONの修正、期待結果への調整は行っていない。
- `model_display_name` と `reasoning_setting` は全タスクで `null`。`configuration_comparability` は `not_demonstrated` であり、同一モデル・同一推論設定だったとは証明されていない。
- したがって、本結果は総合精度や完全な公平性の証明ではなく、あらゆる契約を正しく監査できることも示さない。
- `human_review_required: true` を維持しており、人間の確認を代替しない。
- 外部通信、Web検索、API、Git、Technocore、FLOP、X、DID、ウォレット、秘密鍵、seedには接触していない。
- 既存のPhase 3.2ソース、評価パック、指定結果ZIPは変更していない。
- Phase 3.2の決定的集約で停止し、プロトコル修正、意味的横断評価、公開、Phase 3.3以降には進まない。
