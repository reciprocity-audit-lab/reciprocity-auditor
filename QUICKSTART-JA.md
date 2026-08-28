# クイックスタート

このRelease CandidateはAI APIを使わない、手動受け渡し式のローカルMVPです。Python 3.12以上とWindows PowerShellを使用します。

## 1. 安全確認

提案文やAI回答に、本名、個人メール、住所、実DID、seed、秘密鍵、APIキー、パスワード、ウォレット情報を含めないでください。分析パケットをAIへ渡す前と、生成報告書を利用する前に、必ず人間が内容を確認します。

## 2. PowerShellでフォルダを開く

Release Candidateフォルダをエクスプローラーで開き、フォルダ内でPowerShellを起動します。

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
