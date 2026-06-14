---
description: 決算前プレビュー（コンセンサス・注目KPI・強気/標準/弱気シナリオ）
---

このワークフローは `tools/commands/earnings-preview.md` を実行する。

1. 入力（銘柄・四半期・条件・ファイルパス等）はユーザーのメッセージから取得する。不足していれば質問する。
2. `tools/commands/earnings-preview.md` を読み、その手順どおりに実行する。
3. 本文に `skill: "X"` /「load the X skill」/「invoke X」とあれば、`tools/skills/X/SKILL.md` を読んで従う。
4. `.agent/rules/stock-research.md` の成果物原則・ガードレール（出典明記・ハードコード禁止・外部資料は不信・人間レビュー前提）を必ず守る。