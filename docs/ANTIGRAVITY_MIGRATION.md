# Antigravity 移行ガイド（別PCへのクローン手順）

このプロジェクトは、Claude Code のプラグインに依存せず、**クローンするだけで** Antigravity（および AGENTS.md / `.agent` 規約対応の各種エージェントツール）で株式調査ツールが使える形に再構成済み。

## 何が移植され、何が移植されないか

| 項目 | 移植 | 形態 |
|---|---|---|
| スキル本文（手順・知識） | ○ | `tools/skills/<名前>/SKILL.md`（22個） |
| コマンド本文（ワークフロー手順） | ○ | `tools/commands/<名前>.md`（16個） |
| エージェント定義（ペルソナ・手順） | ○ | `tools/agents/<名前>.md`（3個） |
| 常時適用ルール | ○ | `.agent/rules/stock-research.md` |
| スラッシュコマンド | ○ | `.agent/workflows/<名前>.md`（19個） |
| 普遍的エントリ | ○ | ルート `AGENTS.md` |
| **MCP データコネクタ** | **×（手動）** | `mcp/`（設定例のみ。下記参照） |

移植されなかったのは、もともと移植不能な Claude 固有のランタイム機構（プラグイン自動発火、マーケットプレイス、`/plugin:command` 解決、`.mcp.json` 自動配線）。これらは Antigravity ネイティブ層（`.agent/`）と普遍層（`AGENTS.md`）で**等価に再現済み**。

## クローンだけで完了する範囲

`tools/` `.agent/` `AGENTS.md` `docs/` `mcp/` はすべてリポジトリ内にある。**git clone 後、追加インストール不要**で次が使える。

1. Antigravity で clone したフォルダをワークスペースとして開く。
2. `.agent/rules/stock-research.md` が自動適用される（出典明記・人間レビュー前提などのガードレール）。
3. チャットで `/` を入力 → `/dcf` `/comps` `/earnings` 等のワークフローが候補に出る。
4. 例：`/dcf` を選び「トヨタ自動車（7203）」と指定 → `tools/commands/dcf.md` の手順に従い comps→DCF→クロスチェックを実行。

### クローン手順
```bash
git clone <このリポジトリのURL> stock-research
cd stock-research
# Antigravity でこのフォルダを開くだけ。セットアップ不要。
```

## クローンだけで完了しない唯一の例外：MCP

Antigravity の MCP 設定は**ユーザーグローバル**（`~/.gemini/antigravity/mcp_config.json`、Windows は `C:\Users\<ユーザー名>\.gemini\antigravity\mcp_config.json`）に保存される仕様で、プロジェクト内に置けない。さらに全コネクタは購読契約・認証が必要。

→ これは Antigravity 側の仕様による制約であり、**任意機能**。未接続でも全ツールは Web 検索・手元ファイルで動作する。契約済みプロバイダがある場合のみ [mcp/README.md](../mcp/README.md) の手順で手動設定する。

## 他ツール（Cursor / Codex CLI 等）で使う場合

`AGENTS.md` と `tools/` を読めるツールなら、スラッシュ機構が無くても利用可。「`tools/commands/comps.md` に従って ◯◯ の comps を作って」のようにファイルを直接指定して依頼する。`.agent/workflows/` のスラッシュ起動は Antigravity 固有。

## 元の Claude Code 環境との関係

- 旧構成（`.claude/settings.json` のプラグイン有効化）は残置しているが、`.claude/` は `.gitignore` 済みのため**クローンには含まれない**（管理者方針）。
- 旧プラグインを使い続けたい PC では、別途 `claude plugin install ...`（[README.md](../README.md) 参照）を実行する。Antigravity 移行先では不要。

## 同期・更新について

`tools/` は配布元リポジトリの内容を**ある時点でベンダリング（コピー）**したもの。上流が更新されても自動追従しない。更新を取り込む場合は配布元から該当 `SKILL.md` を再コピーする。自社向けにチューニングした場合は、その差分を維持する前提でローカルが正となる。
