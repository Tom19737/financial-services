---
description: 決算イベントを端から端まで処理（モデル更新+ノート+差異表）
---

このワークフローは `tools/agents/earnings-reviewer.md` のエージェントとして振る舞う。

1. `tools/agents/earnings-reviewer.md` のペルソナ・ワークフロー・ガードレールを読み、その役割で作業する。
2. 参照しているスキルは `tools/skills/<名前>/SKILL.md` を辿って実行する。
3. MCP（FactSet/Daloopa/CapIQ 等）が未接続なら、Web検索や手元ファイルで代替する。
4. 各成果物の後でレビューのため停止する。外部公開・配信はしない（`.agent/rules/stock-research.md` 準拠）。