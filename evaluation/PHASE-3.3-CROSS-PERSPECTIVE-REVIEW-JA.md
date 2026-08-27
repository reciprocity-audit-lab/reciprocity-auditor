# Reciprocity Auditor Phase 3.3 横断比較レビュー

## 範囲と結論の扱い

Phase 3.2 の9ケース・27評価単位（Justice/Reversal/Tower各9）について、元JSONの構造化フィールドをケース単位で横断比較した探索的レビューである。PASS、総合点、公平判定、元JSONの修正は行わない。

各ケース×比較軸（11軸）を1単位とし、計99比較単位を `CASE-COMPARISON.csv` に記録した。ラベルは入力から追跡可能な比較状態であり、元のPASS数ではない。

| label | 件数（99比較単位） | 用法 |
|---|---:|---|
| consistent | 37 | 同じ論点・方向を確認できる |
| complementary | 32 | 片方の視点が他方にない主体・確認点・質問を補う |
| tension | 18 | posture、欠落情報、論点の強調が異なる |
| direct_conflict | 0 | 同一事実について反対命題を明示するものは確認できない |
| cannot_compare | 12 | 元JSONで同じフィールド・論点が揃わず意味比較できない |

## 観察

- Justiceは主体、基準、即時救済、異議申立てを具体的なfindingとして記録する傾向が強い（11 findings）。Reversalは例外が一時的・確認可能か、対称性の反転で検証する（6 findings）。Towerは運用執行、自己例外、削除・停止・返金の統治可能性を強調する（8 findings）。これは優劣ではなく視点固有の射程である。
- holdout-03、04では3視点が自己例外または運用者の例外を異なる語彙で捉えており、補完関係が最も明瞭である。
- holdout-05、06、08では主体・負担・回復の論点が近接する一方、同じ事実を同じ粒度で記録していないため、部分的な補完または緊張として扱った。
- パイロットで指摘された `undefined_enforcement` はholdout-04（Reversal）・07（Justice）・03（Tower）等に現れる。運用者主体、モデレーター／管理者の分離、異議申立て・参加質問、evidence_gapとcannot_assessの区別は、人間確認項目として残す。ただし過去の弱点に合わせた再判定はしていない。
- `direct_conflict` は、視点の役割が異なるため、reasonable_asymmetry と concerns_require_review の差だけでは付与していない。

## 重要な限界

`model_display_name: null`、`reasoning_setting: null`、`configuration_comparability: not_demonstrated`。同一設定で生成されたこと、別モデルによる独立検証であることは証明できない。今回のoperatorによる意味的比較も人間の独立評価ではない。27/27 PASSは一般的な監査性能100%を意味しない。本レビューは元結果を変更しない探索的評価である。

既存資料は指定範囲のみ読み取り、外部通信・Web・API・Git・subagent・秘密情報へのアクセスは行っていない。

## ケース別要約

| case | Justice | Reversal | Tower | 主な比較上の焦点 |
|---|---|---|---|---|
| holdout-01 | priority_criteria_incomplete; post_event_remedy_missing | findingなし; reasonable_asymmetry | findingなし; 運用基準の不足を欠落情報として記録 | 支援基準と事後救済 |
| holdout-02 | training_access_criteria; operator_exemption_unstated | findingなし; reasonable_asymmetry | findingなし; 参加責任・基準の確認を要求 | 参加、運用者例外、異議申立て |
| holdout-03 | moderator_self_exemption; unrecorded_deletion_no_appeal | moderator-self-exemption | unlogged_unreviewable_removal; manager_self_exemption | 管理者／モデレーター、削除記録、異議申立て |
| holdout-04 | operator_payhold_self_exemption | operator-provider-exemption; undisclosed-quality-hold-criteria | undisclosed_quality_holdback; operator_provider_exemption | 運用者・提供者の自己例外と執行 |
| holdout-05 | intermediate_data_retention_gap | intermediate-data-scope | intermediate_data_retention_gap | データ主体・保存範囲・不足情報 |
| holdout-06 | fixed_limit_connectivity_burden | uniform-access-burden | rigid_access_burden | 一律制限と利用者間負担 |
| holdout-07 | leakage_trigger_and_correction | findingなし; reasonable_asymmetry | isolation_communication_gap | undefined_enforcement、通知・運用者 |
| holdout-08 | service_stop_refund_gap | operator-stop-refund-gap | operator_shutdown_refund_gap | 停止権限、回復・返金、安全イベント |
| holdout-09 | findingなし; reasonable_asymmetry | findingなし; reasonable_asymmetry | findingなし; reasonable_asymmetry | 同一論点の比較可能性が限定的 |

詳細な99行は `CASE-COMPARISON.csv`、差分の根拠は `DISAGREEMENTS.json`、人間向けの問いは `HUMAN-REVIEW-PACKET-JA.md` を参照。
