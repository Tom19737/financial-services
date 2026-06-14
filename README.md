# Stock Research

[anthropics/financial-services](https://github.com/anthropics/financial-services)(Claude for Financial Services)の仕組みを活用した株式調査(エクイティリサーチ)プロジェクト。決算分析・カバレッジ開始・モデル更新・セクター/テーマ調査・バリュエーションモデリングのワークフローを提供する。

**2通りの使い方を同梱:**

- **Antigravity 等（推奨・ポータブル）** — ツールに依存しない形に再構成済み。**クローンするだけ**で利用可能。→ [AGENTS.md](AGENTS.md) / 移行手順 [docs/ANTIGRAVITY_MIGRATION.md](docs/ANTIGRAVITY_MIGRATION.md)
- **Claude Code プラグイン（初期導入時の構成）** — マーケットプレイス経由（下記）。`.claude/` は `.gitignore` 済みのためクローンには含まれない。

各機能の解説は [docs/機能ガイド.md](docs/機能ガイド.md)。

## ディレクトリ構成（ポータブル層）

```
AGENTS.md                  普遍的エントリ（Antigravity 標準・要クローンのみ）
tools/skills/<名前>/SKILL.md  実作業の本体（22スキル）
tools/commands/<名前>.md      コマンド本文（16）
tools/agents/<名前>.md        エージェント定義（3）
.agent/rules/              Antigravity 常時適用ルール
.agent/workflows/          Antigravity スラッシュコマンド（19）
mcp/                       外部データMCP設定例（任意・手動・要契約）
docs/                      機能ガイド・移行ガイド
```

---

## （参考）Claude Code プラグイン構成

## 導入済み構成

マーケットプレイス `claude-for-financial-services` を **project スコープ**で登録し、株式調査に直結する 5 プラグインを有効化済み([.claude/settings.json](.claude/settings.json))。

| プラグイン | 種別 | 内容 |
|---|---|---|
| `financial-analysis` | コア(必須) | DCF / comps / LBO / 3-statement モデル、競合分析、Excel 監査、デッキ QC。全 MCP コネクタの定義元 |
| `equity-research` | バーティカル | 決算ノート、カバレッジ開始、モデル更新、投資仮説・カタリスト管理 |
| `market-researcher` | エージェント | セクター/テーマ → 業界概観・競合環境・peer comps・アイデアショートリスト |
| `earnings-reviewer` | エージェント | 決算コール+開示 → モデル更新 → ノート草案 |
| `model-builder` | エージェント | DCF / LBO / 3-statement / comps を Excel 上で構築 |

常時消費トークンは合計 約6.2k tok/セッション。

## 使い方

プラグインは**次回セッション開始時**に有効化される。利用形態は3つ。

### 1. スラッシュコマンド(明示的に起動)

`/プラグイン名:コマンド名` で呼び出す。

- equity-research: `/equity-research:earnings` `/equity-research:earnings-preview` `/equity-research:initiate` `/equity-research:model-update` `/equity-research:morning-note` `/equity-research:screen` `/equity-research:sector` `/equity-research:thesis` `/equity-research:catalysts`
- financial-analysis: `/financial-analysis:dcf` `/financial-analysis:comps` `/financial-analysis:lbo` `/financial-analysis:3-statement-model` `/financial-analysis:competitive-analysis` `/financial-analysis:debug-model` `/financial-analysis:ppt-template`

### 2. エージェント(ワークフロー一括実行)

Task/サブエージェントとして `market-researcher` `earnings-reviewer` `model-builder` を起動。各エージェントは成果物ごとにレビューのため停止し、人間の承認を挟む設計。

### 3. スキル(関連作業時に自動発火)

`dcf-model` `comps-analysis` `earnings-analysis` `initiating-coverage` `sector-overview` `competitive-analysis` `xlsx-author` `pptx-author` など、文脈に応じて自動的に参照される。

## データコネクタ(MCP)について

`financial-analysis` は外部データプロバイダ向け MCP コネクタ(Daloopa, Morningstar, S&P Global/CapIQ, FactSet, Moody's, MT Newswires, Aiera, LSEG, PitchBook, Chronograph, Egnyte, Box)を定義しているが、**現状は未接続**:

1. いずれも購読契約と API キー/認証が必要(未契約のため利用不可)。
2. 配布元の `.mcp.json` に JSON 構文エラーがあり、現バージョンではサーバーが読み込まれない(`claude plugin details` で MCP servers 0 表示)。

コネクタ未接続でもコマンド/スキル/エージェントは動作する(Web 検索や手元データで代替)。将来データプロバイダを契約した場合は、当該コネクタのみを project の `.mcp.json` に正しい JSON で個別追加し、API キーは環境変数経由で渡すこと(本文・設定にハードコードしない)。

## セットアップ再現手順

`.claude/` はコミット対象外(管理者方針)のため、別環境では以下を再実行する。

```bash
claude plugin marketplace add anthropics/financial-services --scope project
claude plugin install financial-analysis@claude-for-financial-services --scope project
claude plugin install equity-research@claude-for-financial-services   --scope project
claude plugin install market-researcher@claude-for-financial-services  --scope project
claude plugin install earnings-reviewer@claude-for-financial-services  --scope project
claude plugin install model-builder@claude-for-financial-services      --scope project
```

## 留意事項

本リポジトリのエージェントは**アナリストの作業成果物の草案**(モデル、メモ、リサーチノート)を作成するもので、投資助言・推奨や取引執行は行わない。全出力は有資格者によるレビュー・承認が前提。出力の検証と、自社に適用される法令・規制の遵守は利用者の責任。
