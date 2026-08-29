# クイックスタート

このRelease CandidateはAI APIを使わない、手動受け渡し式のローカルMVPです。Python 3.12以上とWindows PowerShellを使用します。

## 1. 安全確認

提案文やAI回答に、本名、個人メール、住所、実DID、seed、秘密鍵、APIキー、パスワード、ウォレット情報を含めないでください。分析パケットをAIへ渡す前と、生成報告書を利用する前に、必ず人間が内容を確認します。

## 2. PowerShellでフォルダを開く

Release Candidateフォルダをエクスプローラーで開き、フォルダ内でPowerShellを起動します。

```powershell
Get-ChildItem -Name
```

一覧に`Run-ReciprocityAuditor.ps1`が見えることを確認してください。見えない場合は、ZIPの二重フォルダを含む詳しい探索方法を[`docs/WINDOWS-POWERSHELL-GUIDE-JA.md`](docs/WINDOWS-POWERSHELL-GUIDE-JA.md)で確認します。

## 3. 再現用入力を準備する

```powershell
Copy-Item '.\examples\proposal.txt' '.\proposal.txt'
```

## 4. 分析パケットを作る

```powershell
.\Run-ReciprocityAuditor.ps1 prepare --input '.\proposal.txt' --output '.\work\case-001' --case-id 'case-001'
```

`work\case-001\analysis-packet.md`を開き、秘密情報や個人情報がないことを確認します。通常利用では、このファイルを任意のAIへ手動で渡し、説明文やコードフェンスを除いたJSONオブジェクトだけを`work\case-001\analysis.json`へ保存します。

再現試験では固定fixtureを使えます。

```powershell
Copy-Item '.\fixtures\analysis-valid.json' '.\work\case-001\analysis.json'
```

## 5. 検証、報告書生成、人間レビュー、状態確認

```powershell
.\Run-ReciprocityAuditor.ps1 validate --input '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 render --input '.\work\case-001\analysis.json'
.\Run-ReciprocityAuditor.ps1 review --case '.\work\case-001' --state reviewed --reviewer-label 'reviewer-1'
.\Run-ReciprocityAuditor.ps1 status --case '.\work\case-001'
```

`work\case-001\audit-report-ja.md`を人間が確認します。`reviewed`は監査報告を確認したという意味で、元の契約案やルール案を承認したという意味ではありません。

`status`は、人間確認の対象が監査報告書であることと、確認記録が現在の報告書に対応しているかを表示します。新しく記録するレビューには、確認対象報告書のSHA-256が保存されます。

### 確認済み報告書を再生成する場合

`reviewed`状態の報告書は、`--force`だけでは再生成できません。以前の人間確認が`draft`へ戻ることを明示的に確認してください。

```powershell
.\Run-ReciprocityAuditor.ps1 render `
  --input '.\work\case-001\analysis.json' `
  --force `
  --acknowledge-review-reset
```

再生成前の`review.json`と監査報告書は、ケース内の`review-history\`へ連番で保存されます。再生成後は人間確認待ちに戻るため、新しい報告書を読み直してから`review`を再実行してください。履歴はローカル運用記録であり、公開用エクスポートには含まれません。

## 6. テスト

```powershell
.\Run-ReciprocityAuditor.ps1 test
```

テストは一時ディレクトリへだけ書き込み、ネットワークを使用しません。`work`は実行時生成物であり、公開物へ含めないでください。

最小フロー全体を一括再現する場合は次を実行します。

```powershell
.\Verify-LocalWorkflow.ps1
```

`VERIFICATION PASS`と表示されれば、固定fixtureを使った`prepare → validate → render → review → status`が完走しています。これはAIの意味的な監査精度を測るテストではありません。

## 7. レビュー済みケースの公開用エクスポート

`reviewed`状態のケースは、運用時刻を固定値へ正規化し、絶対パスと代表的な秘密情報形式を検査した公開用コピーへ変換できます。元ケースは変更されません。

```powershell
.\Run-ReciprocityAuditor.ps1 export-public `
  --case '.\work\case-001' `
  --output '.\public\case-001' `
  --zip '.\public\case-001.zip'
```

公開用フォルダには提案、分析パケット、分析JSON、監査報告、人間レビュー注記、公開マニフェスト、README、SHA-256一覧が作成されます。`review.json`、状態ファイル、イベントログおよび正確なレビュー日時は収録しません。

検査は誤公開の可能性を減らしますが、完全な匿名性や全秘密情報の検出を保証しません。公開前に出力フォルダの全ファイルを人間が確認してください。出力先またはZIPが既に存在する場合は上書きせず停止します。

## 8. Justice・Reversal・Towerの3視点を比較する

同じ提案から、視点を明示した3つのケースを作ります。提案ファイルが同一ならSHA-256も一致します。

