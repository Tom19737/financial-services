# MCP データコネクタ（任意・手動設定）

このプロジェクトのスキルは、外部金融データプロバイダの MCP サーバを利用できる。ただし **MCP は移植可能な「ツール本体」とは別物**であり、以下の理由でクローンだけでは有効化されない。

1. **Antigravity の MCP 設定はユーザーグローバル**に保存される（プロジェクト内ではない）。
   - Windows: `C:\Users\<ユーザー名>\.gemini\antigravity\mcp_config.json`
   - macOS/Linux: `~/.gemini/antigravity/mcp_config.json`
2. **全コネクタが購読契約と認証（APIキー等）必須**。契約がなければ接続できない。
3. 配布元の元ファイルには JSON 構文エラーがあった（`box` エントリ直前のカンマ欠落・閉じ括弧不足）。本ディレクトリの [mcp_config.example.json](mcp_config.example.json) は**修正済み**。

## 設定手順（契約済みプロバイダがある場合のみ）

1. Antigravity の Settings → Customizations → Open MCP Config を開く（上記パスのファイルが開く）。
2. [mcp_config.example.json](mcp_config.example.json) の `mcpServers` から、**契約済みのプロバイダだけ**を既存設定にマージする。
3. 各プロバイダの認証方式に従い、ヘッダ/トークンを設定する（プロバイダ毎に異なる。OAuth の場合は初回接続時にブラウザ認証）。
4. Antigravity を再読み込みし、MCP ツールが利用可能になることを確認する。

## 重要

- **コネクタ未接続でも、本プロジェクトのスキル/ワークフローは動作する**（Web 検索や手元のファイルで代替）。
- APIキー・トークンは**この JSON にハードコードしない**。Antigravity の env/secret 機能、または環境変数経由で渡すこと。設定ファイルはリポジトリにコミットしない（`.gitignore` 済み）。
- HTTP リモート MCP に未対応のクライアントでは、`npx mcp-remote <url>` を stdio ブリッジとして噛ませる必要がある場合がある。

## プロバイダ一覧

| プロバイダ | 用途 | URL |
|---|---|---|
| Daloopa | ファンダメンタルズ・財務データ | `https://mcp.daloopa.com/server/mcp` |
| Morningstar | 投信・株式データ | `https://mcp.morningstar.com/mcp` |
| S&P Global (CapIQ/Kensho) | 企業・市場データ | `https://kfinance.kensho.com/integrations/mcp` |
| FactSet | 企業・市場データ | `https://mcp.factset.com/mcp` |
| Moody's | 信用・リスク | `https://api.moodys.com/genai-ready-data/m1/mcp` |
| MT Newswires | ニュース | `https://vast-mcp.blueskyapi.com/mtnewswires` |
| Aiera | 決算イベント・文字起こし | `https://mcp-pub.aiera.com` |
| LSEG | 債券・スワップ・FX・マクロ | `https://api.analytics.lseg.com/lfa/mcp` |
| PitchBook | 非上場・PE/VC | `https://premium.mcp.pitchbook.com/mcp` |
| Chronograph | PE ポートフォリオ | `https://ai.chronograph.pe/mcp` |
| Egnyte | ドキュメントストア | `https://mcp-server.egnyte.com/mcp` |
| Box | ドキュメントストア | `https://mcp.box.com` |
