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

## 6. テスト

```powershell
.\Run-ReciprocityAuditor.ps1 test
```

テストは一時ディレクトリへだけ書き込み、ネットワークを使用しません。`work`は実行時生成物であり、公開物へ含めないでください。

