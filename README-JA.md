# Reciprocity Auditor — Release Candidate v0.1（privacy-hardened package）

Reciprocity Auditorは、契約条件、コミュニティルール、方針、協調ルール案を、相互性、合理的な非対称性、執行、救済、影響主体の観点から検討するための、オフラインの手動受け渡し式ツールです。AIが善悪、適法性、採否、処罰を最終決定するものではありません。

本成果物はPhase 1〜3.3から構成した最小限の公開リリース候補です。Technocoreの公式成果物ではなく、エアドロその他の報酬取得を保証しません。

この配布物では、ZIP内の更新時刻を固定値へ正規化し、パッケージの正確な作成時刻を省略しています。同梱する使用例とfixtureの時刻は固定された合成値です。実行時に生成されるケースファイルには運用時刻が含まれるため、公開前に別途確認してください。

## 3つの視点

- **Justice**: 主体、権利、利益、責任、負担、危険、不足情報、救済を整理し、非対称性に関連性と比例性のある理由があるかを問います。
- **Reversal**: 影響主体の立場を交換し、同じ根拠が交換後にも成立するかを検討します。一方的な権限・免責・義務を探しつつ、合理的な非対称性の可能性を残します。
- **Tower**: 誰が判断、執行、監督するか、自己例外がないか、通知、記録、異議申立て、停止、返金、回復手続が定義されているかを検討します。

3視点は構造化レビューの補助であり、公平点や最終結論ではありません。すべての報告書に人間レビューが必要です。

## ローカルMVPの流れ

APIは使用しません。利用者がローカルで分析パケットを作り、任意のAIへ手動で渡し、返却されたJSONだけをローカルへ保存して、検証、Markdown報告書生成、人間レビュー状態の記録を行います。

```text
提案 → prepare → AIへの手動受け渡し → validate → render → 人間レビュー → status
```

Webサービス、Technocore、Git、DID、ウォレットへ接続しません。入力には秘密情報、個人情報、実DID、認証情報、ウォレット情報を含めないでください。

## 必要環境

- Windows PowerShell 5.1またはPowerShell 7
- Python 3.12以上
- 追加Pythonパッケージ不要
- ネットワーク接続不要

## Windows PowerShellでの最小実行

このフォルダでPowerShellを開いて実行します。

```powershell
Copy-Item '.\examples\proposal.txt' '.\proposal.txt'
.\Run-ReciprocityAuditor.ps1 prepare --input '.\proposal.txt' --output '.\work\case-001' --case-id 'case-001'
Copy-Item '.\fixtures\analysis-valid.json' '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 validate --input '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 render --input '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 review --case '.\work\case-001' --state reviewed --reviewer-label 'reviewer-1'
.\Run-ReciprocityAuditor.ps1 status --case '.\work\case-001'
```

fixtureのコピーは再現確認用です。通常利用では、`analysis-packet.md`を人間が確認してAIへ手動で渡し、JSON回答を`analysis.json`として保存します。`reviewed`は監査報告を人間が確認した状態であり、元提案の承認を意味しません。

代表的な入出力:

- 入力: [`examples/smoke-case/proposal.txt`](examples/smoke-case/proposal.txt)
- 手動受け渡し用パケット: [`examples/smoke-case/analysis-packet.md`](examples/smoke-case/analysis-packet.md)
- 構造化回答: [`examples/smoke-case/analysis.json`](examples/smoke-case/analysis.json)
- 生成報告書: [`examples/smoke-case/audit-report-ja.md`](examples/smoke-case/audit-report-ja.md)

詳しい手順は[`QUICKSTART-JA.md`](QUICKSTART-JA.md)を参照してください。

## 明示的な3視点ワークフロー

`prepare --perspective justice|reversal|tower`を使うと、選択した視点の役割を分析パケットとケース記録へ明示できます。同じ提案に対する3つの検証済み結果は、`compare-perspectives`で11軸の決定的な構造比較へ変換できます。

比較分類は`consistent`、`complementary`、`tension`、`direct_conflict`、`cannot_compare`の5種類です。自由記述の意味的同一性を推測せず、明示的な反対の構造化真偽値がある場合だけ`direct_conflict`とします。比較結果は人間レビューの材料であり、どの視点が正しいか、公平か、適法か、採択・執行・処罰すべきかを決めません。

Windowsでの完全な手順は[`QUICKSTART-JA.md`](QUICKSTART-JA.md)の「Justice・Reversal・Towerの3視点を比較する」を参照してください。

## 評価記録

`record-run-config`は、画面表示、実行マニフェスト、または明示的なoperator記録で確認できたモデル表示名と推論設定だけを、分析JSONのSHA-256へ結び付けて記録します。確認不能な場合は`unavailable`として`null`を保存し、値を推測しません。

3視点の記録項目が一致しても、未記録設定を含む完全な構成同一性は示されないため、`configuration_comparability`は`not_demonstrated`のままです。比較結果には、記録項目が`recorded_fields_match`、`recorded_fields_differ`、`incomplete`のどれかを別に表示します。

`review-comparison`は、比較JSONとMarkdownのSHA-256に結び付いた複数の人間レビューを匿名ラベルで記録できます。独立性は`independent`、`not_independent`、`unknown`の自己申告であり、ツールが保証するものではありません。

回帰用の[`fixtures/evaluation-scenarios.json`](fixtures/evaluation-scenarios.json)は、不足情報、合理的な非対称性、利益相反、未定義の執行を扱います。肯定的な結果には常に限界事項を併記し、限定的なfixtureから一般的な監査精度を主張しません。

## 評価実績

Phase 3.2の決定的集約は9ケースをJustice / Reversal / Towerの3視点で扱い、27評価単位すべてが報告上PASSでした。Phase 3.3は11軸・99比較単位で、`consistent: 37`、`complementary: 32`、`tension: 18`、`direct_conflict: 0`、`cannot_compare: 12`でした。その後、high優先度6ケースを人間が確認し、6ケースすべてが`acceptable_for_release`と記録されました。

ただし、次の制約があります。

- `model_display_name: null`
- `reasoning_setting: null`
- `configuration_comparability: not_demonstrated`
- Phase 3.3も独立した人間評価ではありません。
- 27/27 PASSは一般的性能100%、監査精度100%、完全な公平性の証明を意味しません。
- 同一モデル・同一推論設定での比較や、独立した異種モデル評価だったことは実証されていません。

解釈前に[`evaluation/README.md`](evaluation/README.md)と[`LIMITATIONS.md`](LIMITATIONS.md)を確認してください。

## 安全性と適用範囲

AI出力は検討を補助する資料です。人間が原文、証拠、代替解釈、不足情報、影響を確認しなければなりません。法的助言ではなく、採択、拒否、執行、処罰を自動化してはいけません。

安全・プライバシー資料は[`SECURITY.md`](SECURITY.md)、[`docs/phase1/PRIVACY-MODEL-JA.md`](docs/phase1/PRIVACY-MODEL-JA.md)、[`docs/phase1/SAFETY-AND-LIMITS-JA.md`](docs/phase1/SAFETY-AND-LIMITS-JA.md)にあります。

## ライセンス

[MIT License](LICENSE)で提供します。
