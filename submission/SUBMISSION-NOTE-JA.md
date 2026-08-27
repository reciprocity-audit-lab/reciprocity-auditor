# Reciprocity Auditor RC v0.1（privacy-hardened package）— 提出メモ

Reciprocity Auditorの最小オフラインRelease Candidateです。契約条件や協調ルール案をJustice / Reversal / Towerの3視点で検討し、一方的な権限、見落とされた主体、不明確な執行、欠落した異議申立て、証拠不足を、人間が判断する前に整理します。Technocoreその他の協調システムで、説明可能な事前レビューの補助として役立つ可能性があります。

人間の判断を置き換えるものではなく、Technocore公式成果物でもありません。エアドロや報酬の取得を保証しません。Python 3.12以上とWindows PowerShellでローカル再現でき、AI APIを使いません。ソース、テスト、fixture、使用例、プロトコル、Schema、評価記録、チェックサムを同梱しています。

公開ZIPの更新時刻は固定値へ正規化し、同梱する使用例の時刻は合成値へ置換しています。これは不用意なメタデータ露出を減らす措置であり、ネットワークや運営者に対する完全匿名を保証するものではありません。

評価記録は、9ケース、3視点、27評価単位すべて報告上PASSです。Phase 3.3は11軸・99比較単位で、`consistent: 37`、`complementary: 32`、`tension: 18`、`direct_conflict: 0`、`cannot_compare: 12`でした。high優先度6ケースを人間が確認し、6ケースすべて`acceptable_for_release`と記録されました。

既知の限界として、モデル表示名と推論設定は`null`、設定比較可能性は`not_demonstrated`です。Phase 3.3も独立した人間評価ではなく、27/27 PASSは一般的性能や監査精度100%を意味しません。実利用では常に人間レビューが必要です。