```powershell
.\Run-ReciprocityAuditor.ps1 prepare --input '.\proposal.txt' --output '.\work\case-justice' --case-id 'case-justice' --perspective justice
.\Run-ReciprocityAuditor.ps1 prepare --input '.\proposal.txt' --output '.\work\case-reversal' --case-id 'case-reversal' --perspective reversal
.\Run-ReciprocityAuditor.ps1 prepare --input '.\proposal.txt' --output '.\work\case-tower' --case-id 'case-tower' --perspective tower
```

それぞれの`analysis-packet.md`には、選択した視点の役割が明記されます。各パケットをAIへ個別に手動で渡し、返却されたJSONを各ケースの`analysis.json`へ保存して、3件とも検証します。

```powershell
.\Run-ReciprocityAuditor.ps1 validate --input '.\work\case-justice\analysis.json'
.\Run-ReciprocityAuditor.ps1 validate --input '.\work\case-reversal\analysis.json'
.\Run-ReciprocityAuditor.ps1 validate --input '.\work\case-tower\analysis.json'
```

3件が検証に合格したら、11軸の決定的な構造比較を作成できます。

```powershell
.\Run-ReciprocityAuditor.ps1 compare-perspectives `
  --justice '.\work\case-justice' `
  --reversal '.\work\case-reversal' `
  --tower '.\work\case-tower' `
  --output '.\work\comparison-001'
```

出力は`perspective-comparison.json`と`perspective-comparison-ja.md`です。比較結果は次の5種類です。

- `consistent`: 正規化された構造化項目が一致
- `complementary`: 一方の視点が他方へ項目を追加
- `tension`: 比較可能だが、追加関係だけでは整理できない差異
- `direct_conflict`: 同じ構造化真偽値に明示的な反対値がある
- `cannot_compare`: 比較できる構造化項目がない

この比較は自由記述の意味的同等性を判定しません。`consistent`は共通の見落としがないことを証明せず、`cannot_compare`は問題が存在しないことを意味しません。公平性、善悪、適法性、採否、執行、処罰の判断には使用せず、人間が原文と3つのJSONを確認してください。

## 9. 実行構成と比較レビューを記録する

AI回答を得たとき、モデル表示名または推論設定を画面や実行マニフェストで明示的に確認できた場合だけ記録します。推測値は禁止です。

```powershell
.\Run-ReciprocityAuditor.ps1 record-run-config `
  --case '.\work\case-justice' `
  --evidence-source model_ui `
  --model-display-name '画面に表示された名前' `
  --reasoning-setting '画面に表示された設定'
```

確認できなかった場合は、値を補わず`unavailable`を記録します。

```powershell
.\Run-ReciprocityAuditor.ps1 record-run-config `
  --case '.\work\case-justice' `
  --evidence-source unavailable
```

記録は`analysis.json`のSHA-256へ結び付けられます。記録後に分析JSONが変わった場合、3視点比較は停止します。3視点すべての表示名と推論設定が一致しても、比較出力は「記録された項目が一致」とだけ表示し、未記録設定を含む完全な構成比較可能性は`not_demonstrated`のままです。

3視点比較を確認した人は、匿名ラベルでレビューを記録できます。同じ比較に複数のレビューを追加できます。

```powershell
.\Run-ReciprocityAuditor.ps1 review-comparison `
  --comparison '.\work\comparison-001' `
  --state reviewed `
  --reviewer-label 'reviewer-independent-1' `
  --independence independent `
  --independence-basis '生成と比較に参加していない別の人間が確認'

.\Run-ReciprocityAuditor.ps1 comparison-review-status `
  --comparison '.\work\comparison-001'
```

`independent`は、生成や比較を担当していない別の人間が確認した場合にだけ使用してください。同じ人が生成・比較・確認した場合は`not_independent`、確認できない場合は`unknown`です。独立性は担当者による自己申告であり、ツールが身元や作業分離を外部証拠で検証するものではありません。

比較レビューは比較JSONとMarkdownのSHA-256へ結び付けられます。比較結果が変更されると、`comparison-review-status`は以前のレビューを有効な確認として数えません。この記録は比較結果の確認であり、元提案や各監査報告の承認ではありません。

固定評価シナリオは`fixtures/evaluation-scenarios.json`にあります。不足情報、合理的な非対称性、利益相反、未定義の執行の4種類を収録しています。これは回帰確認用の小規模fixtureであり、一般的な監査精度や完全な公平性を示しません。

## 10. 完成例を確認する

- [`examples/technocore-room-moderation-demo/`](examples/technocore-room-moderation-demo/)：架空提案の意味内容を含む公開完成例
- [`examples/three-perspective-demo/README-JA.md`](examples/three-perspective-demo/README-JA.md)：固定fixtureによる3視点比較の再現例

3視点デモは次で実行できます。

```powershell
.\examples\three-perspective-demo\Run-Demo.ps1
```

## 11. 公開前の人間確認

`export-public`が合格しても、その出力が完全に匿名、安全、正確である保証はありません。公開前に[`docs/PUBLICATION-CHECKLIST-JA.md`](docs/PUBLICATION-CHECKLIST-JA.md)を使い、出力フォルダ内の全ファイルを人間が確認してください。
