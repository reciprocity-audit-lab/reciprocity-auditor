# 3視点の決定的比較・再現デモ

この例は、同じ架空提案についてJustice、Reversal、Towerの3ケースを準備し、検証し、11軸の比較結果を作るまでをWindows PowerShellで再現します。

## 重要な限界

3ケースには同じ固定`analysis-valid.json`を使い、ケースIDだけを各視点へ合わせます。そのため、これはCLI、ハッシュ対応、視点メタデータ、決定的比較の**機械的な再現試験**です。3視点が独立に意味分析を行ったこと、監査精度、完全な公平性を示しません。

意味内容を含む一件の完成例は[`../technocore-room-moderation-demo/`](../technocore-room-moderation-demo/)を参照してください。こちらも架空例であり、Technocoreの公式ルールではありません。

## 実行

リポジトリのルートでPowerShellを開きます。

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\examples\three-perspective-demo\Run-Demo.ps1
```

既定の出力先は`work\three-perspective-demo`です。既に存在する場合は上書きせず停止します。

## 期待される比較集計

[`EXPECTED-SUMMARY.json`](EXPECTED-SUMMARY.json)のとおり、同じ構造化fixtureを使うため10軸が`consistent`、構造化材料のない1軸が`cannot_compare`になります。

`consistent`は共通の見落としがないことを証明しません。`cannot_compare`は問題がないことを意味しません。比較結果は公平性、適法性、採否、執行、処罰の判断ではなく、人間レビューが必要です。

