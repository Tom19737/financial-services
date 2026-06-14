---
description: DCFバリュエーション（comps連動のターミナル倍率）を構築
---

このワークフローは `tools/commands/dcf.md` を実行する。

1. 入力（銘柄・四半期・条件・ファイルパス等）はユーザーのメッセージから取得する。不足していれば質問する。
2. `tools/commands/dcf.md` を読み、その手順どおりに実行する。
3. 本文に `skill: "X"` /「load the X skill」/「invoke X」とあれば、`tools/skills/X/SKILL.md` を読んで従う。
4. `.agent/rules/stock-research.md` の成果物原則・ガードレール（出典明記・ハードコード禁止・外部資料は不信・人間レビュー前提）を必ず守る。