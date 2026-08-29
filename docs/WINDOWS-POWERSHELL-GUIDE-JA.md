# Windows PowerShell完全手順

この手順は、ZIPを初めて展開する人が、プログラム本体を見つけ、テストと最小フローをローカルで再現するためのものです。外部通信、APIキー、DID、ウォレットは使用しません。

## 1. ZIPを展開して本体フォルダを確認する

ZIPを右クリックして「すべて展開」を選びます。展開後、`Run-ReciprocityAuditor.ps1`が見えるフォルダがプログラム本体です。ZIP名と同名のフォルダが二重になっている場合は、内側のフォルダまで開いてください。

PowerShellで現在位置を確認します。

```powershell
Get-Location
Get-ChildItem -Name
```

一覧に`Run-ReciprocityAuditor.ps1`がなければ、展開先から探せます。

```powershell
$runner = Get-ChildItem -LiteralPath "$env:USERPROFILE\Downloads" `
  -Recurse -File -Filter 'Run-ReciprocityAuditor.ps1' `
  -ErrorAction SilentlyContinue |
  Select-Object -First 1

$runner.FullName
Set-Location -LiteralPath $runner.Directory.FullName
```

`$runner.FullName`が空なら、ZIPをまだ展開していないか、Downloads以外へ展開しています。検索対象だけを実際の展開先へ変更してください。

## 2. このPowerShell画面だけ実行を許可する

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

`Process`指定なので、このPowerShell画面を閉じると設定は元へ戻ります。

## 3. Pythonを確認する

```powershell
python --version
```

Python 3.12以上が必要です。複数のPythonがある場合は、実行ファイルを指定できます。

```powershell
.\Run-ReciprocityAuditor.ps1 -PythonPath 'C:\path\to\python.exe' test
```

この例の`C:\path\to\python.exe`は説明用です。実在するPythonのパスへ置き換えてください。公開文書やIssueへ、自分のWindowsユーザー名を含む絶対パスを貼らないでください。

## 4. 自動テストを実行する

```powershell
.\Run-ReciprocityAuditor.ps1 test
```

すべて`OK`になれば、Pythonコードの回帰テストは合格です。

## 5. 完全な最小フローを一括確認する

```powershell
.\Verify-LocalWorkflow.ps1
```

このスクリプトは一時フォルダ内で`prepare → validate → render → review → status`を実行し、最後に`現在状態: reviewed`を確認して、一時生成物を削除します。固定fixtureを使う再現試験であり、AIの意味的性能を測るものではありません。

## 6. 手動で一段ずつ試す

詳しい入力方法と3視点比較は[`../QUICKSTART-JA.md`](../QUICKSTART-JA.md)を参照してください。最初は固定fixtureを使い、動作確認後に自分の提案へ進むのが安全です。

## よくあるエラー

### `Run-ReciprocityAuditor.ps1`が認識されない

現在のフォルダがプログラム本体ではありません。`Get-ChildItem -Name`でスクリプトが見える場所へ移動してください。ZIPを開いただけで展開していない場合も実行できません。

### `else`がコマンドとして認識されない

PowerShellでは`if { ... } else { ... }`を一つのまとまりとして貼り付ける必要があります。`if`ブロックだけを先に実行したあと、別入力で`else`を実行しないでください。本書の探索手順は`if/else`を使わない形にしています。

### `report_exists`

同じケースの報告書が既にあります。内容を変更しないなら再生成は不要です。確認済み報告書を意図的に再生成する場合だけ、以前の確認が`draft`へ戻ることを理解したうえで次を使います。

```powershell
.\Run-ReciprocityAuditor.ps1 render `
  --input '.\work\case-001\analysis.json' `
  --force `
  --acknowledge-review-reset
```

### 文字化けする

Windows PowerShell 5.1では、ファイルをUTF-8で保存してください。ラッパーはPythonをUTF-8モードで起動します。エディターで`analysis.json`を保存するときもUTF-8を選びます。

### 公開前に何を確認するか

[`PUBLICATION-CHECKLIST-JA.md`](PUBLICATION-CHECKLIST-JA.md)を使って、公開用出力フォルダの全ファイルを人間が確認してください。

